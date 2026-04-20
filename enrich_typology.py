#!/usr/bin/env python3
"""
Connecticut H3 Urban Typology Enrichment
=========================================
Adds three columns to baii_test2.gpkg:
  - multifamily_pct      : share of housing units in 2+ unit structures (ACS B25024, tract level)
  - dist_job_center_km   : euclidean km to nearest LODES-derived employment center
  - urban_type           : urban_core | dense_suburban | suburban | rural | uninhabited

Run from the project root:
    python enrich_typology.py
"""

import io
import gzip
import os
import shutil
import zipfile

import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import h3
from shapely.geometry import Point

# ── Config ────────────────────────────────────────────────────────────────────
INPUT_GPKG  = "references/baii_test2 (1).gpkg"
OUTPUT_GPKG = "ct_h3_enriched.gpkg"
CT_FIPS     = "09"
ACS_YEAR    = 2022
CRS_PROJ    = "EPSG:32618"   # UTM Zone 18N — metric CRS for CT distance calcs
TMP_DIR     = "_tmp_enrich"


# ── Helpers ───────────────────────────────────────────────────────────────────
def fetch(url, timeout=300, desc=""):
    print(f"  Downloading {desc or url} ...")
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r


def unzip_to(content, dest):
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        z.extractall(dest)


# ── 1. Load GeoPackage ────────────────────────────────────────────────────────
print("\n[1/7] Loading input GeoPackage...")
gdf = gpd.read_file(INPUT_GPKG)
print(f"      {len(gdf):,} rows, {len(gdf.columns)} columns, CRS: {gdf.crs}")

# ── 2. Compute H3 centroids (h3 v4 API) ──────────────────────────────────────
print("\n[2/7] Computing H3 centroids...")
latlngs = gdf["h3_index"].apply(h3.cell_to_latlng)          # returns (lat, lng)
centroids = gpd.GeoDataFrame(
    {"h3_index": gdf["h3_index"]},
    geometry=[Point(lng, lat) for lat, lng in latlngs],
    crs="EPSG:4326",
)
print(f"      {len(centroids):,} centroids computed")

# ── 3. Fetch ACS B25024 (multifamily housing share) ──────────────────────────
print("\n[3/7] Fetching ACS B25024 (tract-level multifamily housing)...")
# B25024_001E = total units in structure
# B25024_004E–B25024_009E = 2-unit, 3-4, 5-9, 10-19, 20-49, 50+ unit structures
mf_vars = [
    "B25024_001E",
    "B25024_004E", "B25024_005E", "B25024_006E",
    "B25024_007E", "B25024_008E", "B25024_009E",
]
acs_url = (
    f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
    f"?get={','.join(mf_vars)}&for=tract:*&in=state:{CT_FIPS}"
)
data = fetch(acs_url, desc="ACS B25024").json()
acs_df = pd.DataFrame(data[1:], columns=data[0])
for v in mf_vars:
    acs_df[v] = pd.to_numeric(acs_df[v], errors="coerce")

mf_cols = ["B25024_004E","B25024_005E","B25024_006E","B25024_007E","B25024_008E","B25024_009E"]
acs_df["multifamily_units"] = acs_df[mf_cols].sum(axis=1)
acs_df["multifamily_pct"]   = (acs_df["multifamily_units"] / acs_df["B25024_001E"]).clip(0, 1)
acs_df["GEOID"] = acs_df["state"] + acs_df["county"] + acs_df["tract"]
acs_df = acs_df[["GEOID", "multifamily_pct"]].copy()
print(f"      {len(acs_df):,} tracts retrieved")

# ── 4. Download CT tract shapefile & spatial-join to H3 centroids ─────────────
print("\n[4/7] Spatial-joining H3 centroids to Census tracts...")
tract_url = f"https://www2.census.gov/geo/tiger/TIGER{ACS_YEAR}/TRACT/tl_{ACS_YEAR}_{CT_FIPS}_tract.zip"
r = fetch(tract_url, desc="CT tract shapefile")
unzip_to(r.content, f"{TMP_DIR}/tract")
tracts = gpd.read_file(f"{TMP_DIR}/tract/tl_{ACS_YEAR}_{CT_FIPS}_tract.shp")
tracts = tracts[["GEOID", "geometry"]].merge(acs_df, on="GEOID", how="left")
tracts = tracts.to_crs("EPSG:4326")
print(f"      {len(tracts):,} tracts loaded")

