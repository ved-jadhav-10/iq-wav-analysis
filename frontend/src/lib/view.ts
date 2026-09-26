/** Visible window of the waterfall in data units: seconds and hertz (Δf from capture centre). */
export interface View {
  t0: number
  t1: number
  f0: number
  f1: number
}

export const MIN_TIME_SPAN_S = 0.005
export const MIN_FREQ_SPAN_HZ = 2_000

export function fullView(rows: number, hop: number, fs: number): View {
  return { t0: 0, t1: (rows * hop) / fs, f0: -fs / 2, f1: fs / 2 }
}

export function clampView(v: View, full: View): View {
  const tSpan = Math.min(Math.max(v.t1 - v.t0, MIN_TIME_SPAN_S), full.t1 - full.t0)
  const fSpan = Math.min(Math.max(v.f1 - v.f0, MIN_FREQ_SPAN_HZ), full.f1 - full.f0)
  const t0 = Math.min(Math.max(v.t0, full.t0), full.t1 - tSpan)
  const f0 = Math.min(Math.max(v.f0, full.f0), full.f1 - fSpan)
  return { t0, t1: t0 + tSpan, f0, f1: f0 + fSpan }
}

/** Zoom one axis by `factor` (> 1 zooms out) keeping `anchor` fixed on screen. */
export function zoomAxis(lo: number, hi: number, anchor: number, factor: number): [number, number] {
  return [anchor - (anchor - lo) * factor, anchor + (hi - anchor) * factor]
}
