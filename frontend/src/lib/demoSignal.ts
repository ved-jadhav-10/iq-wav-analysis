import { fft, hann } from './fft'

/**
 * Deterministic synthetic capture used by the demo workspace until the backend serves real tiles.
 * Three emitters over complex AWGN (unit power per sample):
 *   #1 QPSK, 25 kBd, RRC β=0.35, +40 kHz, Es/N0 ≈ 14 dB, 80–950 ms
 *   #2 2-FSK, 4.8 kBd, ±6 kHz deviation, −70 kHz, three bursts
 *   #3 CW carrier at +95 kHz for the whole capture
 */
export const DEMO_CONFIG = {
  fs: 250_000,
  n: 1 << 18,
  fftSize: 512,
  hop: 256,
  seed: 26147,
  qpsk: { fc: 40_000, rs: 25_000, beta: 0.35, esN0Db: 14, t0: 0.08, t1: 0.95 },
  fsk: {
    fc: -70_000,
    rs: 4_800,
    deviation: 6_000,
    power: 4,
    bursts: [
      [0.15, 0.35],
      [0.5, 0.62],
      [0.78, 0.92],
    ] as [number, number][],
  },
  cw: { fc: 95_000, power: 0.35 },
  constellation: { symbols: 4096, phaseJitterDeg: 1.5 },
  fskChannel: { fs: 50_000, samples: 6000, snrDb: 16 },
} as const

export interface DemoProducts {
  fs: number
  fftSize: number
  hop: number
  rows: number
  bins: number
  durationS: number
  /** rows × bins, fft-shifted (−fs/2 … +fs/2 left to right), uint8-quantised dB. Row 0 is t = 0. */
  tile: Uint8Array
  dbMin: number
  dbMax: number
  /** Welch PSD in dB, fft-shifted, one value per bin. */
  psdDb: Float64Array
  freqsHz: Float64Array
  /** Interleaved I, Q of QPSK symbols after (simulated) matched filtering and synchronisation. */
  constellation: Float32Array
  evm: number
  /** Instantaneous frequency (Hz) of the channelised FSK emitter. */
  fskInstFreqHz: Float32Array
}

export function mulberry32(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function gaussian(rand: () => number): number {
  let u = 0
  while (u === 0) u = rand()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rand())
}

/** Root-raised-cosine taps, unit energy. */
export function rrcTaps(beta: number, sps: number, spanSymbols: number): Float64Array {
  const len = spanSymbols * sps + 1
  const mid = (len - 1) / 2
  const h = new Float64Array(len)
  for (let i = 0; i < len; i++) {
    const t = (i - mid) / sps
    if (t === 0) {
      h[i] = 1 - beta + (4 * beta) / Math.PI
    } else if (Math.abs(Math.abs(t) - 1 / (4 * beta)) < 1e-9) {
      h[i] =
        (beta / Math.SQRT2) *
        ((1 + 2 / Math.PI) * Math.sin(Math.PI / (4 * beta)) + (1 - 2 / Math.PI) * Math.cos(Math.PI / (4 * beta)))
    } else {
      h[i] =
        (Math.sin(Math.PI * t * (1 - beta)) + 4 * beta * t * Math.cos(Math.PI * t * (1 + beta))) /
        (Math.PI * t * (1 - (4 * beta * t) ** 2))
    }
  }
  let energy = 0
  for (const v of h) energy += v * v
  const norm = Math.sqrt(energy)
  for (let i = 0; i < len; i++) h[i] /= norm
  return h
}

/** Raised-cosine on/off envelope so bursts don't splatter across the band. */
function burstGain(t: number, t0: number, t1: number, rampS = 0.002): number {
  if (t < t0 || t > t1) return 0
  const up = Math.min(1, (t - t0) / rampS)
  const down = Math.min(1, (t1 - t) / rampS)
  const x = Math.min(up, down)
  return 0.5 - 0.5 * Math.cos(Math.PI * x)
}

