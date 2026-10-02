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

test('the Assumptions modal shows the capture quality, and the page still never scrolls', async ({
  page,
}, testInfo) => {
  test.setTimeout(120_000)
  const base = testInfo.outputPath('tone')
  mkdirSync(testInfo.outputDir, { recursive: true })
  writeSigmf(base)
  await openByPath(page, `${base}.sigmf-meta`)
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()

  const open = () =>
    page.getByRole('navigation', { name: 'Workspace section' }).getByRole('button', { name: 'Assumptions' }).click()
  await open()
  const modal = page.getByRole('heading', { name: 'Configuration & Assumptions' }).locator('xpath=ancestor::div[3]')
  const quality = modal.getByRole('region', { name: 'Capture quality' })
  await expect(quality).toBeVisible()
  // A complex recording: clipping, DC offset, both I/Q imbalances and gaps, each with its level.
  for (const name of ['Clipping', 'DC offset', 'I/Q gain imbalance', 'I/Q phase imbalance', 'Dropped-sample gaps']) {
    await expect(quality.getByRole('heading', { name, exact: true })).toBeVisible()
  }
  await expect(quality.getByText('Estimated', { exact: true })).toHaveCount(2)

  // With the modal open, in both themes and at both widths, the page does not scroll as a whole
  // and the modal fits the window (its own content scrolls inside it).
  for (let pass = 0; pass < 2; pass++) {
    if (pass > 0) await open()
    for (const size of [{ width: 1918, height: 950 }, { width: 1440, height: 800 }]) {
      await page.setViewportSize(size)
      const { scrollHeight, innerHeight, top, bottom } = (await page.evaluate(
        `(() => {
          const r = document.querySelector('[aria-label="Capture quality"]').closest('.fixed').firstElementChild.getBoundingClientRect()
          return { scrollHeight: document.documentElement.scrollHeight, innerHeight: window.innerHeight, top: r.top, bottom: r.bottom }
        })()`,
      )) as { scrollHeight: number; innerHeight: number; top: number; bottom: number }
      expect(scrollHeight, `page at ${size.width}, pass ${pass}`).toBeLessThanOrEqual(innerHeight)
      expect(top).toBeGreaterThanOrEqual(0)
      expect(bottom).toBeLessThanOrEqual(innerHeight)
    }
    await modal.getByRole('button', { name: 'Close' }).click()
    await page.getByRole('button', { name: /^Switch to (light|dark) theme$/ }).click()
  }
})


/** The top bar's measurements (a string, not a function: the e2e project has no DOM types): its
 * height, whether its content overflows it or the page, which of its controls overlap another,
 * and where the open menu or message ends. */
async function barMetrics(page: Page) {
  return (await page.evaluate(`(() => {
    const bar = document.querySelector('header')
    const controls = Array.from(bar.querySelectorAll('a, button, input[type=text], label'))
      .filter((e) => e.getClientRects().length > 0 && !e.closest('[role=status], [role=alert], #results-menu'))
      .map((e) => ({ e, r: e.getBoundingClientRect() }))
    const overlaps = []
    for (let i = 0; i < controls.length; i++) {
      for (let j = i + 1; j < controls.length; j++) {
        const a = controls[i], b = controls[j]
        if (a.e.contains(b.e) || b.e.contains(a.e)) continue
        const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left)
        const h = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top)
        if (w > 1 && h > 1) overlaps.push((a.e.textContent || a.e.id).trim().slice(0, 18) + ' x ' + (b.e.textContent || b.e.id).trim().slice(0, 18))
      }
    }
    const wide = Array.from(document.querySelectorAll('body *')).filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1 && e.getClientRects().length > 0)
      .slice(0, 3).map((e) => e.tagName + '.' + String(e.className).slice(0, 40) + ':' + (e.textContent || '').trim().slice(0, 20))
    const open = document.querySelector('#results-menu, [role=status], [role=alert]')
    const o = open && open.getBoundingClientRect()
    return {
      barHeight: bar.getBoundingClientRect().height,
      barOverflow: bar.scrollWidth - bar.clientWidth,
      pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
      scrollHeight: document.documentElement.scrollHeight,
      innerHeight: window.innerHeight,
      overlaps,
      wide,
      popupLeft: o ? o.left : 0,
      popupRight: o ? o.right : 0,
      popupBottom: o ? o.bottom : 0,
      innerWidth: window.innerWidth,
    }
  })()`)) as {
    barHeight: number
    barOverflow: number
    pageOverflow: number
    scrollHeight: number
    innerHeight: number
    overlaps: string[]
    wide: string[]
    popupLeft: number
    popupRight: number
    popupBottom: number
    innerWidth: number
  }
}

