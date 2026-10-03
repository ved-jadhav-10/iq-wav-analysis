import { useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useWidth } from '@/hooks/useWidth'
import type { Detection, Frame } from '@/lib/analysis'
import {
  bytesToBits,
  defaultFrame,
  findPattern,
  frameAnatomy,
  hitBytes,
  parsePattern,
  recurrence,
  streamExtent,
  taggedBytes,
  type Anatomy,
  type Field,
  type Recurrence,
  type TaggedByte,
} from '@/lib/bitstream'
import { hexToText, integer } from '@/lib/format'
import { EvidenceBadge } from './EvidenceBadge'
import { FieldMap } from './FieldMap'
import { InfoTip } from './InfoTip'

const CRC_WORD: Record<Frame['crc'], string> = { pass: 'passes its CRC', fail: 'fails its CRC', truncated: 'is truncated by the end of the burst' }
const CRC_COLOR: Record<Frame['crc'], string> = { pass: 'var(--ev-verified)', fail: 'var(--danger)', truncated: 'var(--ev-unknown)' }

function frameLabel(f: Frame): string {
  return `Frame ${f.index}, start bit ${integer.format(f.startBit)}, ${integer.format(f.lengthBits)} bits, ${CRC_WORD[f.crc]}`
}

/** The glyph for a CRC outcome, drawn at (cx, cy): a check, a cross or a slash, haloed so it reads on
 * the solid, hatched or dashed segment under it. */
function Glyph({ crc, cx, cy }: { crc: Frame['crc']; cx: number; cy: number }) {
  const d = crc === 'pass' ? 'M-3 0 L-1 2.5 L3.5 -2.5' : crc === 'fail' ? 'M-3 -3 L3 3 M3 -3 L-3 3' : 'M-3 3 L3 -3'
  return (
    <g transform={`translate(${cx} ${cy})`} fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {crc !== 'pass' && <path d={d} style={{ stroke: 'var(--surface)' }} strokeWidth={4.5} />}
      <path d={d} style={{ stroke: crc === 'pass' ? 'var(--surface)' : CRC_COLOR[crc] }} strokeWidth={1.75} />
    </g>
  )
}

const AXIS_H = 14
const SEG_Y = 4
const SEG_H = 22

