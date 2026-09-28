import { useCallback, useEffect, useRef, useState } from 'react'

/** A draggable split between two panes, sized as a fraction of the *available* width (the container
 * minus the fixed-width columns around it).
 *
 * Pointer events rather than `mousedown`/`mousemove`, so a drag survives leaving the window and
 * works with touch and pen. Implemented here rather than pulled in as a dependency: it's small, it
 * keeps the "no network at runtime" and air-gap story, and it persists the position, which is the
 * part that actually earns its place.
 *
 * The listeners are attached in an effect instead of being handed to the caller as props: they
 * close over refs, and passing them through render is what `react-hooks/refs` is there to stop.
 * The hook owns `gutterRef` and the caller spreads it onto a focusable separator.
 */
export function useSplit(storageKey: string, defaultFraction: number, minPx = 300, leadingPx = 0) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const gutterRef = useRef<HTMLDivElement | null>(null)
  const [fraction, setFraction] = useState(() => load(storageKey, defaultFraction))
  const [width, setWidth] = useState(0)

  // Handlers read these instead of closing over state, so they can be attached once.
  const fractionRef = useRef(fraction)
  const widthRef = useRef(width)
  const leadingRef = useRef(leadingPx)
  const dragging = useRef(false)

  useEffect(() => {
    fractionRef.current = fraction
  }, [fraction])

  useEffect(() => {
    widthRef.current = width
  }, [width])

  useEffect(() => {
    leadingRef.current = leadingPx
  }, [leadingPx])

  // The container's width decides both where the gutter lands and what the minimums mean, and it
  // changes on window resize and on the display being dragged to another screen.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const measure = () => setWidth(el.getBoundingClientRect().width)
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const persist = useCallback(
    (value: number) => {
      try {
        window.localStorage.setItem(storageKey, String(value))
      } catch {
        // The split still works, it just won't survive a reload.
      }
    },
    [storageKey],
  )

  /** Keeps both panes usable: neither can be dragged down to nothing. */
  const clamp = useCallback(
    (next: number, availablePx: number) => {
      if (availablePx <= 0) return next
      const min = Math.min(minPx / availablePx, 0.45)
      return Math.min(Math.max(next, min), 1 - min)
    },
    [minPx],
  )

  // A resize can leave a stored fraction that now violates the minimums. Clamping is derived
  // during render rather than written back in an effect, so a resize can't drive a render loop.
  const available = width - leadingPx
  const safeFraction = available > 0 ? clamp(fraction, available) : fraction

  useEffect(() => {
    const el = gutterRef.current
    if (!el) return

    function onPointerDown(e: PointerEvent) {
      dragging.current = true
      el?.setPointerCapture(e.pointerId)
      e.preventDefault()
    }

    function onPointerMove(e: PointerEvent) {
      const box = containerRef.current?.getBoundingClientRect()
      if (!dragging.current || !box) return
      // The fraction is of the resizable space, so the fixed rail comes off the pointer position
      // too - otherwise the gutter would sit to the right of the cursor by the rail's width.
      const available = box.width - leadingRef.current
      if (available <= 0) return
      setFraction(clamp((e.clientX - box.left - leadingRef.current) / available, available))
    }

    function onPointerUp(e: PointerEvent) {
      if (!dragging.current) return
      dragging.current = false
      el?.releasePointerCapture(e.pointerId)
      // Persist where it landed, not where it was when the drag started.
      persist(fractionRef.current)
    }

    /** Arrow keys nudge the split, for people who can't drag a gutter. */
    function onKeyDown(e: KeyboardEvent) {
      const available = widthRef.current - leadingRef.current
      if (available <= 0) return
      const step = (e.shiftKey ? 48 : 12) / available
      if (e.key === 'ArrowLeft') setFraction(clamp(fractionRef.current - step, available))
      else if (e.key === 'ArrowRight') setFraction(clamp(fractionRef.current + step, available))
      else return
      e.preventDefault()
    }

    el.addEventListener('pointerdown', onPointerDown)
    el.addEventListener('pointermove', onPointerMove)
    el.addEventListener('pointerup', onPointerUp)
    el.addEventListener('pointercancel', onPointerUp)
    el.addEventListener('keydown', onKeyDown)
    return () => {
      el.removeEventListener('pointerdown', onPointerDown)
      el.removeEventListener('pointermove', onPointerMove)
      el.removeEventListener('pointerup', onPointerUp)
      el.removeEventListener('pointercancel', onPointerUp)
      el.removeEventListener('keydown', onKeyDown)
    }
  }, [clamp, persist])

  // Callback refs, not ref objects: passing a ref object up from a hook trips `react-hooks/refs`.
  const setContainer = useCallback((el: HTMLDivElement | null) => {
    containerRef.current = el
  }, [])
  const setGutter = useCallback((el: HTMLDivElement | null) => {
    gutterRef.current = el
  }, [])

  return { setContainer, setGutter, fraction: safeFraction, available }
}

function load(key: string, fallback: number): number {
  try {
    const raw = window.localStorage.getItem(key)
    if (raw === null) return fallback
    const value = Number(raw)
    return Number.isFinite(value) && value > 0 && value < 1 ? value : fallback
  } catch {
    return fallback
  }
}
