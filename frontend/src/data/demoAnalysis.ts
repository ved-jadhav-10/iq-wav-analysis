import type { Box } from '@/lib/box'
import type { EvidenceLevel, Parameter, StageResult } from '@/lib/evidence'
import { DEMO_CONFIG, mulberry32 } from '@/lib/demoSignal'

/*
 * Stage results for the synthetic demo capture. The values are consistent with the generator in
 * lib/demoSignal.ts; they stand in for the backend's /api/v1 analysis response until it exists.
 */

export type { Box }

export interface Hypothesis {
  layer: 'Interleaver' | 'FEC' | 'Framing'
  candidate: string
  statistic: string
  pValue: number | null
  threshold: number
  outcome: 'accepted' | 'rejected'
  reason: string
}

export interface HypothesisSearch {
  tried: number
  alpha: number
  correction: string
  smallestThreshold: number
  shuffledRuns: number
  shuffledAccepts: number
  rows: Hypothesis[]
}

export interface Frame {
  index: number
  startBit: number
  syncWord: string
  lengthBits: number
  crc: 'pass' | 'truncated'
  headerHex: string
}

export interface Detection {
  id: number
  label: string
  kind: 'qpsk' | 'fsk' | 'cw'
  level: EvidenceLevel
  headline: string
  boxes: Box[]
  stages: StageResult[]
  search: HypothesisSearch | null
  noSearchReason?: string
  frames: Frame[]
  noFramesReason?: string
}

export interface Assumption {
  item: string
  value: string
  level: EvidenceLevel
  note: string
}

type ParamInput = Omit<Parameter, 'evidence' | 'alternatives' | 'warnings' | 'confidence'> &
  Partial<Pick<Parameter, 'evidence' | 'alternatives' | 'warnings' | 'confidence'>>

function p(input: ParamInput): Parameter {
  return { confidence: null, evidence: [], alternatives: [], warnings: [], ...input }
}

function stage(
  id: StageResult['id'],
  name: string,
  summary: string,
  level: EvidenceLevel | null,
  parameters: Parameter[],
): StageResult {
  return { id, name, status: 'done', summary, level, parameters }
}

function notApplicable(id: StageResult['id'], name: string, summary: string): StageResult {
  return { id, name, status: 'not-applicable', summary, level: null, parameters: [] }
}

const { qpsk, fsk, cw } = DEMO_CONFIG
const durationS = DEMO_CONFIG.n / DEMO_CONFIG.fs
const qpskBw = qpsk.rs * (1 + qpsk.beta)

export const RECORDING = {
  fileName: 'demo_capture.sigmf-meta',
  sampleRateHz: DEMO_CONFIG.fs,
  durationS,
  datatype: 'cf32_le',
}

export const ASSUMPTIONS: Assumption[] = [
  { item: 'Container', value: 'SigMF 1.2', level: 'MEASURED', note: 'Parsed from demo_capture.sigmf-meta.' },
  { item: 'Datatype', value: 'cf32_le', level: 'MEASURED', note: 'core:datatype. File size is consistent with 8 bytes per sample.' },
  { item: 'Sample rate', value: '250 kS/s', level: 'MEASURED', note: 'core:sample_rate.' },
  { item: 'Duration', value: `${(durationS * 1000).toFixed(1)} ms`, level: 'MEASURED', note: '262,144 samples at the stated sample rate.' },
  {
    item: 'Centre frequency',
    value: '—',
    level: 'UNKNOWN',
    note: 'core:frequency is absent, so frequencies are shown as Δf from the capture centre. Enter it to see absolute frequencies.',
  },
  {
    item: 'IQ order',
    value: 'I/Q',
    level: 'HYPOTHESIS',
    note: 'Cannot be decided from the samples: swapping I and Q only mirrors the spectrum. Toggle it if a known carrier sits on the wrong side.',
  },
  { item: 'Clipping', value: '0.00 %', level: 'ESTIMATED', note: 'No samples at full scale.' },
  { item: 'DC offset', value: '−51.8 dB', level: 'ESTIMATED', note: 'Relative to total power; below the level where it would bias detection.' },
]

