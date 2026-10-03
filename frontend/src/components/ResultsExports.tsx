import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronDown, Download, Save, X } from 'lucide-react'
import { useDismiss } from '@/hooks/useDismiss'
import type { RecordingInfo } from '@/lib/api'
import { SAVE_MESSAGE_MS, SAVE_SIGMF_HINT, canSaveSigmf, resultLinks, type ResultFormat } from '@/lib/exports'

interface Props {
  /** Where the finished analysis' results download from, by format. */
  resultsUrl: (format: ResultFormat) => string
  /** What SigMF output the recording supports (`RecordingInfo.sigmf`). */
  sigmf: RecordingInfo['sigmf']
  /** Writes the SigMF metadata beside a raw file and returns its path; rejects with the server's text. */
  onSaveSigmf: () => Promise<string>
}

type Message = { ok: boolean; text: string }

interface LinksProps extends Omit<Props, 'onSaveSigmf'> {
  saving: boolean
  onSave: () => void
}

const ITEM =
  'flex w-full flex-col items-start gap-0.5 rounded-md px-2.5 py-1.5 text-left text-xs font-medium text-foreground hover:bg-surface-2 focus-visible:bg-surface-2 disabled:opacity-40'

/** The download rows, and Save as SigMF for a raw file: one row per format with what it is for. */
export function ResultsLinks({ resultsUrl, sigmf, saving, onSave }: LinksProps) {
  return (
    <>
      {resultLinks(sigmf).map((f) => (
        <a key={f.format} href={resultsUrl(f.format)} download aria-label={f.label} title={f.hint} role="menuitem" className={ITEM}>
          {f.label}
          <span className="line-clamp-2 text-2xs font-normal text-muted-foreground">{f.hint}</span>
        </a>
      ))}
      {canSaveSigmf(sigmf) && (
        <button type="button" onClick={onSave} disabled={saving} title={SAVE_SIGMF_HINT} role="menuitem" className={ITEM}>
          <span className="flex items-center gap-1">
            <Save className="size-3" aria-hidden />
            {saving ? 'Saving…' : 'Save as SigMF'}
          </span>
          <span className="line-clamp-2 text-2xs font-normal text-muted-foreground">
            Write the metadata next to the raw file; the samples are never touched
          </span>
        </button>
      )}
    </>
  )
}

/** The top bar's results downloads. Wide windows show them inline; narrower ones a "Results" menu
 * (Escape, a click elsewhere or choosing something closes it). The outcome of a save is a short
 * message under the bar: it clears itself, or is dismissed, and never blocks anything. */
export function ResultsExports(props: Props) {
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const close = useCallback(() => setOpen(false), [])
  useDismiss(open, root, close)

  useEffect(() => {
    if (!message) return
    const timer = setTimeout(() => setMessage(null), SAVE_MESSAGE_MS)
    return () => clearTimeout(timer)
  }, [message])

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

  return (
    <div ref={root} className="relative flex shrink-0 items-center text-xs text-muted-foreground">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls="results-menu"
        title="Download the results, the run record and SigMF metadata"
        className="flex items-center gap-1 rounded-md border border-border-strong px-2 py-1 text-xs font-medium hover:bg-surface-2 hover:text-foreground"
      >
        <Download className="size-3.5" aria-hidden />
        <span className="max-sm:sr-only">Download</span>
        <ChevronDown className="size-3" aria-hidden />
      </button>
      {open && (
        <div
          id="results-menu"
          role="menu"
          aria-label="Results downloads"
          onClick={(e) => {
            if (e.target instanceof Element && e.target.closest('a')) setOpen(false)
          }}
          className="absolute top-full right-0 z-30 mt-2 flex max-h-[calc(100vh-4rem)] w-72 max-w-[calc(100vw-1.5rem)] flex-col gap-0.5 overflow-y-auto rounded-md border border-border-strong bg-surface-2 p-1.5 shadow-lg"
        >
          <ResultsLinks {...props} saving={saving} onSave={() => void save()} />
        </div>
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
