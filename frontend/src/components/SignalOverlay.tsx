import { useEffect, useRef } from 'react'
import { Maximize2, X } from 'lucide-react'
import type { Detection } from '@/data/demoAnalysis'
import type { DemoProducts } from '@/lib/demoSignal'
import type { StageId } from '@/lib/evidence'
import { BottomPanel } from './BottomPanel'
import { EvidencePanel } from './EvidencePanel'
import { SymbolView } from './SymbolView'

interface Props {
  detection: Detection
  demo?: DemoProducts
  activeStage: StageId | null
  assumptionsPanel?: React.ReactNode
  onClose: () => void
}

/**
 * The per-detection deep dive, full screen.
 *
 * Deliberately an overlay rather than a section: you open it to read one signal end to end, then
 * come back out to the survey. Giving it a section of its own would have meant the waterfall
 * losing a third of the display every time anyone wanted to look at a constellation.
 */
export function SignalOverlay({ detection, demo, activeStage, assumptionsPanel, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    // Focus the close button so Escape and Tab work from the moment it opens.
    closeRef.current?.focus()
  }, [])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Detection ${detection.id}, ${detection.label}`}
      className="fixed inset-0 z-50 flex flex-col bg-background"
    >
      <header className="flex h-12 shrink-0 items-center gap-3 border-b bg-surface px-3">
        <Maximize2 className="size-4 shrink-0 text-primary" aria-hidden />
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold tracking-tight">
            <span className="num text-subtle-foreground">#{detection.id}</span> {detection.label}
          </div>
          <p className="truncate text-xs text-muted-foreground">{detection.headline}</p>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          aria-label="Close the full-screen view (Esc)"
          className="ml-auto grid size-8 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-surface-2 hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] max-lg:grid-cols-1 max-lg:grid-rows-[minmax(0,1fr)_minmax(0,1fr)]">
        <section
          aria-label="Symbols and evidence"
          className="min-h-0 min-w-0 overflow-y-auto border-r bg-surface max-lg:border-r-0 max-lg:border-b"
        >
          <SymbolView detection={detection} demo={demo} />
          <EvidencePanel detection={detection} activeStage={activeStage} />
        </section>
        <section
          aria-label="Search ledger"
          className="flex min-h-0 min-w-0 flex-col border-l bg-surface max-lg:border-l-0"
        >
          <BottomPanel detection={detection} assumptionsPanel={assumptionsPanel} />
        </section>
      </div>
    </div>
  )
}