const qpskStages: StageResult[] = [
  stage('ingest', 'Ingest', 'SigMF cf32_le at 250 kS/s', 'MEASURED', [
    p({ id: 'fs', name: 'Sample rate', value: '250,000', unit: 'S/s', level: 'MEASURED', method: 'core:sample_rate in SigMF metadata' }),
  ]),
  stage('detect', 'Detect', `Burst at +40 kHz, ${Math.round(qpskBw / 100) / 10} kHz wide`, 'ESTIMATED', [
    p({
      id: 'offset',
      name: 'Centre offset',
      value: '+40.00',
      unit: 'kHz',
      level: 'ESTIMATED',
      confidence: 0.98,
      method: 'Power-weighted centroid of the detection box',
      evidence: ['OS-CFAR + hysteresis at FFT sizes 256/512/1024, merged by NMS', 'Stable to ±20 Hz across the burst'],
    }),
    p({
      id: 'obw',
      name: 'Occupied bandwidth (99 %)',
      value: (qpskBw / 1000).toFixed(1),
      unit: 'kHz',
      level: 'ESTIMATED',
      confidence: 0.95,
      method: '99 % power bandwidth from the Welch PSD',
      evidence: ['Consistent with Rs × (1 + β) from the estimate stage'],
    }),
    p({
      id: 'extent',
      name: 'Time extent',
      value: `${qpsk.t0 * 1000}–${qpsk.t1 * 1000}`,
      unit: 'ms',
      level: 'ESTIMATED',
      confidence: 0.97,
      method: 'Energy detector with 2 ms hysteresis',
    }),
  ]),
  stage('estimate', 'Estimate', '25.0 kBd, β 0.35, Es/N0 14 dB', 'ESTIMATED', [
    p({
      id: 'rs',
      name: 'Symbol rate',
      value: '25,000',
      unit: 'Bd ± 0.05 %',
      level: 'ESTIMATED',
      confidence: 0.97,
      method: '|x|² spectral line, refined by cyclic autocorrelation, confirmed by FAM',
      evidence: ['|x|² line at 25.000 kHz, 31 dB above its neighbourhood', 'Cyclic autocorrelation peak at α = 25.001 kHz', 'FAM confirms; no competing cycle frequency'],
    }),
    p({
      id: 'beta',
      name: 'Roll-off',
      value: '0.35',
      level: 'ESTIMATED',
      confidence: 0.86,
      method: 'Least-squares fit of the RRC PSD, snapped to a standard value',
      evidence: ['Raw fit 0.34; nearest standard value 0.35', 'Cyclic harmonics indicate RRC, not rectangular, pulses'],
      alternatives: [{ value: '0.25', confidence: 0.11 }],
    }),
    p({
      id: 'snr',
      name: 'Es/N0',
      value: '14.1',
      unit: 'dB ± 0.6',
      level: 'ESTIMATED',
      confidence: 0.9,
      method: 'Three estimators; their agreement sets the confidence',
      evidence: ['PSD in-band vs guard: 14.3 dB', 'M2M4 (valid for PSK): 13.9 dB', 'Eigenvalue / MDL: 14.0 dB, one source'],
    }),
    p({
      id: 'cfo',
      name: 'Residual CFO',
      value: '+12',
      unit: 'Hz',
      level: 'ESTIMATED',
      confidence: 0.88,
      method: '4th-power spectral line after coarse centring',
    }),
  ]),
  stage('sync', 'Sync', 'Timing and carrier locked', 'VERIFIED', [
    p({
      id: 'timing',
      name: 'Timing recovery',
      value: 'Locked',
      level: 'ESTIMATED',
      confidence: 0.96,
      method: 'RRC matched filter → Gardner detector → Farrow interpolator',
      evidence: ['Lock after 212 symbols', 'Timing-error variance settles to 0.004 T²'],
    }),
    p({
      id: 'phase',
      name: 'Phase ambiguity',
      value: '0°',
      level: 'VERIFIED',
      confidence: 1,
      method: 'Four rotations carried forward, resolved downstream',
      evidence: ['Only the 0° rotation yields the CCSDS ASM and passing CRCs'],
    }),
  ]),
  stage('classify', 'Classify', 'QPSK, confirmed by decode', 'VERIFIED', [
    p({
      id: 'mod',
      name: 'Modulation',
      value: 'QPSK',
      level: 'VERIFIED',
      confidence: 0.93,
      method: 'Cumulant rules and 1-D CNN, fused; promoted by downstream proof',
      evidence: ['Rules: C40 = −0.98, C42 = −0.99 (QPSK: −1, −1)', 'CNN: QPSK 0.93 over 64 windows', 'Promoted to VERIFIED: 20 of 20 complete frames pass CRC-16'],
      alternatives: [
        { value: '8PSK', confidence: 0.05 },
        { value: 'OQPSK', confidence: 0.02 },
      ],
    }),
  ]),
  stage('demod', 'Demodulate', '43,488 soft bits, EVM 20 %', 'ESTIMATED', [
    p({
      id: 'evm',
      name: 'EVM',
      value: '19.9',
      unit: '% rms',
      level: 'ESTIMATED',
      confidence: 0.94,
      method: 'Error vector against the nearest ideal QPSK point',
      evidence: ['Consistent with Es/N0 14.1 dB (expected 19.8 %)'],
    }),
    p({ id: 'llr', name: 'Soft bits', value: '43,488', unit: 'LLRs', level: 'MEASURED', method: 'Gray demapping to log-likelihood ratios' }),
  ]),
  stage('deinterleave', 'De-interleave', 'Block 8 × 16', 'VERIFIED', [
    p({
      id: 'interleaver',
      name: 'Interleaver',
      value: 'Block 8 × 16',
      unit: 'period 128 bits',
      level: 'VERIFIED',
      confidence: 1,
      method: 'GF(2) rank-drop scan, KS test on rank distributions',
      evidence: ['Rank drop at every multiple of 128 bits; largest at offset 312', 'KS test p = 2 × 10⁻¹⁹ against the random-data null', 'CRC passes only after de-interleaving'],
    }),
  ]),
  stage('fec', 'FEC', 'Conv K=7 r½ (171,133)₈', 'VERIFIED', [
    p({
      id: 'code',
      name: 'Code',
      value: 'Convolutional K=7, r = ½',
      unit: '(171, 133)₈',
      level: 'VERIFIED',
      confidence: 1,
      method: 'Dual-code parity checks via the shared GF(2) kernel; soft Viterbi decode',
      evidence: ['Parity checks hold on 98.7 % of rows (random: 50 %)', 'Re-encoded bits match the hard decisions at BER 1.9 × 10⁻², consistent with EVM', 'No puncturing: the rate-½ mother code fits directly'],
    }),
  ]),
  stage('frame', 'Frame', 'CCSDS ASM, 20/20 CRC pass', 'VERIFIED', [
    p({
      id: 'sync',
      name: 'Sync word',
      value: '0x1ACFFC1D',
      unit: 'CCSDS ASM',
      level: 'VERIFIED',
      confidence: 1,
      method: 'Known-sync library correlation',
      evidence: ['Recurs every 2,080 channel bits, 21 times, 0 bit errors in 19 of 21'],
    }),
    p({
      id: 'crc',
      name: 'Frame check',
      value: 'CRC-16-CCITT',
      unit: '20 / 20 pass',
      level: 'VERIFIED',
      confidence: 1,
      method: 'CRC over each decoded frame',
      evidence: ['Frame 21 is truncated by the end of the burst and is not counted'],
    }),
    p({
      id: 'header',
      name: 'Header fields',
      value: '0xA53C + counter',
      level: 'ESTIMATED',
      confidence: 0.91,
      method: 'Constant-bit and counter-field significance tests',
      evidence: ['Bits 0–15 constant across all frames', 'Bits 16–23 increment by 1 per frame (p < 10⁻⁹)'],
    }),
  ]),
]

