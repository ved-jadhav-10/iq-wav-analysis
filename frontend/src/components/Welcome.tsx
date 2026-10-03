import { useEffect, useRef } from 'react'
import { BRAND } from '@/brand'
import { LEVEL_INFO, type EvidenceLevel } from '@/lib/evidence'
import { EvidenceBadge } from './EvidenceBadge'
import { Logo } from './Logo'

interface Props {
  onTrySample(): void
  onTakeTour(): void
  onSkip(): void
}

const LEVELS: readonly EvidenceLevel[] = ['VERIFIED', 'MEASURED', 'ESTIMATED', 'HYPOTHESIS', 'UNKNOWN']

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** First-run welcome: what Sanket does and how to read its evidence levels, in a modal that traps
 * focus, treats Esc as Skip, and hands focus back to whatever had it before. */
export function Welcome({ onTrySample, onTakeTour, onSkip }: Props) {
  const dialogRef = useRef<HTMLDivElement | null>(null)
  const primaryRef = useRef<HTMLButtonElement | null>(null)
  const skipRef = useRef(onSkip)

  useEffect(() => {
    skipRef.current = onSkip
  }, [onSkip])

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    primaryRef.current?.focus()
    return () => {
      if (previous?.isConnected) previous.focus()
    }
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        skipRef.current()
        return
      }
      if (e.key !== 'Tab') return
      const dialog = dialogRef.current
      if (!dialog) return
      const items = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      const active = document.activeElement
      if (!dialog.contains(active)) {
        e.preventDefault()
        first.focus()
      } else if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="welcome-title"
        className="flex max-h-[90vh] w-full max-w-xl flex-col overflow-y-auto rounded-lg border border-border-strong bg-surface p-6 shadow-2xl sm:p-8"
      >
        <div className="flex items-center gap-3">
          <Logo className="size-9 shrink-0" />
          <div className="flex items-baseline gap-2">
            <span className="text-base font-semibold">{BRAND.name}</span>
            <span lang="hi" className="font-deva text-sm text-muted-foreground">
              {BRAND.nativeName}
            </span>
          </div>
        </div>

        <h2 id="welcome-title" className="mt-6 text-xl leading-snug font-semibold">
          {BRAND.tagline}
        </h2>

        <div className="mt-3 space-y-2 text-sm leading-relaxed text-muted-foreground">
          <p>Give Sanket an unknown radio recording (.iq, .wav, SigMF).</p>
          <p>
            It works out how it was sent: rate, modulation, interleaving, error correction, framing. Then it undoes each
            layer to recover the bits.
          </p>
          <p>Every result says how sure it is. Nothing is guessed silently, and it all runs offline on this machine.</p>
        </div>

        <p className="eyebrow mt-6">How sure, in five levels</p>
        <ul className="mt-2 space-y-1.5">
          {LEVELS.map((level) => (
            <li key={level} className="flex items-start gap-3 text-xs">
              <span className="flex w-24 shrink-0 justify-start pt-px">
                <EvidenceBadge level={level} />
              </span>
              <span className="min-w-0 text-muted-foreground">{LEVEL_INFO[level].meaning}</span>
            </li>
          ))}
        </ul>

        <div className="mt-8 flex flex-wrap items-center gap-2">
          <button
            ref={primaryRef}
            type="button"
            onClick={onTrySample}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:brightness-110"
          >
            Try a sample
          </button>
          <div className="relative">
            <span className="pointer-events-none absolute -top-5 left-0 rounded-full bg-primary px-2 py-0.5 text-[10px] leading-none font-semibold tracking-wide whitespace-nowrap text-primary-foreground uppercase">
              ★ Highly recommended if you are new here
            </span>
            <button
              type="button"
              onClick={onTakeTour}
              className="rounded-md border-2 border-primary px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-2"
            >
              Take the tour
            </button>
          </div>
          <button
            type="button"
            onClick={onSkip}
            className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground sm:ml-auto"
          >
            Skip
          </button>
        </div>
      </div>
    </div>
  )
}
