import { useState } from 'react'
import type { Assumptions, AssumptionValues } from '@/lib/api'
import { parseFrequency } from '@/lib/format'

interface Props {
  assumptions: Assumptions
  /** Sends the entered values; rejects with a message the form shows. */
  onSubmit: (values: AssumptionValues) => Promise<void>
}

const BUTTON =
  'rounded-md border border-border-strong px-2 py-1 text-xs font-medium text-muted-foreground enabled:hover:bg-background enabled:hover:text-foreground disabled:opacity-40'

/** What the analyst can say about a recording that the file doesn't, or gets wrong: the centre
 * frequency, and whether Q comes first. Each is recorded as entered by the analyst, checked
 * against nothing in the samples, and restarts the analysis. */
export function AssumptionEntry({ assumptions, onSubmit }: Props) {
  const [frequency, setFrequency] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send(values: AssumptionValues) {
    setBusy(true)
    setError(null)
    try {
      await onSubmit(values)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const order = assumptions.iqOrder
  const swapped = order?.value === 'QI'

  return (
    <section aria-label="Enter what you know" className="flex flex-col gap-3 border-b px-3 py-2.5 text-xs">
      <p className="text-muted-foreground">
        Enter what the file doesn’t say. Entries are recorded as entered by you, nothing in the samples confirms them,
        and the analysis restarts.
      </p>
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          const hz = parseFrequency(frequency)
          if (hz === null) {
            setError('Enter a frequency of zero or more, e.g. 433.92M or 518k.')
            return
          }
          void send({ centerFrequency: hz })
        }}
      >
        <label htmlFor="center-frequency-entry" className="w-32 text-muted-foreground">
          Centre frequency
        </label>
        <input
          id="center-frequency-entry"
          type="text"
          inputMode="decimal"
          value={frequency}
          onChange={(e) => setFrequency(e.target.value)}
          placeholder="e.g. 433.92M"
          className="num w-40 rounded-md border border-border-strong bg-surface px-2 py-1 text-xs text-foreground placeholder:text-subtle-foreground"
        />
        <button type="submit" disabled={busy || !frequency.trim()} className={BUTTON}>
          Set centre frequency
        </button>
      </form>
      {order ? (
        <div className="flex flex-wrap items-center gap-2">
          <span id="iq-order-label" className="w-32 text-muted-foreground">
            IQ order
          </span>
          <div role="radiogroup" aria-labelledby="iq-order-label" className="flex gap-1">
            {(['IQ', 'QI'] as const).map((value) => {
              const selected = (order.value === 'QI') === (value === 'QI')
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  disabled={busy}
                  onClick={() => !selected && void send({ iqOrder: value })}
                  className={`num rounded-md border px-2 py-1 text-xs font-medium disabled:opacity-40 ${
                    selected
                      ? 'border-primary bg-surface-2 text-foreground'
                      : 'border-border-strong text-muted-foreground hover:bg-background hover:text-foreground'
                  }`}
                >
                  {value}
                </button>
              )
            })}
          </div>
          <span className="min-w-0 flex-1 basis-64 text-muted-foreground">
            {swapped ? 'Q comes first, so the spectrum is mirrored. ' : 'I comes first. '}
            The samples can’t tell the two apart: swap it if a carrier you know sits on the wrong side.
          </span>
        </div>
      ) : (
        <p className="text-muted-foreground">IQ order doesn’t apply: the samples are real-valued.</p>
      )}
      {error && (
        <span role="alert" className="text-destructive">
          {error}
        </span>
      )}
    </section>
  )
}