function addQpsk(re: Float64Array, im: Float64Array, rand: () => number): void {
  const { fs, n } = DEMO_CONFIG
  const { fc, rs, beta, esN0Db, t0, t1 } = DEMO_CONFIG.qpsk
  const sps = fs / rs
  const span = 8
  const h = rrcTaps(beta, sps, span)
  const nSym = Math.ceil(n / sps) + span
  const symRe = new Float64Array(nSym)
  const symIm = new Float64Array(nSym)
  for (let m = 0; m < nSym; m++) {
    symRe[m] = (rand() < 0.5 ? -1 : 1) * Math.SQRT1_2
    symIm[m] = (rand() < 0.5 ? -1 : 1) * Math.SQRT1_2
  }

  const bbRe = new Float64Array(n)
  const bbIm = new Float64Array(n)
  let power = 0
  let active = 0
  for (let i = 0; i < n; i++) {
    let yr = 0
    let yi = 0
    for (let k = i % sps; k < h.length && k <= i; k += sps) {
      const m = (i - k) / sps
      yr += h[k] * symRe[m]
      yi += h[k] * symIm[m]
    }
    const g = burstGain(i / fs, t0, t1)
    bbRe[i] = yr * g
    bbIm[i] = yi * g
    if (g === 1) {
      power += yr * yr + yi * yi
      active++
    }
  }

  // Es/N0 = Ps · sps / N, with noise power N = 1 per sample.
  const targetPower = 10 ** (esN0Db / 10) / sps
  const scale = Math.sqrt(targetPower / (power / active))
  const w = (2 * Math.PI * fc) / fs
  for (let i = 0; i < n; i++) {
    const c = Math.cos(w * i)
    const s = Math.sin(w * i)
    re[i] += scale * (bbRe[i] * c - bbIm[i] * s)
    im[i] += scale * (bbRe[i] * s + bbIm[i] * c)
  }
}

function addFsk(re: Float64Array, im: Float64Array, rand: () => number): void {
  const { fs, n } = DEMO_CONFIG
  const { fc, rs, deviation, power, bursts } = DEMO_CONFIG.fsk
  const nSym = Math.ceil((n * rs) / fs) + 1
  const bits = new Uint8Array(nSym)
  for (let m = 0; m < nSym; m++) bits[m] = rand() < 0.5 ? 0 : 1
  const amp = Math.sqrt(power)
  let phase = 0
  for (let i = 0; i < n; i++) {
    const bit = bits[Math.floor((i * rs) / fs)]
    phase += (2 * Math.PI * (fc + (bit ? deviation : -deviation))) / fs
    const t = i / fs
    let g = 0
    for (const [b0, b1] of bursts) g = Math.max(g, burstGain(t, b0, b1))
    if (g === 0) continue
    re[i] += amp * g * Math.cos(phase)
    im[i] += amp * g * Math.sin(phase)
  }
}

function addCw(re: Float64Array, im: Float64Array): void {
  const { fs, n } = DEMO_CONFIG
  const { fc, power } = DEMO_CONFIG.cw
  const amp = Math.sqrt(power)
  const w = (2 * Math.PI * fc) / fs
  for (let i = 0; i < n; i++) {
    re[i] += amp * Math.cos(w * i + 0.7)
    im[i] += amp * Math.sin(w * i + 0.7)
  }
}

function makeConstellation(rand: () => number): { points: Float32Array; evm: number } {
  const { symbols, phaseJitterDeg } = DEMO_CONFIG.constellation
  const esN0 = 10 ** (DEMO_CONFIG.qpsk.esN0Db / 10)
  const sigma = Math.sqrt(1 / esN0 / 2)
  const jitter = (phaseJitterDeg * Math.PI) / 180
  const points = new Float32Array(symbols * 2)
  let errPower = 0
  for (let m = 0; m < symbols; m++) {
    const ir = (rand() < 0.5 ? -1 : 1) * Math.SQRT1_2
    const iq = (rand() < 0.5 ? -1 : 1) * Math.SQRT1_2
    const phi = gaussian(rand) * jitter
    const c = Math.cos(phi)
    const s = Math.sin(phi)
    const r = ir * c - iq * s + sigma * gaussian(rand)
    const q = ir * s + iq * c + sigma * gaussian(rand)
    points[2 * m] = r
    points[2 * m + 1] = q
    errPower += (r - ir) ** 2 + (q - iq) ** 2
  }
  return { points, evm: Math.sqrt(errPower / symbols) }
}

