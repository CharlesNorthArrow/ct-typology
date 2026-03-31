import { useState } from 'react'
import Map from './components/Map.jsx'
import Legend from './components/Legend.jsx'
import LayerToggle from './components/LayerToggle.jsx'
import Tooltip from './components/Tooltip.jsx'
import { useH3Data } from './hooks/useH3Data.js'

export default function App() {
  const { geojson, fieldStats, loading, error } = useH3Data()
  const [activeField, setActiveField] = useState('urban_type')
  const [showBoundaries, setShowBoundaries] = useState(false)
  const [hoveredFeature, setHoveredFeature] = useState(null)
  const [tooltipPos, setTooltipPos] = useState(null)

  return (
    <div className="app">
      <header className="header">
        <div className="header-title">CT Book Access — Urban Typology</div>
        <div className="header-sub">H3 Resolution 8 · Connecticut · North Arrow for Read to Grow</div>
      </header>

      <div className="map-wrap">
        {loading && (
          <div className="loading-overlay">
            <div className="loading-text">Building H3 grid…</div>
          </div>
        )}
        {error && (
          <div className="error-overlay">
            <div className="error-text">Error: {error}</div>
          </div>
        )}
        <Map
          geojson={geojson}
          activeField={activeField}
          fieldStats={fieldStats}
          showBoundaries={showBoundaries}
          onHover={(props, pt) => { setHoveredFeature(props); setTooltipPos({ x: pt.x, y: pt.y }) }}
          onLeave={() => { setHoveredFeature(null); setTooltipPos(null) }}
        />
        <div className="sidebar">
          <LayerToggle activeField={activeField} onChange={setActiveField} />
          <button
            className={`boundary-toggle${showBoundaries ? ' active' : ''}`}
            onClick={() => setShowBoundaries(v => !v)}
          >
            {showBoundaries ? '▣' : '□'} Municipal Boundaries
          </button>
          <Legend activeField={activeField} fieldStats={fieldStats} />
        </div>
      </div>

      <Tooltip feature={hoveredFeature} position={tooltipPos} />
    </div>
  )
}
