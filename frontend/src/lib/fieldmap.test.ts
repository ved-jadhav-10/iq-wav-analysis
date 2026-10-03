import { describe, expect, it } from 'vitest'
import type { Frame } from './analysis'
import { binomialTail, fieldMap, MIN_FRAMES_FOR_FIELDS } from './fieldmap'

/** A small deterministic byte source, so "random" payloads are the same on every run. */
function bytesFrom(seed: number, count: number): number[] {
  // mulberry32, started from a hashed seed: neighbouring seeds give unrelated bytes (a plain LCG's
  // top byte moves by a fixed step from seed to seed, which is exactly what a counter looks like).
  let s = Math.imul(seed ^ 0x9e3779b9, 0x85ebca6b) >>> 0
  return Array.from({ length: count }, () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) & 0xff
  })
}

const hex = (bytes: readonly number[]) => bytes.map((b) => b.toString(16).padStart(2, '0')).join('')

/** `n` frames: the 1ACFFC1D sync word, the two constant bytes AB CD, one counter byte, six random bytes. */
function frames(n: number, over: (i: number) => Partial<Frame> = () => ({}), counter = (i: number) => i): Frame[] {
  return Array.from({ length: n }, (_, i) => ({
    index: i + 1,
    startBit: i * 1024,
    syncWord: '1ACFFC1D',
    lengthBits: 1024,
    crc: 'pass' as const,
    headerHex: '',
    payloadHex: hex([0xab, 0xcd, counter(i) & 0xff, ...bytesFrom(7 + i * 31, 6)]),
    ...over(i),
  }))
}

describe('binomialTail', () => {
  it('is the upper tail of the binomial', () => {
    expect(binomialTail(0, 5, 0.3)).toBe(1)
    expect(binomialTail(6, 5, 0.3)).toBe(0)
    expect(binomialTail(2, 2, 0.5)).toBeCloseTo(0.25, 12)
    expect(binomialTail(1, 2, 0.5)).toBeCloseTo(0.75, 12)
    expect(binomialTail(40, 44, 1 / 256)).toBeLessThan(1e-90) // finite and tiny, not NaN
  })
})

describe('fieldMap', () => {
  it('finds the constant sync and header, the counter and where the fixed part ends', () => {
    const m = fieldMap(frames(20))
    expect(m.enough).toBe(true)
    expect(m.syncBits).toBe(32)
    const [fixed, counter, rest] = m.fields
    expect(fixed).toMatchObject({ kind: 'constant', startBit: 0, bits: 48, value: '1A CF FC 1D AB CD' })
    expect(fixed.p).toBeLessThanOrEqual(1e-6)
    expect(counter).toMatchObject({ kind: 'counter', startBit: 48, bits: 8, step: 1 })
    expect(rest).toMatchObject({ kind: 'variable', startBit: 56 })
    expect(m.headerEnd).toBe(56)
    expect(m.agreement.slice(0, 48).every((a) => a === 1)).toBe(true)
    expect(m.agreement[60]).toBeLessThan(1) // inside the random bytes
  })

  it('reads a counter that counts down as a negative step, and survives a missed frame', () => {
    const down = fieldMap(frames(20, () => ({}), (i) => 200 - i))
    expect(down.fields.find((f) => f.kind === 'counter')).toMatchObject({ startBit: 48, step: -1 })
    const skipped = fieldMap(frames(20, () => ({}), (i) => (i < 10 ? i : i + 1)))
    expect(skipped.fields.find((f) => f.kind === 'counter')).toMatchObject({ startBit: 48, step: 1 })
  })

  it('keeps a small counter whole: its constant high bits are not a field of their own', () => {
    const m = fieldMap(frames(20))
    const counter = m.fields.find((f) => f.kind === 'counter')!
    expect(m.fields.filter((f) => f.kind === 'constant' && f.startBit >= counter.startBit && f.startBit < counter.startBit + 8)).toEqual([])
  })

  it('finds a constant that is not on a byte boundary', () => {
    // The payload's first byte is always 101xxxxx: the sync word's 32 bits and those 3 make one run.
    const m = fieldMap(frames(20, (i) => ({ payloadHex: hex([0xa0 | (bytesFrom(3 + i * 101, 1)[0] & 0x1f), ...bytesFrom(9 + i * 17, 7)]) })))
    expect(m.fields[0]).toMatchObject({ kind: 'constant', startBit: 0, bits: 35 })
    expect(m.headerEnd).toBe(35)
  })

  it('claims nothing from too few frames', () => {
    const m = fieldMap(frames(MIN_FRAMES_FOR_FIELDS - 1))
    expect(m.enough).toBe(false)
    expect(m.fields).toEqual([])
    expect(m.of).toBe(MIN_FRAMES_FOR_FIELDS - 1)
  })

  it('compares only the frames that pass their CRC when there are enough of them', () => {
    const mixed = frames(24, (i) => (i % 3 === 2 ? { crc: 'fail' as const, payloadHex: hex(bytesFrom(i, 9)) } : {}))
    const m = fieldMap(mixed)
    expect(m.passingOnly).toBe(true)
    expect(m.frames).toBe(16)
    expect(m.fields[0]).toMatchObject({ kind: 'constant', bits: 48 })
  })

  it('falls back to every frame when too few pass, and says so', () => {
    const m = fieldMap(frames(12, (i) => (i < 6 ? { crc: 'fail' as const } : {})))
    expect(m.passingOnly).toBe(false)
    expect(m.frames).toBe(12)
  })

  it('finds no field in random frames', () => {
    const random = Array.from({ length: 30 }, (_, i) => ({
      index: i + 1,
      startBit: i * 512,
      syncWord: '',
      lengthBits: 512,
      crc: 'pass' as const,
      headerHex: '',
      payloadHex: hex(bytesFrom(1000 + i * 977, 40)),
    }))
    const m = fieldMap(random)
    expect(m.enough).toBe(true)
    expect(m.fields).toHaveLength(1)
    expect(m.fields[0].kind).toBe('variable')
    expect(m.headerEnd).toBe(0)
  })

  it('never claims a field in 300 sets of random frames, even at the fewest frames it will compare', () => {
    for (let trial = 0; trial < 300; trial++) {
      const random = Array.from({ length: MIN_FRAMES_FOR_FIELDS }, (_, i) => ({
        index: i + 1,
        startBit: i * 512,
        syncWord: '',
        lengthBits: 512,
        crc: 'pass' as const,
        headerHex: '',
        payloadHex: hex(bytesFrom(trial * 1009 + i * 7919 + 5, 64)),
      }))
      const claimed = fieldMap(random).fields.filter((f) => f.kind !== 'variable')
      expect(claimed, `trial ${trial}`).toEqual([])
    }
  })
})
