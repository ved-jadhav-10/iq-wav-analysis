import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { BRAND } from '@/brand'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import {
  ApiError,
  fetchLevelGrid,
  getRecording,
  listInputs,
  openRecording,
  openSample,
  putAssumptions,
  saveAsSigmf,
  uploadFiles,
  watchAnalysis,
  type AssumptionValues,
  type InputInfo,
  type RecordingInfo,
} from '@/lib/api'
import type { Detection, DetectionReport } from '@/lib/analysis'
import type { StageId } from '@/lib/evidence'
import { integer } from '@/lib/format'
import { fullView } from '@/lib/view'
import { summaryTarget } from '@/lib/summary'
import { loadStoredView, storeView, viewByDigit, type SectionId } from '@/lib/views'
import { sourceFromRecording, type WaterfallSource } from '@/lib/waterfallSource'
import { hasSeenOnboarding, markOnboardingSeen } from '@/lib/onboarding'
import { startTour } from '@/lib/tour'
import { BatchChooser } from '@/components/BatchChooser'
import { BitstreamView } from '@/components/BitstreamView'
import { Frames, Hypotheses, TabbedPanel, type TabSpec } from '@/components/DetailTabs'
import { EvidenceBadge } from '@/components/EvidenceBadge'
import { FormatPrompt } from '@/components/FormatPrompt'
import { HistorySection } from '@/components/HistorySection'
import { EvidencePanel } from '@/components/EvidencePanel'
import { PipelineRail } from '@/components/PipelineRail'
import { PsdPlot } from '@/components/PsdPlot'
import { SampleRatePrompt } from '@/components/SampleRatePrompt'
import { RecordingAssumptionsPanel } from '@/components/RecordingAssumptionsPanel'
import { SplitPane } from '@/components/SplitPane'
import { StartScreen } from '@/components/StartScreen'
import { SummarySection, SummaryWaiting } from '@/components/SummarySection'
import { ConstellationPlot, EyePlot } from '@/components/SymbolView'
import { TopBar } from '@/components/TopBar'
import { Waterfall } from '@/components/Waterfall'
import { Welcome } from '@/components/Welcome'

/** When, after an analysis reports done, the History list is fetched again (the server keeps the
 * finished analysis on its worker thread, just after the state turns). */
const KEPT_REFETCH_MS = [200, 2000]

type Opened = { info: RecordingInfo; source: WaterfallSource }

/** A detection's `analysis` (the `DetectionReport` contract) plus the `id`/`boxes` the waterfall
 * and the pipeline rail need. */
function toDetection(info: RecordingInfo['detections'][number], index: number): Detection {
  return { ...(info.analysis ?? pendingReport(info)), id: index + 1, boxes: [info.box] }
}

/** What a detection shows until the background analysis reaches it: only the detector's own
 * evidence, and the honest reason nothing else is there yet. */
function pendingReport(info: RecordingInfo['detections'][number]): DetectionReport {
  const waiting = 'The analysis has not reached this signal yet.'
  return {
    label: 'Signal',
    kind: 'unknown',
    level: 'ESTIMATED',
    headline: 'Analysing this signal…',
    stages: [
      {
        id: 'detect',
        name: 'Detect',
        status: 'done',
        summary: 'Band found by the detector',
        level: 'ESTIMATED',
        parameters: info.parameters,
      },
    ],
    search: null,
    noSearchReason: waiting,
    frames: [],
    noFramesReason: waiting,
    constellation: [],
  }
}

function EmptyDetections({ rateUnknown = false }: { rateUnknown?: boolean }) {
  return (
    <nav aria-label="Detections" className="flex flex-col border-r bg-surface max-md:border-r-0 max-md:border-b">
      <div className="px-3 pt-3 pb-2">
        <h2 className="eyebrow">Detections</h2>
      </div>
      <p className="px-3 pb-4 text-xs text-muted-foreground italic">
        {rateUnknown
          ? 'Signals are found once the sample rate is entered.'
          : 'No signals cleared the significance threshold in this recording.'}
      </p>
    </nav>
  )
}