test('the results exports follow the recording: SigMF links for SigMF, Save as SigMF for raw, none for the demo', async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000)
  mkdirSync(testInfo.outputDir, { recursive: true })
  const bar = page.getByRole('banner')
  // Wide enough that the downloads sit in the bar itself; narrower ones fold into a Results menu.
  await page.setViewportSize({ width: 1918, height: 950 })

  // The synthetic demo has no recording behind it: no downloads at all.
  await page.goto('/')
  await expect(page.getByText('Synthetic demo', { exact: true })).toBeVisible()
  await expect(bar.getByRole('link', { name: 'Run record' })).toHaveCount(0)
  await expect(bar.getByRole('button', { name: /^Results/ })).toHaveCount(0)
  await expect(bar.getByRole('button', { name: 'Save as SigMF' })).toHaveCount(0)

  // A SigMF recording: every download, the run record and the annotated metadata, but no save.
  const base = testInfo.outputPath('tone')
  writeSigmf(base)
  await openByPath(page, `${base}.sigmf-meta`)
  const runLink = bar.getByRole('link', { name: 'Run record' })
  await expect(runLink).toBeVisible({ timeout: 60_000 })
  await expect(runLink).toHaveAttribute('href', /\/results\?format=run$/)
  await expect(runLink).toHaveAttribute('title', /time per phase/)
  const sigmfLink = bar.getByRole('link', { name: 'SigMF' })
  await expect(sigmfLink).toHaveAttribute('href', /\/results\?format=sigmf$/)
  await expect(bar.getByRole('button', { name: 'Save as SigMF' })).toHaveCount(0)
  const sigmf = await page.request.get((await sigmfLink.getAttribute('href'))!)
  expect(sigmf.status()).toBe(200)
  expect(((await sigmf.json()) as { global: Record<string, unknown> }).global['core:datatype']).toBe('cf32_le')

  // A raw file: the same links and a Save button; saving writes the file and says where, and
  // saving again is refused with the server's reason.
  const raw = testInfo.outputPath('capture.bin')
  writeFileSync(raw, toneBytes())
  await openByPath(page, raw)
  const save = bar.getByRole('button', { name: 'Save as SigMF' })
  await expect(save).toBeVisible({ timeout: 60_000 })
  await expect(save).toHaveAttribute('title', /next to the original.*never touched/)
  await expect(bar.getByRole('link', { name: 'SigMF' })).toBeVisible()
  await save.click()
  const saved = page.getByRole('status').filter({ hasText: /^Saved / })
  await expect(saved).toContainText('capture.sigmf-meta')
  await saved.getByRole('button', { name: 'Dismiss message' }).click()
  await expect(saved).toHaveCount(0)
  await save.click()
  await expect(page.getByRole('alert').filter({ hasText: 'Not saved' })).toContainText('already exists')
  await page.getByRole('button', { name: 'Dismiss message' }).click()

  // At every width, in both themes: the page never scrolls as a whole, and the top bar stays one
  // 48 px row with nothing overflowing or overlapping. Below 1536 the downloads are a menu, which
  // is opened (and closed again with Escape) so its own box is measured too, as is the message.
  for (let pass = 0; pass < 2; pass++) {
    for (const size of [
      { width: 1918, height: 950 },
      { width: 1440, height: 800 },
      { width: 1100, height: 800 },
    ]) {
      await page.setViewportSize(size)
      const folded = size.width < 1536
      const menu = bar.getByRole('button', { name: /^Results/ })
      // The bar switches between the inline links and the menu a moment after the resize.
      await expect(folded ? menu : bar.getByRole('link', { name: 'Run record' })).toBeVisible()
      const states = folded ? ['closed', 'menu', 'message'] : ['closed', 'message']
      for (const state of states) {
        if (state === 'menu') await menu.click()
        if (state === 'message') {
          if (folded) await menu.click()
          await bar.getByRole('button', { name: 'Save as SigMF' }).click()
          await expect(page.getByRole('alert')).toContainText('already exists')
        }
        const m = await barMetrics(page)
        const where = `${size.width} wide, ${state}, pass ${pass}: ${JSON.stringify(m)}`
        expect(m.scrollHeight, where).toBeLessThanOrEqual(m.innerHeight)
        expect(m.pageOverflow, where).toBeLessThanOrEqual(0)
        expect(m.barHeight, where).toBe(48)
        expect(m.barOverflow, where).toBeLessThanOrEqual(0)
        expect(m.overlaps, where).toEqual([])
        if (state !== 'closed') {
          expect(m.popupLeft, where).toBeGreaterThanOrEqual(0)
          expect(m.popupRight, where).toBeLessThanOrEqual(m.innerWidth)
          expect(m.popupBottom, where).toBeLessThanOrEqual(m.innerHeight)
        }
        if (state === 'menu') {
          await expect(bar.getByRole('link', { name: 'Run record' })).toBeVisible()
          await page.keyboard.press('Escape')
          await expect(bar.getByRole('link', { name: 'Run record' })).toHaveCount(0)
        }
        if (state === 'message') await page.getByRole('button', { name: 'Dismiss message' }).click()
      }
    }
    await page.getByRole('button', { name: /^Switch to (light|dark) theme$/ }).click()
  }
})

