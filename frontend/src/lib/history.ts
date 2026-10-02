/**
 * What the History section shows for a kept analysis (`HistoryEntry`): when it finished, its
 * results hash, and where each download comes from. The downloads are the same formats the top bar
 * offers for a live recording, minus SigMF (which needs the recording's own files).
 */
import type { ResultFormat } from './exports'

/** The first digits of the results SHA-256 a row shows; the full value is in its title. */
export const SHA_SHOWN = 12

export function shortSha(sha256: string): string {
  return sha256.slice(0, SHA_SHOWN)
}

/** `createdUtc` as the analyst's local time, with the UTC value kept for a title. A stamp the
 * browser cannot parse is shown as the server sent it rather than as "Invalid Date". */
export function formatFinished(createdUtc: string): { local: string; utc: string } {
  const when = new Date(createdUtc)
  const local = Number.isNaN(when.getTime())
    ? createdUtc
    : when.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' })
  return { local, utc: createdUtc }
}

export function historyResultsUrl(id: string, format: ResultFormat): string {
  return `/api/v1/history/${encodeURIComponent(id)}/results?format=${format}`
}
