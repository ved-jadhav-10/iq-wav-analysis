import { useEffect, useRef, useState } from 'react'
import type { Detection, Eye } from '@/lib/analysis'
import { integer, signed } from '@/lib/format'
import { cssVar, useTheme } from '@/hooks/theme'
import { isPending } from '@/lib/plainHeadline'
import { InfoTip } from './InfoTip'

const FONT = '10px "IBM Plex Mono", monospace'

function setupCanvas(canvas: HTMLCanvasElement, w: number, h: number): CanvasRenderingContext2D | null {
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.round(w * dpr)
  canvas.height = Math.round(h * dpr)
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)
  return ctx
}

function drawConstellationAxes(ctx: CanvasRenderingContext2D, size: number, range: number, scale: number) {
  const cx = size / 2
  const cy = size / 2
  const X = (v: number) => cx + v * scale
  const Y = (v: number) => cy - v * scale

  ctx.strokeStyle = cssVar('--plot-grid')
  ctx.lineWidth = 1
  for (const g of [-1.5, -1, -0.5, 0.5, 1, 1.5]) {
    ctx.beginPath()
    ctx.moveTo(X(g), Y(-range))
    ctx.lineTo(X(g), Y(range))
    ctx.moveTo(X(-range), Y(g))
    ctx.lineTo(X(range), Y(g))
    ctx.stroke()
  }
  ctx.strokeStyle = cssVar('--plot-axis')
  ctx.globalAlpha = 0.6
  ctx.beginPath()
  ctx.moveTo(X(0), Y(-range))
  ctx.lineTo(X(0), Y(range))
  ctx.moveTo(X(-range), Y(0))
  ctx.lineTo(X(range), Y(0))
  ctx.stroke()
  ctx.setLineDash([2, 3])
  ctx.beginPath()
  ctx.arc(cx, cy, scale, 0, Math.PI * 2)
  ctx.stroke()
  ctx.setLineDash([])
  ctx.globalAlpha = 1

  ctx.strokeStyle = cssVar('--foreground')
  ctx.lineWidth = 1.25
  for (const [i, q] of [
    [1, 1],
    [-1, 1],
    [-1, -1],
    [1, -1],
  ]) {
    const x = X(i * Math.SQRT1_2)
    const y = Y(q * Math.SQRT1_2)
    ctx.beginPath()
    ctx.moveTo(x - 4, y)
    ctx.lineTo(x + 4, y)
    ctx.moveTo(x, y - 4)
    ctx.lineTo(x, y + 4)
    ctx.stroke()
  }

  ctx.fillStyle = cssVar('--subtle-foreground')
  ctx.font = FONT
  ctx.textAlign = 'right'
  ctx.fillText('I', size - 4, cy - 4)
  ctx.textAlign = 'left'
  ctx.fillText('Q', cx + 4, 11)
}

/** A real detection's `analysis.constellation`: symbol-spaced [I, Q] points, unit RMS. */
function drawConstellationPoints(
  ctx: CanvasRenderingContext2D,
  size: number,
  points: readonly (readonly [number, number])[],
  dark: boolean,
) {
  const range = 1.6
  const pad = 18
  const scale = (size - pad * 2) / (2 * range)
  const cx = size / 2
  const cy = size / 2
  const X = (v: number) => cx + v * scale
  const Y = (v: number) => cy - v * scale

  drawConstellationAxes(ctx, size, range, scale)

  ctx.fillStyle = cssVar('--primary')
  ctx.globalCompositeOperation = dark ? 'lighter' : 'source-over'
  ctx.globalAlpha = dark ? 0.35 : 0.28
  for (const [i, q] of points) {
    ctx.fillRect(X(i) - 1.25, Y(q) - 1.25, 2.5, 2.5)
  }
  ctx.globalCompositeOperation = 'source-over'
  ctx.globalAlpha = 1
}

/** Eye diagram: I and Q side by side, every trace overlaid, one symbol either side of the
 * symbol instant. Dashed lines mark the ideal QPSK levels; an open eye is where the traces bunch
 * at the instant and cross between. */
function drawEye(ctx: CanvasRenderingContext2D, w: number, h: number, eye: Eye, dark: boolean) {
  const gap = 12
  const padLeft = 22
  const padTop = 14
  const padBottom = 18
  const panelW = (w - gap) / 2
  const plotW = panelW - padLeft - 4
  const plotH = h - padTop - padBottom
  const range = 1.6
  ctx.font = FONT

  for (const [index, panel] of [
    { label: 'I', traces: eye.i },
    { label: 'Q', traces: eye.q },
  ].entries()) {
    const x0 = index * (panelW + gap) + padLeft
    const X = (t: number) => x0 + ((t + 1) / 2) * plotW
    const Y = (v: number) => padTop + plotH / 2 - (v / range) * (plotH / 2)

    ctx.strokeStyle = cssVar('--plot-grid')
    ctx.lineWidth = 1
    for (const t of [-1, -0.5, 0, 0.5, 1]) {
      ctx.beginPath()
      ctx.moveTo(X(t), padTop)
      ctx.lineTo(X(t), padTop + plotH)
      ctx.stroke()
    }
    ctx.strokeStyle = cssVar('--plot-axis')
    ctx.globalAlpha = 0.6
    ctx.beginPath()
    ctx.moveTo(x0, Y(0))
    ctx.lineTo(x0 + plotW, Y(0))
    ctx.stroke()
    ctx.setLineDash([2, 3])
    for (const level of [-Math.SQRT1_2, Math.SQRT1_2]) {
      ctx.beginPath()
      ctx.moveTo(x0, Y(level))
      ctx.lineTo(x0 + plotW, Y(level))
      ctx.stroke()
    }
    ctx.setLineDash([])
    ctx.globalAlpha = 1

    ctx.strokeStyle = cssVar('--primary')
    ctx.lineWidth = 1
    ctx.globalCompositeOperation = dark ? 'lighter' : 'source-over'
    ctx.globalAlpha = dark ? 0.16 : 0.12
    for (const trace of panel.traces) {
      ctx.beginPath()
      trace.forEach((v, k) => {
        const px = X(-1 + k / eye.samplesPerSymbol)
        if (k === 0) ctx.moveTo(px, Y(v))
        else ctx.lineTo(px, Y(v))
      })
      ctx.stroke()
    }
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1

    ctx.fillStyle = cssVar('--subtle-foreground')
    ctx.textAlign = 'center'
    for (const t of [-1, 0, 1]) ctx.fillText(t === 0 ? '0' : signed(t, 0), X(t), h - 5)
    ctx.textAlign = 'left'
    ctx.fillText(panel.label, index * (panelW + gap) + 2, padTop + 8)
  }
}

