# The Sanket workspace UI

How the frontend is laid out and, above all, the layout invariants that three separate bugs violated. Read the invariants before changing any height, grid or canvas measurement.

## The shell

One column, fixed to the viewport:

```
TopBar      48px   logo · section nav · file name and Synthetic/Real label · Open menu · Download menu · offline badge · Help · team badge · theme
Workspace          the start screen or the selected section, fills the remaining height
StatusBar   24px   version, provenance, tile shape
```

The shell is `h-full min-h-0`, and `html, body, #root` are `height: 100%` in `styles/index.css`, so no section can need to be taller than the window. **The page itself never scrolls:** long content scrolls inside its own panel (the evidence values, the ledger, the summary text and the assumptions view each have their own `overflow-y-auto`).

## Sections

The section decides which regions are on screen. State lives in `App`, above the recording-keyed `Workspace`, so opening another recording keeps your section but resets zoom and selection (different lifetimes).

| Nav item | Layout | Shows |
|---|---|---|
| **Dashboard** (Alt+1, default) | Detections + pipeline rail, the waterfall with its power spectrum, and the resizable symbols column (constellation over eye) | The three plots at once |
| **Evidence** (Alt+2) | Detection chips in a strip, then tabs **Values**, **Frames**, **Bit stream** over one panel that scrolls inside itself | Every value of the selected signal with its level; the frames and the CRC proof |
| **Hypotheses** (Alt+3) | Detection chips, then the search ledger in a panel that scrolls inside itself | Every candidate the blind search tried |
| **Summary** (Alt+4) | A header strip, then the plain-language text filling the rest | What was proved, estimated, unknown |
| **Assumptions** (Alt+5) | A modal, not a section | Everything the analysis took as given, over whatever is on screen |
| **History** (Alt+6) | A header strip, then one table that fills the rest and scrolls inside its own panel | The analyses the server kept (they survive a restart) |

- The choice is persisted in `localStorage` (`sanket.view.v1`): an analyst reopening on Dashboard shouldn't have to click back. A bare `1`–`6` is deliberately *not* used: it would fight numeric fields.
- **Assumptions** keeps its nav place but never switches the workspace: `TopBar` dispatches it to the modal, which can be summoned over any section and dismissed; `App` renders no view for it, and `assumptions` is never the current or stored section (`lib/views.ts` `SectionId`). The modal closes on Esc or a click outside and returns focus to what opened it.
- The nav list lives only in `lib/views.ts`, so the button and the behaviour cannot drift; its definitions, digit mapping and wrap-around stepping are covered by `lib/views.test.ts`. Until a recording is open only Dashboard (then the start screen) and History are in the nav. A stored `survey` or `waterfall` (the retired sections) falls back to Dashboard. Selection (which signal), zoom and the Evidence tab are shared by Dashboard, Evidence and Hypotheses; clicking a stage in the pipeline rail opens its values in Evidence, scrolled to that stage.

## What each view shows

Before a recording is open the workspace shows the **start screen** (`components/StartScreen.tsx`): one primary action (Choose files; dropping files on the window and the path box work too), the bundled samples as cards (`GET /api/v1/samples`, each labelled *Synthetic*, with what to look for), the five evidence levels and the Team Abhedya logo (`components/TeamBadge.tsx`, the light or dark file by theme). Every view then shows real engine output:

