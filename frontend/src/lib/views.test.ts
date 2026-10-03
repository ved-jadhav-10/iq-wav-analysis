import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_VIEW, isSectionId, isViewId, loadStoredView, stepView, VIEWS, viewByDigit, type ViewId } from './views'

// Sections that used to exist must not come back as ids: a stored one falls back to the default.
const RETIRED_VIEWS = ['survey', 'waterfall', 'signal']

const IDS = VIEWS.map((v) => v.id)

describe('views', () => {
  it('exposes a unique id and a digit per section', () => {
    expect(new Set(IDS).size).toBe(IDS.length)
    expect(new Set(VIEWS.map((v) => v.digit)).size).toBe(VIEWS.length)
  })

  it('defaults to the Dashboard', () => {
    expect(DEFAULT_VIEW).toBe('dashboard')
  })

  it('has no section for the retired Survey, Waterfall or full-screen deep dive', () => {
    for (const id of RETIRED_VIEWS) expect(isViewId(id)).toBe(false)
  })

  it('recognises only real ids', () => {
    for (const id of IDS) expect(isViewId(id)).toBe(true)
    expect(isViewId('nope')).toBe(false)
    expect(isViewId('')).toBe(false)
  })

  it('steps forward and backward, wrapping at both ends', () => {
    const first = IDS[0]
    const last = IDS[IDS.length - 1]
    expect(stepView(last, 1)).toBe(first)
    expect(stepView(first, -1)).toBe(last)
    expect(stepView(first, 1)).toBe(IDS[1])
  })

  it('survives a full cycle in both directions', () => {
    const start = 'dashboard' satisfies ViewId
    let v: ViewId = start
    for (let i = 0; i < IDS.length; i++) v = stepView(v, 1)
    expect(v).toBe(start)
    let w: ViewId = start
    for (let i = 0; i < IDS.length; i++) w = stepView(w, -1)
    expect(w).toBe(start)
  })

  it('falls back to the first section rather than throwing on an unknown id', () => {
    // stepView takes a ViewId, so this is only reachable from a corrupted stored value: it must
    // degrade, not index -1 and read undefined.
    expect(stepView('corrupt' as ViewId, 1)).toBe(IDS[1])
  })

  it('maps each digit to its section and ignores anything else', () => {
    for (const v of VIEWS) expect(viewByDigit(v.digit)).toBe(v.id)
    expect(viewByDigit('9')).toBeUndefined()
    expect(viewByDigit('')).toBeUndefined()
  })

  it('never treats the Assumptions modal as a section to land on or to remember', () => {
    expect(isViewId('assumptions')).toBe(true)
    expect(isSectionId('assumptions')).toBe(false)
    expect(isSectionId('dashboard')).toBe(true)
    expect(isSectionId('survey')).toBe(false)
    // Alt+5 used to store it, which left the workspace blank on every reload.
    const store: Record<string, string> = { 'sanket.view.v1': 'assumptions' }
    vi.stubGlobal('window', { localStorage: { getItem: (k: string) => store[k] ?? null } })
    expect(loadStoredView()).toBe(DEFAULT_VIEW)
    vi.unstubAllGlobals()
  })
})
