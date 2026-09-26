import { useMemo, useState } from 'react'
import { BRAND } from '@/brand'
import { DETECTIONS, RECORDING } from '@/data/demoAnalysis'
import { useDemoProducts } from '@/hooks/useDemoProducts'
import type { DemoProducts } from '@/lib/demoSignal'
import type { StageId } from '@/lib/evidence'
import { integer } from '@/lib/format'
import { fullView } from '@/lib/view'
import { BottomPanel } from '@/components/BottomPanel'
import { EvidencePanel } from '@/components/EvidencePanel'
import { PipelineRail } from '@/components/PipelineRail'
import { PsdPlot } from '@/components/PsdPlot'
import { SymbolView } from '@/components/SymbolView'
import { TopBar } from '@/components/TopBar'
import { Waterfall } from '@/components/Waterfall'

function Workspace({ demo }: { demo: DemoProducts }) {
  const full = useMemo(() => fullView(demo.rows, demo.hop, demo.fs), [demo])
  const [view, setView] = useState(full)
  const [selectedId, setSelectedId] = useState(DETECTIONS[0].id)
  const [activeStage, setActiveStage] = useState<StageId | null>(null)
  const selected = DETECTIONS.find((d) => d.id === selectedId) ?? DETECTIONS[0]

  function selectDetection(id: number) {
    setSelectedId(id)
    setActiveStage(null)
  }

  return (
    <main className="grid flex-1 grid-cols-[216px_minmax(0,1fr)_minmax(320px,380px)] max-xl:grid-cols-[200px_minmax(0,1fr)] max-md:grid-cols-1 xl:min-h-0">
      <PipelineRail
        detections={DETECTIONS}
        selected={selected}
        onSelectDetection={selectDetection}
        activeStage={activeStage}
        onSelectStage={setActiveStage}
      />

      <div className="flex min-w-0 flex-col max-xl:h-[780px] xl:min-h-0">
        <Waterfall
          demo={demo}
          full={full}
          view={view}
          onViewChange={setView}
          detections={DETECTIONS}
          selectedId={selected.id}
          onSelect={selectDetection}
        />
        <div className="h-[118px] shrink-0 border-t">
          <PsdPlot demo={demo} view={view} detections={DETECTIONS} selectedId={selected.id} />
        </div>
        <div className="flex h-[232px] shrink-0 flex-col">
          <BottomPanel detection={selected} />
        </div>
      </div>

      <aside
        aria-label="Symbols and evidence"
        className="border-l bg-surface max-xl:col-span-2 max-xl:border-t max-xl:border-l-0 max-md:col-span-1 xl:min-h-0 xl:overflow-y-auto"
      >
        <SymbolView detection={selected} demo={demo} />
        <EvidencePanel detection={selected} activeStage={activeStage} />
      </aside>
    </main>
  )
}

function StatusBar({ demo }: { demo: DemoProducts | null }) {
  return (
    <footer className="num flex h-6 shrink-0 items-center gap-3 border-t bg-surface px-3 text-2xs text-subtle-foreground">
      <span>
        {BRAND.name} {BRAND.version}
      </span>
      <span className="max-sm:hidden">Demo data generated in the browser from a fixed seed</span>
      {demo && (
        <span className="ml-auto max-md:hidden">
          {integer.format(demo.rows)} × {demo.bins} tile · {integer.format(RECORDING.sampleRateHz)} S/s · FFT {demo.fftSize}, hop{' '}
          {demo.hop}
        </span>
      )}
    </footer>
  )
}

export default function App() {
  const { products, error } = useDemoProducts()
  return (
    <div className="flex min-h-full flex-col xl:h-full">
      <TopBar />
      {products ? (
        <Workspace demo={products} />
      ) : (
        <div className="grid flex-1 place-items-center" role={error ? 'alert' : 'status'}>
          <p className="text-sm text-muted-foreground">{error ?? 'Generating the demo capture…'}</p>
        </div>
      )}
      <StatusBar demo={products} />
    </div>
  )
}
