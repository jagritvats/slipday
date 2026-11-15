"""Real landings offered as worked examples for the mission card.

Landing instants are the ones the hindcast uses (sources in slipday/hindcast.py), plus IM-2 from
its Wikipedia infobox (17:28:50 UTC, 6 March 2025), read through a web-fetch tool.  Times are
snapped down to the hour because the slip grid works on hourly samples.

Each example carries its own need.  The sunlit-hours figure is the mission's planned surface
duration where an operations plan in days was published before landing (``need_kind`` "published
plan"), and the illustrative 240 hours where it was not ("illustrative").  The Earth-contact figure
(100 hours) is illustrative for every example: no published requirement was found.  The plan
documents were read through a web-fetch tool on 14 Nov 2026 (relayed text, not byte-exact copies).
"""
NOTE = ("Real landing sites and landing times, as worked examples, not proof of the model. The sunlit hours asked "
        "for are each mission's planned surface duration where one was published before landing (IM-1 about 7 days; "
        "the 10 in its press kit would give No. IM-2 about 10, Blue Ghost 14); Chandrayaan-3's figure (its published "
        "14 days would give No) and every Earth-contact figure are illustrative, not the mission's own.")

_EARTH = {"need_earth_h": 100, "window_days": 14}

MISSIONS = [
    {"id": "im2", "label": "IM-2 Athena", "site": "im2", "landing": "2025-03-06T17:00:00Z",
     "landed_utc": "2025-03-06T17:28:50Z", "source": "https://en.wikipedia.org/wiki/IM-2", "relayed": True,
     "need_sun_h": 240, "need_kind": "published plan",
     "need_source": "https://www.nasa.gov/wp-content/uploads/2025/02/np-2025-02-005-jsc-clps-intuitive-machines-press-kit-508-2-25-25.pdf",
     "need_note": "NASA's IM-2 press kit planned approximately 10 days of surface operations, so this example asks for "
                  "240 sunlit hours. The 100 hours of Earth contact are illustrative. In the event the lander came "
                  "down about 250 m from its target, on its side in a small crater, and the mission ended the next "
                  "day: a terrain skyline cannot predict that.", **_EARTH},
    {"id": "im1", "label": "IM-1 Odysseus", "site": "im1", "landing": "2024-02-22T23:00:00Z",
     "landed_utc": "2024-02-22T23:23:53Z", "source": "https://en.wikipedia.org/wiki/IM-1", "relayed": True,
     "need_sun_h": 168, "need_kind": "published plan",
     "need_source": "https://www.nasa.gov/missions/artemis/clps/nasa-collects-first-surface-science-in-decades-via-commercial-moon-mission/",
     "need_note": "IM-1 was planned for about seven days of surface operations before lunar night, and NASA reports "
                  "that its instruments stopped seven days after landing, as projected before launch: this example "
                  "asks for 168 sunlit hours. NASA's press kit gives approximately 10 days; with 240 hours the "
                  "answer here is No, because the terrain leaves 208 sunlit hours at this site and landing hour. "
                  "The 100 hours of Earth contact are illustrative.", **_EARTH},
    {"id": "chandrayaan3", "label": "Chandrayaan-3", "site": "chandrayaan3", "landing": "2023-08-23T12:00:00Z",
     "landed_utc": "2023-08-23T12:33:00Z", "source": "https://en.wikipedia.org/wiki/Chandrayaan-3", "relayed": True,
     "need_sun_h": 240, "need_kind": "illustrative",
     "need_source": "https://www.isro.gov.in/Chandrayaan3_Details.html",
     "need_note": "ISRO gave the mission life as one lunar day (about 14 Earth days), which is a design life and not "
                  "a number of sunlit hours after touchdown, so this example keeps the illustrative 240 sunlit hours "
                  "and 100 hours of Earth contact. Taken literally, 336 hours would give No: the landing left 283 "
                  "sunlit hours in the window. This site is outside the area checked against the LOLA team's maps.",
     **_EARTH},
    {"id": "blueghost1", "label": "Blue Ghost 1", "site": "blueghost1", "landing": "2025-03-02T08:00:00Z",
     "landed_utc": "2025-03-02T08:34:00Z",
     "source": "https://spaceflightnow.com/2025/03/18/firefly-aerospaces-blue-ghost-mission-1-concludes-successful-14-day-mission-on-the-moon/",
     "relayed": True, "need_sun_h": 336, "need_kind": "published plan",
     "need_source": "https://www.nasa.gov/wp-content/uploads/2025/01/np-2025-01-001-jsc-clps-firefly-press-kit-screen-508-1-10-25-final.pdf",
     "need_note": "NASA's Blue Ghost Mission 1 press kit planned 14 days of surface operations, a full lunar day, so "
                  "this example asks for 336 sunlit hours in 14 days: every hour of the window. A need like that "
                  "leaves no slip margin by construction: the landing has to come just after local sunrise. The 100 "
                  "hours of Earth contact are illustrative. This site is on the 1.9 km grid, outside the area "
                  "checked against the LOLA team's maps.", **_EARTH},
]
