#!/usr/bin/env python3
"""
Reclassify urban_type and urban_type_v2 in ct_h3.geojson using updated thresholds.

Changes from original:
  - Distance thresholds now in miles: 3 mi (near, urban_core supplement) and 10 mi (far, suburban/rural boundary)
  - rural and uninhabited merged into a single "rural" category

Run from project root:
    python reclassify.py
"""
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import h3
from collections import Counter

GEOJSON_PATH = "viz/public/ct_h3.geojson"
NEAR_KM = 1.0 * 1.60934   # 1 mile → km
FAR_KM  = 10.0 * 1.60934  # 10 miles → km

print(f"Thresholds: {NEAR_KM:.3f} km (3 mi near), {FAR_KM:.3f} km (10 mi far)")

with open(GEOJSON_PATH) as f:
    geojson = json.load(f)

features = geojson["features"]
print(f"Loaded {len(features):,} features")

df = pd.DataFrame([f["properties"] for f in features])

# ── Quartile thresholds from populated cells only ──────────────────────────────
populated = df[df["pop_total"] >= 1]
pop_q25 = populated["pop_total"].quantile(0.25)
pop_q50 = populated["pop_total"].quantile(0.50)
pop_q75 = populated["pop_total"].quantile(0.75)
mf_q25  = populated["multifamily_pct"].quantile(0.25)
mf_q50  = populated["multifamily_pct"].quantile(0.50)
mf_q75  = populated["multifamily_pct"].quantile(0.75)

print(f"\npop quartiles: Q1={pop_q25:.1f}  Q2={pop_q50:.1f}  Q3={pop_q75:.1f}")
print(f"mf  quartiles: Q1={mf_q25*100:.1f}%  Q2={mf_q50*100:.1f}%  Q3={mf_q75*100:.1f}%")

# ── v1: independent classification ───────────────────────────────────────────
def classify(pop, mf, dist):
    mf = 0.0 if pd.isna(mf) else mf
    if pop < 1:
        return "rural"
    in_top = pop >= pop_q75
    in_2nd = pop_q50 <= pop < pop_q75
    in_3rd = pop_q25 <= pop < pop_q50
    in_bot = pop < pop_q25
    if in_top and (mf > 0.50 or dist < NEAR_KM):
        return "urban_core"
    if in_2nd or (in_top and 0.25 <= mf <= 0.50):
        return "dense_suburban"
    if in_3rd or dist < FAR_KM:
        return "suburban"
    if in_bot and dist >= FAR_KM:
        return "rural"
    return "suburban"

df["urban_type"] = df.apply(
    lambda r: classify(r["pop_total"], r["multifamily_pct"], r["dist_job_center_km"]), axis=1
)
print("\nurban_type (v1) distribution:")
for label, n in df["urban_type"].value_counts().items():
    print(f"  {label:<18} {n:>6,}  ({n/len(df)*100:.1f}%)")

# ── v2: neighborhood-smoothed pop + majority filter ───────────────────────────
h3_to_pop = dict(zip(df["h3_index"], df["pop_total"]))

print("\nComputing k=1 neighborhood-smoothed population...")
def smooth_pop(h3_idx):
    disk = h3.grid_disk(h3_idx, 1)
    vals = [h3_to_pop[n] for n in disk if n in h3_to_pop]
    return float(np.mean(vals)) if vals else 0.0

df["pop_smooth"] = df["h3_index"].apply(smooth_pop)

ps_pop = df[df["pop_smooth"] >= 1]["pop_smooth"]
ps_q25, ps_q50, ps_q75 = ps_pop.quantile(0.25), ps_pop.quantile(0.50), ps_pop.quantile(0.75)
print(f"pop_smooth quartiles: Q1={ps_q25:.1f}  Q2={ps_q50:.1f}  Q3={ps_q75:.1f}")

def classify_v2(pop_raw, pop_s, mf, dist):
    mf = 0.0 if pd.isna(mf) else mf
    if pop_raw < 1:
        return "rural"
    in_top = pop_s >= ps_q75
    in_2nd = ps_q50 <= pop_s < ps_q75
    in_3rd = ps_q25 <= pop_s < ps_q50
    in_bot = pop_s < ps_q25
    if in_top and (mf > 0.50 or dist < NEAR_KM):
        return "urban_core"
    if in_2nd or (in_top and 0.25 <= mf <= 0.50):
        return "dense_suburban"
    if in_3rd or dist < FAR_KM:
        return "suburban"
    if in_bot and dist >= FAR_KM:
        return "rural"
    return "suburban"