const fskStages: StageResult[] = [
  stage('ingest', 'Ingest', 'SigMF cf32_le at 250 kS/s', 'MEASURED', [
    p({ id: 'fs', name: 'Sample rate', value: '250,000', unit: 'S/s', level: 'MEASURED', method: 'core:sample_rate in SigMF metadata' }),
  ]),
  stage('detect', 'Detect', '3 bursts at −70 kHz', 'ESTIMATED', [
    p({ id: 'offset', name: 'Centre offset', value: '−70.00', unit: 'kHz', level: 'ESTIMATED', confidence: 0.97, method: 'Midpoint of the two tones' }),
    p({ id: 'bursts', name: 'Bursts', value: '3', unit: '200, 120, 140 ms', level: 'ESTIMATED', confidence: 0.95, method: 'Energy detector with 2 ms hysteresis' }),
  ]),
  stage('estimate', 'Estimate', '4.8 kBd, tones ±6 kHz', 'ESTIMATED', [
    p({
      id: 'rs',
      name: 'Symbol rate',
      value: '4,800',
      unit: 'Bd ± 0.2 %',
      level: 'ESTIMATED',
      confidence: 0.92,
      method: 'Transition spacing of the instantaneous frequency (FSK has no |x|² line)',
    }),
    p({ id: 'shift', name: 'Tone spacing', value: '12.0', unit: 'kHz', level: 'ESTIMATED', confidence: 0.95, method: 'Instantaneous-frequency histogram peaks' }),
    p({ id: 'snr', name: 'SNR (in band)', value: '17.8', unit: 'dB ± 1.2', level: 'ESTIMATED', confidence: 0.8, method: 'PSD in-band vs guard; M2M4 not valid for FSK' }),
  ]),
  stage('sync', 'Sync', 'Discriminator, symbol-centred', 'ESTIMATED', [
    p({ id: 'timing', name: 'Timing recovery', value: 'Locked', level: 'ESTIMATED', confidence: 0.9, method: 'FSK discriminator averaged over each symbol interior' }),
  ]),
  stage('classify', 'Classify', '2-FSK or GFSK — disagree', 'HYPOTHESIS', [
    p({
      id: 'mod',
      name: 'Modulation',
      value: '2-FSK',
      level: 'HYPOTHESIS',
      confidence: 0.64,
      method: 'Cumulant rules and 1-D CNN disagree; both rankings shown',
      evidence: ['Rules: 2-FSK — tone transitions show no Gaussian shaping', 'CNN: GFSK 0.52, 2-FSK 0.41'],
      alternatives: [{ value: 'GFSK', confidence: 0.31 }],
      warnings: ['Classifiers disagree. Downstream stages ran on the 2-FSK hypothesis.'],
    }),
  ]),
  stage('demod', 'Demodulate', '2,208 bits', 'ESTIMATED', [
    p({ id: 'bits', name: 'Soft bits', value: '2,208', unit: 'LLRs', level: 'MEASURED', method: 'Non-coherent tone energy difference' }),
  ]),
  stage('deinterleave', 'De-interleave', 'No structure found', 'UNKNOWN', [
    p({
      id: 'interleaver',
      name: 'Interleaver',
      value: null,
      level: 'UNKNOWN',
      method: 'GF(2) rank-drop scan over widths 8–32',
      evidence: ['No rank drop at any width from 8 to 32; KS p ≥ 0.31 everywhere', 'Wider periods cannot be tested: a rank test at width w needs at least (w + 30) × w bits, and this signal has 2,208'],
      resolveHint: 'A longer capture, or naming the transmitting standard, would settle it.',
    }),
  ]),
  stage('fec', 'FEC', 'No catalogued code fits', 'UNKNOWN', [
    p({
      id: 'code',
      name: 'Code',
      value: null,
      level: 'UNKNOWN',
      method: 'Catalogue search: convolutional, RS, LDPC',
      evidence: ['0 of 412 hypotheses beat the corrected threshold', 'Bit statistics are consistent with uncoded data or an uncatalogued code'],
      resolveHint: 'Soft bits are exported so an analyst can test a specific code.',
    }),
  ]),
  stage('frame', 'Frame', 'No recurring sync word', 'UNKNOWN', [
    p({
      id: 'sync',
      name: 'Sync word',
      value: null,
      level: 'UNKNOWN',
      method: 'Known-sync library + blind sync discovery',
      evidence: ['Best blind candidate: a 16-bit pattern with corrected p = 0.08 — not significant'],
      resolveHint: 'More bursts, or naming the protocol, would settle it.',
    }),
  ]),
]

