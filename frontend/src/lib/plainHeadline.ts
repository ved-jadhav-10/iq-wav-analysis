import type { Detection } from './analysis'
import type { Parameter, StageResult } from './evidence'
import { integer } from './format'

export type HeadlineInput = Pick<Detection, 'kind' | 'level' | 'label' | 'headline' | 'stages' | 'frames' | 'search'>

const NBSP = ' '
export const PENDING_HEADLINE = 'Analysing this signal…'

/** The app's placeholder while the analysis has not reached a signal yet. */
export function isPending(d: Pick<Detection, 'label' | 'headline'>): boolean {
  return d.label === 'Signal' && d.headline === PENDING_HEADLINE
}

function param(stages: StageResult[], stage: string, id: string): Parameter | undefined {
  return stages.find((s) => s.id === stage)?.parameters.find((p) => p.id === id)
}

function modulation(d: HeadlineInput): string | null {
  const m = param(d.stages, 'classify', 'modulation')?.value
  if (typeof m === 'string' && m.trim()) return m.trim().replace(/\?$/, '')
  const label = d.label.trim().replace(/\?$/, '')
  return !label || label === 'Unknown' || label === 'Signal' ? null : label
}

/** "25 kBd" with a non-breaking space; null unless the rate is in baud (it can be per sample). */
function symbolRate(d: HeadlineInput): string | null {
  const p = param(d.stages, 'estimate', 'symbol_rate')
  if (!p || typeof p.value !== 'number' || p.unit !== 'Bd' || !(p.value > 0)) return null
  return p.value >= 1000
    ? `${Number((p.value / 1000).toPrecision(3))}${NBSP}kBd`
    : `${Number(p.value.toPrecision(3))}${NBSP}Bd`
}

/** One plain sentence for a detection, built from its structured report and never firmer than its
 * evidence level: "proven" only where a CRC (or a catalogued system's own check) passed on this
 * recording; otherwise "probably" or "possibly", and "not decoded" or "no code found" in words. */
export function plainHeadline(d: HeadlineInput): string {
  if (isPending(d)) return PENDING_HEADLINE

  const mod = modulation(d)
  const frameStage = d.stages.find((s) => s.id === 'frame')
  const fecStage = d.stages.find((s) => s.id === 'fec')
  const matchStage = d.stages.find((s) => s.id === 'match')
  const passes = d.frames.filter((f) => f.crc === 'pass').length
  const complete = d.frames.filter((f) => f.crc !== 'truncated').length
  const matched = matchStage?.level === 'VERIFIED' ? matchStage.summary.split(':')[0].trim() : null

  if (d.kind === 'analog') {
    const name = d.label.trim().replace(/\?$/, '') || 'analog'
    return d.level === 'VERIFIED' || d.level === 'MEASURED'
      ? `${name} (analog), kept out of the digital chain`
      : `Probably ${name} (analog), kept out of the digital chain`
  }

  if (d.kind === 'unknown' && /symbol rate unknown/i.test(d.headline)) {
    return 'Signal detected, but its symbol rate is unknown, so nothing was decoded'
  }

  if (d.kind === 'psk' || d.kind === 'fsk') {
    const base = mod ? `Digital ${mod} signal` : 'Digital signal'

    if (d.level === 'VERIFIED' && passes > 0) {
      if (frameStage?.level === 'VERIFIED') {
        const code = param(d.stages, 'fec', 'code')?.value
        const coded = typeof code === 'string' && code.length > 0 && !/^uncoded$/i.test(code)
        const blind = coded && /\(found blind\)/i.test(d.headline)
        const il = param(d.stages, 'deinterleave', 'interleaver')
        const undone =
          il && il.level === 'VERIFIED' && typeof il.value === 'string' && il.value.trim()
            ? il.value.replace(/\s+from bit\s+\d+\s*$/i, '').trim()
            : null
        return (
          `${base}, ${undone ? `de-interleaved (${undone}), ` : ''}${coded ? (blind ? 'error-corrected by a code it found blind, and ' : 'error-corrected and ') : ''}proven by ${integer.format(passes)} of ` +
          `${integer.format(complete)} frame ${complete === 1 ? 'checksum' : 'checksums'} (CRC)` +
          (matched ? `; matches ${matched}` : '')
        )
      }
      if (matched) {
        return (
          `${base}; matches ${matched}, whose own check passed on ${integer.format(passes)} of ` +
          `${integer.format(complete)} ${complete === 1 ? 'frame' : 'frames'}`
        )
      }
    }

    if (d.level === 'VERIFIED') return d.headline

    const firm = Boolean(mod) && !d.label.trim().endsWith('?')
    const rate = symbolRate(d)
    const hedge = d.level === 'HYPOTHESIS' || d.level === 'UNKNOWN' ? 'Possibly' : 'Probably'
    const lead = firm ? base : mod ? `${hedge} ${mod}` : base
    const head = rate ? `${lead} at about ${rate}` : lead
    const tried = d.search?.tried ?? 0
    const noCode = fecStage !== undefined && fecStage.status === 'done' && fecStage.level === 'UNKNOWN'
    return noCode && tried > 0
      ? `${head}; no error-correction code found among ${integer.format(tried)} hypotheses tried`
      : `${head}; not decoded`
  }

  if (d.level === 'UNKNOWN') return 'Nothing could be determined about this signal'
  return d.headline
}
