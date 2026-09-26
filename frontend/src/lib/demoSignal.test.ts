import { beforeAll, describe, expect, it } from 'vitest'
import { DEMO_CONFIG, generateDemo, rrcTaps, type DemoProducts } from './demoSignal'

let demo: DemoProducts

beforeAll(() => {
  demo = generateDemo()
})

function binOf(freqHz: number): number {
  return Math.round((freqHz / demo.fs) * demo.fftSize) + demo.bins / 2
}

function median(values: Float64Array): number {
  const s = Float64Array.from(values).sort()
  return s[Math.floor(s.length / 2)]
}

describe('demo capture', () => {
  it('has the documented STFT geometry', () => {
    expect(demo.bins).toBe(DEMO_CONFIG.fftSize)
    expect(demo.rows).toBe(Math.floor((DEMO_CONFIG.n - DEMO_CONFIG.fftSize) / DEMO_CONFIG.hop) + 1)
    expect(demo.tile.length).toBe(demo.rows * demo.bins)
    expect(demo.dbMax).toBeGreaterThan(demo.dbMin)
  })

  it('shows the CW carrier as the strongest PSD bin', () => {
    let peak = 0
    for (let k = 1; k < demo.bins; k++) if (demo.psdDb[k] > demo.psdDb[peak]) peak = k
    expect(Math.abs(peak - binOf(DEMO_CONFIG.cw.fc))).toBeLessThanOrEqual(1)
  })

  it('raises the QPSK and FSK bands above the noise floor', () => {
    const floor = median(demo.psdDb)
    expect(demo.psdDb[binOf(DEMO_CONFIG.qpsk.fc)] - floor).toBeGreaterThan(4)
    expect(demo.psdDb[binOf(DEMO_CONFIG.fsk.fc + DEMO_CONFIG.fsk.deviation)] - floor).toBeGreaterThan(4)
  })

  it('produces a QPSK constellation whose EVM matches the configured Es/N0', () => {
    const expected = Math.sqrt(10 ** (-DEMO_CONFIG.qpsk.esN0Db / 10))
    expect(demo.evm).toBeGreaterThan(expected * 0.9)
    expect(demo.evm).toBeLessThan(expected * 1.15)
  })

  it('puts the FSK instantaneous frequency on its two tones', () => {
    const dev = DEMO_CONFIG.fsk.deviation
    let near = 0
    for (const f of demo.fskInstFreqHz) if (Math.abs(Math.abs(f) - dev) < dev * 0.5) near++
    expect(near / demo.fskInstFreqHz.length).toBeGreaterThan(0.7)
  })

  it('is deterministic', () => {
    const again = generateDemo()
    expect(again.tile).toEqual(demo.tile)
    expect(again.evm).toBe(demo.evm)
  })
})

describe('rrcTaps', () => {
  it('has unit energy and is symmetric', () => {
    const h = rrcTaps(0.35, 10, 8)
    let energy = 0
    for (const v of h) energy += v * v
    expect(energy).toBeCloseTo(1, 12)
    for (let i = 0; i < h.length; i++) expect(h[i]).toBeCloseTo(h[h.length - 1 - i], 12)
  })
})
