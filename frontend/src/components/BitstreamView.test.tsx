import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Detection, Frame } from '@/lib/analysis'
import { BitstreamView } from './BitstreamView'

function detection(frames: Frame[], noFramesReason: string | null = null): Detection {
  return {
    id: 1,
    boxes: [],
    label: 'QPSK',
    kind: 'psk',
    level: 'VERIFIED',
    headline: '',
    stages: [],
    search: null,
    noSearchReason: null,
    frames,
    noFramesReason,
    constellation: [],
  }
}

function frames(n: number): Frame[] {
  return Array.from({ length: n }, (_, i) => ({
    index: i + 1,
    startBit: 100 + i * 1024,
    syncWord: '1ACFFC1D',
    lengthBits: 1024,
    crc: 'pass' as const,
    headerHex: '48 45 4C 4C',
    payloadHex: '48454C4C4F20574F524C44',
  }))
}

function render(d: Detection): string {
  return renderToStaticMarkup(createElement(BitstreamView, { detection: d }))
}

describe('BitstreamView', () => {
  it('states the recurrence in words, with the proof explained', () => {
    const html = render(detection(frames(45)))
    expect(html).toContain('recurs')
    expect(html).toContain('1ACFFC1D')
    expect(html).toContain('1,024')
    expect(html).toContain('44 of 44')
    expect(html).toContain('one of the three proofs')
    expect(html).toContain('Frame anatomy')
  })

  it('says there are too few frames from two', () => {
    const html = render(detection(frames(2)))
    expect(html).toContain('too few to say')
    expect(html).not.toContain('recurs every')
  })

  it('reads the default frame as text and splits it into fields', () => {
    const html = render(detection(frames(3)))
    expect(html).toContain('HELLO WORLD'.slice(0, 4))
    expect(html).toContain('Sync')
    expect(html).toContain('Header')
    expect(html).toContain('Payload')
  })

  it('maps the fixed fields and the counter by correlation across frames', () => {
    // A constant header (AB CD), a counter byte, then payload bytes that differ from frame to frame.
    const mixed = (i: number, k: number) => {
      let h = Math.imul(i * 8 + k + 1, 0x9e3779b1)
      h ^= h >>> 15
      h = Math.imul(h, 0x85ebca6b)
      h ^= h >>> 13
      return (h & 0xff).toString(16).padStart(2, '0')
    }
    const counted = frames(20).map((f, i) => ({
      ...f,
      headerHex: '',
      payloadHex: `ABCD${i.toString(16).padStart(2, '0')}${[0, 1, 2, 3, 4, 5].map((k) => mixed(i, k)).join('')}`,
    }))
    const html = render(detection(counted))
    expect(html).toContain('Header and payload by correlation')
    expect(html).toContain('Counter')
    expect(html).toContain('+1 per frame')
    expect(html).toContain('1A CF FC 1D AB CD')
    expect(html).toContain('runs to bit 56, 24 bits after the sync word')
  })

  it('says when no compared bit varies, so no payload boundary can be seen', () => {
    const html = render(detection(frames(20)))
    expect(html).toContain('No compared bit varies')
    expect(html).not.toContain('where the payload most likely begins')
  })

  it('does not map fields from too few frames, and says how many it needs', () => {
    const html = render(detection(frames(5)))
    expect(html).toContain('needs at least 8 frames')
    expect(html).not.toContain('Fields found')
  })

  it('gives the reason and what would settle it when there are no frames', () => {
    const html = render(detection([], 'No sync word recurs in the 4,096 bits demodulated.'))
    expect(html).toContain('No frames to lay out')
    expect(html).toContain('No sync word recurs in the 4,096 bits demodulated.')
    expect(html).toContain('would settle it')
  })
})
