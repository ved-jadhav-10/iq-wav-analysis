/** Which bits of a frame stay the same from frame to frame, and which count: the bit-stream
 * correlation behind the Bit stream view's field map (PS R5, header and payload). Pure functions of
 * a detection's frame table; an analyst's tool, so a field found here is a place to look and never
 * evidence by itself. */
import type { Frame } from './analysis'
import { bytesToBits, hexBytes, taggedBytes } from './bitstream'

/** Fewer frames cannot show that a bit stays put: three frames agree on one bit half the time by chance. */
export const MIN_FRAMES_FOR_FIELDS = 8
/** A field counts when its chance under random bits, corrected for the places it could start, is at most this. */
export const FIELD_P = 1e-6
/** Bits compared per frame, from the first bit listed (the sync word, when it is a bit pattern). */
export const MAX_COLUMNS = 512

export interface MappedField {
  kind: 'constant' | 'counter' | 'variable'
  /** Offset in bits from the first listed bit of the frame. */
  startBit: number
  bits: number
  /** Constant fields: the value, in hex when the field is whole bytes on a byte boundary, else in bits. */
  value: string | null
  /** Counters: the signed increment from one frame to the next (mod 256). */
  step: number | null
  /** The field's chance under random bits, corrected for the places it was looked for; null for variable. */
  p: number | null
}

export interface FieldMap {
  /** Frames compared, and how many the table holds. */
  frames: number
  of: number
  /** True when only the frames that pass their CRC were compared (their bits are the reliable ones). */
  passingOnly: boolean
  /** Bits compared per frame. */
  columns: number
  /** Bits of the sync word at the start, when it is a bit pattern; else 0. */
  syncBits: number
  /** Per bit column, the share of frames that agree with the commoner value (0.5 to 1). */
  agreement: number[]
  fields: MappedField[]
  /** Where the leading run of constant and counter fields ends; 0 when the first bit already varies. */
  headerEnd: number
  /** False with fewer than `MIN_FRAMES_FOR_FIELDS` frames, in which case no fields are claimed. */
  enough: boolean
}

/** ln(n!) for 0 <= n <= max, by summing logs. */
function logFactorials(max: number): number[] {
  const out = [0]
  for (let i = 1; i <= max; i++) out.push(out[i - 1] + Math.log(i))
  return out
}

/** P(X >= k) for X ~ Binomial(n, p), summed in log space so tiny p and large n stay finite. */
export function binomialTail(k: number, n: number, p: number): number {
  if (k <= 0) return 1
  if (k > n) return 0
  const lf = logFactorials(n)
  const lp = Math.log(p)
  const lq = Math.log1p(-p)
  let sum = 0
  for (let i = k; i <= n; i++) sum += Math.exp(lf[n] - lf[i] - lf[n - i] + i * lp + (n - i) * lq)
  return Math.min(1, sum)
}

function mode(values: readonly number[]): { value: number; count: number } {
  const counts = new Map<number, number>()
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1)
  let best = { value: 0, count: 0 }
  for (const [value, count] of counts) {
    if (count > best.count || (count === best.count && value < best.value)) best = { value, count }
  }
  return best
}

function describeValue(rows: readonly string[], start: number, bits: number): string {
  const slice = rows[0].slice(start, start + bits)
  if (start % 8 === 0 && bits % 8 === 0 && bits <= 64) {
    return slice.match(/.{8}/g)!.map((b) => parseInt(b, 2).toString(16).toUpperCase().padStart(2, '0')).join(' ')
  }
  return bits <= 32 ? slice : `${slice.slice(0, 32)}…`
}

/** Compare the frames' bits column by column. Counters are looked for in whole bytes only; constants
 * at any bit, as the longest runs of columns on which every frame agrees. */
export function fieldMap(frames: readonly Frame[]): FieldMap {
  const sorted = [...frames].sort((a, b) => a.index - b.index)
  const passing = sorted.filter((f) => f.crc === 'pass')
  const passingOnly = passing.length >= MIN_FRAMES_FOR_FIELDS
  const used = passingOnly ? passing : sorted
  const rows = used.map((f) => bytesToBits(taggedBytes(f).map((b) => b.hex)))
  const columns = rows.length === 0 ? 0 : Math.min(MAX_COLUMNS, ...rows.map((r) => r.length))
  const n = used.length
  const syncBits = used.length > 0 && /^(0x)?[0-9a-fA-F]+$/.test(used[0].syncWord.trim()) ? hexBytes(used[0].syncWord).length * 8 : 0
  const base = { frames: n, of: sorted.length, passingOnly, columns, syncBits }
  if (n < MIN_FRAMES_FOR_FIELDS || columns === 0) {
    return { ...base, agreement: [], fields: [], headerEnd: 0, enough: false }
  }

  const agreement: number[] = []
  const same: boolean[] = []
  for (let c = 0; c < columns; c++) {
    let ones = 0
    for (const r of rows) if (r[c] === '1') ones++
    agreement.push(Math.max(ones, n - ones) / n)
    same.push(ones === 0 || ones === n)
  }

  const claimed: (MappedField | null)[] = new Array<MappedField | null>(columns).fill(null)
  const fields: MappedField[] = []

  // Counters first, byte by byte: the bytes of a small counter hold constant high bits, which must
  // not be read as a constant field of their own.
  const windows = Math.floor(columns / 8)
  for (let w = 0; w < windows; w++) {
    const values = rows.map((r) => parseInt(r.slice(8 * w, 8 * w + 8), 2))
    const steps: number[] = []
    for (let i = 1; i < n; i++) {
      const d = (values[i] - values[i - 1] + 256) % 256
      if (d !== 0) steps.push(d)
    }
    if (steps.length === 0) continue
    const { value: step, count } = mode(steps)
    // The step was picked from the data among 255 possible ones, in each of the byte windows.
    const p = Math.min(1, binomialTail(count, n - 1, 1 / 256) * 255 * windows)
    if (2 * count >= n - 1 && p <= FIELD_P) {
      const field: MappedField = { kind: 'counter', startBit: 8 * w, bits: 8, value: null, step: step > 128 ? step - 256 : step, p }
      fields.push(field)
      for (let c = 8 * w; c < 8 * w + 8; c++) claimed[c] = field
    }
  }

  // Then runs of columns on which every frame agrees, each judged as a whole.
  let c = 0
  while (c < columns) {
    if (claimed[c] || !same[c]) {
      c++
      continue
    }
    let end = c
    while (end < columns && !claimed[end] && same[end]) end++
    const bits = end - c
    const p = Math.min(1, columns * 2 ** (-bits * (n - 1)))
    if (p <= FIELD_P) {
      const field: MappedField = { kind: 'constant', startBit: c, bits, value: describeValue(rows, c, bits), step: null, p }
      fields.push(field)
      for (let k = c; k < end; k++) claimed[k] = field
    }
    c = end
  }

  // Everything left varies (or agrees too briefly to say more).
  c = 0
  while (c < columns) {
    if (claimed[c]) {
      c++
      continue
    }
    let end = c
    while (end < columns && !claimed[end]) end++
    fields.push({ kind: 'variable', startBit: c, bits: end - c, value: null, step: null, p: null })
    c = end
  }
  fields.sort((a, b) => a.startBit - b.startBit)

  // A counter's own constant high bits sit beside it as a constant field; merge nothing, but find
  // where the fixed part of the frame ends.
  let headerEnd = 0
  for (const f of fields) {
    if (f.kind === 'variable' || f.startBit !== headerEnd) break
    headerEnd = f.startBit + f.bits
  }
  return { ...base, agreement, fields, headerEnd, enough: true }
}