const cwStages: StageResult[] = [
  stage('ingest', 'Ingest', 'SigMF cf32_le at 250 kS/s', 'MEASURED', [
    p({ id: 'fs', name: 'Sample rate', value: '250,000', unit: 'S/s', level: 'MEASURED', method: 'core:sample_rate in SigMF metadata' }),
  ]),
  stage('detect', 'Detect', 'Narrow line at +95 kHz', 'ESTIMATED', [
    p({ id: 'offset', name: 'Frequency', value: '+95.000', unit: 'kHz ± 3 Hz', level: 'ESTIMATED', confidence: 0.99, method: 'Interpolated FFT peak (quadratic on log magnitude)' }),
    p({ id: 'extent', name: 'Time extent', value: 'Whole capture', level: 'ESTIMATED', confidence: 0.99, method: 'Energy detector' }),
  ]),
  stage('estimate', 'Estimate', 'Stable, no modulation', 'ESTIMATED', [
    p({ id: 'drift', name: 'Frequency drift', value: '< 5', unit: 'Hz over capture', level: 'ESTIMATED', confidence: 0.9, method: 'Peak tracking per 32 ms segment' }),
    p({ id: 'cn0', name: 'C/N0', value: '69.4', unit: 'dB-Hz', level: 'ESTIMATED', confidence: 0.9, method: 'Peak power over noise density' }),
  ]),
  notApplicable('sync', 'Sync', 'No symbols to lock to'),
  stage('classify', 'Classify', 'Unmodulated carrier', 'ESTIMATED', [
    p({
      id: 'mod',
      name: 'Modulation',
      value: 'CW (unmodulated)',
      level: 'ESTIMATED',
      confidence: 0.97,
      method: 'Constant envelope, no symbol-rate line, no phase transitions',
    }),
  ]),
  notApplicable('demod', 'Demodulate', 'Nothing to demodulate'),
  notApplicable('deinterleave', 'De-interleave', 'No bits'),
  notApplicable('fec', 'FEC', 'No bits'),
  notApplicable('frame', 'Frame', 'No bits'),
]

