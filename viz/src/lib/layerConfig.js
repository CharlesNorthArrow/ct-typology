// Metadata for each field available in the layer toggle.
// type: 'categorical' | 'continuous'
// format: function to display a raw value in the tooltip

export const LAYERS = [
  {
    id: 'urban_type',
    label: 'Urban Typology',
    type: 'categorical',
    description: 'Derived from population density, multifamily housing share, and distance to employment centers.',
  },
  {
    id: 'urban_type_v2',
    label: 'Typology (Rationalized)',
    type: 'categorical',
    description: 'Same framework as v1 but with neighborhood-smoothed population (k=1 ring avg) and 2 rounds of majority filter to remove isolated cells.',
  },
  {
    id: 'baii_car',
    label: 'BAII — Car',
    type: 'continuous',
    description: 'Book-Access Infrastructure Index score for car travel mode.',
    format: v => (v == null ? 'N/A' : v.toFixed(2)),
    unit: '',
  },
  {
    id: 'baii_pt',
    label: 'BAII — Transit',
    type: 'continuous',
    description: 'Book-Access Infrastructure Index score for public transit travel mode.',
    format: v => (v == null ? 'N/A' : v.toFixed(2)),
    unit: '',
  },
  {
    id: 'pop_total',
    label: 'Population',
    type: 'continuous',
    description: 'WorldPop model estimate of population per H3 cell (~0.74 km²).',
    format: v => (v == null ? 'N/A' : v.toLocaleString('en-US', { maximumFractionDigits: 0 })),
    unit: 'people',
  },
  {
    id: 'multifamily_pct',
    label: 'Multifamily Housing',
    type: 'continuous',
    description: 'Share of housing units in structures with 2+ units (ACS B25024, tract level).',
    format: v => (v == null ? 'N/A' : `${(v * 100).toFixed(1)}%`),
    unit: '',
  },
  {
    id: 'dist_job_center_km',
    label: 'Distance to Job Center',
    type: 'continuous',
    description: 'Euclidean distance to nearest LODES-derived employment center (top 10% by jobs).',
    format: v => (v == null ? 'N/A' : `${v.toFixed(1)} km`),
    unit: 'km',
  },
]

export const LAYER_BY_ID = Object.fromEntries(LAYERS.map(l => [l.id, l]))
