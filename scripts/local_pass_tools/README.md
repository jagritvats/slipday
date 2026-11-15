# Measuring scripts of the local pass (14 Nov 2026)

Small scripts that produced the numbers in `LOCAL_PASS_RESULTS.md`. They are not part of the app and
nothing imports them. Run them from the repository root with the repository's Python; the ones that take
`<entry root>` want the path of this repository (`.`). Those that post requests use the app's own test
client and a private, empty skyline cache, so they do not touch `data/horizon_cache/`.

| Script | What it prints |
|---|---|
| `hash_dir.py <folder>` | size and sha256 of every file in a folder |
| `receipts.py <reference dir> <out.tsv>` | the download receipt (`data/reference/DOWNLOADS.tsv`) |
| `crop_ldem64.py <ldem_64_uint.tif> <out.npy>` | the 60 S to 90 S crop and its hash (`prepare_dem.py` now does this itself) |
| `compare_field.py <old dir> <new dir>` | whether two skyline fields are identical |
| `show_earth.py <entry root>` | the Earth-check rows and the validation tiles from the stored JSON |
| `earth_controls.py <entry root>` | the Earth comparison with the map flipped, transposed and shifted; label keywords |
| `measure_cards.py <entry root> [--scatter 100,150] [--label text]` | mission-card verdicts for six cases (set `SLIPDAY_SKIP_DEMS=ldem_80s_80m` for the fallback) |
| `measure_replays.py`, `measure_replays_final.py <entry root>` | the four real landings under candidate needs, and under the need each now carries |
| `measure_circles.py <entry root> [--sites a,b]` | landing-circle shares, with cold and warm timings |
| `call_robust.py <base url> [start] [candidates]` | the slip-robust list from a running server, timed twice |
| `verify_map.py <entry root>` | slip-map headline figures and the distance to the LOLA map's maximum |
| `horizons_live.py <entry root>` | one live JPL Horizons cross-check through the app's endpoint (makes four requests to ssd.jpl.nasa.gov) |
| `compare_fixtures.py <entry root>` | relayed Horizons fixtures against the direct downloads in `fixtures/raw/` |
| `mark_fixtures.py <entry root>` | adds the "verified" line to the fixture headers (already applied) |
| `docker_mem.ps1 -Root <entry root> -Out <folder>` | the four container load tests of section 9 (PowerShell, needs Docker and the image `slipday-local:pass`) |

Added in the second local pass (LOCAL_PASS_2_RESULTS.md):

- `measure_blocking.py <server>`: starts 0, 1, 2 and 12 slow landing-circle requests for never-seen points
  and times the stored default card, the page and the default circles while they run; counts the slow
  requests answered and refused.
- `measure_pass2.py`: prints, from the app's own endpoints in-process, the figures of the second pass: why
  it flips at five examples, terrain against a smooth sphere date by date, lander classes and landing
  circles with their ranges, the year ribbon, the scatter-checked map for five scenarios and its
  agreement with the mission card at 12 random map points, and the permanent-shadow area.
