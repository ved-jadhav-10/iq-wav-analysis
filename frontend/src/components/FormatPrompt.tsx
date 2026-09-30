import { useState } from 'react'
import { EvidenceBadge } from './EvidenceBadge'

interface Props {
  /** The file's name, for the message. */
  name: string
  /** The sniffer's candidates; may be none. */
  candidates: string[]
  /** Opens the file as this sample format; rejects with a message the prompt shows. */
  onChoose: (datatype: string) => Promise<void>
  onDismiss: () => void
}

/** Shown when a raw file's sample format is UNKNOWN: the recording can't be drawn until the
 * analyst chooses one. Candidates are suggestions, never applied unasked. */
export function FormatPrompt({ name, candidates, onChoose, onDismiss }: Props) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function choose(datatype: string) {
    setBusy(true)
    setError(null)
    try {
      await onChoose(datatype)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  return (
    <section
      aria-label="Sample format needed"
      className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1.5 border-b bg-surface-2 px-3 py-1.5 text-xs"
    >
      <EvidenceBadge level="UNKNOWN" />
      <p className="min-w-0 flex-1 basis-72 text-muted-foreground">
        <strong className="font-semibold text-foreground">Sample format unknown for {name}.</strong> The bytes don’t
        settle it, so nothing is drawn until you choose one.{' '}
        {candidates.length === 0 ? 'The sniffer has no candidates; type a SigMF datatype.' : 'Candidates from the sniffer:'}
      </p>
      {candidates.length > 0 && (
        <ul className="flex flex-wrap items-center gap-1" aria-label="Candidate sample formats">
          {candidates.map((c) => (
            <li key={c}>
              <button
                type="button"
                disabled={busy}
                onClick={() => void choose(c)}
                className="num rounded-md border border-border-strong px-1.5 py-0.5 text-2xs text-muted-foreground enabled:hover:bg-background enabled:hover:text-foreground disabled:opacity-40"
              >
                {c}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="flex items-center gap-1.5"
        onSubmit={(e) => {
          e.preventDefault()
          void choose(text.trim())
        }}
      >
        <label htmlFor="datatype-entry" className="sr-only">
          Sample format as a SigMF datatype
        </label>
        <input
          id="datatype-entry"
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. cu8, ci16_le"
          className="num w-36 rounded-md border border-border-strong bg-surface px-2 py-1 text-xs text-foreground placeholder:text-subtle-foreground"
        />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="rounded-md border border-border-strong px-2 py-1 text-xs font-medium text-muted-foreground enabled:hover:bg-background enabled:hover:text-foreground disabled:opacity-40"
        >
          {busy ? 'Opening…' : 'Use format'}
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
        >
          Dismiss
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
