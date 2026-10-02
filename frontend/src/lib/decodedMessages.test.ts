import { describe, expect, it } from 'vitest'
import type { Parameter, StageResult } from './evidence'
import { decodedMessages, decodedMessagesAsText, parseDecodedParameter } from './decodedMessages'

function param(over: Partial<Parameter> & Pick<Parameter, 'id'>): Parameter {
  return {
    name: over.id,
    value: null,
    level: 'HYPOTHESIS',
    confidence: null,
    method: '',
    evidence: [],
    alternatives: [],
    warnings: [],
    ...over,
  }
}

function matchStage(parameters: Parameter[]): StageResult {
  return { id: 'match', name: 'Match', status: 'done', summary: '', level: 'VERIFIED', parameters }
}

const SYSTEM = param({ id: 'system', name: 'Known system', value: 'POCSAG', level: 'VERIFIED' })
const POCSAG_CONVENTION =
  'Function bits 3 read as alphanumeric 7-bit ASCII (the standard leaves the function bits\' meaning to the operator); shown only from codewords that pass their check, and never used as evidence'

describe('decodedMessages', () => {
  it('parses POCSAG pages, keeping the engine level and convention', () => {
    const pages = param({
      id: 'pages',
      name: 'Pages',
      value: '3 pages',
      evidence: [
        'RIC 0001234 function 3: "HELLO WORLD"',
        'RIC 0004321 function 0: not shown (numeric, or a codeword failed)',
        'RIC 0000007 function 3: "SAY: "QUOTED""',
        '... and 17 more',
      ],
      convention: POCSAG_CONVENTION,
    })
    const [d] = decodedMessages([matchStage([SYSTEM, pages])])
    expect(d.kind).toBe('pages')
    expect(d.system).toBe('POCSAG')
    expect(d.title).toBe('Decoded message')
    expect(d.level).toBe('HYPOTHESIS')
    expect(d.value).toBe('3 pages')
    expect(d.convention).toBe(POCSAG_CONVENTION)
    expect(d.more).toBe(17)
    expect(d.hasText).toBe(true)
    expect(d.lines).toEqual([
      { label: 'RIC 0001234 · function 3', text: 'HELLO WORLD', note: null },
      { label: 'RIC 0004321 · function 0', text: null, note: 'not shown (numeric, or a codeword failed)' },
      { label: 'RIC 0000007 · function 3', text: 'SAY: "QUOTED"', note: null },
    ])
  })

  it('parses NAVTEX messages at the first colon', () => {
    const messages = param({
      id: 'messages',
      name: 'NAVTEX messages',
      value: '1 message (1 distinct)',
      evidence: ['XA01: GALE WARNING: SEA AREA 12 NNNN'],
    })
    const [d] = decodedMessages([matchStage([{ ...SYSTEM, value: 'NAVTEX' }, messages])])
    expect(d.kind).toBe('messages')
    expect(d.system).toBe('NAVTEX')
    expect(d.lines).toEqual([{ label: 'XA01', text: 'GALE WARNING: SEA AREA 12 NNNN', note: null }])
  })

  it('parses DSC calls and AIS messages, and keeps a CCSDS header as a header', () => {
    const calls = param({
      id: 'calls',
      evidence: ['Distress alert (format 112); first field 123456789; content symbols 1 2 3; EOS 127 (end); ECC matches'],
    })
    const ais = param({ id: 'ais_messages', evidence: ['type 1, MMSI 211234567'] })
    const tm = param({ id: 'tm_header', name: 'Transfer frame header', level: 'VERIFIED', evidence: ['spacecraft id 0x1A'] })
    const out = decodedMessages([matchStage([calls, ais, tm])])
    expect(out.map((d) => d.kind)).toEqual(['calls', 'ais', 'header'])
    expect(out[0].lines[0].label).toBe('Distress alert (format 112)')
    expect(out[0].lines[0].text).toContain('first field 123456789')
    expect(out[1].lines).toEqual([{ label: null, text: 'type 1, MMSI 211234567', note: null }])
    expect(out[2].title).toBe('Decoded frame header')
    expect(out[2].level).toBe('VERIFIED')
  })

  it('never upgrades the level: it is whatever the Parameter says', () => {
    const d = parseDecodedParameter(param({ id: 'pages', level: 'ESTIMATED', evidence: ['RIC 0000001 function 3: "X"'] }))
    expect(d?.level).toBe('ESTIMATED')
  })

  it('returns nothing without a match stage, without a decoded-text parameter, or for other parameters', () => {
    expect(decodedMessages([])).toEqual([])
    expect(decodedMessages([{ ...matchStage([]), id: 'classify' }])).toEqual([])
    expect(decodedMessages([matchStage([SYSTEM])])).toEqual([])
    expect(parseDecodedParameter(param({ id: 'modulation' }))).toBeNull()
  })

  it('keeps a matched system whose pages carry no text, and says there is none', () => {
    const pages = param({
      id: 'pages',
      value: '2 pages',
      evidence: ['RIC 0000010 function 0: not shown (numeric, or a codeword failed)'],
    })
    const [d] = decodedMessages([matchStage([SYSTEM, pages])])
    expect(d.hasText).toBe(false)
    expect(d.lines[0].text).toBeNull()
    expect(d.lines[0].note).toContain('not shown')
  })

  it('copes with empty evidence and a null system value', () => {
    const [d] = decodedMessages([matchStage([{ ...SYSTEM, value: null }, param({ id: 'pages', evidence: [] })])])
    expect(d.system).toBeNull()
    expect(d.lines).toEqual([])
    expect(d.hasText).toBe(false)
  })

  it('renders the lines as clipboard text', () => {
    const [d] = decodedMessages([
      matchStage([
        param({
          id: 'pages',
          evidence: ['RIC 0001234 function 3: "HI"', 'RIC 0000002 function 0: not shown (numeric, or a codeword failed)'],
        }),
      ]),
    ])
    expect(decodedMessagesAsText(d)).toBe('RIC 0001234 · function 3: HI\nRIC 0000002 · function 0: not shown (numeric, or a codeword failed)')
  })
})
