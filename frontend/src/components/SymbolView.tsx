import { useEffect, useRef, type ReactNode } from 'react'
import { CircleSlash, Loader2 } from 'lucide-react'
import type { Detection, Eye } from '@/lib/analysis'
import { integer, signed } from '@/lib/format'
import { cssVar, useTheme } from '@/hooks/theme'
import { useSize } from '@/hooks/useWidth'
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


/** Why there is no constellation to draw for this detection. */
function constellationReason(detection: Detection): string {
  if (detection.kind === 'cw') {
    return 'This is a steady carrier, so there are no symbols. Its frequency, drift and C/N0 are in the Evidence section.'
  }
  if (detection.kind === 'analog') {
    return 'This is an analog signal, kept out of the digital chain. See the Evidence section.'
  }
  if (detection.kind === 'fsk') {
    return 'Non-coherent FSK decides each symbol by tone energy, so there is no constellation. Tone spacing and timing are in the Evidence section.'
  }
  const reason = detection.noFramesReason ?? detection.noSearchReason
  const settle =
    ' A stronger or longer capture, or an analyst-entered symbol rate, would give the receiver something to lock to.'
  return reason
    ? `No symbols were recovered. ${reason.trim()}${/[.!?]$/.test(reason.trim()) ? '' : '.'}${settle}`
    : `No symbols were recovered (the signal was not locked to a symbol rate and carrier).${settle}`
}

/** Why there is no eye diagram to draw for this detection. */
function eyeReason(detection: Detection): string {
  if (detection.kind === 'fsk') {
    return 'An eye needs a linear (PSK/QAM) signal; FSK is decided by tone energy, not by symbol amplitude.'
  }
  if (detection.kind === 'cw') return 'This is a steady carrier: there are no symbol transitions to overlay.'
  if (detection.kind === 'analog') return 'This is an analog signal: there are no symbol transitions to overlay.'
  return `No eye was recorded because no symbols were recovered. ${constellationReason(detection)}`
}

function NotApplicable({ children }: { children: string }) {
  return (
    <div className="flex size-full flex-col items-center justify-center gap-1.5 overflow-y-auto px-4 py-3 text-center">
      <CircleSlash className="size-5 shrink-0 text-subtle-foreground" aria-hidden />
      <p className="text-xs font-medium text-muted-foreground">Not applicable</p>
      <p className="max-w-[44ch] text-xs text-subtle-foreground">{children}</p>
    </div>
  )
}

function Analysing() {
  return (
    <div role="status" className="flex size-full items-center justify-center gap-2 px-4 text-xs text-muted-foreground">
      <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />
      Analysing this signal…
    </div>
  )
}

interface CardProps {
  title: string
  tip: 'constellation' | 'eye'
  subtitle: string
  tourAnchor: string
  children: ReactNode
}

/** One plot card: a title row and a body that takes the rest of the height. The body gets a
 * definite size from the card (`min-h-0 flex-1`) and the plot inside it is absolutely positioned,
 * so a canvas can never size its own container. */
function PlotCard({ title, tip, subtitle, tourAnchor, children }: CardProps) {
  return (
    <section
      aria-label={title}
      data-tour={tourAnchor}
      className="flex min-h-0 min-w-0 flex-col border-b bg-surface last:border-b-0"
    >
      <div className="shrink-0 px-3 pt-2">
        <h2 className="flex items-center gap-1.5 text-[13px] font-semibold">
          {title}
          <InfoTip term={tip} />
        </h2>
        <p className="truncate text-2xs text-muted-foreground" title={subtitle}>
          {subtitle}
        </p>
      </div>
      <div className="relative min-h-0 flex-1">{children}</div>
    </section>
  )
}

/** The selected detection's constellation: the real symbols after timing, carrier and phase
 * recovery, or the reason there are none. */
export function ConstellationPlot({ detection }: { detection: Detection }) {
  const [boxRef, { width, height }] = useSize<HTMLDivElement>()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { theme } = useTheme()
  const hasCanvas = detection.kind === 'psk' && detection.constellation.length > 0
  const side = Math.max(0, Math.min(width, height) - 8)
  const symbols = detection.constellation.length

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || side < 40 || !hasCanvas) return
    const ctx = setupCanvas(canvas, side, side)
    if (ctx) drawConstellationPoints(ctx, side, detection.constellation, theme === 'dark')
  }, [side, theme, hasCanvas, detection.constellation])

  return (
    <PlotCard
      title="Constellation"
      tip="constellation"
      tourAnchor="constellation"
      subtitle={hasCanvas ? `${integer.format(symbols)} symbols after sync and phase correction` : detection.headline}
    >
      <div ref={boxRef} className="absolute inset-0 flex items-center justify-center overflow-hidden">
        {hasCanvas ? (
          <canvas
            ref={canvasRef}
            style={{ width: side, height: side }}
            className="block"
            role="img"
            aria-label={`${detection.label} constellation, ${symbols} symbols`}
          />
        ) : isPending(detection) ? (
          <Analysing />
        ) : (
          <NotApplicable>{constellationReason(detection)}</NotApplicable>
        )}
      </div>
    </PlotCard>
  )
}

/** The selected detection's eye diagram (I and Q overlaid over one symbol either side of the
 * symbol instant), or the reason there is none. */
export function EyePlot({ detection }: { detection: Detection }) {
  const [boxRef, { width, height }] = useSize<HTMLDivElement>()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { theme } = useTheme()
  const eye = detection.kind === 'psk' ? (detection.eye ?? null) : null
  const w = Math.max(0, width - 8)
  const h = Math.max(0, height - 8)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || w < 80 || h < 60 || !eye) return
    const ctx = setupCanvas(canvas, w, h)
    if (ctx) drawEye(ctx, w, h, eye, theme === 'dark')
  }, [w, h, theme, eye])

  return (
    <PlotCard
      title="Eye diagram"
      tip="eye"
      tourAnchor="eye"
      subtitle={
        eye
          ? `${integer.format(eye.i.length)} symbols overlaid, one symbol either side of the instant, after phase correction`
          : 'I and Q overlaid over one symbol'
      }
    >
      <div ref={boxRef} className="absolute inset-0 flex items-center justify-center overflow-hidden">
        {eye ? (
          <canvas
            ref={canvasRef}
            style={{ width: w, height: h }}
            className="block"
            role="img"
            aria-label={`${detection.label} eye diagram, I and Q, ${eye.i.length} traces`}
          />
        ) : isPending(detection) ? (
          <Analysing />
        ) : (
          <NotApplicable>{eyeReason(detection)}</NotApplicable>
        )}
      </div>
    </PlotCard>
  )
}