df["urban_type_v2"] = df.apply(
    lambda r: classify_v2(r["pop_total"], r["pop_smooth"], r["multifamily_pct"], r["dist_job_center_km"]), axis=1
)

# Majority filter — 2 rounds; cells with pop_total < 1 are locked as rural
def count_islands(type_map):
    n = 0
    for h3_idx, t in type_map.items():
        if h3_to_pop.get(h3_idx, 0) < 1:
            continue
        ring = h3.grid_ring(h3_idx, 1)
        neighbors = [type_map[nb] for nb in ring if nb in type_map]
        if neighbors and all(nb_t != t for nb_t in neighbors):
            n += 1
    return n

type_map = dict(zip(df["h3_index"], df["urban_type_v2"]))
print(f"\nIslands before majority filter: {count_islands(type_map):,}")

for round_num in range(2):
    type_map = dict(zip(df["h3_index"], df["urban_type_v2"]))
    new_types = []
    for _, row in df.iterrows():
        ring = h3.grid_ring(row["h3_index"], 1)
        neighbors = [type_map[nb] for nb in ring if nb in type_map]
        if not neighbors:
            new_types.append(row["urban_type_v2"])
            continue
        top_type, top_count = Counter(neighbors).most_common(1)[0]
        new_types.append(top_type if top_count >= 4 and top_type != row["urban_type_v2"] else row["urban_type_v2"])
    df["urban_type_v2"] = new_types
    type_map = dict(zip(df["h3_index"], df["urban_type_v2"]))
    print(f"  Round {round_num+1}: islands remaining: {count_islands(type_map):,}")

print("\nurban_type_v2 distribution:")
for label, n in df["urban_type_v2"].value_counts().items():
    print(f"  {label:<18} {n:>6,}  ({n/len(df)*100:.1f}%)")

# ── Water mask: flag cells where <50% of area is on CT land ──────────────────
# Uses Census Cartographic Boundary (CB) county subdivisions, which are clipped to
# the actual shoreline — unlike TIGER/Line towns that extend into Long Island Sound.
print("\nComputing water mask from Census Cartographic Boundary file...")
WATER_THRESHOLD = 0.50
import urllib.request, os
CB_URL = "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_09_cousub_500k.zip"
CB_PATH = os.path.join(os.environ.get("TEMP", "."), "cb_2022_09_cousub_500k.zip")
if not os.path.exists(CB_PATH):
    print(f"  Downloading CB file...")
    urllib.request.urlretrieve(CB_URL, CB_PATH)
    print(f"  Downloaded.")

h3_gdf = gpd.read_file(GEOJSON_PATH).to_crs("EPSG:32618")
ct_land = gpd.read_file(f"zip://{CB_PATH}").dissolve().to_crs("EPSG:32618")

# Compute area before clipping so all 17k cells are in the denominator
h3_gdf["cell_area"] = h3_gdf.geometry.area

# Clip to CT land — drops cells entirely outside, shrinks partial cells
clipped = gpd.clip(h3_gdf[["h3_index", "geometry"]], ct_land)
clipped["land_area"] = clipped.geometry.area  # compute area while still a GeoDataFrame

land_area_by_cell = clipped.groupby("h3_index")["land_area"].sum()
cell_area_by_idx  = h3_gdf.set_index("h3_index")["cell_area"]

land_frac = (land_area_by_cell / cell_area_by_idx).fillna(0)

water_h3s = set(land_frac[land_frac < WATER_THRESHOLD].index)
print(f"  {len(water_h3s):,} cells flagged as water (< {WATER_THRESHOLD*100:.0f}% land coverage)")

# ── Write updated types and water flag back into geojson ──────────────────────
h3_to_new = {
    row["h3_index"]: (row["urban_type"], row["urban_type_v2"])
    for _, row in df.iterrows()
}
for feature in features:
    h3_idx = feature["properties"]["h3_index"]
    if h3_idx in h3_to_new:
        ut, ut2 = h3_to_new[h3_idx]
        feature["properties"]["urban_type"] = ut
        feature["properties"]["urban_type_v2"] = ut2
    feature["properties"]["is_water"] = h3_idx in water_h3s

with open(GEOJSON_PATH, "w") as f:
    json.dump(geojson, f)

print(f"\nDone — updated {GEOJSON_PATH}")
