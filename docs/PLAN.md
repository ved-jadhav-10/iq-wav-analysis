# Build plan — SIH26147

This plan runs from today (**Friday 26 September 2026**) to the grand finale. Phase 0 is the idea-submission sprint (deadline **Tuesday 30 September**). After that, the build phases are counted in weeks (**W1 = week of 1 October**) because the finale date hasn't been announced; confirm it on sih.gov.in.

Related: [README](../README.md) · [Standards to beat](STANDARDS_TO_BEAT.md) · [Claude Code tooling](CLAUDE_SKILLS_MCP.md) · [Dossier](sih_analysis.md)

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
| 5 Interleaver + FEC | W5–W9 | Blind catalogue search with verification | Per-family FEC-ID targets met (STANDARDS §8); **0 false accepts on ≥ 1,000 null files** |
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
  - format *sniffer* that proposes ranked candidates but never picks silently. No existing tool infers raw formats, so we build it:
    - detect headers (WAV/SigMF, byte-entropy)
    - score every datatype × endianness reading by NaN/denormal rate, spectral flatness, lag-1 autocorrelation and I/Q balance
    - check file size against datatype width
    - I/Q vs Q/I stays an analyst toggle, because a swap only mirrors the spectrum
    - tested with a confusion matrix over every format combination
  - **sample-rate candidates, ranked:** filename hints, the WAV `auxi` chunk, standard SDR device rates (RTL-SDR, HackRF, etc.) and matches to known standards. With no candidate, output in normalised units.
  - an `Assumptions` block in every output
- **Ground-truth lab:**
  - NumPy generator (our main training source): modulation × pulse shape × FEC × interleaver × framing with CRC, writing SigMF with the truth stored as annotations. Add a Sig53-style impairment list, ±10–20% samples-per-symbol jitter and an explicit noise class.
  - TorchSig corpus built in WSL2 as an **independent** test generator. Budget up to about 1 TB of disk; generate only the subsets we need.
  - impairment harness: AWGN, CFO, phase noise, IQ imbalance, multipath, timing drift, clipping
- **Bench v0:**
  - fixed seeds
  - a **sealed** held-out set that is never inspected during development
  - a **null set** (noise, uncoded random bits, repetition patterns, idle patterns) to measure false accepts
  - `bench run` writes a versioned results JSON

### Phase 2 — DSP core (W2–W4) · R1

