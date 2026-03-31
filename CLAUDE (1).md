# Connecticut Book Access — Urban Typology Enrichment

## Project purpose

This project enriches a Connecticut H3 grid dataset with an urban/suburban/rural typology to support analysis of children's book access disparities across the state. The typology is needed because standard Census Urban Places definitions conflate dense suburban areas with true urban cores, masking meaningful differences in access patterns and lived experience.

The work is part of the **Book-Access Infrastructure Index (BAII)** project built by North Arrow for Read to Grow (RTG).

---

## Input dataset

**File:** `baii_test2.gpkg` — GeoPackage format, single layer `baii_test2`
**Resolution:** H3 Resolution 8 (~0.74 km² per cell — area is uniform, so population values are directly comparable as a density proxy)
**Total rows:** 17,654 (covering Connecticut; cells over water/state boundary edges included)

**Key columns:**
| Column | Description |
|---|---|
| `h3_index` | Uber H3 cell identifier at resolution 8. All indexes begin with `88`. Cell boundaries and centroids can be derived programmatically — no separate shapefile needed. |
| `pop_total` | WorldPop model estimate — projects Census population onto built infrastructure from satellite imagery. More spatially accurate than raw Census tract apportionment. Use this as the population/density signal — **do not pull Census population to replace it**. Values are unrounded floats; 1,679 cells have `pop_total < 1` (847 exactly zero). |
| `baii_car` | Book-Access Infrastructure Index score, car mode |
| `baii_pt` | Book-Access Infrastructure Index score, public transit mode |
| `baii_walk` | Decommissioned — ignore this column |

The file also contains ~140 additional columns of pre-joined ACS, school district, and KEI data. Do not modify or remove any of these.

---

## Output

The goal is to return the input GeoPackage enriched with exactly **3 new columns**:

| New Column | Description |
|---|---|
| `multifamily_pct` | Share of housing units in multi-family structures (2+ units) for the Census tract containing the H3 cell centroid. Source: ACS Table B25024. |
| `dist_job_center_km` | Euclidean distance in km from the H3 cell centroid to the nearest employment center. Employment centers defined as H3 res-8 clusters above a job-density threshold derived from LEHD LODES data. |
| `urban_type` | Categorical typology: `urban_core`, `dense_suburban`, `suburban`, `rural`, or `uninhabited`. Derived from the composite of `pop_total`, `multifamily_pct`, and `dist_job_center_km` using Connecticut-specific quartile thresholds (see methodology below). |

All other columns must be preserved unchanged. No rows should be dropped.

---

## Typology methodology

### Variables and rationale

**1. `pop_total` (already in dataset)**
Because H3 res-8 cells have uniform area (~0.74 km²), raw population is equivalent to population density. This is the primary signal. Use Connecticut's own quartile distribution — do not apply national thresholds. **Exclude cells with `pop_total < 1` from quartile computation** — these are uninhabited or near-uninhabited cells (water, forest, reservoirs) and should be classified as `uninhabited` directly, bypassing the scoring logic.

**2. `multifamily_pct` (from ACS B25024)**
Share of units in structures with 2+ units. Distinguishes urban built form (apartments, rowhouses) from suburban single-family form even when population density is similar. Pull at the **tract level** via the Census API and spatial-join to H3 centroids.

**3. `dist_job_center_km` (from LEHD LODES)**
Distance to nearest employment cluster. Captures the commuter-suburb vs. urban-core distinction. Define job centers as H3 cells in the top decile of total jobs (C000 field from LODES WAC file for Connecticut, most recent available year). Compute distance from each H3 centroid to the nearest job-center centroid.

### Classification logic

Compute Connecticut-specific quartile breakpoints from **populated cells only** (`pop_total >= 1`) for `pop_total` and `multifamily_pct`. Apply this decision logic:

```
uninhabited     → pop_total < 1 (assign directly, skip all other logic)
urban_core      → pop_total in top quartile AND multifamily_pct > 50%
dense_suburban  → pop_total in 2nd quartile OR (top quartile AND multifamily_pct 25–50%)
suburban        → pop_total in 3rd quartile OR dist_job_center_km < 20km
rural           → pop_total in bottom quartile AND dist_job_center_km >= 20km
```

If cells fall into ambiguous overlapping categories, `urban_core` > `dense_suburban` > `suburban` > `rural` (higher classification wins). Document final breakpoint values in script output.

---

## Data sources

| Data | Source | Notes |
|---|---|---|
| Multi-family housing share | Census ACS 5-year, Table B25024 | Pull via `census` Python package or direct API call. State FIPS: 09. |
| Employment centers | LEHD LODES WAC file, Connecticut | Download from `https://lehd.ces.census.gov/data/lodes/LODES8/ct/`. Use most recent available year. Field `C000` = total jobs. |
| H3 tooling | `h3` Python package | Use `h3.h3_to_geo()` to get centroids for spatial joins |
| Spatial join (H3 → Census tract) | `geopandas` + Census tract shapefile | Download CT tract shapefile from Census TIGER/Line |

---

## Technical constraints

- **Python only.** Use `pandas`, `geopandas`, `h3`, `requests`, and `shapely`. No R.
- **No external APIs with auth** beyond the public Census API (no key required for most endpoints; if a key is needed, prompt the user to provide one — do not hardcode).
- **Reproducible.** The script should run end-to-end from raw inputs to enriched CSV with a single command. Log quartile breakpoints and job-center threshold to stdout so the methodology is auditable.
- **Output file:** write to `ct_h3_enriched.gpkg` in the working directory, preserving the original geometry column.

---

## What NOT to do

- Do not replace `pop_total` with Census tract population — the WorldPop model values are more accurate for this use case.
- Do not apply national urban/rural thresholds (e.g., Census 2,500-person threshold). All thresholds must be derived from Connecticut's own distribution.
- Do not drop H3 cells that fall outside Census tract boundaries (coastline edge cases) — assign `NaN` for `multifamily_pct` and handle gracefully in the typology logic.
- Do not add columns beyond the three specified above.
- Do not use or reference `baii_walk` — this column is decommissioned.
