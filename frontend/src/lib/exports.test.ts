import { describe, expect, it } from 'vitest'
import { canSaveSigmf, resultLinks, SAVE_SIGMF_HINT } from './exports'

const formats = (sigmf: 'annotate' | 'save' | 'none') => resultLinks(sigmf).map((l) => l.format)

describe('resultLinks', () => {
  it('always offers the five downloads and the run record', () => {
    expect(formats('none')).toEqual(['json', 'csv', 'txt', 'pdf', 'run'])
  })

  it('adds the annotated SigMF metadata for a SigMF recording and for a raw file', () => {
    expect(formats('annotate')).toEqual(['json', 'csv', 'txt', 'pdf', 'run', 'sigmf'])
    expect(formats('save')).toEqual(['json', 'csv', 'txt', 'pdf', 'run', 'sigmf'])
  })

  it('gives every link a hint saying what it does', () => {
    for (const link of resultLinks('save')) expect(link.hint.length).toBeGreaterThan(20)
  })
})

describe('Save as SigMF', () => {
  it('belongs to raw files only, and its hint promises the samples are untouched', () => {
    expect(canSaveSigmf('save')).toBe(true)
    expect(canSaveSigmf('annotate')).toBe(false)
    expect(canSaveSigmf('none')).toBe(false)
    expect(SAVE_SIGMF_HINT).toMatch(/next to the original/)
    expect(SAVE_SIGMF_HINT).toMatch(/samples are never touched/)
  })
})
