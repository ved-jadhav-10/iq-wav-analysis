import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const drive = vi.fn()
const config = vi.fn()

vi.mock('driver.js', () => ({
  driver: (c: unknown) => {
    config(c)
    return { drive }
  },
}))
vi.mock('driver.js/dist/driver.css', () => ({}))

import { startTour, TOUR_ANCHORS, TOUR_STEPS } from './tour'

interface Config {
  steps: { element: string; popover: { title: string; description: string } }[]
  onDestroyed: () => void
}

function stubDom(present: readonly string[]) {
  vi.stubGlobal('document', {
    querySelector: (sel: string) => {
      const m = /data-tour="([^"]+)"/.exec(sel)
      return m && present.includes(m[1]) ? {} : null
    },
  })
  vi.stubGlobal('window', { matchMedia: () => ({ matches: false }) })
}

describe('tour', () => {
  beforeEach(() => {
    drive.mockClear()
    config.mockClear()
  })
  afterEach(() => vi.unstubAllGlobals())

  it('gives every step a unique anchor, a title and a description', () => {
    expect(new Set(TOUR_ANCHORS).size).toBe(TOUR_ANCHORS.length)
    for (const s of TOUR_STEPS) {
      expect(s.anchor).toMatch(/^[a-z-]+$/)
      expect(s.title.trim()).not.toBe('')
      expect(s.description.trim()).not.toBe('')
    }
  })

  it('skips steps whose element is not in the DOM', () => {
    stubDom(['open', 'waterfall', 'export'])
    startTour({ onDone: () => {} })
    const { steps } = config.mock.calls[0][0] as Config
    expect(steps.map((s) => s.element)).toEqual([
      '[data-tour="open"]',
      '[data-tour="waterfall"]',
      '[data-tour="export"]',
    ])
    for (const s of steps) {
      expect(s.popover.title).not.toBe('')
      expect(s.popover.description).not.toBe('')
    }
    expect(drive).toHaveBeenCalledOnce()
  })

  it('uses every step when all anchors are present, and reports done on destroy', () => {
    stubDom(TOUR_ANCHORS)
    const onDone = vi.fn()
    startTour({ onDone })
    const c = config.mock.calls[0][0] as Config
    expect(c.steps).toHaveLength(TOUR_ANCHORS.length)
    c.onDestroyed()
    expect(onDone).toHaveBeenCalledOnce()
  })

  it('finishes straight away when nothing is on screen', () => {
    stubDom([])
    const onDone = vi.fn()
    startTour({ onDone })
    expect(drive).not.toHaveBeenCalled()
    expect(onDone).toHaveBeenCalledOnce()
  })
})
