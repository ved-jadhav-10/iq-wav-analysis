# The Sanket workspace UI

One shell, several focused views. This is the reference for how the frontend is laid out and — more
importantly — for the layout invariants that three separate bugs violated. Read the invariants
before changing any height, grid or canvas measurement.

## The shell

Everything is inside one column, fixed to the viewport:

```
TopBar      48px   logo · section nav · file name · open box · offline badge · theme
Workspace          the selected section, fills the remaining height
StatusBar    24px   version, provenance, tile shape
```

The shell is `h-full min-h-0`. `html, body, #root` are already `height: 100%` in
`styles/index.css`, so there is no reason for a section to be taller than the window. **The page
itself must never scroll.** Long content scrolls inside its own panel: the evidence rail, the
search ledger and the assumptions view all have their own `overflow-y-auto`.

## Sections

The section decides which regions are on screen and how they're laid out. State lives in `App`,
above the recording-keyed `Workspace`, so opening another recording keeps your section but resets
zoom and selection — those are genuinely different lifetimes.

| Nav item | Layout | Shows |
|---|---|---|
| **Survey** | The plain-language summary strip (a finished real recording only), then detections + pipeline rail, the plot column and the resizable evidence panel | Everything at once. The default. |
| **Waterfall** | Detection chips in a strip, then the plot column full width | The spectrogram and its power spectrum, nothing competing for the display |
| **History** | A header strip, then one table that fills the rest and scrolls inside its own panel | The analyses the server kept in its workspace (they survive a restart): see below |
| **Assumptions** | A modal, not a section | Everything the analysis took as given, over whatever is on screen |

Switch by clicking the nav in the top bar, or with `Alt+1`–`Alt+4` (Assumptions is `Alt+4`). The choice is persisted in
`localStorage` under `sanket.view.v1`, because an analyst who reopens the tool on Survey and has to
click back costs a beat. A bare `1`–`3` is deliberately *not* used: it would fight numeric
fields and the synthetic-capture worker's inputs.

The **Assumptions** item keeps its place in the nav but does not switch the workspace. It opens the
Settings / Assumptions modal instead, because a modal can be summoned over any section and dismissed,
which a section could not do. `TopBar` dispatches on it; `App` renders no view for it. The
per-detection deep dive is handled the same way, as a full-screen overlay.

The nav list lives in `lib/views.ts` and is the only place an item is declared, so the button and the
behaviour cannot drift apart. Its definitions, digit mapping and wrap-around stepping are covered by
`lib/views.test.ts`.

## What each view shows

Before a file is opened, the workspace runs on a synthetic capture generated in the browser and labelled *Synthetic demo* (PLAN M7 replaces it with bundled sample recordings). Once a recording is open, every view shows real engine output:

- **Waterfall:** one box per detection, placed in time and frequency. Frequency is relative to the capture centre when the centre frequency is unknown; levels are relative, not calibrated.
- **Detections list:** each detection's overall level as glyph + word, never colour alone.
- **Pipeline rail:** one evidence level per stage. Sync, Classify, FEC and Frame read VERIFIED only because a CRC passed on this recording. An analog (FM) detection stops after Classify, and says why.
- **Constellation:** the real symbols after timing, carrier and phase recovery. It is empty for FSK, which is decided by tone energy, and for analog signals. For a linear signal a toggle beside its title switches to the **eye diagram**: I and Q traces overlaid over one symbol either side of the symbol instant, with the ideal levels dashed.
- **Evidence cards:** each value with its level, method, evidence, alternatives and warnings; UNKNOWN cards say why and what would settle it (e.g. how many FEC hypotheses were tried).
- **Hypotheses tab (ledger):** *Tried* counts every cell of the search grid (modulation × rotation × code × alignment, interleaver × alignment, RS grid × sync word × CRC), including cells never run. The threshold is corrected for that count, and the best chains that pass it are re-run on shuffled bits: one that also passes there is blocked, shown as rejected with that reason, and counted in the "Shuffled-bit accepts" tile.
- **Frames tab:** start bit, sync word, CRC result, header and payload hex; for a real recording, download links for the table as JSON, CSV, hex and bits.
- **Summary strip (Survey only):** `GET /api/v1/recordings/{id}/results?format=txt` shown above the pipeline rail, see below. Absent for the demo and while the analysis runs.
- **Results download (top bar):** for a recording whose analysis has finished, a `Results` label with `JSON`, `CSV` and `Summary` links (the results document; one row per value with its level and proof; a plain-language text summary). Absent for the demo and while the analysis runs.
- **Assumptions (modal):** container, datatype, sample rate, centre frequency, IQ order and everything else taken as given, each with its level; above them, entry fields for the centre frequency and the IQ order (a swap has the server tile the recording again). Opening a folder lists its recordings in a dialog to pick from; a raw file whose sample format is UNKNOWN opens a prompt strip with the sniffer's candidates; "Join numbered files" beside the path reads `rec_000`, `rec_001`, … as one recording.