function Timeline({ frames, selected, onSelect }: { frames: Frame[]; selected: number; onSelect: (index: number) => void }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const extent = streamExtent(frames)
  const refs = useRef<Map<number, SVGGElement>>(new Map())
  if (!extent) return null
  const { min, span } = extent
  const x = (bit: number) => ((bit - min) / span) * width

  function onKeyDown(e: KeyboardEvent<SVGSVGElement>) {
    const i = frames.findIndex((f) => f.index === selected)
    let next: number
    if (e.key === 'ArrowRight') next = Math.min(frames.length - 1, i + 1)
    else if (e.key === 'ArrowLeft') next = Math.max(0, i - 1)
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = frames.length - 1
    else return
    e.preventDefault()
    const target = frames[next]
    onSelect(target.index)
    refs.current.get(target.index)?.focus()
  }

  return (
    <div ref={ref} className="w-full min-w-0 overflow-hidden">
      <svg
        width={width}
        style={{ maxWidth: '100%' }}
        height={SEG_Y + SEG_H + AXIS_H + 10}
        role="listbox"
        aria-label={`Frames along the bit stream, ${frames.length} in all. Arrow keys move between frames.`}
        onKeyDown={onKeyDown}
        className="block"
      >
        <defs>
          <pattern id={`${uid}-hatch`} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="5" height="5" style={{ fill: 'var(--surface)' }} />
            <line x1="0" y1="0" x2="0" y2="5" strokeWidth="2" style={{ stroke: 'var(--danger)' }} />
          </pattern>
          <pattern id={`${uid}-slash`} width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
            <rect width="9" height="9" style={{ fill: 'var(--surface)' }} />
            <line x1="0" y1="0" x2="0" y2="9" strokeWidth="1" style={{ stroke: 'var(--ev-unknown)' }} />
          </pattern>
        </defs>
        <line x1={0} x2={width} y1={SEG_Y + SEG_H + 2} y2={SEG_Y + SEG_H + 2} style={{ stroke: 'var(--plot-axis)' }} strokeWidth={1} />
        {width > 0 &&
          frames.map((f) => {
            const left = x(f.startBit)
            const w = Math.max(1.5, x(f.startBit + f.lengthBits) - left - 0.75)
            const isSel = f.index === selected
            const fill = f.crc === 'pass' ? 'var(--ev-verified)' : f.crc === 'fail' ? `url(#${uid}-hatch)` : `url(#${uid}-slash)`
            return (
              <g
                key={f.index}
                ref={(el) => {
                  if (el) refs.current.set(f.index, el)
                  else refs.current.delete(f.index)
                }}
                role="option"
                aria-selected={isSel}
                aria-label={frameLabel(f)}
                tabIndex={isSel ? 0 : -1}
                onClick={() => onSelect(f.index)}
                onFocus={() => onSelect(f.index)}
                className="cursor-pointer outline-none [&:focus-visible>rect]:stroke-[3]"
              >
                <title>{frameLabel(f)}</title>
                <rect
                  x={left}
                  y={SEG_Y}
                  width={w}
                  height={SEG_H}
                  rx={1.5}
                  fill={fill}
                  strokeWidth={isSel ? 2 : 1}
                  strokeDasharray={f.crc === 'truncated' ? '3 2' : undefined}
                  style={{ stroke: isSel ? 'var(--foreground)' : CRC_COLOR[f.crc] }}
                />
                {w >= 14 && <Glyph crc={f.crc} cx={left + w / 2} cy={SEG_Y + SEG_H / 2} />}
                {isSel && (
                  <path
                    d={`M${left + w / 2 - 4} ${SEG_Y + SEG_H + 9} L${left + w / 2 + 4} ${SEG_Y + SEG_H + 9} L${left + w / 2} ${SEG_Y + SEG_H + 4} Z`}
                    style={{ fill: 'var(--foreground)' }}
                    aria-hidden
                  />
                )}
              </g>
            )
          })}
        {width > 0 && (
          <g className="num" style={{ fill: 'var(--subtle-foreground)' }} fontSize={10} aria-hidden>
            <text x={0} y={SEG_Y + SEG_H + AXIS_H + 8} textAnchor="start">
              bit {integer.format(extent.min)}
            </text>
            <text x={width} y={SEG_Y + SEG_H + AXIS_H + 8} textAnchor="end">
              bit {integer.format(extent.max)}
            </text>
          </g>
        )}
      </svg>
    </div>
  )
}

function Legend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-muted-foreground" aria-label="Legend: CRC outcome of each segment">
      <li className="flex items-center gap-1.5">
        <svg width="14" height="12" aria-hidden>
          <rect x="0.5" y="0.5" width="13" height="11" rx="1.5" style={{ fill: 'var(--ev-verified)', stroke: 'var(--ev-verified)' }} />
          <Glyph crc="pass" cx={7} cy={6} />
        </svg>
        Solid with a check: CRC passes
      </li>
      <li className="flex items-center gap-1.5">
        <svg width="14" height="12" aria-hidden>
          <defs>
            <pattern id="legend-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="5" style={{ fill: 'var(--surface)' }} />
              <line x1="0" y1="0" x2="0" y2="5" strokeWidth="2" style={{ stroke: 'var(--danger)' }} />
            </pattern>
          </defs>
          <rect x="0.5" y="0.5" width="13" height="11" rx="1.5" fill="url(#legend-hatch)" style={{ stroke: 'var(--danger)' }} />
          <Glyph crc="fail" cx={7} cy={6} />
        </svg>
        Hatched with a cross: CRC fails
      </li>
      <li className="flex items-center gap-1.5">
        <svg width="14" height="12" aria-hidden>
          <rect x="0.5" y="0.5" width="13" height="11" rx="1.5" strokeDasharray="3 2" style={{ fill: 'var(--surface)', stroke: 'var(--ev-unknown)' }} />
          <Glyph crc="truncated" cx={7} cy={6} />
        </svg>
        Dashed with a slash: truncated, no CRC reached
      </li>
    </ul>
  )
}

