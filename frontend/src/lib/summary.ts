/**
 * The plain-language summary of a finished analysis: the text `GET /api/v1/recordings/{id}/results
 * ?format=txt` serves (`dsp/summary.py`, a fixed template over the results document, never a
 * model). The UI shows it as the server wrote it, line for line; this module only fetches it, tells
 * its headings from its items for styling.
 */
import type { RecordingInfo } from './api'

/** What the Summary section shows: nothing is fetched until an analysis has finished. */
export type SummaryState =
  | { status: 'loading' }
  | { status: 'ready'; text: string }
  | { status: 'error'; message: string }

/** The recording whose summary belongs on screen, or null: the synthetic in-browser capture has no
 * recording behind it (`info` is null), and the server answers 409 until the analysis is done. */
export function summaryTarget(info: Pick<RecordingInfo, 'id' | 'analysis'> | null): string | null {
  return info && info.analysis.state === 'done' ? info.id : null
}

export function summaryUrl(id: string): string {
  return `/api/v1/recordings/${encodeURIComponent(id)}/results?format=txt`
}

/** The server keeps the finished analysis on its worker thread just after its state turns `done`,
 * so a 409 right then is waited out, not shown: these are the pauses before each further try. */
export const NOT_READY_RETRY_MS: readonly number[] = [250, 500, 1000, 2000]

interface LoadOptions {
  fetchImpl?: typeof fetch
  signal?: AbortSignal
  /** Pauses before each retry of a 409; its length is the number of retries. */
  retryMs?: readonly number[]
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>
}

function pause(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('aborted', 'AbortError'))
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer)
        reject(new DOMException('aborted', 'AbortError'))
      },
      { once: true },
    )
  })
}

/** The server's own words for a failed request: its `detail`, else the status line. */
async function failure(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null)
  if (typeof body === 'object' && body && 'detail' in body) return String(body.detail)
  return `request failed: ${response.status} ${response.statusText}`.trim()
}

/** Fetches the summary text. A 409 (the analysis has not finished as far as the server knows) is
 * retried after each pause in `retryMs`; any other failure, or the last 409, rejects with the
 * server's text. Rejects with an AbortError if `signal` aborts. */
export async function loadSummary(id: string, options: LoadOptions = {}): Promise<string> {
  const { fetchImpl = fetch, signal, retryMs = NOT_READY_RETRY_MS, sleep = pause } = options
  for (let attempt = 0; ; attempt++) {
    const response = await fetchImpl(summaryUrl(id), { signal })
    if (response.ok) return response.text()
    if (response.status !== 409 || attempt >= retryMs.length) throw new Error(await failure(response))
    await sleep(retryMs[attempt] ?? 0, signal)
  }
}

export type SummaryLineKind = 'title' | 'heading' | 'subheading' | 'item' | 'text' | 'blank'

export interface SummaryLine {
  kind: SummaryLineKind
  text: string
}

/** The template's lines with what each is: the first the title, an unindented one a heading (a
 * recording, a signal, the conventions), an indented one ending in a colon a subheading (Proved,
 * Not proved, Still unknown), a dash item an item. The text is kept verbatim, indent included. */
export function summaryLines(text: string): SummaryLine[] {
  const lines = text.replace(/\n+$/, '').split('\n')
  return lines.map((line, i) => {
    if (line.trim() === '') return { kind: 'blank', text: '' }
    if (i === 0) return { kind: 'title', text: line }
    if (!line.startsWith(' ')) return { kind: 'heading', text: line }
    if (line.trimStart().startsWith('- ')) return { kind: 'item', text: line }
    if (line.trimEnd().endsWith(':')) return { kind: 'subheading', text: line }
    return { kind: 'text', text: line }
  })
}
