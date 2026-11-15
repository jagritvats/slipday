"""Hindcast of three real landings against reported events (smooth-sphere horizon)."""
import pytest

from slipday.ephem import parse_utc
from slipday.hindcast import hindcast, size_class

H = {m["id"]: m for m in hindcast()["missions"]}


def _h(a, b):
    return (parse_utc(a) - parse_utc(b)).total_seconds() / 3600.0


@pytest.mark.parametrize("mid", ["chandrayaan3", "im1", "blueghost1"])
def test_sun_and_earth_were_up_at_touchdown(mid):
    m = H[mid]
    assert m["sun_el_at_landing"] > 0
    assert m["earth_el_at_landing"] > 0


def test_no_row_is_labelled_as_passing_a_tolerance():
    """Regression (review, medium): the IM-1 79 h miss was printed as 'within' a 120 h tolerance."""
    for m in H.values():
        for c in m["checks"]:
            assert "within_tolerance" not in c and "tolerance_h" not in c
    im1 = H["im1"]["checks"][0]
    assert 70 < im1["predicted_minus_reported_h"] < 90
    assert im1["size"] == "off by 3.3 days"
    assert H["blueghost1"]["checks"][0]["size"] == "within 6 h"
    assert size_class(79.2) == "off by 3.3 days" and size_class(-23.9) == "within 1 day"


def test_chandrayaan3_landed_early_in_the_lunar_morning():
    m = H["chandrayaan3"]
    assert 24 < m["hours_from_sunrise_to_landing"] < 72        # reported: shortly after local sunrise
    # lander was put to sleep on 4 Sep 2023 ahead of sunset: predicted sunset is the same UTC day, later
    assert m["predicted"]["center"]["sunset_after"].startswith("2023-09-04")
    assert _h(m["predicted"]["center"]["sunset_after"], "2023-09-04T02:30:00Z") > 0
    # wake-up was targeted for 22 Sep 2023: geometric sunrise must come first, within three days
    assert 0 < _h("2023-09-22T00:00:00Z", m["predicted"]["center"]["next_sunrise"]) < 72


def test_blue_ghost_sunrise_and_sunset():
    m = H["blueghost1"]
    assert 0 < m["hours_from_sunrise_to_landing"] < 12          # landed hours after local sunrise
    assert m["predicted"]["center"]["sunset_after"].startswith("2025-03-16")   # reported: lunar sunset on 16 Mar 2025
    # last communication came after sunset, within a few hours
    assert 0 < _h("2025-03-16T23:15:00Z", m["predicted"]["center"]["sunset_after"]) < 6


def test_im1_smooth_sphere_sunset_is_later_than_the_real_power_loss():
    m = H["im1"]
    # Known limitation, asserted so it stays visible: terrain and lander tilt ended the mission
    # days before the smooth-sphere sunset.
    assert 48 < _h(m["predicted"]["center"]["sunset_after"], "2024-02-29T00:00:00Z") < 120
