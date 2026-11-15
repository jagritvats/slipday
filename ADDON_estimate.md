# Add-on: a learned instant estimate

Hand-over, Sunday 15 November 2026 (about 22:20 to 22:45 IST).

## What it does

The full answer for a clicked point takes 10 to 40 seconds, because the skyline is traced through the terrain.
This add-on answers in about **2.5 ms** (measured, one point, after warm-up) with a learned estimate of:

- the **verdict**: does the planned landing date meet the need at this point (yes or no), and
- the **slip margin**: how many days of slip the plan survives there.

It is labelled on every answer: "a learned estimate; the full check follows". It is valid for the page's opening plan
only (landing 18 Nov 2026, 60 landing dates, 240 sunlit hours and 100 hours of Earth contact, with a Deep Space
Network station, in the first 14 days), because that is the plan its training answers were worked out for.

## Method

- **Training answers:** the 92,416 whole-map points (one every 2 km over the 608 km square of the LOLA 80 m map,
  `data/addons/fullmap/`, see `ADDON_fullmap.md`), station Earth rule. 4,294 of them (4.6 %) say yes.
- **Cheap terrain numbers** (`slipday/addons/estimate.py`, `features`), read straight from
  `data/dem/ldem_80s_80m_f32.npy`, memory-mapped, never copied, nearest pixel:
  map position (x, y) and distance to the pole; height; slope (from the four pixels 80 m away); local relief
  (highest minus lowest of a 9 x 9 sample within 1 km and within 5 km); height above the mean of those samples;
  a coarse skyline: the highest elevation angle in 16 map directions, sampled at 9 distances from 0.4 km to 100 km,
  allowing for the Moon's curvature and a 2 m mast, plus its mean, highest, lowest and the angle toward Earth
  (roughly toward longitude 0). 29 numbers in all; all 92,416 points take 2.3 s.
- **Grid answers near the click** (the shipped version adds these): the margins of the whole-map grid points within
  2.9 km (nearest margin and its distance, mean, highest, lowest, share saying yes). When training, a grid point
  never sees its own answer, only its neighbours' (2 to 2.8 km away).
- **Model:** two histogram gradient-boosted tree models from scikit-learn, one for yes/no (yes when its chance is 0.5
  or more), one for the margin. Settings were fixed before any test was run and never changed. Model file: 422 kB.
- **Margin error convention:** "no" counts as margin -1, so calling a 0-day point "no" is 1 day off.

## Honest tests (no random split)

**Test A, whole blocks held out.** The map is cut into 8 x 8 blocks, 76 km square, dealt into 5 groups. Each group is
predicted by a model trained on the others, with a 4 km strip round the held-out blocks also left out. This is the
case where no grid answers are nearby (median 18.4 km to the nearest training point), so it uses terrain only.

| on all 92,416 points, each predicted while held out | verdict accuracy | margin error, mean (days) | margin error where truly yes | says yes when the full check says no |
|---|---|---|---|---|
| terrain model | **97.85 %** | **0.058** | 1.10 | **424 (0.48 % of the noes)** |
| nearest training point (18.4 km away, median) | 93.80 % | 0.152 | 1.79 | 2,738 (3.11 %) |
| always "no" | 95.35 % | 0.102 | 2.19 | 0 |

It still misses 36 % of the true yeses (1,559 of 4,294).

**Test B, the page's real case: a click between grid points.** The 2 km grid covers the whole map, so on the page
the question is a click up to 1.4 km from a grid point. Test points: the close-up's 14,400 points (500 m apart, 60 km
square round the pole, same skyline method; computed here with the same code `/api/slipmap` runs) minus the 900 that
sit on the 2 km grid (all 900 have exactly the same margin as the grid, a check that the two agree). That leaves
13,500 points, median 0.71 km from the nearest grid point; 692 truly say yes. The models are trained on the whole
map minus that 60 km square and a 4 km strip round it. Nearest neighbour uses the full 2 km grid, exactly as the
page's stand-in does.

| on 13,500 clicks between grid points | verdict accuracy | margin error, mean (days) | margin error where truly yes | says yes when the full check says no | misses a true yes |
|---|---|---|---|---|---|
| terrain model only | 95.61 % | 0.120 | 2.09 | 128 (1.00 %) | 465 (67 %) |
| nearest grid point (page stand-in) | 96.56 % | 0.130 | 1.45 | 220 (1.72 %) | 244 (35 %) |
| **terrain plus nearby grid answers (shipped)** | **97.48 %** | **0.086** | **1.30** | **107 (0.84 %)** | **233 (34 %)** |
| always "no" | 94.87 % | 0.133 | 2.59 | 0 | 692 (100 %) |

**The terrain-only model does not beat nearest neighbour where the page uses it** (lower verdict accuracy, about
the same margin error). It does beat it by a wide margin far from any known point (test A), but the 2 km grid
already covers the whole 80 m map, so the model covers no point the grid cannot.

**Terrain plus nearby grid answers beats nearest neighbour on every measure in test B**: 97.5 % against 96.6 %
verdict accuracy, 0.086 against 0.130 days mean margin error, and about half as many false yeses (107 against 220).
Be fair about how it was found: this second design was tried *after* the terrain-only result on test B was seen.
Its settings are the same fixed ones and it was run once, but choosing it after a look at test B is a mild form of
fitting to that test, and test B is a single 60 km area round the pole. Treat the gain as real but modest.

## Does it ship?

`ships_on_page: true` in `data/addons/estimate/report.json`, for the terrain-plus-grid version only, as a
first answer shown while the full check runs. It never replaces the full check.

## Endpoint

`GET /api/addons/estimate?lat=-89.45&lon=-137.31` (router `slipday.addons.estimate.router`; not yet registered in
`api.py`). Answer: `available`, `label` ("a learned estimate; the full check follows"), `verdict` ("yes"/"no"),
`verdict_words`, `chance_yes`, `margin_days_estimate` (null when "no"), `margin_days_raw`, `ships_on_page`,
`measured_accuracy` (test B numbers for the served model and for nearest neighbour, plus test A accuracy), `plan`,
`how`. Points outside the 608 km square give `available: false` with the reason; lat outside -90 to -60 gives 422.

## Files

- `scripts/addons/train_estimate.py`: features, both tests, ship decision, final model (18 s, all 92,416 points).
- `slipday/addons/estimate.py`: features, router. Reads `data/addons/estimate/` and `data/addons/fullmap/`; never writes.
- `data/addons/estimate/model.joblib` (422 kB), `report.json` (every number above), `train.log`.
- `tests/addons/test_estimate.py`: 7 tests.

## Needs

scikit-learn (1.9.1 was installed into `.venv`; it is **not** in `requirements.txt`, which this add-on may not edit).
Without it the endpoint answers `available: false` instead of failing.

## Limits

- Opening plan only; any other plan needs a new training run on answers worked out for that plan.
- Point checked at one position, like the whole-map layer (not the 13 touchdown points).
- Misses about a third of true yeses near the pole; when it says no, the full check may still say yes.
