"""Terrain horizon on SYNTHETIC analytic surfaces (test fixtures, not lunar data).

Each case has a closed-form answer from spherical geometry, so the ray-marcher,
the DEM sampling and both grid layouts are checked without any real file.
"""
import numpy as np
import pytest

from slipday import dem as D
from slipday import terrain as T
from slipday.ephem import cached_table, grid_start, parse_utc
from slipday.geometry import Horizon, Site, disc_fraction, segment_fraction, track
from slipday.metrics import Criteria, find_events, span_stats

R = D.MOON_RADIUS_M


@pytest.mark.parametrize("h0", [2.0, 10.0, 100.0, 1000.0])
def test_flat_sphere_gives_the_dip_of_the_horizon(h0):
    dem = D.synthetic_polar(D.flat(0.0), half_width_km=150, pixel_m=200)
    p = T.horizon_profile(dem, -89.0, 30.0, mast_m=h0, max_km=110)
    expected = -np.rad2deg(np.arccos(R / (R + h0)))
    assert p.el_deg.shape == (720,)
    assert np.allclose(p.el_deg, expected, atol=2e-4)
    assert expected == pytest.approx(T.sphere_dip_deg(R + h0))


def test_dip_is_minus_1p94_deg_at_one_kilometre():
    assert T.sphere_dip_deg(R + 1000.0) == pytest.approx(-1.9435, abs=1e-3)


def _cone_case(distance_km, height_m, az_deg, site=(-88.0, 45.0), pixel_m=100.0, half=160.0):
    la, lo = T.destination(site[0], site[1], np.deg2rad(az_deg), distance_km * 1000.0 / R)
    dem = D.synthetic_polar(D.cone(float(la), float(lo), height_m, 20.0), half_width_km=half, pixel_m=pixel_m)
    return dem, site


@pytest.mark.parametrize("distance_km,height_m,az_deg,mast_m", [(30.0, 1500.0, 70.0, 2.0), (50.0, 2000.0, 200.0, 2.0),
                                                                (50.0, 2000.0, 200.0, 10.0),
                                                                (100.0, 2000.0, 310.0, 3000.0)])
def test_cone_of_known_height_at_known_distance(distance_km, height_m, az_deg, mast_m):
    """Apex elevation angle must follow the spherical formula, curvature included."""
    dem, site = _cone_case(distance_km, height_m, az_deg)
    p = T.horizon_profile(dem, site[0], site[1], mast_m=mast_m, max_km=140)
    theta = distance_km * 1000.0 / R
    expected = np.rad2deg(np.arctan2((R + height_m) * np.cos(theta) - (R + mast_m), (R + height_m) * np.sin(theta)))
    i = int(np.argmax(p.el_deg))
    assert p.az_deg[i] == pytest.approx(az_deg, abs=0.51)
    # bilinear sampling rounds the apex off by a few metres: allow 0.012 deg
    assert p.el_deg[i] == pytest.approx(expected, abs=0.012)
    assert p.dist_km[i] == pytest.approx(distance_km, abs=0.6)
    flat_plane = np.rad2deg(np.arctan2(height_m - mast_m, distance_km * 1000.0))
    assert flat_plane - expected > 0.4          # a flat-plane formula would be wrong by this much or more
    # away from the cone the horizon is the dip of the sphere for this observer height
    opposite = int(np.argmin(np.abs(p.az_deg - ((az_deg + 180.0) % 360.0))))
    assert p.el_deg[opposite] == pytest.approx(T.sphere_dip_deg(R + mast_m), abs=3e-4)


def test_a_2_km_peak_100_km_away_is_hidden_from_a_2_m_observer():
    """Curvature drops the surface 2.9 km at 100 km, so the apex sits at -0.5 deg,
    below the observer's own horizon (-0.087 deg).  A flat-plane model would put it at +1.1 deg."""
    dem, site = _cone_case(100.0, 2000.0, 310.0)
    p = T.horizon_profile(dem, site[0], site[1], mast_m=2.0, max_km=140)
    assert np.allclose(p.el_deg, T.sphere_dip_deg(R + 2.0), atol=2e-4)
    theta = 100e3 / R
    apex = T.elevation_angle_deg(theta, R + 2000.0, R + 2.0)
    assert -0.6 < apex < -0.4


