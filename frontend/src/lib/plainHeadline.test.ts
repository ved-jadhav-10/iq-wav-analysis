import { describe, expect, it } from 'vitest'
import type { Frame } from './analysis'
import type { Parameter, StageResult } from './evidence'
import { isPending, plainHeadline, type HeadlineInput } from './plainHeadline'

const NBSP = ' '

function p(id: string, name: string, value: string | number | null, over: Partial<Parameter> = {}): Parameter {
  return { id, name, value, level: 'ESTIMATED', confidence: null, method: '', evidence: [], alternatives: [], warnings: [], ...over }
}

function stage(
  id: string,
  name: string,
  level: StageResult['level'],
  parameters: Parameter[] = [],
  over: Partial<StageResult> = {},
): StageResult {
  return { id, name, status: 'done', summary: name, level, parameters, ...over }
}

function frames(pass: number, fail = 0): Frame[] {
  return Array.from({ length: pass + fail }, (_, i) => ({
    index: i,
    startBit: i * 1000,
    syncWord: '1ACFFC1D',
    lengthBits: 1000,
    crc: i < pass ? ('pass' as const) : ('fail' as const),
    headerHex: '00 01',
    payloadHex: 'AB',
  }))
}

const search = { tried: 1344, alpha: 0.01, correction: 'Holm', smallestThreshold: 7e-6, shuffledRuns: 3, shuffledAccepts: 0, rows: [] }
const estimate = stage('estimate', 'Estimate', 'ESTIMATED', [p('symbol_rate', 'Symbol rate', 25000, { unit: 'Bd', uncertainty: 12 })])
const classify = stage('classify', 'Classify', 'HYPOTHESIS', [p('modulation', 'Modulation', 'QPSK', { level: 'HYPOTHESIS' })])

const base: HeadlineInput = {
  kind: 'psk',
  level: 'ESTIMATED',
  label: 'QPSK?',
  headline: 'QPSK? 25 kBd, not decoded',
  stages: [estimate, classify],
  frames: [],
  search,
}

