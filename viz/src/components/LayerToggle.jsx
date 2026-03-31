import { LAYERS } from '../lib/layerConfig.js'

export default function LayerToggle({ activeField, onChange }) {
  return (
    <div className="layer-toggle">
      <div className="layer-toggle-label">View by</div>
      <div className="layer-toggle-buttons">
        {LAYERS.map(layer => (
          <button
            key={layer.id}
            className={`toggle-btn${activeField === layer.id ? ' active' : ''}`}
            onClick={() => onChange(layer.id)}
          >
            {layer.label}
          </button>
        ))}
      </div>
    </div>
  )
}