## The History section

`components/HistorySection.tsx` lists `GET /api/v1/history` (newest first) as a table: name, container,
finished (local time; the UTC stamp is in the cell's title), signals, the VERIFIED count (the
`EvidenceBadge` glyph and word, or "none verified" in words) and the first 12 hex digits of the results
SHA-256 (full value in a title, with a copy button). Each row has plain `<a download>` links (JSON, CSV,
Summary, PDF, Run record; no SigMF, which needs the recording's files) and a Delete button. Delete opens a
confirmation row straight under the entry ("Delete this analysis and everything derived from it?", Delete
and Cancel; Cancel has focus and Esc cancels); a failing delete shows the server's text in that row, never
an `alert()`.

- The list is fetched when the section opens, when an analysis finishes (App bumps `historyTick` when the
  recording's state turns `done`, at once and again about two seconds later, because the server keeps the
  analysis on its worker thread just after the state turns) and from the Refresh control.
- An empty list says what makes an entry. The demo (no recording open) shows the section with its own
  wording and a *Synthetic demo* label; it still lists whatever the server holds.
- The section renders inside `Workspace`, not beside it, so zoom and selection survive a visit. Layout: a
  `main` that is `flex min-h-0 flex-1 flex-col overflow-hidden`, a fixed 32px strip, and the table in a
  `min-h-0 flex-1 overflow-auto` panel with a sticky header. Measured (e2e, 40 rows, both themes): the
  page's `scrollHeight` equals `innerHeight` at 1918x950 and 1440x800, the panel's content is 1429px in a
  846px / 696px panel, and nothing overflows horizontally.

## The Summary strip

`components/SummaryStrip.tsx` shows the server's plain-language summary (`dsp/summary.py`, a fixed template
over the results document) as it was written: what was proved, what was only estimated, what is unknown
and what would settle it, what rests on a convention. Each line is kept verbatim, in the monospace
tabular face (`num`), with the title, the unindented headings and the Proved / Not proved / Still unknown
subheadings in heavier weights. Levels are in the text's own words, so nothing is colour-only.

- It is mounted by `Workspace` only in the Survey section, for a real recording whose analysis state is
  `done` (`lib/summary.ts` `summaryTarget`); the synthetic in-browser capture, a running analysis and the
  other sections have no strip. A new finish remounts it, so the text is fetched afresh. A recording the
  file itself calls synthetic still has one (the top bar labels it *Synthetic recording*).
- `hooks/useSummary.ts` fetches once per mount. A 409 (the server's state lags the stream's `done` by a
  moment) is retried after 250, 500, 1000 and 2000 ms, then shown; any other failure is shown at once,
  in the server's words, with a Retry button that fetches again.
- The header is one 28px button (`aria-expanded`, `aria-controls`), reachable by Tab, Enter and Space.
  Open or collapsed is remembered in `localStorage` (`sanket.summary.v1`, try/catch). With nothing
  remembered it opens in a window at least 880px tall and starts collapsed below that, because open it
  takes the waterfall's height (1440x800: the waterfall would be left about 94px).
