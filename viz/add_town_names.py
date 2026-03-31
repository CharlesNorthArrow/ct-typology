#!/usr/bin/env python3
"""
Spatial join: adds a 'town' field to ct_h3.geojson based on which CT municipality
each H3 cell centroid falls within. Cells on the water or state boundary that
don't match any town get an empty string.
"""
import json, sys
import geopandas as gpd

GEOJSON  = 'public/ct_h3.geojson'
TOWNS    = 'public/ct_towns.geojson'

print('Loading files…')
h3_gdf    = gpd.read_file(GEOJSON)
towns_gdf = gpd.read_file(TOWNS).to_crs(h3_gdf.crs)

print(f'  H3 cells : {len(h3_gdf):,}')
print(f'  Towns    : {len(towns_gdf)}')

# Build centroid GDF for the join
centroids = gpd.GeoDataFrame(
    {'h3_index': h3_gdf['h3_index']},
    geometry=h3_gdf.geometry.centroid,
    crs=h3_gdf.crs
)

joined = gpd.sjoin(
    centroids, towns_gdf[['NAME', 'geometry']],
    how='left', predicate='within'
).drop_duplicates(subset='h3_index', keep='first')

town_map = joined.set_index('h3_index')['NAME']
h3_gdf['town'] = h3_gdf['h3_index'].map(town_map).fillna('')

matched = (h3_gdf['town'] != '').sum()
print(f'  Matched  : {matched:,} of {len(h3_gdf):,} cells')
print(f'  Unmatched: {len(h3_gdf)-matched} (water / state edge)')

print('\nTop 10 towns by cell count:')
for town, n in h3_gdf['town'].value_counts().head(10).items():
    print(f'  {town}: {n}')

print(f'\nWriting {GEOJSON}…')
h3_gdf.to_file(GEOJSON, driver='GeoJSON')
print('Done.')
