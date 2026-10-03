import { useCallback, useRef, useState, type FormEvent } from 'react'
import { ChevronDown, FolderOpen, Loader2, Upload } from 'lucide-react'
import { useDismiss } from '@/hooks/useDismiss'

interface Props {
  opening: boolean
  /** `sequence` reads numbered files (rec_000, rec_001, ...) as one recording. */
  onOpen: (path: string, sequence: boolean) => void
  /** Files chosen from the picker (a SigMF pair arrives as two); dropped files reach App directly. */
  onUpload: (files: File[]) => void
}

/** One "Open" dropdown for everything that brings a recording in: choose files, or a path on this
 * machine (optionally a numbered sequence read as one recording). Dropping files on the window
 * works without it. */
export function OpenMenu({ opening, onOpen, onUpload }: Props) {
  const [open, setOpen] = useState(false)
  const [path, setPath] = useState('')
  const [sequence, setSequence] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const close = useCallback(() => setOpen(false), [])
  useDismiss(open, root, close)

  function submit(e: FormEvent) {
    e.preventDefault()
    const trimmed = path.trim()
    if (!trimmed || opening) return
    setOpen(false)
    onOpen(trimmed, sequence)
  }

  return (
    <div ref={root} data-tour="open" className="relative flex shrink-0 items-center">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-controls="open-menu"
        title="Open a recording: choose files, or type a path"
        className="flex items-center gap-1 rounded-md border border-border-strong px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground"
      >
        {opening ? <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden /> : <FolderOpen className="size-3.5" aria-hidden />}
        <span className="max-sm:sr-only">{opening ? 'Opening…' : 'Open'}</span>
        <ChevronDown className="size-3" aria-hidden />
      </button>
      {open && (
        <div
          id="open-menu"
          role="dialog"
          aria-label="Open a recording"
          className="absolute top-full left-0 z-30 mt-2 flex w-80 max-w-[calc(100vw-1.5rem)] max-xl:fixed max-xl:top-[3.25rem] max-xl:left-3 max-xl:mt-0 flex-col gap-3 rounded-md border border-border-strong bg-surface-2 p-3 shadow-lg"
        >
          <label
            className={`flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-medium text-primary-foreground focus-within:ring-2 focus-within:ring-ring ${
              opening ? 'opacity-50' : 'cursor-pointer hover:opacity-90'
            }`}
            title="Copy recording files into the workspace and open them"
          >
            <Upload className="size-3.5" aria-hidden />
            Choose files…
            <input
              type="file"
              multiple
              disabled={opening}
              className="sr-only"
              aria-label="Upload recording files"
              onChange={(e) => {
                const files = Array.from(e.target.files ?? [])
                e.target.value = '' // so choosing the same file again fires change
                if (files.length === 0) return
                setOpen(false)
                onUpload(files)
              }}
            />
          </label>
          <p className="text-center text-2xs text-muted-foreground">or drop files anywhere on the window</p>
          <form onSubmit={submit} className="flex flex-col gap-2 border-t pt-3">
            <label htmlFor="open-path" className="text-2xs font-medium text-muted-foreground">
              Path on this machine (a file or a folder)
            </label>
            <div className="flex gap-1.5">
              <input
                id="open-path"
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="Open a recording by path…"
                className="min-w-0 flex-1 rounded-md border border-border-strong bg-surface px-2 py-1 text-xs text-foreground placeholder:text-subtle-foreground"
              />
              <button
                type="submit"
                disabled={opening || !path.trim()}
                className="shrink-0 rounded-md border border-border-strong px-2.5 py-1 text-xs font-medium text-foreground enabled:hover:bg-surface disabled:opacity-40"
              >
                Open
              </button>
            </div>
            <label
              className="flex items-center gap-1.5 text-2xs text-muted-foreground"
              title="Read numbered files (rec_000.cu8, rec_001.cu8, ...) as one recording. A folder is opened as a list of its recordings."
            >
              <input type="checkbox" checked={sequence} onChange={(e) => setSequence(e.target.checked)} />
              Join numbered files (rec_000, rec_001, …) as one recording
            </label>
          </form>
        </div>
      )}
    </div>
  )
}