const SECTION_NAV = (page: Page) => page.getByRole('navigation', { name: 'Workspace section' })

test('History lists a finished analysis, links its downloads and deletes it after an inline confirmation', async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000)
  mkdirSync(testInfo.outputDir, { recursive: true })
  // A name of its own, so this finds its row among whatever earlier runs left in the workspace.
  const base = testInfo.outputPath(`history-${Date.now()}`)
  writeSigmf(base)
  const name = `${base.split(/[\\/]/).pop()}.sigmf-meta`
  await page.setViewportSize({ width: 1918, height: 950 })
  await openByPath(page, `${base}.sigmf-meta`)
  // The analysis has finished once the top bar offers its results.
  await expect(page.getByRole('banner').getByRole('link', { name: 'Run record' })).toBeVisible({ timeout: 90_000 })

  await SECTION_NAV(page).getByRole('button', { name: 'History' }).click()
  await expect(page.getByRole('main', { name: 'History' })).toBeVisible()
  const row = page.getByRole('row').filter({ hasText: name })
  // The list is fetched on opening and when the analysis finishes; Refresh covers the gap between.
  await expect(async () => {
    await page.getByRole('button', { name: 'Refresh' }).click()
    await expect(row).toHaveCount(1, { timeout: 2_000 })
  }).toPass({ timeout: 30_000 })

  await expect(row.getByText('SigMF', { exact: true })).toBeVisible()
  await expect(row.locator('time')).toHaveAttribute('datetime', /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/)
  await expect(row.locator('td[title$="(UTC)"]')).toHaveCount(1)
  const json = row.getByRole('link', { name: 'JSON' })
  const href = (await json.getAttribute('href'))!
  expect(href).toMatch(/^\/api\/v1\/history\/[0-9a-f]+\/results\?format=json$/)
  await expect(json).toHaveAttribute('download', '')
  for (const label of ['CSV', 'Summary', 'PDF', 'Run record']) {
    await expect(row.getByRole('link', { name: label })).toBeVisible()
  }
  const hash = (await row.locator('code').getAttribute('title'))!
  expect(hash).toMatch(/^[0-9a-f]{64}$/)
  await expect(row.locator('code')).toHaveText(hash.slice(0, 12))
  const kept = await page.request.get(href)
  expect(kept.status()).toBe(200)
  expect(((await kept.json()) as { signals: unknown[] }).signals.length).toBeGreaterThan(0)

  // Delete asks first, in the row; Cancel keeps it; a failing server shows its own text.
  const id = href.split('/')[4]!
  await row.getByRole('button', { name: /^Delete the analysis of / }).click()
  const confirm = page.getByRole('group', { name: `Confirm deleting ${name}` })
  await expect(confirm).toContainText('Delete this analysis and everything derived from it?')
  await confirm.getByRole('button', { name: 'Cancel' }).click()
  await expect(confirm).toHaveCount(0)
  await expect(row).toHaveCount(1)

  await page.route(`**/api/v1/history/${id}`, (route) =>
    route.request().method() === 'DELETE'
      ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"the disk is full"}' })
      : route.continue(),
  )
  await row.getByRole('button', { name: /^Delete the analysis of / }).click()
  await confirm.getByRole('button', { name: 'Delete', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Not deleted: the disk is full' })).toBeVisible()
  await expect(row).toHaveCount(1)
  await page.unroute(`**/api/v1/history/${id}`)

  await confirm.getByRole('button', { name: 'Delete', exact: true }).click()
  await expect(row).toHaveCount(0)
  expect((await page.request.get(href)).status()).toBe(404)
  const listed = (await (await page.request.get('/api/v1/history')).json()) as { id: string }[]
  expect(listed.map((e) => e.id)).not.toContain(id)
})

