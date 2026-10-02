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

  it('gives the reason and what would settle it when there are no frames', () => {
    const html = render(detection([], 'No sync word recurs in the 4,096 bits demodulated.'))
    expect(html).toContain('No frames to lay out')
    expect(html).toContain('No sync word recurs in the 4,096 bits demodulated.')
    expect(html).toContain('would settle it')
  })
})
