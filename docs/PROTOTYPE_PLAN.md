# Sanket — prototype plan (demo in ~10 hours)

PLAN.md stays the authority for scope, the production bar and the milestones. This document only
covers the sprint to a working demo: what's cut for now, the phases, and the rules that keep the
honesty guarantees intact while moving fast. **Finishing M2 is dropped for now**; its remaining
items and open gates ([PLAN §0](PLAN.md#0-progress)) come first after the demo, before any M3
production work.

**Current state (start of this sprint):** M0 and M1 done. M2 mostly built: a real recording shows
a real waterfall, detection boxes and Parameter evidence cards. Everything after detection says
"not built".

**Measured check times:** pytest 44 s single-process (12 s of it galois JIT warm-up); pyright 15 s;
frontend checks about 30 s; CI 6.5 min (4 min of it Windows reinstalling Playwright). The time
sink during this sprint is repeated full runs, review agents, bench runs and chasing gate numbers
— so this sprint skips all of those (see Prototype rules).

## Demo target

One synthetic SigMF recording, labelled synthetic, containing:
- a **QPSK and a BPSK** signal, each with conv K=7 r½, CCSDS ASM frames and CRC-16, both decoding
  to **VERIFIED**
- an **FM** signal, labelled analog and kept out of the digital chain
- **one signal that isn't decoded**, shown as UNKNOWN with the reason

The demo shows real frames, a real constellation, the ledger of every candidate tried, and the
full pipeline rail.

## Prototype rules

- **Honesty rules stay:** every output is a `Parameter`, and VERIFIED comes only from a CRC,
  sync-word recurrence or re-encode proof. Never bypass the validator (no `model_construct`).
- **One ground-truth test file per phase.** While iterating, run only that file. Run the full
  check list once, at the end of the phase.
- **No review agents, no bench runs, no gate chasing.** A stage that fails on an edge case gets an
  honest UNKNOWN or `noFramesReason`, not a workaround.
- **If stuck for 30 minutes, pick the simpler method,** and say so in the phase's commit or report.
- **One commit per phase,** with no co-author trailer and a 1–2 line message.

## Phases

### P0 — docs and fast checks (~1 h, alongside P1)

**Goal:** this document, a shorter PLAN.md, and CI/local checks fast enough to iterate against
during the rest of the sprint.
**Scope:** `docs/PROTOTYPE_PLAN.md` (this file); `docs/PLAN.md` cut to ~15k tokens with every
feature kept; `docs/PROGRESS_LOG.md` for the long-form history moved out of PLAN §0; README/QandA
status-line pointers; `pytest-xdist`; CI Playwright caching and concurrency; a format-on-edit hook.
**Done when:** the full check list (CLAUDE.md's list, with `pytest -n auto --dist loadfile`) passes
once, and every `PLAN.md#…` link in the repo still resolves.

### P1 — the thin slice (~3 h)

**Goal:** one real recording decodes end to end in the UI: detect → estimate → sync → demod → FEC
→ frame, with real Parameters, a real ledger and real frames for at least one modulation.
**Scope:** `dsp/sync.py`, `dsp/demod.py`, `dsp/fec/viterbi.py`, `dsp/framing.py`, `dsp/analyse.py`
(main session); the per-detection contract (`dsp/report.py`, `frontend/src/lib/analysis.ts`,
written up front by the main session); backend wiring (`RecordingStore.open`, `DetectionInfo`);
frontend wiring (`App.tsx` feeding real detections to the existing panels, `SymbolView` real
points); `tools/make_demo.py`; `tests/dsp/test_slice.py`.
**Done when:** the demo file opens in the UI and both digital signals show VERIFIED frames whose
payload hex matches the truth.

### P2 — widen (~2 h; stop when the time runs out)

**Goal:** more of the demo target lands — classify, an interleaved signal, outer RS, 2-FSK —
whichever fit in the time left, dropped from the bottom of this list first.
**Scope:** cumulant-ranked classify (BPSK/QPSK/8PSK/16QAM); a block-interleaver catalogue try;
RS(255,223) CCSDS through `galois`; a 2-FSK discriminator path. One exact-bits case per item in
`test_slice.py`.
**Done when:** whatever landed decodes correctly on its synth case; anything dropped is noted in
the P2 commit.

### P3 — demo-ready (~1.5 h)

**Goal:** the demo runs cleanly, both themes, no console errors, and everyone knows what to click.
**Scope:** a run-through of the demo file in the browser, both themes, fixing what breaks; one full
check pass (`ruff check`, `ruff format --check`, `pyright`, `pytest -n auto`; frontend `typecheck`,
`build`, `e2e`); `docs/DEMO.md` (which file to open, what to click, what each screen proves);
PLAN §0 and this file updated with what landed.
**Done when:** the check list is green and `docs/DEMO.md` matches the actual UI.

### What landed (P0–P3)

- **P0:** this plan, the shortened PLAN.md, PROGRESS_LOG.md, pytest-xdist, the CI Playwright
  cache and the format-on-edit hook.
- **P1:** the whole chain for one detection (`dsp/analyse.py` and the modules it calls),
  returned as a `DetectionReport` (`dsp/report.py`, mirrored in `frontend/src/lib/analysis.ts`).
  The backend runs it for every detection on open, and the existing panels draw it.
  `tools/make_demo.py` writes the demo scenes and verifies them against the truth.
- **P2, all four items:**
  - cumulant classify over BPSK/QPSK/8PSK/16QAM
  - the block-interleaver catalogue, aligned by the conv code's parity syndrome
  - outer RS(255,223) CCSDS through galois, with the codeword grid found from an error-free
    codeword
  - 2-FSK
  
  Each has an exact-frames case in `tests/dsp/test_slice.py`. The modules have round-trip tests
  in `tests/dsp/test_p2_modules.py`. P1 and P2 went in as one commit, because they share
  `analyse.py`.
- **P3:** the browser run-through in both themes. It found and fixed:
  - the waterfall's time axis (it assumed one FFT hop per tile row)
  - the "Real recording" badge on synthetic files (now read from SigMF `core:recorder`)
  - a `NaN` in the ledger when nothing was accepted
  - unrounded parameter values

  It also added [DEMO.md](DEMO.md) and the full check pass.

### P4 — after the demo (not started now)

Recorded here so the sprint doesn't lose track of what it deferred:
1. **Finish M2 before any M3 production work:** estimate/analog outputs as `Parameter`s; the SNR
   gate (diagnose `snr_psd`'s bias; add M2M4 and eigenvalue/MDL); the false-detection gate (trace
   `merge`/`absorb_sidelobes`; merge FSK tone combs by spacing; multi-signal scenes); first tile
   ≤ 2 s with the pyramid built in the background; LOD tiles; cyclic/FAM refinement and the
   bandwidth fallback below β ≈ 0.1; analog measurements, SSB and Morse CW with their synth
   generators; real/complex branches; OpenAPI-generated TS types; one run of each review agent,
   and a bench re-run.
2. **Prototype gaps found during the sprint:**
   - `dsp.channel.channelise` only mixes a decimation-1 channel (a wide signal) and doesn't
     filter it, so neighbours leak in. Filtering alone breaks `snr_psd` and the analog test,
     which expect noise across the whole channel. Notch the other detections, or rework those
     estimators.
   - 2-FSK's rate (`fsk_symbol_rates`) is unreliable on a decimated or crowded channel. It
     decodes only on its own undecimated channel, which is why `scene_fsk` is a separate file.
   - Opening a recording is synchronous: the tile pyramid and every detection's analysis run
     before the response (about 45 s for the demo scene). Move this to a background job.
   - The per-row time fix (`RecordingInfo.hop` is now samples per row) and the tone-comb power
     check in `dsp.detect` haven't been re-benched.
   - Real FSK detections carry no symbol-view data yet (only the demo path draws the tone
     histogram).
3. `tools/check.py`, the check command that picks checks from the changed paths.
4. Widen toward the full PLAN milestones: M3 → M5 → M6 → M4 → M7 → M8, then close the Open gates
   ([PLAN §0](PLAN.md#0-progress)). Rough estimate for full 1.0: about 135–210 agent-hours (2–3
   weeks at ~12 h/day), plus anything that needs the analyst directly (real captures, clean-machine
   tests, dataset downloads).

## Execution: two tracks

The critical path (the DSP chain: sync, demod, Viterbi, framing, analyse) stays in the main
session — handing it to a subagent would only add briefing time and hide the debugging. A
background subagent works off to the side on P0's docs/checks and P1's wiring against a contract
the main session writes up front (a pydantic `DetectionReport` plus its TS mirror), committing to
its own branch that gets squash-merged into the phase commit. Budget: about 7 h of planned work
inside the 10 h sprint, leaving about 3 h of buffer for debugging the slice (timing, phase
ambiguity, Viterbi alignment) — the P1 slice is never dropped; P2 items drop from the bottom first
if the buffer runs out.
