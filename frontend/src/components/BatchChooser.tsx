import { useEffect } from 'react'
import { X } from 'lucide-react'
import type { InputInfo } from '@/lib/api'

interface Props {
  /** What was opened: the folder's path. */
  source: string
  items: InputInfo[]
  onOpen: (item: InputInfo) => void
  onClose: () => void
}

/** A folder holds several recordings; pick the one to open. Each opens on its own, as any
 * recording does; the choice is the analyst's, never a guess about which file matters. */
export function BatchChooser({ source, items, onOpen, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Recordings in this folder"
        className="flex max-h-[85vh] w-full max-w-xl flex-col overflow-hidden rounded-md border border-border-strong bg-surface shadow-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold">{items.length} recordings in this folder</h2>
            <p className="num truncate text-xs text-muted-foreground" title={source}>
              {source}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <ul className="min-h-0 flex-1 overflow-y-auto p-2">
          {items.map((item) => (
            <li key={item.path}>
              <button
                type="button"
                onClick={() => onOpen(item)}
                className="flex w-full items-baseline justify-between gap-3 rounded-md px-2 py-1.5 text-left text-xs hover:bg-surface-2"
              >
                <span className="num min-w-0 truncate">{item.name}</span>
                {item.sequence && (
                  <span className="shrink-0 text-2xs text-muted-foreground uppercase">{item.files} files, one recording</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
