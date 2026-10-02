/** Pure computations behind the Bit stream view, from a detection's frames alone. */
import type { Frame } from './analysis'

export interface Extent {
  min: number
  max: number
  span: number
}

/** The stream's bit axis: first start bit to last start + length. Null with no frames. */
export function streamExtent(frames: readonly Frame[]): Extent | null {
  if (frames.length === 0) return null
  let min = Infinity
  let max = -Infinity
  for (const f of frames) {
    min = Math.min(min, f.startBit)
    max = Math.max(max, f.startBit + Math.max(0, f.lengthBits))
  }
  return { min, max, span: Math.max(1, max - min) }
}

export interface Recurrence {
  frames: number
  /** Gaps between consecutive start bits (frames sorted by start bit). */
  gaps: number[]
  /** The most common gap, ties broken by the smaller; null with no gaps. */
  period: number | null
  /** Gaps equal to the period. */
  matching: number
  /** matching / gaps.length, or null with no gaps. */
  fraction: number | null
  /** The most common sync word among the frames (ties: first in sort order), or null. */
  syncWord: string | null
  /** Whether the frames are enough to say anything: at least 3 frames, so at least 2 gaps. */
  enough: boolean
  /** True when there are enough frames and every gap equals the period. */
  periodic: boolean
}

/** Minimum frames before a spacing means anything: two gaps are the least that can repeat. */
export const MIN_FRAMES_FOR_RECURRENCE = 3

function mode<T>(values: readonly T[], smaller: (a: T, b: T) => boolean): T | null {
  const counts = new Map<T, number>()
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1)
  let best: T | null = null
  let bestCount = 0
  for (const [v, c] of counts) {
    if (c > bestCount || (c === bestCount && best !== null && smaller(v, best))) {
      best = v
      bestCount = c
    }
  }
  return best
}

export function recurrence(frames: readonly Frame[]): Recurrence {
  const sorted = [...frames].sort((a, b) => a.startBit - b.startBit)
  const gaps: number[] = []
  for (let i = 1; i < sorted.length; i++) gaps.push(sorted[i].startBit - sorted[i - 1].startBit)
  const period = mode(gaps, (a, b) => a < b)
  const matching = period === null ? 0 : gaps.filter((g) => g === period).length
  const enough = sorted.length >= MIN_FRAMES_FOR_RECURRENCE
  return {
    frames: sorted.length,
    gaps,
    period,
    matching,
    fraction: gaps.length === 0 ? null : matching / gaps.length,
    syncWord: mode(
      sorted.map((f) => f.syncWord),
      (a, b) => a < b,
    ),
    enough,
    periodic: enough && gaps.length > 0 && matching === gaps.length,
  }
}

/** Bytes of a hex string, ignoring spaces and any other separator; a trailing odd digit is dropped. */
export function hexBytes(hex: string): string[] {
  const clean = hex.trim().replace(/^0x/i, '').replace(/[^0-9a-fA-F]/g, '')
  const out: string[] = []
  for (let i = 0; i + 1 < clean.length; i += 2) out.push(clean.slice(i, i + 2).toUpperCase())
  return out
}

/** A sync word written as hex digits, with or without a "0x" prefix (the engine writes "0x1ACFFC1D"). */
function isHexWord(word: string): boolean {
  const digits = word.trim().replace(/^0x/i, '')
  return digits.length > 0 && digits.length % 2 === 0 && /^[0-9a-fA-F]+$/.test(digits)
}

export interface Field {
  id: 'sync' | 'header' | 'payload' | 'crc' | 'unsplit'
  label: string
  bits: number
}

export interface Anatomy {
  fields: Field[]
  /** Frame length in bits as reported. */
  total: number
  /** True when the known fields account for every bit of the frame. */
  split: boolean
  /** What is not known about the split, in words; null when nothing is missing. */
  note: string | null
  /** True when the header bytes are the first bytes of the payload (the generic framer) rather than
   * a separate field (a known system's own header). */
  headerInPayload: boolean
}

/** The widest CRC the framer's catalogue carries; a remainder larger than this is not called a CRC. */
const MAX_CRC_BITS = 32

/** Sync / header / payload / CRC by bit length. Sync is the sync word's hex digits x 4; header and
 * payload are byte counts x 8. The generic framer reports the header as the first bytes of the
 * payload; a known system reports it as a separate field, so when the payload does not start with
 * the header the two are added. What is left of `lengthBits` is the CRC for a complete frame,
 * and anything else is marked "Not split", never guessed. */
