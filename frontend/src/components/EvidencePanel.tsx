import { useEffect } from 'react'
import { ChevronRight, TriangleAlert } from 'lucide-react'
import type { Detection } from '@/data/demoAnalysis'
import type { Parameter, StageId } from '@/lib/evidence'
import { EvidenceBadge } from './EvidenceBadge'
import { formatValue } from '@/lib/format'
import { LEVEL_FILL } from './levelStyles'

function Confidence({ value, level }: { value: number; level: Parameter['level'] }) {
  const pct = Math.round(value * 100)
  return (
    <div className="mt-2 flex items-center gap-2">
      <div
        className="h-1 flex-1 overflow-hidden rounded-full bg-surface-2"
        role="meter"
        aria-label="Confidence"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
      >
        <div className={`h-full rounded-full ${LEVEL_FILL[level]}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="num w-[4ch] text-right text-2xs text-muted-foreground">{pct}%</span>
    </div>
  )
}

export function ParameterCard({ param }: { param: Parameter }) {
  const hasDetails = param.evidence.length > 0 || param.alternatives.length > 0
  return (
    <article className="rounded-md border bg-surface px-3 py-2.5">
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-xs text-muted-foreground">{param.name}</h4>
        <EvidenceBadge level={param.level} />
      </div>
      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5">
        {param.value === null ? (
          <span className="num text-[15px] text-subtle-foreground" aria-label="No value">
            —
          </span>
        ) : (
          <span className="num text-[15px] font-medium">{formatValue(param.value)}</span>
        )}
        {param.uncertainty != null && (
          <span className="num text-xs text-muted-foreground">± {formatValue(param.uncertainty)}</span>
        )}
        {param.unit && <span className="num text-xs text-muted-foreground">{param.unit}</span>}
      </p>
      {param.confidence !== null && <Confidence value={param.confidence} level={param.level} />}
      <p className="mt-1.5 text-xs text-muted-foreground">{param.method}</p>

      {param.warnings.map((w) => (
        <p key={w} className="mt-1.5 flex gap-1.5 text-xs text-ev-hypothesis">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {w}
        </p>
      ))}
      {param.resolveHint && (
        <p className="mt-1.5 text-xs">
          <span className="font-medium">To settle it: </span>
          <span className="text-muted-foreground">{param.resolveHint}</span>
        </p>
      )}

      {hasDetails && (
        <details className="group mt-2" open={param.level === 'UNKNOWN'}>
          <summary className="flex cursor-pointer list-none items-center gap-1 text-xs font-medium text-primary select-none [&::-webkit-details-marker]:hidden">
            <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" aria-hidden />
            Evidence ({param.evidence.length})
            {param.alternatives.length > 0 &&
              ` · ${param.alternatives.length} alternative${param.alternatives.length > 1 ? 's' : ''}`}
          </summary>
          {param.evidence.length > 0 && (
            <ul className="mt-1.5 space-y-1 border-l pl-3 text-xs text-muted-foreground">
              {param.evidence.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          {param.alternatives.length > 0 && (
            <dl className="mt-2 space-y-1">
              {param.alternatives.map((a) => (
                <div key={a.value} className="flex items-center justify-between gap-2 text-xs">
                  <dt className="num">{a.value}</dt>
                  <dd className="num text-muted-foreground">
                    {a.confidence === null ? 'unranked' : `${Math.round(a.confidence * 100)}%`}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </details>
      )}
    </article>
  )
}

export function EvidencePanel({ detection, activeStage }: { detection: Detection; activeStage: StageId | null }) {
  useEffect(() => {
    if (!activeStage) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById(`stage-${activeStage}`)?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  }, [activeStage, detection.id])

  return (
    <div className="space-y-5 px-3 py-3">
      <h2 className="sr-only">Evidence for detection {detection.id}</h2>
      {detection.stages.map((s) => (
        <section
          key={s.id}
          id={`stage-${s.id}`}
          aria-label={s.name}
          className={`scroll-mt-3 rounded-md transition-shadow ${s.id === activeStage ? 'ring-1 ring-primary/50 ring-offset-4 ring-offset-surface' : ''}`}
        >
          <header className="mb-1.5 flex items-center justify-between gap-2">
            <h3 className="eyebrow">{s.name}</h3>
          </header>
          {s.status === 'not-applicable' ? (
            <p className="text-xs text-subtle-foreground italic">Not applicable — {s.summary.toLowerCase()}.</p>
          ) : (
            <div className="space-y-2">
              {s.parameters.map((p) => (
                <ParameterCard key={p.id} param={p} />
              ))}
            </div>
          )}
        </section>
      ))}
    </div>
  )
}
