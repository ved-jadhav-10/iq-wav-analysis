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

function drawConstellation(ctx: CanvasRenderingContext2D, size: number, points: Float32Array, dark: boolean) {
  const range = 1.6
  const pad = 18
  const scale = (size - pad * 2) / (2 * range)
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

  ctx.fillStyle = cssVar('--primary')
  ctx.globalCompositeOperation = dark ? 'lighter' : 'source-over'
  ctx.globalAlpha = dark ? 0.3 : 0.22
  for (let i = 0; i < points.length; i += 2) {
    ctx.fillRect(X(points[i]) - 1, Y(points[i + 1]) - 1, 2, 2)
  }
  ctx.globalCompositeOperation = 'source-over'
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

/** Symbol-domain view for the selected detection: constellation for PSK, tone histogram for FSK. */
export function SymbolView({ detection, demo }: { detection: Detection; demo: DemoProducts }) {
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
  const height = kind === 'qpsk' ? Math.min(width, 300) : 150

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || width === 0 || kind === 'cw') return
    const ctx = setupCanvas(canvas, width, height)
    if (!ctx) return
    if (kind === 'qpsk') drawConstellation(ctx, height, demo.constellation, theme === 'dark')
    else drawInstFreq(ctx, width, height, demo.fskInstFreqHz)
  }, [kind, width, height, demo, theme])

  const symbols = demo.constellation.length / 2
  const title = kind === 'fsk' ? 'Instantaneous frequency' : 'Constellation'
  const subtitle =
    kind === 'qpsk'
      ? `${integer.format(symbols)} symbols after matched filter, Gardner timing and Costas loop`
      : kind === 'fsk'
        ? `Channelised to ${DEMO_CONFIG.fskChannel.fs / 1000} kS/s · dashed lines are the estimated tones`
        : 'Unmodulated carrier'

  return (
    <section aria-labelledby="symview-title" className="border-b px-3 pt-3 pb-3">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id="symview-title" className="text-[13px] font-semibold">
            {title} <span className="num font-normal text-subtle-foreground">· #{detection.id}</span>
          </h2>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
        {kind === 'qpsk' && (
          <span className="num shrink-0 rounded-[3px] bg-surface-2 px-1.5 py-0.5 text-2xs text-muted-foreground">
            EVM {(demo.evm * 100).toFixed(1)}&nbsp;%
          </span>
        )}
      </div>
      <div ref={wrapRef} className="flex justify-center">
        {kind === 'cw' ? (
          <p className="w-full rounded-md border border-dashed px-3 py-6 text-center text-xs text-muted-foreground">
            No symbols to plot: this is a steady carrier. Its frequency, drift and C/N0 are in the evidence below.
          </p>
        ) : (
          <canvas
            ref={canvasRef}
            style={{ width: kind === 'qpsk' ? height : width, height }}
            role="img"
            aria-label={
              kind === 'qpsk'
                ? `QPSK constellation, ${symbols} symbols, EVM ${(demo.evm * 100).toFixed(1)} percent`
                : 'Histogram of instantaneous frequency with two peaks at the FSK tones'
            }
          />
        )}
      </div>
    </section>
  )
}
