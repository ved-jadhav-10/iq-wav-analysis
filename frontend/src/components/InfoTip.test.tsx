import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { InfoTip, InfoTipBody } from './InfoTip'
import { GLOSSARY } from '@/lib/glossary'
import { placePopover } from '@/lib/popoverPlacement'

describe('InfoTip', () => {
  it('renders a small focusable button that names its term and is closed at first', () => {
    const html = renderToStaticMarkup(createElement(InfoTip, { term: 'crc' }))
    expect(html).toMatch(/^<button[^>]*type="button"/)
    expect(html).toContain(`aria-label="What is ${GLOSSARY.crc.term}?"`)
    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('size-3.5')
    expect(html).toContain('text-subtle-foreground')
    expect(html).toContain('inline-flex')
    expect(html).not.toContain('role="tooltip"')
    expect(html).not.toContain('tabindex="-1"')
  })

  it('renders nothing for a term it does not know', () => {
    expect(renderToStaticMarkup(createElement(InfoTip, { term: 'nonsense' }))).toBe('')
  })

  it('shows the term, the short definition and the long one when there is one', () => {
    const withLong = renderToStaticMarkup(createElement(InfoTipBody, { entry: GLOSSARY.crc, id: 'x' }))
    expect(withLong).toContain('font-semibold')
    expect(withLong).toContain(GLOSSARY.crc.term)
    expect(withLong).toContain(GLOSSARY.crc.short)
    expect(withLong).toContain(GLOSSARY.crc.long as string)
    const noLong = renderToStaticMarkup(createElement(InfoTipBody, { entry: GLOSSARY.snr, id: 'y' }))
    expect(noLong).toContain(GLOSSARY.snr.short)
    expect(noLong).not.toContain('text-muted-foreground')
  })
})

describe('placePopover', () => {
  const viewport = { width: 1000, height: 600 }
  const size = { width: 260, height: 80 }
  const anchor = (left: number, top: number) => ({ left, top, right: left + 14, bottom: top + 14 })

  it('opens below the anchor, centred on it', () => {
    const p = placePopover(anchor(400, 100), size, viewport)
    expect(p.placement).toBe('below')
    expect(p.top).toBe(100 + 14 + 6)
    expect(p.left).toBe(407 - 130)
  })

  it('flips above when there is no room below', () => {
    const p = placePopover(anchor(400, 560), size, viewport)
    expect(p.placement).toBe('above')
    expect(p.top).toBe(560 - 6 - 80)
  })

  it('is clamped inside the viewport on every side', () => {
    expect(placePopover(anchor(2, 100), size, viewport).left).toBe(8)
    expect(placePopover(anchor(990, 100), size, viewport).left).toBe(1000 - 8 - 260)
    const tiny = placePopover(anchor(400, 20), size, { width: 1000, height: 100 })
    expect(tiny.top).toBeGreaterThanOrEqual(8)
    expect(tiny.top + size.height).toBeLessThanOrEqual(100 - 8 + 1e-9)
  })
})
