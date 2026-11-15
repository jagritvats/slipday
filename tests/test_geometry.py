"""Physical sanity checks on the Sun/Earth geometry (smooth-sphere horizon)."""
import numpy as np
import pytest

from slipday.ephem import cached_table, compute_table, grid_start, parse_utc, unix_to_jd_tdb
from slipday.geometry import Horizon, Site, sub_point, track
from slipday.metrics import find_events

START = grid_start(parse_utc("2026-01-01T00:00:00Z"))
YEAR = cached_table(START, 24 * 365, 3600)


def test_utc_to_tdb_offset_uses_leap_seconds():
    # 2023: TAI-UTC = 37 s, so TT-UTC = 69.184 s
    jd = unix_to_jd_tdb(parse_utc("2023-08-23T00:00:00Z").timestamp())[0]
    assert (jd - 2460179.5) * 86400 == pytest.approx(69.184, abs=1e-3)
    # 2015-01-01: TAI-UTC = 35 s
    jd = unix_to_jd_tdb(parse_utc("2015-01-01T00:00:00Z").timestamp())[0]
    assert (jd - 2457023.5) * 86400 == pytest.approx(67.184, abs=1e-3)


def test_equatorial_sunrise_period_is_the_synodic_month():
    site = Site("equator", 0.0, 0.0)
    tr = track(site, YEAR)
    rises = [e["unix"] for e in find_events(site, tr, "sun") if e["type"] == "sunrise"]
    gaps = np.diff(rises) / 86400.0
    assert len(gaps) >= 11
    assert gaps.mean() == pytest.approx(29.53, abs=0.05)
    assert gaps.min() > 29.2 and gaps.max() < 29.9


def test_equatorial_noon_sun_is_high_and_day_is_half_the_month():
    site = Site("equator", 0.0, 0.0)
    tr = track(site, YEAR)
    assert tr.sun_el.max() > 88.0
    # a calendar year is 12.4 lunar days, so the partial day shifts the share slightly off one half
    assert (tr.sun_clear > 0).mean() == pytest.approx(0.5, abs=0.02)


def test_polar_sun_only_grazes_the_horizon():
    tr = track(Site("near south pole", -89.9, 0.0), YEAR)
    # lunar equator is tilted 1.54 deg to the ecliptic, so the Sun never climbs above about 1.7 deg here
    assert 1.0 < tr.sun_el.max() < 1.8
    assert tr.sun_el.min() > -1.8


def test_far_side_never_sees_earth():
    tr = track(Site("Chang'e 6", -41.64, -153.99), YEAR)
    assert tr.earth_el.max() < -30.0
    assert not (tr.earth_clear > 0).any()


def test_sub_earth_point_sees_earth_near_zenith():
    tr = track(Site("sub-Earth", 0.0, 0.0), YEAR)
    assert tr.earth_el.min() > 78.0
    assert (tr.earth_clear > 0).all()


def test_sub_earth_point_stays_inside_the_libration_box():
    lat, lon = sub_point(YEAR.earth)
    assert np.abs(lat).max() < 7.0      # optical libration in latitude, about 6.7 deg
    assert np.abs(lon).max() < 8.3      # optical libration in longitude, about 7.9 deg
    assert np.abs(lat).max() > 5.0 and np.abs(lon).max() > 5.0   # and it does librate


def test_earth_stays_in_a_small_patch_of_sky_from_a_near_side_site():
    tr = track(Site("Apollo 11", 0.6741, 23.4730), YEAR)
    assert tr.earth_el.max() - tr.earth_el.min() < 20.0
    assert tr.earth_el.min() > 50.0


def test_antipodal_sites_see_opposite_sun_elevation():
    a = track(Site("a", 20.0, 30.0), YEAR)
    b = track(Site("b", -20.0, -150.0), YEAR)
    assert np.abs(a.sun_el + b.sun_el).max() < 0.01


def test_two_orientation_models_agree():
    u = START + 6 * 3600 * np.arange(4 * 365)
    site = Site("s", -69.37, 32.32)
    a = track(site, compute_table(u, orientation="de421"))
    b = track(site, compute_table(u, orientation="iau2009"))
    assert np.abs(a.sun_el - b.sun_el).max() < 0.01
    assert np.abs(a.earth_el - b.earth_el).max() < 0.01


def test_event_refinement_lands_on_the_horizon():
    from slipday.geometry import track_at
    site = Site("Blue Ghost", 18.562, 61.810)
    tr = track(site, cached_table(START, 24 * 60, 3600))
    ev = find_events(site, tr, "sun")
    assert [e["type"] for e in ev][:2] in (["sunrise", "sunset"], ["sunset", "sunrise"])
    at = track_at(site, [e["unix"] for e in ev])
    assert np.abs(at.sun_el).max() < 1e-3


def test_horizon_mask_shortens_the_day():
    table = cached_table(START, 24 * 60, 3600)
    flat = track(Site("s", -69.37, 32.32), table)
    masked = track(Site("s", -69.37, 32.32, horizon=Horizon(mask_deg=5.0)), table)
    assert (masked.sun_clear > 0).sum() < (flat.sun_clear > 0).sum()
    assert Horizon().kind == "smooth-sphere" and Horizon(mask_deg=5).kind == "flat-mask"


def test_terrain_profile_plugs_in_and_interpolates_around_north():
    h = Horizon(profile_az_deg=[0, 90, 180, 270], profile_el_deg=[4, 0, 2, 0], source="synthetic test ridge")
    assert h.kind == "profile"
    assert h.elevation_at(0.0) == pytest.approx(4.0)
    assert h.elevation_at(45.0) == pytest.approx(2.0)
    assert h.elevation_at(315.0) == pytest.approx(2.0)   # wraps through 360
    table = cached_table(START, 24 * 60, 3600)
    ridge = track(Site("s", -85.0, 0.0, horizon=h), table)
    bare = track(Site("s", -85.0, 0.0), table)
    assert (ridge.sun_clear > 0).sum() < (bare.sun_clear > 0).sum()


def test_out_of_range_inputs_are_rejected():
    with pytest.raises(ValueError):
        Site("bad", 91.0, 0.0)
    with pytest.raises(ValueError):
        compute_table([parse_utc("2090-01-01").timestamp()])
