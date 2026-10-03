import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const drive = vi.fn()
const moveTo = vi.fn()
const destroy = vi.fn()
const config = vi.fn()
let activeIndex = 0

vi.mock('driver.js', () => ({
  driver: (c: unknown) => {
    config(c)
    return { drive, moveTo, destroy, getActiveIndex: () => activeIndex }
  },
}))
vi.mock('driver.js/dist/driver.css', () => ({}))

import { startTour, TOUR_ANCHORS, TOUR_STEPS } from './tour'

interface Config {
  steps: { element: string; popover: { title: string; description: string } }[]
  onDestroyed: () => void
  onDestroyStarted: () => void
  onNextClick: () => void
  onPrevClick: () => void
}

/** `present` is what is in the DOM right now; `appear` anchors show up once a section is shown. */
function stubDom(present: string[], appear: Record<string, string[]> = {}) {
  vi.stubGlobal('document', {
    querySelector: (sel: string) => {
      const m = /data-tour="([^"]+)"/.exec(sel)
      return m && present.includes(m[1]) ? {} : null
    },
  })
  vi.stubGlobal('window', { matchMedia: () => ({ matches: false }) })
  vi.stubGlobal('requestAnimationFrame', (cb: () => void) => cb())
  return (section: string) => present.push(...(appear[section] ?? []))
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0))

describe('tour', () => {
  beforeEach(() => {
    for (const m of [drive, moveTo, destroy, config]) m.mockClear()
    activeIndex = 0
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

  it('without a way to switch sections, tours only what is on screen', () => {
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

  it('with a recording open, includes the steps of the other sections', () => {
    stubDom(['open', 'section-nav', 'detections', 'waterfall', 'constellation', 'eye', 'export', 'assumptions'])
    startTour({ onDone: () => {}, section: 'dashboard', showSection: () => {} })
    const { steps } = config.mock.calls[0][0] as Config
    expect(steps).toHaveLength(TOUR_ANCHORS.length)
  })

  it('drops a step of the current section whose element is not there', () => {
    stubDom(['open', 'section-nav', 'waterfall'])
    startTour({ onDone: () => {}, section: 'dashboard', showSection: () => {} })
    const anchors = (config.mock.calls[0][0] as Config).steps.map((s) => s.element)
    expect(anchors).not.toContain('[data-tour="eye"]')
    expect(anchors).toContain('[data-tour="evidence"]')
  })

  it('switches section before showing a step that lives in another one', async () => {
    const show = stubDom(['open', 'section-nav', 'detections', 'waterfall', 'constellation', 'eye'], {
      evidence: ['evidence'],
    })
    const showSection = vi.fn((s: string) => show(s))
    startTour({ onDone: () => {}, section: 'dashboard', showSection })
    const c = config.mock.calls[0][0] as Config
    activeIndex = c.steps.findIndex((s) => s.element === '[data-tour="eye"]')
    c.onNextClick()
    await tick()
    expect(showSection).toHaveBeenCalledWith('evidence')
    expect(moveTo).toHaveBeenCalledWith(activeIndex + 1)
  })

  it('skips a step whose element never appears, and ends when none is left', async () => {
    stubDom(['open', 'section-nav', 'export', 'assumptions'])
    startTour({ onDone: () => {}, section: 'dashboard', showSection: () => {} })
    const c = config.mock.calls[0][0] as Config
    activeIndex = c.steps.findIndex((s) => s.element === '[data-tour="section-nav"]')
    c.onNextClick()
    await tick()
    expect(moveTo).toHaveBeenCalledWith(c.steps.findIndex((s) => s.element === '[data-tour="export"]'))
    activeIndex = c.steps.length - 1
    c.onNextClick()
    await tick()
    expect(destroy).toHaveBeenCalledOnce()
  })

  it('returns to the section the analyst started on, then reports done', async () => {
    const show = stubDom(['open', 'section-nav', 'export'], { summary: ['summary'] })
    const showSection = vi.fn((s: string) => show(s))
    const onDone = vi.fn()
    startTour({ onDone, section: 'dashboard', showSection })
    const c = config.mock.calls[0][0] as Config
    activeIndex = c.steps.findIndex((s) => s.element === '[data-tour="hypotheses"]') - 1
    c.onNextClick()
    await tick()
    c.onDestroyed()
    expect(showSection).toHaveBeenLastCalledWith('dashboard')
    expect(onDone).toHaveBeenCalledOnce()
  })

  it('ends once however it is closed, even if driver.js never reports it destroyed', () => {
    stubDom(['open', 'section-nav', 'export'])
    const onDone = vi.fn()
    startTour({ onDone, section: 'dashboard', showSection: () => {} })
    const c = config.mock.calls[0][0] as Config
    c.onDestroyStarted() // Esc, the close button or a click on the overlay
    c.onDestroyed()
    expect(destroy).toHaveBeenCalledOnce()
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
