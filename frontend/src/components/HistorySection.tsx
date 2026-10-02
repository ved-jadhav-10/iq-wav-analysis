import { useCallback, useEffect, useState } from 'react'
import { Copy, RefreshCw, Trash2 } from 'lucide-react'
import { deleteHistory, fetchHistory, type HistoryEntry } from '@/lib/api'
import { resultLinks } from '@/lib/exports'
import { formatFinished, historyResultsUrl, shortSha } from '@/lib/history'
import { EvidenceBadge } from './EvidenceBadge'

export const CONFIRM_TEXT = 'Delete this analysis and everything derived from it?'

/** What makes an entry; the empty list says it so nobody has to guess how to fill it. */
export const EMPTY_TEXT =
  'Nothing kept yet. An analysis that finishes is kept in the workspace and listed here, and it survives a restart of the server.'

const LINKS = resultLinks('none')

interface ViewProps {
  entries: HistoryEntry[] | null
  /** Why the list could not be fetched, in the server's words. */
  loadError: string | null
  refreshing: boolean
  /** The entry whose inline delete confirmation is open. */
  confirming: string | null
  /** The entry being deleted right now. */
  deleting: string | null
  /** The server's text for a delete that failed, by entry. */
  rowErrors: Readonly<Record<string, string>>
  /** The entry whose hash was just copied (`ok` false: the browser refused). */
  copied: { id: string; ok: boolean } | null
  onRefresh: () => void
  onAskDelete: (id: string) => void
  onCancel: () => void
  onDelete: (id: string) => void
  onCopy: (entry: HistoryEntry) => void
}

const btn =
  'whitespace-nowrap rounded-md border border-border-strong px-1.5 py-0.5 text-2xs font-medium uppercase hover:bg-surface-2 hover:text-foreground'

