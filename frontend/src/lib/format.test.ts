import { describe, expect, it } from 'vitest'
import { niceTicks, sci, signed } from './format'

describe('sci', () => {
  it('formats small p-values with superscript exponents', () => {
    expect(sci(7.788e-6)).toBe('7.8 × 10⁻⁶')
    expect(sci(2e-19)).toBe('2 × 10⁻¹⁹')
    expect(sci(3.1e-41)).toBe('3.1 × 10⁻⁴¹')
  })

  it('rolls a rounded mantissa of 10 into the exponent', () => {
    expect(sci(9.96e-5)).toBe('1 × 10⁻⁴')
  })

  it('keeps ordinary values as plain decimals', () => {
    expect(sci(0.21)).toBe('0.21')
    expect(sci(0.08)).toBe('0.08')
    expect(sci(0)).toBe('0')
  })
})

describe('niceTicks', () => {
  it('uses 1/2/5 steps and stays inside the range', () => {
    const { ticks, step } = niceTicks(-125_000, 125_000, 6)
    expect(step).toBe(50_000)
    expect(ticks).toEqual([-100_000, -50_000, 0, 50_000, 100_000])
  })

  it('handles an empty span', () => {
    expect(niceTicks(3, 3).ticks).toEqual([3])
  })
})

describe('signed', () => {
  it('uses a true minus sign and no sign on zero', () => {
    expect(signed(-40, 1)).toBe('−40.0')
    expect(signed(40, 0)).toBe('+40')
    expect(signed(-0.0001, 1)).toBe('0.0')
  })
})
