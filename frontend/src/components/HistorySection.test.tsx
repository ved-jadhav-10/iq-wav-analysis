import { createElement, type ComponentProps } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { HistoryEntry } from '@/lib/api'
import { CONFIRM_TEXT, EMPTY_TEXT, HistoryView } from './HistorySection'

const SHA_A = '0123456789abcdef'.repeat(4)
const SHA_B = 'fedcba9876543210'.repeat(4)

const A: HistoryEntry = {
  id: 'aaa111',
  createdUtc: '2026-03-04T05:06:07Z',
  name: 'pager.sigmf-meta',
  container: 'SigMF',
  signals: 3,
  verified: 2,
  resultsSha256: SHA_A,
}
const B: HistoryEntry = {
  id: 'bbb222',
  createdUtc: '2026-03-03T01:02:03Z',
  name: 'noise.bin',
  container: 'raw',
  signals: 1,
  verified: 0,
  resultsSha256: SHA_B,
}

const NONE = () => undefined

function render(over: Partial<ComponentProps<typeof HistoryView>> = {}): string {
  return renderToStaticMarkup(
    createElement(HistoryView, {
      entries: [A, B],
      loadError: null,
      refreshing: false,
      confirming: null,
      deleting: null,
      rowErrors: {},
      copied: null,
      onRefresh: NONE,
      onAskDelete: NONE,
      onCancel: NONE,
      onDelete: NONE,
      onCopy: NONE,
      ...over,
    }),
  )
}

describe('HistoryView', () => {
  it('lists each kept analysis: name, container, finished with its UTC title, signals', () => {
    const html = render()
    for (const text of ['pager.sigmf-meta', 'SigMF', 'noise.bin', 'raw']) expect(html).toContain(text)
    expect(html).toContain('title="2026-03-04T05:06:07Z (UTC)"')
    expect(html).toContain('dateTime="2026-03-04T05:06:07Z"')
    expect(html).toContain('2 kept analyses')
    expect(html.indexOf('pager.sigmf-meta')).toBeLessThan(html.indexOf('noise.bin')) // newest first, as sent
  })

  it('shows the VERIFIED count with the evidence badge (glyph and word), and says so when there is none', () => {
    const html = render({ entries: [A] })
    expect(html).toContain('>2</span>')
    expect(html).toContain('ring-ev-verified') // the badge ...
    expect(html).toMatch(/ring-ev-verified[^>]*>(<svg[^>]*>.*?<\/svg>)Verified</) // ... with its glyph and word
    const none = render({ entries: [B] })
    expect(none).toContain('none verified')
    expect(none).not.toContain('ring-ev-verified')
  })

  it('shows 12 hex digits of the hash with the full value in a title and a copy button', () => {
    const html = render({ entries: [A] })
    expect(html).toContain(`>${SHA_A.slice(0, 12)}</code>`)
    expect(html).not.toContain(`>${SHA_A}<`)
    expect(html).toContain(`title="${SHA_A}"`)
    expect(html).toContain('aria-label="Copy the full results SHA-256 of pager.sigmf-meta"')
  })

  it('offers each download as a plain download link to the kept analysis', () => {
    const html = render({ entries: [A] })
    for (const format of ['json', 'csv', 'txt', 'pdf', 'run']) {
      expect(html).toContain(`href="/api/v1/history/aaa111/results?format=${format}"`)
    }
    for (const label of ['JSON', 'CSV', 'Summary', 'PDF', 'Run record']) expect(html).toContain(`>${label}</a>`)
    expect(html).not.toContain('format=sigmf')
    expect(html.match(/ download=""/g)).toHaveLength(5)
  })

  it('asks for confirmation in the row before anything is deleted', () => {
    expect(render()).not.toContain(CONFIRM_TEXT)
    const html = render({ confirming: 'bbb222' })
    expect(html).toContain(CONFIRM_TEXT)
    expect(html).toContain('aria-label="Confirm deleting noise.bin"')
    expect(html.match(new RegExp(CONFIRM_TEXT, 'g'))).toHaveLength(1) // only the row asked about
    expect(html).toContain('>Cancel</button>')
    // the confirmation row sits straight after the row it belongs to
    expect(html.indexOf(CONFIRM_TEXT)).toBeGreaterThan(html.indexOf('noise.bin'))
  })

  it('shows a delete in progress, and the server text when it failed', () => {
    expect(render({ confirming: 'aaa111', deleting: 'aaa111' })).toContain('Deleting…')
    const html = render({ confirming: 'aaa111', rowErrors: { aaa111: 'no such analysis' } })
    expect(html).toContain('role="alert"')
    expect(html).toContain('Not deleted: no such analysis')
  })

  it('says what makes an entry when the list is empty', () => {
    expect(render({ entries: [] })).toContain(EMPTY_TEXT)
  })

  it('reports a failed fetch and shows loading before the first answer', () => {
    expect(render({ entries: null, loadError: 'connection refused' })).toContain(
      'Could not load the history: connection refused',
    )
    expect(render({ entries: null })).toContain('Loading the kept analyses')
  })

  it('keeps the table inside its own scrolling panel', () => {
    const html = render()
    expect(html).toContain('overflow-auto')
    expect(html).toContain('min-h-0 flex-1')
  })
})
