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
