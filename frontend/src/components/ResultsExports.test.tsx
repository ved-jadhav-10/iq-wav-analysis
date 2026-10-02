import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ResultsLinks } from './ResultsExports'

const html = (sigmf: 'annotate' | 'save' | 'none', saving = false) =>
  renderToStaticMarkup(
    createElement(ResultsLinks, {
      resultsUrl: (format) => `/api/v1/recordings/r1/results?format=${format}`,
      sigmf,
      stacked: false,
      saving,
      onSave: () => undefined,
    }),
  )

describe('ResultsLinks', () => {
  it('links the run record for every recording, to the run format', () => {
    for (const sigmf of ['none', 'annotate', 'save'] as const) {
      expect(html(sigmf)).toContain('href="/api/v1/recordings/r1/results?format=run"')
    }
  })

  it('shows the SigMF link only where the server can describe the recording', () => {
    expect(html('none')).not.toContain('format=sigmf')
    expect(html('annotate')).toContain('format=sigmf')
    expect(html('save')).toContain('format=sigmf')
  })

  it('shows the Save as SigMF button for a raw file only, disabled while it saves', () => {
    expect(html('save')).toContain('Save as SigMF')
    expect(html('save')).not.toContain('disabled=""')
    expect(html('save', true)).toContain('Saving…')
    expect(html('save', true)).toContain('disabled=""')
    expect(html('annotate')).not.toContain('Save as SigMF')
    expect(html('none')).not.toContain('Save as SigMF')
  })
})
