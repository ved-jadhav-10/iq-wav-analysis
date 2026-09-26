import { describe, expect, it } from 'vitest'
import { buildLut, COLORMAPS, relativeLuminance, type ColormapName } from './colormaps'

describe('colormaps', () => {
  for (const name of Object.keys(COLORMAPS) as ColormapName[]) {
    it(`${name}: 256 opaque entries with monotonically rising luminance`, () => {
      const lut = buildLut(name)
      expect(lut.length).toBe(256 * 4)
      let prev = -Infinity
      for (let i = 0; i < 256; i++) {
        expect(lut[i * 4 + 3]).toBe(255)
        const y = relativeLuminance(lut[i * 4], lut[i * 4 + 1], lut[i * 4 + 2])
        // Small tolerance for 8-bit rounding between neighbouring entries.
        expect(y).toBeGreaterThanOrEqual(prev - 1e-3)
        prev = y
      }
    })
  }

  it('starts and ends on the first and last stop exactly', () => {
    const lut = buildLut('gray')
    expect(Array.from(lut.slice(0, 3))).toEqual([0, 0, 0])
    expect(Array.from(lut.slice(255 * 4, 255 * 4 + 3))).toEqual([255, 255, 255])
  })
})
