import { TriangleAlert } from 'lucide-react'
import type { Parameter } from '@/lib/evidence'
import { ParameterCard } from './EvidencePanel'

/** What the samples say about how the recording was captured (`dsp.quality`): clipping, DC offset,
 * I/Q imbalance and gaps. Each is the same `Parameter` card the stages use, so its level, method
 * and evidence read the same way; a warning is a real fault of the capture and is always shown
 * on its card, with a count in the heading, so it is never behind a disclosure. */
export function CaptureQualitySection({ parameters }: { parameters: readonly Parameter[] }) {
  const warnings = parameters.reduce((n, p) => n + p.warnings.length, 0)
  return (
    <section aria-label="Capture quality" className="border-t">
      <header className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <h3 className="eyebrow">Capture quality</h3>
        {warnings > 0 && (
          <span className="flex items-center gap-1 text-xs font-medium text-ev-hypothesis">
            <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
            {warnings} {warnings === 1 ? 'warning' : 'warnings'}
          </span>
        )}
      </header>
      {parameters.length === 0 ? (
        <p className="px-3 py-2.5 text-xs text-muted-foreground">No capture-quality measurements for this recording.</p>
      ) : (
        <div className="grid grid-cols-1 gap-2 px-3 py-2.5 sm:grid-cols-2">
          {parameters.map((p) => (
            <ParameterCard key={p.id} param={p} />
          ))}
        </div>
      )}
    </section>
  )
}