describe('plainHeadline', () => {
  it('says a verified decode was proven by the frame checks, and that it was error-corrected', () => {
    const d: HeadlineInput = {
      ...base,
      level: 'VERIFIED',
      label: 'QPSK',
      headline: 'QPSK 25 kBd → conv K=7 r½ → CCSDS ASM frames, 51/51 CRC pass',
      stages: [
        estimate,
        classify,
        stage('fec', 'FEC', 'VERIFIED', [p('code', 'Code', 'conv K=7 r½', { level: 'VERIFIED' })]),
        stage('frame', 'Frame', 'VERIFIED'),
      ],
      frames: frames(51),
    }
    expect(plainHeadline(d)).toBe('Digital QPSK signal, error-corrected and proven by 51 of 51 frame checksums (CRC)')
  })

  it('names the interleaver it undid, without the bit offset, only when that was verified', () => {
    const verified: HeadlineInput = {
      ...base,
      level: 'VERIFIED',
      label: '8PSK',
      headline: '8PSK 50 kBd → conv K=7 r½ → CCSDS ASM frames, 67/67 CRC pass',
      stages: [
        estimate,
        stage('classify', 'Classify', 'VERIFIED', [p('modulation', 'Modulation', '8PSK', { level: 'VERIFIED' })]),
        stage('deinterleave', 'De-interleave', 'VERIFIED', [
          p('interleaver', 'Interleaver', 'block 16x36 from bit 284', { level: 'VERIFIED' }),
        ]),
        stage('fec', 'FEC', 'VERIFIED', [p('code', 'Code', 'conv K=7 r½', { level: 'VERIFIED' })]),
        stage('frame', 'Frame', 'VERIFIED'),
      ],
      frames: frames(67),
    }
    expect(plainHeadline(verified)).toBe(
      'Digital 8PSK signal, de-interleaved (block 16x36), error-corrected and proven by 67 of 67 frame checksums (CRC)',
    )
    const hypothesis = {
      ...verified,
      stages: verified.stages.map((s) =>
        s.id === 'deinterleave'
          ? { ...s, parameters: [p('interleaver', 'Interleaver', 'block 16x36 from bit 284', { level: 'HYPOTHESIS' })] }
          : s,
      ),
    }
    expect(plainHeadline(hypothesis)).not.toContain('de-interleaved')
    const none = {
      ...verified,
      stages: verified.stages.map((s) =>
        s.id === 'deinterleave'
          ? { ...s, parameters: [p('interleaver', 'Interleaver', 'none', { level: 'VERIFIED' })] }
          : s,
      ),
    }
    expect(plainHeadline(none)).toBe(
      'Digital 8PSK signal, error-corrected and proven by 67 of 67 frame checksums (CRC)',
    )
  })

  it('says when the error-correcting code was found blind rather than taken from the catalogue', () => {
    const d: HeadlineInput = {
      ...base,
      level: 'VERIFIED',
      label: 'QPSK',
      headline: 'QPSK 35.7 kBd → Conv K=9 r1/2 (561,753)₈ (found blind) → CCSDS ASM frames, 47/47 CRC pass',
      stages: [
        estimate,
        classify,
        stage('fec', 'FEC', 'VERIFIED', [p('code', 'Code', 'Conv K=9 r1/2 (561,753)₈', { level: 'VERIFIED' })]),
        stage('frame', 'Frame', 'VERIFIED'),
      ],
      frames: frames(47),
    }
    expect(plainHeadline(d)).toBe(
      'Digital QPSK signal, error-corrected by a code it found blind, and proven by 47 of 47 frame checksums (CRC)',
    )
  })

  it('leaves out error-corrected for an uncoded chain and counts partial passes', () => {
    const d: HeadlineInput = {
      ...base,
      level: 'VERIFIED',
      label: 'QPSK',
      stages: [
        estimate,
        classify,
        stage('fec', 'FEC', 'VERIFIED', [p('code', 'Code', 'Uncoded', { level: 'VERIFIED' })]),
        stage('frame', 'Frame', 'VERIFIED'),
      ],
      frames: frames(12, 2),
    }
    expect(plainHeadline(d)).toBe('Digital QPSK signal, proven by 12 of 14 frame checksums (CRC)')
  })

  it('names a known system and never calls its own check a CRC when only that check passed', () => {
    const d: HeadlineInput = {
      ...base,
      kind: 'fsk',
      level: 'VERIFIED',
      label: '2-FSK',
      headline: '2-FSK 1.2 kBd → POCSAG: 3/3 frames pass its check',
      stages: [
        stage('classify', 'Classify', 'HYPOTHESIS', [p('modulation', 'Modulation', '2-FSK')]),
        stage('match', 'Match', 'VERIFIED', [], { summary: 'POCSAG: 3 batches decoded' }),
      ],
      frames: frames(3),
    }
    const text = plainHeadline(d)
    expect(text).toBe('Digital 2-FSK signal; matches POCSAG, whose own check passed on 3 of 3 frames')
    expect(text).not.toContain('CRC')
  })

  it('keeps an analog signal out of the digital story, hedged by its estimated level', () => {
    const d: HeadlineInput = {
      kind: 'analog',
      level: 'ESTIMATED',
      label: 'FM',
      headline: 'Analog FM: not sent to the digital chain',
      stages: [stage('classify', 'Classify', 'ESTIMATED')],
      frames: [],
      search: null,
    }
    expect(plainHeadline(d)).toBe('Probably FM (analog), kept out of the digital chain')
  })

  it('reports a firm modulation with no code found, with the number of hypotheses tried', () => {
    const d: HeadlineInput = {
      ...base,
      label: 'QPSK',
      stages: [
        estimate,
        classify,
        stage('fec', 'FEC', 'UNKNOWN', [p('code', 'Code', null, { level: 'UNKNOWN' })], { summary: 'No catalogued code confirmed' }),
      ],
    }
    expect(plainHeadline(d)).toBe(
      `Digital QPSK signal at about 25${NBSP}kBd; no error-correction code found among 1,344 hypotheses tried`,
    )
  })

  it('hedges an unconfirmed modulation and says it was not decoded', () => {
    expect(plainHeadline(base)).toBe(`Probably QPSK at about 25${NBSP}kBd; not decoded`)
  })

  it('says possibly for a bare hypothesis and drops a rate that is not in baud', () => {
    const d: HeadlineInput = {
      ...base,
      level: 'HYPOTHESIS',
      stages: [
        stage('estimate', 'Estimate', 'ESTIMATED', [p('symbol_rate', 'Symbol rate', 0.05, { unit: 'symbols/sample' })]),
        classify,
      ],
      search: null,
    }
    expect(plainHeadline(d)).toBe('Possibly QPSK; not decoded')
  })

  it('reads the pending placeholder as analysing', () => {
    const d: HeadlineInput = {
      kind: 'unknown',
      level: 'ESTIMATED',
      label: 'Signal',
      headline: 'Analysing this signal…',
      stages: [stage('detect', 'Detect', 'ESTIMATED')],
      frames: [],
      search: null,
    }
    expect(isPending(d)).toBe(true)
    expect(plainHeadline(d)).toBe('Analysing this signal…')
    expect(isPending({ label: 'QPSK', headline: 'Analysing this signal…' })).toBe(false)
  })

  it('explains a detection whose symbol rate is unknown', () => {
    const d: HeadlineInput = {
      kind: 'unknown',
      level: 'ESTIMATED',
      label: 'Unknown',
      headline: 'Detected; symbol rate unknown, not decoded',
      stages: [stage('detect', 'Detect', 'ESTIMATED'), stage('estimate', 'Estimate', 'UNKNOWN')],
      frames: [],
      search: null,
    }
    expect(plainHeadline(d)).toBe('Signal detected, but its symbol rate is unknown, so nothing was decoded')
  })

  it('falls back to the engine headline when it cannot say more, and never claims proof without a pass', () => {
    const odd: HeadlineInput = { ...base, kind: 'cw', label: 'CW', headline: 'Carrier at 1 kHz' }
    expect(plainHeadline(odd)).toBe('Carrier at 1 kHz')
    const noPass: HeadlineInput = { ...base, level: 'VERIFIED', frames: frames(0, 3), headline: 'engine says verified' }
    expect(plainHeadline(noPass)).toBe('engine says verified')
  })

  it('shows a rate in baud below 1 kBd and in kBd above', () => {
    const at = (value: number): HeadlineInput => ({
      ...base,
      stages: [stage('estimate', 'Estimate', 'ESTIMATED', [p('symbol_rate', 'Symbol rate', value, { unit: 'Bd' })]), classify],
    })
    expect(plainHeadline(at(1200))).toContain(`1.2${NBSP}kBd`)
    expect(plainHeadline(at(300))).toContain(`300${NBSP}Bd`)
  })
})
