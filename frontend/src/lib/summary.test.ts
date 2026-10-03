import { describe, expect, it, vi } from 'vitest'
import {
  NOT_READY_RETRY_MS,
  loadSummary,
  summaryLines,
  summaryTarget,
  summaryUrl,
} from './summary'

const TEXT = [
  'Sanket 0.1.0 results summary',
  '',
  'Recording: 1 file.',
  'Taken as given about the recording:',
  '  - sample rate: 1e+06 S/s (read from the file or entered)',
  '',
  'Signal 1 (s1), VERIFIED: GFSK 9600 baud',
  '  Proved:',
  '    - frame sync: 1 (proved on this recording); crc',
  '  Frames in the table: 3, 3 pass their CRC.',
  '',
  'No value rests on a convention.',
  '',
].join('\n')

function reply(status: number, body: string | object, ok = status >= 200 && status < 300): Response {
  const text = typeof body === 'string' ? body : JSON.stringify(body)
  return {
    ok,
    status,
    statusText: ok ? 'OK' : 'Error',
    text: () => Promise.resolve(text),
    json: () => new Promise<unknown>((resolve) => resolve(JSON.parse(text))),
  } as Response
}

const noSleep = () => Promise.resolve()

describe('summaryTarget', () => {
  const info = (state: 'running' | 'done' | 'cancelled') => ({
    id: 'rec1',
    analysis: { state, done: 1, total: 1 },
  })

  it('is the recording id only once its analysis has finished', () => {
    expect(summaryTarget(info('done'))).toBe('rec1')
    expect(summaryTarget(info('running'))).toBeNull()
    expect(summaryTarget(info('cancelled'))).toBeNull()
  })

  it('is null for the synthetic in-browser capture, which has no recording', () => {
    expect(summaryTarget(null)).toBeNull()
  })
})

describe('loadSummary', () => {
  it('fetches the text rendering of the finished recording', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(reply(200, TEXT))
    await expect(loadSummary('rec1', { fetchImpl, sleep: noSleep })).resolves.toBe(TEXT)
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    expect(fetchImpl.mock.calls[0]?.[0]).toBe('/api/v1/recordings/rec1/results?format=txt')
    expect(summaryUrl('a b')).toBe('/api/v1/recordings/a%20b/results?format=txt')
  })

  it('waits out a 409 and then returns the text', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(reply(409, { detail: 'the analysis has not finished' }))
      .mockResolvedValueOnce(reply(409, { detail: 'the analysis has not finished' }))
      .mockResolvedValueOnce(reply(200, TEXT))
    const sleep = vi.fn().mockResolvedValue(undefined)
    await expect(loadSummary('rec1', { fetchImpl, sleep })).resolves.toBe(TEXT)
    expect(fetchImpl).toHaveBeenCalledTimes(3)
    expect(sleep.mock.calls.map((c) => c[0])).toEqual([NOT_READY_RETRY_MS[0], NOT_READY_RETRY_MS[1]])
  })

  it('gives up after the last retry with the server text', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(reply(409, { detail: 'the analysis has not finished' }))
    await expect(loadSummary('rec1', { fetchImpl, sleep: noSleep, retryMs: [1, 1] })).rejects.toThrow(
      'the analysis has not finished',
    )
    expect(fetchImpl).toHaveBeenCalledTimes(3)
  })

  it('does not retry any other failure, and says what the server said', async () => {
    const missing = vi.fn().mockResolvedValue(reply(404, { detail: 'no such recording' }))
    await expect(loadSummary('x', { fetchImpl: missing, sleep: noSleep })).rejects.toThrow('no such recording')
    expect(missing).toHaveBeenCalledTimes(1)
    const opaque = vi.fn().mockResolvedValue(reply(500, 'oops'))
    await expect(loadSummary('x', { fetchImpl: opaque, sleep: noSleep })).rejects.toThrow('request failed: 500')
    const down = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(loadSummary('x', { fetchImpl: down, sleep: noSleep })).rejects.toThrow('Failed to fetch')
  })
})

describe('summaryLines', () => {
  const lines = summaryLines(TEXT)
  const kind = (starts: string) => lines.find((l) => l.text.trimStart().startsWith(starts))?.kind

  it('keeps the template line for line, verbatim, without the trailing newline', () => {
    expect(lines.map((l) => l.text).join('\n')).toBe(TEXT.replace(/\n+$/, ''))
  })

  it('tells the title, headings, subheadings and items apart', () => {
    expect(lines[0]?.kind).toBe('title')
    expect(kind('Recording:')).toBe('heading')
    expect(kind('Signal 1')).toBe('heading')
    expect(kind('No value rests')).toBe('heading')
    expect(kind('Proved:')).toBe('subheading')
    expect(kind('- sample rate')).toBe('item')
    expect(kind('- frame sync')).toBe('item')
    expect(kind('Frames in the table')).toBe('text')
    expect(lines.filter((l) => l.kind === 'blank').length).toBe(3)
  })
})