- **Detection:**
  - streaming Welch PSD and spectrogram
  - percentile noise floor
  - OS-CFAR threshold + hysteresis + morphological clean-up + `scipy.ndimage.label` → multiple signals in time **and** frequency
  - run at 2–3 FFT sizes and merge the boxes with non-maximum suppression, to catch both short bursts and narrow carriers
  - channelisation: mix, filter, decimate
  - *stretch:* cluster detections with DBSCAN to find frequency hoppers (hop set, dwell time). Detect co-channel overlap from multiple cyclic lines and an MDL source count; separate only easy cases, by filtering or SIC. Optional YOLO detector via ONNX as a cross-check (check Ultralytics' licence first).
- **Estimators:**
  - occupied bandwidth; RRC roll-off by least-squares fit of the theoretical PSD
  - SNR from three estimators (in-band PSD, M2M4 for PSK, eigenvalue/MDL); their agreement sets the confidence. EVM only after a successful demodulation.
  - symbol rate: FFT of |x|² spectral line (x² for BPSK, x⁴ for QPSK), refined with cyclic autocorrelation and confirmed with our own NumPy/Numba FAM/SSCA; ranked by harmonic comb. FSK uses instantaneous frequency. At low roll-off, fall back to occupied bandwidth.
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
  - a **tiny complex-as-real 1-D CNN (about 10K parameters, ULCNN/LDCVNN style)**. Published models this size match a 406K-parameter MCLDNN on RadioML (about 60% averaged over SNR, 92–96% peak).
  - input [I, Q, |x|, Δφ], power-normalised, after estimating symbol rate and CFO and resampling to a fixed 4 or 8 samples per symbol
  - cumulant features fused before the classifier head. Cumulants separate 16QAM from 64QAM poorly, so the CNN carries that case.
  - trained mainly on **our own impaired generator** (frequency/phase/timing offsets, rate jitter, Rayleigh/Rician fading, IQ imbalance, phase noise), with an explicit noise class
  - temperature calibration applied **only if** expected calibration error improves
- **Open-set rejection, in three layers:** SNR gate → energy score → Mahalanobis distance to class prototypes with per-class thresholds. Logits are averaged over several windows.
- **Fusion:** agreement → ESTIMATED; disagreement → HYPOTHESIS showing both rankings.
- **Deployment:**
  - export to ONNX, keep FP32 logits, no FFT/atan2 inside the graph
  - if quantising, use static QDQ for the CNN and re-fit temperature and rejection thresholds afterwards
  - model identity (hash, data, metrics) pinned in `ml/MODEL_CARD.md`
- **Evaluation:**
  - accuracy vs SNR from −20 to +30 dB, with confusion matrices and reliability diagrams
  - open-set metrics per SNR bin with modulations held out as unknowns: AUROC, FPR@95%TPR, OSCR
  - run on data we **did not generate** (TorchSig, HisarMod, RadioML with corrected labels) as well as our own
  - RadioML flaws to correct and state: SNR labels are off by tens of dB, AM-SSB in 2016.10a is noise, the 2018.01A class-name mapping is wrong, and it is licensed non-commercial
  - a sim-to-real test: models can drop from about 96% to 35% on real captures, so fine-tune (e.g. CORAL) on labelled real recordings from Phase 8

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
- **Build the GF(2) kernel first (W5):**
  - one bit-packed, Numba-JIT Gaussian-elimination routine (GJETP) is the shared engine for code length, sync offset, puncturing pattern, parity-check recovery and interleaver period
  - variants: soft GJETP (rows ordered by LLR reliability), rank iteration (repeat elimination for noise tolerance), dual-code parity-check search (Marazin/Gautier/Burel)
  - **no public implementation of these methods exists**, so a working, benchmarked one is differentiator D9
- **Blind identification by code family:**
  - **convolutional:** dual-code parity checks via the kernel; punctured codes via Marazin's two-stage method (equivalent encoder, then mother code + puncturing pattern); catalogue scoring by the probability that parity checks hold, computed from LLRs (Moosavi–Larsson)
  - **RS:** a binary rank scan finds the codeword length in bits and the alignment. Then a Galois-field Fourier transform over 16 primitive polynomials × symbol offsets, plus the CCSDS dual-basis variant, shows a run of consecutive zeros: its length is n−k and its start is the first root. Uses `galois`.
  - **LDPC:** soft syndrome scoring against the standard-matrix catalogue. Rebuilding a sparse H from scratch is a stretch goal.
  - **concatenated:** identify and decode the inner conv code, then search the Forney interleaver, then run the RS pipeline
  - *optional:* a gradient-boosted or small-CNN code-family pre-classifier. Deep-learning papers only pick among trained classes and can't recover parameters.
- **Interleavers:**
  - block: rank-drop criterion (Sicot/Houcke/Barbier) for the period; the largest rank drop gives the sync; a Kolmogorov–Smirnov test on rank distributions for low-SNR confirmation
  - convolutional (Forney): a small (I, J, phase) grid search using the kernel
  - diagonal/helical: period, row/column and codeword-length estimator (2012/2015 methods)
  - pseudo-random: test a catalogue of **standard permutations** (3GPP turbo, LTE QPP, 802.11, DVB-S2); anything else is UNKNOWN with its measured period. No generic seed search.
- **Search engine and false-alarm control:**
  - coarse-to-fine pruning with cheap syndrome screening before full decodes
  - **every hypothesis is counted**; binomial-tail p-values with Holm/Bonferroni (or Benjamini–Hochberg) across the whole catalogue
  - rank matrices always have L ≥ w + 30 rows
  - every detector also runs on **shuffled bits** to measure its empirical false-alarm rate, shown in the GUI hypothesis table
  - VERIFIED requires a CRC pass, sync recurrence, or a re-encode BER consistent with EVM
- **Targets are set per code family and use soft decisions** (see [STANDARDS §8](STANDARDS_TO_BEAT.md#8-our-bar--measurable-targets)). Hard-decision rank methods can't tolerate a flat 3% BER on long codes.
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
  - study and borrow components from IQEngine (MIT: React/TS + FastAPI + SigMF, with its own `webfft` package)
  - waterfall from a server-side **tiled STFT pyramid** (uint8 dB tiles, level of detail), drawn as WebGL2 R8 textures with a colormap lookup in the shader, via deck.gl TileLayer or regl. Contrast and colormap changes need no re-fetch. Zoom, pan and detection boxes.
  - PSD and time plots in uPlot with min/max decimation per pixel
  - constellation: additive-blended WebGL scatter for small captures; a server-side `histogram2d` shown as a log-density texture for large ones. Eye diagram.
  - stage timeline with evidence cards
  - **hypothesis table** showing how many guesses were tried, the corrected threshold and each rejection reason
  - bitstream/frame viewer, batch view, compare view
- **Analyst-in-the-loop:** change any stage's decision → later stages re-run → a before/after diff is shown.
- **Offline bundle:**
  - FastAPI serves the built SPA; no CDN; bundled fonts; offline wheelhouse
  - PyInstaller **one-folder** build with a pinned Numba/llvmlite and `NUMBA_CACHE_DIR` set to a writable directory. Frozen Numba has known Windows failures (missing `numba.core.*`, WinError 126), so test the frozen build in CI. Check for WebView2 and MSVC runtimes if we wrap it with pywebview or Tauri.
  - one start command on Windows and Linux
  - a CI test that blocks sockets and runs the whole E2E suite

### Phase 8 — Validation (W8–W11) · R6, all

- **Legal order of sources** (see the README "Lawful use" section; Telecom Act 2023 §3 makes *possessing* a receiver an authorisation question):
  1. public licensed datasets
  2. remote public KiwiSDRs
  3. our own RTL-SDR captures, only under the college's umbrella and after checking with the organisers or WPC
- **Ground truth comes from our own `decoder-truth` harness.** No public dataset pairs IQ with checksum-verified decodes. Record, run a reference decoder as a *subprocess*, and store frames that pass their CRC as SigMF annotations. Decoders:
  - readsb (ADS-B), AIS-catcher, rtl_433, multimon-ng, SatDump: all GPL, so never linked into the product
  - redsea (RDS): MIT
- **Real recordings, each stored as SigMF with provenance and licence:**
  - **Indian NAVTEX (primary Indian ground truth):** 7 DGLL stations on 518 kHz (English) and 490 kHz (regional languages), each with a known ID letter and a fixed 4-hourly schedule. Record via public KiwiSDRs in Bangalore with `kiwirecorder.py -m iq --kiwi-wav`, which adds GPS timestamps. KiwiSDR bandwidth is about 12–20 kHz, so it suits HF only.
  - Other Indian HF: AIR shortwave, VOLMET, HFDL, ham RTTY/PSK31/FT8
  - ADS-B at 1090 MHz near airports and AIS at 162 MHz in coastal cities: CRC-verified
  - **Meteor-M LRPT** as the main satellite target. **NOAA APT and FM RDS are conditional**: confirm the satellites are still transmitting in 2026 and that Indian FM stations broadcast RDS.
  - Public sets for breadth: ORACLE (SigMF; note its data is actually complex128), DroneDetect, IQEngine/SigMF samples (licence per file)
  - Contribute our CC-BY captures to LakeShark-Signal-Corpus (currently empty)
- **Hardware:** RTL-SDR Blog V4, about ₹6,000 from Robu, ElectroPi or Fab.to.Lab. Check stock; one source says it has been discontinued.
- **Sim-to-real:** fine-tune AMC on labelled real captures (Phase 3) and report before/after numbers.
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
| Pseudo-random interleaver with unknown permutation | Technical | Catalogue of standard permutations (3GPP, LTE QPP, 802.11, DVB-S2); otherwise UNKNOWN with the measured period. No generic seed-search claim. |
| Flat "95% at 3% BER" FEC target is mathematically unreachable for long codes | Credibility | Per-family, soft-decision targets (STANDARDS §8) |
| Receiver possession needs authorisation (Telecom Act 2023 §3) | Legal | Public datasets and remote KiwiSDRs first; own captures only under the college umbrella after checking with organisers or WPC |
| RadioML label/SNR flaws and non-commercial licence | Data / legal | Train on our own generator; use RadioML only as a benchmark, with corrected labels |
| Frozen Numba fails on Windows | Tooling | Pin Numba; PyInstaller one-folder; `NUMBA_CACHE_DIR`; test the frozen build in CI |
| NOAA APT / Indian RDS may not be on air | Data | Meteor-M LRPT and NAVTEX as primary targets; APT and RDS conditional |
| Scope too broad | Scope | Phases have exit criteria; FEC depth before UI polish; cut stretch modulations first |
| TorchSig needs Linux | Tooling | WSL2 Ubuntu 22.04+; pre-generate datasets offline (up to about 1 TB, so generate only needed subsets) |
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