function makeFskInstFreq(rand: () => number): Float32Array {
  const { fs, samples, snrDb } = DEMO_CONFIG.fskChannel
  const { rs, deviation } = DEMO_CONFIG.fsk
  const sigma = Math.sqrt(10 ** (-snrDb / 10) / 2)
  const nSym = Math.ceil((samples * rs) / fs) + 1
  const bits = new Uint8Array(nSym)
  for (let m = 0; m < nSym; m++) bits[m] = rand() < 0.5 ? 0 : 1
  const out = new Float32Array(samples - 1)
  let phase = 0
  let prevRe = 1
  let prevIm = 0
  for (let i = 0; i < samples; i++) {
    const bit = bits[Math.floor((i * rs) / fs)]
    phase += (2 * Math.PI * (bit ? deviation : -deviation)) / fs
    const xr = Math.cos(phase) + sigma * gaussian(rand)
    const xi = Math.sin(phase) + sigma * gaussian(rand)
    if (i > 0) {
      const dr = xr * prevRe + xi * prevIm
      const di = xi * prevRe - xr * prevIm
      out[i - 1] = (Math.atan2(di, dr) * fs) / (2 * Math.PI)
    }
    prevRe = xr
    prevIm = xi
  }
  return out
}

export function generateDemo(): DemoProducts {
  const { fs, n, fftSize, hop, seed } = DEMO_CONFIG
  const rand = mulberry32(seed)

  const re = new Float64Array(n)
  const im = new Float64Array(n)
  const noiseSigma = Math.SQRT1_2
  for (let i = 0; i < n; i++) {
    re[i] = noiseSigma * gaussian(rand)
    im[i] = noiseSigma * gaussian(rand)
  }
  addQpsk(re, im, rand)
  addFsk(re, im, rand)
  addCw(re, im)

  const rows = Math.floor((n - fftSize) / hop) + 1
  const bins = fftSize
  const win = hann(fftSize)
  let winEnergy = 0
  for (const v of win) winEnergy += v * v
  const db = new Float64Array(rows * bins)
  const welch = new Float64Array(bins)
  const fr = new Float64Array(fftSize)
  const fi = new Float64Array(fftSize)
  const halfBins = bins >> 1

  for (let r = 0; r < rows; r++) {
    const off = r * hop
    for (let k = 0; k < fftSize; k++) {
      fr[k] = re[off + k] * win[k]
      fi[k] = im[off + k] * win[k]
    }
    fft(fr, fi)
    for (let k = 0; k < bins; k++) {
      const p = (fr[k] * fr[k] + fi[k] * fi[k]) / winEnergy
      const shifted = (k + halfBins) % bins
      welch[shifted] += p
      db[r * bins + shifted] = 10 * Math.log10(p + 1e-20)
    }
  }

  const sorted = Float64Array.from(db).sort()
  const noiseFloor = sorted[Math.floor(sorted.length * 0.5)]
  const dbMin = Math.floor(noiseFloor - 8)
  const dbMax = Math.ceil(sorted[sorted.length - 1])
  const span = dbMax - dbMin
  const tile = new Uint8Array(rows * bins)
  for (let i = 0; i < db.length; i++) {
    tile[i] = Math.max(0, Math.min(255, Math.round(((db[i] - dbMin) / span) * 255)))
  }

  const psdDb = new Float64Array(bins)
  const freqsHz = new Float64Array(bins)
  for (let k = 0; k < bins; k++) {
    psdDb[k] = 10 * Math.log10(welch[k] / rows + 1e-20)
    freqsHz[k] = ((k - halfBins) * fs) / fftSize
  }

  const { points, evm } = makeConstellation(rand)

  return {
    fs,
    fftSize,
    hop,
    rows,
    bins,
    durationS: n / fs,
    tile,
    dbMin,
    dbMax,
    psdDb,
    freqsHz,
    constellation: points,
    evm,
    fskInstFreqHz: makeFskInstFreq(rand),
  }
}