const qpskSearch: HypothesisSearch = {
  tried: 1284,
  alpha: 0.01,
  correction: 'Holm',
  smallestThreshold: 0.01 / 1284,
  shuffledRuns: 10_000,
  shuffledAccepts: 0,
  rows: [
    { layer: 'FEC', candidate: 'Conv K=7 r½ (171,133)₈', statistic: 'Parity checks hold 98.7 %', pValue: 3.1e-41, threshold: 0.01 / 1284, outcome: 'accepted', reason: 'CRC-16 passes on 20 / 20 frames' },
    { layer: 'Interleaver', candidate: 'Block 8 × 16', statistic: 'Rank drop, KS', pValue: 2e-19, threshold: 0.01 / 1283, outcome: 'accepted', reason: 'CRC passes only after de-interleaving' },
    { layer: 'Framing', candidate: 'CCSDS ASM 0x1ACFFC1D', statistic: '21 recurrences, 2,080-bit period', pValue: 1e-30, threshold: 0.01 / 1282, outcome: 'accepted', reason: 'Recurs at the frame period' },
    { layer: 'FEC', candidate: 'Conv K=7 r½ punctured ¾', statistic: 'Parity checks hold 51.2 %', pValue: 0.21, threshold: 0.01 / 1281, outcome: 'rejected', reason: 'Fails at every puncture phase' },
    { layer: 'FEC', candidate: 'Conv K=9 r½ (561,753)₈', statistic: 'Parity checks hold 50.4 %', pValue: 0.43, threshold: 0.01 / 1280, outcome: 'rejected', reason: 'At the random-data baseline' },
    { layer: 'FEC', candidate: 'RS(255,223) CCSDS', statistic: 'GFFT zero run: none', pValue: 0.62, threshold: 0.01 / 1279, outcome: 'rejected', reason: 'No zero run at any of 16 polynomials × 8 offsets' },
    { layer: 'FEC', candidate: 'LDPC AR4JA r½ (CCSDS)', statistic: 'Syndrome posterior 0.49', pValue: 0.55, threshold: 0.01 / 1278, outcome: 'rejected', reason: 'Indistinguishable from random bits' },
    { layer: 'Interleaver', candidate: 'Convolutional (Forney) I=12, J=17', statistic: 'RS rank after de-interleave', pValue: 0.38, threshold: 0.01 / 1277, outcome: 'rejected', reason: 'No code structure after de-interleaving' },
    { layer: 'Interleaver', candidate: 'DVB-S2 column twist', statistic: 'Syndrome posterior 0.50', pValue: 0.71, threshold: 0.01 / 1276, outcome: 'rejected', reason: 'Standard permutation does not fit' },
  ],
}

