import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Download, Save, X } from 'lucide-react'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import type { RecordingInfo } from '@/lib/api'
import { SAVE_MESSAGE_MS, SAVE_SIGMF_HINT, canSaveSigmf, resultLinks, type ResultFormat } from '@/lib/exports'

/** Below this width the downloads would crowd the open-by-path controls, so they fold into a menu. */
const INLINE_MIN_WIDTH = '(min-width: 1536px)'

interface Props {
  /** Where the finished analysis' results download from, by format. */
  resultsUrl: (format: ResultFormat) => string
  /** What SigMF output the recording supports (`RecordingInfo.sigmf`). */
  sigmf: RecordingInfo['sigmf']
  /** Writes the SigMF metadata beside a raw file and returns its path; rejects with the server's text. */
  onSaveSigmf: () => Promise<string>
}

type Message = { ok: boolean; text: string }

interface LinksProps extends Props {
  stacked: boolean
  saving: boolean
  onSave: () => void
}

/** The download links, and Save as SigMF for a raw file: in a row on a wide window, in a column
 * inside the menu on a narrower one. */
export function ResultsLinks({ resultsUrl, sigmf, stacked, saving, onSave }: Omit<LinksProps, 'onSaveSigmf'>) {
  const item = `whitespace-nowrap rounded-md border border-border-strong text-2xs font-medium uppercase hover:bg-surface-2 hover:text-foreground ${
    stacked ? 'px-2.5 py-1.5' : 'px-1.5 py-0.5'
  }`
  return (
    <>
      {resultLinks(sigmf).map((f) => (
        <a key={f.format} href={resultsUrl(f.format)} download title={f.hint} className={item}>
          {f.label}
        </a>
      ))}
      {canSaveSigmf(sigmf) && (
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          title={SAVE_SIGMF_HINT}
          className={`flex items-center gap-1 disabled:opacity-40 ${item}`}
        >
          <Save className="size-3" aria-hidden />
          {saving ? 'Saving…' : 'Save as SigMF'}
        </button>
      )}
    </>
  )
}

/** The top bar's results downloads. Wide windows show them inline; narrower ones a "Results" menu
 * (Escape, a click elsewhere or choosing something closes it). The outcome of a save is a short
 * message under the bar: it clears itself, or is dismissed, and never blocks anything. */
export function ResultsExports(props: Props) {
  const inline = useMediaQuery(INLINE_MIN_WIDTH)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!message) return
    const timer = setTimeout(() => setMessage(null), SAVE_MESSAGE_MS)
    return () => clearTimeout(timer)
  }, [message])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onPointer = (e: PointerEvent) => {
      if (e.target instanceof Node && !root.current?.contains(e.target)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [open])

  async function save() {
    setOpen(false)
    setSaving(true)
    setMessage(null)
    try {
      setMessage({ ok: true, text: `Saved ${await props.onSaveSigmf()}` })
    } catch (error) {
      setMessage({ ok: false, text: `Not saved: ${error instanceof Error ? error.message : String(error)}` })
    } finally {
      setSaving(false)
    }
  }

  const links = (stacked: boolean) => <ResultsLinks {...props} stacked={stacked} saving={saving} onSave={() => void save()} />

  return (
    <div ref={root} className="relative flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
      {inline ? (
        <>
          <Download className="size-3.5" aria-hidden />
          <span>Results</span>
          {links(false)}
        </>
      ) : (
        <>
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            aria-controls="results-menu"
            title="Download the results, the run record and SigMF metadata"
            className="flex items-center gap-1 rounded-md border border-border-strong px-2 py-1 text-xs font-medium hover:bg-surface-2 hover:text-foreground"
          >
            <Download className="size-3.5" aria-hidden />
            Results
            <ChevronDown className="size-3" aria-hidden />
          </button>
          {open && (
            <div
              id="results-menu"
              role="group"
              aria-label="Results downloads"
              className="absolute top-full right-0 z-20 mt-2 flex w-44 flex-col gap-1 rounded-md border border-border-strong bg-surface-2 p-1.5 shadow-lg"
            >
              {links(true)}
            </div>
          )}
        </>
      )}
      {message && (
        <div
          role={message.ok ? 'status' : 'alert'}
          className={`fixed top-14 right-3 z-20 flex w-max max-w-[min(24rem,calc(100vw-1.5rem))] items-start gap-2 rounded-md border bg-surface-2 px-2.5 py-1.5 text-xs shadow-lg ${
            message.ok ? 'border-border-strong text-foreground' : 'border-destructive text-destructive'
          }`}
        >
          <span className="min-w-0 break-words">{message.text}</span>
          <button
            type="button"
            onClick={() => setMessage(null)}
            aria-label="Dismiss message"
            className="shrink-0 rounded-sm text-muted-foreground hover:text-foreground"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        </div>
      )}
    </div>
  )
}
