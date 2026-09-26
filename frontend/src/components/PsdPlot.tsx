import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import type { Detection } from '@/data/demoAnalysis'
import type { DemoProducts } from '@/lib/demoSignal'
import { decimalsFor, signed } from '@/lib/format'
import type { View } from '@/lib/view'
import { cssVar, useTheme } from '@/hooks/theme'
import { LEVEL_CSS_VAR } from './levelStyles'

interface Props {
  demo: DemoProducts
  view: View
  detections: Detection[]
  selectedId: number
}

function withAlpha(hex: string, alpha: number): string {
  const v = parseInt(hex.replace('#', ''), 16)
  return `rgba(${(v >> 16) & 255}, ${(v >> 8) & 255}, ${v & 255}, ${alpha})`
}

const FONT = '10px "IBM Plex Mono", monospace'

/** Welch PSD sharing the waterfall's frequency window; its x-axis is the frequency axis for both. */
export function PsdPlot({ demo, view, detections, selectedId }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const plotRef = useRef<uPlot | null>(null)
  const viewRef = useRef(view)
  const { theme } = useTheme()

  useEffect(() => {
    viewRef.current = view
    plotRef.current?.setScale('x', { min: view.f0 / 1000, max: view.f1 / 1000 })
  }, [view])

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const grid = cssVar('--plot-grid')
    const axis = cssVar('--plot-axis')
    const primary = cssVar('--primary')
    const spans = detections.map((d) => ({
      id: d.id,
      color: cssVar(LEVEL_CSS_VAR[d.level]),
      f0: Math.min(...d.boxes.map((b) => b.f0)) / 1000,
      f1: Math.max(...d.boxes.map((b) => b.f1)) / 1000,
    }))

    const axisStyle = {
      stroke: axis,
      font: FONT,
      grid: { stroke: grid, width: 1 },
      ticks: { stroke: grid, width: 1, size: 3 },
    }

    const opts: uPlot.Options = {
      width: el.clientWidth,
      height: el.clientHeight,
      padding: [6, 0, 0, 0],
      legend: { show: false },
      cursor: { y: false, points: { show: false }, drag: { x: false, y: false } },
      scales: {
        x: { time: false, min: viewRef.current.f0 / 1000, max: viewRef.current.f1 / 1000 },
        y: { range: (_u, min, max) => [Math.floor(min - 2), Math.ceil(max + 3)] },
      },
      axes: [
        {
          ...axisStyle,
          size: 22,
          gap: 3,
          values: (_u, splits, _i, _space, incr) => splits.map((v) => signed(v, decimalsFor(incr))),
        },
        { ...axisStyle, size: 44, gap: 4, values: (_u, splits) => splits.map((v) => signed(v, 0)) },
      ],
      series: [{}, { stroke: primary, width: 1.25, fill: withAlpha(primary, 0.08), points: { show: false } }],
      hooks: {
        drawClear: [
          (u) => {
            const { ctx } = u
            const { top, height } = u.bbox
            for (const s of spans) {
              const x0 = u.valToPos(s.f0, 'x', true)
              const x1 = u.valToPos(s.f1, 'x', true)
              ctx.fillStyle = withAlpha(s.color, s.id === selectedId ? 0.16 : 0.06)
              ctx.fillRect(x0, top, Math.max(1, x1 - x0), height)
            }
          },
        ],
      },
    }

    const data: uPlot.AlignedData = [Array.from(demo.freqsHz, (f) => f / 1000), Array.from(demo.psdDb)]
    const plot = new uPlot(opts, data, el)
    plotRef.current = plot
    const ro = new ResizeObserver(() => plot.setSize({ width: el.clientWidth, height: el.clientHeight }))
    ro.observe(el)
    return () => {
      ro.disconnect()
      plot.destroy()
      plotRef.current = null
    }
  }, [demo, detections, selectedId, theme])

  return (
    <div className="relative h-full">
      <span className="absolute top-0.5 left-1.5 z-10 text-2xs text-subtle-foreground">dB</span>
      <span className="absolute bottom-1 left-1.5 z-10 text-2xs text-subtle-foreground">kHz</span>
      <div ref={wrapRef} className="h-full" role="img" aria-label="Power spectral density (Welch average) across the capture" />
    </div>
  )
}
