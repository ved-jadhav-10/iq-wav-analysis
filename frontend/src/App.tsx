import { useCallback, useEffect, useMemo, useState } from 'react'
import { ChevronRight, Maximize2, PanelRightClose, X } from 'lucide-react'
import { BRAND } from '@/brand'
import { DETECTIONS, RECORDING, type Detection } from '@/data/demoAnalysis'
import { useDemoProducts } from '@/hooks/useDemoProducts'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { ApiError, fetchLevelGrid, openRecording, type RecordingInfo } from '@/lib/api'
import type { DemoProducts } from '@/lib/demoSignal'
import type { StageId } from '@/lib/evidence'
import { integer } from '@/lib/format'
import { fullView } from '@/lib/view'
import { loadStoredView, storeView, viewByDigit, type ViewId } from '@/lib/views'
import { sourceFromRecording, type WaterfallSource } from '@/lib/waterfallSource'
import { BottomPanel } from '@/components/BottomPanel'
import { EvidenceBadge } from '@/components/EvidenceBadge'
import { EvidencePanel } from '@/components/EvidencePanel'
import { PipelineRail } from '@/components/PipelineRail'
import { PsdPlot } from '@/components/PsdPlot'
import { RecordingAssumptionsPanel } from '@/components/RecordingAssumptionsPanel'
import { SignalOverlay } from '@/components/SignalOverlay'
import { SplitPane } from '@/components/SplitPane'
import { SymbolView } from '@/components/SymbolView'
import { TopBar } from '@/components/TopBar'
import { Waterfall } from '@/components/Waterfall'

type Mode = { kind: 'demo'; demo: DemoProducts } | { kind: 'recording'; info: RecordingInfo; source: WaterfallSource }

/** A real detection's `analysis` (the `DetectionReport` contract) plus the `id`/`boxes` the
 * waterfall and the pipeline rail need - the same shape the demo path's `Detection` already is
 * (see data/demoAnalysis.ts), so both feed the same panels unchanged. */
function toDetection(info: RecordingInfo['detections'][number], index: number): Detection {
  return { ...info.analysis, id: index + 1, boxes: [info.box] }
}

function EmptyDetections() {
  return (
    <nav aria-label="Detections" className="flex flex-col border-r bg-surface max-md:border-r-0 max-md:border-b">
      <div className="px-3 pt-3 pb-2">
        <h2 className="eyebrow">Detections</h2>
      </div>
      <p className="px-3 pb-4 text-xs text-muted-foreground italic">
        No signals cleared the significance threshold in this recording.
      </p>
    </nav>
  )
}

/** Detections as a horizontal strip, for the section that gives the whole display to the plot. */
function DetectionStrip({
  detections,
  selectedId,
  onSelect,
}: {
  detections: Detection[]
  selectedId: number
  onSelect: (id: number) => void
}) {
  return (
    <nav
      aria-label="Detections"
      className="flex shrink-0 items-center gap-1.5 overflow-x-auto border-b bg-surface px-2 py-1.5"
    >
      <h2 className="eyebrow shrink-0 pr-1">Detections</h2>
      {detections.length === 0 ? (
        <span className="text-xs text-muted-foreground italic">None in this recording.</span>
      ) : (
        detections.map((d) => (
          <button
            key={d.id}
            type="button"
            onClick={() => onSelect(d.id)}
            aria-current={d.id === selectedId ? 'true' : undefined}
            className={`flex shrink-0 items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors ${
              d.id === selectedId
                ? 'border-primary/50 bg-surface-2 text-foreground'
                : 'border-border text-muted-foreground hover:bg-surface-2/60 hover:text-foreground'
            }`}
          >
            <span className="num text-subtle-foreground">#{d.id}</span>
            <span className="font-medium">{d.label}</span>
            <EvidenceBadge level={d.level} />
          </button>
        ))
      )}
    </nav>
  )
}