joined = gpd.sjoin(centroids, tracts[["GEOID", "multifamily_pct", "geometry"]], how="left", predicate="within")
# Resolve any duplicates from boundary-straddling centroids
joined = joined.groupby("h3_index", as_index=False).first()[["h3_index", "multifamily_pct"]]
gdf = gdf.merge(joined, on="h3_index", how="left")

matched = gdf["multifamily_pct"].notna().sum()
print(f"      {matched:,} H3 cells matched to a tract ({len(gdf)-matched} unmatched, NaN)")

# ── 5. Download LEHD LODES WAC & build job centers ────────────────────────────
print("\n[5/7] Building LODES employment centers...")

# 5a. Download WAC file (most recent available year)
lodes_year = None
lodes_content = None
for year in [2022, 2021, 2020]:
    url = f"https://lehd.ces.census.gov/data/lodes/LODES8/ct/wac/ct_wac_S000_JT00_{year}.csv.gz"
    r = requests.get(url, timeout=120)
    if r.status_code == 200:
        lodes_year = year
        lodes_content = r.content
        break
if lodes_content is None:
    raise RuntimeError("Could not download LODES WAC file for CT (tried 2020-2022)")
print(f"      Using LODES year {lodes_year}")

with gzip.open(io.BytesIO(lodes_content)) as f:
    lodes_df = pd.read_csv(f, dtype={"w_geocode": str})
lodes_df = lodes_df[["w_geocode", "C000"]].copy()
print(f"      {len(lodes_df):,} blocks in LODES WAC")

# 5b. Download CT 2020 block shapefile to get block centroids
block_url = f"https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_{CT_FIPS}_tabblock20.zip"
r = fetch(block_url, desc="CT 2020 block shapefile (~50MB, may take a moment)")
unzip_to(r.content, f"{TMP_DIR}/block")
blocks = gpd.read_file(f"{TMP_DIR}/block/tl_2020_{CT_FIPS}_tabblock20.shp")
blocks = blocks[["GEOID20", "geometry"]].copy()
# Project before computing centroids to avoid geographic CRS warning
centroids_b = blocks.to_crs(CRS_PROJ).geometry.centroid.to_crs("EPSG:4326")
blocks["lat"] = centroids_b.y
blocks["lng"] = centroids_b.x
print(f"      {len(blocks):,} blocks loaded")

# 5c. Match LODES blocks to shapefile, convert to H3 res 8
lodes_df = lodes_df.merge(
    blocks[["GEOID20", "lat", "lng"]],
    left_on="w_geocode", right_on="GEOID20",
    how="inner",
)
lodes_df["h3_index"] = lodes_df.apply(
    lambda row: h3.latlng_to_cell(row["lat"], row["lng"], 8), axis=1
)

# 5d. Aggregate jobs per H3 cell
h3_jobs = lodes_df.groupby("h3_index")["C000"].sum().reset_index()

# 5e. Job centers = top decile of total jobs per H3 cell
threshold = h3_jobs["C000"].quantile(0.90)
job_centers = h3_jobs[h3_jobs["C000"] >= threshold].copy()

job_latlng = job_centers["h3_index"].apply(h3.cell_to_latlng)
job_centers["lat"] = [ll[0] for ll in job_latlng]
job_centers["lng"] = [ll[1] for ll in job_latlng]

jc_gdf = gpd.GeoDataFrame(
    job_centers,
    geometry=gpd.points_from_xy(job_centers["lng"], job_centers["lat"]),
    crs="EPSG:4326",
).to_crs(CRS_PROJ)

print(f"      Job center threshold (top 10%): {threshold:.0f} jobs/cell")
print(f"      Job centers identified: {len(jc_gdf):,} H3 cells")

# ── 6. Compute distance to nearest job center ─────────────────────────────────
print("\n[6/7] Computing distances to nearest job center...")
centroids_proj = centroids.to_crs(CRS_PROJ)

# Vectorised numpy distance — faster than shapely nearest_points loop
jc_x = jc_gdf.geometry.x.values
jc_y = jc_gdf.geometry.y.values
h3_x = centroids_proj.geometry.x.values
h3_y = centroids_proj.geometry.y.values

# Chunk to avoid large memory spike (17k × ~700 float64 is ~95MB — fine on modern hardware)
dx = h3_x[:, None] - jc_x[None, :]
dy = h3_y[:, None] - jc_y[None, :]
dist_km = np.sqrt(dx**2 + dy**2).min(axis=1) / 1000.0