- **Waterfall:** follows the theme: a dark ground and the colormap as defined in the dark theme, and in the light theme a pale ground with each colormap reversed (quiet cells pale, strong signals dark; `lib/colormaps.ts` `themedStops`), the overlays using that theme's tokens. One box per detection in time and frequency; frequency relative to the capture centre when the centre frequency is unknown; levels relative, not calibrated.
- **Detections list:** each detection's overall level as glyph + word, never colour alone.
- **Pipeline rail:** one level per stage. Sync, Classify, FEC and Frame read VERIFIED only because a CRC passed on this recording. An analog (FM) detection stops after Classify and says why.
- **Constellation and eye (Dashboard, right column):** two cards, each with a definite height and an absolutely positioned canvas. The constellation is the real symbols after timing, carrier and phase recovery; the eye overlays I and Q over one symbol either side of the symbol instant, ideal levels dashed. A plot that cannot be drawn (FSK is decided by tone energy; analog; a steady carrier; no symbols recovered) shows **Not applicable** with a glyph and the reason; a signal still being analysed shows *Analysing…* instead.
- **Evidence cards (Evidence, Values tab):** each value with its level, method, evidence, alternatives and warnings; UNKNOWN cards say why and what would settle it (e.g. how many FEC hypotheses were tried).
- **Decoded message card (Values tab):** when a known-system match carries text (POCSAG pages, NAVTEX messages, DSC calls, AIS identities, the CCSDS header), `DecodedMessages.tsx` shows it above the stage cards with the Parameter's own level (HYPOTHESIS: the text rests on a convention and is never evidence), a Copy button and the engine's convention under a disclosure.
- **Hypotheses section (ledger):** *Tried* counts every cell of the search grid (modulation × rotation × code × alignment, interleaver × alignment, RS grid × sync word × CRC), including cells never run; the threshold is corrected for that count; the best chains that pass are re-run on shuffled bits, and one that also passes there is blocked, shown as rejected with that reason and counted in the "Shuffled-bit accepts" tile.
- **Frames tab (Evidence):** start bit, sync word, CRC result, header and payload hex, an ASCII column; for a real recording, download links for the table as JSON, CSV, hex and bits.
- **Bit stream tab (Evidence)** (`BitstreamView.tsx`, `lib/bitstream.ts`, from the frame table only):
  - a timeline of the frames (CRC outcome as glyph and pattern, not colour alone);
  - the sync word's recurrence: frames, dominant spacing in bits, how many gaps match it, the gaps plotted against that period;
  - one frame's anatomy (sync / header / payload / CRC, hex coloured by field, a text row, hex or bits);
  - a **field map**, "Header and payload by correlation" (`FieldMap.tsx`, `lib/fieldmap.ts`): the first 512 bits of the CRC-passing frames compared bit by bit, as agreement bars per bit, a band of constant (solid), counting (hatched) and varying (dotted) fields, a table with each field's value or step and its chance under random bits, and where the fixed part ends (the likely start of the payload); nothing claimed from fewer than 8 frames, and it says so;
  - a pattern search: hex bytes or bits (`0b…`) in every listed frame at any bit offset, hits marked in the byte grid and listed as frame chips.
  The map and the search are analyst tools: a field or a hit is never evidence. Too few frames to say anything says so.
- **Summary section:** `GET /api/v1/recordings/{id}/results?format=txt` shown in full (below). While the analysis runs it says the summary is written once the analysis finishes, and how far it has got.
- **Download menu (top bar, `ResultsExports.tsx`):** one **Download** dropdown at every width (Escape or a click elsewhere closes it, as does choosing a link; `hooks/useDismiss.ts`). One row per format with what it is for: `JSON`, `CSV` (one row per value with its level and proof), `Summary`, `PDF`, `Run record` and, by what the recording supports, `SigMF` annotations or a Save as SigMF row for a raw file. A save's outcome is a message fixed under the bar's right edge, so it stays inside the window at any width. Absent while the analysis runs.
- **Open menu (top bar, `OpenMenu.tsx`):** one **Open** dropdown: Choose files…, the path box (a file or a folder) with its Open button, and *Join numbered files* (`rec_000`, `rec_001`, … as one recording). Dropping files anywhere on the window still works without it. Below 1280px the panel is fixed under the bar's left edge, so it never leaves the window. At phone width the Open and Download labels give way to their icons.
- **Assumptions (modal):** container, datatype, sample rate, centre frequency, IQ order and everything else taken as given, each with its level; above them, entry fields for the centre frequency and the IQ order (a swap has the server tile the recording again). Opening a folder lists its recordings in a dialog; a raw file whose sample format is UNKNOWN opens a prompt strip with the sniffer's candidates.

## The History section

`components/HistorySection.tsx` lists `GET /api/v1/history` (newest first): name, container, finished (local time; UTC in the cell's title), signals, the VERIFIED count (`EvidenceBadge` glyph and word, or "none verified"), and the first 12 hex digits of the results SHA-256 (full value in a title, with a copy button). Each row has plain `<a download>` links (JSON, CSV, Summary, PDF, Run record; no SigMF, which needs the recording's files) and Delete, which opens a confirmation row under the entry ("Delete this analysis and everything derived from it?", Delete and Cancel; Cancel has focus, Esc cancels); a failing delete shows the server's text there, never an `alert()`.

- Fetched when the section opens, from Refresh, and when an analysis finishes (App bumps `historyTick` when the recording turns `done`, at once and again about two seconds later, because the server keeps the analysis on its worker thread just after). An empty list says what makes an entry; with nothing open the section still lists what the server holds.
- It renders inside `Workspace`, so zoom and selection survive a visit. Layout: a `main` that is `flex min-h-0 flex-1 flex-col overflow-hidden`, a fixed 32px strip, the table in a `min-h-0 flex-1 overflow-auto` panel with a sticky header. Measured (e2e, 40 rows, both themes): `scrollHeight` equals `innerHeight` at 1918x950 and 1440x800, 1429px of content scrolls in an 846px / 696px panel, nothing overflows sideways.