test('History fills the window and its table scrolls inside its own panel, in both themes', async ({ page }) => {
  const entries = Array.from({ length: 40 }, (_, i) => ({
    id: `e${String(i).padStart(30, '0')}`,
    createdUtc: `2026-03-${String(1 + (i % 28)).padStart(2, '0')}T0${i % 10}:15:00Z`,
    name: `a-rather-long-recording-name-number-${i}-from-the-field-trip.sigmf-meta`,
    container: i % 2 ? 'raw' : 'SigMF',
    signals: 1 + (i % 5),
    verified: i % 3,
    resultsSha256: (i + 1).toString(16).padStart(2, '0').repeat(32),
  }))
  // The demo shows the section too: nothing is open, and the list is the server's.
  let served: typeof entries = entries
  await page.route('**/api/v1/history', (route) =>
    route.request().method() === 'GET' ? route.fulfill({ json: served }) : route.continue(),
  )
  await page.goto('/')
  await expect(page.getByText('Synthetic demo', { exact: true })).toBeVisible()

  const measure = async () =>
    (await page.evaluate(`(() => {
      const main = document.querySelector('main[aria-label="History"]')
      const panel = main.querySelector('.overflow-auto')
      const r = main.getBoundingClientRect()
      return {
        scrollHeight: document.documentElement.scrollHeight,
        innerHeight: window.innerHeight,
        pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
        mainBottom: r.bottom,
        panelScroll: panel ? panel.scrollHeight : 0,
        panelClient: panel ? panel.clientHeight : 0,
      }
    })()`)) as {
      scrollHeight: number
      innerHeight: number
      pageOverflow: number
      mainBottom: number
      panelScroll: number
      panelClient: number
    }

  for (let pass = 0; pass < 2; pass++) {
    for (const size of [
      { width: 1918, height: 950 },
      { width: 1440, height: 800 },
    ]) {
      await page.setViewportSize(size)
      await SECTION_NAV(page).getByRole('button', { name: 'History' }).click()
      await expect(page.getByRole('row')).toHaveCount(41) // the header and 40 entries
      const where = `${size.width} wide, pass ${pass}`
      let m = await measure()
      expect(m.scrollHeight, where).toBeLessThanOrEqual(m.innerHeight)
      expect(m.pageOverflow, where).toBeLessThanOrEqual(0)
      expect(m.mainBottom, where).toBeLessThanOrEqual(m.innerHeight)
      // 40 rows do not fit: the panel holds the overflow, so the page does not.
      expect(m.panelScroll, where).toBeGreaterThan(m.panelClient)

      // An open confirmation adds a row and still changes nothing outside the panel.
      await page.getByRole('button', { name: /^Delete the analysis of / }).first().click()
      await expect(page.getByRole('group', { name: /^Confirm deleting / })).toBeVisible()
      m = await measure()
      expect(m.scrollHeight, `${where}, confirming`).toBeLessThanOrEqual(m.innerHeight)
      expect(m.pageOverflow, `${where}, confirming`).toBeLessThanOrEqual(0)
      await page.getByRole('button', { name: 'Cancel' }).click()

      // The empty list, with the demo's own wording.
      served = []
      await page.getByRole('button', { name: 'Refresh' }).click()
      await expect(page.getByText(/synthetic demo is generated in the browser/i)).toBeVisible()
      m = await measure()
      expect(m.scrollHeight, `${where}, empty`).toBeLessThanOrEqual(m.innerHeight)
      served = entries
      await SECTION_NAV(page).getByRole('button', { name: 'Survey' }).click()
    }
    await page.getByRole('button', { name: /^Switch to (light|dark) theme$/ }).click()
  }
})

