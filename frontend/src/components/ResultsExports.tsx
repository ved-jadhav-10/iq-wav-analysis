import { useEffect, useState } from 'react'
import { Download, Save, X } from 'lucide-react'
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

/** The top bar's results downloads, and Save as SigMF for a raw file. The outcome of a save is
 * a short message under the bar: it clears itself, or is dismissed, and never blocks anything. */
export function ResultsExports({ resultsUrl, sigmf, onSaveSigmf }: Props) {
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)

  useEffect(() => {
    if (!message) return
    const timer = setTimeout(() => setMessage(null), SAVE_MESSAGE_MS)
    return () => clearTimeout(timer)
  }, [message])

  async function save() {
    setSaving(true)
    setMessage(null)
    try {
      setMessage({ ok: true, text: `Saved ${await onSaveSigmf()}` })
    } catch (error) {
      setMessage({ ok: false, text: `Not saved: ${error instanceof Error ? error.message : String(error)}` })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="relative flex shrink-0 items-center gap-1 text-xs text-muted-foreground max-md:hidden">
      <Download className="size-3.5" aria-hidden />
      <span className="max-xl:sr-only">Results</span>
      {resultLinks(sigmf).map((f) => (
        <a
          key={f.format}
          href={resultsUrl(f.format)}
          download
          title={f.hint}
          className="whitespace-nowrap rounded-md border border-border-strong px-1.5 py-0.5 text-2xs font-medium uppercase hover:bg-surface-2 hover:text-foreground"
        >
          {f.label}
        </a>
      ))}
      {canSaveSigmf(sigmf) && (
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          title={SAVE_SIGMF_HINT}
          className="flex items-center gap-1 whitespace-nowrap rounded-md border border-border-strong px-1.5 py-0.5 text-2xs font-medium uppercase hover:bg-surface-2 hover:text-foreground disabled:opacity-40"
        >
          <Save className="size-3" aria-hidden />
          {saving ? 'Saving…' : 'Save as SigMF'}
        </button>
      )}
      {message && (
        <div
          role={message.ok ? 'status' : 'alert'}
          className={`absolute top-full right-0 z-20 mt-2 flex max-w-sm items-start gap-2 rounded-md border bg-surface-2 px-2.5 py-1.5 text-xs shadow-lg ${
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
