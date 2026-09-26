export type ColormapName = 'sanket' | 'viridis' | 'inferno' | 'gray'

export const COLORMAPS: Record<ColormapName, { label: string; stops: string[] }> = {
  // House map: lightness rises monotonically from the dark UI background through teal to near-white,
  // so weak signals stay distinguishable from the noise floor in both themes.
  sanket: {
    label: 'Sanket',
    stops: ['#070a0f', '#0c1a2c', '#11304f', '#134b6c', '#136a80', '#198b8d', '#3aab97', '#7bc9a2', '#c0e5b3', '#f5fbe2'],
  },
  viridis: {
    label: 'Viridis',
    stops: ['#440154', '#482878', '#3e4a89', '#31688e', '#26828e', '#1f9e89', '#35b779', '#6dcd59', '#b4de2c', '#fde725'],
  },
  inferno: {
    label: 'Inferno',
    stops: ['#000004', '#1b0c41', '#4a0c6b', '#781c6d', '#a52c60', '#cf4446', '#ed6925', '#fb9b06', '#f7d13d', '#fcffa4'],
  },
  gray: { label: 'Grayscale', stops: ['#000000', '#ffffff'] },
}

function hexToRgb(hex: string): [number, number, number] {
  const v = parseInt(hex.slice(1), 16)
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255]
}

/** 256-entry RGBA lookup table, linearly interpolated between evenly spaced stops. */
export function buildLut(name: ColormapName): Uint8Array {
  const stops = COLORMAPS[name].stops.map(hexToRgb)
  const lut = new Uint8Array(256 * 4)
  const segments = stops.length - 1
  for (let i = 0; i < 256; i++) {
    const x = (i / 255) * segments
    const s = Math.min(Math.floor(x), segments - 1)
    const t = x - s
    const a = stops[s]
    const b = stops[s + 1]
    for (let c = 0; c < 3; c++) lut[i * 4 + c] = Math.round(a[c] + (b[c] - a[c]) * t)
    lut[i * 4 + 3] = 255
  }
  return lut
}

/** WCAG relative luminance of an sRGB colour given as 0–255 channels. */
export function relativeLuminance(r: number, g: number, b: number): number {
  const lin = (c: number) => {
    const s = c / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}
