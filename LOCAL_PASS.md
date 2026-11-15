# Local pass: what to run on a computer with open internet

**Status: run on 14 Nov 2026** on a Windows 11 machine (Python 3.12, Git Bash for the `.sh` script, Docker
Desktop). Every step below was executed there except where it says otherwise; the results, with the
command behind each number, are in LOCAL_PASS_RESULTS.md. This file is kept as the instructions, corrected
where the first, untested version was wrong:

- the Sun-map GeoTIFFs are under `/data/MoonIllumination/` at pgda.gsfc.nasa.gov, and that server answers
  a wrong path with HTTP 200 and a web page, so the download script now refuses a file that starts like
  HTML;
- one folder is used throughout (`data/reference/`); `scripts/fetch_lola.sh` used to save elsewhere;
- the Earth tile reports the rule in the map's label, not the best-fitting rule.

Do the steps in order from the repository root. Python 3.11 or later, in a virtual environment:
`python -m venv .venv`, then `pip install -r requirements.txt` with that environment's Python.
On Windows write `python` for `python3`, set variables with `$env:NAME = "value"`, and run the `.sh`
script from Git Bash.

## 1. Download the official files (10 to 20 minutes, 1.27 GB)

```
sh scripts/fetch_on_your_machine.sh
```

It saves into `data/reference/` (git-ignored):

| File | What it is | Needed for |
|---|---|---|
| `AVGVISIB_85S_060M_201608_EARTH.IMG` + `.LBL` | LOLA team Earth-visibility map, 85 S to the pole, 60 m | step 2 |
| `AVGVISIB_75S_120M_201608_EARTH.IMG` + `.LBL` | the same, 75 S to the pole, 120 m | step 2 |
| `AVGVISIB_65S_240M_201608_EARTH.IMG` + `.LBL` | the same, 65 S to the pole, 240 m | not used yet |
| `AVGVISIB_85S_060M_201608.TIF`, `AVGVISIB_75S_120M_201608.TIF` | Sun-visibility maps | steps 3 and 4 |
| `AVGVISIB_65S_240M_201608.JP2` + `_JP2.LBL`, three Sun-map `.LBL` files | the 240 m Sun map and the labels | one reader test; the labels' definitions |
| `LDEM_80S_80MPP_ADJ.TIF` | 80 m elevation mosaic (pgda.gsfc.nasa.gov) | step 3 |
| `LDEM_75S_240M.JP2` + label, `LDEM_16.IMG` + label | PDS LOLA grids (pds-geosciences.wustl.edu) | step 3 |
| `ldem_64_uint.tif` | 64 px/deg grid of NASA SVS's CGI Moon Kit, 531 MB | step 3 |

Expected: a "got" or "have" line per file, "hash ok" for the ten files with a recorded hash, and "all
files present". If a line says FAILED or "not a data file", the address has moved: the Earth maps are
listed at https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/ and GeoTIFF versions of the Sun and Earth maps
are linked from https://pgda.gsfc.nasa.gov/products/69. Any file whose name contains `AVGVISIB`, the
region (`85S_060M`, `75S_120M`) and `EARTH` is picked up by step 2; a GeoTIFF needs no label.

Only the 80 m grid, without the validation files: `python3 scripts/fetch_grid80.py`.

## 2. Run the Earth-visibility check (under a minute)

```
python3 scripts/validate_more.py data/reference --only e              # the stored model side against the maps
PROCS=8 python3 scripts/validate_more.py data/reference --recompute   # all six checks, model side recomputed (45 s)
```

