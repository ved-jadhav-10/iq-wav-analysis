import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { RotateCcw } from 'lucide-react'
import { useTheme } from '@/hooks/theme'
import { buildLut, COLORMAPS, themedStops, type ColormapName } from '@/lib/colormaps'
import type { DetectionMarker } from '@/lib/detections'
import { decimalsFor, niceTicks, signed } from '@/lib/format'
import { clampView, zoomAxis, type View } from '@/lib/view'
import { createWaterfallGl, type WaterfallGl } from '@/lib/waterfallGl'
import { axisUnits, type WaterfallSource } from '@/lib/waterfallSource'
import { LEVEL_BORDER, LEVEL_TEXT } from './levelStyles'

interface Props {
  source: WaterfallSource
  full: View
  view: View
  onViewChange: (v: View) => void
  detections: DetectionMarker[]
  selectedId: number
  onSelect: (id: number) => void
}

interface Hover {
  x: number
  y: number
  t: number
  f: number
  db: number
}

const COLORMAP_NAMES = Object.keys(COLORMAPS) as ColormapName[]

export function Waterfall({ source, full, view, onViewChange, detections, selectedId, onSelect }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const plotRef = useRef<HTMLDivElement>(null)
  const glRef = useRef<WaterfallGl | null>(null)
  const viewRef = useRef(view)
  const onViewChangeRef = useRef(onViewChange)
  const dragRef = useRef<{ x: number; y: number; v: View } | null>(null)

  const [glError, setGlError] = useState<string | null>(null)
  const { theme } = useTheme()
  const [cmap, setCmap] = useState<ColormapName>('sanket')
  const [floorDb, setFloorDb] = useState(() => Math.round(source.dbMin + 6))
  const [ceilDb, setCeilDb] = useState(source.dbMax)
  const [size, setSize] = useState({ w: 0, h: 0 })
  const [hover, setHover] = useState<Hover | null>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    viewRef.current = view
    onViewChangeRef.current = onViewChange
  })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    let gl: WaterfallGl | null = null
    let failure: string | null = null
    try {
      gl = createWaterfallGl(canvas, source.tile, source.bins, source.rows)
      if (!gl) failure = 'WebGL2 is not available in this browser, so the waterfall cannot be drawn.'
    } catch (e) {
      failure = e instanceof Error ? e.message : String(e)
    }
    glRef.current = gl
    queueMicrotask(() => setGlError(failure))
    return () => {
      gl?.dispose()
      glRef.current = null
    }
  }, [source])

  useEffect(() => {
    glRef.current?.setLut(buildLut(cmap, theme))
  }, [cmap, source, theme])

  useEffect(() => {
    const el = plotRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      // Ignore a zero-height report (the plot is briefly unlaid out) and anything taller than the
      // window. The canvas is absolutely positioned with `size-full`, so if the plot's own height
      // is ever auto, `height: 100%` resolves against the canvas's `height` attribute instead -
      // which makes the plot size itself, and the measurement then confirms it. Bounding here
      // breaks that loop instead of letting the plot stick at whatever it was first measured at.
      const h = entry.contentRect.height
      if (h === 0 || h > window.innerHeight * 4) return
      setSize({ w: entry.contentRect.width, h })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    const gl = glRef.current
    if (!canvas || !gl || size.w === 0 || size.h === 0) return
    const dpr = window.devicePixelRatio || 1
    const w = Math.round(size.w * dpr)
    const h = Math.round(size.h * dpr)
    if (canvas.width !== w) canvas.width = w
    if (canvas.height !== h) canvas.height = h
    const fSpan = full.f1 - full.f0
    const dbSpan = source.dbMax - source.dbMin
    gl.draw(
      [(view.f0 - full.f0) / fSpan, (view.f1 - full.f0) / fSpan, view.t0 / full.t1, view.t1 / full.t1],
      [(floorDb - source.dbMin) / dbSpan, (ceilDb - source.dbMin) / dbSpan],
    )
  }, [view, floorDb, ceilDb, cmap, theme, size, source, full])

  useEffect(() => {
    const el = plotRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const v = viewRef.current
      const delta = e.deltaY || e.deltaX
      const factor = Math.exp(delta * 0.0015)
      if (e.shiftKey) {
        const anchor = v.f0 + ((e.clientX - rect.left) / rect.width) * (v.f1 - v.f0)
        const [f0, f1] = zoomAxis(v.f0, v.f1, anchor, factor)
        onViewChangeRef.current(clampView({ ...v, f0, f1 }, full))
      } else {
        const anchor = v.t0 + ((e.clientY - rect.top) / rect.height) * (v.t1 - v.t0)
        const [t0, t1] = zoomAxis(v.t0, v.t1, anchor, factor)
        onViewChangeRef.current(clampView({ ...v, t0, t1 }, full))
      }
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [full])

  function readout(clientX: number, clientY: number): Hover | null {
    const el = plotRef.current
    if (!el) return null
    const rect = el.getBoundingClientRect()
    const x = clientX - rect.left
    const y = clientY - rect.top
    const f = view.f0 + (x / rect.width) * (view.f1 - view.f0)
    const t = view.t0 + (y / rect.height) * (view.t1 - view.t0)
    const col = Math.min(source.bins - 1, Math.max(0, Math.floor(((f - full.f0) / (full.f1 - full.f0)) * source.bins)))
    const row = Math.min(source.rows - 1, Math.max(0, Math.floor((t / full.t1) * source.rows)))
    const q = source.tile[row * source.bins + col]
    return { x, y, t, f, db: source.dbMin + (q / 255) * (source.dbMax - source.dbMin) }
  }

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    if (e.button !== 0 || (e.target as HTMLElement).closest('[data-detection]')) return
    e.currentTarget.setPointerCapture(e.pointerId)
    dragRef.current = { x: e.clientX, y: e.clientY, v: view }
    setDragging(true)
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current
    if (drag) {
      const rect = e.currentTarget.getBoundingClientRect()
      const df = -((e.clientX - drag.x) / rect.width) * (drag.v.f1 - drag.v.f0)
      const dt = -((e.clientY - drag.y) / rect.height) * (drag.v.t1 - drag.v.t0)
      onViewChange(
        clampView({ t0: drag.v.t0 + dt, t1: drag.v.t1 + dt, f0: drag.v.f0 + df, f1: drag.v.f1 + df }, full),
      )
    }
    setHover(readout(e.clientX, e.clientY))
  }

  function onPointerUp(e: PointerEvent<HTMLDivElement>) {
    dragRef.current = null
    setDragging(false)
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId)
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const tSpan = view.t1 - view.t0
    const fSpan = view.f1 - view.f0
    const tMid = (view.t0 + view.t1) / 2
    const fMid = (view.f0 + view.f1) / 2
    let next: View | null = null
    switch (e.key) {
      case 'ArrowLeft':
        next = { ...view, f0: view.f0 - fSpan * 0.1, f1: view.f1 - fSpan * 0.1 }
        break
      case 'ArrowRight':
        next = { ...view, f0: view.f0 + fSpan * 0.1, f1: view.f1 + fSpan * 0.1 }
        break
      case 'ArrowUp':
        next = { ...view, t0: view.t0 - tSpan * 0.1, t1: view.t1 - tSpan * 0.1 }
        break
      case 'ArrowDown':
        next = { ...view, t0: view.t0 + tSpan * 0.1, t1: view.t1 + tSpan * 0.1 }
        break
      case '+':
      case '=':
      case '-':
      case '_': {
        const factor = e.key === '-' || e.key === '_' ? 1.25 : 0.8
        if (e.shiftKey && (e.key === '_' || e.key === '+')) {
          const [f0, f1] = zoomAxis(view.f0, view.f1, fMid, factor)
          next = { ...view, f0, f1 }
        } else {
          const [t0, t1] = zoomAxis(view.t0, view.t1, tMid, factor)
          next = { ...view, t0, t1 }
        }
        break
      }
      case '0':
      case 'Escape':
        next = full
        break
    }
    if (next) {
      e.preventDefault()
      onViewChange(clampView(next, full))
    }
  }

  const units = axisUnits(source)
  const tTicks = useMemo(
    () => niceTicks(view.t0 * units.timeMul, view.t1 * units.timeMul, Math.max(3, Math.floor(size.h / 56))),
    [view.t0, view.t1, size.h, units.timeMul],
  )
  const tDecimals = decimalsFor(tTicks.step)
  const isFull = view.t0 === full.t0 && view.t1 === full.t1 && view.f0 === full.f0 && view.f1 === full.f1

  return (
    <section aria-labelledby="wf-title" className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-3 py-2">
        <div className="mr-auto min-w-0">
          <h2 id="wf-title" className="text-[13px] font-semibold">
            Waterfall
          </h2>
          <p className="truncate text-xs text-muted-foreground">
            Δf from capture centre (centre frequency unknown) · level in dB, relative and uncalibrated
          </p>
        </div>

        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          Colormap
          <select
            value={cmap}
            onChange={(e) => setCmap(e.target.value as ColormapName)}
            className="rounded-md border border-border-strong bg-surface px-1.5 py-0.5 text-xs text-foreground"
          >
            {COLORMAP_NAMES.map((n) => (
              <option key={n} value={n}>
                {COLORMAPS[n].label}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span aria-hidden>Range</span>
          <input
            id="wf-floor"
            aria-label="Floor"
            type="range"
            min={source.dbMin}
            max={ceilDb - 3}
            step={1}
            value={floorDb}
            onChange={(e) => setFloorDb(Number(e.target.value))}
            className="w-20"
          />
          <span
            className="h-2 w-16 rounded-[2px]"
            style={{ background: `linear-gradient(to right, ${themedStops(cmap, theme).join(',')})` }}
            aria-hidden
          />
          <input
            id="wf-ceil"
            type="range"
            min={floorDb + 3}
            max={source.dbMax}
            step={1}
            value={ceilDb}
            onChange={(e) => setCeilDb(Number(e.target.value))}
            className="w-20"
            aria-label="Ceiling"
          />
          <span className="num w-[11ch] text-foreground">
            {signed(floorDb, 0)}…{signed(ceilDb, 0)} dB
          </span>
        </div>

        <button
          type="button"
          onClick={() => onViewChange(full)}
          disabled={isFull}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground enabled:hover:bg-surface-2 enabled:hover:text-foreground disabled:opacity-40"
        >
          <RotateCcw className="size-3.5" aria-hidden />
          Reset view
        </button>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[44px_minmax(0,1fr)]">
        <div className="relative border-r" aria-hidden>
          <span className="absolute top-1 right-1.5 text-2xs text-subtle-foreground">{units.timeUnit}</span>
          {tTicks.ticks.map((t) => {
            const top = ((t - view.t0 * units.timeMul) / ((view.t1 - view.t0) * units.timeMul)) * 100
            if (top < 7 || top > 98) return null
            return (
              <span
                key={t}
                className="num absolute right-1.5 -translate-y-1/2 text-2xs text-muted-foreground"
                style={{ top: `${top}%` }}
              >
                {t.toFixed(tDecimals)}
              </span>
            )
          })}
        </div>

        <div
          ref={plotRef}
          tabIndex={0}
          role="img"
          aria-label={`Waterfall of the capture. Time runs downward. Arrow keys pan, plus and minus zoom time, Shift with plus or minus zooms frequency, 0 resets.`}
          title="Scroll: zoom time · Shift+scroll: zoom frequency · Drag: pan · Double-click: reset"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onPointerLeave={() => setHover(null)}
          onDoubleClick={() => onViewChange(full)}
          onKeyDown={onKeyDown}
          // The plot follows the theme: a dark ground in the dark theme and a pale one in the light
          // theme (the colormap is reversed to match), and its overlays use that theme's palette.
          className={`relative min-h-0 cursor-crosshair touch-none overflow-hidden select-none focus-visible:outline-offset-[-2px] ${theme === 'dark' ? 'bg-[#05070a]' : 'bg-[#f6f9fb]'}`}
        >
          <canvas ref={canvasRef} className="absolute inset-0 size-full" />

          {detections.flatMap((d) =>
            d.boxes.map((b, i) => {
              const fSpan = view.f1 - view.f0
              const tSpan = view.t1 - view.t0
              const left = (b.f0 - view.f0) / fSpan
              const right = (b.f1 - view.f0) / fSpan
              const top = (b.t0 - view.t0) / tSpan
              const bottom = (b.t1 - view.t0) / tSpan
              if (right < 0 || left > 1 || bottom < 0 || top > 1) return null
              const selected = d.id === selectedId
              const labelTop = top < 0 ? (-top / (bottom - top)) * 100 : 0
              return (
                <button
                  key={`${d.id}-${i}`}
                  type="button"
                  data-detection
                  onClick={() => onSelect(d.id)}
                  aria-label={`Select detection ${d.id}, ${d.label}`}
                  aria-pressed={selected}
                  style={{
                    left: `${left * 100}%`,
                    width: `${Math.max(0.4, (right - left) * 100)}%`,
                    top: `${top * 100}%`,
                    height: `${(bottom - top) * 100}%`,
                  }}
                  className={`absolute rounded-[2px] ${LEVEL_BORDER[d.level]} ${selected ? 'border-2 bg-foreground/[0.05]' : 'border border-dashed opacity-75 hover:opacity-100'}`}
                >
                  {i === 0 && (
                    <span
                      style={{ top: `calc(${labelTop}% + 2px)` }}
                      className={`num absolute left-0.5 rounded-[2px] bg-background/85 px-1 text-2xs font-semibold whitespace-nowrap ${LEVEL_TEXT[d.level]}`}
                    >
                      #{d.id} {d.label}
                    </span>
                  )}
                </button>
              )
            }),
          )}

          {hover && !dragging && (
            <>
              <div className="pointer-events-none absolute inset-y-0 w-px bg-foreground/30" style={{ left: hover.x }} />
              <div className="pointer-events-none absolute inset-x-0 h-px bg-foreground/30" style={{ top: hover.y }} />
              <div className="num pointer-events-none absolute right-2 bottom-2 rounded-[3px] bg-background/85 px-2 py-1 text-2xs text-foreground">
                Δf {signed(hover.f / units.freqDiv, units.freqDecimals)} {units.freqUnit} · t{' '}
                {(hover.t * units.timeMul).toFixed(units.timeDecimals)} {units.timeUnit} · {signed(hover.db, 1)} dB
              </div>
            </>
          )}

          {glError && (
            <div className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-foreground" role="alert">
              {glError}
            </div>
          )}
        </div>
      </div>

    </section>
  )
}