const fskSearch: HypothesisSearch = {
  tried: 412,
  alpha: 0.01,
  correction: 'Holm',
  smallestThreshold: 0.01 / 412,
  shuffledRuns: 10_000,
  shuffledAccepts: 0,
  rows: [
    { layer: 'FEC', candidate: 'Conv K=7 r½ (171,133)₈', statistic: 'Parity checks hold 52.1 %', pValue: 0.09, threshold: 0.01 / 412, outcome: 'rejected', reason: 'Best candidate, still far above threshold' },
    { layer: 'FEC', candidate: 'Conv K=5 r½ (23,35)₈', statistic: 'Parity checks hold 50.9 %', pValue: 0.31, threshold: 0.01 / 411, outcome: 'rejected', reason: 'At the random-data baseline' },
    { layer: 'Framing', candidate: 'Blind 16-bit pattern 0x2DD4', statistic: '4 recurrences', pValue: 0.08, threshold: 0.01 / 410, outcome: 'rejected', reason: 'Not significant after correction' },
    { layer: 'Interleaver', candidate: 'Block, widths 8–32', statistic: 'Rank drop, KS', pValue: 0.31, threshold: 0.01 / 409, outcome: 'rejected', reason: 'No rank drop at any width' },
  ],
}

function makeFrames(): Frame[] {
  const rand = mulberry32(147)
  const frames: Frame[] = []
  for (let i = 0; i < 21; i++) {
    const byte = Math.floor(rand() * 256)
    frames.push({
      index: i + 1,
      startBit: 312 + i * 2080,
      syncWord: '0x1ACFFC1D',
      lengthBits: i === 20 ? 1576 : 2080,
      crc: i === 20 ? 'truncated' : 'pass',
      headerHex: `A5 3C ${(i + 7).toString(16).toUpperCase().padStart(2, '0')} ${byte.toString(16).toUpperCase().padStart(2, '0')}`,
    })
  }
  return frames
}

export const DETECTIONS: Detection[] = [
  {
    id: 1,
    label: 'QPSK',
    kind: 'qpsk',
    level: 'VERIFIED',
    headline: 'QPSK 25 kBd → conv K=7 → CCSDS frames',
    boxes: [{ t0: qpsk.t0, t1: qpsk.t1, f0: qpsk.fc - qpskBw / 2, f1: qpsk.fc + qpskBw / 2 }],
    stages: qpskStages,
    search: qpskSearch,
    frames: makeFrames(),
  },
  {
    id: 2,
    label: '2-FSK',
    kind: 'fsk',
    level: 'HYPOTHESIS',
    headline: '2-FSK 4.8 kBd, coding unknown',
    boxes: fsk.bursts.map(([t0, t1]) => ({ t0, t1, f0: fsk.fc - fsk.deviation - 4800, f1: fsk.fc + fsk.deviation + 4800 })),
    stages: fskStages,
    search: fskSearch,
    frames: [],
    noFramesReason: 'No recurring sync word was significant, so no frame boundaries are claimed.',
  },
  {
    id: 3,
    label: 'CW',
    kind: 'cw',
    level: 'ESTIMATED',
    headline: 'Unmodulated carrier',
    boxes: [{ t0: 0, t1: durationS, f0: cw.fc - 700, f1: cw.fc + 700 }],
    stages: cwStages,
    search: null,
    noSearchReason: 'An unmodulated carrier carries no bits, so no code or interleaver search ran.',
    frames: [],
    noFramesReason: 'An unmodulated carrier carries no bits.',
  },
]
