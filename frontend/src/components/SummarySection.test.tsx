import { createElement, type ComponentProps } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { SummarySection, SummaryView, SummaryWaiting } from './SummarySection'

const NONE = () => undefined

function render(over: Partial<ComponentProps<typeof SummaryView>> = {}): string {
  return renderToStaticMarkup(
    createElement(SummaryView, {
      state: { status: 'ready', text: 'Sanket 0.1.0 results summary\n\nSignal 1 (s1), VERIFIED: x\n  Proved:\n    - a: 1 (proved on this recording)\n' },
      onRetry: NONE,
      ...over,
    }),
  )
}

describe('SummaryView', () => {
  it('shows the finished summary text, keeping its lines and indents', () => {
    const html = render()
    expect(html).toContain('aria-label="Summary"')
    expect(html).toContain('Signal 1 (s1), VERIFIED: x')
    expect(html).toContain('>  Proved:<')
    expect(html).toContain('>    - a: 1 (proved on this recording)<')
    expect(html).toContain('whitespace-pre-wrap')
  })

  it('reads in the tabular monospace face and scrolls inside its own focusable panel', () => {
    const html = render()
    expect(html).toMatch(/role="region"[^>]*aria-label="Summary text"[^>]*tabindex="0"/)
    expect(html).toContain('min-h-0 flex-1 overflow-y-auto')
    expect(html).toContain('>Summary</h2>')
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

describe('SummarySection', () => {
  it('starts loading, until the text arrives', () => {
    const html = renderToStaticMarkup(createElement(SummarySection, { recordingId: 'rec1' }))
    expect(html).toContain('Loading the summary')
  })
})

describe('SummaryWaiting', () => {
  it('says the summary comes when the analysis finishes, and how far it has got', () => {
    const html = renderToStaticMarkup(createElement(SummaryWaiting, { done: 1, total: 3 }))
    expect(html).toContain('written once the analysis finishes')
    expect(html).toContain('signal 2 of 3')
  })
})
