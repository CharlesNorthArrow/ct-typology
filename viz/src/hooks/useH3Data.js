import { useState, useEffect } from 'react'
import { cellToBoundary } from 'h3-js'

const NUMERIC_FIELDS = ['baii_car', 'baii_pt', 'pop_total', 'multifamily_pct', 'dist_job_center_km']

function quantile(sorted, p) {
  const idx = p * (sorted.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo)
}

export function useH3Data() {
  const [geojson, setGeojson] = useState(null)
  const [fieldStats, setFieldStats] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/ct_h3.json')
      .then(r => {
        if (!r.ok) throw new Error(`Failed to load ct_h3.json: ${r.status}`)
        return r.json()
      })
      .then(rows => {
        // Compute quantile breakpoints for each numeric field
        const stats = {}
        for (const field of NUMERIC_FIELDS) {
          const vals = rows.map(r => r[field]).filter(v => v != null).sort((a, b) => a - b)
          stats[field] = {
            min: vals[0],
            max: vals[vals.length - 1],
            // 5 stops at 0%, 25%, 50%, 75%, 100% — maps evenly to the 5 color ramp
            quantiles: [0, 0.25, 0.5, 0.75, 1].map(p => quantile(vals, p)),
          }
        }

        // Build GeoJSON FeatureCollection — cellToBoundary(idx, true) returns [lng,lat]
        const features = rows.map((row, i) => {
          const boundary = cellToBoundary(row.h3_index, true)
          const ring = [...boundary, boundary[0]]
          return {
            type: 'Feature',
            id: i,
            geometry: { type: 'Polygon', coordinates: [ring] },
            properties: row,
          }
        })

        setFieldStats(stats)
        setGeojson({ type: 'FeatureCollection', features })
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return { geojson, fieldStats, loading, error }
}
