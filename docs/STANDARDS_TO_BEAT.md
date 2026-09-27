# Standards to beat — SIH26147

This document sets the bar our tool has to clear. It covers commercial products, open-source tools, published research, and every public SIH26147 repository we could find.

- **Snapshot date:** 26 September 2026. The field moves daily, so re-run the scan before any pitch (see [§10](#10-how-to-refresh-this-document)).
- **How it was verified:** repository metadata (created, last push, licence) came from the GitHub REST API. Capabilities were checked against each repo's **file tree** and its **README**. We did not clone or run rival code.
- **Source dossier:** [`SIHPS_ANALYSIS.md`](SIHPS_ANALYSIS.md) §B1–B7. Where this document disagrees with the dossier, this document is newer (see [§5.5](#55-corrections-to-the-dossier-b6f)).

**Legend:** ✅ backed by code in the repo tree · 📄 README claim, not traced to code · ❌ not found · — not applicable.

---

## 1. Summary — what the bar looks like now

1. **There are 35 live SIH26147 repos, not the "14+" the dossier counted.** About 26 contain real code. Two named repos are gone or were misattributed.
2. **Real off-air validation is no longer a differentiator.** `SumitKumar00113/sigma-signal-analysis` decodes real NAVTEX, RTTY, RS41 radiosonde and NOAA APT recordings. `SomeNobody21112/ICHNOVA` decodes WWV, DCF77, MSF, JJY, DDH47 and All India Radio carriers received through KiwiSDR.
3. **The technical leader is `sigma-signal-analysis`**, a PySide6 desktop app. It covers 18 modulations and blindly identifies:
   - convolutional codes from K=3 to 9, including punctured codes
   - Reed-Solomon parameters
   - LDPC codes from a standards catalogue (DVB-S2, 5G NR, CCSDS)
   - interleavers, including a pseudo-random seed search
   - sync words, using a Poisson test

   The dossier's one-line summary badly underrates it.
4. **The rigour leader is `ICHNOVA`.** It runs a sealed benchmark with **0 false accepts**, corrects for multiple tests, keeps a SHA-256 decision receipt chain, and documents its limits honestly. It covers only BPSK/QPSK with convolutional codes and a block interleaver.
5. **Honesty labels, SigMF ingestion, four interleaver types, Viterbi + RS, and CRC/sync/re-encode checks are now table stakes.** At least 8 repos have them.
6. **Verified gaps nobody fills yet:**
   - a deep-learning AMC model evaluated on **public** datasets with a full accuracy-vs-SNR curve
   - a **web** GUI with sigma-level decoding depth
   - a sealed benchmark that compares rivals **head-to-head**
   - **committed, licensed Indian over-the-air recordings**
   - automatic downstream re-runs after an analyst correction
   - multi-GB streaming through the **whole** chain, not just detection
   - overlapping co-channel and frequency-hopping signals

   Details are in [§7](#7-table-stakes-vs-open-differentiators).
7. **Overclaiming exists and judges will spot it.** One repo shows a "SIH 2026 Finalist" badge before any finale was held. It also claims ">95% accuracy at −10 dB SNR" but ships no model files and has 2 test files. Our deck must never make a claim that the `bench/` scripts cannot reproduce.

---

## 2. Commercial incumbents

Source: dossier §B1, §B4. Only two prices are public.

| Product | Maker | Price | Constraints |
|---|---|---|---|
| Krypto500 / Krypto1000 | COMINT Consulting | Krypto500 about **US$7,400** | ITAR-controlled; no trial or light version |
| W-CODE | Wavecom (Switzerland) | Entry level about **US$995** (reseller-listed) | Commercial licence |
| go2DECODE / go2MONITOR | PROCITEC (Germany) | Quotation only | Export-controlled |
| GX430 | Rohde & Schwarz (Germany) | Quotation only | Export-controlled |
| Decodio | Decodio (Switzerland) | Quotation only | — |

**Our angle:** open, indigenous, air-gapped, SigMF-native, and ground-truth verified. None of these products is all of those at once (dossier §B6e). We will not claim to match their protocol libraries. We claim **transparent evidence** and **no licence or ITAR lock-in**.

---

## 3. Open-source prior art

These are tools to learn from or build on. Star counts and pushes are as of 26 Sep 2026.

| Tool | What it is | Licence | Relevance to us |
|---|---|---|---|
| [GNU Radio](https://www.gnuradio.org/) | Signal-processing flowgraph toolkit | GPL-3.0 | Synthetic data generation and reference receivers. **Dev-time only**: don't link GPL code into the product. |
| [TorchSig](https://github.com/TorchDSP/torchsig) (★376, pushed 2 Sep) | PyTorch RF-ML toolkit: 57 modulation variants, impairments, Sig53 / WidebandSig53 | MIT | AMC training data. **Needs Ubuntu ≥ 22.04**, so use WSL2 on Windows. |
| [IQEngine](https://github.com/IQEngine/IQEngine) (★332) | Web SDR toolkit for viewing and annotating recordings: React/TS client, FastAPI backend, SigMF, its own `webfft` package | MIT | **Closest match to our architecture.** Borrow components rather than start from scratch. Pinpoint studied it too. |
| OpenWebRX | Web SDR receiver UI | **AGPL-3.0** | UX reference only |
| [SigMF](https://github.com/sigmf/SigMF) (★466) + `sigmf` Python package | Metadata standard for recordings | Spec CC-BY-SA-4.0 | Native input/output format |
| gr-spectrumdetect | YOLOv8 wideband detector trained with TorchSig, inside GNU Radio | — | Reference for wideband detection |
| Inspectrum, Universal Radio Hacker (URH) | Manual IQ inspection and protocol analysis | GPL | Cross-checking our results by hand |
| liquid-dsp, AFF3CT | C/C++ DSP and FEC libraries | MIT | Performance references. Rivals found them hard to install on Windows. |
| [galois](https://github.com/mhostetter/galois) 0.4.11 | Finite fields (Numba), BCH and RS codes | MIT | **Primary GF/RS dependency.** Makes the RS Galois-field Fourier test straightforward. |
| scikit-commpy 0.8.0, reedsolo 1.7.0, pyldpc 0.7.9 | Python FEC | BSD-3 / public domain / MIT | commpy (last release 2022) and pyldpc (2020) are stale: vendor the functions we need; don't depend on them. **Known pitfalls are in [§6](#6-engineering-lessons-from-rivals-free-bug-reports).** |
| komm 0.34.0 | Most active Python comms toolbox | **GPL-3.0** | Reference only; keep out of the product |
| [PySDR](https://pysdr.org) | Free IQ/DSP textbook with code examples (FSM/TSM/FAM, etc.) | **CC BY-NC-SA** | Onboarding and method reference; don't copy its code into the product |
| Sionna 2.1 | NVIDIA link-level simulator, now on PyTorch | Apache-2.0 | Too heavy for an air-gapped CPU install |
| onnxruntime 1.30, numba 0.67, sigmf 1.13 | Inference, JIT, metadata | MIT / BSD / LGPL | All have Windows wheels; numpy 2.5 needs Python 3.12+ |
| Reference decoders: readsb, AIS-catcher, rtl_433, multimon-ng, SatDump; redsea | Ground-truth decoders for real captures | GPL; redsea MIT | Run as subprocesses in the test harness only |

---

## 4. Academic AMC benchmarks

Source: dossier §B3, §B6a.

| Model / paper | Dataset | Reported accuracy |
|---|---|---|
| O'Shea, Roy & Clancy, IEEE JSTSP 2018 (ResNet) | RadioML 2018.01A (24 classes, −20 to +30 dB, 2.56 M examples) | About 95% at high SNR, about 90% at around 6 dB, collapsing below −6 dB |
| AMC-Transformer | RadioML 2018.01A | 98.8% at SNR ≥ 10 dB |
| MobileRaT (MDPI *Drones* 7(10):596, 2023) | RadioML 2018.01A | 98.4% peak (+18 dB), **65.9% averaged over all SNRs** |
| Harper, Thornton & Larson (MDPI *Electronics* 12:3962, 2023) | RadioML 2018.01A | 98.9% peak, **63.7% overall** |

**Takeaway:** at high SNR, AMC is close to solved. The all-SNR average (around 64–66%) and behaviour below 0 dB are what separate honest work from marketing.

---

## 5. SIH26147 rival repositories

### 5.1 Capability matrix — the eight leaders

| | [sigma](https://github.com/SumitKumar00113/sigma-signal-analysis) | [ICHNOVA](https://github.com/SomeNobody21112/ICHNOVA) | [Devansh-567](https://github.com/Devansh-567/hackathon) | [Team Vertex](https://github.com/Gururaghavendra123/sihps2-2026) | [RadioFry](https://github.com/The-4Script/RadioFry) | [arachknight66](https://github.com/arachknight66/SIH26147) | [Pinpoint](https://github.com/pranshu1141-sharma/Pinpoint) | [SignalScope](https://github.com/Manas-Dikshit/SignalScope) |
|---|---|---|---|---|---|---|---|---|
| Last push | 26 Sep | 25 Sep | 17 Sep | 18 Sep | 25 Sep | 22 Sep | 26 Sep | 19 Sep |
| GUI | PySide6 desktop | React 19 web console | React/TS web | PyQt6 + vanilla-JS web | Streamlit | PySide6 | React/TS web | Next.js web |
| SigMF input | ✅ | ❌ (WAV + JSON sidecar) | ✅ full datatype vocabulary | ❌ | ❌ | ✅ | ✅ validated with `sigmf` | ✅ |
| Raw IQ formats | cf32, ci16, cu8 | IQ WAV | full SigMF set, LE/BE | float32 only | int16, float32 | int16/float, explicit order | cf32/ci16 LE/BE | 📄 |
| Mono WAV handled honestly | ✅ Hilbert FIR + FM re-mod | — | ✅ | ❌ | ✅ labels withheld | ✅ asks stereo mode | ✅ never invents Q | 📄 |
| Multi-signal per file | ✅ burst detection, split by frequency | ❌ | 📄 up to 5 time-separated regions | ❌ | ❌ | ❌ | ✅ detection only | 📄 bursts |
| AMC method | Rules + gradient boosting, **18 types** | Blind BPSK/QPSK search (no ML) | Rules + 1D CNN (**68–70%**, 8-way) | Cumulants, 6 mods | CNN (8 digital) + analog gate | Measured features | BPSK/QPSK, SNR-gated | Classifier 📄 |
| AMC evaluated on a public dataset | ❌ own synthetic | ❌ | ❌ own synthetic | ❌ | RML2016 tool (experimental only) | ❌ | ❌ | ❌ |
| Convolutional / Viterbi | ✅ K=3–9, r½, r⅓, punctured, soft/hard | ✅ K=7/5/3 r½, soft | ✅ K≤7 (commpy) | ✅ K=7 | ✅ K=7 (171,133) | ✅ K=7 soft, C++ | ❌ | ✅ r½ hard |
| Reed-Solomon | ✅ blind parameter ID | ❌ | ✅ | ✅ RS(255,223) | ✅ 32 parity | ✅ | ❌ | ✅ |
| LDPC | ✅ DVB-S2, 5G NR, CCSDS, Wi-Fi | ❌ | ❌ | ✅ BP | ❌ | ✅ configured | ❌ | ✅ |
| Concatenated RS + conv | ✅ | ❌ | ❌ | ✅ | ✅ | 📄 | ❌ | ✅ |
| **Blind** FEC identification | ✅ deepest; recovers generators | ✅ syndrome test (conv) | ✅ conv + RS search | ✅ 96-hypothesis catalogue | ✅ structural | ❌ configured only | ❌ | ❌ selectable |
| Interleavers | 4, incl. PR seed search | Block | 4 (PR declared unrecoverable) | 4 | 4 (PR needs seed) | Configured | ❌ | 4 |
| Decode verification | Trial-decode residual vs EVM + sync | Significance-tested syndrome | Re-encode distance | **CRC-16 + sync + re-encode BER** | Sync significance vs control words | CRC | — | CRC |
| Multiple-testing control | ✅ Poisson test, p_fa 10⁻⁶ | ✅ explicit | ❌ | ❌ | ✅ control words | ❌ | — | ❌ |
| Blind framing / header fields | ✅ sync discovery, counters, fixed fields | Time-code frames | Sync word, periodic framing | Sync word | Sync significance | Correlation | — | Bit correlation |
| Real over-the-air validation | ✅ NAVTEX, RTTY, RS41, NOAA APT (**recordings not committed**) | ✅ WWV, DCF77, MSF, JJY, DDH47, AIR (**committed**) | ❌ synthetic only | ❌ | ❌ ("real-world accuracy not established") | ❌ | Synthetic + 1 GiB test | ❌ |
| Large files | First 10 M samples only | — | Chunked detection (80 MB tested), 2 M-sample cap on the signal of interest | — | — | Chunked streaming | ✅ **2 GiB** async (1 GiB validated) | — |
| Tests (README claim / test files in tree) | — / 46 | 30 / 15 | 188 / 16 ⚠️ | 132 / 6 | — / 79 | — / 61 + ctest | — / 15 | 55 + 32 / 35 |
| CI | ✅ | ✅ | ❌ | ❌ | Removed | ✅ | ❌ | ❌ |
| Licence | MIT | None | None | None | CC0 | None | None | Usage note, no SPDX |

⚠️ Devansh-567's README says "188/188 tests" in one place and "104 tests across 10 files" in another. It also lists multi-signal segmentation as both built and not built.

**"None" licence means all rights reserved.** Study those repos; never copy from them.

### 5.2 What to match and what to exploit, per leader

**`SumitKumar00113/sigma-signal-analysis`**, the technical leader.
- *Match:*
  - blind conv-code ID from dual-code parity checks
  - RS parameter ID (n, k, field polynomial, first root, alignment)
  - LDPC from a standards catalogue (a 64,800-bit DVB-S2 frame decodes in about 0.2 s)
  - blind sync discovery with a significance test
  - burst separation
  - 18-type classifier (99% at 4 dB in hybrid mode, on its own synthetic signals)
  - regression tests created from off-air failures
- *Exploit:*
  - desktop only, no web GUI
  - analyses only the first 10 M samples
  - no deep learning; AMC is never evaluated on a public dataset
  - off-air recordings are not in the repo, so results can't be reproduced
  - no SigMF export (JSON/HTML only)
  - it lists its own limits: OFDM/APSK are unknown, no Doppler tracking

**`SomeNobody21112/ICHNOVA`**, the rigour leader.
- *Match:*
  - three outcomes: `DECODED` / `SIGNAL_NO_CODE` / `UNKNOWN`
  - significance corrected for the number of hypotheses tried
  - sealed benchmark (30/30, 0 false accepts; 63/100 on the train set, 0 false accepts)
  - capture-quality gate reported beside the verdict
  - SHA-256 receipt chain
  - "sufficiency": what evidence would settle a refusal
  - committed real recordings with GPS timestamps
- *Exploit:*
  - BPSK/QPSK only
  - convolutional code + block interleaver only
  - no RS, LDPC, QAM or FSK in the blind path (FSK only for teleprinter)
  - its own README says the benchmark transmits only 30–60 of 400 payload bits

**`Devansh-567/hackathon`**, the breadth and honesty reference.
- *Match:*
  - five-state honesty vocabulary
  - full SigMF datatype parser with no silent defaults
  - DSP + ML confidence fusion that surfaces disagreement
  - SQLite history, compare, feedback and fingerprint features
  - JSON/CSV/PDF/SigMF export
  - a 21-item list of bugs it found (see [§6](#6-engineering-lessons-from-rivals-free-bug-reports))
- *Exploit:*
  - CNN is 68–70% and confuses 8PSK with QPSK 87% of the time
  - no LDPC or concatenated codes
  - feed-forward sync only (no Costas or Gardner loops)
  - last push 17 Sep

**`Gururaghavendra123/sihps2-2026`** (Team Vertex), the verification reference.
- *Match:*
  - CRC-16 + sync-word + re-encode-BER acceptance
  - adaptive coarse-to-fine pruning (70–90% fewer decodes)
  - Dataset B scenarios with multipath and CFO
- *Exploit:*
  - fixed 96-hypothesis catalogue
  - float32 raw only, no SigMF
  - synthetic data only

**`The-4Script/RadioFry`**, the honest-limits reference.
- *Match:*
  - measured false-positive residuals are published (e.g. a false interleaver in 5 of 600 streams)
  - sync words must be significant at 1% against control words
  - production model identity is pinned in a freeze document
  - the most test files of any rival (79)
- *Exploit:*
  - Streamlit UI
  - LDPC not identifiable
  - CNN trained only on its own generator
  - demodulation slices one sample per symbol with no matched filter

**`arachknight66/SIH26147`**, the performance reference.
- *Match:*
  - C++20 core via pybind11: native soft Viterbi, RS, LDPC, CRC
  - streaming chunks
  - a missing sample rate is kept missing (output in cycles/sample)
  - CI + ctest
- *Exploit:* codecs are configured, not blind; PySide6 UI.

**`pranshu1141-sharma/Pinpoint`**, the ingestion and detection reference.
- *Match:*
  - 2 GiB async uploads with disk-backed blocks
  - quadrature check on stereo WAV
  - SigMF export validated with the `sigmf` package
  - CFAR-style detection
  - pulse width and PRI
  - every panel mapped to a PS requirement
- *Exploit:* no demodulation or decoding at all.

**`Manas-Dikshit/SignalScope`**, the full-stack reference.
- *Match:* per-estimate provenance record (`source`, `confidence`, `evidence`, `alternatives`, `warnings`); Vitest tests on the frontend.
- *Exploit:*
  - symbol-centre sampling with no closed-loop sync
  - hard-decision Viterbi only
  - heavy stack (Postgres, Redis, Celery) that works against a simple air-gapped install

### 5.3 Second tier — real code, narrower or less verified

| Repo | Last push | Stack | Notable claims | Test files | Verdict |
|---|---|---|---|---|---|
| [Andro-HM/IQWAV](https://github.com/Andro-HM/IQWAV) | 13 Sep | Python + notebooks | 861 tests 📄; real FM validation (PySDR capture, Mumbai wideband FM) | 43 | Disciplined foundations; its own list of what it **doesn't yet do** includes AMC, FEC, interleaving and GUI |
| [karurravishankermohit-stack/-SignalX](https://github.com/karurravishankermohit-stack/-SignalX) | 21 Sep | React + Plotly, FastAPI, **Firebase auth** | 17 stages, 4 interleavers, Viterbi/RS/concatenated, "LDPC reporting"; six provenance labels | 14 | Broad claims; cloud auth conflicts with air-gapped use |
| [arunkumarmeda27/SpectraSync](https://github.com/arunkumarmeda27/SpectraSync) | 23 Sep | React/TS, FastAPI, JWT, Docker | 13 stages; block/conv interleavers; Viterbi + RS; claims **sample-rate inference** | 10 | Polish over substance; placeholder screenshot |
| [EDM-Fan/Nova-Signum](https://github.com/EDM-Fan/Nova-Signum---Signal-Analyzer-) | 22 Sep | PySide6 (about 3,000-line window) | RF classifier on cumulants (4 mods); RS, LDPC(128,64), concatenated, K=7; re-encode match | 12 | Desktop reference; raw `.iq` **defaults to 1 MHz** |
| [rabishankar21/SignalSight](https://github.com/rabishankar21/SignalSight) | 25 Sep (new) | Desktop | 6 mods; Viterbi/RS/concatenated/LDPC(256,128); 4 interleavers; "sample rate" extraction | 19 | Mid; recent |
| [Alekhkr/PS2](https://github.com/Alekhkr/PS2) | 23 Sep (new) | PySide6 | 6 mods; Viterbi/RS/LDPC hypothesis testing; `ParameterEvidence` provenance | 23 | Mid; thin README |
| [WaghJagdish/PS147](https://github.com/WaghJagdish/PS147) | 19 Sep (new) | Python + web | **11-criterion raw-format scorer** (cf32/ci16/cs8, LE/BE, interleaved/planar); Oerder-Meyr; cumulants | 7 | Format scorer is worth studying |
| [ShantanuSomwanshi/SIH-Rf-Signal-Intelligence](https://github.com/ShantanuSomwanshi/SIH-Rf-Signal-Intelligence) | 24 Sep (new) | Streamlit | cu8 (RTL-SDR) input; 8FSK; conv K=3/5/7, RS, LDPC; interleaver size and seed | 0 (script PASS/FAIL) | Mid; no pytest |
| [Rohanbhandari9703/SignalIQ](https://github.com/Rohanbhandari9703/SignalIQ) | 20 Sep (new) | PySide6 | RF classifier (92.5% CV 📄); K=7 + RS(255,223); FEC × interleaver grid search; eye diagram | 14 | Mid |
| [NirmitSingh-main/SYNAPS](https://github.com/NirmitSingh-main/SYNAPS) | 25 Sep | React/TS + FastAPI + **LLM copilot** | CNN / transformer / SSL-MAE models; **6,666 IQ files committed (938 MB repo)** | 20 | README is 12 lines; hard to judge |
| [tejaswi-jain2007/SIGNEX](https://github.com/tejaswi-jain2007/SIGNEX) | 22 Sep | React + FastAPI + Tkinter | ResNet-18, 11 classes incl. APSK/OFDM 📄 | 17 | **README folder layout doesn't match the code**; built `dist/` committed |
| [RohithvijayR/SIGNALX](https://github.com/RohithvijayR/SIGNALX) | 10 Sep (new) | React/TS | Paired IQ + WAV "fusion"; provenance labels | 2 | Low–mid |
| [aayushkasurde112-cell/RF_MVP](https://github.com/aayushkasurde112-cell/RF_MVP) | 17 Sep (new) | Python functions | SigMF writer; CFAR; Gardner + Farrow + Costas | 3 | Clean but early |
| [harikesh2709-creator/spectra-signal-analyzer](https://github.com/harikesh2709-creator/spectra-signal-analyzer) | 26 Sep (new) | FastAPI + web | ">95% at −10 dB SNR" CNN-Transformer 📄; "SIH 2026 Finalist" badge | 2 | **Overclaim; no model files found.** Team FUTURISTICS. |
| [Shivanshgh/Spectra-Sense](https://github.com/Shivanshgh/Spectra-Sense) | 16 Sep | React/TS client-side DSP, Vercel | Orchestration over GNU Radio / URH; `UNRESOLVED` state | 0 | Concept; no FEC code |
| [Selvamurugan-hub/SpectraSense-AI](https://github.com/Selvamurugan-hub/SpectraSense-AI) | 9 Sep (new) | Web | Fingerprints, anomaly detection | 4 | Analytics only; no demod/FEC |
| [DevWithShubham18/SAGE-RF](https://github.com/DevWithShubham18/SAGE-RF) | 10 Sep (new) | Firebase, Vercel, Render, LLM | Hosted workstation | 5 | Cloud-dependent; no FEC |
| [Akshat030307/SIH](https://github.com/Akshat030307/SIH) | 1 Sep | Python, spec in `CLAUDE.md` | I/O done; detector in progress | 9 | **Stalled.** Multi-signal analysis is *planned*, not built. |

### 5.4 Early stage or placeholder

These have 15 files or fewer, or no README: [gourabde7/Spectra](https://github.com/gourabde7/Spectra) (★1), [Muizzahmed786/SIH26147](https://github.com/Muizzahmed786/SIH26147), [xarjunpatil/SIH26147-…](https://github.com/xarjunpatil/SIH26147-Automated-model-for-analysis-of-IQ-and-wav-files-along-with-signal), [Jagzz-Coder/sigscope](https://github.com/Jagzz-Coder/sigscope), [sautiksamui-tech/SIH2026](https://github.com/sautiksamui-tech/SIH2026), [dharsankumar250053-spec/SignalLens](https://github.com/dharsankumar250053-spec/SignalLens), [dasmahapatrapranati-rgb/Signal_Analyzer](https://github.com/dasmahapatrapranati-rgb/Signal_Analyzer), [26147-alt/index](https://github.com/26147-alt/index), [harideskzone-hue/SIH26147-Border](https://github.com/harideskzone-hue/SIH26147-Border) (empty).

### 5.5 Corrections to the dossier (§B6(f))

| Dossier says | Verified on 26 Sep 2026 |
|---|---|
| `mks-Roald/ps26147_toolkit`: CLI + Streamlit, RF on RadioML 2016.10a | **404**: deleted, renamed or made private |
| `harikesh2709-creator/FUTURISTICS`: full DSP chain | That repo is now **FreightForecast Pro**, a maritime freight app for a different PS. The team's SIH26147 repo is `spectra-signal-analyzer`, created 25 Sep. |
| `Akshat030307/SIH` "now does multi-signal scene analysis" | Only planned. Phase 3 of 8 is in progress; last push 1 Sep. |
| `SumitKumar00113/sigma-signal-analysis`: "PySide6 GUI; ingestion; IQ-imbalance checks" | The **most capable repo in the field** (see §5.2) |
| Real over-the-air validation is a differentiator (§B2) | Already done by sigma, ICHNOVA and IQWAV |
| "14+ repos" | **35 live repos**; about 26 with substantive code |

---

## 6. Engineering lessons from rivals (free bug reports)

Other teams found these bugs by testing against ground truth. We should design them out from day one. Credit goes to the repo named after each item.

1. **Silent sample-rate defaults.** One repo shipped with the rate defaulting to 1 Hz; Nova-Signum defaults raw `.iq` to 1 MHz. *Rule:* an unresolved rate means frequency-dependent stages are skipped with a stated reason. (Devansh-567, Pinpoint)
2. **SNR and detection unit errors.** Comparing a PSD-per-Hz noise floor against total time-domain power put the detection threshold about 30 dB too low. *Rule:* integrate over bandwidth, and unit-test the dimensions. (Devansh-567 #1, #13)
3. **RRC needs a matched filter.** A single RRC is not zero-ISI; the correct sampling phase after matched filtering was 0, not `sps//2`. (Devansh-567 #2, #3)
4. **QAM breaks naive M-th-power carrier recovery.** Gate it on peak-to-median ratio, or skip it. (Devansh-567 #5)
5. **`reedsolo.RSCodec` does not pad to n.** It appends n−k parity bytes to any payload length. (Devansh-567 #11)
6. **A successful RS decode with a weaker preset can be wrong.** An `rs_255_239` decode of `rs_255_223` data reported success with 0 corrections and still returned the wrong bytes. *Rule:* prefer more parity, and always cross-check with CRC or sync. (Devansh-567 #12)
7. **scikit-commpy's `Trellis` overflows for K ≥ 8** under current NumPy. (Devansh-567)
8. **False FEC from repetition and half-element sampling.** Such streams satisfy parity checks by chance. *Rule:* reject a candidate when a trial decode leaves more than about 12% channel errors, or more than the EVM allows. (sigma)
9. **False framing from idle patterns.** *Rule:* require at least 64-bit frames with varying payload, and significance-test any counters. (sigma, RadioFry)
10. **Symbol-rate harmonics beat the fundamental** on long captures. *Rule:* rank candidates by their harmonic comb. (sigma)
11. **FM carrying audio looks like FSK/PSK.** *Rule:* check the FM discriminator output first. (sigma)
12. **FastAPI route order.** `/analyses/{id}` registered before `/analyses/compare` swallows `compare`. (Devansh-567 #18)
13. **Benchmark hygiene.** If a "sealed" set was inspected during development, it is only a regression tripwire. Keep a truly held-out set. (ICHNOVA)
14. **Quadrature is evidence, not proof.** Stereo audio can pass the IQ check. Record the heuristic and let the analyst override it. (Pinpoint)

---

## 7. Table stakes vs open differentiators

**Table stakes.** Do all of these or lose credibility:
- SigMF in/out; raw cf32/ci16/ci8/cu8 with explicit format; honest mono-WAV handling
- per-parameter provenance and evidence levels; no silent defaults
- spectrum, waterfall, constellation, eye diagram
- PSK/QAM/FSK demodulation with real sync loops
- all four interleaver families
- Viterbi, RS, concatenated and LDPC
- CRC / sync-word / re-encode verification
- JSON/PDF/SigMF reports
- offline operation
- a pytest suite and CI

**Open differentiators** (no public rival does these as of 26 Sep):

| # | Differentiator | Closest rival and its gap |
|---|---|---|
| D1 | **Deep-learning AMC evaluated on public datasets** (RadioML 2018.01A, TorchSig/Sig53, HisarMod) with a full −20 to +30 dB curve, calibration and open-set noise rejection | sigma and Devansh evaluate only on their own synthetic data; RadioFry's RadioML models are "experimental, not production" |
| D2 | **Web GUI (React/TS, WebGL) with sigma-level blind decoding depth**, running air-gapped | The deepest decoders are desktop apps (sigma, Vertex); the web apps (Devansh, SignalScope, Pinpoint) decode far less |
| D3 | **Open sealed benchmark plus head-to-head results** against public rival tools, including a null set for false-accept rate | ICHNOVA's sealed set is 30 files, BPSK/QPSK only; nobody benchmarks rivals |
| D4 | **Committed, licensed, Indian over-the-air recordings** with protocol-level ground truth (Indian NAVTEX and other HF via KiwiSDR, ADS-B CRC, AIS CRC, Meteor-M LRPT; NOAA APT and FM RDS only if confirmed on air in India) | sigma's recordings aren't in its repo; ICHNOVA's are mostly foreign time stations |
| D5 | **Analyst-in-the-loop:** correct any stage and every later stage re-runs automatically, with a before/after diff | Devansh re-runs 3 overrides and only records feedback; sigma's workbench is manual |
| D6 | **Multi-GB streaming through the entire chain**, not just detection | Pinpoint streams 2 GiB (detection only); sigma stops at 10 M samples |
| D7 | **Overlapping co-channel and frequency-hopping signals** (detect and label, even when decoding isn't possible) | No rival attempts this |
| D8 | **Transparent hypothesis accounting in the UI:** how many code/interleaver guesses were tried, the corrected threshold, the empirical false-alarm rate on shuffled bits, and why each was rejected | ICHNOVA and sigma compute it but don't expose it as an analyst view |
| D9 | **The first open, benchmarked implementation of the literature's blind code and interleaver identification methods:** GJETP/dual-code for convolutional and punctured codes, GFFT for RS, rank-drop and KS tests for interleavers. Research in Sep 2026 found **no public implementation** of these methods anywhere. | Rivals use ad-hoc search or trial decoding; deep-learning papers only pick among trained classes and release no code |

**Talking point for judges:** RadioML, the dataset most rivals cite, has SNR labels off by tens of dB, a noise-only AM-SSB class (2016.10a), a wrong class-name mapping in 2018.01A, and a non-commercial licence. We train on our own impaired generator and use RadioML only as a benchmark, with corrected labels.

---

## 8. Our bar — measurable targets

These are **targets, not claims.** A number moves into the deck only after a `bench/` script reproduces it.

| Area | Metric | Best public rival today | Our target |
|---|---|---|---|
| Ingestion | Formats | Full SigMF vocabulary (Devansh-567) | Full SigMF vocabulary + raw cf32/ci16/ci8/cu8 LE/BE + WAV mono/stereo with quadrature check; **0 silent defaults** (tested) |
| Scale | Largest file processed | 2 GiB, detection only (Pinpoint) | **≥ 4 GiB** streamed through detection, and the full chain on every selected signal |
| Detection | Recall / false detections on a multi-signal bench | Not published | ≥ 95% recall, ≤ 5% false detections at ≥ 6 dB in-band SNR |
| Estimation | Symbol rate / SNR / CFO error | sigma: SNR within 0.3 dB, rate within 1 Hz on its own files | Rate ≤ 0.1% at ≥ 10 dB; SNR ±1 dB over 0–20 dB; CFO ≤ 1% of Rs, reported per SNR bucket |
| AMC, public data | RadioML 2018.01A, 24 classes, held-out, **with corrected SNR labels** | None published; ~10K-parameter models reach about 58–60% averaged / 92–96% peak in papers | ≥ 93% at SNR ≥ +10 dB; ≥ 55% averaged over all 26 SNRs (stretch: 60%); full curve published with a ≤ 50K-parameter model |
| AMC, open set | Held-out modulations as unknowns, per SNR bin | None published | AUROC ≥ 0.90 at ≥ 6 dB; FPR@95%TPR and OSCR reported |
| AMC, real signals | Accuracy on labelled real captures (PLAN M8) | None published; papers show about 96% → 35% sim-to-real drops | Report before/after fine-tuning; target ≥ 85% at ≥ 10 dB |
| AMC, in scope | ≥ 12 digital classes, TorchSig-impaired, **independent** generator | sigma: 99% at 4 dB, own synthetic | ≥ 95% at ≥ 6 dB; ≥ 80% at 0 dB; noise-only rejection ≥ 99% (unseen modulations: see the open-set row) |
| FEC ID: convolutional | Code + generators + puncturing, soft decisions | sigma: works "at several percent BER" | ≥ 95% at raw channel BER ≤ 2% (K ≤ 7), with LLR input |
| FEC ID: RS | n, k, field polynomial, first root, alignment | sigma: identifies with errors present | ≥ 95% at symbol-error rate after the inner decoder ≤ 1% (or on uncoded-inner streams at channel BER ≤ 10⁻³) |
| FEC ID: LDPC | Catalogue matrix + alignment | sigma: standards catalogue | ≥ 95% at Es/N0 ≥ the code's decoding threshold + 1 dB, via soft syndrome scoring |
| False accepts | Accepted decodes on a null set (noise, uncoded, random) | ICHNOVA: 0 on 130 files | **0 on ≥ 1,000 null files** (95% upper bound ≤ 0.3%) |
| Interleaver ID | Block / diagonal / convolutional with an inner code | sigma (not quantified) | ≥ 90%; pseudo-random either matched to a standard permutation (3GPP, LTE QPP, 802.11, DVB-S2) or reported UNKNOWN with its measured period, **never a false VERIFIED** |
| Framing | Blind sync-discovery false alarm | sigma: 10⁻⁶ | ≤ 10⁻⁶ per stream, reported |
| Real signals | Committed over-the-air recordings | ICHNOVA: 7 stations | ≥ 10 recordings, ≥ 6 services, ≥ 4 captured in India, each with SigMF provenance and a licence |
| Speed | Full chain, 10 M samples, 4-core laptop CPU | sigma: ≈ 2 s on a 2.5 s multi-burst file | ≤ 10 s, excluding blind LDPC catalogue search |
| Offline | Outbound connections at runtime | Most claim it; none test it | 0, enforced by a socket-blocking test |
| Quality | Automated tests / CI | IQWAV: 861 claimed; RadioFry: 79 test files | ≥ 300 tests + Playwright E2E; CI green on every PR |

**Why FEC targets are per family.** A flat "95% at 3% BER" can't be met for long codes. Hard-decision rank methods need error-free rows, and at 3% BER a 2,040-bit RS(255,223) row is clean with probability 0.97²⁰⁴⁰ ≈ 10⁻²⁷.

---

## 9. Competitive matrix — draft for the idea deck

Our column shows **targets** and must say so on the slide. The point is to show we know the field better than anyone.

| | Us (target) | sigma | ICHNOVA | Devansh-567 | Team Vertex | Krypto500 |
|---|---|---|---|---|---|---|
| Open source & indigenous | ✅ | ✅ MIT | ✅ | ✅ | ✅ | ❌ ITAR |
| Web GUI, air-gapped | ✅ | Desktop | ✅ | ✅ | Desktop + web | Desktop |
| Blind FEC (conv + RS + LDPC) | ✅ | ✅ | Conv only | Conv + RS | Catalogue | ✅ |
| Verified decode + false-accept rate published | ✅ | Partial | ✅ | ❌ | Partial | ? |
| DL AMC on public datasets | ✅ | ❌ | ❌ | ❌ | ❌ | ? |
| Committed Indian off-air recordings | ✅ | ❌ | AIR carriers | ❌ | ❌ | — |
| Analyst correction → automatic re-run | ✅ | Manual | ❌ | Partial | ❌ | ? |
| Literature blind-ID methods (GJETP / GFFT / rank-drop), open + benchmarked | ✅ | Own methods | Syndrome test | Trial search | Catalogue | ? |
| Multi-GB full-chain streaming | ✅ | ❌ | ❌ | ❌ | ❌ | ? |

---

## 10. How to refresh this document

- **Automated:** the `rival-scan` custom skill ([CLAUDE_SKILLS_MCP §8](../.claude/CLAUDE_SKILLS_MCP.md#8-custom-project-skills); not created yet) will re-run the searches and diff the results against this file. Until it exists, run the queries below by hand.
- **Queries used on 26 Sep:** `SIH26147`, `SIH 26147`, `26147 in:name,description,readme`, `iq wav signal parameter extraction`, `NTRO signal analysis`, `automated model analysis .IQ .wav`, `modulation classification iq wav created:>2026-08-15`, and `sigmf created:>2026-08-20`.
- **Before each pitch:** re-check the top 8. `sigma` and `Pinpoint` were both pushed on the day of this snapshot.
- **Unauthenticated GitHub API limit:** 60 requests/hour. Run `gh auth login` to raise it.
