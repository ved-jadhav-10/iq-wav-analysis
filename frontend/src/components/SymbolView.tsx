import { useEffect, useRef, useState } from 'react'
import type { Detection } from '@/data/demoAnalysis'
import { DEMO_CONFIG, type DemoProducts } from '@/lib/demoSignal'
import { integer, signed } from '@/lib/format'
import { cssVar, useTheme } from '@/hooks/theme'

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

/** The demo's own (larger, phase-jittered) point cloud: interleaved I, Q. */
function drawConstellation(ctx: CanvasRenderingContext2D, size: number, points: Float32Array, dark: boolean) {
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
  ctx.globalAlpha = dark ? 0.3 : 0.22
  for (let i = 0; i < points.length; i += 2) {
    ctx.fillRect(X(points[i]) - 1, Y(points[i + 1]) - 1, 2, 2)
  }
  ctx.globalCompositeOperation = 'source-over'
  ctx.globalAlpha = 1
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

function drawInstFreq(ctx: CanvasRenderingContext2D, w: number, h: number, values: Float32Array) {
  const lim = 15_000
  const nBins = 90
  const counts = new Float64Array(nBins)
  for (const v of values) {
    const b = Math.floor(((v + lim) / (2 * lim)) * nBins)
    if (b >= 0 && b < nBins) counts[b]++
  }
  const max = Math.max(...counts)
  const padX = 10
  const padTop = 14
  const padBottom = 20
  const plotW = w - padX * 2
  const plotH = h - padTop - padBottom
  const X = (f: number) => padX + ((f + lim) / (2 * lim)) * plotW

  ctx.strokeStyle = cssVar('--plot-grid')
  ctx.fillStyle = cssVar('--subtle-foreground')
  ctx.font = FONT
  ctx.textAlign = 'center'
  for (let f = -15_000; f <= 15_000; f += 5_000) {
    ctx.beginPath()
    ctx.moveTo(X(f), padTop)
    ctx.lineTo(X(f), padTop + plotH)
    ctx.stroke()
    ctx.fillText(signed(f / 1000, 0), X(f), h - 6)
  }

  ctx.fillStyle = cssVar('--primary')
  const barW = plotW / nBins
  for (let b = 0; b < nBins; b++) {
    const bh = (counts[b] / max) * plotH
    ctx.fillRect(padX + b * barW + 0.5, padTop + plotH - bh, Math.max(1, barW - 1), bh)
  }

  const dev = DEMO_CONFIG.fsk.deviation
  ctx.strokeStyle = cssVar('--ev-estimated')
  ctx.fillStyle = cssVar('--ev-estimated')
  ctx.setLineDash([3, 3])
  for (const f of [-dev, dev]) {
    ctx.beginPath()
    ctx.moveTo(X(f), padTop - 4)
    ctx.lineTo(X(f), padTop + plotH)
    ctx.stroke()
    ctx.fillText(`${signed(f / 1000, 1)} kHz`, X(f), padTop - 5)
  }
  ctx.setLineDash([])
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
  return (
    detection.noFramesReason ??
    detection.noSearchReason ??
    'No symbols were recovered for this detection.'
  )
}

/** Symbol-domain view for the selected detection: constellation for PSK, tone histogram for FSK
 * (demo only - a real FSK detection carries no plot data yet), nothing to plot otherwise. `demo` is only
 * present on the demo path, whose synthetic constellation/instantaneous-frequency arrays have
 * more points and simulated timing/carrier recovery than the contract's `constellation` field
 * carries for a real detection. */
export function SymbolView({ detection, demo }: { detection: Detection; demo?: DemoProducts }) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [width, setWidth] = useState(0)
  const { theme } = useTheme()

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const kind = detection.kind
  const hasFskHistogram = kind === 'fsk' && !!demo
  const hasCanvas = kind === 'psk' || hasFskHistogram
  const height = kind === 'psk' ? Math.min(width, 300) : 150

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || width === 0 || !hasCanvas) return
    const canvasW = kind === 'psk' ? height : width
    const ctx = setupCanvas(canvas, canvasW, height)
    if (!ctx) return
    if (kind === 'psk') {
      if (demo) drawConstellation(ctx, height, demo.constellation, theme === 'dark')
      else drawConstellationPoints(ctx, height, detection.constellation, theme === 'dark')
    } else if (hasFskHistogram && demo) {
      drawInstFreq(ctx, width, height, demo.fskInstFreqHz)
    }
  }, [kind, width, height, demo, theme, hasCanvas, hasFskHistogram, detection.constellation])

  const symbols = demo ? demo.constellation.length / 2 : detection.constellation.length
  const title = kind === 'psk' ? 'Constellation' : hasFskHistogram ? 'Instantaneous frequency' : 'Symbols'
  const subtitle = demo
    ? kind === 'psk'
      ? `${integer.format(symbols)} symbols after matched filter, Gardner timing and Costas loop`
      : hasFskHistogram
        ? `Channelised to ${DEMO_CONFIG.fskChannel.fs / 1000} kS/s · dashed lines are the estimated tones`
        : 'Unmodulated carrier'
    : kind === 'psk'
      ? `${integer.format(symbols)} symbols after sync and phase correction`
      : detection.headline

  return (
    <section aria-labelledby="symview-title" className="border-b px-3 pt-3 pb-3">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id="symview-title" className="text-[13px] font-semibold">
            {title}
          </h2>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
        {kind === 'psk' && demo && (
          <span className="num shrink-0 rounded-[3px] bg-surface-2 px-1.5 py-0.5 text-2xs text-muted-foreground">
            EVM {(demo.evm * 100).toFixed(1)}&nbsp;%
          </span>
        )}
      </div>
      <div ref={wrapRef} className="flex justify-center w-full min-w-0 overflow-hidden">
        {hasCanvas ? (
          <canvas
            ref={canvasRef}
            style={{ width: kind === 'psk' ? height : width, height, maxWidth: '100%' }}
            className="block"
            role="img"
            aria-label={
              kind === 'psk'
                ? `${detection.label} constellation, ${symbols} symbols`
                : 'Histogram of instantaneous frequency with two peaks at the FSK tones'
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
