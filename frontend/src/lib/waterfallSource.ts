import type { LevelInfo, RecordingInfo } from './api'

/** What `Waterfall` and `PsdPlot` need, whichever of the demo generator or a real recording it
 * came from - `DemoProducts` already has every one of these fields (PLAN §5 M2). */
export interface WaterfallSource {
  fs: number
  fftSize: number
  hop: number
  rows: number
  bins: number
  /** rows × bins, fft-shifted, uint8-quantised dB. Row 0 is t = 0. */
  tile: Uint8Array
  dbMin: number
  dbMax: number
  psdDb: ArrayLike<number>
  freqsHz: ArrayLike<number>
}

/** `null` when the recording's sample rate is UNKNOWN: there is no Hz frequency axis to show
 * yet (never a default rate just so the waterfall has units - PLAN's "never assume a sample
 * rate" rule). `level`'s row span already folds into `hop`, so `fullView` sees this level's own
 * time resolution, not level 0's. */
export function sourceFromRecording(info: RecordingInfo, level: LevelInfo, grid: Uint8Array): WaterfallSource | null {
  if (info.sampleRate === null || info.freqsHz === null) return null
  return {
    fs: info.sampleRate,
    fftSize: info.fftSize,
    hop: info.hop * level.rowSpan,
    rows: level.rows,
    bins: level.cols,
    tile: grid,
    dbMin: info.dbMin,
    dbMax: info.dbMax,
    psdDb: info.psdDb,
    freqsHz: info.freqsHz,
  }
}
