import type { Assumptions, AssumptionValues } from '@/lib/api'
import type { Parameter } from '@/lib/evidence'
import { integer } from '@/lib/format'
import { AssumptionEntry } from './AssumptionEntry'
import { ParameterCard } from './EvidencePanel'

/** The backend sends a bare number; every other number in the workspace is thousands-grouped. */
function withFormattedValue(p: Parameter): Parameter {
  return typeof p.value === 'number' ? { ...p, value: integer.format(p.value) } : p
}

/** The real Assumptions block a recording was opened with (PLAN §5 M2): the same `Parameter`
 * evidence cards `EvidencePanel` uses for a stage result, since an assumption carries the same
 * honesty rules (UNKNOWN states why, a convention is named, nothing is silently defaulted). */
export function RecordingAssumptionsPanel({
  assumptions,
  onEnter,
}: {
  assumptions: Assumptions
  /** Sends values the analyst entered; rejects with a message the form shows. */
  onEnter: (values: AssumptionValues) => Promise<void>
}) {
  const params = [
    assumptions.datatype,
    assumptions.dataOffset,
    assumptions.sampleRate,
    assumptions.centerFrequency,
    assumptions.iqOrder,
  ]
    .filter((p) => p !== null)
    .map(withFormattedValue)

  return (
    <section aria-label="Recording assumptions" className="flex min-h-0 flex-col overflow-auto border-t bg-surface">
      <p className="border-b px-3 py-2 text-xs text-muted-foreground">
        Everything opening this recording took as given.
      </p>
      <AssumptionEntry assumptions={assumptions} onSubmit={onEnter} />
      <div className="grid grid-cols-1 gap-2 px-3 py-2.5 sm:grid-cols-2">
        {params.map((p) => (
          <ParameterCard key={p.id} param={p} />
        ))}
      </div>
    </section>
  )
}
