"""The 3-D view's data (/api/terrain3d, slipday/view3d.py): the height patch is the real grid, the shadow
agrees with the site's own skyline, bad input is refused, and missing terrain is said plainly.

Three groups: no DEM installed (what conftest sets up), the labelled SYNTHETIC fixture, and the real LOLA
grids (skipped when they are not installed; the 80 m ones skip without the 231 MB grid)."""
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from slipday import api, demstore, hindcast, load, moonmap, sites, view3d
from slipday.api import app
from slipday.ephem import compute_table, parse_utc
from slipday.geometry import track_at
from slipday.sites import get_site
from slipday.terrain import destination

client = TestClient(app)
REAL_DEM = os.environ.get("SLIPDAY_REAL_DEM_DIR", "")
HAVE_REAL = os.path.exists(os.path.join(REAL_DEM, "dems.json"))
HAVE_80 = os.path.exists(os.path.join(REAL_DEM, "ldem_80s_80m_f32.npy"))
needs_real = pytest.mark.skipif(not HAVE_REAL, reason="real LOLA grids are not installed (run scripts/prepare_dem.py)")
needs_80 = pytest.mark.skipif(not (HAVE_REAL and HAVE_80), reason="the 80 m grid is not installed (run scripts/fetch_grid80.py)")
LANDING = "2026-11-18T00:00:00Z"            # the default example: Shackleton connecting ridge C1
CLEAR_MARGIN_DEG = 0.1                      # "by a clear margin": the Sun's centre this far above or below the skyline


def _reset():
    demstore.reload()
    sites._terrain_profile.cache_clear()
    hindcast.hindcast.cache_clear()
    api._stats.cache_clear()
    moonmap._cache.clear()
    moonmap._layer_cache.clear()
    view3d.clear_cache()


@pytest.fixture()
def synthetic_dem(monkeypatch):
    monkeypatch.setenv("SLIPDAY_SYNTHETIC_DEM", "1")
    _reset()
    yield
    monkeypatch.delenv("SLIPDAY_SYNTHETIC_DEM")
    _reset()


@pytest.fixture()
def real_dem():
    old = os.environ.get("SLIPDAY_DEM_DIR")
    os.environ["SLIPDAY_DEM_DIR"] = REAL_DEM
    os.environ.pop("SLIPDAY_SKIP_DEMS", None)
    _reset()
    yield demstore.get_dem()
    os.environ["SLIPDAY_DEM_DIR"] = old
    os.environ.pop("SLIPDAY_SKIP_DEMS", None)
    _reset()


def _get(**params):
    return client.get("/api/terrain3d", params=params)


def _centre_clearance(dem, site, unix):
    """Sun-centre clearance (deg) at the site from one 3-D shadow ray per instant, with the module's own settings."""
    la, lo = np.full(len(unix), site.lat), np.full(len(unix), site.lon)
    h = dem.height_m(la, lo)
    sun = compute_table(unix).sun
    az, el = np.empty(len(unix)), np.empty(len(unix))
    for i in range(len(unix)):
        a, e, _ = view3d.sun_from_cells(la[i:i + 1], lo[i:i + 1], sun[i])
        az[i], el[i] = a[0], e[0]
    step0 = float(dem.member_at(site.lat, site.lon).resolution_m)
    return el - view3d.cell_horizon(dem, la, lo, h, az, 2.0, step0)


# ------------------------------------------------------------------ no terrain installed, and bad input

def test_without_terrain_the_view_says_so_plainly():
    r = _get(site="shackleton", at=LANDING)
    assert r.status_code == 200
    assert r.json() == {"available": False, "reason": "no terrain data installed"}


@pytest.mark.parametrize("params, field", [
    (dict(site="shackleton", at="not a date"), "at"),
    (dict(at=LANDING), "site"),                                   # neither an id nor coordinates
    (dict(lat=-89.5, at=LANDING), "site"),                        # latitude without longitude
    (dict(site="shackleton", at=LANDING, half_km=50), "half_km"),
    (dict(site="shackleton", at=LANDING, half_km=0.2), "half_km"),
    (dict(site="shackleton", at=LANDING, n=5), "n"),
    (dict(site="shackleton", at=LANDING, n=400), "n"),
    (dict(lat=95, lon=0, at=LANDING), "lat"),
    (dict(lat=-89, lon=720, at=LANDING), "lon"),
    (dict(site="shackleton", at=LANDING, mast_m=-1), "mast_m"),
    (dict(site="shackleton", at="2060-01-01"), "ephemeris"),      # past the end of DE421
    (dict(site="shackleton"), "at"),                              # no time at all
])
def test_bad_input_is_refused_with_422_and_names_the_field(params, field):
    r = _get(**params)
    assert r.status_code == 422, r.text
    assert field in r.text


def test_unknown_site_id_is_a_404(synthetic_dem):
    assert _get(site="no_such_site", at=LANDING).status_code == 404


# ------------------------------------------------------------------ the SYNTHETIC fixture (not lunar data)

