# The Sanket workspace UI

How the frontend is laid out and, above all, the layout invariants that three separate bugs violated. Read the invariants before changing any height, grid or canvas measurement.

## The shell

One column, fixed to the viewport:

```
TopBar      48px   logo · section nav · file name and Synthetic/Real label · open box · Results · offline badge · Help · theme
Workspace          the start screen or the selected section, fills the remaining height
StatusBar   24px   version, provenance, tile shape
```

The shell is `h-full min-h-0`, and `html, body, #root` are `height: 100%` in `styles/index.css`, so no section can need to be taller than the window. **The page itself never scrolls:** long content scrolls inside its own panel (the evidence rail, the search ledger and the assumptions view each have their own `overflow-y-auto`).

## Sections

The section decides which regions are on screen. State lives in `App`, above the recording-keyed `Workspace`, so opening another recording keeps your section but resets zoom and selection (different lifetimes).

| Nav item | Layout | Shows |
|---|---|---|
| **Survey** (Alt+1, default) | The summary strip (a finished real recording only), then detections + pipeline rail, the plot column and the resizable evidence panel | Everything at once |
| **Waterfall** (Alt+2) | Detection chips in a strip, then the plot column full width | The spectrogram and its power spectrum, nothing competing |
| **History** (Alt+3) | A header strip, then one table that fills the rest and scrolls inside its own panel | The analyses the server kept (they survive a restart) |
| **Assumptions** (Alt+4) | A modal, not a section | Everything the analysis took as given, over whatever is on screen |

- The choice is persisted in `localStorage` (`sanket.view.v1`): an analyst reopening on Survey shouldn't have to click back. A bare `1`–`3` is deliberately *not* used: it would fight numeric fields.
- **Assumptions** keeps its nav place but never switches the workspace: `TopBar` dispatches it to the modal, which can be summoned over any section and dismissed; `App` renders no view for it, and `assumptions` is never the current or stored section (`lib/views.ts` `SectionId`). The modal closes on Esc or a click outside and returns focus to what opened it. The per-detection deep dive is likewise an overlay.
- The nav list lives only in `lib/views.ts`, so the button and the behaviour cannot drift; its definitions, digit mapping and wrap-around stepping are covered by `lib/views.test.ts`. Until a recording is open only Survey (then the start screen) and History are in the nav.

## What each view shows

Before a recording is open the workspace shows the **start screen** (`components/StartScreen.tsx`): one primary action (Choose files; dropping files on the window and the path box work too), the bundled samples as cards (`GET /api/v1/samples`, each labelled *Synthetic*, with what to look for) and the five evidence levels. Every view then shows real engine output:

- **Waterfall:** one box per detection in time and frequency; frequency relative to the capture centre when the centre frequency is unknown; levels relative, not calibrated.
- **Detections list:** each detection's overall level as glyph + word, never colour alone.
- **Pipeline rail:** one level per stage. Sync, Classify, FEC and Frame read VERIFIED only because a CRC passed on this recording. An analog (FM) detection stops after Classify and says why.
- **Constellation:** the real symbols after timing, carrier and phase recovery; empty for FSK (decided by tone energy) and analog signals. For a linear signal a toggle beside the title switches to the **eye diagram**: I and Q overlaid over one symbol either side of the symbol instant, ideal levels dashed.
- **Evidence cards:** each value with its level, method, evidence, alternatives and warnings; UNKNOWN cards say why and what would settle it (e.g. how many FEC hypotheses were tried).
- **Decoded message card (evidence panel):** when a known-system match carries text (POCSAG pages, NAVTEX messages, DSC calls, AIS identities, the CCSDS header), `DecodedMessages.tsx` shows it above the stage cards with the Parameter's own level (HYPOTHESIS: the text rests on a convention and is never evidence), a Copy button and the engine's convention under a disclosure.
- **Hypotheses tab (ledger):** *Tried* counts every cell of the search grid (modulation × rotation × code × alignment, interleaver × alignment, RS grid × sync word × CRC), including cells never run; the threshold is corrected for that count; the best chains that pass are re-run on shuffled bits, and one that also passes there is blocked, shown as rejected with that reason and counted in the "Shuffled-bit accepts" tile.
- **Frames tab:** start bit, sync word, CRC result, header and payload hex, an ASCII column; for a real recording, download links for the table as JSON, CSV, hex and bits.
- **Bit stream tab** (`BitstreamView.tsx`, `lib/bitstream.ts`, from the frame table only):
  - a timeline of the frames (CRC outcome as glyph and pattern, not colour alone);
  - the sync word's recurrence: frames, dominant spacing in bits, how many gaps match it, the gaps plotted against that period;
  - one frame's anatomy (sync / header / payload / CRC, hex coloured by field, a text row, hex or bits);
  - a **field map**, "Header and payload by correlation" (`FieldMap.tsx`, `lib/fieldmap.ts`): the first 512 bits of the CRC-passing frames compared bit by bit, as agreement bars per bit, a band of constant (solid), counting (hatched) and varying (dotted) fields, a table with each field's value or step and its chance under random bits, and where the fixed part ends (the likely start of the payload); nothing claimed from fewer than 8 frames, and it says so;
  - a pattern search: hex bytes or bits (`0b…`) in every listed frame at any bit offset, hits marked in the byte grid and listed as frame chips.
  The map and the search are analyst tools: a field or a hit is never evidence. Too few frames to say anything says so.