def test_ridge_against_a_dense_one_dimensional_reference():
    """A long east-west ridge with a Gaussian cross-section, checked against the
    same surface sampled every 5 m along the ray (no grid involved)."""
    crest_lat, sigma_km, height = -86.0, 3.0, 1800.0

    def ridge(lat, lon):
        d = (np.asarray(lat) - crest_lat) * np.pi / 180.0 * R / 1000.0
        return height * np.exp(-0.5 * (d / sigma_km) ** 2)

    dem = D.synthetic_equirect(ridge, ppd=64, lat_top=-80.0, lat_bottom=-90.0)
    site = (-87.5, 10.0)
    p = T.horizon_profile(dem, site[0], site[1], mast_m=10.0, n_az=360, max_km=120, min_step_m=200.0)
    z0 = float(ridge(site[0], site[1]))
    d = np.arange(5.0, 120000.0, 5.0)
    lat = site[0] + np.rad2deg(d / R)          # due north along the meridian
    ref = T.elevation_angle_deg(d / R, R + ridge(lat, site[1]), R + z0 + 10.0).max()
    assert p.el_deg[0] == pytest.approx(ref, abs=0.02)
    assert p.el_deg[0] > 1.0 and p.el_deg[180] < 0.0


def test_equirect_and_polar_grids_agree_on_the_same_surface():
    shape = D.cone(-87.0, 100.0, 2500.0, 25.0)
    polar = D.synthetic_polar(shape, half_width_km=200, pixel_m=200)
    globe = D.synthetic_equirect(shape, ppd=128, lat_top=-82.0, lat_bottom=-90.0)
    a = T.horizon_profile(polar, -88.2, 60.0, mast_m=2.0, n_az=360, max_km=100)
    b = T.horizon_profile(globe, -88.2, 60.0, mast_m=2.0, n_az=360, max_km=100, min_step_m=200.0)
    assert np.abs(a.el_deg - b.el_deg).max() < 0.03
    assert a.el_deg.max() > 0.5


def test_height_sampling_matches_the_generating_function():
    shape = D.cone(-88.0, 20.0, 3000.0, 30.0)
    polar = D.synthetic_polar(shape, half_width_km=120, pixel_m=250)
    rng = np.random.default_rng(1)
    lat = -90 + rng.uniform(0.2, 3.5, 300)
    lon = rng.uniform(-180, 180, 300)
    assert np.abs(polar.height_m(lat, lon) - shape(lat, lon)).max() < 15.0   # cone slope 0.1 x half a pixel
    x, y = polar.project(lat, lon)
    la2, lo2 = polar.unproject(x, y)
    assert np.allclose(la2, lat, atol=1e-9) and np.allclose(np.mod(lo2 - lon + 180, 360) - 180, 0, atol=1e-7)
    assert np.isnan(polar.height_m(np.array([-80.0, 85.0]), np.array([0.0, 0.0]))).all()   # off grid, wrong pole


def test_composite_uses_the_fine_grid_first_and_the_coarse_one_beyond_it():
    fine = D.synthetic_polar(D.flat(100.0), half_width_km=30, pixel_m=100, name="fine")
    coarse = D.synthetic_equirect(D.flat(0.0), ppd=8, name="coarse")
    both = D.CompositeDEM(members=[fine, coarse])
    h = both.height_m(np.array([-89.9, -85.0, 10.0]), np.array([0.0, 0.0, 0.0]))
    assert h[0] == pytest.approx(100.0) and h[1] == pytest.approx(0.0) and h[2] == pytest.approx(0.0)
    assert both.member_at(-89.9, 0.0) is fine and both.member_at(-85.0, 0.0) is coarse
    assert "SYNTHETIC" in both.label()
    # standing on a 100 m plateau 30 km across, over a sphere: horizon is the plateau edge or the sphere beyond
    p = T.horizon_profile(both, -89.95, 0.0, mast_m=2.0, n_az=72, max_km=200)
    assert p.coverage_km.min() > 190 and not p.floor_used.any()
    assert np.all(p.el_deg < 0)


def test_profile_cache_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "CACHE_DIR", str(tmp_path))
    dem, site = _cone_case(30.0, 1500.0, 70.0)
    a = T.cached_profile(dem, site[0], site[1], 2.0, n_az=180, max_km=60)
    assert len(list(tmp_path.iterdir())) == 1
    b = T.cached_profile(dem, site[0], site[1], 2.0, n_az=180, max_km=60)
    assert np.array_equal(a.el_deg, b.el_deg) and b.dem["synthetic"] is True and b.mast_m == 2.0
    c = T.cached_profile(dem, site[0], site[1], 10.0, n_az=180, max_km=60)
    assert len(list(tmp_path.iterdir())) == 2 and not np.array_equal(a.el_deg, c.el_deg)


def test_outside_the_dem_is_an_error_not_a_guess():
    dem = D.synthetic_polar(D.flat(0.0), half_width_km=50, pixel_m=500)
    with pytest.raises(ValueError):
        T.horizon_profile(dem, -80.0, 0.0)


