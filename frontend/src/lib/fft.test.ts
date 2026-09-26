import { describe, expect, it } from 'vitest'
import { fft } from './fft'

describe('fft', () => {
  it('turns an impulse into a flat spectrum', () => {
    const re = new Float64Array(16)
    const im = new Float64Array(16)
    re[0] = 1
    fft(re, im)
    for (let k = 0; k < 16; k++) {
      expect(re[k]).toBeCloseTo(1, 12)
      expect(im[k]).toBeCloseTo(0, 12)
    }
  })

  it('puts a complex exponential in exactly one bin', () => {
    const n = 64
    const bin = 5
    const re = new Float64Array(n)
    const im = new Float64Array(n)
    for (let i = 0; i < n; i++) {
      re[i] = Math.cos((2 * Math.PI * bin * i) / n)
      im[i] = Math.sin((2 * Math.PI * bin * i) / n)
    }
    fft(re, im)
    for (let k = 0; k < n; k++) {
      const mag = Math.hypot(re[k], im[k])
      expect(mag).toBeCloseTo(k === bin ? n : 0, 9)
    }
  })

  it('preserves energy (Parseval)', () => {
    const n = 256
    const re = new Float64Array(n)
    const im = new Float64Array(n)
    let timeEnergy = 0
    for (let i = 0; i < n; i++) {
      re[i] = Math.sin(i * 0.37) + 0.2 * Math.cos(i * 1.9)
      im[i] = Math.cos(i * 0.11)
      timeEnergy += re[i] ** 2 + im[i] ** 2
    }
    fft(re, im)
    let freqEnergy = 0
    for (let k = 0; k < n; k++) freqEnergy += re[k] ** 2 + im[k] ** 2
    expect(freqEnergy / n).toBeCloseTo(timeEnergy, 9)
  })

  it('rejects lengths that are not powers of two', () => {
    expect(() => fft(new Float64Array(12), new Float64Array(12))).toThrow(/power of two/)
  })
})
