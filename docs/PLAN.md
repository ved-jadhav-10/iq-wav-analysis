# Build plan — SIH26147

This plan runs from today (**Friday 26 September 2026**) to the grand finale. Phase 0 is the idea-submission sprint (deadline **Tuesday 30 September**). After that, the build phases are counted in weeks (**W1 = week of 1 October**) because the finale date hasn't been announced; confirm it on sih.gov.in.

Related: [README](../README.md) · [Standards to beat](STANDARDS_TO_BEAT.md) · [Claude Code tooling](CLAUDE_SKILLS_MCP.md) · [Dossier](../sih_analysis.md)

---

## Guiding rules

1. **Measure, don't claim.** Every number in the deck or README comes from a script in `bench/` that anyone can re-run.
2. **Ground truth before estimators.** Build the synthetic lab with known answers first; then build the stages it tests.
3. **No silent defaults.** An unknown format or sample rate becomes a stated assumption or an UNKNOWN, never a quiet guess.
4. **Streaming from day one.** Every reader and detector works on chunks, so multi-GB files never need a rewrite.
5. **Study rivals, write our own code.** Most rival repos have no licence. Every team member must be able to explain every module.

## Team roles (6 members)

| Role | Owns | Main phases |
|---|---|---|
| **R1 DSP lead** | Detection, estimation, sync, demodulation | 2, 4 |
| **R2 Coding lead** | Interleaver + FEC catalogue, blind identification, framing | 5, 6 |
| **R3 ML lead** | Datasets, AMC training and evaluation, ONNX export, calibration | 1 (data), 3 |
| **R4 Platform lead** | Ingestion, evidence model, FastAPI, jobs, storage, exports, offline packaging, CI | 1, 7 |
| **R5 Frontend lead** | React/TS app, WebGL waterfall, constellation, eye, evidence and hypothesis UX | 7 |
| **R6 Validation & pitch lead** | Benchmark and null set, real captures, rival head-to-head, deck, judge drills | 0, 1 (bench), 8, 9 |

Pair across roles for review: R1↔R2 (bits handoff), R3↔R1 (features), R4↔R5 (API contract).

---

## Phase 0 — Idea-submission sprint (26–30 Sep)

**Goal:** a submitted idea deck that is honest, specific and visibly better informed than the rest of the field, backed by a small working proof of concept for screenshots.

