import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Detection } from '@/lib/analysis'
import type { Parameter } from '@/lib/evidence'
import { DecodedMessages } from './DecodedMessages'

function detection(parameters: Parameter[]): Detection {
  return {
    id: 1,
    boxes: [],
    label: 'FSK',
    kind: 'fsk',
    level: 'VERIFIED',
    headline: '',
    stages: [{ id: 'match', name: 'Match', status: 'done', summary: '', level: 'VERIFIED', parameters }],
    search: null,
    noSearchReason: null,
    frames: [],
    noFramesReason: null,
    constellation: [],
  }
}

const base = { confidence: null, method: '', alternatives: [], warnings: [] }
const system: Parameter = { ...base, id: 'system', name: 'Known system', value: 'POCSAG', level: 'VERIFIED', evidence: [] }
const pages: Parameter = {
  ...base,
  id: 'pages',
  name: 'Pages',
  value: '1 page',
  level: 'HYPOTHESIS',
  evidence: ['RIC 0001234 function 3: "HELLO"'],
  convention: 'Function bits 3 read as alphanumeric 7-bit ASCII',
}

function render(d: Detection): string {
  return renderToStaticMarkup(createElement(DecodedMessages, { detection: d }))
}

describe('DecodedMessages', () => {
  it('shows a titled card with the system, the text, the data level and the caption', () => {
    const html = render(detection([system, pages]))
    expect(html).toContain('Decoded message')
    expect(html).toContain('POCSAG')
    expect(html).toContain('HELLO')
    expect(html).toContain('RIC 0001234 · function 3')
    expect(html).toContain('Hypothesis')
    expect(html).not.toContain('Verified')
    expect(html).toContain('rests on a convention and is never used as evidence')
    expect(html).toContain('Function bits 3 read as alphanumeric')
    expect(html).toContain('Copy')
  })

  it('renders nothing when the system matched without any text parameter, or without a match stage', () => {
    expect(render(detection([system]))).toBe('')
    expect(render({ ...detection([system, pages]), stages: [] })).toBe('')
  })

  it('says so when a page carries no text', () => {
    const none = { ...pages, evidence: ['RIC 0000010 function 0: not shown (numeric, or a codeword failed)'] }
    const html = render(detection([system, none]))
    expect(html).toContain('no text: not shown')
    expect(html).toContain('No text was decoded')
  })
})
