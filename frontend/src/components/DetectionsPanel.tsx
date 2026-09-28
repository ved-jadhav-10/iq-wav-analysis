import type { DetectionInfo } from '@/lib/api'
import { signed } from '@/lib/format'
import { EvidenceBadge } from './EvidenceBadge'

/** A detection's own findings summarised for the list: centre frequency and bandwidth from its
 * box (already converted to Hz - `detect`'s own Parameters stay in cycles/sample, unit-honest
 * without needing a sample rate), and the detector's SNR statistic from its Parameters. */
function headline(d: DetectionInfo): string {
  const centre = (d.box.f0 + d.box.f1) / 2
  const bandwidth = d.box.f1 - d.box.f0
  const snr = d.parameters.find((p) => p.id === 'snr_db')?.value
  const parts = [`Δf ${signed(centre / 1000, 1)} kHz`, `${(bandwidth / 1000).toFixed(1)} kHz BW`]
  if (typeof snr === 'number') parts.push(`${snr.toFixed(1)} dB SNR`)
  return parts.join(' · ')
}

interface Props {
  detections: DetectionInfo[]
  selectedId: number
  onSelect: (id: number) => void
}

/** The real detections found in an opened recording (PLAN §5 M2), in place of `PipelineRail`'s
 * demo pipeline - there is no per-stage rail yet because sync, classify and demod aren't built
 * (PLAN M3 onward), only `detect`'s own findings. */
export function DetectionsPanel({ detections, selectedId, onSelect }: Props) {
  return (
    <nav aria-label="Detections" className="flex flex-col border-r bg-surface max-md:border-r-0 max-md:border-b xl:min-h-0 xl:overflow-y-auto">
      <div className="px-3 pt-3 pb-2">
        <h2 className="eyebrow">Detections</h2>
      </div>
      {detections.length === 0 ? (
        <p className="px-3 pb-4 text-xs text-muted-foreground italic">
          No signals cleared the significance threshold in this recording.
        </p>
      ) : (
        <ul className="space-y-px px-1.5 pb-3">
          {detections.map((d, i) => {
            const active = i === selectedId
            return (
              <li key={d.id}>
                <button
                  type="button"
                  onClick={() => onSelect(i)}
                  aria-current={active ? 'true' : undefined}
                  className={`group relative w-full rounded-md px-2 py-1.5 text-left transition-colors ${active ? 'bg-surface-2' : 'hover:bg-surface-2/60'}`}
                >
                  {active && <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary" aria-hidden />}
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[13px] font-medium">
                      <span className="num text-subtle-foreground">#{i + 1}</span> Signal
                    </span>
                    <EvidenceBadge level={d.parameters[0]?.level ?? 'ESTIMATED'} />
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{headline(d)}</p>
                </button>
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-auto border-t px-3 py-2 text-xs text-muted-foreground">
        Synchronisation, classification and demodulation aren't built yet (PLAN M3 onward) - only
        detection's own findings are shown.
      </p>
    </nav>
  )
}