function GapPlot({ r }: { r: Recurrence }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const height = 56
  const padX = 6
  const padY = 8
  if (r.gaps.length === 0 || r.period === null) return null
  const yMax = Math.max(r.period * 2, ...r.gaps) * 1.05
  const px = (i: number) => padX + (r.gaps.length === 1 ? (width - 2 * padX) / 2 : (i / (r.gaps.length - 1)) * (width - 2 * padX))
  const py = (g: number) => height - padY - (g / yMax) * (height - 2 * padY)
  const dot = r.gaps.length > 120 ? 1.5 : 2.5
  return (
    <div ref={ref} className="w-full min-w-0 overflow-hidden">
      <svg
        width={width}
        style={{ maxWidth: '100%' }}
        height={height}
        role="img"
        aria-label={`Gap between consecutive frames, ${r.gaps.length} gaps against a period of ${integer.format(r.period)} bits: ${r.matching} on the period, ${r.gaps.length - r.matching} off it`}
        className="block"
      >
        {width > 0 && (
          <>
            <line x1={padX} x2={width - padX} y1={py(r.period)} y2={py(r.period)} strokeDasharray="4 3" strokeWidth={1} style={{ stroke: 'var(--plot-axis)' }} />
            {r.gaps.map((g, i) => {
              const on = g === r.period
              return on ? (
                <g key={i}>
                  <line x1={px(i)} x2={px(i)} y1={py(r.period as number)} y2={py(g)} strokeWidth={1} style={{ stroke: 'var(--ev-verified)' }} />
                  <circle cx={px(i)} cy={py(g)} r={dot} style={{ fill: 'var(--ev-verified)' }} />
                </g>
              ) : (
                <g key={i}>
                  <line x1={px(i)} x2={px(i)} y1={py(r.period as number)} y2={py(g)} strokeWidth={1} style={{ stroke: 'var(--danger)' }} />
                  <rect
                    x={px(i) - dot - 0.5}
                    y={py(g) - dot - 0.5}
                    width={2 * dot + 1}
                    height={2 * dot + 1}
                    transform={`rotate(45 ${px(i)} ${py(g)})`}
                    strokeWidth={1.25}
                    style={{ fill: 'var(--surface)', stroke: 'var(--danger)' }}
                  />
                </g>
              )
            })}
            <text x={width - padX} y={9} textAnchor="end" fontSize={10} className="num" style={{ fill: 'var(--subtle-foreground)' }}>
              dashed: period {integer.format(r.period)} bits
            </text>
          </>
        )}
      </svg>
    </div>
  )
}

function Recurrences({ r, frameStage }: { r: Recurrence; frameStage: Detection['stages'][number] | undefined }) {
  const word = r.syncWord ?? 'unknown'
  const off = r.gaps.length - r.matching
  return (
    <section aria-labelledby="bs-recur-title" className="min-w-0">
      <h3 id="bs-recur-title" className="eyebrow mb-1 flex items-center gap-1">
        Sync-word recurrence <InfoTip term="asm" />
      </h3>
      {!r.enough || r.period === null ? (
        <p className="text-xs text-muted-foreground">
          <span className="num text-foreground">{r.frames}</span> frame{r.frames === 1 ? '' : 's'} found
          {r.frames > 0 && (
            <>
              {' '}
              with sync <span className="num text-foreground">{word}</span>
            </>
          )}
          : too few to say whether the sync word recurs at a fixed spacing. Three frames (two gaps) are the least that can repeat; a longer capture
          would settle it.
        </p>
      ) : (
        <>
          <p className="text-xs">
            <span className="num font-medium">{integer.format(r.frames)}</span> frames, sync <span className="num font-medium">{word}</span> recurs
            every <span className="num font-medium">{integer.format(r.period)}</span> bits (
            <span className="num font-medium">
              {integer.format(r.matching)} of {integer.format(r.gaps.length)}
            </span>{' '}
            gaps)
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {r.periodic
              ? 'Every gap equals the period, so the stream is periodic.'
              : `${integer.format(off)} gap${off === 1 ? '' : 's'} differ${off === 1 ? 's' : ''} from the period (a missed or extra sync-word hit), shown as hollow diamonds.`}
          </p>
          <div className="mt-1.5">
            <GapPlot r={r} />
            <p className="text-2xs text-subtle-foreground">
              Gap between consecutive frames, in bits: filled circle on the period, hollow diamond off it. A periodic stream is a flat line.
            </p>
          </div>
        </>
      )}
      <p className="mt-1.5 text-2xs text-muted-foreground">
        The same sync word recurring at a fixed period is what makes a sync word verified: it is one of the three proofs, with a CRC pass and a
        re-encode match. This view recomputes it from the frames listed here.
        {frameStage && (
          <>
            {' '}
            The engine&rsquo;s verdict on the Frame stage:{' '}
            <span className="inline-flex align-middle">
              <EvidenceBadge level={frameStage.level ?? 'UNKNOWN'} />
            </span>
          </>
        )}
      </p>
    </section>
  )
}

