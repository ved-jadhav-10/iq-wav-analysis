import { expect, test, type Page } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'

// The welcome dialog is a first-run thing; every test but the onboarding one starts past it.
test.beforeEach(async ({ page }) => {
  await page.addInitScript("window.localStorage.setItem('sanket.onboarding.v1', 'seen')")
})

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
  await expect(page.getByTestId('start-screen')).toBeVisible()
  await expect(page.getByRole('button', { name: /Open sample/ }).first()).toBeVisible()
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

/** The top bar's Open dropdown, which holds the file picker and the path box. */
async function openMenu(page: Page) {
  if ((await page.locator('#open-menu').count()) === 0) await page.locator('button[aria-controls="open-menu"]').click()
}

async function openByPath(page: Page, path: string) {
  await page.goto('/')
  await openMenu(page)
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
  await expect(page.getByTestId('start-screen')).toBeHidden()
  await expect(page.getByText(/tile · rate unknown/)).toBeVisible()
  await expect(page.getByRole('button', { name: /^#1 / })).toHaveCount(0)

  // The prompt takes its own row; the page still never scrolls as a whole, in either section.
  for (const size of [{ width: 1918, height: 950 }, { width: 1440, height: 800 }]) {
    await page.setViewportSize(size)
    for (const section of ['Dashboard', 'Evidence', 'Hypotheses', 'Summary']) {
      await page.getByRole('navigation', { name: 'Workspace section' }).getByRole('button', { name: section }).click()
      // A string, not a function: the e2e project has no DOM types, and this runs in the page.
      const { scrollHeight, innerHeight } = (await page.evaluate(
        '({ scrollHeight: document.documentElement.scrollHeight, innerHeight: window.innerHeight })',
      )) as { scrollHeight: number; innerHeight: number }
      expect(scrollHeight, `${section} at ${size.width}`).toBeLessThanOrEqual(innerHeight)
    }
  }

  await page.getByRole('navigation', { name: 'Workspace section' }).getByRole('button', { name: 'Dashboard' }).click()
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
  await openMenu(page)
  const picker = page.getByLabel('Upload recording files')

  await picker.setInputFiles({ name: 'bad;name.bin', mimeType: 'application/octet-stream', buffer: toneBytes() })
  await expect(page.getByRole('alert')).toContainText('file names may hold')
  await openMenu(page) // choosing files closes the menu

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

  // The recording replaces the start screen as soon as tiles and boxes exist ...
  await expect(page.getByTestId('start-screen')).toBeHidden()
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
    for (const section of ['Dashboard', 'Evidence', 'Hypotheses', 'Summary']) {
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
  await expect(page.getByTestId('start-screen')).toBeVisible() // nothing was opened
  await expect(prompt.getByRole('list', { name: 'Candidate sample formats' }).getByRole('button')).toHaveCount(4)

  // A bad type is refused with a message; a candidate opens the file, which then asks for the rate.
  await prompt.getByLabel('Sample format as a SigMF datatype').fill('bogus')
  await prompt.getByRole('button', { name: 'Use format' }).click()
  await expect(prompt.getByRole('alert')).toContainText('not a sample format')
  await prompt.getByRole('button', { name: 'ci16_le' }).click()
  await expect(prompt).toBeHidden()
  await expect(page.getByTestId('start-screen')).toBeHidden()
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
      const measure = async () =>
        (await page.evaluate(
          `(() => {
          const r = document.querySelector('[aria-label="Capture quality"]').closest('.fixed').firstElementChild.getBoundingClientRect()
          const tall = Array.from(document.querySelectorAll('body *'))
            .filter((e) => !e.closest('.fixed'))
            .map((e) => ({ e, b: e.getBoundingClientRect().bottom }))
            .sort((x, y) => y.b - x.b)
            .slice(0, 3)
            .map((x) => x.e.tagName + '.' + String(x.e.className).slice(0, 60) + ' ' + Math.round(x.b))
          return { scrollHeight: document.documentElement.scrollHeight, innerHeight: window.innerHeight, top: r.top, bottom: r.bottom, tall }
        })()`,
        )) as { scrollHeight: number; innerHeight: number; top: number; bottom: number; tall: string[] }
      // The charts re-measure a moment after the resize (slower on a busy runner): wait until the
      // layout holds, and say which elements are tallest if it never does.
      await expect
        .poll(async () => {
          const m = await measure()
          return m.scrollHeight <= m.innerHeight ? 'fits' : `page ${m.scrollHeight} > ${m.innerHeight}; tallest: ${m.tall.join(' | ')}`
        }, { message: `page at ${size.width}, pass ${pass}` })
        .toBe('fits')
      const { top, bottom, innerHeight } = await measure()
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
      .filter((e) => e.getClientRects().length > 0 && !e.closest('[role=status], [role=alert], #results-menu, #open-menu'))
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
    const open = document.querySelector('#results-menu, #open-menu, [role=status], [role=alert]')
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
  const download = bar.getByRole('button', { name: /^Download/ })
  const menu = page.getByRole('menu', { name: 'Results downloads' })
  await page.setViewportSize({ width: 1918, height: 950 })

  // The start screen has no recording behind it: no downloads at all.
  await page.goto('/')
  await expect(page.getByTestId('start-screen')).toBeVisible()
  await expect(download).toHaveCount(0)

  // A SigMF recording: every download, the run record and the annotated metadata, but no save.
  const base = testInfo.outputPath('tone')
  writeSigmf(base)
  await openByPath(page, `${base}.sigmf-meta`)
  await expect(download).toBeVisible({ timeout: 60_000 })
  await expect(menu).toHaveCount(0) // one dropdown: nothing sits in the bar until it is opened
  await download.click()
  const runLink = menu.getByRole('menuitem', { name: 'Run record' })
  await expect(runLink).toBeVisible()
  await expect(runLink).toHaveAttribute('href', /\/results\?format=run$/)
  await expect(runLink).toHaveAttribute('title', /time per phase/)
  const sigmfLink = menu.getByRole('menuitem', { name: 'SigMF' })
  await expect(sigmfLink).toHaveAttribute('href', /\/results\?format=sigmf$/)
  await expect(menu.getByRole('menuitem', { name: 'Save as SigMF' })).toHaveCount(0)
  const sigmf = await page.request.get((await sigmfLink.getAttribute('href'))!)
  expect(sigmf.status()).toBe(200)
  expect(((await sigmf.json()) as { global: Record<string, unknown> }).global['core:datatype']).toBe('cf32_le')
  await page.keyboard.press('Escape')
  await expect(menu).toHaveCount(0)

  // A raw file: the same links and a Save button; saving writes the file and says where, and
  // saving again is refused with the server's reason.
  const raw = testInfo.outputPath('capture.bin')
  writeFileSync(raw, toneBytes())
  await openByPath(page, raw)
  await expect(download).toBeVisible({ timeout: 60_000 })
  await download.click()
  const save = menu.getByRole('menuitem', { name: /Save as SigMF/ })
  await expect(save).toBeVisible()
  await expect(save).toHaveAttribute('title', /next to the original.*never touched/)
  await expect(menu.getByRole('menuitem', { name: 'SigMF', exact: true })).toBeVisible()
  await save.click()
  const saved = page.getByRole('status').filter({ hasText: /^Saved / })
  await expect(saved).toContainText('capture.sigmf-meta')
  await saved.getByRole('button', { name: 'Dismiss message' }).click()
  await expect(saved).toHaveCount(0)
  await download.click()
  await menu.getByRole('menuitem', { name: /Save as SigMF/ }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Not saved' })).toContainText('already exists')
  await page.getByRole('button', { name: 'Dismiss message' }).click()

  // At every width, in both themes: the page never scrolls as a whole, and the top bar stays one
  // 48 px row with nothing overflowing or overlapping. Both dropdowns and the save message are
  // opened (and closed again) so their own boxes are measured too.
  const openTrigger = page.locator('button[aria-controls="open-menu"]')
  for (let pass = 0; pass < 2; pass++) {
    for (const size of [
      { width: 1918, height: 950 },
      { width: 1440, height: 800 },
      { width: 1100, height: 800 },
      { width: 900, height: 700 },
      { width: 700, height: 700 },
      { width: 390, height: 800 },
    ]) {
      await page.setViewportSize(size)
      await expect(download).toBeVisible()
      // Wait for the charts to re-measure: a lasting overflow still fails here.
      await expect
        .poll(async () => (await barMetrics(page)).pageOverflow, { message: `${size.width} wide, sideways, pass ${pass}` })
        .toBeLessThanOrEqual(0)
      for (const state of ['closed', 'download', 'open', 'message']) {
        if (state === 'download') await download.click()
        if (state === 'open') await openTrigger.click()
        if (state === 'message') {
          await download.click()
          await menu.getByRole('menuitem', { name: /Save as SigMF/ }).click()
          await expect(page.getByRole('alert')).toContainText('already exists')
        }
        const m = await barMetrics(page)
        const where = `${size.width} wide, ${state}, pass ${pass}: ${JSON.stringify(m)}`
        // Below 900 the workspace's own panels are the known compromise (UI.md); the bar is not.
        if (size.width >= 900) expect(m.scrollHeight, where).toBeLessThanOrEqual(m.innerHeight)
        expect(m.pageOverflow, where).toBeLessThanOrEqual(0)
        expect(m.barHeight, where).toBe(48)
        expect(m.barOverflow, where).toBeLessThanOrEqual(0)
        expect(m.overlaps, where).toEqual([])
        if (state !== 'closed') {
          expect(m.popupLeft, where).toBeGreaterThanOrEqual(0)
          expect(m.popupRight, where).toBeLessThanOrEqual(m.innerWidth)
          expect(m.popupBottom, where).toBeLessThanOrEqual(m.innerHeight)
        }
        if (state === 'download') {
          await expect(menu.getByRole('menuitem', { name: 'Run record' })).toBeVisible()
          await page.keyboard.press('Escape')
          await expect(menu).toHaveCount(0)
        }
        if (state === 'open') {
          await expect(page.getByRole('dialog', { name: 'Open a recording' })).toBeVisible()
          await page.keyboard.press('Escape')
          await expect(page.getByRole('dialog', { name: 'Open a recording' })).toHaveCount(0)
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
  await expect(page.getByRole('banner').getByRole('button', { name: /^Download/ })).toBeVisible({ timeout: 90_000 })

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
  // The start screen shows the section too: nothing is open, and the list is the server's.
  let served: typeof entries = entries
  await page.route('**/api/v1/history', (route) =>
    route.request().method() === 'GET' ? route.fulfill({ json: served }) : route.continue(),
  )
  await page.goto('/')
  await expect(page.getByTestId('start-screen')).toBeVisible()

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

      // The empty list says what makes an entry.
      served = []
      await page.getByRole('button', { name: 'Refresh' }).click()
      await expect(page.getByText(/An analysis that finishes is kept in the workspace/)).toBeVisible()
      m = await measure()
      expect(m.scrollHeight, `${where}, empty`).toBeLessThanOrEqual(m.innerHeight)
      served = entries
      await SECTION_NAV(page).getByRole('button', { name: 'Dashboard' }).click()
    }
    await page.getByRole('button', { name: /^Switch to (light|dark) theme$/ }).click()
  }
})

test('the Summary section fills the window with the finished summary, never of the demo, and never scrolls the page', async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000)
  mkdirSync(testInfo.outputDir, { recursive: true })
  const summary = page.getByRole('main', { name: 'Summary' })
  const text = summary.getByRole('region', { name: 'Summary text' })
  const metrics = async () =>
    (await page.evaluate(`(() => {
      const main = document.querySelector('main[aria-label="Summary"]')
      const body = main && main.querySelector('[aria-label="Summary text"]')
      const panel = body && body.parentElement
      const r = main && main.getBoundingClientRect()
      return {
        scrollHeight: document.documentElement.scrollHeight,
        innerHeight: window.innerHeight,
        pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
        mainBottom: r ? Math.round(r.bottom) : 0,
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

  // The start screen has no summary to offer.
  await page.setViewportSize({ width: 1918, height: 950 })
  await page.goto('/')
  await expect(page.getByTestId('start-screen')).toBeVisible()
  await expect(SECTION_NAV(page).getByRole('button', { name: 'Summary' })).toHaveCount(0)

  // A real recording: the Summary section is a click away and its text is open, nothing to expand.
  const base = testInfo.outputPath('tone')
  writeSigmf(base)
  await page.setViewportSize({ width: 1440, height: 800 })
  await openByPath(page, `${base}.sigmf-meta`)
  await expect(page.getByRole('banner').getByRole('button', { name: /^Download/ })).toBeVisible({ timeout: 90_000 })
  await SECTION_NAV(page).getByRole('button', { name: 'Summary' }).click()
  await expect(summary).toBeVisible()
  await expect(text).toBeVisible()
  await expect(text).toContainText('results summary')
  await expect(text).toContainText('Taken as given about the recording:')
  await expect(text).toContainText('Not proved:')
  await expect(text).toContainText('Results SHA-256')
  await page.getByRole('banner').getByRole('button', { name: /^Download/ }).click()
  const served = await page.request.get(
    (await page.getByRole('menuitem', { name: 'Summary' }).getAttribute('href'))!,
  )
  expect(served.status()).toBe(200)
  expect(await text.innerText()).toContain((await served.text()).split('\n')[0]!)
  await page.keyboard.press('Escape')

  // A long summary scrolls inside its own panel; the page never scrolls, at both widths and in
  // both themes.
  const long = ['Sanket test results summary', ...Array.from({ length: 300 }, (_, i) => `  - line ${i}: a value (estimated)`)].join('\n')
  await page.route('**/results?format=txt', (route) => route.fulfill({ contentType: 'text/plain', body: long }))
  await page.reload()
  await openByPath(page, `${base}.sigmf-meta`)
  await SECTION_NAV(page).getByRole('button', { name: 'Summary' }).click()
  await expect(text).toContainText('line 299', { timeout: 90_000 })
  for (let pass = 0; pass < 2; pass++) {
    for (const size of [
      { width: 1918, height: 950 },
      { width: 1440, height: 800 },
    ]) {
      await page.setViewportSize(size)
      const where = `${size.width} wide, pass ${pass}`
      await expect
        .poll(async () => (await metrics()).pageOverflow, { message: `${where}, sideways` })
        .toBeLessThanOrEqual(0)
      const m = await metrics()
      expect(m.scrollHeight, where).toBeLessThanOrEqual(m.innerHeight)
      expect(m.mainBottom, where).toBeLessThanOrEqual(m.innerHeight)
      expect(m.panelScroll, where).toBeGreaterThan(m.panelClient) // the text scrolls in its panel
      expect(m.panelClient, where).toBeGreaterThan(300) // and the panel is most of the window
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
  await SECTION_NAV(page).getByRole('button', { name: 'Summary' }).click()
  const summary = page.getByRole('main', { name: 'Summary' })
  await expect(summary.getByRole('alert')).toContainText('Could not load the summary: the report broke', {
    timeout: 90_000,
  })
  failing = false
  await summary.getByRole('button', { name: 'Retry' }).click()
  await expect(summary.getByRole('region', { name: 'Summary text' })).toContainText('results summary')
  await expect(summary.getByRole('alert')).toHaveCount(0)
})

const SIZES = [
  { width: 1918, height: 950 },
  { width: 1440, height: 800 },
]

/** Whether the page scrolls as a whole, and by how much it overflows sideways. A string, not a
 * function: the e2e project has no DOM types, and this runs in the page. */
async function pageFit(page: Page) {
  const measure = async () =>
    (await page.evaluate(
      '({ scrollHeight: document.documentElement.scrollHeight, innerHeight: window.innerHeight, overflowX: document.documentElement.scrollWidth - window.innerWidth })',
    )) as { scrollHeight: number; innerHeight: number; overflowX: number }
  // Charts and observers re-measure a moment after a resize: take the layout once it holds still.
  let last = await measure()
  for (let i = 0; i < 10; i++) {
    await page.waitForTimeout(120)
    const next = await measure()
    if (JSON.stringify(next) === JSON.stringify(last)) return next
    last = next
  }
  return last
}

test('the start screen offers the samples, fills the window and never scrolls the page, in both themes', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('start-screen')).toBeVisible()
  // The bundled samples (at least the original four), each labelled synthetic.
  await expect(page.getByRole('button', { name: /Open sample/ }).first()).toBeVisible()
  const cards = await page.getByRole('button', { name: /Open sample/ }).count()
  expect(cards).toBeGreaterThanOrEqual(4)
  await expect(page.getByText('Synthetic', { exact: true })).toHaveCount(cards)
  for (let pass = 0; pass < 2; pass++) {
    for (const size of SIZES) {
      await page.setViewportSize(size)
      const fit = await pageFit(page)
      expect(fit.scrollHeight, `${size.width} wide, pass ${pass}`).toBeLessThanOrEqual(fit.innerHeight)
      expect(fit.overflowX, `${size.width} wide, pass ${pass}`).toBeLessThanOrEqual(0)
    }
    await page.getByRole('button', { name: /^Switch to (light|dark) theme$/ }).click()
  }
  // With nothing open, only the sections that have something to show are in the nav.
  const nav = SECTION_NAV(page)
  await expect(nav.getByRole('button', { name: 'Dashboard' })).toBeVisible()
  await expect(nav.getByRole('button', { name: 'History' })).toBeVisible()
  for (const name of ['Evidence', 'Hypotheses', 'Summary', 'Assumptions']) {
    await expect(nav.getByRole('button', { name })).toHaveCount(0)
  }
})

test('a sample opens from its card and its analysis reaches VERIFIED', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/')
  await page.locator('[data-sample="scene_fsk"]').click()
  await expect(page.getByTestId('start-screen')).toBeHidden()
  await expect(page.getByText('Synthetic recording', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: /^Analysing signal/ })).toHaveCount(0, { timeout: 150_000 })
  await expect(page.getByText('Verified', { exact: true }).first()).toBeVisible()
  // The dashboard has all three plots; an FSK signal has neither constellation nor eye, and says so.
  await expect(page.getByRole('region', { name: 'Constellation' })).toContainText('Not applicable')
  await expect(page.getByRole('region', { name: 'Eye diagram' })).toContainText('Not applicable')
  for (const size of SIZES) {
    await page.setViewportSize(size)
    const fit = await pageFit(page)
    expect(fit.scrollHeight, `${size.width} wide`).toBeLessThanOrEqual(fit.innerHeight)
  }
})

test('Alt+5 opens the Assumptions modal over the section instead of blanking the workspace', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/')
  await page.locator('[data-sample="scene_fsk"]').click()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  await page.keyboard.press('Alt+5')
  const dialog = page.getByRole('dialog', { name: /Assumptions/ })
  await expect(dialog).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  // The section is still the Dashboard, and a reload does not land on a blank page.
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  await page.reload()
  await expect(page.getByTestId('start-screen')).toBeVisible()
})

test('the logo returns to the start screen without a reload, and a sample opens again from there', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/')
  // Already home: the brand is not a control.
  await expect(page.getByRole('button', { name: /back to the start screen/ })).toHaveCount(0)
  await page.locator('[data-sample="scene_fsk"]').click()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  await page.getByRole('button', { name: /back to the start screen/ }).click()
  await expect(page.getByTestId('start-screen')).toBeVisible()
  await expect(page.getByRole('button', { name: /back to the start screen/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Open sample/ }).first()).toBeVisible()
  // From History too, which is where the logo would otherwise be dead.
  await SECTION_NAV(page).getByRole('button', { name: 'History' }).click()
  await page.getByRole('button', { name: /back to the start screen/ }).click()
  await expect(page.getByTestId('start-screen')).toBeVisible()
  await page.locator('[data-sample="scene_fsk"]').click()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  const fit = await pageFit(page)
  expect(fit.scrollHeight).toBeLessThanOrEqual(fit.innerHeight)
})

test('first run shows the welcome once; Skip remembers it and Help brings it back', async ({ page }) => {
  // Only on the first load: the reload below must find what the dialog remembered.
  await page.addInitScript(
    "if (!window.sessionStorage.getItem('fresh')) { window.sessionStorage.setItem('fresh', '1'); window.localStorage.removeItem('sanket.onboarding.v1') }",
  )
  await page.goto('/')
  const welcome = page.getByRole('dialog', { name: /Blind signal analysis/ })
  await expect(welcome).toBeVisible()
  // The five evidence levels, as glyph + word.
  for (const level of ['Verified', 'Measured', 'Estimated', 'Hypothesis', 'Unknown']) {
    await expect(welcome.getByText(level, { exact: true })).toBeVisible()
  }
  for (const size of SIZES) {
    await page.setViewportSize(size)
    const fit = await pageFit(page)
    expect(fit.scrollHeight, `${size.width} wide`).toBeLessThanOrEqual(fit.innerHeight)
  }
  await page.keyboard.press('Escape')
  await expect(welcome).toBeHidden()
  expect(await page.evaluate("window.localStorage.getItem('sanket.onboarding.v1')")).toBe('seen')
  await page.reload()
  await expect(page.getByTestId('start-screen')).toBeVisible()
  await expect(welcome).toBeHidden()
  await page.getByRole('button', { name: /Help/ }).click()
  await expect(welcome).toBeVisible()
})

test('the guided tour walks the real dashboard and the page never scrolls at any step', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/')
  await page.locator('[data-sample="scene_fsk"]').click()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: /^Analysing signal/ })).toHaveCount(0, { timeout: 150_000 })
  await page.getByRole('button', { name: /Help/ }).click()
  await page.getByRole('button', { name: 'Take the tour' }).click()
  const popover = page.locator('.driver-popover')
  await expect(popover).toBeVisible()
  const titles: string[] = []
  for (let step = 0; step < 14; step++) {
    titles.push(await popover.locator('.driver-popover-title').innerText())
    const fit = await pageFit(page)
    expect(fit.scrollHeight, `tour step ${step}`).toBeLessThanOrEqual(fit.innerHeight)
    const box = await popover.boundingBox()
    // The popover sits inside the viewport.
    expect(box && box.x >= 0 && box.y >= 0 && box.x + box.width <= fit.innerHeight * 4).toBeTruthy()
    const done = popover.getByRole('button', { name: 'Done' })
    if (await done.isVisible()) {
      await done.click()
      break
    }
    await popover.getByRole('button', { name: 'Next' }).click()
    // Moving to a step in another section takes a moment: wait for the new step before measuring.
    await expect(popover.locator('.driver-popover-title')).not.toHaveText(titles[titles.length - 1]!)
  }
  await expect(popover).toBeHidden()
  // It went through the other sections too, and came back to the Dashboard it started on.
  for (const title of ['Constellation', 'Eye diagram', 'Evidence', 'Hypotheses', 'Plain-language summary', 'Download']) {
    expect(titles, title).toContain(title)
  }
  await expect(page.getByRole('region', { name: 'Eye diagram' })).toBeVisible()
})

test('a known-system sample shows its decoded messages and the bit stream, without scrolling the page', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/')
  await page.locator('[data-sample="scene_systems"]').click()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: /^Analysing signal/ })).toHaveCount(0, { timeout: 150_000 })
  // The POCSAG pages, as text, under their own level (the text rests on a convention).
  await SECTION_NAV(page).getByRole('button', { name: 'Evidence' }).click()
  const card = page.getByRole('region', { name: 'Decoded message' })
  await expect(card).toBeVisible()
  await expect(card).toContainText('SANKET DEMO PAGE ONE')
  await expect(card.getByText('Hypothesis', { exact: true })).toBeVisible()
  // The NAVTEX warning is on the second signal.
  await page.getByRole('button', { name: /^#2 / }).click()
  await expect(page.getByRole('region', { name: 'Decoded message' })).toContainText('GALE WARNING ARABIAN SEA')
  await page.getByRole('tab', { name: /^Bit stream/ }).click()
  await expect(page.getByText('Sync-word recurrence', { exact: false }).first()).toBeVisible()
  // The pattern search: "GALE" in ASCII hex is found, and the bytes can be shown as bits.
  const find = page.getByLabel(/^Pattern to search for/)
  await find.fill('47 41 4C 45')
  await expect(page.getByRole('status').filter({ hasText: /hits? in/ })).toBeVisible()
  await page.getByRole('button', { name: 'Bits', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Frame bytes' })).toContainText('01000111')
  await find.fill('4')
  await expect(page.getByText(/Not a pattern/)).toBeVisible()
  await find.fill('')
  // The AIS signal has enough frames passing their CRC to compare bit by bit: its fixed fields and
  // the point where the bits start to vary are found by correlation.
  await page.getByRole('button', { name: /^#3 / }).click()
  await page.getByRole('tab', { name: /^Bit stream/ }).click()
  await expect(page.getByRole('heading', { name: 'Header and payload by correlation' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Fields found' })).toContainText('Constant')
  for (const size of SIZES) {
    await page.setViewportSize(size)
    // The charts re-measure a moment after the resize, so wait for the settled layout.
    await expect
      .poll(async () => (await pageFit(page)).overflowX, { message: `${size.width} wide, sideways` })
      .toBeLessThanOrEqual(0)
    const fit = await pageFit(page)
    expect(fit.scrollHeight, `${size.width} wide`).toBeLessThanOrEqual(fit.innerHeight)
  }
})

test('the raw sample opens with its sample rate UNKNOWN and asks for it', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/')
  await page.locator('[data-sample="scene_raw"]').click()
  const prompt = page.getByRole('region', { name: 'Sample rate needed' })
  await expect(prompt).toBeVisible()
  await page.getByLabel('Sample rate in samples per second').fill('1M')
  await page.getByLabel('Sample rate in samples per second').press('Enter')
  await expect(prompt).toBeHidden()
  await expect(page.getByRole('status').filter({ hasText: /^Analysing signal/ })).toHaveCount(0, { timeout: 150_000 })
  await expect(page.getByText('Verified', { exact: true }).first()).toBeVisible()
})

test('the dashboard draws the waterfall, constellation and eye together and every plot fits its box', async ({ page }, testInfo) => {
  test.setTimeout(180_000)
  mkdirSync(testInfo.outputDir, { recursive: true })
  await page.goto('/')
  await page.locator('[data-sample="scene"]').click()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: /^Analysing signal/ })).toHaveCount(0, { timeout: 150_000 })
  // A QPSK signal is selected first: the constellation and the eye are both real canvases.
  const constellation = page.getByRole('img', { name: /constellation, \d+ symbols$/ })
  const eye = page.getByRole('img', { name: /eye diagram, I and Q/ })
  await expect(constellation).toBeVisible()
  await expect(eye).toBeVisible()
  const fits = async () =>
    (await page.evaluate(`(() => {
      const box = (e) => e.getBoundingClientRect()
      const inside = (inner, outer) => inner.left >= outer.left - 1 && inner.right <= outer.right + 1 && inner.top >= outer.top - 1 && inner.bottom <= outer.bottom + 1
      const card = (name) => document.querySelector('section[aria-label="' + name + '"]')
      const wf = document.querySelector('[aria-label^="Waterfall of the capture"]')
      return {
        scrollHeight: document.documentElement.scrollHeight,
        innerHeight: window.innerHeight,
        pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
        wide: Array.from(document.querySelectorAll('body *')).filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1 && e.getClientRects().length > 0).slice(0, 4).map((e) => e.tagName + '.' + String(e.className).slice(0, 50) + ':' + Math.round(e.getBoundingClientRect().right)),
        constellationInside: inside(box(card('Constellation').querySelector('canvas')), box(card('Constellation'))),
        eyeInside: inside(box(card('Eye diagram').querySelector('canvas')), box(card('Eye diagram'))),
        constellationH: Math.round(box(card('Constellation')).height),
        eyeH: Math.round(box(card('Eye diagram')).height),
        waterfallCanvas: wf ? wf.querySelector('canvas').height : -1,
        waterfallBox: wf ? Math.round(wf.getBoundingClientRect().height * (window.devicePixelRatio || 1)) : -1,
      }
    })()`)) as {
      scrollHeight: number
      innerHeight: number
      pageOverflow: number
      wide: string[]
      constellationInside: boolean
      eyeInside: boolean
      constellationH: number
      eyeH: number
      waterfallCanvas: number
      waterfallBox: number
    }
  for (let pass = 0; pass < 2; pass++) {
    for (const size of [
      { width: 1918, height: 950 },
      { width: 1440, height: 800 },
    ]) {
      await page.setViewportSize(size)
      // The charts re-measure a moment after the resize: wait until the layout holds.
      await expect
        .poll(async () => {
          const f = await fits()
          return f.pageOverflow <= 0 && f.waterfallCanvas === f.waterfallBox
        }, { message: `${size.width} wide, settling: ${JSON.stringify(await fits())}` })
        .toBe(true)
      const m = await fits()
      const where = `${size.width} wide, pass ${pass}: ${JSON.stringify(m)}`
      expect(m.scrollHeight, where).toBeLessThanOrEqual(m.innerHeight)
      expect(m.constellationInside, where).toBe(true)
      expect(m.eyeInside, where).toBe(true)
      expect(m.constellationH, where).toBeGreaterThan(120)
      expect(m.eyeH, where).toBeGreaterThan(120)
      expect(m.waterfallCanvas, where).toBe(m.waterfallBox)
      await page.screenshot({ path: testInfo.outputPath(`dashboard-${size.width}-${pass}.png`) })
    }
    await page.getByRole('button', { name: /^Switch to (light|dark) theme$/ }).click()
  }
})

test('the logo leaves for the start screen in one click even while the tour dims the page', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/')
  await page.locator('[data-sample="scene_fsk"]').click()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  await page.getByRole('button', { name: 'Help' }).click()
  await page.getByRole('button', { name: /Take the tour/ }).click()
  await expect(page.locator('.driver-popover')).toBeVisible()
  // The overlay covers the logo, so Playwright's own hit test refuses; force sends the click to
  // the logo's position, as a mouse would.
  await page.getByRole('button', { name: /back to the start screen/ }).click({ force: true })
  await expect(page.getByTestId('start-screen')).toBeVisible()
  await expect(page.locator('.driver-popover')).toHaveCount(0)
  await expect(page.locator('.driver-overlay')).toHaveCount(0)
})

test('during the tour the Open menu shows in full, clear of the popover, at every width', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/')
  await page.locator('[data-sample="scene_fsk"]').click()
  await expect(page.getByRole('button', { name: /^#1 / })).toBeVisible()
  const rect = (selector: string) =>
    `(() => { const r = document.querySelector('${selector}').getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom } })()`
  type Box = { l: number; t: number; r: number; b: number }
  for (const size of [
    { width: 1918, height: 950 },
    { width: 1440, height: 800 },
    { width: 1280, height: 720 },
    { width: 1100, height: 760 },
    { width: 900, height: 700 },
  ]) {
    await page.setViewportSize(size)
    await page.getByRole('button', { name: 'Help' }).click()
    await page.getByRole('button', { name: /Take the tour/ }).click()
    await expect(page.locator('.driver-popover')).toBeVisible()
    await expect(page.locator('.driver-popover-title')).toHaveText('Open any recording')
    await page.locator('button[aria-controls="open-menu"]').click()
    const menu = page.locator('#open-menu')
    await expect(menu).toBeVisible()
    const where = `${size.width} wide`
    const m = (await page.evaluate(rect('#open-menu'))) as Box
    const p = (await page.evaluate(rect('.driver-popover'))) as Box
    const apart = p.r <= m.l || p.l >= m.r || p.b <= m.t || p.t >= m.b
    expect(apart, `${where}: popover ${JSON.stringify(p)} vs menu ${JSON.stringify(m)}`).toBe(true)
    // Above the dimming overlay: what is at the menu's centre is the menu itself.
    const top = await page.evaluate(
      `(() => { const e = document.elementFromPoint(${(m.l + m.r) / 2}, ${m.t + 20}); return e ? e.closest('#open-menu') !== null : false })()`,
    )
    expect(top, `${where}: the menu is under the overlay`).toBe(true)
    await page.keyboard.press('Escape') // ends the tour
    await expect(page.locator('.driver-popover')).toHaveCount(0)
    if (await menu.isVisible()) await page.locator('button[aria-controls="open-menu"]').click()
  }
})