function emptyMessage(detection: Detection): string {
  if (detection.kind === 'cw') {
    return 'No symbols to plot: this is a steady carrier. Its frequency, drift and C/N0 are in the evidence below.'
  }
  if (detection.kind === 'analog') {
    return 'No symbols to plot: this is an analog signal, kept out of the digital chain. See the evidence below.'
  }
  if (detection.kind === 'fsk') {
    return 'No constellation: non-coherent FSK decides each symbol by tone energy. Tone spacing and timing are in the evidence below.'
  }
  if (isPending(detection)) {
    return 'Analysing this signal. Its symbols appear here once timing and carrier recovery have run.'
  }
  const reason = detection.noFramesReason ?? detection.noSearchReason
  const settle =
    ' A stronger or longer capture, or an analyst-entered symbol rate, would give the receiver something to lock to.'
  return reason
    ? `No symbols to plot. ${reason.trim()}${/[.!?]$/.test(reason.trim()) ? '' : '.'}${settle}`
    : `No symbols were recovered for this detection (the signal was not locked to a symbol rate and carrier).${settle}`
}

/** Symbol-domain view for the selected detection: the constellation (or, on the toggle, the eye
 * diagram) for a linear signal, and the honest reason there is nothing to plot for the rest. */
export function SymbolView({ detection }: { detection: Detection }) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [width, setWidth] = useState(0)
  const [view, setView] = useState<'constellation' | 'eye'>('constellation')
  const { theme } = useTheme()

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const kind = detection.kind
  const hasCanvas = kind === 'psk' && detection.constellation.length > 0
  // A real detection may carry an eye.
  const eye = kind === 'psk' ? (detection.eye ?? null) : null
  const showEye = eye !== null && view === 'eye'
  const height = showEye ? 180 : kind === 'psk' ? Math.min(width, 300) : 150

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || width === 0 || !hasCanvas) return
    const canvasW = !showEye ? height : width
    const ctx = setupCanvas(canvas, canvasW, height)
    if (!ctx) return
    if (showEye && eye) drawEye(ctx, width, height, eye, theme === 'dark')
    else drawConstellationPoints(ctx, height, detection.constellation, theme === 'dark')
  }, [width, height, theme, hasCanvas, detection.constellation, showEye, eye])

  const symbols = detection.constellation.length
  const title = showEye ? 'Eye diagram' : kind === 'psk' ? 'Constellation' : 'Symbols'
  const subtitle = showEye
    ? `${integer.format(eye?.i.length ?? 0)} symbols overlaid, one symbol either side of the instant, after phase correction`
    : kind === 'psk' && hasCanvas
      ? `${integer.format(symbols)} symbols after sync and phase correction`
      : detection.headline

  return (
    <section aria-labelledby="symview-title" data-tour="symbols" className="border-b px-3 pt-3 pb-3">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id="symview-title" className="flex items-center gap-1.5 text-[13px] font-semibold">
            {title}
            {kind === 'psk' && <InfoTip term={showEye ? 'eye' : 'constellation'} />}
          </h2>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
        {eye && (
          <div role="radiogroup" aria-label="Symbol view" className="flex shrink-0 gap-1">
            {(['constellation', 'eye'] as const).map((id) => (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={view === id}
                onClick={() => setView(id)}
                className={`rounded-md border px-1.5 py-0.5 text-2xs font-medium ${
                  view === id
                    ? 'border-primary bg-surface-2 text-foreground'
                    : 'border-border-strong text-muted-foreground hover:bg-background hover:text-foreground'
                }`}
              >
                {id === 'eye' ? 'Eye' : 'Constellation'}
              </button>
            ))}
          </div>
        )}
      </div>
      <div ref={wrapRef} className="flex justify-center w-full min-w-0 overflow-hidden">
        {hasCanvas ? (
          <canvas
            ref={canvasRef}
            style={{ width: !showEye ? height : width, height, maxWidth: '100%' }}
            className="block"
            role="img"
            aria-label={
              showEye
                ? `${detection.label} eye diagram, I and Q, ${eye?.i.length ?? 0} traces`
                : `${detection.label} constellation, ${symbols} symbols`
            }
          />
        ) : (
          <p className="w-full rounded-md border border-dashed px-3 py-6 text-center text-xs text-muted-foreground">
            {emptyMessage(detection)}
          </p>
        )}
      </div>
    </section>
  )
}
