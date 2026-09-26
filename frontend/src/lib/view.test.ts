import { describe, expect, it } from 'vitest'
import { clampView, fullView, MIN_TIME_SPAN_S, zoomAxis } from './view'

const full = fullView(1023, 256, 250_000)

describe('view', () => {
  it('spans the whole capture by default', () => {
    expect(full.f0).toBe(-125_000)
    expect(full.f1).toBe(125_000)
    expect(full.t1).toBeCloseTo((1023 * 256) / 250_000, 12)
  })

  it('keeps a panned view inside the data without changing its span', () => {
    const v = clampView({ t0: -0.2, t1: 0.1, f0: 100_000, f1: 150_000 }, full)
    expect(v.t0).toBe(0)
    expect(v.t1).toBeCloseTo(0.3, 12)
    expect(v.f1).toBe(125_000)
    expect(v.f1 - v.f0).toBe(50_000)
  })

  it('never zooms in past the minimum span or out past the full extent', () => {
    expect(clampView({ ...full, t0: 0.5, t1: 0.5001 }, full).t1 - 0.5).toBeCloseTo(MIN_TIME_SPAN_S, 12)
    expect(clampView({ t0: -10, t1: 10, f0: -1e6, f1: 1e6 }, full)).toEqual(full)
  })

  it('zooms around the anchor', () => {
    expect(zoomAxis(0, 100, 25, 0.5)).toEqual([12.5, 62.5])
  })
})