## The Summary section

`components/SummarySection.tsx` shows the server's plain-language summary (`dsp/summary.py`, a fixed template over the results) verbatim: what was proved, what was only estimated, what is unknown and what would settle it, what rests on a convention. Monospace tabular face (`num`), the title, unindented headings and the Proved / Not proved / Still unknown subheadings in heavier weights; levels are in the text's own words, so nothing is colour-only.

- It was a collapsible strip above the old Survey and started collapsed in windows under 880px tall, so it was easy to miss; it is now a section of its own (nothing to expand, nothing remembered).
- Mounted by `Workspace` for a recording whose analysis is `done` (`lib/summary.ts` `summaryTarget`); a running analysis shows `SummaryWaiting`. A recording the file itself calls synthetic still has one (the top bar labels it *Synthetic recording*). A new finish remounts it and fetches afresh.
- `hooks/useSummary.ts` fetches once per mount; a 409 (the server's state lags the stream's `done`) is retried after 250, 500, 1000 and 2000 ms, then shown; any other failure is shown at once, in the server's words, with a Retry button.
- Layout: a `main` that is `flex min-h-0 flex-1 flex-col overflow-hidden`, a 32px header strip, and the text in a `min-h-0 flex-1 overflow-y-auto` panel (focusable, `max-w-5xl` centred).
- Measured (e2e, both themes, a 300-line summary): `scrollHeight` equals `innerHeight` with no sideways overflow at 1918x950 and 1440x800, and the text scrolls inside a panel that is most of the window.

## Onboarding and plain language

- **Welcome** (`Welcome.tsx`): a modal on first run and from Help: three plain sentences, the five levels as glyph + word + meaning, *Try a sample* (focuses the first sample card, or opens `scene` when a recording is open), *Take the tour*, *Skip* (Esc). Remembered under `sanket.onboarding.v1` (try/catch); the e2e `beforeEach` sets it so other tests start past it. The desktop window keeps `localStorage`, so it shows only on the first launch.
- **Tour** (`lib/tour.ts`, driver.js bundled, no network): reached from Help, then *Take the tour* (there is no separate top-bar button). Steps are anchored on `data-tour` attributes (`open`, `section-nav`, `detections`, `waterfall`, `constellation`, `eye`, `evidence`, `hypotheses`, `summary`, `export`, `assumptions`). A step names the section its anchor lives in; the tour switches to that section before showing the step (two animation frames for the layout to settle), skips a step whose anchor still is not there, and returns to the section the analyst started on when it ends. With nothing open, *Take the tour* opens `scene` and starts when its first result lands. No animation under reduced motion; the popover is styled from the tokens (`.sanket-tour` in `styles/index.css`).
- **Plain headline** (`lib/plainHeadline.ts`): one sentence per signal from the structured report, never firmer than its level; the engine's own headline stays under it in small mono type.
- **Glossary and InfoTips** (`lib/glossary.ts`, `InfoTip.tsx`): a focusable ? beside jargon (Es/N0, EVM, CRC, sync word, ledger, p, threshold, family-wise error, shuffled-bit check, constellation, eye); the popover is portalled to `body`, clamped inside the viewport, closes on Esc or blur.
- **Progress:** a 2px bar under the top bar (done of total signals), a spinner and *Analysing…* on each signal card until its report lands; the first finished signal is selected unless the analyst picked one.

## The resizable split

`components/SplitPane.tsx` and `hooks/useSplit.ts` give the Dashboard's plot column and its symbols column (constellation over eye) a draggable, persisted split (`sanket.split.v2`, default 0.72):

- Pointer events, not `mousedown`/`mousemove`, so a drag survives leaving the window.
- The gutter is a focusable `role="separator"` with arrow keys (shift for bigger steps), reachable without a pointer.
- The fraction is of the space **after** the fixed rail; a percentage of the container would hand the rail's width to the plot and leave the symbols short.
- Neither pane goes below 340px. There is no hide button: all three plots are always on screen.
- Only at 1280px and above. Below that the three panels stack (the two symbol cards side by side underneath, one column below 768px), a gutter would have nothing to divide, and `App` renders a plain grid.

## Layout invariants

Not stylistic: each is a bug that already shipped once.

