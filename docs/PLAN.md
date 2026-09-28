# Sanket — build plan

**Sanket** (संकेत, "signal") is our SIH26147 product: an offline, CPU-only workstation that takes an unknown `.iq` or `.wav` recording and works out how it was transmitted — sample format, bandwidth, SNR, symbol rate, modulation, interleaver, error-correction code and framing — then undoes each layer to recover the bits, showing the evidence for every claim.

This plan is written to ship **Sanket 1.0 as production software**, not a demo. It is organised by milestones with measurable exit gates rather than by calendar weeks or people. Last revised **28 September 2026**.

Related: [Problem statement](PROBLEM_STATEMENT.md) · [README](../README.md) · [Standards to beat](STANDARDS_TO_BEAT.md) · [Source dossier](SIHPS_ANALYSIS.md) · [Research report](../reports/SIH26147%20solution%20research.md) · [Claude Code tooling](../.claude/CLAUDE_SKILLS_MCP.md)

---

## 0. Progress

*Checked against the repository on **28 September 2026**. This section tracks the current snapshot only; the full dated narrative for how each stage got here is in [PROGRESS_LOG.md](PROGRESS_LOG.md). Update this section whenever an item lands.*

**Prototype mode is active** ([PROTOTYPE_PLAN.md](PROTOTYPE_PLAN.md)): the project is sprinting toward a demo — one synthetic recording decoding two signals to VERIFIED, one labelled analog, one honestly undecoded. Finishing M2's own exit gate is deferred to Phase P4, after the demo, before any M3 production work.