def test_synthetic_patch_is_labelled_synthetic_and_a_site_off_the_grid_says_no_coverage(synthetic_dem):
    j = _get(site="shackleton", at=LANDING, n=41).json()
    assert j["available"] and j["dem"]["synthetic"] is True and "SYNTHETIC" in j["dem"]["label"]
    assert j["skyline"]["synthetic"] is True
    # Apollo 11 is outside the polar test surface: no heights are invented for it
    k = _get(site="apollo11", at=LANDING).json()
    assert k["available"] is False and k["reason"] == "no terrain data covers this site"
    assert k["site"]["name"].startswith("Apollo 11") and "heights_m" not in k and "shadow" not in k


def test_on_a_cone_the_side_facing_the_sun_is_lit_and_the_far_side_is_dark(synthetic_dem):
    """The fixture has a 1500 m cone, 12 km in radius, with its apex under this site: a 7.1 degree slope.
    The Sun stands about 1 degree high, so the flank towards it is lit and the flank behind the apex is not."""
    n, half = 41, 4.0
    j = _get(site="shackleton", at=LANDING, n=n, half_km=half).json()
    assert 0.5 < j["sun"]["el_deg"] < 1.6 and j["sun"]["up"] is True
    assert j["heights_m"][(n * n) // 2] == 0.0 and j["site"]["height_m"] == pytest.approx(1500, abs=60)
    shade = j["shadow"]["shade"]
    assert len(shade) == n * n and set(shade) <= set("0123456789")
    az = np.deg2rad(j["sun"]["az_deg"])
    sp = j["spacing_m"]

    def cell(dist_m, sign):
        col = int(round((n - 1) / 2 + sign * dist_m * np.sin(az) / sp))
        row = int(round((n - 1) / 2 - sign * dist_m * np.cos(az) / sp))        # row 0 is the northern edge
        return int(shade[row * n + col])

    for d in (1000.0, 2000.0, 3000.0):
        assert cell(d, +1) >= 5, f"the flank {d:g} m towards the Sun should be lit"
        assert cell(d, -1) < 5, f"the flank {d:g} m behind the apex should be in shadow"
    assert 25.0 < j["shadow"]["lit_share_pct"] < 75.0
    assert j["shadow"]["lit_cells"] == sum(c >= "5" for c in shade) and j["shadow"]["cells"] == n * n


# ------------------------------------------------------------------ the real LOLA grids

@needs_80
def test_the_patch_is_the_real_grid(real_dem):
    dem = real_dem
    j = _get(site="shackleton", at=LANDING).json()
    s = get_site("shackleton")
    n, sp = j["n"], j["spacing_m"]
    assert j["available"] and n == 81 and sp == 100.0 and j["half_km"] == 4.0 and len(j["heights_m"]) == n * n
    assert j["dem"]["label"].startswith("LOLA, 80 m/px") and j["dem"]["synthetic"] is False and j["dem"]["interpolated"] is False
    assert "LDEM_80S_80MPP_ADJ" in j["dem"]["provenance"]
    z0 = float(dem.height_m(np.array([s.lat]), np.array([s.lon]))[0])
    assert j["site"]["height_m"] == round(z0, 1) and j["heights_m"][(n * n) // 2] == 0.0
    # a few cells against the grid itself, placed independently of the module: so many metres along a compass bearing
    c = (n - 1) // 2
    for row, col in ((c, c + 10), (c - 10, c), (c + 7, c - 24), (0, 0), (n - 1, n - 1), (5, 70)):
        east, north = (col - c) * sp, (c - row) * sp
        la, lo = destination(s.lat, s.lon, np.arctan2(east, north), np.array(np.hypot(east, north) / 1737400.0))
        want = float(dem.height_m(np.array([float(la)]), np.array([float(lo)]))[0]) - z0
        assert j["heights_m"][row * n + col] == pytest.approx(want, abs=0.06), (row, col)
    assert j["height_range_m"] == [min(j["heights_m"]), max(j["heights_m"])]
    # at 101 points per side the cells are 80 m apart, the spacing of the grid itself
    assert _get(site="shackleton", at=LANDING, n=101, heights=False).json()["spacing_m"] == 80.0


@needs_80
def test_sun_and_earth_are_the_apps_own_numbers(real_dem):
    j = _get(site="shackleton", at=LANDING).json()
    s = get_site("shackleton")
    tr = track_at(s, [parse_utc(LANDING).timestamp()], 0.5)
    assert j["sun"]["az_deg"] == round(float(tr.sun_az[0]), 2) and j["sun"]["el_deg"] == round(float(tr.sun_el[0]), 3)
    assert j["sun"]["clear_deg"] == round(float(tr.sun_clear[0]), 3) and j["sun"]["up"] is bool(tr.sun_lit[0] > 0)
    assert j["earth"]["el_deg"] == round(float(tr.earth_el[0]), 3) and j["earth"]["up"] is bool(tr.earth_clear[0] > 0)
    assert j["sun"]["skyline_km"] is not None and j["sun"]["skyline_el_deg"] == pytest.approx(j["sun"]["el_deg"] - j["sun"]["clear_deg"], abs=0.002)
    assert j["sun"]["skyline_el_deg"] == pytest.approx(float(s.horizon.elevation_at(tr.sun_az)[0]), abs=0.002)
    assert "DE421" in j["directions"] and j["skyline"]["model"] == "terrain" and j["shadow"]["observer_m"] == 2.0
    assert "centre of the Sun's disc" in j["shadow"]["rule"]


@needs_80
def test_centre_cell_agrees_with_the_site_skyline_over_the_default_window(real_dem, capsys):
    """Shackleton connecting ridge C1, landing 18 Nov 2026 00:00 UTC, 14 days, hourly."""
    dem = real_dem
    s = get_site("shackleton", 0.0, 2.0, True)
    unix = parse_utc(LANDING).timestamp() + np.arange(0, 14 * 24 + 1) * 3600.0
    tr = track_at(s, unix, 0.5)
    clear = _centre_clearance(dem, s, unix)
    agree = (clear > 0) == (tr.sun_clear > 0)
    clear_cut = np.abs(tr.sun_clear) > CLEAR_MARGIN_DEG
    with capsys.disabled():
        print(f"\n  3-D centre cell against the site skyline, C1, 14 days hourly: {int(agree.sum())} of {len(unix)} hours agree "
              f"({int(clear_cut.sum())} of them with the Sun more than {CLEAR_MARGIN_DEG} deg from the skyline); "
              f"largest clearance difference {float(np.abs(clear - tr.sun_clear).max()):.3f} deg")
    assert agree[clear_cut].all()                       # never wrong when the margin is clear
    assert agree.mean() >= 0.99
    assert float(np.abs(clear - tr.sun_clear).max()) < 0.15
    # and the frames themselves carry the same centre value as the one-ray computation
    for k in (0, 100, 336):
        f = view3d.shadow_frame(dem, s.lat, s.lon, 4.0, 33, 2.0, float(unix[k]))
        assert f["centre_clear_deg"] == pytest.approx(float(clear[k]), abs=2e-3)
        assert (int(f["shade"][(33 * 33) // 2]) >= 5) == bool(tr.sun_clear[k] > 0)


@needs_80
def test_centre_cell_agrees_where_the_sun_really_sets(real_dem, capsys):
    """The default window never brings the Sun within 1.6 deg of the skyline at C1, so the same check is run
    where the Sun rises and sets: the IM-1 site over its landing window, and the Malapert shoulder for 60 days."""
    dem = real_dem
    for sid, landing, days in (("im1", "2024-02-22T23:00:00Z", 14), ("malapert_earth", LANDING, 60)):
        s = get_site(sid, 0.0, 2.0, True)
        unix = parse_utc(landing).timestamp() + np.arange(0, days * 24 + 1) * 3600.0
        tr = track_at(s, unix, 0.5)
        clear = _centre_clearance(dem, s, unix)
        app_lit = tr.sun_clear > 0
        agree = (clear > 0) == app_lit
        clear_cut = np.abs(tr.sun_clear) > CLEAR_MARGIN_DEG
        with capsys.disabled():
            print(f"\n  {sid}, {days} days hourly: the app has the Sun's centre up for {int(app_lit.sum())} of {len(unix)} hours; "
                  f"the 3-D centre cell agrees on {int(agree.sum())}")
        assert 0.2 < app_lit.mean() < 0.95               # a window with real sunrises and sunsets
        assert agree[clear_cut].all() and agree.mean() >= 0.99


@needs_80
def test_frames_are_stored_and_the_slider_request_leaves_the_heights_out(real_dem):
    before = load.lanes()["escalated"]
    a = _get(site="shackleton", at="2026-11-20T06:00:00Z", n=40, heights=False)       # an even n becomes the next odd one
    assert a.status_code == 200
    j = a.json()
    assert j["n"] == 41 and "heights_m" not in j and len(j["shadow"]["shade"]) == 41 * 41 and j["shadow"]["cached"] is False
    assert load.lanes()["escalated"] == before + 1       # a new frame is slow work: it went through the cold lane
    k = _get(site="shackleton", at="2026-11-20T06:00:00Z", n=40, heights=False).json()
    assert k["shadow"]["cached"] is True and k["shadow"]["shade"] == j["shadow"]["shade"]
    assert load.lanes()["escalated"] == before + 1       # the stored frame answered from the light lane
    assert j["at_utc"] == "2026-11-20T06:00:00Z" and j["sun"]["az_deg"] != _get(site="shackleton", at=LANDING, n=40, heights=False).json()["sun"]["az_deg"]


@needs_real
def test_on_the_240m_fallback_the_view_says_the_grid_is_coarser_than_its_cells(real_dem):
    os.environ["SLIPDAY_SKIP_DEMS"] = "ldem_80s_80m"
    _reset()
    try:
        j = _get(site="shackleton", at=LANDING, n=41).json()
        assert j["available"] and j["dem"]["label"].startswith("LOLA, 240 m/px")
        assert j["spacing_m"] == 200.0 and j["dem"]["interpolated"] is True and j["shadow"]["first_sample_m"] == 240.0
    finally:
        os.environ.pop("SLIPDAY_SKIP_DEMS", None)
        _reset()
