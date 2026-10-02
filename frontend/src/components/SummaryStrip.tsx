import { useState } from 'react'
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react'
import { useSummary } from '@/hooks/useSummary'
import { loadSummaryOpen, storeSummaryOpen, summaryLines, type SummaryLineKind, type SummaryState } from '@/lib/summary'

export const SUMMARY_BODY_ID = 'plain-language-summary'

const LINE_CLASS: Record<SummaryLineKind, string> = {
  title: 'font-semibold text-foreground',
  heading: 'mt-1.5 font-semibold text-foreground',
  subheading: 'font-medium text-muted-foreground',
  item: 'text-foreground',
  text: 'text-foreground',
  blank: 'h-1',
}

interface ViewProps {
  state: SummaryState
  open: boolean
  onToggle: () => void
  onRetry: () => void
}

/** The summary's text as the server wrote it, one line per line, in the monospace tabular face. */
function SummaryText({ text }: { text: string }) {
  return (
    <>
      {summaryLines(text).map((line, i) => (
        <div key={i} className={`whitespace-pre-wrap break-words ${LINE_CLASS[line.kind]}`}>
          {line.text}
        </div>
      ))}
    </>
  )
}

/** The plain-language summary strip (presentation only: `SummaryStrip` owns the state). It sits
 * above the Survey layout, `shrink-0`, and its body is capped in height with its own scrolling, so
 * a long summary never grows the strip past the cap or the page past the window. */
export function SummaryView({ state, open, onToggle, onRetry }: ViewProps) {
  return (
    <section aria-label="Plain-language summary" className="flex shrink-0 flex-col border-b bg-surface">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={SUMMARY_BODY_ID}
        title={open ? 'Collapse the summary' : 'Expand the summary'}
        className="flex h-7 shrink-0 items-center gap-1.5 px-3 text-left hover:bg-surface-2/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
      >
        {open ? (
          <ChevronDown className="size-3.5 text-muted-foreground" aria-hidden />
        ) : (
          <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden />
        )}
        <h2 className="eyebrow">Summary</h2>
        <span className="truncate text-2xs text-muted-foreground">
          {state.status === 'loading'
            ? 'Loading…'
            : state.status === 'error'
              ? 'Could not be loaded'
              : 'What was proved, what was only estimated, what is unknown'}
        </span>
      </button>
      <div id={SUMMARY_BODY_ID} hidden={!open}>
        {state.status === 'loading' && (
          <p role="status" className="px-3 pb-2 text-xs text-muted-foreground italic">
            Loading the summary…
          </p>
        )}
        {state.status === 'error' && (
          <div role="alert" className="flex flex-wrap items-center gap-2 px-3 pb-2 text-xs text-destructive">
            <span className="min-w-0 break-words">Could not load the summary: {state.message}</span>
            <button
              type="button"
              onClick={onRetry}
              className="flex items-center gap-1 rounded-md border border-border-strong px-1.5 py-0.5 text-2xs font-medium text-foreground uppercase hover:bg-surface-2"
            >
              <RefreshCw className="size-3" aria-hidden />
              Retry
            </button>
          </div>
        )}
        {state.status === 'ready' && (
          // Focusable so the keyboard can scroll it; `max-h` bounds it and `overflow-y-auto` holds
          // the rest, which is what keeps the page itself from growing.
          <div
            role="region"
            aria-label="Summary text"
            tabIndex={0}
            className="num max-h-[min(22vh,160px)] overflow-y-auto px-3 pb-2 text-xs leading-[1.15rem] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
          >
            <SummaryText text={state.text} />
          </div>
        )}
      </div>
    </section>
  )
}

/** The summary of a recording whose analysis has finished (the caller mounts this only then, so
 * every finish fetches the text afresh). Open or collapsed is remembered across reloads. */
export function SummaryStrip({ recordingId }: { recordingId: string }) {
  const { state, retry } = useSummary(recordingId)
  const [open, setOpen] = useState(loadSummaryOpen)
  return (
    <SummaryView
      state={state}
      open={open}
      onToggle={() => {
        storeSummaryOpen(!open)
        setOpen(!open)
      }}
      onRetry={retry}
    />
  )
}
