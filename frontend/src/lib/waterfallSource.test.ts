import { describe, expect, it } from 'vitest'
import type { Assumptions, LevelInfo, RecordingInfo } from './api'
import type { Parameter } from './evidence'
import { axisUnits, sourceFromRecording } from './waterfallSource'

function param(id: string, value: string | number | null, level: Parameter['level'] = 'MEASURED'): Parameter {
  return { id, name: id, value, level, confidence: null, method: 'test fixture', evidence: [], alternatives: [], warnings: [] }
}

const assumptions: Assumptions = {
  datatype: param('datatype', 'cf32_le'),
  dataOffset: param('dataOffset', 0),
  sampleRate: param('sampleRate', 1_000_000),
  centerFrequency: param('centerFrequency', 0),
  iqOrder: param('iqOrder', 'IQ'),
}

function recording(overrides: Partial<RecordingInfo> = {}): RecordingInfo {
  return {
    id: 'rec-1',
    container: 'SigMF',
    name: 'capture.sigmf-meta',
    numSamples: 65536,
    real: false,
    recorder: null,
    synthetic: false,
    fftSize: 1024,
    hop: 512,
    sampleRate: 1_000_000,
    dbMin: -80,
    dbMax: 0,
    freqsHz: [-500_000, 0, 500_000],
    freqsNorm: [-0.5, 0, 0.5],
    psdDb: [-70, -60, -70],
    levels: [{ level: 0, rows: 128, cols: 1024, rowSpan: 1 }],
    assumptions,
    captureQuality: [],
    analysis: { state: 'done', done: 0, total: 0 },
    detections: [],
    ...overrides,
  }
}

const level: LevelInfo = { level: 1, rows: 64, cols: 1024, rowSpan: 2 }

describe('sourceFromRecording', () => {
  it('folds the level row span into hop, so fullView sees that level’s own time resolution', () => {
    const grid = new Uint8Array(64 * 1024)
    const source = sourceFromRecording(recording(), level, grid)
    expect(source.hop).toBe(512 * 2)
    expect(source.rows).toBe(64)
    expect(source.bins).toBe(1024)
    expect(source.tile).toBe(grid)
    expect(source.fs).toBe(1_000_000)
    expect(source.freqsHz).toEqual([-500_000, 0, 500_000])
  })

  it('draws an UNKNOWN sample rate in normalised units, never a default rate', () => {
    const info = recording({ sampleRate: null, freqsHz: null })
    const source = sourceFromRecording(info, level, new Uint8Array(0))
    expect(source.normalised).toBe(true)
    expect(source.fs).toBe(1)
    expect(source.freqsHz).toEqual(info.freqsNorm)
    expect(axisUnits(source).timeUnit).toBe('samples')
    expect(axisUnits(source).freqUnit).toBe('× fs')
  })

  it('is normalised too when freqsHz is missing even if a sample rate is somehow present', () => {
    const source = sourceFromRecording(recording({ freqsHz: null }), level, new Uint8Array(0))
    expect(source.normalised).toBe(true)
  })

  it('shows a known rate in kHz and ms', () => {
    const source = sourceFromRecording(recording(), level, new Uint8Array(0))
    expect(source.normalised).toBe(false)
    expect(axisUnits(source).freqUnit).toBe('kHz')
  })
})