# ---------------------------------------------------------------- solar disc

def test_disc_fraction_on_a_level_horizon_matches_the_segment_formula():
    hz = Horizon(profile_az_deg=np.arange(0, 360, 1.0), profile_el_deg=np.full(360, 1.0))
    el = 1.0 + np.linspace(-0.3, 0.3, 25)
    f = disc_fraction(hz, np.full(25, 123.0), el, 0.266, n_strips=15)
    assert np.abs(f - segment_fraction(el - 1.0, 0.266)).max() < 0.012
    assert f[0] == 0.0 and f[-1] == 1.0 and f[12] == pytest.approx(0.5, abs=1e-9)
    assert np.all(np.diff(f) >= 0)


def test_disc_fraction_sees_a_notch_narrower_than_the_disc():
    az = np.arange(0, 360, 0.1)
    el = np.where(np.abs(az - 90.0) < 0.1, 0.0, 2.0)     # a 0.2 deg wide gap in a 2 deg wall
    hz = Horizon(profile_az_deg=az, profile_el_deg=el)
    f = float(disc_fraction(hz, [90.0], [1.0], 0.266, n_strips=31)[0])
    assert 0.2 < f < 0.6                                   # only the strip in the gap shows
    assert float(disc_fraction(hz, [95.0], [1.0], 0.266)[0]) == 0.0


def test_terrain_changes_sunrise_and_the_smooth_result_is_kept():
    """A wall to the east delays sunrise; the smooth-sphere twin is unchanged."""
    az = np.arange(0, 360, 1.0)
    wall = np.where((az > 45) & (az < 135), 5.0, 0.0)
    smooth = Site("s", 0.0, 0.0)
    walled = Site("w", 0.0, 0.0, horizon=Horizon(profile_az_deg=az, profile_el_deg=wall, source="SYNTHETIC wall"))
    table = cached_table(grid_start(parse_utc("2026-01-01T00:00:00Z")), 24 * 60, 3600)
    r0 = [e["unix"] for e in find_events(smooth, track(smooth, table), "sun") if e["type"] == "sunrise"]
    r1 = [e["unix"] for e in find_events(walled, track(walled, table), "sun") if e["type"] == "sunrise"]
    delay_h = (r1[0] - r0[0]) / 3600.0
    assert 9.0 < delay_h < 10.6                            # 5 deg at 0.508 deg/h
    assert walled.horizon.describe()["model"] == "terrain" and smooth.horizon.describe()["model"] == "smooth sphere"


def test_sun_rule_fractions_order_the_sunrise_times():
    az = np.arange(0, 360, 1.0)
    hz = Horizon(profile_az_deg=az, profile_el_deg=np.zeros(360), source="SYNTHETIC level")
    site = Site("x", 0.0, 0.0, horizon=hz)
    table = cached_table(grid_start(parse_utc("2026-01-01T00:00:00Z")), 24 * 40, 3600)
    t = {}
    for f in (0.0, 0.5, 1.0):
        c = Criteria(min_sun_fraction=f)
        ev = find_events(site, track(site, table, f), "sun", crit=c)
        t[f] = [e["unix"] for e in ev if e["type"] == "sunrise"][0]
    assert t[0.0] < t[0.5] < t[1.0]
    assert (t[1.0] - t[0.0]) / 3600.0 == pytest.approx(2 * 0.266 / 0.508, abs=0.15)   # one disc diameter


def test_span_stats_on_an_elevated_polar_observer():
    """SYNTHETIC: an observer whose horizon is 2 deg below level near the pole is lit far more than the sphere says."""
    az = np.arange(0, 360, 1.0)
    low = Site("ridge", -89.45, -137.3, horizon=Horizon(profile_az_deg=az, profile_el_deg=np.full(360, -2.0), source="SYNTHETIC -2 deg"))
    flat = Site("sphere", -89.45, -137.3)
    a = span_stats(low, "2027-01-01", 365)
    b = span_stats(flat, "2027-01-01", 365)
    assert a["any_light_pct"] > 95 and 45 < b["any_light_pct"] < 60
    assert a["longest_dark_h"] < 24 * 10 and b["longest_dark_h"] > 24 * 120
    assert b["longest_below_rule_h"] == pytest.approx(164.7 * 24, abs=30)   # the reviewer's 164.7-day dark run
    assert a["mean_disc_fraction_pct"] <= a["any_light_pct"]
    assert b["centre_up_pct"] == pytest.approx(52.0, abs=0.5)     # the reviewer's smooth-sphere figure
    assert set(a) >= {"lit_pct", "longest_light_h", "earth_visible_pct", "longest_earth_outage_h"}