function Row({ entry, view }: { entry: HistoryEntry; view: ViewProps }) {
  const { local, utc } = formatFinished(entry.createdUtc)
  const asking = view.confirming === entry.id
  const busy = view.deleting === entry.id
  const error = view.rowErrors[entry.id]
  const copied = view.copied?.id === entry.id ? view.copied : null
  return (
    <>
      <tr className="border-b align-middle hover:bg-surface-2/40">
        <td className="num max-w-[22rem] truncate px-3 py-1.5" title={entry.name}>
          {entry.name}
        </td>
        <td className="px-3 py-1.5 whitespace-nowrap">{entry.container}</td>
        <td className="num px-3 py-1.5 whitespace-nowrap" title={`${utc} (UTC)`}>
          <time dateTime={utc}>{local}</time>
        </td>
        <td className="num px-3 py-1.5 text-right">{entry.signals}</td>
        <td className="px-3 py-1.5 whitespace-nowrap">
          <span className="inline-flex items-center gap-1.5">
            <span className="num">{entry.verified}</span>
            {entry.verified > 0 ? (
              <EvidenceBadge level="VERIFIED" />
            ) : (
              <span className="text-2xs text-muted-foreground uppercase">none verified</span>
            )}
          </span>
        </td>
        <td className="px-3 py-1.5 whitespace-nowrap">
          <span className="inline-flex items-center gap-1">
            <code className="num" title={entry.resultsSha256}>
              {shortSha(entry.resultsSha256)}
            </code>
            <button
              type="button"
              onClick={() => view.onCopy(entry)}
              aria-label={`Copy the full results SHA-256 of ${entry.name}`}
              title={`Copy ${entry.resultsSha256}`}
              className="flex items-center gap-1 rounded-md px-1 py-0.5 text-2xs text-muted-foreground hover:bg-surface-2 hover:text-foreground"
            >
              <Copy className="size-3" aria-hidden />
              {copied ? (copied.ok ? 'Copied' : 'Not copied') : null}
            </button>
          </span>
        </td>
        <td className="px-3 py-1.5">
          <span className="flex items-center gap-1 text-muted-foreground">
            {LINKS.map((f) => (
              <a key={f.format} href={historyResultsUrl(entry.id, f.format)} download title={f.hint} className={btn}>
                {f.label}
              </a>
            ))}
            <button
              type="button"
              onClick={() => view.onAskDelete(entry.id)}
              disabled={asking || busy}
              aria-label={`Delete the analysis of ${entry.name}`}
              className={`ml-1 flex items-center gap-1 enabled:hover:border-destructive enabled:hover:text-destructive disabled:opacity-40 ${btn}`}
            >
              <Trash2 className="size-3" aria-hidden />
              Delete
            </button>
          </span>
        </td>
      </tr>
      {(asking || error) && (
        <tr className="border-b bg-surface-2/60">
          <td colSpan={7} className="px-3 py-1.5">
            <div
              role={asking ? 'group' : undefined}
              aria-label={asking ? `Confirm deleting ${entry.name}` : undefined}
              onKeyDown={(e) => {
                if (asking && e.key === 'Escape') view.onCancel()
              }}
              className="flex flex-wrap items-center gap-2 text-xs"
            >
              {asking && (
                <>
                  <span className="font-medium">{CONFIRM_TEXT}</span>
                  <button
                    type="button"
                    onClick={() => view.onDelete(entry.id)}
                    disabled={busy}
                    className={`border-destructive text-destructive disabled:opacity-40 ${btn}`}
                  >
                    {busy ? 'Deleting…' : 'Delete'}
                  </button>
                  <button type="button" onClick={view.onCancel} disabled={busy} autoFocus className={btn}>
                    Cancel
                  </button>
                </>
              )}
              {error && (
                <span role="alert" className="text-destructive">
                  Not deleted: {error}
                </span>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

const COLUMNS = ['Name', 'Container', 'Finished', 'Signals', 'Verified', 'Results SHA-256', 'Downloads']

/** The kept analyses as a table (presentation only: `HistorySection` owns the state). */
export function HistoryView(view: ViewProps) {
  const { entries } = view
  return (
    <main aria-label="History" className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex h-8 shrink-0 items-center gap-2 border-b bg-surface px-3">
        <h2 className="eyebrow">History</h2>
        {entries && (
          <span className="num text-2xs text-subtle-foreground">
            {entries.length} kept {entries.length === 1 ? 'analysis' : 'analyses'}
          </span>
        )}
        <button
          type="button"
          onClick={view.onRefresh}
          disabled={view.refreshing}
          title="Fetch the list from the server again"
          className="ml-auto flex items-center gap-1 rounded-md px-1.5 py-0.5 text-2xs font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground disabled:opacity-40"
        >
          <RefreshCw className={`size-3 ${view.refreshing ? 'animate-spin' : ''}`} aria-hidden />
          Refresh
        </button>
      </div>
      {view.loadError && (
        <p role="alert" className="shrink-0 border-b px-3 py-2 text-xs text-destructive">
          Could not load the history: {view.loadError}
        </p>
      )}
      {entries === null ? (
        !view.loadError && (
          <p role="status" className="px-3 py-4 text-xs text-muted-foreground italic">
            Loading the kept analyses…
          </p>
        )
      ) : entries.length === 0 ? (
        <p className="max-w-2xl px-3 py-4 text-xs text-muted-foreground italic">
          {EMPTY_TEXT}
        </p>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full min-w-max border-collapse text-xs">
            <thead className="sticky top-0 z-10 bg-surface">
              <tr className="border-b text-left">
                {COLUMNS.map((h) => (
                  <th key={h} scope="col" className={`eyebrow px-3 py-1.5 ${h === 'Signals' ? 'text-right' : ''}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <Row key={e.id} entry={e} view={view} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}

function without(errors: Record<string, string>, id: string): Record<string, string> {
  return Object.fromEntries(Object.entries(errors).filter(([key]) => key !== id))
}

/** The History section: the server's kept analyses, fetched when the section opens and again
 * whenever `refreshKey` changes (an analysis has finished). Deleting asks first, in the row. */
export function HistorySection({ refreshKey }: { refreshKey: number }) {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({})
  const [copied, setCopied] = useState<{ id: string; ok: boolean } | null>(null)

  const load = useCallback(async () => {
    setRefreshing(true)
    try {
      setEntries(await fetchHistory())
      setLoadError(null)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e))
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    // Fetching is the effect: the state it sets is the server's answer arriving.
    void load()
  }, [load, refreshKey])

  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(null), 2500)
    return () => clearTimeout(timer)
  }, [copied])

  async function remove(id: string) {
    setDeleting(id)
    setRowErrors((prev) => without(prev, id))
    try {
      await deleteHistory(id)
      setEntries((prev) => prev && prev.filter((e) => e.id !== id))
      setConfirming(null)
    } catch (e) {
      setRowErrors((prev) => ({ ...prev, [id]: e instanceof Error ? e.message : String(e) }))
    } finally {
      setDeleting(null)
    }
  }

  async function copy(entry: HistoryEntry) {
    try {
      await navigator.clipboard.writeText(entry.resultsSha256)
      setCopied({ id: entry.id, ok: true })
    } catch {
      setCopied({ id: entry.id, ok: false })
    }
  }

  return (
    <HistoryView
      entries={entries}
      loadError={loadError}
      refreshing={refreshing}
      confirming={confirming}
      deleting={deleting}
      rowErrors={rowErrors}
      copied={copied}
      onRefresh={() => void load()}
      onAskDelete={(id) => {
        setConfirming(id)
        setRowErrors((prev) => without(prev, id))
      }}
      onCancel={() => setConfirming(null)}
      onDelete={(id) => void remove(id)}
      onCopy={(entry) => void copy(entry)}
    />
  )
}