/** Detections as a horizontal strip, for the section that gives the whole display to the plot. */
function DetectionStrip({
  detections,
  selectedId,
  onSelect,
  rateUnknown,
}: {
  detections: Detection[]
  selectedId: number
  onSelect: (id: number) => void
  rateUnknown: boolean
}) {
  return (
    <nav
      aria-label="Detections"
      className="flex shrink-0 items-center gap-1.5 overflow-x-auto border-b bg-surface px-2 py-1.5"
    >
      <h2 className="eyebrow shrink-0 pr-1">Detections</h2>
      {detections.length === 0 ? (
        <span className="text-xs text-muted-foreground italic">
          {rateUnknown ? 'Found once the sample rate is entered.' : 'None in this recording.'}
        </span>
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

type EvidenceTab = 'values' | 'frames' | 'bitstream'

function Workspace({
  mode,
  view,
  onViewChange,
  historyTick,
}: {
  mode: Opened
  view: SectionId
  onViewChange: (view: SectionId) => void
  /** Changes whenever an analysis finishes, so the History list is fetched again. */
  historyTick: number
}) {
  const source = mode.source
  const full = useMemo(() => fullView(source.rows, source.hop, source.fs), [source])
  // `view` is the section; the waterfall's zoom window is `zoom`, which belongs to the recording.
  const [zoom, setZoom] = useState(full)
  // Null until the analyst picks a signal: then the first one the analysis has reached is shown.
  const [pickedId, setPickedId] = useState<number | null>(null)
  const [activeStage, setActiveStage] = useState<StageId | null>(null)
  const [evidenceTab, setEvidenceTab] = useState<EvidenceTab>('values')

  // The split only applies where there's room for two panes; below xl the grid stacks.
  const splittable = useMediaQuery('(min-width: 1280px)')

  const rateUnknown = Boolean(mode.source.normalised)
  const detections: Detection[] = mode.info.detections.map(toDetection)
  const firstReached = mode.info.detections.findIndex((d) => d.analysis !== null)
  const selected =
    detections.find((d) => d.id === pickedId) ??
    (detections.length > 0 ? detections[Math.max(firstReached, 0)] : undefined)

  function selectDetection(id: number) {
    setPickedId(id)
    setActiveStage(null)
  }

  /** A stage clicked in the pipeline rail opens its values in the Evidence section. */
  function showStage(id: StageId) {
    setActiveStage(id)
    setEvidenceTab('values')
    onViewChange('evidence')
  }

  const frameExportUrl = selected
    ? (format: string) => `/api/v1/recordings/${mode.info.id}/detections/${selected.id - 1}/frames?format=${format}`
    : undefined

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

  // The waterfall column. `flex-1 min-h-0` so the column is bounded by its parent and the
  // waterfall takes what's left over. Without `flex-1` the column is auto-height in a flex parent,
  // the waterfall's own `flex-1` has no definite space to fill, and the plot collapses to zero. As
  // a grid item, `flex-1` is inert and `align-self` stretches it, so the same class works in both.
  const plotColumn = (
    <div data-tour="waterfall" className="flex min-h-0 min-w-0 flex-1 flex-col">
      {waterfall}
      {psd}
    </div>
  )

  // Constellation over eye, each in a card with a definite height (UI.md invariants 1 and 2); side
  // by side when the layout stacks.
  const symbolsColumn = (
    <aside
      aria-label="Constellation and eye"
      className="grid h-full min-h-0 min-w-0 grid-rows-[minmax(0,1fr)_minmax(0,1fr)] border-l bg-surface max-xl:grid-cols-2 max-xl:grid-rows-[minmax(0,1fr)] max-xl:border-t max-xl:border-l-0 max-md:grid-cols-1 max-md:grid-rows-[minmax(220px,1fr)_minmax(220px,1fr)]"
    >
      {selected ? (
        <>
          <ConstellationPlot detection={selected} />
          <EyePlot detection={selected} />
        </>
      ) : (
        <p className="px-3 py-4 text-xs text-muted-foreground italic">
          {rateUnknown
            ? 'Signals are found once the sample rate is entered.'
            : 'No signals were detected in this recording, so there is no constellation or eye to draw.'}
        </p>
      )}
    </aside>
  )

  const rail = selected ? (
    <PipelineRail
      detections={detections}
      selected={selected}
      onSelectDetection={selectDetection}
      activeStage={activeStage}
      onSelectStage={showStage}
    />
  ) : (
    <EmptyDetections rateUnknown={rateUnknown} />
  )

  const detectionStrip = (
    <DetectionStrip
      detections={detections}
      selectedId={selected?.id ?? -1}
      onSelect={selectDetection}
      rateUnknown={rateUnknown}
    />
  )

  const noSignal = (
    <p className="px-4 py-6 text-xs text-muted-foreground italic">
      {rateUnknown ? 'Signals are found once the sample rate is entered.' : 'No signals were detected in this recording.'}
    </p>
  )

  const evidenceTabs: readonly TabSpec<EvidenceTab>[] = [
    { id: 'values', label: 'Values', caption: 'Every value with its level, method, evidence and alternatives, stage by stage.' },
    {
      id: 'frames',
      label: 'Frames',
      count: selected?.frames.length ?? null,
      caption: 'Frames found by sync-word search, with the CRC result, header and payload of each.',
    },
    {
      id: 'bitstream',
      label: 'Bit stream',
      count: selected?.frames.length ?? null,
      caption: 'How the frames sit in the stream and how the sync word recurs.',
    },
  ]

  // The plain-language summary belongs to a recording whose analysis has finished.
  const summaryId = summaryTarget(mode.info)

  return (
    <>
      {view === 'dashboard' &&
        (splittable ? (
          <SplitPane rail={rail} main={plotColumn} panel={symbolsColumn} panelLabel="the constellation and eye" />
        ) : (
          <main className="grid min-h-0 flex-1 grid-cols-[216px_minmax(0,1fr)] grid-rows-[minmax(216px,1.6fr)_minmax(0,1fr)] max-md:grid-cols-1 max-md:grid-rows-[auto_minmax(0,1fr)]">
            {rail}
            {plotColumn}
            {/* Two columns, three children: the symbols wrap to a second row, so they span both
                rather than land in the 216px column. `min-h-0` plus the aside's `h-full` give them
                a definite height. */}
            <div className="min-h-0 min-w-0 max-xl:col-span-2">{symbolsColumn}</div>
          </main>
        ))}

      {view === 'evidence' && (
        <main aria-label="Evidence" className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {detectionStrip}
          {selected ? (
            <div data-tour="evidence" className="flex min-h-0 flex-1 flex-col">
              <TabbedPanel label="Evidence" tabs={evidenceTabs} tab={evidenceTab} onTab={setEvidenceTab}>
                {evidenceTab === 'values' && (
                  <div className="mx-auto max-w-4xl">
                    <EvidencePanel detection={selected} activeStage={activeStage} />
                  </div>
                )}
                {evidenceTab === 'frames' && <Frames detection={selected} exportUrl={frameExportUrl} />}
                {evidenceTab === 'bitstream' && <BitstreamView detection={selected} />}
              </TabbedPanel>
            </div>
          ) : (
            noSignal
          )}
        </main>
      )}

      {view === 'hypotheses' && (
        <main aria-label="Hypotheses" className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {detectionStrip}
          {selected ? (
            <div data-tour="hypotheses" className="min-h-0 flex-1 overflow-auto bg-surface">
              <Hypotheses detection={selected} />
            </div>
          ) : (
            noSignal
          )}
        </main>
      )}

      {view === 'summary' &&
        (summaryId ? (
          <SummarySection key={summaryId} recordingId={summaryId} />
        ) : (
          <SummaryWaiting done={mode.info.analysis.done} total={mode.info.analysis.total} />
        ))}

      {/* The kept analyses are the server's, not this recording's: the section sits in the
          Workspace only so that zoom and selection survive a visit to it. */}
      {view === 'history' && <HistorySection refreshKey={historyTick} />}
    </>
  )
}

function StatusBar({ opened }: { opened: Opened | null }) {
  return (
    <footer className="num flex h-6 shrink-0 items-center gap-3 border-t bg-surface px-3 text-2xs text-subtle-foreground">
      <span>
        {BRAND.name} {BRAND.version}
      </span>
      <span className="max-sm:hidden">
        {opened ? `Opened from ${opened.info.container}` : 'Offline · nothing leaves this machine'}
      </span>
      {opened?.info.analysis.state === 'running' && (
        <span role="status" className="text-foreground">
          Analysing signal {Math.min(opened.info.analysis.done + 1, opened.info.analysis.total)} of{' '}
          {opened.info.analysis.total}…
        </span>
      )}
      {opened && (
        <span className="ml-auto max-md:hidden">
          {integer.format(opened.source.rows)} × {opened.source.bins} tile ·{' '}
          {opened.source.normalised ? 'rate unknown' : `${integer.format(opened.source.fs)} S/s`} · FFT{' '}
          {opened.source.fftSize}, hop {integer.format(Math.round(opened.source.hop))}
        </span>
      )}
    </footer>
  )
}

export default function App() {
  const [recording, setRecording] = useState<Opened | null>(null)
  const [opening, setOpening] = useState(false)
  // Which bundled sample is being opened, for its card's spinner.
  const [openingSample, setOpeningSample] = useState<string | null>(null)
  const [openError, setOpenError] = useState<string | null>(null)
  const [view, setView] = useState<SectionId>(loadStoredView)
  const [assumptionsModalOpen, setAssumptionsModalOpen] = useState(false)
  // A folder that holds several recordings, until the analyst picks one.
  const [batch, setBatch] = useState<{ source: string; items: InputInfo[] } | null>(null)
  // Counts restarts of the analysis (entered values), so the progress stream is followed again.
  const [run, setRun] = useState(0)
  // Counts finished analyses, so the History list is fetched again.
  const [historyTick, setHistoryTick] = useState(0)
  // A raw file whose sample format is UNKNOWN, until the analyst chooses one.
  const [formatNeeded, setFormatNeeded] = useState<{ item: InputInfo; candidates: string[] } | null>(null)

  // With nothing open only the start screen (Dashboard) and History have anything to show.
  const shownView: SectionId = recording || view === 'history' ? view : 'dashboard'
  const hasRecording = recording !== null

  const changeView = useCallback((next: SectionId) => {
    setView(next)
    storeView(next)
  }, [])

  // Alt+1..6 jumps between sections without leaving the waterfall's keyboard handling. A bare 1..6
  // would fight numeric fields. Assumptions is a modal over the current section, never a section.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!e.altKey || e.ctrlKey || e.metaKey) return
      const target = e.target as HTMLElement | null
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return
      const next = viewByDigit(e.key)
      if (!next) return
      e.preventDefault()
      if (next === 'assumptions') {
        if (hasRecording) setAssumptionsModalOpen(true)
      } else if (hasRecording || next === 'dashboard' || next === 'history') {
        changeView(next)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [changeView, hasRecording])

  async function upload(files: File[]) {
    if (opening) return
    setOpening(true)
    setOpenError(null)
    try {
      await openPath(await uploadFiles(files), true)
    } catch (e) {
      setOpenError(e instanceof Error ? e.message : String(e))
      setOpening(false)
    }
  }

  // Files dropped anywhere on the window are uploaded, as the picker's would be.
  useEffect(() => {
    const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes('Files')
    const onDragOver = (e: DragEvent) => {
      if (hasFiles(e)) e.preventDefault() // makes the window a drop target
    }
    const onDrop = (e: DragEvent) => {
      if (!hasFiles(e)) return
      e.preventDefault()
      const files = Array.from(e.dataTransfer?.files ?? [])
      if (files.length > 0) void upload(files)
    }
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('drop', onDrop)
    }
  })

  async function openPath(path: string, alreadyOpening = false, sequence = false) {
    if (!alreadyOpening) {
      setOpening(true)
      setOpenError(null)
    }
    let only: InputInfo | undefined
    try {
      const items = await listInputs(path, sequence)
      only = items[0]
      if (!only) throw new ApiError(`${path} holds no recordings`)
      if (items.length > 1) {
        setBatch({ source: path, items })
        return
      }
      await openItem(only)
    } catch (e) {
      reportOpenError(e, only)
    } finally {
      setOpening(false)
    }
  }

  /** A failed open is a message, except an UNKNOWN sample format, which is a question. */
  function reportOpenError(e: unknown, item?: InputInfo) {
    if (item && e instanceof ApiError && e.formatCandidates !== null) {
      setFormatNeeded({ item, candidates: e.formatCandidates })
      setOpenError(null)
      return
    }
    setOpenError(e instanceof Error ? e.message : String(e))
  }

  async function openItem(item: InputInfo, datatype?: string) {
    const info = await openRecording(item.path, item.sequence, datatype)
    const level = info.levels[0]
    if (!level) throw new ApiError(`${item.name} has no spectrogram levels to show`)
    const grid = await fetchLevelGrid(info.id, level)
    setFormatNeeded(null)
    setRecording({ info, source: sourceFromRecording(info, level, grid) })
  }

  /** A bundled sample opens like any recording: tiles and boxes now, the analysis in the background. */
  async function openSampleById(id: string) {
    if (opening) return
    setOpening(true)
    setOpeningSample(id)
    setOpenError(null)
    try {
      const info = await openSample(id)
      const level = info.levels[0]
      if (!level) throw new ApiError(`${info.name} has no spectrogram levels to show`)
      const grid = await fetchLevelGrid(info.id, level)
      setRecording({ info, source: sourceFromRecording(info, level, grid) })
    } catch (e) {
      setOpenError(e instanceof Error ? e.message : String(e))
    } finally {
      setOpening(false)
      setOpeningSample(null)
    }
  }

  async function openFromBatch(item: InputInfo) {
    setBatch(null)
    setOpening(true)
    setOpenError(null)
    try {
      await openItem(item)
    } catch (e) {
      reportOpenError(e, item)
    } finally {
      setOpening(false)
    }
  }

  // While the server is still analysing, follow its progress and refetch the recording as
  // reports land; the effect ends itself when the state turns 'done'.
  const watchedId = recording?.info.id
  const analysing = recording?.info.analysis.state === 'running'
  useEffect(() => {
    if (!watchedId || !analysing) return
    const refetch = () =>
      getRecording(watchedId)
        .then((info) => setRecording((prev) => (prev && prev.info.id === info.id ? { ...prev, info } : prev)))
        .catch((e: unknown) => setOpenError(e instanceof Error ? e.message : String(e)))
    return watchAnalysis(watchedId, () => void refetch(), () => setOpenError('lost the connection to the analysis'))
  }, [watchedId, analysing, run])

  // A finished analysis is kept by the server a moment after the stream reports `done`, so the
  // History list is fetched again at once and once more shortly after.
  const analysisState = recording?.info.analysis.state
  useEffect(() => {
    if (!watchedId || analysisState !== 'done') return
    const timers = KEPT_REFETCH_MS.map((ms) => setTimeout(() => setHistoryTick((n) => n + 1), ms))
    return () => timers.forEach(clearTimeout)
  }, [watchedId, analysisState])

  // The analyst entered what the file lacks (or gets wrong): the server restarts the analysis with
  // it. The waterfall grid stays the same unless I and Q were swapped, which mirrors the spectrum
  // and has the server tile it again; otherwise only the units (and the boxes) change.
  async function enterAssumptions(values: AssumptionValues) {
    if (!recording) return
    const info = await putAssumptions(recording.info.id, values)
    const level = info.levels[0]
    if (!level) throw new ApiError('the server sent no spectrogram level')
    const grid = values.iqOrder ? await fetchLevelGrid(info.id, level) : recording.source.tile
    setRecording({ info, source: sourceFromRecording(info, level, grid) })
    setRun((n) => n + 1)
  }

  /** Back to the start screen. The server keeps analysing and keeps the result in History; the
   * stored section is left alone, so the next recording opens on the section this one was on. */
  function goHome() {
    tourWaiting.current = false
    setRecording(null)
    setBatch(null)
    setFormatNeeded(null)
    setOpenError(null)
    setAssumptionsModalOpen(false)
    if (view === 'history') changeView('dashboard')
  }

  // First run: the welcome dialog, once. Help in the top bar brings it back.
  const [welcomeOpen, setWelcomeOpen] = useState(() => !hasSeenOnboarding())
  // "Take the tour" with nothing open opens the first sample and waits for its first result.
  const tourWaiting = useRef(false)

  function closeWelcome() {
    markOnboardingSeen()
    setWelcomeOpen(false)
  }

  // The section on screen when the tour starts, which it returns to; read at start, not render time.
  const shownRef = useRef(shownView)
  useEffect(() => {
    shownRef.current = shownView
  }, [shownView])

  function runTour() {
    // After the next paint, so the sections the tour points at are in the DOM.
    requestAnimationFrame(() =>
      startTour({ onDone: markOnboardingSeen, section: shownRef.current, showSection: changeView }),
    )
  }

  const reachedFirst = recording ? recording.info.analysis.done >= 1 || recording.info.analysis.state === 'done' : false
  useEffect(() => {
    if (!tourWaiting.current || !reachedFirst) return
    tourWaiting.current = false
    runTour()
  }, [reachedFirst])

  function takeTour() {
    closeWelcome()
    if (recording) runTour()
    else {
      tourWaiting.current = true
      void openSampleById('scene')
    }
  }

  function trySample() {
    closeWelcome()
    if (recording) void openSampleById('scene')
    else setTimeout(() => document.querySelector<HTMLElement>('[data-sample]')?.focus(), 0)
  }

  // Escape closes the Assumptions modal, and focus returns to what opened it.
  const modalOpener = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (!assumptionsModalOpen) return
    modalOpener.current = document.activeElement as HTMLElement | null
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setAssumptionsModalOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      modalOpener.current?.focus()
    }
  }, [assumptionsModalOpen])

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      <TopBar
        fileName={recording ? recording.info.name : null}
        synthetic={recording?.info.synthetic ?? false}
        opening={opening}
        progress={
          recording?.info.analysis.state === 'running'
            ? { done: recording.info.analysis.done, total: recording.info.analysis.total }
            : undefined
        }
        view={shownView}
        onViewChange={changeView}
        onHome={(recording || shownView === 'history') && !opening ? goHome : undefined}
        onHelp={() => setWelcomeOpen(true)}
        onOpen={(path, sequence) => void openPath(path, false, sequence)}
        onUpload={(files) => void upload(files)}
        onOpenSettings={() => setAssumptionsModalOpen(true)}
        resultsUrl={
          recording && recording.info.analysis.state === 'done'
            ? (format) => `/api/v1/recordings/${recording.info.id}/results?format=${format}`
            : undefined
        }
        sigmf={recording?.info.sigmf}
        onSaveSigmf={recording ? () => saveAsSigmf(recording.info.id) : undefined}
      />
      {openError && (
        <div
          role="alert"
          className="flex shrink-0 items-start gap-2 border-b border-destructive/40 bg-destructive/10 px-3 py-1.5 text-xs text-destructive"
        >
          <span className="min-w-0 flex-1 break-words">{openError}</span>
          <button
            type="button"
            onClick={() => setOpenError(null)}
            aria-label="Dismiss the error"
            className="shrink-0 rounded-sm hover:text-foreground"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        </div>
      )}
      {formatNeeded && (
        <FormatPrompt
          name={formatNeeded.item.name}
          candidates={formatNeeded.candidates}
          onChoose={(datatype) => openItem(formatNeeded.item, datatype)}
          onDismiss={() => setFormatNeeded(null)}
        />
      )}
      {recording && recording.info.sampleRate === null && (
        <SampleRatePrompt
          sampleRate={recording.info.assumptions.sampleRate}
          onSubmit={(rate) => enterAssumptions({ sampleRate: rate })}
        />
      )}
      {recording ? (
        /* Keyed by recording (and its units - entering a sample rate changes them) so opening a
           different one remounts Workspace with fresh zoom/selection state, instead of carrying
           over the previous recording's zoom and (numerically coincidental) selected id. Section
           and rail state live above this key, so they survive the switch. */
        <Workspace
          key={`${recording.info.id}:${recording.source.normalised ? 'norm' : 'hz'}:${recording.info.assumptions.iqOrder?.value ?? ''}`}
          mode={recording}
          view={shownView}
          onViewChange={changeView}
          historyTick={historyTick}
        />
      ) : shownView === 'history' ? (
        <HistorySection refreshKey={historyTick} />
      ) : (
        <StartScreen
          opening={opening}
          openingSample={openingSample}
          onUpload={(files) => void upload(files)}
          onOpenSample={(id) => void openSampleById(id)}
        />
      )}

      {/* Assumptions modal: over whatever section is on screen. */}
      {assumptionsModalOpen && recording && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setAssumptionsModalOpen(false)
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="assumptions-title"
            className="flex max-h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-md border border-border-strong bg-surface shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border bg-surface-2 px-4 py-3">
              <h2 id="assumptions-title" className="text-sm font-semibold tracking-wider text-primary uppercase">
                Configuration &amp; Assumptions
              </h2>
              <button
                type="button"
                aria-label="Close"
                autoFocus
                onClick={() => setAssumptionsModalOpen(false)}
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              <RecordingAssumptionsPanel
                assumptions={recording.info.assumptions}
                captureQuality={recording.info.captureQuality}
                onEnter={enterAssumptions}
              />
            </div>
          </div>
        </div>
      )}

      {batch && (
        <BatchChooser source={batch.source} items={batch.items} onOpen={(item) => void openFromBatch(item)} onClose={() => setBatch(null)} />
      )}

      {welcomeOpen && <Welcome onTrySample={trySample} onTakeTour={takeTour} onSkip={closeWelcome} />}

      <StatusBar opened={recording} />
    </div>
  )
}
