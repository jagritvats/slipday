# Add-on: instant approximate skyline (`/api/addons/skyfast`)

A map click asks `/api/why` for the exact skyline at the clicked point: 720 directions ray-cast over LOLA terrain,
5 to 10 s in all. This add-on returns the skyline of the **nearest stored grid point** at once, so the page can
draw an approximate skyline straight away and swap in the exact one when `/api/why` answers.

Router: `slipday/addons/skyfast.py` (`router`; the orchestrator registers it, `api.py` is not edited).

## Endpoint

`GET /api/addons/skyfast?lat=-89.6&lon=30`

| field | meaning |
|---|---|
| `skyline` | same keys and shape as `/api/why`'s `skyline`: `az_deg` (720 values, 0.0 to 359.5, 0.5 deg apart, clockwise from north), `el_deg` (skyline elevation angle, deg, 3 decimals), `dist_km` (**all `null`**: not stored for grid points), `site_height_m` (`null` for scatter points), `mast_m` (2.0) |
| `point` | `lat`, `lon` of the stored point used |
| `distance_m` | great-circle distance from the clicked point to that point, metres |
| `grid` | `name` (`close-up`, `close-up scatter`, `whole map`), `step_m` (500, 100, 2000), `text` |
| `label` | `"approximate: nearest precomputed point"`; `approximate: true` |
| `clicked`, `note` | the request point; a note on `dist_km` |

404 when no stored point is within 3 km (outside the South pole to 80 deg S maps); 422 for missing or bad arguments.

## What it searches

All three stored sets, nearest wins:

- `data/field/pole_el_i16.npy` + `pole_points.npz`: close-up, 120 x 120 points 500 m apart, 60 km square round the pole.
- `data/field/scatter_el_i16.npy` + `scatter_points.npz`: 12 touchdown points 50 m / 100 m round 2407 close-up points.
- `data/addons/skyfast/fullmap_el_i16.npy` + `fullmap_points.npz`: whole map to 80 deg S, 304 x 304 points 2 km apart.
  The whole-map build stored its skylines in 1444 chunk files (`data/addons/fullmap/chunks_2000m/`); they were gathered,
  values unchanged, into one memory-mappable array by `scripts/addons/build_skyfast.py` (133 MB, run once).

All are int16 x 0.002 deg, 720 azimuths from north, 2 m mast, same ray-march and terrain stack as `/api/why`.

## Speed

Arrays are memory-mapped (`mmap_mode="r"`); a request finds the nearest point by a vectorised search over ~135,000
precomputed positions and reads one 1.4 kB row. First call (opening the files) 28 ms; then median 1.3 ms, max 2 ms
in-process; under 50 ms through the HTTP stack (tested).

## Accuracy

10 random clicks, stored nearest skyline against the exact skyline (`sites.terrain_profile`, the function `/api/why`
draws its `skyline` from), absolute difference over the 720 directions:

| grid | distance to stored point | median diff | max diff |
|---|---|---|---|
| close-up scatter | 84 m | 0.04 deg | 0.37 deg |
| close-up | 121 to 208 m (5 clicks) | 0.20 to 0.40 deg | 0.39 to 0.69 deg |
| whole map | 236 to 714 m (3 clicks) | 0.23 to 0.33 deg | 1.8 to 6.4 deg |
| whole map | 906 m | 0.33 deg | 4.4 deg |
| whole map | 942 m | **3.05 deg** | **9.1 deg** |

- **Inside the close-up square** the approximation is good: median under 0.4 deg, max under 0.7 deg.
- **On the whole-map 2 km grid** the typical direction is still within about 0.3 deg, but the nearby ground can differ a lot:
  single directions are off by 2 to 9 deg, and on rough ground (one click of five) the whole skyline was off by 3 deg median.
  Treat it as a placeholder only.
- Even at a stored point itself the exact skyline differs slightly from the stored one (median 0.001 to 0.02 deg, max up to
  ~1 deg, site height differing by up to 3 m): the terrain code has had small changes since the grids were built.

## How the front end should use it

1. On click, fire `GET /api/addons/skyfast` and `POST /api/why` together.
2. When skyfast answers (and `/api/why` has not), draw `skyline.az_deg` / `skyline.el_deg` with the existing skyline
   drawing code, visibly marked approximate (dashed or faded line) with the `label`, `distance_m` and `grid.text`,
   e.g. "approximate: nearest precomputed point, 640 m away, whole-map 2 km grid". Skip anything that needs `dist_km`
   (blocking-terrain distances) and the Sun / Earth verdicts, which only `/api/why` gives.
3. When `/api/why` answers, replace the approximate line with `why.skyline` and drop the label. Ignore a skyfast answer
   that arrives after `/api/why`, or for an earlier click.
4. On 404 / 503 just wait for `/api/why`.

## Files

- `slipday/addons/skyfast.py`: the router.
- `scripts/addons/build_skyfast.py`: gathers the whole-map chunks into `data/addons/skyfast/`.
- `tests/addons/test_skyfast.py`: 9 tests (shape matches `/api/why`, stored point returns its own row, grid choice,
  404 / 422, under 50 ms, memory-mapped).
