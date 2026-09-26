/** In-place iterative radix-2 complex FFT. Length must be a power of two. */
export function fft(re: Float64Array, im: Float64Array): void {
  const n = re.length
  if (n !== im.length || n === 0 || (n & (n - 1)) !== 0) {
    throw new Error(`fft length must be a power of two, got ${n}`)
  }

  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1
    for (; j & bit; bit >>= 1) j ^= bit
    j ^= bit
    if (i < j) {
      const tr = re[i]
      re[i] = re[j]
      re[j] = tr
      const ti = im[i]
      im[i] = im[j]
      im[j] = ti
    }
  }

  for (let len = 2; len <= n; len <<= 1) {
    const half = len >> 1
    const ang = (-2 * Math.PI) / len
    const wStepRe = Math.cos(ang)
    const wStepIm = Math.sin(ang)
    for (let start = 0; start < n; start += len) {
      let wRe = 1
      let wIm = 0
      for (let k = 0; k < half; k++) {
        const a = start + k
        const b = a + half
        const xr = re[b] * wRe - im[b] * wIm
        const xi = re[b] * wIm + im[b] * wRe
        re[b] = re[a] - xr
        im[b] = im[a] - xi
        re[a] += xr
        im[a] += xi
        const nextRe = wRe * wStepRe - wIm * wStepIm
        wIm = wRe * wStepIm + wIm * wStepRe
        wRe = nextRe
      }
    }
  }
}

/** Periodic Hann window, the usual choice for STFT/Welch. */
export function hann(n: number): Float64Array {
  const w = new Float64Array(n)
  for (let i = 0; i < n; i++) w[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / n)
  return w
}
