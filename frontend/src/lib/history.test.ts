import { describe, expect, it } from 'vitest'
import { formatFinished, historyResultsUrl, shortSha } from './history'

describe('history helpers', () => {
  it('shows the first 12 hex digits of the hash', () => {
    expect(shortSha('0123456789abcdef0123456789abcdef')).toBe('0123456789ab')
    expect(shortSha('abc')).toBe('abc')
  })

  it('keeps the UTC stamp for the title and formats the local time from it', () => {
    const { local, utc } = formatFinished('2026-03-04T05:06:07Z')
    expect(utc).toBe('2026-03-04T05:06:07Z')
    expect(local).toContain('2026')
    expect(local).not.toContain('Invalid')
  })

  it('shows an unparseable stamp as the server sent it', () => {
    expect(formatFinished('yesterday').local).toBe('yesterday')
  })

  it('points each format at the kept analysis, never at a recording', () => {
    expect(historyResultsUrl('ab12', 'json')).toBe('/api/v1/history/ab12/results?format=json')
    expect(historyResultsUrl('ab12', 'run')).toBe('/api/v1/history/ab12/results?format=run')
  })
})
