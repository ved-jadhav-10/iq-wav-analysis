import { useId, useMemo } from 'react'
import { useWidth } from '@/hooks/useWidth'
import type { Frame } from '@/lib/analysis'
import { fieldMap, MIN_FRAMES_FOR_FIELDS, type FieldMap as FieldMapData, type MappedField } from '@/lib/fieldmap'
import { integer } from '@/lib/format'

const BAR_H = 26
const BAND_Y = BAR_H + 4
const BAND_H = 16
/** Rows listed in the table; the strip above always shows every field. */
const MAX_ROWS = 60

const KIND_WORD: Record<MappedField['kind'], string> = { constant: 'Constant', counter: 'Counter', variable: 'Varies' }

function detail(f: MappedField): string {
  if (f.kind === 'constant') return f.value ?? ''
  if (f.kind === 'counter') return `${f.step! > 0 ? '+' : '−'}${Math.abs(f.step!)} per frame`
  return ''
}

function chance(p: number | null): string {
  if (p === null) return ''
  if (p === 0) return '< 1e−300'
  const [mantissa, exponent] = p.toExponential(0).split('e')
  return `${mantissa}e${exponent.replace('-', '−')}`
}

function describe(f: MappedField): string {
  const end = f.startBit + f.bits - 1
  return `${KIND_WORD[f.kind]}, bits ${f.startBit} to ${end}${detail(f) ? `: ${detail(f)}` : ''}`
}

function Strip({ map }: { map: FieldMapData }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const x = (bit: number) => (bit / map.columns) * width
  return (
    <div ref={ref} className="w-full min-w-0 overflow-hidden">
      <svg
        width={width}
        style={{ maxWidth: '100%' }}
        height={BAND_Y + BAND_H + 14}
        role="img"
        aria-label={`Bit-by-bit agreement across ${map.frames} frames over the first ${map.columns} bits. ${map.fields.map(describe).join('; ')}`}
        className="block"
      >
        <defs>
          <pattern id={`${uid}-ctr`} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="5" height="5" style={{ fill: 'var(--surface)' }} />
            <line x1="0" y1="0" x2="0" y2="5" strokeWidth="2" style={{ stroke: 'var(--ev-estimated)' }} />
          </pattern>
          <pattern id={`${uid}-var`} width="4" height="4" patternUnits="userSpaceOnUse">
            <rect width="4" height="4" style={{ fill: 'var(--surface)' }} />
            <circle cx="2" cy="2" r="0.8" style={{ fill: 'var(--subtle-foreground)' }} />
          </pattern>
        </defs>
        {width > 0 && (
          <>
            <line x1={0} x2={width} y1={BAR_H + 1} y2={BAR_H + 1} style={{ stroke: 'var(--plot-axis)' }} strokeWidth={1} />
            {map.agreement.map((a, c) => {
              const h = Math.max(1, (a - 0.5) * 2 * BAR_H)
              return (
                <rect key={c} x={x(c)} y={BAR_H - h} width={Math.max(0.75, x(c + 1) - x(c) - 0.25)} height={h} opacity={0.75} style={{ fill: 'var(--muted-foreground)' }} />
              )
            })}
            {map.fields.map((f, i) => {
              const left = x(f.startBit)
              const w = Math.max(1.5, x(f.startBit + f.bits) - left - 1)
              const constant = f.kind === 'constant'
              const counter = f.kind === 'counter'
              const fill = constant ? 'var(--primary)' : counter ? `url(#${uid}-ctr)` : `url(#${uid}-var)`
              const stroke = constant ? 'var(--primary)' : counter ? 'var(--ev-estimated)' : 'var(--border-strong)'
              return (
                <g key={i}>
                  <title>{describe(f)}</title>
                  <rect x={left} y={BAND_Y} width={w} height={BAND_H} rx={2} fill={fill} strokeWidth={1} strokeDasharray={f.kind === 'variable' ? '3 2' : undefined} style={{ stroke }} />
                  {w >= 40 && (
                    <text
                      x={left + w / 2}
                      y={BAND_Y + BAND_H / 2 + 3.5}
                      textAnchor="middle"
                      fontSize={10}
                      fontWeight={600}
                      strokeWidth={counter ? 3 : 0}
                      style={{ fill: constant ? 'var(--primary-foreground)' : 'var(--foreground)', paintOrder: 'stroke', stroke: counter ? 'var(--surface)' : 'none' }}
                    >
                      {constant ? 'constant' : counter ? 'counter' : 'varies'}
                    </text>
                  )}
                </g>
              )
            })}
            <g className="num" style={{ fill: 'var(--subtle-foreground)' }} fontSize={10} aria-hidden>
              <text x={0} y={BAND_Y + BAND_H + 11} textAnchor="start">
                bit 0
              </text>
              <text x={width} y={BAND_Y + BAND_H + 11} textAnchor="end">
                bit {integer.format(map.columns)}
              </text>
            </g>
          </>
        )}
      </svg>
    </div>
  )
}

