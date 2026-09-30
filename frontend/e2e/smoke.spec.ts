import { expect, test, type Page } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'

test('workspace loads fully offline with no console errors', async ({ page, context, baseURL }) => {
  const origin = new URL(baseURL!).origin
  const external: string[] = []
  const errors: string[] = []

  // Everything outside the local server is refused and recorded, so any CDN, font or
  // telemetry request fails the test rather than silently succeeding online.
  await context.route('**/*', (route) => {
    const url = route.request().url()
    if (url.startsWith(origin)) return route.continue()
    external.push(url)
    return route.abort('internetdisconnected')
  })
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text())
  })
  page.on('pageerror', (err) => errors.push(err.message))

  await page.goto('/')
  await expect(page).toHaveTitle(/Sanket/)
  await expect(page.getByText('Synthetic demo', { exact: true })).toBeVisible()
  await expect(page.locator('canvas').first()).toBeVisible()
  await page.waitForLoadState('networkidle')

  expect(external).toEqual([])
  expect(errors).toEqual([])
})

/** A narrowband tone in noise as cf32_le samples (raw bytes, no header). */
function toneBytes(): Buffer {
  const n = 1 << 16
  const samples = new Float32Array(2 * n)
  let seed = 12345
  const noise = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    return seed / 2 ** 32 - 0.5
  }
  for (let i = 0; i < n; i++) {
    const phase = 2 * Math.PI * 0.15 * i
    samples[2 * i] = Math.cos(phase) + 0.05 * noise()
    samples[2 * i + 1] = Math.sin(phase) + 0.05 * noise()
  }
  return Buffer.from(samples.buffer)
}

/** `base.sigmf-data` and `base.sigmf-meta` for the tone, stating a 1 MS/s rate and 100 MHz centre. */
function writeSigmf(base: string) {
  writeFileSync(`${base}.sigmf-data`, toneBytes())
  writeFileSync(
    `${base}.sigmf-meta`,
    JSON.stringify({
      global: { 'core:datatype': 'cf32_le', 'core:sample_rate': 1_000_000, 'core:version': '1.0.0' },
      captures: [{ 'core:sample_start': 0, 'core:frequency': 100_000_000 }],
      annotations: [],
    }),
  )
}

async function openByPath(page: Page, path: string) {
  await page.goto('/')
  await page.getByPlaceholder('Open a recording by path…').fill(path)
  await page.keyboard.press('Enter')
}

test('a raw file with an unknown sample rate opens, asks for the rate, then analyses', async ({ page }, testInfo) => {
  test.setTimeout(120_000)
  mkdirSync(testInfo.outputDir, { recursive: true })
  const path = testInfo.outputPath('capture.bin')
  writeFileSync(path, toneBytes())

  await openByPath(page, path)
  // Opened, not refused: the waterfall is up in normalised units and the prompt is asking.
  const prompt = page.getByRole('region', { name: 'Sample rate needed' })
  await expect(prompt).toBeVisible()
  await expect(page.getByText('Synthetic demo', { exact: true })).toBeHidden()
  await expect(page.getByText(/tile · rate unknown/)).toBeVisible()
  await expect(page.getByRole('button', { name: /^#1 / })).toHaveCount(0)

  // The prompt takes its own row; the page still never scrolls as a whole, in either section.
  for (const size of [{ width: 1918, height: 950 }, { width: 1440, height: 800 }]) {
    await page.setViewportSize(size)
    for (const section of ['Survey', 'Waterfall']) {
      await page.getByRole('navigation', { name: 'Workspace section' }).getByRole('button', { name: section }).click()
      // A string, not a function: the e2e project has no DOM types, and this runs in the page.
      const { scrollHeight, innerHeight } = (await page.evaluate(
        '({ scrollHeight: document.documentElement.scrollHeight, innerHeight: window.innerHeight })',
      )) as { scrollHeight: number; innerHeight: number }
      expect(scrollHeight, `${section} at ${size.width}`).toBeLessThanOrEqual(innerHeight)
    }
  }

  // A bad entry is refused with a message; a good one replaces the prompt with real detections.
  await page.getByLabel('Sample rate in samples per second').fill('fast')
  await page.getByLabel('Sample rate in samples per second').press('Enter')
  await expect(prompt.getByRole('alert')).toBeVisible()
  await page.getByLabel('Sample rate in samples per second').fill('1M')
  await page.getByLabel('Sample rate in samples per second').press('Enter')
  await expect(prompt).toBeHidden()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  await expect(page.getByText('1,000,000 S/s')).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: /^Analysing signal/ })).toHaveCount(0, {
    timeout: 60_000,
  })
})

test('uploaded files are opened from the workspace, and a bad name is refused', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/')
  const picker = page.getByLabel('Upload recording files')

  await picker.setInputFiles({ name: 'bad;name.bin', mimeType: 'application/octet-stream', buffer: toneBytes() })
  await expect(page.getByRole('alert')).toContainText('file names may hold')

  // A SigMF pair arrives as two files and opens as one recording, with its stated rate.
  const meta = JSON.stringify({
    global: { 'core:datatype': 'cf32_le', 'core:sample_rate': 1_000_000, 'core:version': '1.0.0' },
    captures: [{ 'core:sample_start': 0 }],
    annotations: [],
  })
  await picker.setInputFiles([
    { name: 'upload-tone.sigmf-data', mimeType: 'application/octet-stream', buffer: toneBytes() },
    { name: 'upload-tone.sigmf-meta', mimeType: 'application/json', buffer: Buffer.from(meta) },
  ])
  await expect(page.getByText('Opened from SigMF')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Sample rate needed' })).toBeHidden()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
})

