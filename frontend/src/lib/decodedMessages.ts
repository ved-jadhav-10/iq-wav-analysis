/**
 * The decoded text a known-system match shows (POCSAG pages, NAVTEX messages, DSC calls, AIS
 * messages, a CCSDS frame header), parsed from the Match stage's Parameters. The Parameter's level
 * is kept as the engine gave it: the text is HYPOTHESIS on purpose, because it rests on a
 * convention and is never evidence. Formats mirror `dsp/src/dsp/systems/match.py`
 * (`_pages_parameter`, `_messages_parameter`, `_calls_parameter`, `_ais_messages_parameter`).
 */
import type { EvidenceLevel, Parameter, StageResult } from './evidence'

export type DecodedKind = 'pages' | 'messages' | 'calls' | 'ais' | 'header'

export interface DecodedLine {
  /** Who the line is from: "RIC 0001234 · function 3", a NAVTEX "XA01", a DSC call type. */
  label: string | null
  /** The text itself, without the quoting the engine added; null when none was decoded. */
  text: string | null
  /** Why a line carries no text, in the engine's words. */
  note: string | null
}

export interface DecodedMessages {
  parameterId: string
  kind: DecodedKind
  /** The matched system's name (the Match stage's "Known system" value), or null. */
  system: string | null
  /** The card's title: "Decoded message" for text, "Decoded frame header" for a header. */
  title: string
  name: string
  value: string | number | null
  level: EvidenceLevel
  convention: string | null
  lines: DecodedLine[]
  /** Lines the engine left out ("... and 5 more"). */
  more: number
  /** True when at least one line carries decoded text. */
  hasText: boolean
}

const KINDS: Record<string, DecodedKind> = {
  pages: 'pages',
  messages: 'messages',
  calls: 'calls',
  ais_messages: 'ais',
  tm_header: 'header',
}

const MORE = /^\.\.\. and (\d+) more$/
const PAGE = /^RIC (\d+) function (\d+): (.*)$/

function unquote(text: string): string {
  return text.length >= 2 && text.startsWith('"') && text.endsWith('"') ? text.slice(1, -1) : text
}

function pageLine(line: string): DecodedLine {
  const m = PAGE.exec(line)
  if (!m) return { label: null, text: line, note: null }
  const label = `RIC ${m[1]} · function ${m[2]}`
  const rest = m[3]
  if (rest.startsWith('not shown')) return { label, text: null, note: rest }
  return { label, text: unquote(rest), note: null }
}

function splitAt(line: string, sep: string): DecodedLine {
  const at = line.indexOf(sep)
  if (at <= 0) return { label: null, text: line, note: null }
  return { label: line.slice(0, at), text: line.slice(at + sep.length), note: null }
}

/** Parse one Parameter into a card's worth of lines; null for a Parameter that is not decoded text. */
export function parseDecodedParameter(param: Parameter, system: string | null = null): DecodedMessages | null {
  const kind = KINDS[param.id]
  if (!kind) return null
  let more = 0
  const lines: DecodedLine[] = []
  for (const raw of param.evidence) {
    const skipped = MORE.exec(raw)
    if (skipped) {
      more += Number(skipped[1])
      continue
    }
    if (raw.trim() === '') continue
    if (kind === 'pages') lines.push(pageLine(raw))
    else if (kind === 'messages') lines.push(splitAt(raw, ': '))
    else if (kind === 'calls') lines.push(splitAt(raw, '; '))
    else lines.push({ label: null, text: raw, note: null })
  }
  return {
    parameterId: param.id,
    kind,
    system,
    title: kind === 'header' ? 'Decoded frame header' : 'Decoded message',
    name: param.name,
    value: param.value,
    level: param.level,
    convention: param.convention ?? null,
    lines,
    more,
    hasText: lines.some((l) => l.text !== null),
  }
}

/** Every decoded-text Parameter of the detection's Match stage, in the order the engine gave them.
 * Empty when nothing matched, or when a system matched but listed no text. */
export function decodedMessages(stages: readonly StageResult[]): DecodedMessages[] {
  const match = stages.find((s) => s.id === 'match')
  if (!match) return []
  const sys = match.parameters.find((p) => p.id === 'system')
  const system = sys && sys.value !== null ? String(sys.value) : null
  const out: DecodedMessages[] = []
  for (const p of match.parameters) {
    const parsed = parseDecodedParameter(p, system)
    if (parsed) out.push(parsed)
  }
  return out
}

/** The lines as plain text for the clipboard, one per line, label first. */
export function decodedMessagesAsText(d: Pick<DecodedMessages, 'lines'>): string {
  return d.lines
    .map((l) => {
      const body = l.text ?? l.note ?? ''
      return l.label ? `${l.label}: ${body}` : body
    })
    .join('\n')
}