1. **Every grid that contains a plot has an explicit `grid-rows`.** Without `grid-template-rows` the implicit row is content-sized, so the plot sizes to its own content and overflows its box. `SplitPane` uses `grid-rows-[minmax(0,1fr)]`; the symbols column `grid-rows-[minmax(0,1fr)_minmax(0,1fr)]`.
2. **The canvas must never be able to size its own container.** The waterfall canvas is `absolute inset-0 size-full`. If its container ever has an `auto` height, `height: 100%` resolves against the canvas's `height` *attribute*; the parent grows to match, the `ResizeObserver` measures that and writes it back to the attribute: a ratchet, so the plot sticks at whatever it was first measured at and never shrinks. It held the waterfall at 2681px inside a 956px box. `Waterfall.tsx` therefore rejects a zero-height report and anything taller than four viewports. The constellation and eye follow the same rule: each canvas sits in an `absolute inset-0` box whose size comes from its card (`hooks/useWidth.ts` `useSize`), never the other way round.
3. **`min-h-0` on every flex or grid child that should shrink.** A flex item's default `min-height: auto` refuses to shrink below its content: this is why the evidence rail grew to fit all nine stages in an auto-height row and dragged the page to 3165px. A wrapper that is only a grid item also needs a definite height (`h-full` on the child) for its own `overflow-y-auto` to engage.
4. **The plot column carries `flex-1`.** Without it, wherever the column is a flex child rather than a grid item, the waterfall's own `flex-1` has no definite space and collapses to zero, leaving the spectrum and an empty void.
5. **Evidence is never colour-only** (PLAN §4): the split, the section nav and the detection chips carry words and glyphs too.

## Checking a layout change

Measure the DOM; never judge by eye. The screenshot tool is unreliable here, and two rounds of this work went wrong because a screenshot was read by eye. A throwaway Playwright script is fastest (it is how the numbers above were obtained):

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

`doc` must equal `view` in every section and `canvas` must equal `wf` (and the constellation and eye canvases must sit inside their cards), at 1918 and 1440 in both themes. If Playwright's bundled Chromium is a broken install, point `executablePath` at an older `%LOCALAPPDATA%\ms-playwright\chromium-<build>\chrome-win64\chrome.exe`. The e2e suite serves the last production build: run `npm run build` first.

## Known compromise

Below 1280px the three-panel Dashboard is cramped: the plot column and the symbols stack and the waterfall gets roughly 150px, and with several detections the pipeline rail can make the page taller than the window, because bounding the page to the viewport starves it (true of the original fixed layout too; the split is off in that range by design). The team badge is hidden in that range so the 48px bar never overflows. Below about 900px the workspace can also be taller than the window; the top bar itself is measured down to 390px (one 48px row, no overflow, no overlap, both themes). Not a regression to fix casually: a narrow-window layout is real work, and the presentation target is a wide display.

## Where the code is

| File | Role |
|---|---|
| `lib/views.ts` | The nav list, digit mapping, persistence (`views.test.ts`) |
| `components/SplitPane.tsx`, `hooks/useSplit.ts` | The two-pane grid and gutter; drag, arrow keys, clamping, persistence |
| `hooks/useMediaQuery.ts`, `hooks/useWidth.ts` | Where the split applies and where the grid stacks; width and size measurement for charts |
| `components/SymbolView.tsx` | The constellation and eye cards, their Not-applicable reasons |
| `components/DetailTabs.tsx` | The ledger, the frame table and the tab strip the Evidence section uses |
| `components/SummarySection.tsx` | The Summary section (`hooks/useSummary.ts` the fetch; `lib/summary.ts` when it shows, 409 retries, line kinds) |
| `components/HistorySection.tsx` | The History table, inline delete and fetching (`lib/history.ts` row formatting and download URLs) |
| `components/BitstreamView.tsx`, `FieldMap.tsx`, `DecodedMessages.tsx` | The Bit stream tab, its field map, the decoded-message card (`lib/bitstream.ts`, `lib/fieldmap.ts`, `lib/decodedMessages.ts`; `hooks/useWidth.ts` measures the charts) |
| `components/StartScreen.tsx`, `Welcome.tsx`, `InfoTip.tsx` | Start screen with sample cards, welcome dialog, glossary popover (`lib/tour.ts`, `lib/onboarding.ts`, `lib/glossary.ts`, `lib/plainHeadline.ts`) |
| `components/ResultsExports.tsx`, `OpenMenu.tsx`, `TeamBadge.tsx` | The top bar's Download menu (`lib/exports.ts`), Open menu and team logo; `hooks/useDismiss.ts` closes the menus |
| `App.tsx` | Section branching, the plot column, the symbols column, the Evidence tabs |
| `TopBar.tsx` | The section nav, the menus, Help, the team badge, the theme toggle |
