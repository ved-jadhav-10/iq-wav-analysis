import { describe, expect, it } from 'vitest'
import type { Frame } from './analysis'
import { defaultFrame, frameAnatomy, hexBytes, MIN_FRAMES_FOR_RECURRENCE, recurrence, streamExtent, taggedBytes } from './bitstream'

function frame(over: Partial<Frame> = {}): Frame {
  return {
    index: 1,
    startBit: 0,
    syncWord: '1ACFFC1D',
    lengthBits: 1024,
    crc: 'pass',
    headerHex: '',
    payloadHex: '',
    ...over,
  }
}

function periodic(n: number, period = 1024, over: Partial<Frame> = {}): Frame[] {
  return Array.from({ length: n }, (_, i) => frame({ index: i + 1, startBit: 100 + i * period, lengthBits: period, ...over }))
}

describe('streamExtent', () => {
  it('spans the first start bit to the last start plus length', () => {
    expect(streamExtent(periodic(3))).toEqual({ min: 100, max: 100 + 2 * 1024 + 1024, span: 3 * 1024 })
  })
  it('is null with no frames and never zero-width with one empty frame', () => {
    expect(streamExtent([])).toBeNull()
    expect(streamExtent([frame({ startBit: 7, lengthBits: 0 })])?.span).toBe(1)
  })
})

describe('recurrence', () => {
  it('finds the dominant spacing and the share of gaps equal to it', () => {
    const r = recurrence(periodic(45))
    expect(r.frames).toBe(45)
    expect(r.period).toBe(1024)
    expect(r.matching).toBe(44)
    expect(r.gaps).toHaveLength(44)
    expect(r.fraction).toBe(1)
    expect(r.syncWord).toBe('1ACFFC1D')
    expect(r.enough).toBe(true)
    expect(r.periodic).toBe(true)
  })

  it('counts a missed frame as an off-period gap, not as the period', () => {
    const frames = periodic(6)
    frames.splice(3, 1) // one frame missing: one gap of 2048
    const r = recurrence(frames)
    expect(r.period).toBe(1024)
    expect(r.gaps.filter((g) => g === 2048)).toHaveLength(1)
    expect(r.matching).toBe(r.gaps.length - 1)
    expect(r.fraction).toBeCloseTo(3 / 4)
    expect(r.periodic).toBe(false)
  })

  it('sorts by start bit before differencing', () => {
    const r = recurrence([...periodic(5)].reverse())
    expect(r.period).toBe(1024)
    expect(r.gaps.every((g) => g > 0)).toBe(true)
  })

  it('breaks a tie by the smaller gap', () => {
    const r = recurrence([frame({ startBit: 0 }), frame({ startBit: 10 }), frame({ startBit: 30 })])
    expect(r.gaps).toEqual([10, 20])
    expect(r.period).toBe(10)
  })

  it('says nothing from 0, 1 or 2 frames', () => {
    expect(MIN_FRAMES_FOR_RECURRENCE).toBe(3)
    const none = recurrence([])
    expect(none).toMatchObject({ frames: 0, period: null, fraction: null, syncWord: null, enough: false, periodic: false })
    const one = recurrence(periodic(1))
    expect(one).toMatchObject({ frames: 1, gaps: [], period: null, enough: false, periodic: false })
    const two = recurrence(periodic(2))
    expect(two).toMatchObject({ frames: 2, period: 1024, matching: 1, fraction: 1, enough: false, periodic: false })
  })
})

describe('hexBytes', () => {
  it('reads spaced and unspaced hex, uppercases, drops a dangling digit', () => {
    expect(hexBytes('00 01 ab')).toEqual(['00', '01', 'AB'])
    expect(hexBytes('deadbeef')).toEqual(['DE', 'AD', 'BE', 'EF'])
    expect(hexBytes('ABC')).toEqual(['AB'])
    expect(hexBytes('')).toEqual([])
  })
})

