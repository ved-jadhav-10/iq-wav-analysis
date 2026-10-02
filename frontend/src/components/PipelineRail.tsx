import { Loader2, Minus } from 'lucide-react'
import type { Detection } from '@/lib/analysis'
import { LEVEL_INFO, type EvidenceLevel, type StageId } from '@/lib/evidence'
import { glossaryKeyFor } from '@/lib/glossary'
import { isPending, plainHeadline } from '@/lib/plainHeadline'
import { EvidenceBadge } from './EvidenceBadge'
import { InfoTip } from './InfoTip'
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
    <nav aria-label="Detections and pipeline" data-tour="detections" className="flex flex-col border-r bg-surface max-md:border-r-0 max-md:border-b xl:min-h-0 xl:overflow-y-auto">
      <div className="px-3 pt-3 pb-2">
        <h2 className="eyebrow">Detections</h2>
      </div>
      {detections.length === 0 && (
        <p className="mx-3 mb-2 rounded-md border border-dashed px-2 py-3 text-xs text-muted-foreground">
          No signal found above the noise floor. A longer capture, a different centre frequency or a higher gain would show weaker ones.
        </p>
      )}
      <ul className="space-y-px px-1.5">
        {detections.map((d) => {
          const active = d.id === selected.id
          const pending = isPending(d)
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
                  {pending ? (
                    <span className="inline-flex shrink-0 items-center gap-1 text-2xs font-medium text-muted-foreground" role="status">
                      <Loader2 className="size-3 animate-spin motion-reduce:animate-none" aria-hidden />
                      Analysing…
                    </span>
                  ) : (
                    <EvidenceBadge level={d.level} />
                  )}
                </div>
                {!pending && (
                  <>
                    <p className="mt-0.5 line-clamp-2 text-xs text-foreground">{plainHeadline(d)}</p>
                    <p title={d.headline} className="num mt-0.5 truncate text-2xs text-subtle-foreground">
                      {d.headline}
                    </p>
                  </>
                )}
              </button>
            </li>
          )
        })}
      </ul>

      <div className="mt-4 px-3 pb-2">
        <h2 className="eyebrow">Pipeline · #{selected.id}</h2>
      </div>
      {selected.stages.length === 0 && (
        <p className="mx-3 mb-3 rounded-md border border-dashed px-2 py-3 text-xs text-muted-foreground">
          {isPending(selected)
            ? 'Analysing this signal. A row appears here for each stage as it finishes.'
            : 'No stage has reported for this signal, so there is nothing to step through.'}
        </p>
      )}
      <ol className="relative px-1.5 pb-3">
        {selected.stages.map((s, i) => {
          const na = s.status === 'not-applicable'
          const active = s.id === activeStage
          const tip = glossaryKeyFor(s.name)
          return (
            <li key={s.id} className="relative">
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
              {tip && (
                <span className="absolute top-2 right-2.5 inline-flex">
                  <InfoTip term={tip} />
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
