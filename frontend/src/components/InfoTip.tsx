import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { CircleHelp } from 'lucide-react'
import { GLOSSARY, type GlossaryEntry } from '@/lib/glossary'
import { placePopover } from '@/lib/popoverPlacement'

/** The popover's content, apart from its position, so it renders (and is tested) on its own. */
export function InfoTipBody({ entry, id }: { entry: GlossaryEntry; id: string }) {
  return (
    <>
      <span className="block font-semibold">{entry.term}</span>
      <span id={id} className="mt-0.5 block text-popover-foreground">
        {entry.short}
      </span>
      {entry.long && <span className="mt-1 block text-muted-foreground">{entry.long}</span>}
    </>
  )
}

function Tip({ term, entry }: { term: string; entry: GlossaryEntry }) {
  const [hover, setHover] = useState(false)
  const [focus, setFocus] = useState(false)
  const [pinned, setPinned] = useState(false)
  const open = hover || focus || pinned
  const button = useRef<HTMLButtonElement>(null)
  const popover = useRef<HTMLSpanElement>(null)
  const id = useId()

  const close = useCallback(() => {
    setHover(false)
    setFocus(false)
    setPinned(false)
  }, [])

  const position = useCallback(() => {
    const b = button.current
    const p = popover.current
    if (!b || !p) return
    const a = b.getBoundingClientRect()
    const at = placePopover(
      a,
      { width: p.offsetWidth, height: p.offsetHeight },
      { width: document.documentElement.clientWidth, height: document.documentElement.clientHeight },
    )
    p.style.left = `${at.left}px`
    p.style.top = `${at.top}px`
  }, [])

  // Measured before paint and written straight to the element: no state, no flash at 0,0.
  useLayoutEffect(() => {
    if (open) position()
  }, [open, position])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    const onPointer = (e: PointerEvent) => {
      if (!button.current?.contains(e.target as Node)) close()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    window.addEventListener('resize', position)
    window.addEventListener('scroll', position, true)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
      window.removeEventListener('resize', position)
      window.removeEventListener('scroll', position, true)
    }
  }, [open, close, position])

  return (
    <>
      <button
        ref={button}
        type="button"
        aria-label={`What is ${term}?`}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setFocus(true)}
        onBlur={close}
        onClick={() => {
          if (pinned) close()
          else setPinned(true)
        }}
        className="inline-flex size-3.5 shrink-0 cursor-help items-center justify-center rounded-full align-middle text-subtle-foreground hover:text-foreground focus-visible:text-foreground"
      >
        <CircleHelp className="size-3.5" aria-hidden />
      </button>
      {open &&
        createPortal(
          <span
            ref={popover}
            role="tooltip"
            style={{ left: 0, top: 0 }}
            className="pointer-events-none fixed z-50 block w-max max-w-[260px] rounded-md border border-border-strong bg-popover px-2.5 py-2 text-left text-xs leading-snug font-normal tracking-normal text-popover-foreground normal-case shadow-lg"
          >
            <InfoTipBody entry={entry} id={id} />
          </span>,
          document.body,
        )}
    </>
  )
}

/** A small "what is this?" button beside a term. Opens on hover, focus or click; closes on Esc,
 * blur or an outside click. An unknown term renders nothing. */
export function InfoTip({ term }: { term: string }) {
  const entry = GLOSSARY[term]
  if (!entry) return null
  return <Tip term={entry.term} entry={entry} />
}