function Workspace({
  mode,
  view,
  railOpen,
  onRailOpenChange,
}: {
  mode: Mode
  view: ViewId
  railOpen: boolean
  onRailOpenChange: (open: boolean) => void
}) {
  const demo = mode.kind === 'demo' ? mode.demo : undefined
  const source = mode.kind === 'demo' ? mode.demo : mode.source
  const full = useMemo(() => fullView(source.rows, source.hop, source.fs), [source])
  // `view` is the section; the waterfall's zoom window is `zoom`, which belongs to the recording.
  const [zoom, setZoom] = useState(full)
  const [selectedId, setSelectedId] = useState(DETECTIONS[0].id)
  const [activeStage, setActiveStage] = useState<StageId | null>(null)
  const [fullScreen, setFullScreen] = useState(false)

  // The split only applies where there's room for two panes; below xl the grid stacks.
  const splittable = useMediaQuery('(min-width: 1280px)')

  const detections: Detection[] =
    mode.kind === 'demo' ? DETECTIONS : mode.info.detections.map(toDetection)
  // selectedId can be stale (left over from the demo, or a recording with fewer signals than the
  // last one) - clamped to the first detection, same as the demo path's own fallback below.
  const selected =
    detections.find((d) => d.id === selectedId) ?? (detections.length > 0 ? detections[0] : undefined)

  function selectDetection(id: number) {
    setSelectedId(id)
    setActiveStage(null)
  }

  const assumptionsPanel =
    mode.kind === 'recording' ? <RecordingAssumptionsPanel assumptions={mode.info.assumptions} /> : undefined

  const waterfall = (
    <Waterfall
      source={source}
      full={full}
      view={zoom}
      onViewChange={setZoom}
      detections={detections}
      selectedId={selected?.id ?? -1}
      onSelect={selectDetection}
    />
  )

  const psd = (
    <div className="h-[118px] shrink-0 border-t">
      <PsdPlot source={source} view={zoom} detections={detections} selectedId={selected?.id ?? -1} />
    </div>
  )

  // The plot column, shared by Survey and Waterfall: same waterfall, same zoom, same selection.
  // `flex-1 min-h-0` so the column is bounded by its parent and the waterfall takes what's left
  // over. Without `flex-1` the column is auto-height in the Waterfall section, the waterfall's own
  // `flex-1` has no definite space to fill, and the plot collapses to zero - leaving the power
  // spectrum and a large empty gap. As a grid item in Survey, `flex-1` is inert and `align-self`
  // stretches it, so the same class works in both places.
  const plotColumn = (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      {waterfall}
      {psd}
      {view === 'survey' && (
        <div className="flex h-[232px] shrink-0 flex-col">
          {selected ? (
            <BottomPanel detection={selected} assumptionsPanel={assumptionsPanel} />
          ) : mode.kind === 'recording' ? (
            <RecordingAssumptionsPanel assumptions={mode.info.assumptions} />
          ) : null}
        </div>
      )}
    </div>
  )

  const evidenceRail = (
    <aside
      aria-label="Symbols and evidence"
      className="flex h-full min-h-0 min-w-0 flex-col bg-surface max-xl:border-t max-xl:border-l-0"
    >
      {selected ? (
        <>
          <div className="flex h-8 shrink-0 items-center gap-2 border-b px-2">
            <h2 className="eyebrow">Evidence · #{selected.id}</h2>
            <button
              type="button"
              onClick={() => setFullScreen(true)}
              className="ml-auto flex items-center gap-1 rounded-md px-1.5 py-0.5 text-2xs font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground"
              title="Open this detection full screen (Esc to close)"
            >
              <Maximize2 className="size-3" aria-hidden />
              Full screen
            </button>
            {splittable && (
              <button
                type="button"
                onClick={() => onRailOpenChange(false)}
                aria-label="Hide the evidence panel"
                className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-2xs font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                title="Hide the evidence panel"
              >
                <PanelRightClose className="size-3.5" aria-hidden />
              </button>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <SymbolView detection={selected} demo={demo} />
            <EvidencePanel detection={selected} activeStage={activeStage} />
          </div>
        </>
      ) : (
        <p className="px-3 py-4 text-xs text-muted-foreground italic">
          No signals were detected in this recording.
        </p>
      )}
    </aside>
  )

  // The rail is its own grid cell, so hiding it has to change the template, not just skip a child.
  const showRail = splittable ? railOpen : true

  return (
    <>
      {view === 'survey' &&
        (splittable ? (
          <SplitPane
            rail={
              selected ? (
                <PipelineRail
                  detections={detections}
                  selected={selected}
                  onSelectDetection={selectDetection}
                  activeStage={activeStage}
                  onSelectStage={setActiveStage}
                />
              ) : (
                <EmptyDetections />
              )
            }
            main={plotColumn}
            panel={showRail ? evidenceRail : null}
            panelLabel="the evidence panel"
          />
        ) : (
          <main className="grid min-h-0 flex-1 grid-cols-[216px_minmax(0,1fr)] grid-rows-[minmax(216px,1.6fr)_minmax(0,1fr)] max-md:grid-cols-1 max-md:grid-rows-[auto_minmax(0,1fr)]">
            {selected ? (
              <PipelineRail
                detections={detections}
                selected={selected}
                onSelectDetection={selectDetection}
                activeStage={activeStage}
                onSelectStage={setActiveStage}
              />
            ) : (
              <EmptyDetections />
            )}
            {plotColumn}
            {/* Two columns, three children: the rail wraps to a second row, so it has to span
                both rather than land in the 216px column. `min-h-0` plus the aside's `h-full`
                give the evidence panel a definite height, which is what makes its own
                `overflow-y-auto` engage instead of the page growing to fit every stage. */}
            <div className="min-h-0 min-w-0 max-xl:col-span-2">{evidenceRail}</div>
          </main>
        ))}

      {view === 'waterfall' && (
        <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <DetectionStrip detections={detections} selectedId={selected?.id ?? -1} onSelect={selectDetection} />
          {plotColumn}
        </main>
      )}

      {/* Removed separate assumptions view, using modal below */}

      {!showRail && view === 'survey' && (
        <button
          type="button"
          onClick={() => onRailOpenChange(true)}
          aria-label="Show the evidence panel"
          className="absolute top-1/2 right-0 z-20 flex -translate-y-1/2 items-center gap-0.5 rounded-l-md border border-r-0 bg-surface px-1 py-3 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
        >
          <PanelRightClose className="size-3.5" aria-hidden />
          <ChevronRight className="size-3" aria-hidden />
        </button>
      )}

      {fullScreen && selected && (
        <SignalOverlay
          detection={selected}
          demo={demo}
          activeStage={activeStage}
          assumptionsPanel={assumptionsPanel}
          onClose={() => setFullScreen(false)}
        />
      )}
    </>
  )
}

function StatusBar({ mode }: { mode: Mode | null }) {
  return (
    <footer className="num flex h-6 shrink-0 items-center gap-3 border-t bg-surface px-3 text-2xs text-subtle-foreground">
      <span>
        {BRAND.name} {BRAND.version}
      </span>
      <span className="max-sm:hidden">
        {mode?.kind === 'recording'
          ? `Opened from ${mode.info.container}`
          : 'Demo data generated in the browser from a fixed seed'}
      </span>
      {mode && (
        <span className="ml-auto max-md:hidden">
          {integer.format(mode.kind === 'demo' ? mode.demo.rows : mode.source.rows)} ×{' '}
          {mode.kind === 'demo' ? mode.demo.bins : mode.source.bins} tile ·{' '}
          {integer.format(mode.kind === 'demo' ? RECORDING.sampleRateHz : mode.source.fs)} S/s · FFT{' '}
          {mode.kind === 'demo' ? mode.demo.fftSize : mode.source.fftSize}, hop{' '}
          {integer.format(Math.round(mode.kind === 'demo' ? mode.demo.hop : mode.source.hop))}
        </span>
      )}
    </footer>
  )
}

export default function App() {
  const { products, error } = useDemoProducts()
  const [recording, setRecording] = useState<{ info: RecordingInfo; source: WaterfallSource } | null>(null)
  const [opening, setOpening] = useState(false)
  const [openError, setOpenError] = useState<string | null>(null)
  const [view, setView] = useState<ViewId>(loadStoredView)
  const [railOpen, setRailOpen] = useState(true)
  const [assumptionsModalOpen, setAssumptionsModalOpen] = useState(false)

  const changeView = useCallback((next: ViewId) => {
    setView(next)
    storeView(next)
  }, [])

  // Alt+1..3 jumps between sections without leaving the waterfall's keyboard handling. A bare 1..3
  // would fight the demo worker's inputs and any future numeric field.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!e.altKey || e.ctrlKey || e.metaKey) return
      const target = e.target as HTMLElement | null
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return
      const next = viewByDigit(e.key)
      if (next) {
        e.preventDefault()
        changeView(next)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [changeView])

  async function openPath(path: string) {
    setOpening(true)
    setOpenError(null)
    try {
      const info = await openRecording(path)
      const level = info.levels[0]
      if (!level) throw new ApiError(`${path} has no spectrogram levels to show`)
      const grid = await fetchLevelGrid(info.id, level)
      const source = sourceFromRecording(info, level, grid)
      if (!source) {
        throw new ApiError(
          "this recording's sample rate is UNKNOWN, so its waterfall has no frequency axis to show yet " +
            '(entering it as an assumption lands with M7)',
        )
      }
      setRecording({ info, source })
    } catch (e) {
      setOpenError(e instanceof Error ? e.message : String(e))
    } finally {
      setOpening(false)
    }
  }

  const mode: Mode | null = recording
    ? { kind: 'recording', info: recording.info, source: recording.source }
    : products
      ? { kind: 'demo', demo: products }
      : null

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      <TopBar
        fileName={recording ? recording.info.name : RECORDING.fileName}
        isDemo={!recording}
        synthetic={recording?.info.synthetic ?? false}
        opening={opening}
        openError={openError}
        view={view}
        onViewChange={changeView}
        onOpen={openPath}
        onOpenSettings={() => setAssumptionsModalOpen(true)}
      />
      {mode ? (
        /* Keyed by recording so opening a different one - or switching back to the demo - remounts
           Workspace with fresh zoom/selection state, instead of carrying over the previous
           recording's zoom and (numerically coincidental) selected id. Section and rail state live
           above this key, so they survive the switch. */
        <Workspace
          key={mode.kind === 'recording' ? mode.info.id : 'demo'}
          mode={mode}
          view={view}
          railOpen={railOpen}
          onRailOpenChange={setRailOpen}
        />
      ) : (
        <div className="grid flex-1 place-items-center" role={error ? 'alert' : 'status'}>
          <p className="text-sm text-muted-foreground">{error ?? 'Generating the demo capture…'}</p>
        </div>
      )}
      
      {/* Settings / Assumptions Overlay Modal */}
      {assumptionsModalOpen && mode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="flex max-h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-md border border-border-strong bg-[#121212] shadow-2xl">
            <div className="flex items-center justify-between border-b border-border bg-[#0a0a0a] px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-primary">Configuration & Assumptions</h2>
              <button 
                onClick={() => setAssumptionsModalOpen(false)}
                className="rounded-md p-1 text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {mode.kind === 'recording' ? (
                <RecordingAssumptionsPanel assumptions={mode.info.assumptions} />
              ) : (
                <p className="text-sm text-muted-foreground">No assumptions for generated demo.</p>
              )}
            </div>
          </div>
        </div>
      )}

      <StatusBar mode={mode} />
    </div>
  )
}
