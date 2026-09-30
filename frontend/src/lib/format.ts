const SUPERSCRIPT: Record<string, string> = {
  '-': '⁻',
  '0': '⁰',
  '1': '¹',
  '2': '²',
  '3': '³',
  '4': '⁴',
  '5': '⁵',
  '6': '⁶',
  '7': '⁷',
  '8': '⁸',
  '9': '⁹',
}

/** Scientific notation for p-values and thresholds: 7.8e-6 → "7.8 × 10⁻⁶". Plain decimals in [0.001, 1000). */
export function sci(x: number, digits = 1): string {
  if (x === 0) return '0'
  const abs = Math.abs(x)
  if (abs >= 0.001 && abs < 1000) return String(Number(x.toPrecision(2)))
  let exp = Math.floor(Math.log10(abs))
  let mantissa = Number((x / 10 ** exp).toFixed(digits))
  if (Math.abs(mantissa) >= 10) {
    mantissa /= 10
    exp += 1
  }
  const m = String(Number(mantissa.toFixed(digits)))
  const e = String(exp)
    .split('')
    .map((c) => SUPERSCRIPT[c] ?? c)
    .join('')
  return `${m} × 10${e}`
}

/** Evenly spaced "nice" tick values (1, 2, 5 × 10ⁿ) covering [min, max]. */
export function niceTicks(min: number, max: number, target = 6): { ticks: number[]; step: number } {
  const span = max - min
  if (!(span > 0)) return { ticks: [min], step: 1 }
  const raw = span / Math.max(1, target)
  const mag = 10 ** Math.floor(Math.log10(raw))
  const norm = raw / mag
  const step = (norm < 1.5 ? 1 : norm < 3.5 ? 2 : norm < 7.5 ? 5 : 10) * mag
  const ticks: number[] = []
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) {
    ticks.push(Math.abs(v) < step * 1e-9 ? 0 : v)
  }
  return { ticks, step }
}

export function decimalsFor(step: number): number {
  return Math.max(0, -Math.floor(Math.log10(step) + 1e-9))
}

export function signed(value: number, decimals: number): string {
  const s = Math.abs(value).toFixed(decimals)
  if (Number(s) === 0) return s
  return value < 0 ? `−${s}` : `+${s}`
}

export const integer = new Intl.NumberFormat('en-US')

const SI: Record<string, number> = { k: 1e3, K: 1e3, M: 1e6, G: 1e9 }

/** A rate typed as "2400000", "2.4e6", "2.4M" or "250 k" (with an optional trailing S/s or sps);
 * null when it isn't a positive, finite number - the caller says so rather than guessing. */
export function parseRate(text: string): number | null {
  const m = /^\s*([0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)\s*([kKMG]?)\s*(?:S\/s|sps)?\s*$/.exec(text)
  if (!m) return null
  const value = Number(m[1]) * (SI[m[2]] ?? 1)
  return Number.isFinite(value) && value > 0 ? value : null
}

/** A rate with an SI prefix and a non-breaking space: 2400000 → "2.4 MS/s". */
export function formatRate(rate: number): string {
  const [div, prefix] = rate >= 1e9 ? [1e9, 'G'] : rate >= 1e6 ? [1e6, 'M'] : rate >= 1e3 ? [1e3, 'k'] : [1, '']
  return `${Number((rate / div).toPrecision(6))} ${prefix}S/s`
}

/** A Parameter's value for display: integers grouped, other numbers to 6 significant figures
 * (the unrounded value stays in the results document), strings as they are. */
export function formatValue(value: string | number): string {
  if (typeof value === 'string') return value
  if (Number.isInteger(value)) return integer.format(value)
  return String(Number(value.toPrecision(6)))
}
