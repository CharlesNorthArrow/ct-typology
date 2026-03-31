// Color definitions for each layer type.

// Divergent categorical palette — semantically ordered dark→light by urban intensity,
// with clearly distinct hues so adjacent categories never read as the same.
export const URBAN_TYPE_COLORS = {
  urban_core:      '#7b2d8b',  // deep purple
  dense_suburban:  '#e05c1a',  // burnt orange
  suburban:        '#f5c518',  // amber yellow
  rural:           '#3a9e5f',  // medium green
  uninhabited:     '#e0e0e0',  // light gray
}

export const URBAN_TYPE_LABELS = {
  urban_core:     'Urban Core',
  dense_suburban: 'Dense Suburban',
  suburban:       'Suburban',
  rural:          'Rural',
  uninhabited:    'Uninhabited',
}

// Sequential ramp for continuous fields — 5 stops, pale → dark teal.
// Stop *positions* are injected as quantile breakpoints at runtime, not linear steps,
// so the gradient spreads evenly across the actual data distribution.
const SEQUENTIAL_COLORS = ['#f7fbff', '#c6dbef', '#6baed6', '#2171b5', '#084594']

function urbanTypeMatchExpression(fieldId) {
  return [
    'match',
    ['get', fieldId],
    'urban_core',     URBAN_TYPE_COLORS.urban_core,
    'dense_suburban', URBAN_TYPE_COLORS.dense_suburban,
    'suburban',       URBAN_TYPE_COLORS.suburban,
    'rural',          URBAN_TYPE_COLORS.rural,
    'uninhabited',    URBAN_TYPE_COLORS.uninhabited,
    '#cccccc',
  ]
}

// Build a Mapbox fill-color expression for the active field.
// fieldStats shape: { [fieldId]: { min, max, quantiles: [q0,q25,q50,q75,q100] } }
export function buildFillColor(fieldId, fieldStats) {
  if (fieldId === 'urban_type' || fieldId === 'urban_type_v2') {
    return urbanTypeMatchExpression(fieldId)
  }

  const stats = fieldStats[fieldId]
  if (!stats) return '#cccccc'

  const stops = stats.quantiles
  if (!stops || stops.every(v => v === stops[0])) return SEQUENTIAL_COLORS[2]

  // Map each quantile breakpoint to a color stop
  const colorStops = SEQUENTIAL_COLORS.flatMap((color, i) => [stops[i], color])

  return [
    'case',
    ['==', ['get', fieldId], null], '#cccccc',
    [
      'interpolate',
      ['linear'],
      ['get', fieldId],
      ...colorStops,
    ],
  ]
}

// Legend items for the sidebar
export function getLegendItems(fieldId, fieldStats) {
  if (fieldId === 'urban_type' || fieldId === 'urban_type_v2') {
    return Object.entries(URBAN_TYPE_COLORS).map(([value, color]) => ({
      color,
      label: URBAN_TYPE_LABELS[value],
      type: 'swatch',
    }))
  }

  const stats = fieldStats?.[fieldId]
  if (!stats?.quantiles) return []

  return SEQUENTIAL_COLORS.map((color, i) => ({
    color,
    value: stats.quantiles[i],
    type: 'gradient',
  }))
}
