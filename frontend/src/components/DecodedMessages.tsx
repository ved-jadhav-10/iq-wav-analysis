import { useEffect, useRef, useState } from 'react'
import { Check, Copy, MessageSquareText } from 'lucide-react'
import type { Detection } from '@/lib/analysis'
import { decodedMessages, decodedMessagesAsText, type DecodedMessages as Decoded } from '@/lib/decodedMessages'
import { EvidenceBadge } from './EvidenceBadge'

/** The caption under the text: what it rests on. The engine's own convention follows in a disclosure. */
const TEXT_CAPTION =
  "Shown from codewords that pass the system's own check; the text itself rests on a convention and is never used as evidence."
const HEADER_CAPTION = "Read from the first frame that passes the system's own check."

type CopyState = 'idle' | 'copied' | 'failed'

/** One decoded-message card. Exported for tests. */
export function DecodedMessageCard({ d }: { d: Decoded }) {
  const [copy, setCopy] = useState<CopyState>('idle')
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])

  async function onCopy() {
    let next: CopyState = 'copied'
    try {
      await navigator.clipboard.writeText(decodedMessagesAsText(d))
    } catch {
      next = 'failed'
    }
    setCopy(next)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setCopy('idle'), 2000)
  }

  const titleId = `decoded-${d.parameterId}-title`
  return (
    <section aria-labelledby={titleId} className="relative rounded-md border bg-surface px-3 py-2.5" data-testid="decoded-message">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 id={titleId} className="flex items-center gap-1.5 text-[13px] font-semibold">
            <MessageSquareText className="size-3.5 shrink-0 text-primary" aria-hidden />
            {d.title}
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {d.system ? <span className="font-medium text-foreground">{d.system}</span> : 'Known system'}
            {d.value !== null && <> · {d.value}</>}
          </p>
        </div>
        <EvidenceBadge level={d.level} />
      </header>

      {d.lines.length === 0 ? (
        <p className="mt-2 rounded-md border border-dashed px-2 py-2 text-xs text-muted-foreground">
          The system matched, but the engine listed no lines to show. The check itself is in the Match stage below.
        </p>
      ) : (
        <div
          tabIndex={0}
          role="region"
          aria-label={`${d.name}, decoded lines`}
          className="num mt-2 max-h-40 overflow-y-auto rounded-md bg-surface-2 px-2 py-1.5 text-xs leading-relaxed"
        >
          <ul className="space-y-1">
            {d.lines.map((l, i) => (
              <li key={i} className="break-words whitespace-pre-wrap">
                {l.label && <span className="text-muted-foreground">{l.label}</span>}
                {l.label && (l.text !== null || l.note) && <span className="text-muted-foreground">{' → '}</span>}
                {l.text !== null ? (
                  <span className="text-foreground">{l.text}</span>
                ) : (
                  <span className="text-subtle-foreground italic">no text: {l.note}</span>
                )}
              </li>
            ))}
          </ul>
          {d.more > 0 && <p className="mt-1 text-subtle-foreground">… and {d.more} more not listed</p>}
        </div>
      )}
      {d.lines.length > 0 && !d.hasText && (
        <p className="mt-1.5 text-xs text-muted-foreground">
          No text was decoded from these codewords (numeric, or a codeword failed its check), so there is nothing to read here.
        </p>
      )}

      <div className="mt-2 flex items-start justify-between gap-2">
        <p className="text-2xs text-muted-foreground">{d.kind === 'header' ? HEADER_CAPTION : TEXT_CAPTION}</p>
        {d.lines.length > 0 && (
          <button
            type="button"
            onClick={onCopy}
            className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border-strong px-1.5 py-0.5 text-2xs font-medium hover:bg-background"
          >
            {copy === 'copied' ? <Check className="size-3" aria-hidden /> : <Copy className="size-3" aria-hidden />}
            {copy === 'copied' ? 'Copied' : copy === 'failed' ? 'Copy failed' : 'Copy'}
          </button>
        )}
      </div>
      <span role="status" className="sr-only">
        {copy === 'copied' ? 'Copied to the clipboard' : copy === 'failed' ? 'The clipboard is not available; select the text instead' : ''}
      </span>
      {d.convention && (
        <details className="mt-1.5 text-2xs text-muted-foreground">
          <summary className="cursor-pointer font-medium text-primary select-none">Convention</summary>
          <p className="mt-1">{d.convention}</p>
        </details>
      )}
    </section>
  )
}

/** The decoded text of the selected detection's known-system match, or nothing when the Match stage
 * has none. Each card keeps the Parameter's own level: this component never raises it. */
export function DecodedMessages({ detection }: { detection: Detection }) {
  const found = decodedMessages(detection.stages)
  if (found.length === 0) return null
  return (
    <div className="space-y-2">
      {found.map((d) => (
        <DecodedMessageCard key={d.parameterId} d={d} />
      ))}
    </div>
  )
}