- **Summary strip (Survey only):** the plain-language summary above the pipeline rail (below). Absent while the analysis runs.
- **Results download (top bar, `ResultsExports.tsx`):** for a finished analysis, the results as `JSON`, a `CSV` (one row per value with its level and proof), a plain-language `Summary`, a `PDF`, the `Run record` and, by what the recording supports, `SigMF` annotations or a Save as SigMF button for a raw file. From 1536 px they sit in the bar; narrower (to 390 px) they fold into one **Results** menu (Escape, a click elsewhere or a choice closes it). A save's outcome is a message fixed under the bar's right edge, so it stays inside the window at any width. Absent while the analysis runs.
- **Assumptions (modal):** container, datatype, sample rate, centre frequency, IQ order and everything else taken as given, each with its level; above them, entry fields for the centre frequency and the IQ order (a swap has the server tile the recording again). Opening a folder lists its recordings in a dialog; a raw file whose sample format is UNKNOWN opens a prompt strip with the sniffer's candidates; "Join numbered files" beside the path reads `rec_000`, `rec_001`, … as one recording.

## The History section

`components/HistorySection.tsx` lists `GET /api/v1/history` (newest first): name, container, finished (local time; UTC in the cell's title), signals, the VERIFIED count (`EvidenceBadge` glyph and word, or "none verified"), and the first 12 hex digits of the results SHA-256 (full value in a title, with a copy button). Each row has plain `<a download>` links (JSON, CSV, Summary, PDF, Run record; no SigMF, which needs the recording's files) and Delete, which opens a confirmation row under the entry ("Delete this analysis and everything derived from it?", Delete and Cancel; Cancel has focus, Esc cancels); a failing delete shows the server's text there, never an `alert()`.

- Fetched when the section opens, from Refresh, and when an analysis finishes (App bumps `historyTick` when the recording turns `done`, at once and again about two seconds later, because the server keeps the analysis on its worker thread just after). An empty list says what makes an entry; with nothing open the section still lists what the server holds.
- It renders inside `Workspace`, so zoom and selection survive a visit. Layout: a `main` that is `flex min-h-0 flex-1 flex-col overflow-hidden`, a fixed 32px strip, the table in a `min-h-0 flex-1 overflow-auto` panel with a sticky header. Measured (e2e, 40 rows, both themes): `scrollHeight` equals `innerHeight` at 1918x950 and 1440x800, 1429px of content scrolls in an 846px / 696px panel, nothing overflows sideways.

## The Summary strip

`components/SummaryStrip.tsx` shows the server's plain-language summary (`dsp/summary.py`, a fixed template over the results) verbatim: what was proved, what was only estimated, what is unknown and what would settle it, what rests on a convention. Monospace tabular face (`num`), the title, unindented headings and the Proved / Not proved / Still unknown subheadings in heavier weights; levels are in the text's own words, so nothing is colour-only.