Expected output: a line starting `e [` in which each map has a `reference` entry with the file name, the
map's own description from its label, `points_inside_map` (200 for each of the two regions), and for each
of four rules the mean absolute difference and correlation. Measured: with the rule in the label ("any
fraction of the Earth disc") 0.97 points and correlation 0.9946 on the 60 m map, 0.69 and 0.9984 on the
120 m map. Then restart the app and open "Can you trust it?": the tile "Earth in view against the LOLA
team's Earth-visibility map" shows ±1.0 pts and names the rule.

What to check if it is ever re-run on other files:

- The description printed from the label says which rule the map uses. The tile and the row marked "(the
  map's rule)" must be that rule; the tile text says so, and says if another rule fits better.
- A correlation near zero would mean a georeferencing or definition mismatch: check
  `LINE_PROJECTION_OFFSET` and `MAP_SCALE` in the label against `slipday/refmaps.py` before concluding
  anything about the model. For the files of 14 Nov 2026: 2528.5 and 60 m/pix (3811.5 and 120), and
  flipping or transposing the map drops the correlation to between -0.52 and +0.55.
- The labels name no observer height and no time span. The model side is at 0 m over one 18.6-year cycle.

## 3. Rebuild the working arrays from the official files (1 minute)

```
python3 scripts/prepare_dem.py data/reference
python3 -m pytest -q
```

`prepare_dem.py` reads the 80 m TIFF, the 240 m JPEG2000, `LDEM_16.IMG`, the Sun map for the display
layer, and `ldem_64_uint.tif`, which it crops to 60 S to 90 S itself. Expected: five lines of output, the
array hashes of LOCAL_PASS_RESULTS.md section 2, and 152 tests passing. If a source hash differs from the
recorded one the archive has a newer product version: do steps 4 and 5 and say so.

Changing `data/dem/dems.json` in any way (even the provenance text) changes the cache keys: rebuild the
field and the cache (step 5).

## 4. Re-run the stored validation from the official maps (10 to 20 minutes)

```
python3 scripts/validate_terrain.py data/reference                    # 9 minutes on two free cores; 18 on a busy laptop
PROCS=8 python3 scripts/validate_more.py data/reference --recompute   # 40 s; run it after the line above, which resets the tiles
```

Expected headline rows, unchanged on 14 Nov 2026: 60 m map 0.80 points (correlation 0.9916), 120 m map
0.76 (0.9949), ridge pixels 4.02 points (0.61), C1 at 2 m 88.01 / 92.06 / 198 h. Earth: 0.97 (0.9946),
0.69 (0.9984), and 1.57 (0.9707) on the ridge pixels (check f, which runs with the others).

## 5. Rebuild derived files (15 to 25 minutes)

```
python3 scripts/build_field.py --procs 10     # 14,400 skylines for the slip map; 14 minutes with 10 processes
python3 scripts/warm_cache.py                 # skylines of the default and replay sites, 80 m configuration
python3 scripts/warm_cache.py --no-80m        # the same for the 240 m configuration
```

Delete the old files in `data/horizon_cache/` first if `dems.json` changed: their keys can no longer match.

## 6. Live checks

```
SLIPDAY_HORIZONS=1 MALLOC_ARENA_MAX=2 uvicorn slipday.api:app --port 8000
```

- Open the page, scroll to the bottom and press "Run a live Horizons cross-check for the first site".
  Measured through the same endpoint: 41 rows each for the Sun and the Earth, largest elevation
  difference 1.4e-05 degrees. `python3 scripts/fetch_horizons_fixtures.py` downloads the six reference
  tables into `fixtures/raw/`.
- `docker build -t slipday .`, then `docker run -d --name slipday -m 512m -p 8000:8000 slipday` and
  `python3 scripts/stress_check.py http://127.0.0.1:8000 --docker slipday` for the load test with memory
  (add `-e SLIPDAY_SKIP_DEMS=ldem_80s_80m` to test the 240 m grid). Results of 14 Nov 2026 for both
  grids and three memory limits are in the README ("Deploy").
- Browser checks: `NODE_PATH=<node_modules with puppeteer-core> CHROME=<browser binary> node
  scripts/ui_check.js http://127.0.0.1:8000/ <folder for screenshots>` (the folder must exist). 43 checks.

Not done on 14 Nov 2026: a deployment to a public host; `docker build --build-arg GRID80=1` (the script it
runs was tested by itself); the page on a real phone.

## 7. Before submitting

- Deploy with the 80 m grid in the image (`docker build --build-arg GRID80=1`, or build on a machine
  that has `data/dem/ldem_80s_80m_f32.npy`); on the 240 m grid the default example reads "Not sure".
  Check the badge at the top of the deployed page: it must say "80 m/px". Measured in containers: the
  80 m grid peaks at 431 MB of a 512 MB limit under the load test; 768 MB or 1 GB is the safer choice.
- Replace the placeholder line in the "Use of artificial intelligence" field of SUBMISSION_DRAFT.md.
- Re-take the storyboard frames against the deployed site:
  `NODE_PATH=<...> CHROME=<...> node scripts/storyboard.js https://<your site>/ demo`. The frames use
  fixed dates, so they should not change.
- Check the 2026 submission form's field names against SUBMISSION_DRAFT.md.