describe('frameAnatomy', () => {
  it('splits sync, header, payload and CRC when the header is the start of the payload', () => {
    // 32 sync + 8 payload bytes (64) + 16 CRC = 112
    const f = frame({ lengthBits: 112, headerHex: '48 45 4C 4C', payloadHex: '48454C4C4F212121' })
    const a = frameAnatomy(f)
    expect(a.headerInPayload).toBe(true)
    expect(a.fields).toEqual([
      { id: 'sync', label: 'Sync', bits: 32 },
      { id: 'header', label: 'Header', bits: 32 },
      { id: 'payload', label: 'Payload', bits: 32 },
      { id: 'crc', label: 'CRC', bits: 16 },
    ])
    expect(a.split).toBe(true)
    expect(a.note).toBeNull()
    expect(a.fields.reduce((n, x) => n + x.bits, 0)).toBe(a.total)
  })

  it('adds a separate header when the payload does not start with it (a known system)', () => {
    const f = frame({ syncWord: '7CD215D8', lengthBits: 32 + 40 + 32, headerHex: '01 02 03 04 05', payloadHex: 'AABBCCDD' })
    const a = frameAnatomy(f)
    expect(a.headerInPayload).toBe(false)
    expect(a.fields.map((x) => [x.id, x.bits])).toEqual([
      ['sync', 32],
      ['header', 40],
      ['payload', 32],
    ])
    expect(a.split).toBe(true)
  })

  it('marks what it cannot account for as not split', () => {
    const a = frameAnatomy(frame({ lengthBits: 1024, headerHex: '00 01', payloadHex: '0001AABB' }))
    expect(a.split).toBe(false)
    expect(a.fields.at(-1)).toEqual({ id: 'unsplit', label: 'Not split', bits: 1024 - 32 - 32 })
    expect(a.note).toContain('not accounted for')
  })

  it('handles empty header and payload hex', () => {
    const a = frameAnatomy(frame({ lengthBits: 48 }))
    expect(a.fields).toEqual([
      { id: 'sync', label: 'Sync', bits: 32 },
      { id: 'crc', label: 'CRC', bits: 16 },
    ])
    expect(a.split).toBe(true)
  })

  it('does not invent a CRC on a truncated frame, and says why', () => {
    const f = frame({ crc: 'truncated', lengthBits: 32 + 24, headerHex: 'AA BB CC', payloadHex: 'AABBCC' })
    const a = frameAnatomy(f)
    expect(a.fields.map((x) => x.id)).toEqual(['sync', 'header'])
    expect(a.split).toBe(true)
    expect(a.note).toContain('CRC was never reached')
  })

  it('truncated with bits left over leaves them not split', () => {
    const a = frameAnatomy(frame({ crc: 'truncated', lengthBits: 100, payloadHex: 'AABB' }))
    expect(a.fields.at(-1)).toEqual({ id: 'unsplit', label: 'Not split', bits: 100 - 32 - 16 })
    expect(a.split).toBe(false)
  })

  it('shows only the sync word when the lengths exceed the reported length', () => {
    const a = frameAnatomy(frame({ lengthBits: 40, payloadHex: 'AABBCCDDEEFF' }))
    expect(a.split).toBe(false)
    expect(a.fields.map((x) => x.id)).toEqual(['sync', 'unsplit'])
    expect(a.note).toContain('more than the 40 bits')
  })

  it('does not split a frame whose sync word is text, not bits', () => {
    const a = frameAnatomy(frame({ syncWord: 'ZCZC', lengthBits: 700, headerHex: '5841303', payloadHex: '41' }))
    expect(a.fields).toEqual([{ id: 'unsplit', label: 'Not split', bits: 700 }])
    expect(a.note).toContain('not a bit pattern')
    expect(taggedBytes(frame({ syncWord: 'ZCZC' })).filter((b) => b.field === 'sync')).toEqual([])
  })
})

describe('a sync word written with a 0x prefix', () => {
  it('splits and tags like the bare hex', () => {
    const f = frame({ syncWord: '0x1ACFFC1D', lengthBits: 48, headerHex: '', payloadHex: '' })
    expect(frameAnatomy(f).fields[0]).toEqual({ id: 'sync', label: 'Sync', bits: 32 })
    expect(taggedBytes(f).map((b) => b.hex)).toEqual(['1A', 'CF', 'FC', '1D'])
    expect(hexBytes('0x1ACFFC1D')).toEqual(['1A', 'CF', 'FC', '1D'])
  })
})

describe('taggedBytes and defaultFrame', () => {
  it('tags sync, header and payload bytes without repeating the header', () => {
    const t = taggedBytes(frame({ headerHex: 'AA BB', payloadHex: 'AABBCC' }))
    expect(t.map((b) => `${b.field}:${b.hex}`)).toEqual(['sync:1A', 'sync:CF', 'sync:FC', 'sync:1D', 'header:AA', 'header:BB', 'payload:CC'])
  })
  it('picks the first CRC-passing frame, else the first, else null', () => {
    const fs = [frame({ index: 1, crc: 'fail' }), frame({ index: 2, crc: 'pass' }), frame({ index: 3, crc: 'pass' })]
    expect(defaultFrame(fs)?.index).toBe(2)
    expect(defaultFrame([frame({ index: 9, crc: 'fail' })])?.index).toBe(9)
    expect(defaultFrame([])).toBeNull()
  })
})
