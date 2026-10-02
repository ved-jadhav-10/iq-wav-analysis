import type { LevelInfo, RecordingInfo } from './api'

/** What `Waterfall` and `PsdPlot` need, taken from a real recording's tile grid (`sourceFromRecording`). */
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
  /** The sample rate is UNKNOWN: frequencies are fractions of it (`fs` is 1) and time is in
   * samples, so the axes say so rather than claim Hz and seconds. */
  normalised?: boolean
}

/** How a source's frequency (Hz) and time (s) values are shown: kHz and ms for a known rate,
 * fractions of the sample rate and samples for an unknown one. */
export function axisUnits(source: { normalised?: boolean }) {
  return source.normalised
    ? { freqDiv: 1, freqUnit: '× fs', freqDecimals: 4, timeMul: 1, timeUnit: 'samples', timeDecimals: 0 }
    : { freqDiv: 1000, freqUnit: 'kHz', freqDecimals: 2, timeMul: 1000, timeUnit: 'ms', timeDecimals: 1 }
}

/** A recording whose sample rate is UNKNOWN is drawn in normalised units (`fs` 1, flagged
 * `normalised`) - never a default rate just so the waterfall has Hz (PLAN's "never assume a
 * sample rate" rule). `level`'s row span already folds into `hop`, so `fullView` sees this
 * level's own time resolution, not level 0's. */
export function sourceFromRecording(info: RecordingInfo, level: LevelInfo, grid: Uint8Array): WaterfallSource {
  const { sampleRate, freqsHz } = info
  const known = sampleRate !== null && freqsHz !== null
  return {
    fs: known ? sampleRate : 1,
    fftSize: info.fftSize,
    hop: info.hop * level.rowSpan,
    rows: level.rows,
    bins: level.cols,
    tile: grid,
    dbMin: info.dbMin,
    dbMax: info.dbMax,
    psdDb: info.psdDb,
    freqsHz: known ? freqsHz : info.freqsNorm,
    normalised: !known,
  }
}
