import { createElement, type ComponentProps } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { SUMMARY_BODY_ID, SummaryStrip, SummaryView } from './SummaryStrip'

const NONE = () => undefined

function render(over: Partial<ComponentProps<typeof SummaryView>> = {}): string {
  return renderToStaticMarkup(
    createElement(SummaryView, {
      state: { status: 'ready', text: 'Sanket 0.1.0 results summary\n\nSignal 1 (s1), VERIFIED: x\n  Proved:\n    - a: 1 (proved on this recording)\n' },
      open: true,
      onToggle: NONE,
      onRetry: NONE,
      ...over,
    }),
  )
}

describe('SummaryView', () => {
  it('shows the finished summary text, keeping its lines and indents', () => {
    const html = render()
    expect(html).toContain('aria-label="Plain-language summary"')
    expect(html).toContain('Signal 1 (s1), VERIFIED: x')
    expect(html).toContain('>  Proved:<')
    expect(html).toContain('>    - a: 1 (proved on this recording)<')
    expect(html).toContain('whitespace-pre-wrap')
  })

  it('reads in the tabular monospace face and scrolls inside its own bounded, focusable panel', () => {
    const html = render()
    expect(html).toMatch(/role="region"[^>]*aria-label="Summary text"[^>]*tabindex="0"/)
    expect(html).toContain('num max-h-[min(22vh,160px)] overflow-y-auto')
    expect(html).toContain('shrink-0') // the strip itself never grows past what it holds
  })

  it('has a keyboard-reachable toggle that says whether it is open and what it controls', () => {
    const open = render()
    expect(open).toMatch(/<button[^>]*aria-expanded="true"[^>]*aria-controls="plain-language-summary"/)
    expect(open).toContain(`id="${SUMMARY_BODY_ID}"`)
    expect(open).not.toContain('hidden=""')
    const collapsed = render({ open: false })
    expect(collapsed).toContain('aria-expanded="false"')
    expect(collapsed).toContain(`id="${SUMMARY_BODY_ID}" hidden=""`)
    expect(collapsed).toContain('>Summary</h2>')
  })

  it('says it is loading, with no retry', () => {
    const html = render({ state: { status: 'loading' } })
    expect(html).toContain('Loading the summary')
    expect(html).toContain('role="status"')
    expect(html).not.toContain('Retry')
    expect(html).not.toContain('Summary text')
  })

  it('shows why it failed, in the server words, with a retry that does something', () => {
    const html = render({ state: { status: 'error', message: 'the analysis has not finished' } })
    expect(html).toContain('role="alert"')
    expect(html).toContain('Could not load the summary: the analysis has not finished')
    expect(html).toContain('Retry')
    expect(html).not.toContain('Summary text')
  })
})

describe('SummaryStrip', () => {
  it('starts loading, until the text arrives', () => {
    const html = renderToStaticMarkup(createElement(SummaryStrip, { recordingId: 'rec1' }))
    expect(html).toContain('Loading the summary')
    expect(html).toContain('aria-expanded=')
  })
})
