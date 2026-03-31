import { getLegendItems } from '../lib/colorScales.js'
import { LAYER_BY_ID } from '../lib/layerConfig.js'

export default function Legend({ activeField, fieldStats }) {
  const layer = LAYER_BY_ID[activeField]
  const items = getLegendItems(activeField, fieldStats)
  if (!items.length) return null

  return (
    <div className="legend">
      <div className="legend-title">{layer.label}</div>
      {layer.type === 'categorical' ? (
        <div className="legend-swatches">
          {items.map(item => (
            <div key={item.label} className="legend-row">
              <span className="legend-swatch" style={{ background: item.color }} />
              <span className="legend-label">{item.label}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="legend-gradient-wrap">
          <div
            className="legend-gradient-bar"
            style={{
              background: `linear-gradient(to right, ${items.map(i => i.color).join(', ')})`,
            }}
          />
          <div className="legend-gradient-labels">
            <span>{formatValue(items[0].value, layer)}</span>
            <span>{formatValue(items[Math.floor(items.length / 2)].value, layer)}</span>
            <span>{formatValue(items[items.length - 1].value, layer)}</span>
          </div>
        </div>
      )}
      <div className="legend-desc">{layer.description}</div>
    </div>
  )
}

function formatValue(v, layer) {
  if (layer.format) return layer.format(v)
  return typeof v === 'number' ? v.toLocaleString() : String(v)
}