dist_df = pd.DataFrame({"h3_index": centroids_proj["h3_index"].values, "dist_job_center_km": dist_km})
gdf = gdf.merge(dist_df, on="h3_index", how="left")
print(f"      Distance range: {dist_km.min():.2f} km to {dist_km.max():.2f} km")

# ── 7. Classify urban typology ────────────────────────────────────────────────
print("\n[7/7] Classifying urban typology...")

populated = gdf[gdf["pop_total"] >= 1]

# Connecticut-specific quartile breakpoints derived from populated cells only
pop_q25 = populated["pop_total"].quantile(0.25)
pop_q75 = populated["pop_total"].quantile(0.75)
pop_q50 = populated["pop_total"].quantile(0.50)

mf_q25  = populated["multifamily_pct"].quantile(0.25)
mf_q50  = populated["multifamily_pct"].quantile(0.50)
mf_q75  = populated["multifamily_pct"].quantile(0.75)

print("\n--- METHODOLOGY LOG ---")
print(f"  ACS year:                  {ACS_YEAR}")
print(f"  LODES year:                {lodes_year}")
print(f"  Job-center threshold:      {threshold:.0f} jobs/H3 cell (top 10%)")
print(f"  Job centers:               {len(jc_gdf):,} cells")
print(f"  pop_total quartile cutoffs (populated cells, n={len(populated):,}):")
print(f"    Q1 / 25th pct:  {pop_q25:.2f}")
print(f"    Q2 / 50th pct:  {pop_q50:.2f}")
print(f"    Q3 / 75th pct:  {pop_q75:.2f}")
print(f"  multifamily_pct quartile cutoffs (populated cells):")
print(f"    Q1 / 25th pct:  {mf_q25:.4f}  ({mf_q25*100:.1f}%)")
print(f"    Q2 / 50th pct:  {mf_q50:.4f}  ({mf_q50*100:.1f}%)")
print(f"    Q3 / 75th pct:  {mf_q75:.4f}  ({mf_q75*100:.1f}%)")
print("--- END METHODOLOGY LOG ---\n")

NEAR_KM = 1.0 * 1.60934   # 1 mile — urban_core distance supplement
FAR_KM  = 10.0 * 1.60934  # 10 miles — suburban / rural boundary

def classify(row):
    pop  = row["pop_total"]
    mf   = row["multifamily_pct"] if pd.notna(row["multifamily_pct"]) else 0.0
    dist = row["dist_job_center_km"]

    if pop < 1:
        return "rural"  # uninhabited cells merged into rural

    in_top_q    = pop >= pop_q75
    in_2nd_q    = (pop >= pop_q50) and (pop < pop_q75)
    in_3rd_q    = (pop >= pop_q25) and (pop < pop_q50)
    in_bottom_q = pop < pop_q25

    # Priority: urban_core > dense_suburban > suburban > rural
    if in_top_q and (mf > 0.50 or dist < NEAR_KM):
        return "urban_core"
    if in_2nd_q or (in_top_q and 0.25 <= mf <= 0.50):
        return "dense_suburban"
    if in_3rd_q or dist < FAR_KM:
        return "suburban"
    if in_bottom_q and dist >= FAR_KM:
        return "rural"
    return "suburban"

gdf["urban_type"] = gdf.apply(classify, axis=1)

print("Urban type distribution (v1 — independent classification):")
counts = gdf["urban_type"].value_counts()
for label, n in counts.items():
    pct = n / len(gdf) * 100
    print(f"  {label:<18} {n:>6,}  ({pct:.1f}%)")

# ── 8. Rationalized typology (urban_type_v2) ──────────────────────────────────
print("\n[8/8] Building rationalized typology (v2)...")

# Step A: Neighborhood-smooth pop_total using k=1 H3 ring (7 cells incl. self)
print("  Step A: Smoothing pop_total over k=1 neighborhood...")
h3_to_pop = dict(zip(gdf["h3_index"], gdf["pop_total"]))

def smooth_pop(h3_idx):
    disk = h3.grid_disk(h3_idx, 1)   # 7 cells including self
    vals = [h3_to_pop[n] for n in disk if n in h3_to_pop]
    return float(np.mean(vals)) if vals else 0.0

gdf["pop_smooth"] = gdf["h3_index"].apply(smooth_pop)

# Step B: Re-classify using pop_smooth (same logic, recomputed thresholds)
print("  Step B: Classifying with smoothed population...")
pop_smooth_populated = gdf[gdf["pop_smooth"] >= 1]["pop_smooth"]
ps_q25 = pop_smooth_populated.quantile(0.25)
ps_q50 = pop_smooth_populated.quantile(0.50)
ps_q75 = pop_smooth_populated.quantile(0.75)

