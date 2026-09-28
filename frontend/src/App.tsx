import { useMemo, useState } from 'react'
import { BRAND } from '@/brand'
import { DETECTIONS, RECORDING } from '@/data/demoAnalysis'
import { useDemoProducts } from '@/hooks/useDemoProducts'
import { ApiError, fetchLevelGrid, openRecording, type RecordingInfo } from '@/lib/api'
import type { DemoProducts } from '@/lib/demoSignal'
import type { StageId } from '@/lib/evidence'
import { integer } from '@/lib/format'
import { fullView } from '@/lib/view'
import { sourceFromRecording, type WaterfallSource } from '@/lib/waterfallSource'
import { BottomPanel } from '@/components/BottomPanel'
import { EvidencePanel } from '@/components/EvidencePanel'
import { PipelineRail } from '@/components/PipelineRail'
import { PsdPlot } from '@/components/PsdPlot'
import { RecordingAssumptionsPanel } from '@/components/RecordingAssumptionsPanel'
import { SymbolView } from '@/components/SymbolView'
import { TopBar } from '@/components/TopBar'
import { Waterfall } from '@/components/Waterfall'

type Mode = { kind: 'demo'; demo: DemoProducts } | { kind: 'recording'; info: RecordingInfo; source: WaterfallSource }

function NotYetAvailable({ children }: { children: string }) {
  return <p className="px-3 py-4 text-xs text-muted-foreground italic">{children}</p>
}

function Workspace({ mode }: { mode: Mode }) {
  const demo = mode.kind === 'demo' ? mode.demo : null
  const source = mode.kind === 'demo' ? mode.demo : mode.source
  const full = useMemo(() => fullView(source.rows, source.hop, source.fs), [source])
  const [view, setView] = useState(full)
  const [selectedId, setSelectedId] = useState(DETECTIONS[0].id)
  const [activeStage, setActiveStage] = useState<StageId | null>(null)
  const detections = demo ? DETECTIONS : []
  const selected = demo ? (DETECTIONS.find((d) => d.id === selectedId) ?? DETECTIONS[0]) : null

  function selectDetection(id: number) {
    setSelectedId(id)
    setActiveStage(null)
  }

  return (
    <main className="grid flex-1 grid-cols-[216px_minmax(0,1fr)_minmax(320px,380px)] max-xl:grid-cols-[200px_minmax(0,1fr)] max-md:grid-cols-1 xl:min-h-0">
      {selected ? (
        <PipelineRail
          detections={detections}
          selected={selected}
          onSelectDetection={selectDetection}
          activeStage={activeStage}
          onSelectStage={setActiveStage}
        />
      ) : (
        <nav aria-label="Detections and pipeline" className="border-r bg-surface max-md:border-r-0 max-md:border-b xl:min-h-0 xl:overflow-y-auto">
          <NotYetAvailable>
            Detection isn't built yet (PLAN M2 onward is still landing) — nothing to list for this recording yet.
          </NotYetAvailable>
        </nav>
      )}

      <div className="flex min-w-0 flex-col max-xl:h-[780px] xl:min-h-0">
        <Waterfall
          source={source}
          full={full}
          view={view}
          onViewChange={setView}
          detections={detections}
          selectedId={selected?.id ?? -1}
          onSelect={selectDetection}
        />
        <div className="h-[118px] shrink-0 border-t">
          <PsdPlot source={source} view={view} detections={detections} selectedId={selected?.id ?? -1} />
        </div>
        <div className="flex h-[232px] shrink-0 flex-col">
          {mode.kind === 'recording' ? (
            <RecordingAssumptionsPanel assumptions={mode.info.assumptions} />
          ) : (
            <BottomPanel detection={selected!} />
          )}
        </div>
      </div>

      <aside
        aria-label="Symbols and evidence"
        className="border-l bg-surface max-xl:col-span-2 max-xl:border-t max-xl:border-l-0 max-md:col-span-1 xl:min-h-0 xl:overflow-y-auto"
      >
        {selected && demo ? (
          <>
            <SymbolView detection={selected} demo={demo} />
            <EvidencePanel detection={selected} activeStage={activeStage} />
          </>
        ) : (
          <NotYetAvailable>
            Synchronisation, demodulation and per-stage evidence aren't built yet (PLAN M3 onward) — this
            recording's waterfall and PSD are real; everything downstream of them still needs those stages.
          </NotYetAvailable>
        )}
      </aside>
    </main>
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
          {mode.kind === 'demo' ? mode.demo.hop : mode.source.hop}
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
    <div className="flex min-h-full flex-col xl:h-full">
      <TopBar
        fileName={recording ? recording.info.name : RECORDING.fileName}
        isDemo={!recording}
        opening={opening}
        openError={openError}
        onOpen={openPath}
      />
      {mode ? (
        <Workspace mode={mode} />
      ) : (
        <div className="grid flex-1 place-items-center" role={error ? 'alert' : 'status'}>
          <p className="text-sm text-muted-foreground">{error ?? 'Generating the demo capture…'}</p>
        </div>
      )}
      <StatusBar mode={mode} />
    </div>
  )
}