const FIELD_FILL: Record<Field['id'], string> = {
  sync: 'bg-primary text-primary-foreground',
  header: 'bg-ev-estimated text-surface',
  payload: 'bg-foreground/70 text-surface',
  crc: 'bg-ev-hypothesis text-surface',
  unsplit: 'border border-dashed border-border-strong bg-transparent text-muted-foreground',
}

const FIELD_SWATCH: Record<Field['id'], string> = {
  sync: 'bg-primary',
  header: 'bg-ev-estimated',
  payload: 'bg-foreground/70',
  crc: 'bg-ev-hypothesis',
  unsplit: 'border border-dashed border-border-strong',
}

const BYTE_STYLE: Record<TaggedByte['field'], string> = {
  sync: 'font-semibold text-primary',
  header: 'text-ev-estimated underline decoration-dotted underline-offset-2',
  payload: 'text-foreground',
}

const BYTES_PER_LINE = 16
const MAX_BYTES = 512

function AnatomyBar({ a }: { a: Anatomy }) {
  return (
    <>
      <div
        role="img"
        aria-label={`Frame of ${a.total} bits: ${a.fields.map((f) => `${f.label} ${f.bits} bits`).join(', ')}`}
        className="flex h-6 w-full overflow-hidden rounded-md"
      >
        {a.fields.map((f, i) => (
          <div
            key={`${f.id}-${i}`}
            title={`${f.label}: ${integer.format(f.bits)} bits`}
            style={{ flexGrow: f.bits, flexBasis: 0, minWidth: 2 }}
            className={`flex items-center justify-center overflow-hidden px-1 text-2xs font-medium whitespace-nowrap ${FIELD_FILL[f.id]}`}
          >
            <span className="truncate">{f.label}</span>
          </div>
        ))}
      </div>
      <ul className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-2xs text-muted-foreground" aria-label="Frame fields">
        {a.fields.map((f, i) => (
          <li key={`${f.id}-${i}`} className="flex items-center gap-1.5">
            <span className={`inline-block size-2.5 rounded-[2px] ${FIELD_SWATCH[f.id]}`} aria-hidden />
            {f.label} <span className="num text-foreground">{integer.format(f.bits)}</span> bits
          </li>
        ))}
      </ul>
      {a.note && <p className="mt-1 text-xs text-muted-foreground">{a.note}</p>}
    </>
  )
}

type ByteView = 'hex' | 'bits'

function ByteGrid({ bytes, view, hits }: { bytes: TaggedByte[]; view: ByteView; hits: ReadonlySet<number> }) {
  if (bytes.length === 0) {
    return <p className="text-xs text-muted-foreground">This frame lists no bytes to show (its header and payload are empty).</p>
  }
  const perLine = view === 'bits' ? 8 : BYTES_PER_LINE
  const shown = bytes.slice(0, MAX_BYTES)
  const lines: { byte: TaggedByte; at: number }[][] = []
  for (let i = 0; i < shown.length; i += perLine) lines.push(shown.slice(i, i + perLine).map((byte, k) => ({ byte, at: i + k })))
  const mark = (at: number) => (hits.has(at) ? ' rounded-[2px] bg-primary/25 ring-1 ring-primary' : '')
  return (
    <div tabIndex={0} role="region" aria-label="Frame bytes" className="num max-h-32 overflow-auto rounded-md bg-surface-2 px-2 py-1.5 text-xs leading-5">
      {lines.map((line, li) => (
        <div key={li} className="flex gap-3 whitespace-nowrap">
          <span className="w-[4ch] shrink-0 text-right text-subtle-foreground" aria-hidden>
            {(li * perLine).toString(16).toUpperCase().padStart(4, '0')}
          </span>
          <span>
            {line.map(({ byte: b, at }) => (
              <span key={at} className={`${BYTE_STYLE[b.field]} mr-[1ch]${mark(at)}`}>
                {view === 'bits' ? bytesToBits([b.hex]) : b.hex}
              </span>
            ))}
          </span>
          <span className="text-muted-foreground" aria-label={`As text: ${hexToText(line.map(({ byte }) => byte.hex).join(''))}`}>
            {line.map(({ byte: b, at }) => (
              <span key={at} className={`${BYTE_STYLE[b.field]}${mark(at)}`}>
                {hexToText(b.hex)}
              </span>
            ))}
          </span>
        </div>
      ))}
      {bytes.length > shown.length && (
        <p className="mt-1 text-subtle-foreground">… and {integer.format(bytes.length - shown.length)} more bytes not shown</p>
      )}
    </div>
  )
}