test('a real recording opens, then its analysis lands in the background', async ({ page }, testInfo) => {
  test.setTimeout(120_000)
  // Written as SigMF cf32_le with a stated rate, so the server draws boxes without any
  // assumption being entered.
  const base = testInfo.outputPath('tone')
  mkdirSync(testInfo.outputDir, { recursive: true })
  writeSigmf(base)

  await openByPath(page, `${base}.sigmf-meta`)

  // The recording replaces the demo as soon as tiles and boxes exist ...
  await expect(page.getByText('Synthetic demo', { exact: true })).toBeHidden()
  await expect(page.getByText('Opened from SigMF')).toBeVisible()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  // ... and the background analysis ends on its own: no "Analysing" status is left.
  await expect(page.getByRole('status').filter({ hasText: /^Analysing signal/ })).toHaveCount(0, {
    timeout: 60_000,
  })
})

test('a folder lists its recordings and opens the one that is picked', async ({ page }, testInfo) => {
  test.setTimeout(120_000)
  const folder = testInfo.outputPath('batch')
  mkdirSync(folder, { recursive: true })
  writeSigmf(`${folder}/first`)
  writeSigmf(`${folder}/second`)
  writeFileSync(`${folder}/notes.txt`, 'not a recording')

  await openByPath(page, folder)
  const dialog = page.getByRole('dialog', { name: 'Recordings in this folder' })
  await expect(dialog.getByRole('heading', { name: '2 recordings in this folder' })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'notes.txt' })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'second.sigmf-meta' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByText('second.sigmf-meta')).toBeVisible()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
})

test('the analyst can enter a centre frequency and swap I and Q', async ({ page }, testInfo) => {
  test.setTimeout(180_000)
  const base = testInfo.outputPath('tone')
  mkdirSync(testInfo.outputDir, { recursive: true })
  writeSigmf(base)
  await openByPath(page, `${base}.sigmf-meta`)
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()

  await page.getByRole('navigation', { name: 'Workspace section' }).getByRole('button', { name: 'Assumptions' }).click()
  const modal = page.getByRole('heading', { name: 'Configuration & Assumptions' }).locator('xpath=ancestor::div[3]')
  const entry = modal.getByRole('region', { name: 'Enter what you know' })

  // A bad frequency is refused with a message; a good one is recorded as entered by the analyst.
  await entry.getByLabel('Centre frequency').fill('fast')
  await entry.getByRole('button', { name: 'Set centre frequency' }).click()
  await expect(entry.getByRole('alert')).toBeVisible()
  await entry.getByLabel('Centre frequency').fill('433.92M')
  await entry.getByRole('button', { name: 'Set centre frequency' }).click()
  await expect(modal.getByText('433,920,000')).toBeVisible()

  // I and Q are swapped: the server tiles the recording again from the mirrored samples.
  const iq = entry.getByRole('radiogroup', { name: 'IQ order' })
  await expect(iq.getByRole('radio', { name: 'IQ' })).toBeChecked()
  await iq.getByRole('radio', { name: 'QI' }).click()
  await expect(iq.getByRole('radio', { name: 'QI' })).toBeChecked()
  await expect(entry.getByText('Q comes first, so the spectrum is mirrored.')).toBeVisible()
  await expect(entry.getByRole('alert')).toHaveCount(0)

  // The page still never scrolls as a whole, in either section, with the entries in place.
  await modal.getByRole('button', { name: 'Close' }).click()
  for (const size of [{ width: 1918, height: 950 }, { width: 1440, height: 800 }]) {
    await page.setViewportSize(size)
    for (const section of ['Survey', 'Waterfall']) {
      await page.getByRole('navigation', { name: 'Workspace section' }).getByRole('button', { name: section }).click()
      const { scrollHeight, innerHeight } = (await page.evaluate(
        '({ scrollHeight: document.documentElement.scrollHeight, innerHeight: window.innerHeight })',
      )) as { scrollHeight: number; innerHeight: number }
      expect(scrollHeight, `${section} at ${size.width}`).toBeLessThanOrEqual(innerHeight)
    }
  }
})

test('an unknown sample format is a question: the candidates are offered and the choice is recorded', async ({
  page,
}, testInfo) => {
  test.setTimeout(120_000)
  mkdirSync(testInfo.outputDir, { recursive: true })
  const path = testInfo.outputPath('silence.bin')
  writeFileSync(path, Buffer.alloc(1 << 16)) // all zeros fit every width, so the sniffer can't choose

  await openByPath(page, path)
  const prompt = page.getByRole('region', { name: 'Sample format needed' })
  await expect(prompt).toBeVisible()
  await expect(page.getByText('Synthetic demo', { exact: true })).toBeVisible() // nothing was opened
  await expect(prompt.getByRole('list', { name: 'Candidate sample formats' }).getByRole('button')).toHaveCount(4)

  // A bad type is refused with a message; a candidate opens the file, which then asks for the rate.
  await prompt.getByLabel('Sample format as a SigMF datatype').fill('bogus')
  await prompt.getByRole('button', { name: 'Use format' }).click()
  await expect(prompt.getByRole('alert')).toContainText('not a sample format')
  await prompt.getByRole('button', { name: 'ci16_le' }).click()
  await expect(prompt).toBeHidden()
  await expect(page.getByText('Synthetic demo', { exact: true })).toBeHidden()
  await expect(page.getByRole('region', { name: 'Sample rate needed' })).toBeVisible()
})
