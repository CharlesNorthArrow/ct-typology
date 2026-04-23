#!/usr/bin/env python3
"""
Fetch CT town population: 2010 Decennial Census vs ACS 2023 5-year estimates.
Compute % change, attach to town centroids.
Output: viz/public/ct_pop_growth.geojson
"""
import json, re, requests
import geopandas as gpd
import pandas as pd

def clean_name(s):
    """Strip Census suffixes: 'Andover town, Tolland County, Connecticut' → 'andover'"""
    s = re.sub(r'\s+(town|city|borough|village|plantation)\b.*', '', str(s), flags=re.I)
    return s.strip().lower()

# ── 2010 Decennial Census SF1 ─────────────────────────────────────────────────
r2010 = requests.get(
    "https://api.census.gov/data/2010/dec/sf1",
    params={"get": "P001001,NAME", "for": "county subdivision:*", "in": "state:09"}
)
r2010.raise_for_status()
d2010 = r2010.json()
df2010 = pd.DataFrame(d2010[1:], columns=d2010[0])
df2010['pop_2010'] = df2010['P001001'].astype(int)
df2010 = df2010[df2010['pop_2010'] > 0]          # drop "not defined" areas
df2010['key'] = df2010['NAME'].apply(clean_name)
print(f"2010 Decennial: {len(df2010)} records")

# ── ACS 2023 5-year ───────────────────────────────────────────────────────────
r2023 = requests.get(
    "https://api.census.gov/data/2023/acs/acs5",
    params={"get": "B01001_001E,NAME", "for": "county subdivision:*", "in": "state:09"}
)
r2023.raise_for_status()
d2023 = r2023.json()
df2023 = pd.DataFrame(d2023[1:], columns=d2023[0])
df2023['pop_2023'] = df2023['B01001_001E'].astype(int)
df2023 = df2023[df2023['pop_2023'] > 0]
df2023['key'] = df2023['NAME'].apply(clean_name)
print(f"ACS 2023:       {len(df2023)} records")

# ── Merge and compute change ──────────────────────────────────────────────────
df = df2010[['key','pop_2010']].merge(df2023[['key','pop_2023']], on='key')
df['pop_change'] = df['pop_2023'] - df['pop_2010']
df['pct_change']  = (df['pop_change'] / df['pop_2010'] * 100).round(1)
df['abs_pct']     = df['pct_change'].abs().round(1)
print(f"Merged:         {len(df)} towns")

# ── Get town centroids from existing GeoJSON ──────────────────────────────────
gdf = gpd.read_file('viz/public/ct_towns.geojson').to_crs('EPSG:4326')
gdf['key'] = gdf['NAME'].apply(clean_name)
gdf['centroid'] = gdf.geometry.centroid

matched = gdf[['key','NAME','centroid']].merge(df, on='key')
print(f"Matched:        {len(matched)} towns")
unmatched = df[~df['key'].isin(matched['key'])]['key'].tolist()
if unmatched:
    print("Unmatched:", unmatched)

# ── Build GeoJSON ─────────────────────────────────────────────────────────────
features = []
for _, row in matched.iterrows():
    features.append({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [round(row['centroid'].x, 5), round(row['centroid'].y, 5)]
        },
        "properties": {
            "name":       row['NAME'],
            "pop_2010":   int(row['pop_2010']),
            "pop_2023":   int(row['pop_2023']),
            "pop_change": int(row['pop_change']),
            "pct_change": float(row['pct_change']),
            "abs_pct":    float(row['abs_pct']),
        }
    })

out = {"type": "FeatureCollection", "features": features}
with open('viz/public/ct_pop_growth.geojson', 'w') as f:
    json.dump(out, f)

print(f"\nWrote {len(features)} features → viz/public/ct_pop_growth.geojson")
print("\nTop 5 growth:")
print(matched.nlargest(5,'pct_change')[['NAME','pop_2010','pop_2023','pct_change']].to_string(index=False))
print("\nTop 5 decline:")
print(matched.nsmallest(5,'pct_change')[['NAME','pop_2010','pop_2023','pct_change']].to_string(index=False))