function FrameAnatomy({
  frames,
  frame,
  onSelect,
  offsets,
  patternBits,
}: {
  frames: Frame[]
  frame: Frame
  onSelect: (index: number) => void
  offsets: readonly number[]
  patternBits: number
}) {
  const [view, setView] = useState<ByteView>('hex')
  const a = useMemo(() => frameAnatomy(frame), [frame])
  const bytes = useMemo(() => taggedBytes(frame), [frame])
  const hits = useMemo(() => hitBytes(offsets, patternBits), [offsets, patternBits])
  const selectId = useId()
  return (
    <section aria-labelledby="bs-anatomy-title" className="min-w-0">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h3 id="bs-anatomy-title" className="eyebrow">
          Frame anatomy
        </h3>
        <label htmlFor={selectId} className="flex items-center gap-1.5 text-2xs text-muted-foreground">
          Frame
          <select
            id={selectId}
            value={frame.index}
            onChange={(e) => onSelect(Number(e.target.value))}
            className="num max-w-[22ch] rounded-md border border-border-strong bg-surface px-1 py-0.5 text-2xs text-foreground"
          >
            {frames.map((f) => (
              <option key={f.index} value={f.index}>
                #{f.index} · bit {integer.format(f.startBit)} · CRC {f.crc}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="mb-1.5 text-xs text-muted-foreground">
        Frame <span className="num text-foreground">#{frame.index}</span>, start bit{' '}
        <span className="num text-foreground">{integer.format(frame.startBit)}</span>, {frame.crc === 'pass' ? 'CRC passes' : frame.crc === 'fail' ? 'CRC fails' : 'truncated before its CRC'}.
      </p>
      <AnatomyBar a={a} />
      <div className="mt-2">
        <div className="mb-1 flex items-center gap-1 text-2xs" role="group" aria-label="Show the bytes as">
          {(['hex', 'bits'] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className={`rounded-[3px] border px-1.5 py-0.5 font-medium ${view === v ? 'border-primary bg-primary/10 text-foreground' : 'border-border-strong text-muted-foreground hover:text-foreground'}`}
            >
              {v === 'hex' ? 'Hex' : 'Bits'}
            </button>
          ))}
        </div>
        <ByteGrid bytes={bytes} view={view} hits={hits} />
      </div>
      <p className="mt-1 text-2xs text-subtle-foreground">
        Bytes are coloured and marked by field: <span className="font-semibold text-primary">sync</span> in bold,{' '}
        <span className="text-ev-estimated underline decoration-dotted underline-offset-2">header</span> dotted-underlined, payload plain. Right:
        printable ASCII, a dot for anything else.
      </p>
    </section>
  )
}

/** Look for a bit pattern across every listed frame: the analyst's own search, so a hit is a place to
 * look and never evidence by itself. */
function PatternSearch({
  frames,
  text,
  onText,
  onPick,
  selected,
}: {
  frames: Frame[]
  text: string
  onText: (t: string) => void
  onPick: (index: number) => void
  selected: number
}) {
  const inputId = useId()
  const pattern = useMemo(() => parsePattern(text), [text])
  const found = useMemo(() => (pattern ? findPattern(frames, pattern) : []), [frames, pattern])
  const total = found.reduce((n, h) => n + h.offsets.length, 0)
  return (
    <section aria-labelledby="bs-find-title" className="relative min-w-0">
      <h3 id="bs-find-title" className="eyebrow mb-1">
        Find a pattern
      </h3>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={inputId} className="sr-only">
          Pattern to search for, as hex bytes or bits with a 0b prefix
        </label>
        <input
          id={inputId}
          value={text}
          onChange={(e) => onText(e.target.value)}
          spellCheck={false}
          autoComplete="off"
          placeholder="1A CF FC 1D, or 0b10110"
          aria-invalid={text.trim() !== '' && !pattern}
          className="num w-56 max-w-full rounded-md border border-border-strong bg-surface px-2 py-1 text-xs"
        />
        <p role="status" className="text-xs text-muted-foreground">
          {text.trim() === '' ? (
            'Search every listed frame, at any bit offset.'
          ) : !pattern ? (
            'Not a pattern: write whole hex bytes (1A CF), or bits after 0b (0b1010).'
          ) : found.length === 0 ? (
            <>No match in {integer.format(frames.length)} frames.</>
          ) : (
            <>
              <span className="num text-foreground">{integer.format(total)}</span> hit{total === 1 ? '' : 's'} in{' '}
              <span className="num text-foreground">{integer.format(found.length)}</span> of {integer.format(frames.length)} frames.
            </>
          )}
        </p>
      </div>
      {found.length > 0 && (
        <ul className="mt-1.5 flex max-h-16 flex-wrap gap-1 overflow-auto" aria-label="Frames with a hit">
          {found.map(({ frame, offsets }) => (
            <li key={frame.index}>
              <button
                type="button"
                onClick={() => onPick(frame.index)}
                aria-pressed={frame.index === selected}
                title={`Frame ${frame.index}: ${offsets.length} hit${offsets.length === 1 ? '' : 's'} at bit ${offsets.join(', ')}`}
                className={`num rounded-[3px] border px-1.5 py-px text-2xs ${frame.index === selected ? 'border-primary bg-primary/10 text-foreground' : 'border-border-strong text-muted-foreground hover:text-foreground'}`}
              >
                #{frame.index}
                {offsets.length > 1 ? ` ×${offsets.length}` : ''}
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-1 text-2xs text-subtle-foreground">
        Searches the sync word, header and payload bytes as listed (not the CRC). A match shows where a pattern sits; it proves nothing on its own.
      </p>
    </section>
  )
}

/** How the frames sit in the bit stream and how the sync word recurs, from `detection.frames` alone. */
export function BitstreamView({ detection }: { detection: Detection }) {
  const frames = detection.frames
  const [picked, setPicked] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const recur = useMemo(() => recurrence(frames), [frames])

  if (frames.length === 0) {
    return (
      <div className="px-3 py-5 text-center text-xs text-muted-foreground">
        <p>
          No frames to lay out.{' '}
          {detection.noFramesReason ?? 'The frame search did not run for this detection.'}
        </p>
        <p className="mt-1 text-subtle-foreground">
          A frame needs a sync word that recurs at a fixed spacing: a longer or cleaner capture, in which the same word repeats, would settle it.
        </p>
      </div>
    )
  }

  const current = frames.find((f) => f.index === picked) ?? defaultFrame(frames)
  const frameStage = detection.stages.find((s) => s.id === 'frame')
  const pattern = parsePattern(query)
  const here = pattern && current ? (findPattern([current], pattern)[0]?.offsets ?? []) : []
  return (
    <div className="@container space-y-3 px-3 py-2.5">
      <section aria-labelledby="bs-timeline-title">
        <h3 id="bs-timeline-title" className="eyebrow mb-1">
          Frames along the stream
        </h3>
        <Timeline frames={frames} selected={current?.index ?? -1} onSelect={setPicked} />
        <Legend />
      </section>
      <div className="grid grid-cols-1 gap-x-6 gap-y-3 @2xl:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
        <Recurrences r={recur} frameStage={frameStage} />
        {current && (
          <FrameAnatomy frames={frames} frame={current} onSelect={setPicked} offsets={here} patternBits={pattern?.bits.length ?? 0} />
        )}
      </div>
      <FieldMap frames={frames} />
      <PatternSearch frames={frames} text={query} onText={setQuery} onPick={setPicked} selected={current?.index ?? -1} />
    </div>
  )
}