test('the plain-language summary tops the Survey of a finished recording, never of the demo, and never scrolls the page', async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000)
  mkdirSync(testInfo.outputDir, { recursive: true })
  const summary = page.getByRole('region', { name: 'Plain-language summary' })
  const toggle = summary.getByRole('button', { name: /^Summary/ })
  const text = summary.getByRole('region', { name: 'Summary text' })
  const metrics = async () =>
    (await page.evaluate(`(() => {
      const strip = document.querySelector('section[aria-label="Plain-language summary"]')
      const body = strip && strip.querySelector('[aria-label="Summary text"]')
      const rail = document.querySelector('nav[aria-label="Detections and pipeline"]')
      const r = strip && strip.getBoundingClientRect()
      return {
        scrollHeight: document.documentElement.scrollHeight,
        innerHeight: window.innerHeight,
        pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
        stripHeight: r ? Math.round(r.height) : 0,
        stripBottom: r ? Math.round(r.bottom) : 0,
        railTop: rail ? Math.round(rail.getBoundingClientRect().top) : 0,
        bodyScroll: body ? body.scrollHeight : 0,
        bodyClient: body ? body.clientHeight : 0,
        wide: Array.from(document.querySelectorAll('body *')).filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1 && e.getClientRects().length > 0).slice(0, 4).map((e) => e.tagName + '.' + String(e.className).slice(0, 50) + ':' + Math.round(e.getBoundingClientRect().right)),
      }
    })()`)) as {
      wide: string[]
      scrollHeight: number
      innerHeight: number
      pageOverflow: number
      stripHeight: number
      stripBottom: number
      railTop: number
      bodyScroll: number
      bodyClient: number
    }

  // The synthetic in-browser capture is labelled as such and has no summary.
  await page.setViewportSize({ width: 1918, height: 950 })
  await page.goto('/')
  await expect(page.getByText('Synthetic demo', { exact: true })).toBeVisible()
  await expect(summary).toHaveCount(0)

  // A real recording: the summary appears once its analysis has finished, above the pipeline rail.
  // With nothing remembered it starts collapsed in a short window (it would leave the waterfall
  // about 90px) and open in a tall one.
  const base = testInfo.outputPath('tone')
  writeSigmf(base)
  await page.setViewportSize({ width: 1440, height: 800 })
  await page.goto('/')
  await openByPath(page, `${base}.sigmf-meta`)
  await expect(page.getByRole('banner').getByRole('button', { name: /^Results/ })).toBeVisible({ timeout: 90_000 })
  await expect(summary).toBeVisible()
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await page.setViewportSize({ width: 1918, height: 950 })
  await page.reload()
  await openByPath(page, `${base}.sigmf-meta`)
  await expect(page.getByRole('banner').getByRole('link', { name: 'Run record' })).toBeVisible({ timeout: 90_000 })
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(text).toContainText('results summary')
  await expect(text).toContainText('Taken as given about the recording:')
  await expect(text).toContainText('Not proved:')
  await expect(text).toContainText('Results SHA-256')
  const served = await page.request.get(`${(await page.getByRole('banner').getByRole('link', { name: 'Summary' }).getAttribute('href'))!}`)
  expect(served.status()).toBe(200)
  expect(await text.innerText()).toContain((await served.text()).split('\n')[0]!)
  let m = await metrics()
  expect(m.stripBottom, 'the strip sits above the pipeline rail').toBeLessThanOrEqual(m.railTop)

  // Keyboard: the toggle is reachable, Enter collapses it, and the choice survives a reload.
  await toggle.focus()
  await page.keyboard.press('Enter')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(text).toBeHidden()
  await page.reload()
  await expect(page.getByText('Synthetic demo', { exact: true })).toBeVisible() // a reload opens nothing
  await openByPath(page, `${base}.sigmf-meta`)
  await expect(toggle).toBeVisible({ timeout: 90_000 })
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(text).toBeVisible()

  // A long summary scrolls inside its own panel; the page never scrolls, collapsed or open, at
  // both widths and in both themes.
  const long = ['Sanket test results summary', ...Array.from({ length: 300 }, (_, i) => `  - line ${i}: a value (estimated)`)].join('\n')
  await page.route('**/results?format=txt', (route) => route.fulfill({ contentType: 'text/plain', body: long }))
  await page.reload()
  await openByPath(page, `${base}.sigmf-meta`)
  await expect(text).toContainText('line 299', { timeout: 90_000 })
  for (let pass = 0; pass < 2; pass++) {
    for (const size of [
      { width: 1918, height: 950 },
      { width: 1440, height: 800 },
    ]) {
      await page.setViewportSize(size)
      // The top bar folds its downloads into a menu below 1536 a moment after the resize.
      const bar = page.getByRole('banner')
      await expect(
        size.width < 1536 ? bar.getByRole('button', { name: /^Results/ }) : bar.getByRole('link', { name: 'Run record' }),
      ).toBeVisible()
      for (const open of [true, false]) {
        if ((await toggle.getAttribute('aria-expanded')) !== String(open)) await toggle.click()
        const where = `${size.width} wide, ${open ? 'expanded' : 'collapsed'}, pass ${pass}`
        m = await metrics()
        expect(m.scrollHeight, where).toBeLessThanOrEqual(m.innerHeight)
        expect(m.pageOverflow, where + JSON.stringify(m.wide)).toBeLessThanOrEqual(0)
        expect(m.stripBottom, where).toBeLessThanOrEqual(m.railTop)
        if (open) {
          expect(m.bodyScroll, where).toBeGreaterThan(m.bodyClient) // the text scrolls in its panel ...
          expect(m.stripHeight, where).toBeLessThanOrEqual(28 + 160 + 8) // ... and the panel is bounded
        } else {
          expect(m.stripHeight, where).toBeLessThanOrEqual(30)
        }
      }
    }
    await page.getByRole('button', { name: /^Switch to (light|dark) theme$/ }).click()
  }
  await page.unroute('**/results?format=txt')
})

test('a summary that cannot be fetched says why, and Retry fetches it again', async ({ page }, testInfo) => {
  test.setTimeout(180_000)
  mkdirSync(testInfo.outputDir, { recursive: true })
  const base = testInfo.outputPath('tone')
  writeSigmf(base)
  let failing = true
  await page.setViewportSize({ width: 1918, height: 950 })
  await page.route('**/results?format=txt', (route) =>
    failing
      ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"the report broke"}' })
      : route.continue(),
  )
  await openByPath(page, `${base}.sigmf-meta`)
  const summary = page.getByRole('region', { name: 'Plain-language summary' })
  await expect(summary.getByRole('alert')).toContainText('Could not load the summary: the report broke', {
    timeout: 90_000,
  })
  failing = false
  await summary.getByRole('button', { name: 'Retry' }).click()
  await expect(summary.getByRole('region', { name: 'Summary text' })).toContainText('results summary')
  await expect(summary.getByRole('alert')).toHaveCount(0)
})