function summary(map: FieldMapData): string {
  if (map.headerEnd >= map.columns) {
    return 'No compared bit varies: these frames are identical or count in these bits, so no boundary between header and payload can be seen. A longer capture, or frames with different payloads, would show it.'
  }
  if (map.headerEnd === 0) return 'The first bit already differs between frames: no fixed header.'
  if (map.headerEnd <= map.syncBits) {
    return `Only the sync word (${map.syncBits} bits) is fixed; the bits after it differ between frames, so the payload starts right after it.`
  }
  const after = map.syncBits > 0 ? `, ${integer.format(map.headerEnd - map.syncBits)} bits after the sync word` : ''
  return `The fixed part (constant and counting fields) runs to bit ${integer.format(map.headerEnd)}${after}; after it the bits vary, which is where the payload most likely begins.`
}

/** Which bits stay put from frame to frame and which count: where the fixed header ends and the
 * payload begins, found by correlating the frames' bits. Recomputed from the frame table, and an
 * analyst's tool: a field here is a place to look, never evidence. */
export function FieldMap({ frames }: { frames: Frame[] }) {
  const map = useMemo(() => fieldMap(frames), [frames])
  const shown = map.fields.slice(0, MAX_ROWS)
  return (
    <section aria-labelledby="bs-fields-title" className="min-w-0">
      <h3 id="bs-fields-title" className="eyebrow mb-1">
        Header and payload by correlation
      </h3>
      {!map.enough ? (
        <p className="text-xs text-muted-foreground">
          Comparing frames bit by bit needs at least {MIN_FRAMES_FOR_FIELDS} frames: a few frames agree on a bit by chance. This detection lists{' '}
          <span className="num text-foreground">{map.of}</span>. A longer capture would settle it.
        </p>
      ) : (
        <>
          <p className="text-xs">
            First <span className="num font-medium">{integer.format(map.columns)}</span> bits of <span className="num font-medium">{integer.format(map.frames)}</span> frames
            {map.passingOnly ? ' that pass their CRC' : ' (too few pass their CRC, so all are used)'}. {summary(map)}
          </p>
          <div className="mt-1.5">
            <Strip map={map} />
            <p className="text-2xs text-subtle-foreground">
              Bars: the share of frames that agree on each bit (full height: all of them). Band: solid is constant, hatched counts up or down, dotted varies.
            </p>
          </div>
          <div tabIndex={0} role="region" aria-label="Fields found" className="mt-1.5 max-h-32 overflow-auto rounded-md bg-surface-2">
            <table className="num w-full text-left text-2xs">
              <thead className="sticky top-0 bg-surface-2 text-muted-foreground">
                <tr>
                  <th className="px-2 py-1 font-medium">Bits</th>
                  <th className="px-2 py-1 font-medium">Width</th>
                  <th className="px-2 py-1 font-medium">Kind</th>
                  <th className="px-2 py-1 font-medium">Value</th>
                  <th className="px-2 py-1 font-medium" title="Probability of this pattern in random bits, corrected for the places it was looked for">
                    Chance
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((f, i) => (
                  <tr key={i} className="border-t border-border/60">
                    <td className="px-2 py-0.5">
                      {integer.format(f.startBit)}–{integer.format(f.startBit + f.bits - 1)}
                    </td>
                    <td className="px-2 py-0.5">{f.bits}</td>
                    <td className="px-2 py-0.5">{KIND_WORD[f.kind]}</td>
                    <td className="px-2 py-0.5 break-all">{detail(f)}</td>
                    <td className="px-2 py-0.5">{chance(f.p)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {map.fields.length > shown.length && (
              <p className="px-2 py-1 text-subtle-foreground">… and {integer.format(map.fields.length - shown.length)} more fields not shown</p>
            )}
          </div>
        </>
      )}
      <p className="mt-1 text-2xs text-subtle-foreground">
        Recomputed from the frames listed here. Constants are found at any bit, counters in whole bytes only. A field is a place to look, not proof of a header; the
        chance is that of the same pattern in random bits.
      </p>
    </section>
  )
}
