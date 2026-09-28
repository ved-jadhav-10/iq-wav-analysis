# Sanket demo

Everything here runs offline on one machine. All three recordings are **synthetic**: `dsp.synth`
generates them with exact ground truth, and the UI labels them "Synthetic recording". The UI shows
"Synthetic demo" before any file is opened.

## Setup (about 2 minutes)

```
uv run python tools/make_demo.py      # writes data/demo/*.sigmf-meta and checks every signal against the truth
cd frontend && npm run build && cd ..
uv run sanket                         # prints the local URL
```

`make_demo.py` must end with `all checks passed`. It opens each file the way the server does
(detect, then analyse), and compares every decoded frame's payload with the transmitted bytes.

To open a file, paste its full path into the path box in the top bar and press **Open**.
Opening `scene` takes about 45 s. The server builds the tiles and analyses every signal before it
answers, so wait for "Opening…" to clear.

The workspace never scrolls as a page: every section fills the window and long content scrolls
inside its own panel. If a view ever does scroll as a whole, that is a layout bug — see the
invariants in [UI.md](UI.md).

## 1. `data/demo/scene.sigmf-meta`: the main demo

Four signals at 1 MS/s, about 1 s long.

| # | What's in the file | What Sanket shows |
|---|---|---|
| 1 | QPSK, 50 kBd, conv K=7 r½, CCSDS ASM frames, CRC-16 | **VERIFIED**. 44/44 complete frames pass their CRC |
| 2 | FM, analog | **FM**, labelled analog and kept out of the digital chain |
| 3 | BPSK, 31.25 kBd, same coding, a shorter burst | **VERIFIED**. 24/24 complete frames pass their CRC |
| 4 | QPSK with no code and no frames | **QPSK?**, ESTIMATED and not decoded. The FEC code is **UNKNOWN**, with the reason |

What to click, and what each view proves:

- **Section nav** (top bar, left of the file name). **Survey** is the default and shows everything
  at once; **Waterfall** gives the spectrogram the whole display. `Alt+1`–`Alt+2` also switch.
  **Assumptions** is the third item, but it opens a modal over the current view rather than
  replacing the workspace, so it can be summoned and dismissed from anywhere. The per-detection
  deep dive works the same way: press **Full screen** in the evidence panel to open it over the
  workspace, and `Esc` to come back. See [UI.md](UI.md) for the layout.
- **Waterfall.** Each box is a detection, positioned in time and frequency. The badges in the
  Detections list never rely on colour alone: each carries a glyph and a word.
- **#1 QPSK → pipeline rail.** Every stage has its own evidence level. Sync, Classify, FEC and
  Frame are VERIFIED only because the CRC passed on this recording. The Classify card shows the
  cumulant ranking and the alternatives it weighed.
- **Constellation.** Real symbols after timing, carrier and phase recovery.
- **Hypotheses tab.** The ledger. *Tried* counts every candidate in the search grid, including
  cells the search never had to run. That covers modulation × rotation × code × alignment,
  interleaver × alignment, and RS grid × sync word × CRC. The threshold is Bonferroni-corrected
  for that count. The accepted chain is re-run on shuffled bits, and it must never pass.
- **Frames tab.** Real frames: start bit, sync word, CRC result, header and payload hex. The
  payloads match `data/demo/scene.truth.json`.
- **#2 FM.** The rail stops after Classify, and the ledger explains why no search ran.
- **#4 QPSK?.** An honest UNKNOWN. Open the FEC card's evidence: it says how many hypotheses were
  tried, and that none reached a significant CRC result.
- **Drag the gutter** between the plot and the evidence panel, or collapse the panel to a tab. The
  position is remembered for the next recording.
- **Theme toggle** (top right). The same evidence in dark mode.

## 2. `data/demo/scene_widen.sigmf-meta`: deeper chains

| What's in the file | What Sanket shows |
|---|---|
| 8PSK, conv K=7 r½, 16×36 block interleaver | **VERIFIED**. The rail gains a **Deinterleave** stage ("block 16x36 from bit …"), found from the inner code's parity syndrome |
| QPSK, conv K=7 r½ inside RS(255,223) CCSDS | **VERIFIED**. The FEC card shows the outer code: codewords decoded, bytes corrected |

## 3. `data/demo/scene_fsk.sigmf-meta`: 2-FSK

A lone coded 2-FSK signal decodes to **VERIFIED** frames. There is no constellation, since
non-coherent FSK decides each symbol by tone energy. Tone spacing and timing are in the Estimate
and Sync cards.

## Known limits (say them if asked)

- 2-FSK decodes only on its own undecimated channel. On a crowded or decimated channel its
  symbol-rate estimate is unreliable, which is why it's in a separate file.
- A signal wide enough that its channel isn't decimated (bandwidth above about 0.08 of the
  sample rate) is only mixed down, not filtered, so neighbouring signals leak into its analysis.
  The demo scenes keep every signal narrower than that.
- Opening a file is synchronous and slow (about 45 s here). There's no background job yet.
- These are synthetic recordings. No claim here is about real-world captures or bench numbers.