| Day | Tasks | Owner |
|---|---|---|
| **Fri 26 Sep** | Confirm PS text, theme, template and submission format on sih.gov.in; register the team; pick a product name. Install Python 3.12 + uv; `gh auth login`. Scaffold the repo (`dsp/`, `backend/`, `frontend/`, `bench/`). | R6, R4 |
| **Sat 27 Sep** | PoC ingestion: SigMF, raw cf32/ci16 with explicit rate, stereo/mono WAV with an assumptions printout. PoC plots: waterfall + PSD + constellation (matplotlib is fine). Draft the deck outline. | R4, R1, R6 |
| **Sun 28 Sep** | PoC ground truth: generate BPSK/QPSK with known bits and a CRC-16 frame → demodulate → BER = 0 → CRC passes. Architecture diagram. Competitive-matrix slide from [STANDARDS §9](STANDARDS_TO_BEAT.md#9-competitive-matrix--draft-for-the-idea-deck). | R1, R2, R5 |
| **Mon 29 Sep** | Finish the deck. Internal review: can we answer all six §B7 judge questions? Remove any claim `bench/` can't reproduce. | All |
| **Tue 30 Sep** | Submit **in the morning**. Portals slow down near deadlines. Keep a PDF copy. | R6 |

### Deck outline

This follows the usual six-slide SIH idea template; confirm the exact template on the portal.

1. **Title:** team, PS ID SIH26147, product name.
2. **Idea:** the problem in one line. The India case:
   - 1,951 GPS-interference incidents (Nov 2023 – Nov 2025)
   - 12–18 person-hours to isolate one signal manually
   - Krypto500 costs about US$7,400 and is ITAR-controlled

   Then our solution and what's different: evidence levels, verified decodes, a web GUI that runs air-gapped.
3. **Technical approach:** pipeline diagram, stack, evidence levels, PoC screenshots (waterfall, constellation, CRC-verified decode).
4. **Feasibility & viability:** honest limits, phased scope, CPU-only offline deployment, risk table (from §B4).
5. **Impact & benefits:**
   - audiences: NTRO, WMO/WPC (28 monitoring stations), DGCA, DoT/TRAI, ISRO, NDRF, academia
   - Atmanirbhar Bharat and import substitution
   - SDGs 9.1, 9.c, 16.4, 16.a, 17.8
6. **Research & references:** key papers and datasets, plus the **competitive matrix** naming the leading public rivals and our targets (labelled as targets).

**PoC exit criteria:**
- one synthetic QPSK SigMF file goes through ingest → waterfall → constellation → bits → CRC pass
- the same file loaded as headerless `.iq` with no rate given produces an explicit "sample rate unknown" message, not a default

**Submission checklist:**
- [ ] PS details re-verified on the portal on 29 or 30 Sep
- [ ] All figures sourced from the dossier or `bench/`
- [ ] Every rival named in the deck re-checked within 24 hours
- [ ] Team details complete; deck exported to the required format
- [ ] Submitted, with the confirmation saved

---

## Build phases (after submission)

| Phase | Weeks | Goal | Exit criterion (measured in `bench/`) |
|---|---|---|---|
| 1 Foundations | W1–W2 | Repo, CI, ingestion, evidence model, ground-truth lab, bench v0 | Round-trip tests for every format; bench v0 + null set generated; CI green |
| 2 DSP core | W2–W4 | Detection, estimation, sync | Estimator error targets met per SNR bucket |
| 3 AMC | W3–W6 | Rules + CNN, fusion, ONNX | AMC targets met on public and in-scope sets |
| 4 Demodulation | W4–W6 | PSK/QAM/FSK to soft bits | BER within 1 dB of theory on AWGN |
| 5 Interleaver + FEC | W5–W9 | Blind catalogue search with verification | FEC-ID ≥ 95%; **0 false accepts on ≥ 1,000 null files** |
| 6 Framing | W7–W9 | Sync discovery, frame length, header fields | Blind sync false alarm ≤ 10⁻⁶ |
| 7 GUI + API | W2–W10 | Web app, analyst-in-the-loop, exports, offline bundle | Playwright E2E passes with networking off |
| 8 Validation | W8–W11 | Real captures, scale tests, head-to-head | Validation report published in `bench/` |
| 9 Finale prep | Final 2 weeks | Freeze, rehearse, fallback plans | Demo runs clean three times in a row on the finale laptop |

The numeric targets are in [STANDARDS §8](STANDARDS_TO_BEAT.md#8-our-bar--measurable-targets).

### Phase 1 — Foundations (W1–W2) · R4, R3, R6

- **Monorepo and CI:**
  - uv workspace for `dsp/`, `ml/`, `backend/`
  - Vite + React + TS in `frontend/`
  - GitHub Actions: ruff, pyright, pytest, `tsc`, ESLint, Vitest
  - pre-commit hooks
- **Evidence model:** `Parameter{value, unit, level, confidence, method, evidence[], alternatives[], warnings[]}`, shared by every stage and the API schema. Levels: VERIFIED / MEASURED / ESTIMATED / HYPOTHESIS / UNKNOWN.
- **Ingestion:**
  - the full SigMF `core:datatype` vocabulary
  - raw cf32/ci16/ci8/cu8, LE/BE, IQ/QI order
  - WAV mono (analytic signal, flagged) and stereo (quadrature check plus an analyst prompt)
  - memory-mapped chunked reader
  - format *sniffer* that proposes ranked candidates but never picks silently
  - an `Assumptions` block in every output
- **Ground-truth lab:**
  - NumPy generator: modulation × pulse shape × FEC × interleaver × framing with CRC, writing SigMF with the truth stored as annotations
  - TorchSig 2.x corpus built in WSL2
  - impairment harness: AWGN, CFO, phase noise, IQ imbalance, multipath, timing drift, clipping
- **Bench v0:**
  - fixed seeds
  - a **sealed** held-out set that is never inspected during development
  - a **null set** (noise, uncoded random bits, repetition patterns, idle patterns) to measure false accepts
  - `bench run` writes a versioned results JSON

### Phase 2 — DSP core (W2–W4) · R1

- **Detection:**
  - streaming Welch PSD and spectrogram
  - robust noise floor
  - CFAR-style threshold + hysteresis + connected components → multiple signals in time **and** frequency
  - channelisation: mix, filter, decimate
- **Estimators:**
  - occupied bandwidth
  - SNR (M2M4 + spectral, with correct units)
  - symbol rate (cyclostationary / Oerder-Meyr, ranked by harmonic comb)
  - CFO (M-th power, gated for QAM)
  - cumulants C20, C40, C42
- **Sync:**
  - RRC matched filter
  - Gardner / Mueller-Müller timing with a Farrow interpolator
  - Costas loop, plus decision-directed tracking for QAM
  - FSK discriminator averaged over each symbol interior
- **Detect FM first:** check whether the signal is FM carrying audio before any digital classification (a lesson from sigma).

### Phase 3 — Modulation classification (W3–W6) · R3

- **Explainable baseline:** cumulant and spectral-line rules. Each decision lists its evidence.
- **CNN:**
  - small ResNet/CNN on raw IQ (O'Shea-style)
  - trained on RadioML 2018.01A plus TorchSig-generated in-scope classes, with an explicit noise/unknown class
  - temperature calibration applied **only if** expected calibration error improves
- **Fusion:** agreement → ESTIMATED; disagreement → HYPOTHESIS showing both rankings.
- **Deployment:** export to ONNX; CPU inference with onnxruntime; model identity (hash, data, metrics) pinned in `ml/MODEL_CARD.md`.
- **Evaluation:**
  - accuracy vs SNR from −20 to +30 dB
  - confusion matrices and reliability diagrams
  - run on data we **did not generate** (RadioML, HisarMod, Sig53) as well as our own

### Phase 4 — Demodulation to bits (W4–W6) · R1

- **Modulations:**
  - BPSK, QPSK, 8PSK, 16/64-QAM, 2/4/8-FSK
  - stretch: MSK/GMSK, OQPSK, π/4-DQPSK
- **Bit mapping:** Gray demapping; soft outputs (LLRs); EVM and lock metrics.
- **Phase ambiguity:** carry the rotated or inverted candidates forward. The FEC and sync stages resolve them; this stage never forces a pick.

### Phase 5 — De-interleaving + FEC (W5–W9) · R2 · *the core differentiator*

- **Catalogue** (versioned YAML, licence-checked):
  - convolutional codes K=3–9 at rates ½ and ⅓, with CCSDS / DVB / 802.11 punctures
  - RS(255,223) CCSDS, RS(204,188) DVB, and shortened variants
  - concatenated RS + conv with a byte interleaver
  - LDPC: CCSDS, DVB-S2 short frames, 802.11n, 5G NR base-graph subsets
- **Blind identification:**
  - conv codes from dual-code parity checks / GF(2) rank
  - RS by syndrome at each alignment
  - LDPC by H·c syndrome at each alignment
- **Interleavers:**
  - block and diagonal via stride/rank scans
  - convolutional via delay structure
  - pseudo-random: search known PRNG families over a bounded seed range, otherwise UNKNOWN with measured bounds
- **Search engine:**
  - coarse-to-fine pruning with cheap syndrome screening before full decodes
  - **every hypothesis is counted**; the acceptance threshold is Holm/Bonferroni-corrected
  - VERIFIED requires a CRC pass, sync recurrence, or a re-encode BER consistent with EVM
- **Performance:** Numba-JIT Viterbi and normalised min-sum LDPC. Profile with `bench perf`.

### Phase 6 — Framing (W7–W9) · R2

- **Sync words:** a known-sync library (CCSDS ASM, Barker codes, POCSAG, etc.), plus blind sync discovery using a significance test against control words.
- **Frame structure:** frame length from autocorrelation; header fields (constant bits, frame counters with a significance test); CRC-16/32 checks.
- **Output:** frame table with header/payload split, exportable as bits, hex and JSON.

### Phase 7 — GUI + API (W2–W10, continuous) · R4, R5

- **API:**
  - chunked upload
  - job runner with SSE progress
  - stage-graph endpoints
  - `POST /override` (analyst correction → downstream re-run)
  - exports: JSON, CSV, PDF, SigMF
  - literal routes registered before parameterised ones
- **Frontend:**
  - WebGL2 waterfall with zoom, pan and detection boxes
  - constellation (density-shaded), eye diagram, PSD
  - stage timeline with evidence cards
  - **hypothesis table** showing how many guesses were tried, the corrected threshold and each rejection reason
  - bitstream/frame viewer, batch view, compare view
- **Analyst-in-the-loop:** change any stage's decision → later stages re-run → a before/after diff is shown.
- **Offline bundle:**
  - FastAPI serves the built SPA; no CDN; bundled fonts; offline wheelhouse
  - one start command on Windows and Linux
  - a CI test that blocks sockets and runs the whole E2E suite

### Phase 8 — Validation (W8–W11) · R6, all

- **Real captures** (receive-only, lawful), each stored as SigMF with provenance and licence:
  - FM broadcast: 19 kHz pilot, 57 kHz RDS → decode PI/PS
  - ADS-B at 1090 MHz: CRC-verified
  - AIS at 162 MHz: CRC-verified
  - NOAA APT / Meteor-M LRPT passes over India
  - HF NAVTEX / RTTY / time signals via public KiwiSDR receivers, including Indian receivers where available
- **Robustness:**
  - deliberately wrong format and sample rate
  - truncated, corrupt and NaN files
  - files ≥ 4 GiB
  - fuzzing the parsers
- **Head-to-head:** run the leading public rival tools on our sealed bench where their licences allow it. Publish the results neutrally, including where they beat us.
- **Report:** `bench/VALIDATION.md` with every number, script, seed and hardware spec.

### Phase 9 — Finale prep (final 2 weeks) · all

- Code freeze 7 days before the finale; bug fixes only.
- Rehearse the §B7 judge questions, each answered with a live demo:
  1. no metadata
  2. how do you know it's correct
  3. accuracy at 0 dB
  4. two overlapping signals
  5. pseudo-random interleaver
  6. networking off
- Demo script: a 5-minute version and a 15-minute version. Keep a recorded fallback video and a second laptop with an identical offline bundle.
- Every member can explain every module; hold a cross-quiz session.

---

## Risk register

| Risk | Type | Mitigation |
|---|---|---|
| A rival already matches our headline feature | Competitive | Lead with the differentiators D1–D8 in [STANDARDS §7](STANDARDS_TO_BEAT.md#7-table-stakes-vs-open-differentiators); re-scan before every pitch |
| Blind FEC / de-interleaving is unsolved in general | Technical | Catalogue-bounded search; VERIFIED only with proof; publish the false-accept rate |
| No absolute sample rate or centre frequency from IQ | Data | Require SigMF or analyst input; estimate relative quantities; print assumptions |
| AMC collapses at low SNR | Performance | Publish the curve; suppress labels outside the validated range |
| Domain gap between synthetic and real signals | Data | TorchSig impairments + real captures in Phase 8; evaluate on external datasets |
| Mono WAV mistaken for IQ | Data | Detect channel count; quadrature check; HYPOTHESIS labels |
| False matches from many FEC and interleaver guesses | Technical | Count hypotheses; Holm/Bonferroni correction; null set with ≥ 1,000 files |
| Pseudo-random interleaver with unknown seed | Technical | Bounded seed search; otherwise UNKNOWN with bounds |
| Scope too broad | Scope | Phases have exit criteria; FEC depth before UI polish; cut stretch modulations first |
| TorchSig needs Linux | Tooling | WSL2 Ubuntu 22.04+; pre-generate datasets offline |
| Python not installed on the main dev machine | Tooling | Install Python 3.12 + uv on day 1 (Phase 0) |
| LDPC matrix licences unclear | Legal | Use matrices from published standards with a recorded source; download on request, as sigma does |
| Looks copied from public repos | Scope / legal | Own code only; credit libraries; cross-quiz |
| Legal sensitivity of interception | Legal | Offline file analysis only; lawful-use notice; provenance in SigMF |
| Finale connectivity not guaranteed | Operational | Offline bundle, datasets and weights pre-staged; fallback video |

## Definition of done

A feature is done only when **all** of these are true:
- [ ] It is tested against known ground truth (exact bits or values in, exact expected out), including a failure case.
- [ ] Its outputs carry an evidence level, confidence, method and evidence.
- [ ] Its limits are written down, both in code docstrings and in the user-facing text.
- [ ] Its `bench/` numbers are updated, and the README or deck quotes only those numbers.
- [ ] It is visible and overridable in the GUI.
- [ ] It works with networking switched off.
