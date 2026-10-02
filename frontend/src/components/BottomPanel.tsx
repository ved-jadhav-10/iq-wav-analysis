import { useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { CircleSlash, ShieldCheck, X } from 'lucide-react'
import type { Detection } from '@/lib/analysis'
import { hexToText, integer, sci } from '@/lib/format'
import { InfoTip } from './InfoTip'

const TABS = [
  { id: 'hypotheses', label: 'Hypotheses' },
  { id: 'frames', label: 'Frames' },
  { id: 'assumptions', label: 'Assumptions' },
] as const
type TabId = (typeof TABS)[number]['id']

const TH = 'sticky top-0 z-10 bg-surface px-3 py-1.5 text-left text-2xs font-semibold tracking-wide text-subtle-foreground uppercase'
const TD = 'px-3 py-1.5 align-top'

function Empty({ children }: { children: string }) {
  return <p className="px-3 py-6 text-center text-xs text-muted-foreground">{children}</p>
}

function Stat({ label, value, note, tip }: { label: string; value: string; note?: string; tip?: string }) {
  return (
    <div className="min-w-0">
      <div className="eyebrow flex items-center gap-1">
        {label}
        {tip && <InfoTip term={tip} />}
      </div>
      <div className="num text-[13px] font-medium">{value}</div>
      {note && <div className="text-2xs text-muted-foreground">{note}</div>}
    </div>
  )
}

function Hypotheses({ detection }: { detection: Detection }) {
  const s = detection.search
  if (!s) return <Empty>{detection.noSearchReason ?? 'No search ran.'}</Empty>
  const accepted = s.rows.filter((r) => r.outcome === 'accepted' && r.layer !== 'Match').length
  const systems = s.rows.filter((r) => r.outcome === 'accepted' && r.layer === 'Match').length
  return (
    <div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 border-b px-3 py-2 sm:grid-cols-5">
        <Stat
          label="Tried"
          tip="ledger"
          value={integer.format(s.tried)}
          note={
            s.blindSearched
              ? `blind code search named a code on ${s.blindIdentified ?? 0} of ${s.blindSearched} branches`
              : 'every candidate counted'
          }
        />
        <Stat label="Family-wise error" tip="fwer" value={`α = ${s.alpha}`} note={`${s.correction} step-down`} />
        <Stat label="Strictest threshold" tip="threshold" value={sci(s.smallestThreshold)} />
        <Stat
          label="Shuffled-bit accepts"
          tip="shuffled"
          value={s.shuffledRuns === 0 ? 'Not run' : `${s.shuffledAccepts} / ${integer.format(s.shuffledRuns)}`}
          note={
            s.shuffledRuns === 0
              ? 'nothing accepted to re-test'
              : s.shuffledAccepts === 0
                ? `95 % upper bound ${sci(3 / s.shuffledRuns)}`
                : undefined
          }
        />
        <Stat
          label="Accepted"
          value={String(accepted)}
          note={
            systems > 0
              ? `plus ${systems} known system${systems > 1 ? 's' : ''} from ${s.matchTried ?? 0} Match checks`
              : accepted === 0
                ? 'nothing claimed'
                : undefined
          }
        />
      </div>
      <table className="w-full text-xs">
        <caption className="sr-only">
          Top {s.rows.length} of {s.tried} hypotheses, with corrected thresholds and outcomes
        </caption>
        <thead>
          <tr className="border-b">
            <th className={TH}>Outcome</th>
            <th className={TH}>Layer</th>
            <th className={TH}>Candidate</th>
            <th className={`${TH} max-lg:hidden`}>Statistic</th>
            <th className={`${TH} text-right`}>
              <span className="inline-flex items-center justify-end gap-1">
                p <InfoTip term="pvalue" />
              </span>
            </th>
            <th className={`${TH} text-right`}>
              <span className="inline-flex items-center justify-end gap-1">
                Threshold <InfoTip term="threshold" />
              </span>
            </th>
            <th className={TH}>Why</th>
          </tr>
        </thead>
        <tbody>
          {s.rows.map((r) => (
            <tr key={r.candidate} className="border-b border-border/60 hover:bg-surface-2/50">
              <td className={TD}>
                {r.outcome === 'accepted' ? (
                  <span className="inline-flex items-center gap-1 font-medium text-ev-verified">
                    <ShieldCheck className="size-3.5" aria-hidden /> Accepted
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-muted-foreground">
                    <X className="size-3.5" aria-hidden /> Rejected
                  </span>
                )}
              </td>
              <td className={`${TD} text-muted-foreground`}>{r.layer}</td>
              <td className={`${TD} num whitespace-nowrap`}>{r.candidate}</td>
              <td className={`${TD} text-muted-foreground max-lg:hidden`}>{r.statistic}</td>
              <td className={`${TD} num text-right whitespace-nowrap`}>{r.pValue === null ? '—' : sci(r.pValue)}</td>
              <td className={`${TD} num text-right whitespace-nowrap text-muted-foreground`}>{sci(r.threshold)}</td>
              <td className={`${TD} text-muted-foreground`}>{r.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 py-2 text-2xs text-subtle-foreground">
        Showing the {s.rows.length} highest-ranked of {integer.format(s.tried)} hypotheses. Thresholds follow the {s.correction}{' '}
        step-down order, so each row is tested against α divided by the hypotheses still in play.
      </p>
    </div>
  )
}

function CrcBadge({ crc }: { crc: 'pass' | 'fail' | 'truncated' }) {
  if (crc === 'pass') {
    return (
      <span className="inline-flex items-center gap-1 text-ev-verified">
        <ShieldCheck className="size-3.5" aria-hidden /> Pass
      </span>
    )
  }
  if (crc === 'fail') {
    return (
      <span className="inline-flex items-center gap-1 text-muted-foreground">
        <X className="size-3.5" aria-hidden /> Fail
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-ev-unknown">
      <CircleSlash className="size-3.5" aria-hidden /> Truncated
    </span>
  )
}

const EXPORTS = [
  { format: 'json', label: 'JSON', hint: 'every frame with its CRC outcome' },
  { format: 'csv', label: 'CSV', hint: 'every frame with its CRC outcome' },
  { format: 'hex', label: 'Hex', hint: 'payload bytes of the CRC-passing frames, one per line' },
  { format: 'bits', label: 'Bits', hint: 'payload bits of the CRC-passing frames, one per line' },
] as const

/** The frame table as a file. A plain download link: the server renders it, nothing leaves the
 * machine. The report holds at most the first 500 frames, and so does the file. */
function FrameExport({ url }: { url: (format: string) => string }) {
  return (
    <p className="flex flex-wrap items-center gap-x-2 border-b px-3 py-1.5 text-xs text-muted-foreground">
      <span>Export</span>
      {EXPORTS.map((e) => (
        <a
          key={e.format}
          href={url(e.format)}
          download
          title={e.hint}
          className="rounded-md border border-border-strong px-1.5 py-0.5 text-2xs font-medium hover:bg-surface-2 hover:text-foreground"
        >
          {e.label}
        </a>
      ))}
    </p>
  )
}

function Frames({ detection, exportUrl }: { detection: Detection; exportUrl?: (format: string) => string }) {
  const frames = detection.frames
  if (frames.length === 0) return <Empty>{detection.noFramesReason ?? 'No frames found.'}</Empty>
  const complete = frames.filter((f) => f.crc === 'pass').length
  const failed = frames.filter((f) => f.crc === 'fail').length
  const truncated = frames.filter((f) => f.crc === 'truncated').length
  return (
    <div>
      <p className="border-b px-3 py-2 text-xs text-muted-foreground">
        <span className="num text-foreground">{frames.length}</span> frames ·{' '}
        <span className="num text-foreground">{complete}</span> pass CRC
        {failed > 0 && (
          <>
            {' '}
            · <span className="num text-foreground">{failed}</span> fail CRC
          </>
        )}
        {truncated > 0 && (
          <>
            {' '}
            · <span className="num text-foreground">{truncated}</span> truncated by the end of the burst
          </>
        )}
      </p>
      {exportUrl && <FrameExport url={exportUrl} />}
      <table className="w-full text-xs">
        <caption className="sr-only">Frames found by sync-word correlation</caption>
        <thead>
          <tr className="border-b">
            <th className={`${TH} text-right`}>#</th>
            <th className={`${TH} text-right`}>Start bit</th>
            <th className={TH}>
              <span className="inline-flex items-center gap-1">
                Sync word <InfoTip term="asm" />
              </span>
            </th>
            <th className={`${TH} text-right`}>Length</th>
            <th className={TH}>
              <span className="inline-flex items-center gap-1">
                CRC <InfoTip term="crc" />
              </span>
            </th>
            <th className={TH}>Header</th>
            <th className={TH}>Payload (hex)</th>
            <th className={`${TH} max-xl:hidden`}>As text</th>
          </tr>
        </thead>
        <tbody>
          {frames.map((f) => (
            <tr key={f.index} className="border-b border-border/60 hover:bg-surface-2/50">
              <td className={`${TD} num text-right text-muted-foreground`}>{f.index}</td>
              <td className={`${TD} num text-right`}>{integer.format(f.startBit)}</td>
              <td className={`${TD} num`}>{f.syncWord}</td>
              <td className={`${TD} num text-right`}>{integer.format(f.lengthBits)}</td>
              <td className={TD}>
                <CrcBadge crc={f.crc} />
              </td>
              <td className={`${TD} num tracking-wider`}>{f.headerHex}</td>
              <td className={`${TD} num max-w-[34ch] truncate tracking-wider`} title={f.payloadHex || undefined}>
                {f.payloadHex || '—'}
              </td>
              <td className={`${TD} num max-w-[24ch] truncate text-muted-foreground max-xl:hidden`} title={hexToText(f.payloadHex) || undefined}>
                {hexToText(f.payloadHex) || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface Props {
  detection: Detection
  /** The Assumptions tab's content: the recording's own `<RecordingAssumptionsPanel>` (App.tsx
   * passes it in so this component doesn't need to know about `lib/api`'s `Assumptions` shape). */
  assumptionsPanel?: ReactNode
  /** How many assumptions the recording lists, shown on the tab. */
  assumptionsCount?: number
  /** The download link for the frame table in a format, for a real recording. */
  frameExportUrl?: (format: string) => string
}

export function BottomPanel({ detection, assumptionsPanel, assumptionsCount, frameExportUrl }: Props) {
  const [tab, setTab] = useState<TabId>('hypotheses')
  const tabRefs = useRef<Record<TabId, HTMLButtonElement | null>>({ hypotheses: null, frames: null, assumptions: null })

  const counts: Record<TabId, number | null> = {
    hypotheses: detection.search?.tried ?? null,
    frames: detection.frames.length,
    assumptions: assumptionsCount ?? null,
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const i = TABS.findIndex((t) => t.id === tab)
    let next: number
    if (e.key === 'ArrowRight') next = (i + 1) % TABS.length
    else if (e.key === 'ArrowLeft') next = (i - 1 + TABS.length) % TABS.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = TABS.length - 1
    else return
    e.preventDefault()
    const id = TABS[next].id
    setTab(id)
    tabRefs.current[id]?.focus()
  }

  return (
    <section aria-label="Analysis details" data-tour="bottom-tabs" className="flex min-h-0 flex-col border-t bg-surface">
      <div role="tablist" aria-label="Analysis details" className="flex shrink-0 gap-1 border-b px-2" onKeyDown={onKeyDown}>
        {TABS.map((t) => {
          const selected = t.id === tab
          const count = counts[t.id]
          return (
            <button
              key={t.id}
              ref={(el) => {
                tabRefs.current[t.id] = el
              }}
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={selected}
              aria-controls={`panel-${t.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setTab(t.id)}
              className={`relative flex items-center gap-1.5 px-2 py-2 text-xs font-medium ${selected ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            >
              {t.label}
              {count !== null && (
                <span className="num rounded-[3px] bg-surface-2 px-1 text-2xs text-muted-foreground">
                  {integer.format(count)}
                </span>
              )}
              {selected && <span className="absolute inset-x-1 -bottom-px h-0.5 rounded-full bg-primary" aria-hidden />}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} tabIndex={0} className="min-h-0 flex-1 overflow-auto">
        {tab === 'hypotheses' && <Hypotheses detection={detection} />}
        {tab === 'frames' && <Frames detection={detection} exportUrl={frameExportUrl} />}
        {tab === 'assumptions' && assumptionsPanel}
      </div>
    </section>
  )
}
