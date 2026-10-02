import { describe, expect, it } from 'vitest'
import { GLOSSARY, glossaryKeyFor } from './glossary'
import { EVIDENCE_LEVELS, LEVEL_INFO } from './evidence'

describe('GLOSSARY', () => {
  it('gives every entry a term and a non-empty short definition', () => {
    for (const [key, entry] of Object.entries(GLOSSARY)) {
      expect(entry.term.trim(), key).not.toBe('')
      expect(entry.short.trim(), key).not.toBe('')
      if (entry.long !== undefined) expect(entry.long.trim(), key).not.toBe('')
    }
  })

  it('has the terms the panels rely on', () => {
    for (const key of [
      'esn0', 'snr', 'evm', 'symbolRate', 'crc', 'asm', 'conv', 'viterbi', 'interleaver', 'rs', 'ldpc',
      'ledger', 'pvalue', 'fwer', 'shuffled', 'iqOrder', 'constellation', 'eye',
    ]) {
      expect(GLOSSARY[key], key).toBeDefined()
    }
  })

  it('reuses the evidence level wording', () => {
    for (const level of EVIDENCE_LEVELS) {
      const entry = GLOSSARY[level.toLowerCase()]
      expect(entry.short).toBe(LEVEL_INFO[level].meaning)
      expect(entry.term).toBe(LEVEL_INFO[level].label)
    }
  })
})

describe('glossaryKeyFor', () => {
  it.each([
    ['Es/N0', 'esn0'],
    ['EVM', 'evm'],
    ['evm', 'evm'],
    ['CRC', 'crc'],
    ['Frame check', 'crc'],
    ['Sync word', 'asm'],
    ['Symbol rate', 'symbolRate'],
    ['Interleaver', 'interleaver'],
    ['Deinterleave', 'interleaver'],
    ['FEC', 'fec'],
    ['Code', 'fec'],
    ['RS', 'rs'],
    ['Outer code', 'rs'],
    ['LDPC', 'ldpc'],
    ['LDPC code', 'ldpc'],
    ['SNR (detector statistic)', 'snr'],
    ['IQ order', 'iqOrder'],
    ['Sync', 'timingSync'],
    ['Shuffled-bit accepts', 'shuffled'],
    ['Family-wise error', 'fwer'],
    ['p', 'pvalue'],
    ['Verified', 'verified'],
  ])('maps %s to %s', (label, key) => {
    expect(glossaryKeyFor(label)).toBe(key)
  })

  it('returns null for labels it does not know and for near misses', () => {
    expect(glossaryKeyFor('')).toBeNull()
    expect(glossaryKeyFor('Carrier frequency')).toBeNull()
    expect(glossaryKeyFor('Code alignment')).toBeNull()
    expect(glossaryKeyFor('Frame length')).toBeNull()
    expect(glossaryKeyFor('Payload')).toBeNull()
  })

  it('only ever returns keys that exist', () => {
    for (const label of ['Es/N0', 'EVM', 'CRC', 'Sync', 'FEC', 'Frame', 'Match', 'Known system', 'Roll-off', 'Phase ambiguity', 'Threshold', 'Tried', 'Eye']) {
      const key = glossaryKeyFor(label)
      expect(key, label).not.toBeNull()
      expect(GLOSSARY[key as string], label).toBeDefined()
    }
  })
})