export function frameAnatomy(f: Frame): Anatomy {
  const total = Math.max(0, f.lengthBits)
  const header = hexBytes(f.headerHex)
  const payload = hexBytes(f.payloadHex)
  const headerInPayload = header.length > 0 && header.length <= payload.length && header.every((b, i) => b === payload[i])
  if (!isHexWord(f.syncWord)) {
    return {
      fields: total > 0 ? [{ id: 'unsplit', label: 'Not split', bits: total }] : [],
      total,
      split: false,
      note: `The sync word "${f.syncWord}" is not a bit pattern, so this frame's bit length is not split into fields.`,
      headerInPayload,
    }
  }
  const syncBits = hexBytes(f.syncWord).length * 8
  const headerBits = header.length * 8
  const payloadBits = payload.length * 8
  const dataBits = headerInPayload ? payloadBits : headerBits + payloadBits
  const known = syncBits + dataBits
  if (known > total) {
    const fields: Field[] = []
    if (total > 0) fields.push({ id: 'sync', label: 'Sync', bits: Math.min(syncBits, total) })
    if (total > syncBits) fields.push({ id: 'unsplit', label: 'Not split', bits: total - syncBits })
    return {
      fields,
      total,
      split: false,
      note: `Sync, header and payload add up to ${known} bits, more than the ${total} bits reported, so only the sync word is marked.`,
      headerInPayload,
    }
  }
  const fields: Field[] = [{ id: 'sync', label: 'Sync', bits: syncBits }]
  if (headerBits > 0) fields.push({ id: 'header', label: 'Header', bits: headerBits })
  const payloadOnly = headerInPayload ? payloadBits - headerBits : payloadBits
  if (payloadOnly > 0) fields.push({ id: 'payload', label: 'Payload', bits: payloadOnly })
  const rest = total - known
  if (f.crc === 'truncated') {
    if (rest > 0) fields.push({ id: 'unsplit', label: 'Not split', bits: rest })
    return {
      fields,
      total,
      split: rest === 0,
      note: 'The burst ended inside this frame, so its CRC was never reached.',
      headerInPayload,
    }
  }
  if (rest === 0) return { fields, total, split: true, note: null, headerInPayload }
  if (rest <= MAX_CRC_BITS) {
    fields.push({ id: 'crc', label: 'CRC', bits: rest })
    return { fields, total, split: true, note: null, headerInPayload }
  }
  fields.push({ id: 'unsplit', label: 'Not split', bits: rest })
  return {
    fields,
    total,
    split: false,
    note: `${rest} bits are not accounted for by the sync word, header and payload; the frame's own layout would say what they are.`,
    headerInPayload,
  }
}

/** The default frame for the anatomy: the first that passes its CRC, else the first. */
export function defaultFrame(frames: readonly Frame[]): Frame | null {
  return frames.find((f) => f.crc === 'pass') ?? frames[0] ?? null
}

export interface TaggedByte {
  hex: string
  field: 'sync' | 'header' | 'payload'
}

/** The frame's bytes tagged with the field each belongs to: the sync word, then the header, then the
 * rest of the payload (the header bytes are not repeated when the payload starts with them). A
 * sync word that is not hex (a text marker such as "ZCZC") has no bytes here. */
export function taggedBytes(f: Frame): TaggedByte[] {
  const header = hexBytes(f.headerHex)
  const payload = hexBytes(f.payloadHex)
  const inPayload = header.length > 0 && header.length <= payload.length && header.every((b, i) => b === payload[i])
  const body = inPayload ? payload.slice(header.length) : payload
  return [
    ...(isHexWord(f.syncWord) ? hexBytes(f.syncWord) : []).map((hex) => ({ hex, field: 'sync' as const })),
    ...header.map((hex) => ({ hex, field: 'header' as const })),
    ...body.map((hex) => ({ hex, field: 'payload' as const })),
  ]
}

/** A frame's bytes as one string of '0' and '1', most significant bit first. */
export function bytesToBits(bytes: readonly string[]): string {
  return bytes.map((b) => parseInt(b, 16).toString(2).padStart(8, '0')).join('')
}

export interface Pattern {
  /** The pattern as bits. */
  bits: string
  /** How the analyst wrote it. */
  kind: 'hex' | 'binary'
}

/** Parse a search pattern: hex bytes ("1A CF FC 1D", "0x1ACF") or bits with a "0b" prefix ("0b1010 0011").
 * Null for an empty, odd-digit or otherwise unreadable pattern, so the view says what it expects
 * rather than searching for something other than what was typed. */
export function parsePattern(text: string): Pattern | null {
  const t = text.trim()
  if (!t) return null
  if (/^0b/i.test(t)) {
    const bits = t.slice(2).replace(/[\s_]/g, '')
    return /^[01]+$/.test(bits) ? { bits, kind: 'binary' } : null
  }
  const digits = t.replace(/^0x/i, '').replace(/[\s_]/g, '')
  if (!/^[0-9a-fA-F]+$/.test(digits) || digits.length % 2 !== 0) return null
  return { bits: bytesToBits(hexBytes(digits)), kind: 'hex' }
}

export interface FrameHits {
  frame: Frame
  /** Bit offsets into the frame's listed bytes (sync word first) where the pattern starts, overlapping hits included. */
  offsets: number[]
}

/** Every place the pattern occurs in each frame's listed bytes, at any bit offset (so a pattern
 * shifted off the byte boundary is still found). Frames with no hit are left out. Only the bytes
 * the frame table lists are searched: not the CRC, nor anything the engine did not report. */
export function findPattern(frames: readonly Frame[], pattern: Pattern): FrameHits[] {
  const out: FrameHits[] = []
  for (const frame of frames) {
    const bits = bytesToBits(taggedBytes(frame).map((b) => b.hex))
    const offsets: number[] = []
    for (let at = bits.indexOf(pattern.bits); at !== -1; at = bits.indexOf(pattern.bits, at + 1)) offsets.push(at)
    if (offsets.length > 0) out.push({ frame, offsets })
  }
  return out
}

/** The bytes (by index) that any hit at `offsets` touches, for highlighting. */
export function hitBytes(offsets: readonly number[], patternBits: number): Set<number> {
  const touched = new Set<number>()
  for (const at of offsets) {
    for (let b = Math.floor(at / 8); b <= Math.floor((at + patternBits - 1) / 8); b++) touched.add(b)
  }
  return touched
}
