import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Parameter } from '@/lib/evidence'
import { CaptureQualitySection } from './CaptureQualitySection'

function param(over: Partial<Parameter> & Pick<Parameter, 'id' | 'name'>): Parameter {
  return {
    value: 0,
    level: 'MEASURED',
    confidence: null,
    method: `${over.name} method`,
    evidence: [],
    alternatives: [],
    warnings: [],
    ...over,
  }
}

const CLIPPING = param({
  id: 'clipping',
  name: 'Clipping',
  value: 0.0021,
  unit: '% of components at the peak',
  evidence: ['Read all 65,536 samples; the peak component is 1.'],
  warnings: ['A plateau at the peak means the capture saturated.'],
})
const GAIN = param({
  id: 'iq_gain_imbalance',
  name: 'I/Q gain imbalance',
  value: 0.123,
  unit: 'dB (I over Q)',
  level: 'ESTIMATED',
  uncertainty: 0.02,
})
const GAPS = param({ id: 'gaps', name: 'Dropped-sample gaps', value: 3, unit: 'runs of 32+ repeated samples' })

function render(parameters: Parameter[]): string {
  return renderToStaticMarkup(createElement(CaptureQualitySection, { parameters }))
}

describe('CaptureQualitySection', () => {
  it('lists each parameter with its value, unit, level label and method', () => {
    const html = render([CLIPPING, GAIN, GAPS])
    for (const p of [CLIPPING, GAIN, GAPS]) {
      expect(html).toContain(p.name)
      expect(html).toContain(p.method)
    }
    expect(html).toContain('0.0021')
    expect(html).toContain('% of components at the peak')
    expect(html).toContain('dB (I over Q)')
    expect(html).toContain('runs of 32+ repeated samples')
  })

  it('shows the evidence level as a label, never colour alone', () => {
    const html = render([CLIPPING, GAIN])
    expect(html).toContain('Measured')
    expect(html).toContain('Estimated')
  })

  it('states an estimate with its uncertainty', () => {
    expect(render([GAIN])).toContain('± 0.02')
  })

  it('shows a warning in the open and counts it in the heading', () => {
    const html = render([CLIPPING, GAIN, GAPS])
    expect(html).toContain('A plateau at the peak means the capture saturated.')
    expect(html).toContain('1 warning')
    expect(html).not.toContain('1 warnings')
    const two = render([CLIPPING, param({ id: 'gaps', name: 'Gaps', warnings: ['Looks like a buffer overrun.'] })])
    expect(two).toContain('2 warnings')
  })

  it('shows no warning count for a clean capture', () => {
    expect(render([GAIN, GAPS])).not.toMatch(/warning/)
  })

  it('says so when nothing was measured, instead of showing an empty section', () => {
    expect(render([])).toContain('No capture-quality measurements for this recording.')
  })

  it('shows the one UNKNOWN of an empty file with its reason', () => {
    const html = render([
      param({
        id: 'capture_quality',
        name: 'Capture quality',
        value: null,
        level: 'UNKNOWN',
        evidence: ['The recording holds no samples.'],
        resolveHint: 'Open a recording that holds samples.',
      }),
    ])
    expect(html).toContain('Unknown')
    expect(html).toContain('The recording holds no samples.')
    expect(html).toContain('Open a recording that holds samples.')
  })
})
