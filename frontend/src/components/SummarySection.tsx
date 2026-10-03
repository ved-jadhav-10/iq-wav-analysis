import { Loader2, RefreshCw } from 'lucide-react'
import { useSummary } from '@/hooks/useSummary'
import { summaryLines, type SummaryLineKind, type SummaryState } from '@/lib/summary'

const LINE_CLASS: Record<SummaryLineKind, string> = {
  title: 'font-semibold text-foreground',
  heading: 'mt-3 font-semibold text-foreground',
  subheading: 'font-medium text-muted-foreground',
  item: 'text-foreground',
  text: 'text-foreground',
  blank: 'h-1',
}

interface ViewProps {
  state: SummaryState
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

/** The plain-language summary section (presentation only). A header strip, then the text in a
 * panel that fills the rest of the height and scrolls inside itself, so a long summary never grows
 * the page. */
export function SummaryView({ state, onRetry }: ViewProps) {
  return (
    <main aria-label="Summary" data-tour="summary" className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <div className="flex h-8 shrink-0 items-center gap-2 border-b bg-surface px-3">
        <h2 className="eyebrow">Summary</h2>
        <span className="truncate text-2xs text-muted-foreground">
          What was proved, what was only estimated, what is unknown
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {state.status === 'loading' && (
          <p role="status" className="px-4 py-4 text-xs text-muted-foreground italic">
            Loading the summary…
          </p>
        )}
        {state.status === 'error' && (
          <div role="alert" className="flex flex-wrap items-center gap-2 px-4 py-4 text-xs text-destructive">
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
          // Focusable so the keyboard can scroll it.
          <div
            role="region"
            aria-label="Summary text"
            tabIndex={0}
            className="num mx-auto max-w-5xl px-4 py-4 text-xs leading-[1.15rem] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
          >
            <SummaryText text={state.text} />
          </div>
        )}
      </div>
    </main>
  )
}

/** The summary of a recording whose analysis has finished (mounted only then, so every finish
 * fetches the text afresh). */
export function SummarySection({ recordingId }: { recordingId: string }) {
  const { state, retry } = useSummary(recordingId)
  return <SummaryView state={state} onRetry={retry} />
}

/** What the section shows while the analysis is still running: the summary is written from the
 * finished results, so there is nothing to fetch yet. */
export function SummaryWaiting({ done, total }: { done: number; total: number }) {
  return (
    <main aria-label="Summary" data-tour="summary" className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
      <div className="flex h-8 shrink-0 items-center gap-2 border-b bg-surface px-3">
        <h2 className="eyebrow">Summary</h2>
      </div>
      <p role="status" className="flex items-center gap-2 px-4 py-4 text-xs text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
        The summary is written once the analysis finishes
        {total > 0 ? ` (signal ${Math.min(done + 1, total)} of ${total})` : ''}.
      </p>
    </main>
  )
}
