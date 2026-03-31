import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { buildFillColor } from '../lib/colorScales.js'

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN

const INITIAL_VIEW = { center: [-72.65, 41.6], zoom: 8.2 }

export default function Map({ geojson, activeField, fieldStats, showBoundaries, onHover, onLeave }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const hoveredIdRef = useRef(null)

  // Initialize map once
  useEffect(() => {
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      ...INITIAL_VIEW,
    })
    map.addControl(new mapboxgl.NavigationControl(), 'top-right')
    mapRef.current = map
    return () => map.remove()
  }, [])

  // Add H3 hexagon source + layers when data arrives
  useEffect(() => {
    const map = mapRef.current
    if (!map || !geojson) return

    const addLayers = () => {
      if (map.getSource('hexagons')) return

      map.addSource('hexagons', { type: 'geojson', data: geojson, generateId: false })

      map.addLayer({
        id: 'hexagons-fill',
        type: 'fill',
        source: 'hexagons',
        paint: {
          'fill-color': buildFillColor(activeField, fieldStats),
          'fill-opacity': [
            'case', ['boolean', ['feature-state', 'hovered'], false], 0.92, 0.72,
          ],
        },
      })

      map.addLayer({
        id: 'hexagons-line',
        type: 'line',
        source: 'hexagons',
        paint: {
          'line-color': [
            'case', ['boolean', ['feature-state', 'hovered'], false],
            '#ffffff', 'rgba(255,255,255,0.25)',
          ],
          'line-width': [
            'case', ['boolean', ['feature-state', 'hovered'], false], 1.5, 0.3,
          ],
        },
      })

      // Municipal boundary layers (added here so they sit above hexagons)
      map.addSource('towns', { type: 'geojson', data: '/ct_towns.geojson' })

      map.addLayer({
        id: 'towns-line',
        type: 'line',
        source: 'towns',
        layout: { visibility: 'none' },
        paint: {
          'line-color': '#1c3557',
          'line-width': 1.2,
          'line-opacity': 0.7,
        },
      })

      // Hover events
      map.on('mousemove', 'hexagons-fill', e => {
        if (!e.features.length) return
        const feature = e.features[0]
        if (hoveredIdRef.current !== null) {
          map.setFeatureState({ source: 'hexagons', id: hoveredIdRef.current }, { hovered: false })
        }
        hoveredIdRef.current = feature.id
        map.setFeatureState({ source: 'hexagons', id: feature.id }, { hovered: true })
        map.getCanvas().style.cursor = 'pointer'
        onHover(feature.properties, e.point)
      })

      map.on('mouseleave', 'hexagons-fill', () => {
        if (hoveredIdRef.current !== null) {
          map.setFeatureState({ source: 'hexagons', id: hoveredIdRef.current }, { hovered: false })
          hoveredIdRef.current = null
        }
        map.getCanvas().style.cursor = ''
        onLeave()
      })
    }

    if (map.isStyleLoaded()) {
      addLayers()
    } else {
      map.once('load', addLayers)
    }
  }, [geojson])

  // Update fill color when active field changes
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.getLayer('hexagons-fill')) return
    map.setPaintProperty('hexagons-fill', 'fill-color', buildFillColor(activeField, fieldStats))
  }, [activeField, fieldStats])

  // Toggle municipal boundary visibility
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.getLayer('towns-line')) return
    map.setLayoutProperty('towns-line', 'visibility', showBoundaries ? 'visible' : 'none')
  }, [showBoundaries])

  return <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
}
