import { Minus } from 'lucide-react'
import type { Detection } from '@/data/demoAnalysis'
import { LEVEL_INFO, type EvidenceLevel, type StageId } from '@/lib/evidence'
import { EvidenceBadge } from './EvidenceBadge'
import { LEVEL_ICON, LEVEL_TEXT } from './levelStyles'

function StageGlyph({ level }: { level: EvidenceLevel | null }) {
  if (!level) return <Minus className="mt-0.5 size-3.5 shrink-0 text-subtle-foreground" aria-hidden />
  const Icon = LEVEL_ICON[level]
  return (
    <Icon
      className={`mt-0.5 size-3.5 shrink-0 ${LEVEL_TEXT[level]}`}
      strokeWidth={2.25}
      aria-label={LEVEL_INFO[level].label}
    />
  )
}

interface Props {
  detections: Detection[]
  selected: Detection
  onSelectDetection: (id: number) => void
  activeStage: StageId | null
  onSelectStage: (id: StageId) => void
}

export function PipelineRail({ detections, selected, onSelectDetection, activeStage, onSelectStage }: Props) {
  return (
    <nav aria-label="Detections and pipeline" className="flex flex-col border-r bg-surface max-md:border-r-0 max-md:border-b xl:min-h-0 xl:overflow-y-auto">
      <div className="px-3 pt-3 pb-2">
        <h2 className="eyebrow">Detections</h2>
      </div>
      <ul className="space-y-px px-1.5">
        {detections.map((d) => {
          const active = d.id === selected.id
          return (
            <li key={d.id}>
              <button
                type="button"
                onClick={() => onSelectDetection(d.id)}
                aria-current={active ? 'true' : undefined}
                className={`group relative w-full rounded-md px-2 py-1.5 text-left transition-colors ${active ? 'bg-surface-2' : 'hover:bg-surface-2/60'}`}
              >
                {active && <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary" aria-hidden />}
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-medium">
                    <span className="num text-subtle-foreground">#{d.id}</span> {d.label}
                  </span>
                  <EvidenceBadge level={d.level} />
                </div>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{d.headline}</p>
              </button>
            </li>
          )
        })}
      </ul>

      <div className="mt-4 px-3 pb-2">
        <h2 className="eyebrow">Pipeline · #{selected.id}</h2>
      </div>
      <ol className="relative px-1.5 pb-3">
        {selected.stages.map((s, i) => {
          const na = s.status === 'not-applicable'
          const active = s.id === activeStage
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onSelectStage(s.id)}
                disabled={na}
                aria-current={active ? 'step' : undefined}
                className={`flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors enabled:hover:bg-surface-2/60 disabled:cursor-default ${active ? 'bg-surface-2' : ''}`}
              >
                <StageGlyph level={na ? null : s.level} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className={`text-[13px] ${na ? 'text-subtle-foreground' : 'font-medium'}`}>
                      <span className="num mr-1.5 text-2xs text-subtle-foreground">{String(i + 1).padStart(2, '0')}</span>
                      {s.name}
                    </span>
                  </span>
                  <span className={`block truncate text-xs ${na ? 'text-subtle-foreground italic' : 'text-muted-foreground'}`}>
                    {na ? `Not applicable — ${s.summary.toLowerCase()}` : s.summary}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