- Mounted by `Workspace` only in Survey, for a real recording whose analysis is `done` (`lib/summary.ts` `summaryTarget`); a running analysis and the other sections have none. A recording the file itself calls synthetic still has one (the top bar labels it *Synthetic recording*). A new finish remounts it and fetches afresh.
- `hooks/useSummary.ts` fetches once per mount; a 409 (the server's state lags the stream's `done`) is retried after 250, 500, 1000 and 2000 ms, then shown; any other failure is shown at once, in the server's words, with a Retry button.
- The header is one 28px button (`aria-expanded`, `aria-controls`; Tab, Enter, Space). Open or collapsed is remembered (`sanket.summary.v1`, try/catch); with nothing remembered it opens in a window at least 880px tall and starts collapsed below that, because open it takes the waterfall's height (at 1440x800 the waterfall would keep about 94px).
- Layout: a `shrink-0` `section` above the Survey `main`, a direct child of the shell column outside `SplitPane` (the split's measurement is unaffected). The text panel is `max-h-[min(22vh,160px)] overflow-y-auto` and focusable, so the strip is at most 29px collapsed or 189px open; `main` is `min-h-0 flex-1`.
- Measured (e2e and a probe, both themes, a 300-line summary): `scrollHeight` equals `innerHeight` with no sideways overflow at 1918x950 and 1440x800, collapsed and open; 569px of text scrolls in 160px; the waterfall canvas equals its container (1918: 412px collapsed, 252px open; 1440: 254px, 94px).

## Onboarding and plain language

- **Welcome** (`Welcome.tsx`): a modal on first run and from Help: three plain sentences, the five levels as glyph + word + meaning, *Try a sample* (focuses the first sample card, or opens `scene` when a recording is open), *Take the tour*, *Skip* (Esc). Remembered under `sanket.onboarding.v1` (try/catch); the e2e `beforeEach` sets it so other tests start past it. The desktop window keeps `localStorage`, so it shows only on the first launch.
- **Tour** (`lib/tour.ts`, driver.js bundled, no network): steps anchored on `data-tour` attributes (`open`, `section-nav`, `waterfall`, `detections`, `evidence`, `symbols`, `bottom-tabs`, `summary`, `export`, `assumptions`); a step whose anchor is not on screen is skipped. With nothing open, *Take the tour* opens `scene` and starts when its first result lands. No animation under reduced motion; the popover is styled from the tokens (`.sanket-tour` in `styles/index.css`).
- **Plain headline** (`lib/plainHeadline.ts`): one sentence per signal from the structured report, never firmer than its level; the engine's own headline stays under it in small mono type.
- **Glossary and InfoTips** (`lib/glossary.ts`, `InfoTip.tsx`): a focusable ? beside jargon (Es/N0, EVM, CRC, sync word, ledger, p, threshold, family-wise error, shuffled-bit check, constellation, eye); the popover is portalled to `body`, clamped inside the viewport, closes on Esc or blur.
- **Progress:** a 2px bar under the top bar (done of total signals), a spinner and *Analysing…* on each signal card until its report lands; the first finished signal is selected unless the analyst picked one.

## The Signal overlay

The per-detection deep dive is a full-screen overlay, **not** a section: you read one signal end to end and come back; as a section it cost the waterfall a third of the display whenever anyone wanted a constellation. Open it from **Full screen** in the evidence panel's header; Esc closes it and focus lands on the close button. It shows the constellation and every pipeline stage on the left, the ledger on the right, each scrolling on its own, and the frame exports.

## The resizable split

`components/SplitPane.tsx` and `hooks/useSplit.ts` give the plot column and the evidence panel a draggable, persisted split (`sanket.split.v1`, default 0.68):

- Pointer events, not `mousedown`/`mousemove`, so a drag survives leaving the window.
- The gutter is a focusable `role="separator"` with arrow keys (shift for bigger steps), reachable without a pointer.
- The fraction is of the space **after** the fixed rail; a percentage of the container would hand the rail's width to the plot and leave the panel short.
- Neither pane goes below 340px; the panel also collapses to a tab on the right edge.
- Only at 1280px and above. Below that the three panels stack, a gutter would have nothing to divide, and `App` renders a plain grid.

## Layout invariants

Not stylistic: each is a bug that already shipped once.

1. **Every grid that contains a plot has an explicit `grid-rows`.** Without `grid-template-rows` the implicit row is content-sized, so the plot sizes to its own content and overflows its box. `SplitPane` uses `grid-rows-[minmax(0,1fr)]`.
2. **The canvas must never be able to size its own container.** The waterfall canvas is `absolute inset-0 size-full`. If its container ever has an `auto` height, `height: 100%` resolves against the canvas's `height` *attribute*; the parent grows to match, the `ResizeObserver` measures that and writes it back to the attribute: a ratchet that held the waterfall at 2681px inside a 956px box. `Waterfall.tsx` therefore rejects a zero-height report and anything taller than four viewports.
3. **`min-h-0` on every flex or grid child that should shrink.** A flex item's default `min-height: auto` refuses to shrink below its content: this is why the evidence rail grew to fit all nine stages in an auto-height row and dragged the page to 3165px. A wrapper that is only a grid item also needs a definite height (`h-full` on the child) for its own `overflow-y-auto` to engage.
4. **The plot column carries `flex-1`.** Without it, in the Waterfall section (a flex child, not a grid item) the waterfall's own `flex-1` had no definite space and collapsed to zero, leaving the spectrum and an empty void.
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

`doc` must equal `view` in every section and `canvas` must equal `wf`, at 1918 and 1440 in both themes. If Playwright's bundled Chromium is a broken install, point `executablePath` at an older `%LOCALAPPDATA%\ms-playwright\chromium-<build>\chrome-win64\chrome.exe`. The e2e suite serves the last production build: run `npm run build` first.

## Known compromise

Below 1280px the three-panel Survey is cramped: the plot column and evidence panel stack and the waterfall gets roughly 150px, because bounding the page to the viewport starves it (true of the original fixed layout too; the split is off in that range by design). Below about 900px the workspace can also be taller than the window; the top bar itself is measured down to 390px (one 48px row, no overflow, no overlap, both themes). Not a regression to fix casually: a narrow-window layout is real work, and the presentation target is a wide display.

## Where the code is

| File | Role |
|---|---|
| `lib/views.ts` | The nav list, digit mapping, persistence (`views.test.ts`) |
| `components/SplitPane.tsx`, `hooks/useSplit.ts` | The two-pane grid and gutter; drag, arrow keys, clamping, persistence |
| `hooks/useMediaQuery.ts` | Where the split applies and where the grid stacks |
| `components/SignalOverlay.tsx` | The full-screen deep dive |
| `components/SummaryStrip.tsx` | The summary strip and its toggle (`hooks/useSummary.ts` the fetch; `lib/summary.ts` when it shows, 409 retries, line kinds, the remembered state) |
| `components/HistorySection.tsx` | The History table, inline delete and fetching (`lib/history.ts` row formatting and download URLs) |
| `components/BitstreamView.tsx`, `FieldMap.tsx`, `DecodedMessages.tsx` | The Bit stream tab, its field map, the decoded-message card (`lib/bitstream.ts`, `lib/fieldmap.ts`, `lib/decodedMessages.ts`; `hooks/useWidth.ts` measures the charts) |
| `components/StartScreen.tsx`, `Welcome.tsx`, `InfoTip.tsx` | Start screen with sample cards, welcome dialog, glossary popover (`lib/tour.ts`, `lib/onboarding.ts`, `lib/glossary.ts`, `lib/plainHeadline.ts`) |
| `components/ResultsExports.tsx` | The top bar's downloads and Results menu (`lib/exports.ts`) |
| `App.tsx` | Section branching, the plot column, the evidence rail |
| `TopBar.tsx` | The section nav, the open box, Help, the theme toggle |
