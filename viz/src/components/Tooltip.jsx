import { createPortal } from 'react-dom'
import { LAYERS } from '../lib/layerConfig.js'
import { URBAN_TYPE_LABELS } from '../lib/colorScales.js'

export default function Tooltip({ feature, position }) {
  if (!feature || !position) return null

  const { urban_type, pop_total, baii_car, baii_pt, multifamily_pct, dist_job_center_km } = feature

  const tooltip = (
    <div
      className="tooltip"
      style={{
        left: position.x + 14,
        top: position.y - 10,
      }}
    >
      <div className="tooltip-type">{URBAN_TYPE_LABELS[urban_type] ?? urban_type}</div>
      <table className="tooltip-table">
        <tbody>
          {LAYERS.filter(l => l.id !== 'urban_type').map(layer => (
            <tr key={layer.id}>
              <td className="tooltip-key">{layer.label}</td>
              <td className="tooltip-val">{layer.format(feature[layer.id])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  return createPortal(tooltip, document.body)
}
