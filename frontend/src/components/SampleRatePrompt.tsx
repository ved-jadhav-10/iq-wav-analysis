import { useState } from 'react'
import type { Parameter } from '@/lib/evidence'
import { formatRate, parseRate } from '@/lib/format'
import { EvidenceBadge } from './EvidenceBadge'

interface Props {
  /** The recording's sample-rate assumption; its alternatives are offered as candidates. */
  sampleRate: Parameter
  /** Sends the entered rate (S/s); rejects with a message the prompt shows. */
  onSubmit: (rate: number) => Promise<void>
}

/** Shown while a recording's sample rate is UNKNOWN: the plots are in fractions of the rate and
 * samples, and the detections wait for a rate. Candidates are suggestions, never applied
 * unasked. */
export function SampleRatePrompt({ sampleRate, onSubmit }: Props) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const candidates = sampleRate.alternatives.map((a) => a.value).filter((v): v is number => typeof v === 'number')

  async function submit(rate: number | null) {
    if (rate === null) {
      setError('Enter a positive number, e.g. 2.4M or 250000.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onSubmit(rate)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  return (
    <section
      aria-label="Sample rate needed"
      className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1.5 border-b bg-surface-2 px-3 py-1.5 text-xs"
    >
      <EvidenceBadge level="UNKNOWN" />
      <p className="min-w-0 flex-1 basis-72 text-muted-foreground">
        <strong className="font-semibold text-foreground">Sample rate unknown.</strong> The file doesn’t state it, so
        frequency is shown as a fraction of it and time in samples, and signals aren’t analysed yet.{' '}
        {sampleRate.resolveHint}
      </p>
      {candidates.length > 0 && (
        <ul className="flex flex-wrap items-center gap-1" aria-label="Candidate sample rates">
          {candidates.slice(0, 6).map((c) => (
            <li key={c}>
              <button
                type="button"
                disabled={busy}
                onClick={() => void submit(c)}
                className="num rounded-md border border-border-strong px-1.5 py-0.5 text-2xs text-muted-foreground enabled:hover:bg-background enabled:hover:text-foreground disabled:opacity-40"
              >
                {formatRate(c)}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="flex items-center gap-1.5"
        onSubmit={(e) => {
          e.preventDefault()
          void submit(parseRate(text))
        }}
      >
        <label htmlFor="sample-rate-entry" className="sr-only">
          Sample rate in samples per second
        </label>
        <input
          id="sample-rate-entry"
          type="text"
          inputMode="decimal"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Sample rate, e.g. 2.4M"
          className="num w-40 rounded-md border border-border-strong bg-surface px-2 py-1 text-xs text-foreground placeholder:text-subtle-foreground"
        />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="rounded-md border border-border-strong px-2 py-1 text-xs font-medium text-muted-foreground enabled:hover:bg-background enabled:hover:text-foreground disabled:opacity-40"
        >
          {busy ? 'Applying…' : 'Set rate'}
        </button>
      </form>
      {error && (
        <span role="alert" className="basis-full text-destructive">
          {error}
        </span>
      )}
    </section>
  )
}
