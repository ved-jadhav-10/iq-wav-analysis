/**
 * The per-detection analysis report: mirrors `dsp/src/dsp/report.py`'s `DetectionReport`, which
 * the backend sends as `RecordingInfo.detections[i].analysis` and the demo data also follows.
 */
import type { EvidenceLevel, StageResult } from './evidence'

export interface Hypothesis {
  layer: 'Demod' | 'Interleaver' | 'FEC' | 'Framing' | 'Match'
  candidate: string
  statistic: string
  /** Chance of the statistic under the no-structure null; null when not computed. */
  pValue: number | null
  /** The corrected acceptance threshold on pValue. */
  threshold: number
  outcome: 'accepted' | 'rejected'
  reason: string
}

export interface HypothesisSearch {
  /** Every hypothesis tried, including ones not listed in `rows`. */
  tried: number
  alpha: number
  correction: string
  smallestThreshold: number
  shuffledRuns: number
  shuffledAccepts: number
  /** Chains that passed the threshold but also passed on shuffled bits, so were not accepted. */
  shuffledBlocked?: number
  /** Branches the blind rate-1/n convolutional search ran on, and on how many it named a code. */
  blindSearched?: number
  blindIdentified?: number
  /** Known-system checks the Match stage ran (rows with layer 'Match'), corrected among themselves. */
  matchTried?: number
  rows: Hypothesis[]
}

export interface Frame {
  index: number
  startBit: number
  syncWord: string
  lengthBits: number
  crc: 'pass' | 'fail' | 'truncated'
  /** The first bytes after the sync word, space-separated. */
  headerHex: string
  /** The frame's payload bytes (CRC excluded), no spaces. */
  payloadHex: string
}

/** Eye diagram traces: the matched-filter output around a spread of symbols, from one symbol before
 * to one after, after carrier correction; each trace has `2 * samplesPerSymbol + 1` points, and
 * the samples at the symbol instants have unit RMS. */
export interface Eye {
  samplesPerSymbol: number
  i: number[][]
  q: number[][]
}

export type SignalKind = 'psk' | 'fsk' | 'cw' | 'analog' | 'unknown'

export interface DetectionReport {
  label: string
  /** Picks the symbol view: constellation for psk, instantaneous frequency for fsk, none otherwise. */
  kind: SignalKind
  level: EvidenceLevel
  headline: string
  stages: StageResult[]
  search: HypothesisSearch | null
  noSearchReason: string | null
  frames: Frame[]
  noFramesReason: string | null
  /** Symbol-spaced [I, Q] points after sync and phase correction, unit RMS, at most 2048. */
  constellation: [number, number][]
  /** Present for a linear signal whose symbols were recovered; absent or null otherwise. */
  eye?: Eye | null
}