| Stage | Built | Gate met |
|---|---|---|
| Idea submission (due 30 Sep, [§9](#9-external-dates-sih)) | Docs done, deck not started | — |
| M0 Foundations and identity | Yes | Yes (27 Sep) |
| M1 Ingest, evidence model, ground-truth lab, bench v0 | Yes | Yes (27 Sep) |
| M2 Spectrum, detection, estimation, real tiles | DSP core, bench numbers, 4 GiB scale test, server tile pyramid, detection results/boxes in the UI | No — see Open gates |
| M3 Synchronisation and demodulation | Prototype thin slice in progress | No |
| M4 Modulation classification | Not started (a cumulant-rank prototype may land in P2) | No |
| M5 GF(2) kernel, interleavers, FEC | Not started (an RS/interleaver prototype may land in P2) | No |
| M6 Framing and known-system verification | Not started (CCSDS ASM + CRC-16 is the P1 demo target) | No |
| M7 Analyst workflow and reports | Not started | No |
| M8 Hardening, validation and 1.0 release | Not started | No |

**Open gates**

| Gate | Target | Measured | Suspected cause |
|---|---|---|---|
| M2 SNR-error | ±1 dB, 0–20 dB | −8.7 dB median error at 0 dB, only inside ±1 dB at ≥ 15 dB — [bench-v0-detect.md](../bench/results/bench-v0-detect.md) | Single estimator (`snr_psd`); M2M4 and eigenvalue/MDL cross-checks not built |
| M2 false detections | ≤ 0.05/scene | 0.20/scene on linear modulations at 3/6/20 dB — [bench-v0-detect.md](../bench/results/bench-v0-detect.md) | Untraced for linear modulations; M-FSK's share is traced to unshaped tone splatter in `dsp.synth` (see PROGRESS_LOG.md); `merge`/`absorb_sidelobes` in `dsp/detect.py` are the likely place to look next |
| M2 first tile ≤ 2 s | ≤ 2 s | Not measured yet | `RecordingStore.open` builds the whole pyramid before returning; needs a fast first pass or a background build |

**Next**
- Land the prototype P1 thin slice: QPSK + BPSK to VERIFIED frames, FM labelled analog, one signal honestly undecoded ([PROTOTYPE_PLAN.md](PROTOTYPE_PLAN.md)).
- Widen in P2 as time allows: cumulant classify, a block interleaver, RS(255,223), 2-FSK.
- After the demo (P4): close M2's SNR-error and false-detection gates, then resume M3 production work.
- Confirm the SIH submission template and re-run the rival scan ([§9](#9-external-dates-sih)).
- Build the idea-submission deck.

---

## 1. What 1.0 is

**In scope**

- **Every kind of input except real-time streams.** Every input ends up as a file on this machine, and every analysis runs on a file. Files of any size are streamed.
  - **File formats** (M1):
    - SigMF: the full `core:datatype` vocabulary, archives, multi-capture recordings, and metadata that points at another file.
    - Raw headerless files in all 28 SigMF datatypes, both byte orders, IQ or QI.
    - WAV: mono or stereo, integer or float, including RF64/Wave64 for files over 4 GiB and the SDR `auxi` chunk.
    - Compressed audio (FLAC, MP3, Ogg).
    - SDRangel `.sdriq`, MIDAS Blue, VITA 49 packet recordings, NumPy `.npy`, and `.gz`/`.zip`-compressed recordings.
    - Anything else is read as raw bytes, with a header offset and the format sniffer.
  - **Routes:**
    - Open a path (nothing is copied).
    - Upload by drag-and-drop to the local server.
    - Open a folder as a batch, or a numbered sequence of files as one recording.
    - The `sanket analyse` command line.
    - Capture from a locally connected receiver (M7): a USB SDR, or a sound-card input carrying a receiver's audio or IQ output.
- **Analyst context:** known parameters, a suspected standard or service, and capture details, entered before or during analysis.
- **Save as SigMF:** once its format is confirmed, any non-SigMF recording gets a `.sigmf-meta`, so its format is never guessed again.
- **Known-system verification** (M6): after the blind chain, the results are matched against a small catalogue of common public systems (CCSDS telemetry coding, AIS, NAVTEX, MF/HF DSC, POCSAG). A match is VERIFIED only when that system's own check passes on this recording.
- **Analyst profiles** (M7): save the chain a finished analysis found, then apply it to later recordings, so the work isn't redone. It is still checked on every recording.
- Multi-signal detection in time and frequency, parameter estimation, synchronisation and demodulation of PSK, QAM and FSK to soft bits.
- Analog signals (AM, FM, SSB, Morse CW) detected, labelled and measured, and kept out of the digital chain.
- Modulation classification with open-set rejection.
- Blind identification and decoding of block, convolutional, helical and catalogued pseudo-random interleavers; convolutional (incl. punctured), Reed-Solomon, concatenated and catalogued LDPC codes.
- Frame sync discovery, frame length, header fields, CRC checks.
- A web GUI served locally: waterfall, PSD, constellation, eye diagram, evidence, hypothesis accounting, frames, assumptions. Analyst overrides that re-run downstream stages.
- Exports: JSON, CSV, PDF, SigMF annotations; profiles as files.
- One-folder installable build for Windows 10/11 x64 and Ubuntu 22.04+ that runs with networking switched off. The build opens Sanket in its **own desktop window** (pywebview) over the same local server. The same UI stays reachable from any browser at 127.0.0.1, which is also the fallback when no system webview is available.

**Out of scope for 1.0**:
- real-time analysis of a live stream (capture always goes to a file first)
- capture from network-attached receivers (KiwiSDR, LAN SDRs, VITA 49 over UDP). It would break the 0-outbound-connections rule (§2). Record with the receiver's own tool, then open the file.
- transmitting
- decrypting protected payloads
- generic pseudo-random permutation recovery
- a large protocol library: the known-system catalogue verifies a few public systems, not thousands of modems
- multi-user server deployment

**After 1.0** (future scope; not scheduled in any milestone):

- Playable audio: demodulate analog AM, FM and SSB voice to a WAV the analyst can listen to and export. Digital voice (DMR, P25 and similar) stays out, because its voice codecs are patented.
- Time-domain views: I and Q, amplitude, phase and instantaneous frequency against time for the selected signal. The FSK instantaneous-frequency view is the first of these.
- OFDM (Wi-Fi, LTE, DVB-T): detect it and estimate its subcarrier spacing and cyclic-prefix length. Until then, OFDM is labelled unknown by the open-set rejection (M4) rather than forced into a single-carrier label.
- An explain mode that redraws the selected signal on a slow toy carrier, as sine and cosine, so phase flips (PSK), tone changes (FSK) and amplitude steps (QAM) are visible. It is always labelled *illustrative*, because the recording holds no carrier.
- ASK/OOK and pulse-position demodulation (garage remotes, 433 MHz sensors, RFID, ADS-B), which would let ADS-B join the known-system catalogue.
- Payload text for catalogued systems whose payload is plain characters (NAVTEX messages, POCSAG alphanumeric pages).
- More known-system entries, wherever the specification is public, e.g. MIL-STD-188-110 and STANAG 4285 serial-tone modems, and ACARS.

## 2. The production bar

1.0 ships only when every row holds, each enforced by a test or a script rather than a review comment. Numeric targets for the signal-processing itself are in [STANDARDS §8](STANDARDS_TO_BEAT.md#8-our-bar--measurable-targets); these are the product-level requirements around them.

| Area | Requirement | Enforced by |
|---|---|---|
| Correctness | Every stage is tested against exact ground truth from our generator, including a case where it must fail or abstain | pytest + `bench/` |
| Honesty | Every reported value is a `Parameter` with an evidence level; **0 silent defaults**; VERIFIED only from a CRC pass, sync-word recurrence or a re-encode match consistent with EVM; every value taken on a convention is a HYPOTHESIS listed under `needsReview` | Schema validation on every result; an ingest test that enumerates every unknown-format path |
| False accepts | **0 accepted decodes on ≥ 1,000 null files** (noise, uncoded, repetition, idle) | `bench run --null` in CI (nightly) |
| Scale | Files ≥ 4 GiB processed end to end; peak memory stays bounded and independent of file size | Scale test on a generated 4 GiB file; RSS ceiling asserted |
| Performance | Full chain on 10 M samples ≤ 10 s on a 4-core laptop (excluding blind LDPC catalogue search); first waterfall tile ≤ 2 s after ingest starts; pan/zoom holds 60 fps at 1080p on integrated graphics | `bench perf` with thresholds; a frame-time check in E2E |
| Reliability | A stage that throws is marked FAILED with its error and the job continues where it can; the server never crashes on bad input; jobs survive a restart | Fault-injection tests; parser fuzzing; restart test |
| Offline | **0 outbound connections** at runtime; no CDN; fonts and assets bundled | Socket-blocking E2E run in CI; build scan for external URLs |
| Security | Binds to 127.0.0.1 by default; upload size limits; export filenames sanitised (a rival had path traversal here); no shell interpolation of filenames; capture recorders run from an argument list, never through a shell; archive extraction is guarded against path traversal and decompression bombs; imported profiles are schema-validated data, never code; dependency audit | Security tests; `pip-audit` and `npm audit` in CI |
| Reproducibility | Same file + same Sanket version + same settings → byte-identical results JSON. Results record the Sanket version, the FEC and known-system catalogue versions, the model hash, seeds, and the profile (name and version) if one was applied | Hash test on the bench set |
| Accessibility | Every control keyboard-reachable; WCAG 2.2 AA contrast in both themes; evidence never conveyed by colour alone; reduced-motion respected | axe checks in E2E; manual keyboard pass per release |
| Observability | Structured local logs (JSON lines, per job); per-stage timings in the run record (§3), kept out of the results so they stay reproducible; a "diagnostics bundle" export with logs and versions but no recording data | Tests on the bundle and run-record contents |
| Licensing | No GPL, AGPL or non-commercial code in the product; `THIRD_PARTY.md` generated from the lockfiles | Licence check in CI fails the build |
| Data handling | Recordings never leave the machine; the workspace directory is configurable; deleting a job deletes everything derived from it. Profiles hold no samples, only parameters and the source recording's hash, so they outlive the job they came from. | Tests on deletion and on profile contents |
| Packaging | One-folder build per platform, one start command, frozen Numba works (pinned numba/llvmlite, writable `NUMBA_CACHE_DIR`, kernels pre-warmed); the start command opens the desktop window, or the browser when no webview is available; the window passes the same 0-outbound-connections check as the browser | Frozen-build smoke test in CI on both platforms, including window launch and the browser fallback |

## 3. Architecture

```mermaid
flowchart LR
    UI["Desktop window (pywebview)<br/>or any browser<br/>React + TS, WebGL2"] -- "/api/v1 + SSE" --> API["FastAPI on 127.0.0.1<br/>(serves the SPA too)"]
    API --> Jobs["Job runner<br/>process pool"]
    Jobs --> Graph["Stage graph<br/>dsp/ + ml/"]
    Graph --> Store[("Workspace<br/>SQLite + content-addressed artifacts")]
    API --> Store
```

One local process tree, no external services. The pieces and the contracts between them:

- **Stage graph.** Each stage is a pure function `run(inputs, params, overrides) → StageResult {parameters, artifacts, warnings}`; its duration goes to the run record. Its cache key is the hash of its input artifacts, parameters and stage code version. An analyst override invalidates that stage and its descendants only, which is what makes "correct a stage, re-run the rest, show the diff" (D5) cheap.
- **Evidence model.** `Parameter {value, unit, uncertainty, level, confidence, method, evidence[], alternatives[], warnings[], resolve_hint, proof, convention}` in [`dsp/src/dsp/evidence.py`](../dsp/src/dsp/evidence.py) is the source of truth; its JSON uses the frontend's camelCase field names. It enforces the honesty rules when a value is built: UNKNOWN has no value and must state why and what would settle it, an ESTIMATED number carries its uncertainty, and VERIFIED requires a CRC, sync-recurrence or re-encode proof. A value the evidence can't decide, taken on a stated convention instead (a raw file's IQ order, say), is a HYPOTHESIS whose `convention` field names the convention. Downstream proof may **promote** an upstream value (a CRC pass makes the modulation VERIFIED); the promotion is recorded as evidence and clears any convention. The frontend type in [`frontend/src/lib/evidence.ts`](../frontend/src/lib/evidence.ts) predates it: the demo data puts uncertainty inside the unit text. That type is replaced by one generated from the API schema when real results reach the UI (M2).
- **Results and run record.** A job writes two documents, each with its own schema version. `results.json` ([`dsp/results.py`](../dsp/src/dsp/results.py), schema generated to `results.schema.json`) holds only what the analysis concluded — the `Assumptions` block, stage results, parameters — and is byte-identical across runs. Its top-level `needsReview` lists every value taken on a convention, derived from the parameters so it can't disagree with them: one field tells a reader, a script or the PDF whether anything rests on a guess. `run.json` holds how the run went: the job id and the SHA-256 of the results it belongs to, per-stage duration and whether the stage was computed or served from cache, start and end times, peak memory, Sanket version, and hardware class and OS version. It never contains the hostname, username or file paths. `bench perf` reads run records.
- **Hypothesis ledger.** Every blind search writes every candidate it tried — statistic, p-value, corrected threshold, outcome, reason — plus its shuffled-bit false-alarm runs. The D8 hypothesis table renders this ledger directly. Known-system and profile matches (M6, M7) are hypotheses too and are counted in the same ledger.
- **Stages.** Ingest → Detect → Estimate → Sync → Classify → Demodulate → De-interleave → FEC → Frame → **Match**. Match runs after the blind chain. It compares the results with the known-system catalogue and the analyst's profiles, and runs each candidate system's own check. It never overwrites a blind result; a VERIFIED match may promote upstream values, as any proof does.
- **Inputs.** Every route (path, upload, folder, file sequence, CLI, capture) produces a *recording*: one or more files plus a container description. Readers for each container expose the same chunked sample interface, so nothing downstream knows where a recording came from. Capture is a job that runs a recorder subprocess into the workspace and then writes SigMF metadata.
- **Profiles.** A profile is a schema-versioned document that lists the confirmed stage settings (see M7). It is stored in the workspace database and can be exported and imported as a file. A job may run with a profile; its settings enter as analyst-entered values and are checked like any other.
- **Streaming.** Readers are memory-mapped and chunked; detectors run on chunks; nothing loads a whole file.
- **Tiles.** The server computes a multi-resolution STFT pyramid quantised to uint8 dB in fixed-size tiles, **max-pooled** between levels so short bursts survive zooming out. The frontend already renders a uint8 dB texture through a LUT shader; switching it from one demo texture to server tiles is an M2 task.
- **API.** Versioned under `/api/v1`. The OpenAPI schema generates the TypeScript types the frontend compiles against, so a contract break fails the build. Progress over server-sent events. Literal routes are registered before parameterised ones.

  | Endpoint | Purpose |
  |---|---|
  | `POST /recordings` | Chunked upload; or register a local path, a folder (one recording per file) or an ordered file sequence (one recording), without copying |
  | `GET /recordings/{id}` | Metadata, container, format candidates, assumptions |
  | `PUT /recordings/{id}/context` | Analyst context: known parameters, suspected standard, capture details |
  | `POST /recordings/{id}/sigmf` | Write a `.sigmf-meta` for a confirmed non-SigMF recording |
  | `GET /devices` · `POST /captures` | Locally connected receivers and sound-card inputs · record a set duration into a new SigMF recording |
  | `GET /profiles` · `POST /profiles` | List · save a profile from a finished job |
  | `GET /profiles/{id}/export` · `POST /profiles/import` | Profile as a file · import one |
  | `POST /jobs` · `GET /jobs/{id}/events` | Start analysis, optionally with a profile · SSE progress |
  | `GET /jobs/{id}/results` | Stage results, parameters, ledger, frames |
  | `GET /tiles/{rec}/{level}/{t}/{f}` | uint8 dB waterfall tile |
  | `POST /jobs/{id}/overrides` | Analyst correction → downstream re-run |
  | `GET /jobs/{id}/export.{json,csv,pdf,sigmf}` | Exports, each carrying the assumptions block; the run record is included unless the analyst opts out |

- **Repository layout.**

  ```
  frontend/   React + TS + Vite (identity, workspace, demo data; e2e/ holds the Playwright tests)
  dsp/        ingest, synth (ground-truth generator), detect, estimate, sync, demod, gf2, deinterleave, fec, framing, systems (known-system catalogue and match), evidence
  ml/         AMC training, evaluation, ONNX export, model card
  backend/    FastAPI app, job runner, storage, capture, profiles, exports, CLI, packaging
  bench/      generator presets, sealed set, null set, results, perf, decoder-truth harness
  tests/      Python tests, one folder per package
  tools/      repo scripts (THIRD_PARTY.md and licence check)
  docs/       plan, standards, dossier
  ```

## 4. Product identity (fixed)

The identity is implemented in [`frontend/`](../frontend/) and is the reference for every screen, export and slide.

| Element | Decision | Source of truth |
|---|---|---|
| Name | **Sanket** (संकेत, "signal"); tagline "Blind signal analysis, with evidence" | `frontend/src/brand.ts` — change it there only |
| Mark | A waveform resolving into a four-point constellation: signal in, symbols out | `frontend/src/components/Logo.tsx`, `frontend/public/favicon.svg` |
| Colour | Dark-first instrument UI with a light theme; accent "signal cyan"; all colours are tokens with shadcn/ui-compatible names | `frontend/src/styles/index.css` |
| Evidence levels | VERIFIED green + shield · MEASURED blue + ruler · ESTIMATED violet + Σ · HYPOTHESIS amber + dashed circle · UNKNOWN grey + slashed circle | `frontend/src/components/levelStyles.ts` |
| Type | IBM Plex Sans for UI, IBM Plex Mono with tabular numerals for every number, IBM Plex Sans Devanagari for the native name — all bundled | `frontend/src/main.tsx` |
| Colormaps | "Sanket" house map plus Viridis, Inferno, Grayscale; all tested for monotonic luminance | `frontend/src/lib/colormaps.ts` |

**UI rules** that every new screen follows:

1. An evidence level is always glyph + label + colour, never colour alone.
2. Every number shows its unit and, where it's estimated, its uncertainty. True minus signs; non-breaking space before units.
3. UNKNOWN always says why and what would settle it.
4. Demo or synthetic data is always labelled as such, on screen and in any screenshot.
5. No dead controls: a button that can't work yet isn't shown.
6. Plots are dark in both themes; their overlays use the dark palette.
7. A value taken on a convention says so and offers the alternative; the `needsReview` items are visible without opening each parameter.
8. Workspace layout: detections and pipeline on the left; waterfall, PSD and the hypotheses/frames/assumptions tabs in the centre; symbol view and evidence on the right. Below 1280 px the page scrolls and panels stack.

## 5. Milestones

Dependencies: **M0 → M1 → M2 → M3 → (M4 ∥ M5) → M6 → M8**, with **M7** running alongside from M2 onward. Every exit gate is measured in `bench/` or CI, never asserted. Status is tracked in [§0](#0-progress); the Claude Code skills, plugins and MCP servers for each milestone are mapped in the [tooling map](../.claude/CLAUDE_SKILLS_MCP.md#1-tooling-by-milestone).

**Gate policy:** a missed exit-gate number becomes an *Open gate* in [§0](#0-progress) rather than blocking the next milestone — the work moves on, and every open gate closes by M8. **Build order:** land the thinnest slice through the whole chain first (ingest → detect → estimate → sync → demod → decode → frame, one modulation, one code, exact ground truth), prove it end to end, then widen breadth (more modulations, codes, interleavers) before depth (edge cases, performance, real captures).

| | Milestone |
|---|---|
| M0 | Foundations and identity |
| M1 | Ingest, evidence model, ground-truth lab, bench v0 |
| M2 | Spectrum, detection, estimation, real tiles in the UI |
| M3 | Synchronisation and demodulation |
| M4 | Modulation classification |
| M5 | GF(2) kernel, interleavers, FEC |
| M6 | Framing and known-system verification |
| M7 | Analyst workflow and reports |
| M8 | Hardening, validation and 1.0 release |

### M0 — Foundations and identity

- **Frontend:** Vite + React 19 + TypeScript (strict) + Tailwind 4; the §4 identity and design tokens; the full analysis workspace driven by a deterministic synthetic capture generated in a Web Worker — WebGL2 waterfall (R8 dB texture + LUT shader, zoom/pan/keyboard, detection overlays, hover readout), uPlot PSD locked to the waterfall's frequency window, constellation and FSK tone views, evidence cards, hypothesis ledger, frames and assumptions tables; unit tests for FFT, colormaps, generator, view maths and formatting.
- **Python:** 3.12 (pinned) + uv workspace for `dsp/`, `ml/`, `backend/`, `bench/`.
- **Backend:** FastAPI skeleton that serves the built frontend; a `sanket` start command.
- **CI** on Windows and Ubuntu: ruff, pyright (strict on `dsp/`), pytest, `tsc`, ESLint, Vitest, build, licence check.
- pre-commit hooks; `THIRD_PARTY.md` generated from lockfiles.
- Playwright smoke test (the identity-pass browser checks become the first E2E), run once with sockets blocked.
- **Exit gate:** a clean clone goes green in CI on both platforms, and `sanket` starts one process that serves the UI with networking off.

**Checklist** (detail: [PROGRESS_LOG.md](PROGRESS_LOG.md))
- [x] Vite + React 19 + TS strict + Tailwind 4; §4 identity and design tokens
- [x] Full analysis workspace on synthetic data: waterfall, PSD, constellation/FSK views, evidence, ledger, frames, assumptions tables
- [x] 26 unit tests; lint/typecheck/build clean; browser check both themes, no console errors, no non-localhost requests
- [x] uv workspace (`dsp`/`ml`/`backend`/`bench`); ruff + pyright (strict on `dsp/`) + pytest clean; `ml/` excluded from the product install
- [x] FastAPI app + `sanket` start command bound to 127.0.0.1; `GET /api/v1/health`
- [x] pytest-socket (loopback-only tests); pre-commit hooks; `THIRD_PARTY.md` generated, fails on GPL/AGPL/non-commercial
- [x] Playwright smoke test with sockets blocked; CI green on Windows and Ubuntu
- [x] Claude Code setup: project MCP servers, permissions, `plan-status`, `ponytail`/`frontend-design` plugins

### M1 — Ingest, evidence model, ground-truth lab, bench v0

- **Evidence model** in `dsp/evidence` (§3); JSON schema generated from it; every result validated against the schema.
- **Ingest:**
  - SigMF full `core:datatype` vocabulary; raw formats in both byte orders and IQ/QI; WAV mono (analytic signal, flagged HYPOTHESIS for digital labels) and stereo (quadrature check plus an analyst prompt)
  - **every container we can name**, each behind the same chunked reader interface:
    - WAV: integer and float PCM, `WAVE_FORMAT_EXTENSIBLE`, RF64/Wave64 over 4 GiB. The `auxi` chunk written by SDR#, HDSDR and SDRuno is read as MEASURED metadata (centre frequency, start time).
    - SigMF archives (`.sigmf`), multi-capture recordings, and metadata that points at another file with a header offset. "Save as SigMF" (M7) writes that last form.
    - SDRangel `.sdriq`, MIDAS Blue and VITA 49 packet recordings: their headers or context packets give sample rate and centre frequency.
    - NumPy `.npy`.
    - Compressed audio (FLAC, MP3, Ogg) via `soundfile` (libsndfile, LGPL-2.1). Lossy formats distort phase, so digital labels from them are capped at HYPOTHESIS, with the reason stated.
    - `.gz`/`.zip` recordings, decompressed into the workspace first, because analysis needs random access; the disk cost is shown before decompressing.
    - A numbered sequence of files, read as one recording.
    - Anything else: raw bytes with an analyst-set header offset, and the format sniffer.
  - recorder file extensions (`.cfile`, `.cu8`, `.cs8`, `.cs16`, `.cf32`, `.raw`, `.bin`, `.dat`) are only **hints** that rank the sniffer's candidates, never taken as fact
  - chunked, random-access reader with memory bounded by the chunk size; file-size-versus-datatype consistency check (ORACLE's metadata says 32-bit, its data is complex128)
  - **format sniffer** that proposes ranked candidates and never picks silently: header detection, then every SigMF datatype scored by estimated code length (bits/byte) under a linear predictor on blocks sampled across the file — a wrong byte order, width or signedness looks like random bytes, and invalid floats cost their full width; report the margin over the runner-up, and UNKNOWN with the tied candidates when formats with different components tie. Real vs complex is decided on prediction gain; where the samples can't tell them apart (noise, real low-pass signals), complex is proposed as a HYPOTHESIS on a stated convention, listed under `needsReview`. IQ/QI stays an analyst toggle — a swap only mirrors the spectrum. Validated with a confusion matrix over all format permutations.
  - **sample-rate candidates**, ranked: filename hints, the WAV `auxi` chunk, standard SDR device rates, and structural matches (a recognised symbol rate × candidate Fs within 0.1 % promotes it to HYPOTHESIS). With no candidate, output in normalised units.
  - an `Assumptions` block in every output
- **Ground-truth lab:**
  - `dsp/synth`, a NumPy generator, as the main source: modulation × pulse shape × FEC × interleaver × framing with CRC, writing SigMF with the truth in annotations; Sig53-style impairments (AWGN, CFO, phase noise, IQ imbalance, multipath/fading, timing drift, clipping, AGC), ±10–20 % samples-per-symbol jitter, an explicit noise class
  - TorchSig (WSL2) as an **independent** test generator; generate only the subsets needed (full corpus is about 1 TB)
- **Bench v0:** fixed seeds; a **sealed** held-out set never inspected during development; the null set; `bench run` writes versioned results JSON.
- **Exit gate:** round-trip tests pass for every format and container (read-only containers and lossy audio are tested against files of known content); sniffer confusion matrix published; 0 silent defaults (tested); bench v0 and null set generated.

**Checklist** (detail: [PROGRESS_LOG.md](PROGRESS_LOG.md))
- [x] Evidence model (`dsp/evidence.py`) with honesty rules enforced at construction; `promote()` for downstream proof
- [x] All 28 SigMF datatypes round-tripped; IQ/QI swap; chunked random-access reader with header offset and trailing-byte count
- [x] SigMF metadata → Parameters (datatype/rate/centre frequency MEASURED or UNKNOWN); JSON schema generated with `needsReview`
- [x] Format sniffer with ranked candidates: 0 wrong formats on the 864-file bench ([sniffer.md](../bench/results/sniffer.md))
- [x] Sample-rate candidates (filename hints, device rates, structural match), tested at α = 1%
- [x] WAV (RIFF/RF64/Wave64, int/float PCM, `WAVE_FORMAT_EXTENSIBLE`, `auxi` chunk) with the stereo quadrature check
- [x] SigMF archives/multi-capture/NCD, `.npy`, `.sdriq`, MIDAS Blue, VITA 49, FLAC/MP3/Ogg, `.gz`/`.zip`, numbered sequences — one chunked reader interface
- [x] 0 silent defaults tested for every reader; recorder-extension sniffer hints
- [x] `dsp/synth` ground-truth generator (bits → frames → FEC → interleave → modulate → impair → SigMF), regenerable from (scene, seed)
- [x] TorchSig (WSL2) as an independent generator, dev-time only, nothing in the product imports it
- [x] Bench v0 (`generate|run dev|null|sealed`); [dev](../bench/results/bench-v0-dev.md) and [null](../bench/results/bench-v0-null.md) results published

### M2 — Spectrum, detection, estimation, real tiles

- **Detection:** streaming Welch PSD and spectrogram; percentile noise floor; OS-CFAR + hysteresis + morphological clean-up + connected-component labelling; run at 2–3 FFT sizes and merge with NMS; channelisation (mix, filter, decimate).
- **Analog signals:** detect AM, FM, SSB and Morse CW before digital classification, from the envelope, the FM discriminator output and the spectrum's sideband symmetry. Label and measure them: carrier, occupied bandwidth, FM deviation, Morse keying speed. A signal labelled analog skips the digital chain, and the reason is stated. FM carrying audio otherwise looks like FSK or PSK (STANDARDS §6.11).
- **Estimation:** occupied bandwidth; RRC roll-off by least-squares PSD fit, snapped to standard values; SNR from three estimators (PSD in-band vs guard, M2M4 for PSK, eigenvalue/MDL) with their agreement as the confidence; symbol rate from the |x|² line (x²/x⁴ for BPSK/QPSK), refined by cyclic autocorrelation and confirmed by our own FAM/SSCA, with an occupied-bandwidth fallback below β ≈ 0.1; FSK rate from instantaneous frequency; CFO by M-th power (gated for QAM); cumulants C20, C40, C42.
- **Tiles in the UI:** server STFT pyramid with max-pooling; frontend switches from the demo texture to tiled level-of-detail rendering; detection boxes from real results.
- **Real/complex ties:** when the format sniffer can't tell the real and complex readings apart, the stage graph carries both forward, as with phase ambiguity (M3), and downstream proof (sync recurrence, CRC) decides. This replaces the interim "complex by convention" rule; a branch that finds nothing is dropped and its cost goes to the run record.
- *Stretch:* frequency-hopper clustering (DBSCAN over detections); co-channel overlap *detection* via multiple cyclic lines or MDL > 1.
- **Exit gate:** STANDARDS §8 detection and estimation targets met per SNR bucket; a 4 GiB file streams through detection with bounded memory; first tile ≤ 2 s. **Not yet met** — see [§0 Open gates](#0-progress).

**Checklist** (detail: [PROGRESS_LOG.md](PROGRESS_LOG.md))
- [x] Reader dispatcher picks a reader from header magic and name
- [x] Streaming Welch spectrogram/PSD bounded by `MAX_CELLS`; real input keeps only non-negative frequencies
- [x] Detection: OS-CFAR + hysteresis + morphological clean-up + connected-component labelling, multi-FFT-size merge, sidelobe absorption, I/Q-image mirroring
- [x] Channelisation: streaming mix + Kaiser low-pass + decimate
- [x] Estimation: symbol rate, CFO, occupied bandwidth, SNR (single estimator), RRC roll-off, cumulants
- [x] Analog AM/FM detection with a kurtosis gate against M-FSK
- [x] `dsp-reviewer` pass over the new modules; three real bugs found and fixed
- [ ] STANDARDS §8 targets: recall/rate-error/CFO-error met; **SNR-error and false detections open** (see [§0](#0-progress))
- [x] 4 GiB file streams with RSS < 512 MiB (`tests/dsp/test_scale.py`)
- [x] Server STFT tile pyramid, max-pooled, served over `/api/v1/tiles`
- [x] Frontend switched from the demo texture to server tiles; recording Assumptions as evidence cards
- [ ] First tile ≤ 2 s: not measured, likely unmet (the pyramid builds from a full file read today)
- [x] Detection results as `Parameter`s (`detection_parameters`); boxes on the real waterfall from real results
- [ ] LOD tile rendering; estimator refinements (cyclic autocorrelation, FAM/SSCA, 2nd/3rd SNR estimator); analog measurements (carrier, bandwidth, deviation); real/complex branches; generated frontend types; hopper clustering/co-channel overlap (stretch)

### M3 — Synchronisation and demodulation

- RRC matched filter; Gardner / Mueller-Müller timing with a Farrow interpolator; Costas loop plus decision-directed tracking for QAM; FSK discriminator averaged over each symbol interior.
- BPSK, QPSK, 8PSK, 16/64-QAM, 2/4/8-FSK (stretch: MSK/GMSK, OQPSK, π/4-DQPSK); Gray demapping to LLRs; EVM and lock metrics; eye diagram in the UI.
- Phase ambiguity: carry every rotation forward; FEC and sync stages resolve it.
- **Exit gate:** BER within 1 dB of theory on AWGN for every supported modulation.

### M4 — Modulation classification

- Explainable cumulant and spectral-line rules, each decision listing its evidence.
- A ~10K-parameter complex-as-real 1-D CNN on [I, Q, |x|, Δφ] after resampling to 4–8 samples per symbol, cumulant features fused before the head, trained on our impaired generator. Temperature calibration only if expected calibration error improves.
- Three-layer open-set rejection: SNR gate → energy score → Mahalanobis distance to class prototypes with per-class thresholds; logits averaged over windows. An "analog" outcome sits beside "unknown", so AM/FM/SSB audio that slipped past the M2 check is never given a digital label.
- Organiser data: the PS suggests using training data in both `.IQ` and `.wav` formats. If the organisers supply a labelled set, ingest it through the normal readers, evaluate on it, then fine-tune and report both results. It is never used as the sealed test set.
- Fusion: agreement → ESTIMATED; disagreement → HYPOTHESIS with both rankings.
- FP32 ONNX with no signal processing in the graph; model identity pinned in `ml/MODEL_CARD.md`.
- Evaluation on data we didn't generate (TorchSig, HisarMod, RadioML with corrected labels — its SNR labels, AM-SSB class and 2018.01A class mapping are wrong, and its licence is non-commercial); accuracy vs SNR −20 to +30 dB; open-set AUROC, FPR@95 %TPR, OSCR per SNR bin.
- **Exit gate:** STANDARDS §8 AMC targets met; labels are suppressed outside the validated SNR range.

### M5 — GF(2) kernel, interleavers, FEC

The core differentiator (D9): no public implementation of these methods exists.

- **Kernel first:** one bit-packed, Numba-JIT GF(2) Gauss-Jordan elimination (GJETP) reused for code length, sync offset, puncturing period, parity-check recovery and interleaver period; soft variant (rows ordered by LLR reliability) and rank iteration.
- **Catalogue** (versioned YAML, each entry with source and licence): convolutional K=3–9 at ½ and ⅓ with CCSDS / DVB / 802.11 punctures; RS(255,223) CCSDS, RS(204,188) DVB and shortened variants; concatenated RS + conv with a byte interleaver; LDPC from CCSDS, DVB-S2 short frames, 802.11n and 5G NR base-graph subsets.
- **Identification:** convolutional via dual-code parity checks, punctured codes via Marazin's two-stage method, scored by parity-check probability from LLRs; RS via a binary rank scan then a Galois-field Fourier transform over 16 primitive polynomials × symbol offsets plus the CCSDS dual basis (`galois`); LDPC by soft syndrome-posterior scoring against the catalogue; concatenated chains inner-first.
- **Interleavers:** block via rank-drop plus a KS test on rank distributions; Forney via an (I, J, phase) grid; helical via the dedicated period/row/column estimators; pseudo-random only against a catalogue of **standard permutations** (3GPP turbo, LTE QPP, 802.11, DVB-S2) — anything else is UNKNOWN with its measured period.
- **False-alarm control:** every hypothesis counted into the ledger; Holm (or Benjamini–Hochberg) across the whole search; rank matrices always have L ≥ w + 30 rows; every detector also runs on shuffled bits and reports its empirical false-alarm rate.
- **Decoders:** Numba Viterbi (soft), RS via `galois`, normalised min-sum LDPC.
- *Stretch:* a gradient-boosted code-family pre-classifier on handcrafted bitstream features (run length, entropy, autocorrelation, rank features) that only **orders** the catalogue search; the full search still runs and decides. Built only if the search misses the §2 performance target; versioned and recorded in results like the AMC model.
- **Exit gate:** per-family, soft-decision FEC-ID targets from STANDARDS §8; **0 false accepts on ≥ 1,000 null files**.

### M6 — Framing and known-system verification

- Known-sync library (CCSDS ASM, Barker, POCSAG and others) plus blind sync discovery with a significance test against control words.
- Frame length from autocorrelation; constant-bit and counter-field tests on headers; CRC-16/32 checks.
- Frame table with header/payload split, exportable as bits, hex and JSON.
- **Known-system catalogue** (`dsp/systems`): versioned YAML like the FEC catalogue.
  - **What an entry records:** its public specification and licence note; modulation, symbol rate, tone shift or bandwidth; pulse shaping; interleaver; FEC; sync word or preamble; frame layout; and the system's own check. It may also name link-layer steps from a small fixed set: NRZI, HDLC bit de-stuffing, descrambling, time-diversity combining.
  - **1.0 entries**, chosen because each is public, is relevant to Indian real-world targets (M8), and has a check that can prove a match:

    | System | Specification | Signal | Proof that can make it VERIFIED (evidence-model proof kind) |
    |---|---|---|---|
    | CCSDS telemetry coding (also Meteor-M LRPT) | CCSDS 131.0-B, 132.0-B | BPSK/QPSK; ASM `0x1ACFFC1D`; conv K=7 r½, RS(255,223) | ASM recurrence (`sync_recurrence`); frame CRC-16 (`crc`) |
    | AIS | ITU-R M.1371 | GMSK 9,600 bit/s; NRZI; HDLC | CRC-16 per packet (`crc`) |
    | NAVTEX (SITOR-B) | ITU-R M.540, M.476/M.625 | 2-FSK 100 Bd, 170 Hz shift; 4-of-7 constant-ratio code; time diversity | Phasing-signal recurrence (`sync_recurrence`); the two time-diversity copies agree (`reencode`, of the repetition) |
    | MF/HF DSC | ITU-R M.493 | 2-FSK 100 Bd, 170 Hz shift; 10-bit check code; time diversity | Phasing recurrence (`sync_recurrence`); check bits and diversity copies agree (`reencode`) |
    | POCSAG | ITU-R M.584 | 2-FSK 512/1,200/2,400 bit/s | Sync codeword `0x7CD215D8` recurrence (`sync_recurrence`); BCH(31,21) check bits reproduced from the data bits (`reencode`) |

    No new proof kind is added: every check above is one of the three the evidence model already accepts.

    AIS needs the GMSK demodulator, a stretch item in M3. If that slips, AIS moves after 1.0.
  - **Match stage**, run after the blind chain:
    1. Each entry's parameters are compared with the blind results, within stated tolerances.
    2. Candidates that fit run their own link layer and check on this recording's demodulated bits.
    3. Every entry tried is counted in the hypothesis ledger, with the Holm correction.
    4. The output is a `System` parameter:
       - VERIFIED "POCSAG 1200 (ITU-R M.584)", when the check passes above the corrected threshold
       - HYPOTHESIS "consistent with …", when the parameters fit but the check can't run or doesn't pass
       - UNKNOWN "no catalogued system matches", listing the closest entries and why each failed
  - **Blind results always stand.** A verified system whose nominal values differ from them shows the difference, rather than hiding it. A VERIFIED match may promote upstream values (modulation, symbol rate) through the normal proof mechanism.
  - **Testing:** each entry ships with a `dsp/synth` preset and a test that the blind chain plus Match identifies it. The null set gains near-misses (right rate, wrong sync word; right sync, failing check) that must not match.
- **Exit gate:**
  - blind sync false-alarm rate ≤ 10⁻⁶ per stream, measured and reported
  - every catalogue entry VERIFIED on its synth preset
  - 0 false system matches on the null set

### M7 — Analyst workflow and reports

- Open-recording flow: drag-and-drop or path, format candidates shown before analysis, assumptions editable (centre frequency, sample rate, IQ swap). Every `needsReview` item (a value resting on a convention rather than evidence, e.g. a real/complex tie) is shown as a visible prompt in the Assumptions table, and exports and the PDF report list them.
- **Analyst context**, optional, at open time or later:
  - What it takes: known parameters (sample rate, centre frequency, symbol rate, modulation, bandwidth), a suspected standard or service, and capture details (receiver, location, time).
  - What entered values become: MEASURED with the method "entered by the analyst", and still checked against the data. A conflict (entered 9,600 Bd, measured 4,800 Bd) is shown as a warning, and the analyst resolves it.
  - What a suspected standard does: it can name a known-system entry or a profile. It only reorders the FEC and known-system catalogue searches, which still run in full, so a wrong hint cannot hide the true answer.
  - Where it is recorded: in the results beside the assumptions block.
- **Every input route in the UI:** open a path; drag-and-drop upload; open a folder as a batch; select a numbered file sequence as one recording. The same routes are available from the `sanket analyse <paths…>` command line, which writes the same results JSON.
- **Save as SigMF:** for any non-SigMF recording, write a `.sigmf-meta` holding the confirmed datatype, sample rate, centre frequency, IQ order and provenance. The samples stay untouched, and the source file is referenced with its header offset. The next open reads it as MEASURED instead of sniffing it.
- **Capture from a connected receiver** (receive-only):
  - Records a set duration into a SigMF recording, stamped with the device, gain, sample rate, centre frequency and time. The recording is then analysed like any file.
  - **USB SDRs:** RTL-SDR, HackRF, Airspy, USRP and others. Their drivers (librtlsdr, libhackrf, UHD) are mostly GPL, so each runs as a **subprocess** through its own command-line recorder (`rtl_sdr`, `hackrf_transfer`, `airspy_rx`, `rx_samples_to_file`). Other recorders can be added as an argument template, run without a shell. No driver is ever linked or imported.
  - **Sound-card input:** records a receiver's audio output, or an IQ output wired to a stereo input, to WAV via `sounddevice` (PortAudio, MIT). This is how HF receivers are commonly connected.
  - Devices appear only when their recorder or input is present. No dead controls: with no device, the capture button isn't shown.
  - Tested against a simulated recorder process and a virtual audio input.
  - The UI states that capture needs authorisation (§8).
- **Analyst profiles:** so the work isn't redone.
  - **What a profile holds:** after an analysis the analyst accepts, the chain it found — assumptions (datatype, sample rate, IQ order), channel (offset, bandwidth), modulation and its parameters, sync settings, interleaver, FEC, sync word, frame layout, and the header-field names the analyst assigned. Plus a name, notes, author and version, the Sanket and catalogue versions, and the source recording's hash. No samples.
  - **How it's applied:** to a new recording, a folder, or at open time.
    - Profile values enter as analyst-entered (MEASURED, with the method naming the profile) and are still checked against the data.
    - The decode is VERIFIED only by this recording's own CRC, sync or re-encode proof.
    - If the checks fail, Sanket reports that the profile doesn't fit and why, then runs the blind chain.
  - **How it's suggested:** the Match stage (M6) also compares results with saved profiles and suggests "matches your profile *X*". Suggestions are counted in the ledger like catalogue entries.
  - **Sharing:** profiles are exported and imported as schema-versioned files. They are validated on import and never executed. Moving them by file keeps stations air-gapped.
  - **Versions:** editing a profile creates a new version. Results record which version was applied.
- Overrides on any stage → downstream re-run → before/after diff.
- Job history; batch view; compare view.
- Exports: JSON (schema-versioned), CSV, PDF report, SigMF annotations; each carries the assumptions block and the Sanket/catalogue/model versions.
- Run record in exports: an "Include run record (timings, machine details)" checkbox in the export dialog, ticked by default and remembering the last choice; unticked, `run.json` is left out and the PDF drops its timing table. The CLI and batch export take `--no-run-record`.
- **Exit gate:** Playwright E2E covers open → analyse → override → save profile → apply it to a second recording → export, with sockets blocked. Capture is tested end to end against the simulated recorder.

### M8 — Hardening, validation and 1.0 release

- **Packaging:** PyInstaller one-folder builds for Windows and Linux with pinned numba/llvmlite, hidden imports, writable `NUMBA_CACHE_DIR`, kernels pre-warmed on first launch; offline wheelhouse.
- **Desktop window:** the start command launches the local server, then opens it in a pywebview window (BSD-3-Clause). It uses the same React UI, so there is no second frontend.
  - **Windows** uses Edge WebView2. Air-gapped or older Windows 10 machines may lack its runtime, so the build bundles Microsoft's fixed-version WebView2 runtime instead of relying on an online install.
  - **Linux** uses the GTK backend (WebKit2GTK, LGPL, a system package). Never the Qt backend through PyQt, which is GPL.
  - With no usable webview, the start command says so and opens the default browser instead; `sanket --browser` does that on purpose.
  - The window allows only 127.0.0.1: any other navigation is refused, and it gets the same socket-blocked smoke test as the browser.
  - Closing the window stops the server, unless jobs are still running, in which case Sanket asks first.
- **Robustness:** wrong format and wrong sample rate deliberately; truncated, corrupt and NaN files; ≥ 4 GiB files; parser fuzzing for every container; malicious archives and profiles; a Canvas2D waterfall fallback for machines without WebGL2.
- **Security and accessibility:** security review (uploads, exports, subprocess use); axe clean; full keyboard pass.
- **Real-signal validation**, sourced in this legal order (Telecommunications Act 2023 §3 makes *possessing* a receiver an authorisation question):
  1. public licensed datasets (IQEngine/SigMF samples, ORACLE, DroneDetect; licence per file)
  2. remote public KiwiSDRs — **Indian NAVTEX** from the seven DGLL stations on 518/490 kHz is the primary Indian ground truth; also AIR shortwave, VOLMET, HFDL
  3. own RTL-SDR captures only under an institutional umbrella after checking with the organisers or WPC: ADS-B and AIS (CRC-verified), **Meteor-M LRPT** as the primary satellite target; NOAA APT and FM RDS only if confirmed on air in India

  Ground truth comes from a `bench/decoder_truth/` harness that runs reference decoders (readsb, AIS-catcher, rtl_433, multimon-ng, SatDump — GPL, so **subprocess only**; redsea is MIT) and keeps only CRC-passing frames. Real recordings of catalogued systems (NAVTEX, AIS, POCSAG, Meteor-M LRPT) must be VERIFIED by Sanket's Match stage and, where a reference decoder exists, agree with it frame by frame. AMC is fine-tuned on labelled real captures (e.g. CORAL) and reported before/after.
- **Head-to-head** against the leading public rival tools on the sealed bench where their licences allow, published neutrally including where they win.
- **Docs:** user guide, method notes per stage, a limits page, `bench/VALIDATION.md` with every number, script, seed and hardware spec.
- **Exit gate:** every row of §2 holds, and the release checklist in §6 is complete.

## 6. Quality system

**Tests, from fastest to slowest**

1. Unit tests against exact ground truth (bits in, exact values out), including failure and abstain cases.
2. Property-based tests (Hypothesis) for parsers, the GF(2) kernel and decoders.
3. Golden results: each bench file has a committed results JSON; any change is a reviewed diff.
4. Null-set run for false accepts (nightly).
5. Playwright E2E with networking blocked, plus axe checks.
6. Parser fuzzing (nightly).
7. `bench perf` with regression thresholds.
8. Frozen-build smoke test on both platforms.

**Definition of done** for any feature:

- [ ] Tested against known ground truth, including a failure case.
- [ ] Outputs carry an evidence level, confidence, method and evidence; UNKNOWN carries its reason.
- [ ] Limits written down in docstrings and in the user-facing text.
- [ ] `bench/` numbers updated; the README and any deck quote only those numbers.
- [ ] Visible and overridable in the GUI, following the §4 UI rules.
- [ ] Works with networking switched off.

**Release checklist (1.0)**

- [ ] All §2 rows green in CI on the release commit
- [ ] Sealed-bench and null-set results published in `bench/VALIDATION.md`
- [ ] Frozen builds pass the smoke test on a clean Windows and a clean Ubuntu machine
- [ ] `THIRD_PARTY.md` and the licence check up to date
- [ ] User guide and limits page reviewed against the shipped behaviour
- [ ] Version, results-schema version, profile-schema version, both catalogue versions and model hash tagged together

## 7. Versioning and compatibility

- Semantic versioning for Sanket. The results JSON carries `schema_version`; a breaking schema change is a major version.
- The FEC/interleaver catalogue, the known-system catalogue and the AMC model are versioned independently and recorded in every result, so any result can be reproduced.
- Profiles carry their own schema version and a version per edit. A profile saved by an older minor version must still import; a profile that references a catalogue entry that no longer exists is reported, not silently ignored.
- SQLite schema changes ship as migrations; the workspace from the previous minor version must open.
- A changelog entry for every user-visible change.

## 8. Risk register

| Risk | Mitigation |
|---|---|
| Blind FEC / de-interleaving is unsolved in general | Catalogue-bounded search; VERIFIED only with proof; publish the false-accept rate |
| No absolute sample rate or centre frequency in a headerless file | Ranked candidates, promoted only by structural matches; normalised units otherwise; assumptions on every output |
| AMC collapses at low SNR | Publish the curve; suppress labels outside the validated range |
| Synthetic-to-real domain gap | Impairment-rich generator; independent TorchSig tests; real-capture fine-tuning in M8 |
| Mono WAV mistaken for IQ | Channel count, quadrature check, HYPOTHESIS labels |
| Analog voice in real recordings mislabelled as a digital mode | Analog check before digital classification (M2); "analog" outcome in open-set rejection (M4) |
| GPL SDR drivers leaking into the product via capture | Drivers run only as subprocesses; licence check in CI |
| Analyst context is wrong | Entered values are still checked against the data; hints reorder the search but never skip it |
| A profile is applied to a signal it doesn't fit | Its values are checked on each recording; VERIFIED only from that recording's own proof; on failure, say so and run the blind chain |
| A known-system match is a coincidence | The system's own check must pass; every entry is counted with Holm correction; near-miss signals in the null set |
| Many containers multiply parser bugs | One chunked reader interface; round-trip tests and fuzzing per container |
| Lossy audio (MP3, Ogg) distorts the waveform | Accepted with a warning; digital labels capped at HYPOTHESIS |
| False matches from many code/interleaver guesses | Ledger of every hypothesis; Holm correction; L ≥ w + 30; shuffled-bit runs; ≥ 1,000-file null set |
| Pseudo-random interleaver with an unknown permutation | Standard-permutation catalogue; otherwise UNKNOWN with the measured period |
| A flat "95 % at 3 % BER" FEC target is unreachable for long codes | Per-family, soft-decision targets (STANDARDS §8) |
| Frozen Numba fails on Windows | Pinned numba/llvmlite, one-folder build, writable cache, frozen-build test in CI |
| WebView2 runtime missing on an air-gapped Windows machine, or no WebKit2GTK on Linux | Bundle the fixed-version WebView2 runtime; fall back to the default browser with a clear message; `sanket --browser` |
| No WebGL2 on a target machine | Clear message today; Canvas2D fallback over the same tiles in M8 |
| Huge files exceed GPU texture limits | Tiled pyramid with level of detail, never one texture per file |
| Receiver possession needs authorisation (Telecom Act 2023 §3) | Public datasets and remote KiwiSDRs first; own captures only under an institutional umbrella after checking. The capture feature states this in the UI, and the operator is responsible for it. |
| RadioML label/SNR flaws and non-commercial licence | Train on our generator; RadioML only as a corrected benchmark |
| NOAA APT / Indian RDS may not be on air | Meteor-M LRPT and NAVTEX as primary targets |
| TorchSig needs Linux and ~1 TB | WSL2; generate only needed subsets |
| LDPC matrix licences unclear | Matrices from published standards with a recorded source |
| GPL or unlicensed code leaking into the product | Licence check in CI; rival repos studied, never copied |
| Scope too broad for 1.0 | Milestone exit gates; FEC depth before UI polish; stretch items cut first |
| Gate-chasing stalls the build | A missed number is recorded as an Open gate ([§0](#0-progress)) rather than blocked on; every open gate closes by M8 |

## 9. External dates (SIH)

- **Idea submission: Tuesday 30 September 2026.** The deck draws on this plan: the problem, the §3 architecture, the §4 identity with screenshots of the workspace (labelled *synthetic demo data*), and the STANDARDS §9 competitive matrix with our column labelled as targets. The PS text is in [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md); confirm the submission template on sih.gov.in before submitting.
  - [x] Plan, standards to beat, source dossier and research report
  - [x] Workspace UI to screenshot, labelled *synthetic demo data*
  - [x] Official PS text, category and theme recorded in [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md)
  - [ ] Confirm the submission template on sih.gov.in
  - [ ] Re-run the rival scan ([STANDARDS §10](STANDARDS_TO_BEAT.md#10-how-to-refresh-this-document)); `gh` is logged in
  - [ ] Build the deck; every number traced to STANDARDS or labelled as a target
- **Grand finale:** date not yet announced; confirm on sih.gov.in. The finale demo is whatever state the milestones have reached, run from the offline build with networking switched off.
