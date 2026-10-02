import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ResultsExports } from './ResultsExports'

const html = (sigmf: 'annotate' | 'save' | 'none') =>
  renderToStaticMarkup(
    createElement(ResultsExports, {
      resultsUrl: (format) => `/api/v1/recordings/r1/results?format=${format}`,
      sigmf,
      onSaveSigmf: () => Promise.resolve('x'),
    }),
  )

describe('ResultsExports', () => {
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

  it('shows the Save as SigMF button for a raw file only', () => {
    expect(html('save')).toContain('Save as SigMF')
    expect(html('annotate')).not.toContain('Save as SigMF')
    expect(html('none')).not.toContain('Save as SigMF')
  })

  it('shows no message before anything is saved', () => {
    expect(html('save')).not.toContain('role="alert"')
    expect(html('save')).not.toContain('role="status"')
  })
})