- Layout: a `shrink-0` `section` above the Survey `main` (a direct child of the shell column, outside
  `SplitPane`, so the split's measurement is unaffected). Its text panel is `max-h-[min(22vh,160px)]
  overflow-y-auto` and focusable (`tabindex=0`), so a long summary scrolls inside it and the strip never
  exceeds 29px collapsed or 189px open; `main` is `min-h-0 flex-1` and takes the rest.
- Measured (e2e and a probe, light and dark, a 300-line summary): `scrollHeight` equals `innerHeight` and
  there is no horizontal overflow at 1918x950 and 1440x800, collapsed and open; the strip is 29px / 189px,
  the text panel scrolls 569px of text in 160px, and the waterfall canvas equals its container (1918:
  412px collapsed, 252px open; 1440: 254px collapsed, 94px open).

## The Signal overlay

The per-detection deep dive is a full-screen overlay, **not** a fourth section. You open it to read
one signal end to end and then come back out; giving it a section meant the waterfall lost a third
of the display every time anyone wanted a constellation.

Launch it from **Full screen** in the evidence panel's header. `Esc` closes it and focus lands on
the close button on open. It shows the constellation and every pipeline stage on the left, the
search ledger on the right, and each side scrolls on its own.

## The resizable split

`components/SplitPane.tsx` and `hooks/useSplit.ts` give the plot column and the evidence panel a
draggable, persisted split (`sanket.split.v1`, default 0.68).

- Pointer events, not `mousedown`/`mousemove`, so a drag survives leaving the window.
- The gutter is a focusable `role="separator"` with arrow-key support (shift for bigger steps), so
  the split is reachable without a pointer.
- The fraction is of the space **after** the fixed rail, not of the whole container. A percentage of
  the container hands the rail's width to the plot and leaves the panel short.
- Neither pane can be dragged below 340px.
- The panel also collapses to a tab on the right edge, for when the plot is the point.

The split only applies at 1280px and above. Below that the three panels stack and a gutter would
have nothing useful to divide, so `App` renders a plain grid instead.

## Layout invariants

These are not stylistic. Each one is a bug that already shipped once.

1. **Every grid that contains a plot has an explicit `grid-rows`.** With no `grid-template-rows`
   the implicit row is content-sized, so the plot sizes to its own content and overflows the box
   that was supposed to contain it. `SplitPane` uses `grid-rows-[minmax(0,1fr)]`.

2. **The canvas must never be able to size its own container.** The waterfall's canvas is
   `absolute inset-0 size-full`. If the element containing it ever has an `auto` height, `height:
   100%` resolves against the canvas's `height` *attribute* instead of the parent. The parent then
   grows to match, the `ResizeObserver` measures that grown size and writes it back to the
   attribute. The result is a ratchet: the plot sticks at whatever it was first measured at and
   never shrinks. It held the waterfall at 2681px inside a 956px box. `Waterfall.tsx` therefore
   rejects a zero-height report and anything taller than four viewports.

3. **`min-h-0` on every flex or grid child that should shrink.** A flex item's default
   `min-height: auto` refuses to shrink below its content. This is why the evidence rail grew to
   fit all nine pipeline stages in an auto-height row and dragged the page to 3165px. A wrapper that
   is only a grid item must also carry a definite height (`h-full` on the child) for its own
   `overflow-y-auto` to engage.

4. **The plot column carries `flex-1`.** Without it, in the Waterfall section — where it is a flex
   child rather than a grid item — the waterfall's own `flex-1` had no definite space and collapsed
   to zero, leaving the power spectrum and an empty void.

5. **Evidence is never colour-only** (PLAN §4). The split, the section nav and the detection chips
   all carry words and glyphs as well as colour.

## Checking a layout change

The browser screenshot tool is unreliable, and eyeballing pixels is worse: two rounds of this work
went wrong because a screenshot was read by eye. Measure the DOM instead. A throwaway Playwright
script is the fastest way, and it is how the numbers above were obtained:

```js
const page = await ctx.newPage()
await page.goto('http://127.0.0.1:8765')
await page.waitForSelector('[aria-label^="Waterfall of the capture"]')
const m = await page.evaluate(() => ({
  doc: document.documentElement.scrollHeight,
  view: window.innerHeight,
  wf: Math.round(document.querySelector('[role="img"]').getBoundingClientRect().height),
  canvas: document.querySelector('canvas').height,
}))
```

`doc` must equal `view` in every section, and `canvas` must equal `wf`. Playwright's bundled
Chromium may be a broken install; point `executablePath` at an older
`%LOCALAPPDATA%\ms-playwright\chromium-<build>\chrome-win64\chrome.exe` if it fails to launch.

## Known compromise

Below 1280px the three-panel Survey is cramped: the plot column and the evidence panel stack, and
the waterfall gets roughly 150px. Bounding the page to the viewport is what starves it. This was
true of the original fixed layout too, and the split is off in that range by design. It is not a
regression to fix casually — a narrow-window layout is real work, and the presentation target is a
wide display.

## Where the code is

| File | Role |
|---|---|
| `lib/views.ts` | The nav list, digit mapping, persistence. `views.test.ts` covers it. |
| `components/SplitPane.tsx` | The two-pane grid and the gutter |
| `hooks/useSplit.ts` | Drag, arrow keys, clamping, persistence |
| `hooks/useMediaQuery.ts` | Where the split applies and where the grid stacks |
| `components/SignalOverlay.tsx` | The full-screen deep dive |
| `components/SummaryStrip.tsx` | The plain-language summary strip and its toggle (`hooks/useSummary.ts`: the fetch; `lib/summary.ts`: when it shows, 409 retries, line kinds, the remembered state) |
| `components/HistorySection.tsx` | The History table, its inline delete confirmation and its fetching (`lib/history.ts`: row formatting and download URLs) |
| `App.tsx` | Section branching, the plot column, the evidence rail |
| `TopBar.tsx` | The section nav, the open box, the theme toggle |