print(f"  pop_smooth quartile cutoffs (n={len(pop_smooth_populated):,}):")
print(f"    Q1: {ps_q25:.2f}  Q2: {ps_q50:.2f}  Q3: {ps_q75:.2f}")

def classify_v2(row):
    pop  = row["pop_smooth"]
    mf   = row["multifamily_pct"] if pd.notna(row["multifamily_pct"]) else 0.0
    dist = row["dist_job_center_km"]

    if row["pop_total"] < 1:
        return "rural"  # uninhabited cells merged into rural

    in_top_q    = pop >= ps_q75
    in_2nd_q    = (pop >= ps_q50) and (pop < ps_q75)
    in_3rd_q    = (pop >= ps_q25) and (pop < ps_q50)
    in_bottom_q = pop < ps_q25

    if in_top_q and (mf > 0.50 or dist < NEAR_KM):
        return "urban_core"
    if in_2nd_q or (in_top_q and 0.25 <= mf <= 0.50):
        return "dense_suburban"
    if in_3rd_q or dist < FAR_KM:
        return "suburban"
    if in_bottom_q and dist >= FAR_KM:
        return "rural"
    return "suburban"

gdf["urban_type_v2"] = gdf.apply(classify_v2, axis=1)

# Step C: Majority filter — 2 rounds, uninhabited locked
from collections import Counter

PRIORITY = {"urban_core": 4, "dense_suburban": 3, "suburban": 2, "rural": 1}

def count_islands(df):
    h3_map = dict(zip(df["h3_index"], df["urban_type_v2"]))
    n = 0
    for idx, row in df.iterrows():
        if row["pop_total"] < 1:
            continue
        ring = h3.grid_ring(row["h3_index"], 1)
        neighbor_types = [h3_map[n] for n in ring if n in h3_map]
        if neighbor_types and all(t != row["urban_type_v2"] for t in neighbor_types):
            n += 1
    return n

islands_before = count_islands(gdf)
print(f"  Step C: Majority filter — islands before: {islands_before:,}")

for round_num in range(2):
    h3_to_type = dict(zip(gdf["h3_index"], gdf["urban_type_v2"]))
    new_types = []
    for _, row in gdf.iterrows():
        ring = h3.grid_ring(row["h3_index"], 1)
        neighbor_types = [h3_to_type[n] for n in ring if n in h3_to_type]
        if not neighbor_types:
            new_types.append(row["urban_type_v2"])
            continue
        counts_nb = Counter(neighbor_types)
        top_type, top_count = counts_nb.most_common(1)[0]
        # Reclassify if 4+ of 6 neighbors agree on a different type (no pop lock — lets isolated parks/rivers absorb into surrounding type)
        if top_count >= 4 and top_type != row["urban_type_v2"]:
            new_types.append(top_type)
        else:
            new_types.append(row["urban_type_v2"])
    gdf["urban_type_v2"] = new_types
    islands_after = count_islands(gdf)
    print(f"    Round {round_num+1}: islands remaining: {islands_after:,}")

gdf = gdf.drop(columns=["pop_smooth"])  # working column, not a deliverable

print("\nUrban type distribution comparison (v1 vs v2):")
print(f"  {'Type':<18} {'v1':>8} {'v2':>8}")
for label in ["urban_core", "dense_suburban", "suburban", "rural"]:
    n1 = (gdf["urban_type"] == label).sum()
    n2 = (gdf["urban_type_v2"] == label).sum()
    print(f"  {label:<18} {n1:>8,} {n2:>8,}")

# ── Output ────────────────────────────────────────────────────────────────────
print(f"\nWriting {OUTPUT_GPKG} ...")
# Verify only the four expected columns were added
new_cols = [c for c in gdf.columns if c not in gpd.read_file(INPUT_GPKG, rows=0).columns]
assert set(new_cols) == {"multifamily_pct", "dist_job_center_km", "urban_type", "urban_type_v2"}, \
    f"Unexpected extra columns: {new_cols}"

gdf.to_file(OUTPUT_GPKG, driver="GPKG")
print(f"Done. Output: {OUTPUT_GPKG} ({os.path.getsize(OUTPUT_GPKG)/1e6:.1f} MB)")

# ── Cleanup temp files ────────────────────────────────────────────────────────
shutil.rmtree(TMP_DIR, ignore_errors=True)
print("Temp files cleaned up.")
