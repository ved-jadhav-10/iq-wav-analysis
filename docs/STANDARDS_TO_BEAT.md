# Standards to beat — SIH26147

The bar our tool has to clear: commercial products, open-source tools, published research, and every public SIH26147 repository we could find.

- **Snapshot:** rivals re-scanned **30 Sep 2026** (first scan 26 Sep); vendor facts (§2) checked against primary sources on 29 Sep. The field moves daily: re-run the scan before any pitch ([§10](#10-how-to-refresh-this-document)).
- **Method:** repo metadata (created, last push, licence) from the GitHub REST API; capabilities checked against each repo's **file tree** and **README**. We did not clone or run rival code.
- **Sources:** every citation behind this document, the plan's methods and the standards versions is in [§11](#11-references).

**Legend:** ✅ backed by code in the repo tree · 📄 README claim, not traced to code · ❌ not found · — not applicable.

---

## 1. Summary — what the bar looks like now

1. **About 60 SIH26147 repos are public** (35 on 26 Sep, about 60 by 30 Sep); about 40 contain real code. The strongest newcomer is `Venkata-Manoj/RF-signal-analysis` (§5.3): all four interleaver families, Viterbi/RS/LDPC/concatenated behind a CRC gate, desktop + web + CLI.
2. **Real off-air decoding is table stakes among the leaders.** sigma decodes real NAVTEX (SITOR-B), RTTY and NOAA APT to messages and images; ICHNOVA decodes WWV, DCF77, MSF, JJY, DDH47 and All India Radio carriers via KiwiSDR; Pinpoint scores a frozen benchmark of 170 real SigMF captures.
3. **The technical leader is sigma** (PySide6 desktop, now with Windows and macOS installers): 18 modulations; blind convolutional (K=3–9, punctured), RS and catalogue-LDPC identification; interleavers including a pseudo-random seed search; Poisson-tested sync words.
4. **The rigour leader is ICHNOVA:** sealed benchmark with 0 false accepts, multiple-testing correction, a SHA-256 receipt chain, a payload-reliability gate — but only BPSK/QPSK, convolutional codes and a block interleaver.
5. **Table stakes:** honesty labels, SigMF ingest, four interleaver types, Viterbi + RS, CRC/sync/re-encode checks (8+ repos).
6. **Commercial tools automate more than we first assumed.** R&S CA250 advertises fully automated detection of convolutional, RS and BCH codes; Wavecom W-BitView has an automatic convolutional-code search. No vendor documents **automatic interleaver recovery chained to blind FEC, from raw IQ, with stated evidence**: that is our claim (§2).
7. **Gaps nobody fills yet:** deep-learning AMC on public datasets with a full SNR curve; a web GUI with sigma-level decoding depth; a head-to-head sealed benchmark; committed, licensed Indian off-air recordings; automatic downstream re-runs after an analyst correction; multi-GB streaming through the whole chain; co-channel and frequency-hopping signals ([§7](#7-table-stakes-vs-open-differentiators)).
8. **Overclaiming exists and judges will spot it** (a "SIH 2026 Finalist" badge before any finale; ">95 % at −10 dB" with no model files). Our docs and deck never make a claim `bench/` can't reproduce.

---

## 2. Commercial incumbents

Checked against vendor material on 29 Sep 2026 ([§11](#11-references)). **No vendor publishes a price.**

| Product | Maker | Price | Constraints |
|---|---|---|---|
| Krypto500 / Krypto1000 | COMINT Consulting (USA) | None public. "US$7,400" appears only in a Feb 2012 third-party review (*Monitoring Quarterly*): never quote it as current | ITAR-controlled (22 CFR §120-130, vendor brochure); no demo, trial or light version |
| R&S CA120 + CA250 | Rohde & Schwarz (Germany) | Quotation only | Export status not public |
| go2MONITOR / go2DECODE / go2ANALYSE | PROCITEC (Germany) | Quotation only | German export permission for its MIL/PMR packages |
| W-CODE, W-BitView | Wavecom (Switzerland) | Via contact only (a third-party page reported about US$995 per user on 27 Sep: unverified, never quote) | Export status not public |
| CODE300-32 | Hoka Electronic (Netherlands) | Not checked | Commercial licence |
| Decodio | Decodio (Switzerland) | Quotation only | — |

What the vendors' own material says:
- **Krypto500:** narrowband up to 48 kHz (Krypto1000 wideband); automatic classification of ">3,000" modems (current site; older brochures "nearly 4000" / "4000+"); "hundreds of decoders"; parsers, RadioID fingerprinting, traffic and network analysis, output formats that support cryptanalysis; baseband audio, WAV/RF64 and I/Q input; output as decoded text or the demodulated bitstream in ASCII or hex; Windows, 400+ receivers and SDRs ([brochure](https://datatec.es/wp-content/uploads/2016/04/Krypto500.pdf), [site](https://www.comintconsulting.com/krypto500)). **No blind FEC or de-interleaving documented.**
- **R&S CA120** recognises modulation and transmission systems automatically and reports unknowns as "unknown". **R&S CA250** (a separate bitstream tool) advertises "fully automated detection of convolutional, Reed-Solomon and BCH codes", plus descrambling and de-interleaving functions; automatic *interleaver* recovery is not stated. GX430 is the legacy product (rated best automatic classifier in the 2012 review).
- **PROCITEC:** go2MONITOR wideband detection and classification; go2DECODE recognition and decoding of ">470 modems" including digital voice (DMR, TETRA, P25, NXDN), manual displays for "new, unidentified signals" (spectrogram and baud-rate measurement, autocorrelation, constellation, amplitude/frequency/phase behaviour, a raster display for coding analysis) and a decoder-writing language (DDL/pyDDL) ([go2DECODE brochure](https://procitec.com/file_access/6816/4250/3024/PRO_Broschure_go2DECODE_22.1_lres.pdf)); go2ANALYSE tests bitstreams against a list of codes and de-interleaves with set parameters; its own brochure says manual analysis of unknowns takes "often hours!".
- **Wavecom** ([site](https://www.wavecom.ch/)): W-CODE has an automatic classifier and ">226" modes (2015 brochure; the site read "300+" on 27 Sep), including MIL-STD-188-110 and STANAG 4285/4529/4539/5066. W-BitView searches convolutional codes K = 2–14, n = 2–4 automatically; de-interleaving takes user-set parameters.

**How incumbents work:** a large **library of known modems**, recognised and decoded automatically, plus **analyst tools** for what the library doesn't know (the "carried out manually" the PS describes). At least R&S and Wavecom automate modulation recognition and convolutional/RS/BCH code detection.

**Our angle:** open, indigenous, air-gapped, SigMF-native and ground-truth verified; no vendor is all of these. We don't claim their protocol libraries or live monitoring. We claim **automatic interleaver recovery chained to blind FEC and framing, from raw IQ in one chain** (undocumented by any vendor), **transparent evidence and hypothesis accounting** for every result, and **no licence or ITAR lock-in**.

---

## 3. Open-source prior art

Tools to learn from or build on (stars and pushes as of 26 Sep 2026).

| Tool | What it is | Licence | Relevance to us |
|---|---|---|---|
| [GNU Radio](https://www.gnuradio.org/) | Signal-processing flowgraph toolkit | GPL-3.0 | Synthetic data and reference receivers. **Dev-time only**: never link GPL code into the product |
| [TorchSig](https://github.com/TorchDSP/torchsig) (★376, pushed 2 Sep) | PyTorch RF-ML toolkit; 2.x is a configurable generator with "60+" signal types and impairments. Sig53/WidebandSig53 renamed Narrowband/Wideband in v0.6.0 | MIT | Independent test generator (training uses `dsp.synth`). **Needs Ubuntu ≥ 22.04**, so WSL2 on Windows |
| [IQEngine](https://github.com/IQEngine/IQEngine) (★332) | Web SDR toolkit for viewing and annotating recordings: React/TS client, FastAPI backend, SigMF, its own `webfft` | MIT | **Closest match to our architecture.** Borrow components rather than start from scratch. Pinpoint studied it too |
| OpenWebRX | Web SDR receiver UI | **AGPL-3.0** | UX reference only |
| [SigMF](https://github.com/sigmf/SigMF) (★466) + `sigmf` Python package | Metadata standard for recordings | Spec CC-BY-SA-4.0 | Native input/output format |
| gr-spectrumdetect | YOLOv8 wideband detector trained with TorchSig, inside GNU Radio | — | Reference for wideband detection |
| Inspectrum, Universal Radio Hacker (URH) | Manual IQ inspection and protocol analysis | GPL | Cross-checking our results by hand |
| [SigDigger](https://github.com/BatchDrake/SigDigger) (★2,904) | Qt desktop analyser for unknown signals: FSK/PSK/ASK demodulation, bursty signals, analog audio | LGPL-3.0 | The closest free tool to manual technical analysis; UX and workflow reference; not linked into the product |
| liquid-dsp, AFF3CT | C/C++ DSP and FEC libraries | MIT | Performance references; rivals found them hard to install on Windows |
| [galois](https://github.com/mhostetter/galois) 0.4.11 | Finite fields (Numba), BCH and RS codes | MIT | **Primary GF/RS dependency**; makes the RS Galois-field Fourier test straightforward |
| scikit-commpy 0.8.0, reedsolo 1.7.0, pyldpc 0.7.9 | Python FEC | BSD-3 / public domain / MIT | commpy (last release 2022) and pyldpc (2020) are stale: vendor the functions we need, don't depend on them. **Pitfalls in [§6](#6-engineering-lessons-from-rivals-free-bug-reports)** |
| komm 0.34.0 | Most active Python comms toolbox | **GPL-3.0** | Reference only; keep out of the product |
| [PySDR](https://pysdr.org) | Free IQ/DSP textbook with code (FSM/TSM/FAM, etc.) | **CC BY-NC-SA** | Onboarding and method reference; don't copy its code |
| Sionna 2.1 | NVIDIA link-level simulator, now on PyTorch | Apache-2.0 | Too heavy for an air-gapped CPU install |
| onnxruntime 1.30, numba 0.67, sigmf 1.13 | Inference, JIT, metadata | MIT / BSD / LGPL | All have Windows wheels; numpy 2.5 needs Python 3.12+ |
| [iqscan](https://github.com/gdamdam/iqscan) (new, Sep 2026) | Scans raw IQ recordings for activity; interactive offline HTML report | **GPL-3.0** | UX reference only |
| Reference decoders: readsb, AIS-catcher, rtl_433, multimon-ng, SatDump; redsea | Ground-truth decoders for real captures | GPL; redsea MIT | Subprocesses in the test harness only |

---

## 4. Academic AMC benchmarks

From the papers themselves (O'Shea 2018 in [§11](#11-references); MobileRaT and Harper et al. as cited).

| Model / paper | Dataset | Reported accuracy |
|---|---|---|
| O'Shea, Roy & Clancy, IEEE JSTSP 2018 (ResNet) | RadioML 2018.01A (24 classes, −20 to +30 dB, 2.56 M examples) | About 95 % at high SNR, about 90 % at around 6 dB, collapsing below −6 dB |
| AMC-Transformer | RadioML 2018.01A | 98.8 % at SNR ≥ 10 dB |
| MobileRaT (MDPI *Drones* 7(10):596, 2023) | RadioML 2018.01A | 98.4 % peak (+18 dB), **65.9 % averaged over all SNRs** |
| Harper, Thornton & Larson (MDPI *Electronics* 12:3962, 2023) | RadioML 2018.01A | 98.9 % peak, **63.7 % overall** |

**Takeaway:** at high SNR AMC is close to solved; the all-SNR average (about 64–66 %) and behaviour below 0 dB separate honest work from marketing.

---

## 5. SIH26147 rival repositories

### 5.1 Capability matrix — the eight leaders

| | [sigma](https://github.com/SumitKumar00113/sigma-signal-analysis-SIH-2026) | [ICHNOVA](https://github.com/SomeNobody21112/ICHNOVA) | [Devansh-567](https://github.com/Devansh-567/hackathon) | [Team Vertex](https://github.com/Gururaghavendra123/sihps2-2026) | [RadioFry](https://github.com/The-4Script/RadioFry) | [arachknight66](https://github.com/arachknight66/SIH26147) | [Pinpoint](https://github.com/pranshu1141-sharma/Pinpoint) | [SignalScope](https://github.com/Manas-Dikshit/SignalScope) |
|---|---|---|---|---|---|---|---|---|
| Last push | 29 Sep | 29 Sep | 17 Sep | 28 Sep | 25 Sep | 29 Sep | 29 Sep | 19 Sep |
| GUI | PySide6 desktop; Windows/macOS installers | React 19 web console | React/TS web | PyQt6 + vanilla-JS web | Streamlit | PySide6 | React/TS web | Next.js web |
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
| Real over-the-air validation | ✅ NAVTEX, RTTY, NOAA APT decoded to messages/images; RS41 (**recordings not committed**) | ✅ WWV, DCF77, MSF, JJY, DDH47, AIR (**committed**) | ❌ synthetic only | ❌ | ❌ ("real-world accuracy not established") | ❌ | ✅ **frozen 170-capture real SigMF benchmark** (sha256-pinned) | ❌ |
| Large files | First 10 M samples only | — | Chunked detection (80 MB tested), 2 M-sample cap on the signal of interest | — | — | Chunked streaming | ✅ **2 GiB** async (1 GiB validated) | — |
| Tests (README claim / test files in tree) | — / ~42–46 | 30 / 27 | 188 / 16 ⚠️ | 132 / 6 | — / 79 | — / 61 + ctest | — / 15 | 55 + 32 / 35 |
| CI | ✅ | ✅ | ❌ | ❌ | Removed | ✅ | ❌ | ❌ |
| Licence | MIT in README; no LICENSE file detected | None | None | None | CC0 | None | None | Usage note, no SPDX |

⚠️ Devansh-567's README says "188/188 tests" in one place and "104 tests across 10 files" in another, and lists multi-signal segmentation as both built and not built.

**"None" licence means all rights reserved.** Study those repos; never copy from them.

### 5.2 What to match and what to exploit, per leader

- **`SumitKumar00113/sigma-signal-analysis-SIH-2026`** (renamed ~29 Sep), the technical leader.
  *Match:* blind conv-code ID from dual-code parity checks; RS parameter ID (n, k, field polynomial, first root, alignment); LDPC from a standards catalogue (a 64,800-bit DVB-S2 frame decodes in about 0.2 s); blind sync discovery with a significance test; burst separation; an 18-type classifier (99 % at 4 dB in hybrid mode, on its own synthetic signals); regression tests made from off-air failures; message-level output for real signals (NAVTEX text, APT images); Windows/macOS installers.
  *Exploit:* desktop only, no web GUI; analyses only the first 10 M samples; no deep learning, AMC never evaluated on a public dataset; off-air recordings not in the repo, so results can't be reproduced; no LICENSE file, so its README's "MIT" is not machine-detectable; no SigMF export (JSON/HTML only); its own listed limits: OFDM/APSK unknown, no Doppler tracking.
- **`SomeNobody21112/ICHNOVA`**, the rigour leader.
  *Match:* three outcomes `DECODED` / `SIGNAL_NO_CODE` / `UNKNOWN`; significance corrected for the hypotheses tried; sealed benchmark (30/30, 0 false accepts; 63/100 on the train set, 0 false accepts); a capture-quality gate beside the verdict; a SHA-256 receipt chain; "sufficiency": what evidence would settle a refusal; committed real recordings with GPS timestamps; a payload-reliability gate that withholds unreliable payloads (it measures its own Doppler limitation).
  *Exploit:* BPSK/QPSK only; conv code + block interleaver only; no RS, LDPC, QAM or FSK in the blind path (FSK only for teleprinter); its own README says the benchmark transmits only 30–60 of 400 payload bits.
- **`Devansh-567/hackathon`**, the breadth and honesty reference.
  *Match:* a five-state honesty vocabulary; a full SigMF datatype parser with no silent defaults; DSP + ML confidence fusion that surfaces disagreement; SQLite history, compare, feedback and fingerprint features; JSON/CSV/PDF/SigMF export; a 21-item list of bugs it found ([§6](#6-engineering-lessons-from-rivals-free-bug-reports)).
  *Exploit:* CNN at 68–70 %, confusing 8PSK with QPSK 87 % of the time; no LDPC or concatenated codes; feed-forward sync only (no Costas or Gardner); last push 17 Sep.
- **`Gururaghavendra123/sihps2-2026`** (Team Vertex), the verification reference.
  *Match:* CRC-16 + sync-word + re-encode-BER acceptance; adaptive coarse-to-fine pruning (70–90 % fewer decodes); Dataset B scenarios with multipath and CFO. *Exploit:* a fixed 96-hypothesis catalogue; float32 raw only, no SigMF; synthetic data only.
- **`The-4Script/RadioFry`**, the honest-limits reference.
  *Match:* published false-positive residuals (e.g. a false interleaver in 5 of 600 streams); sync words significant at 1 % against control words; production model identity pinned in a freeze document; the most test files of any rival (79). *Exploit:* Streamlit UI; LDPC not identifiable; CNN trained only on its own generator; demodulation slices one sample per symbol with no matched filter.
- **`arachknight66/SIH26147`**, the performance reference.
  *Match:* C++20 core via pybind11 (native soft Viterbi, RS, LDPC, CRC); streaming chunks; a missing sample rate kept missing (output in cycles/sample); CI + ctest. *Exploit:* codecs configured, not blind; PySide6 UI.
- **`pranshu1141-sharma/Pinpoint`**, the ingestion and detection reference.
  *Match:* 2 GiB async uploads with disk-backed blocks; quadrature check on stereo WAV; SigMF export validated with the `sigmf` package; CFAR-style detection; pulse width and PRI; every panel mapped to a PS requirement; a frozen 170-capture real benchmark with pre-registered expectations and a diagnosis of why it abstains; an offline batch CLI. *Exploit:* demodulation limited to simple ASK/FSK checks; no FEC or interleaver decoding.
- **`Manas-Dikshit/SignalScope`**, the full-stack reference.
  *Match:* a per-estimate provenance record (`source`, `confidence`, `evidence`, `alternatives`, `warnings`); Vitest frontend tests. *Exploit:* symbol-centre sampling with no closed-loop sync; hard-decision Viterbi only; a heavy stack (Postgres, Redis, Celery) against a simple air-gapped install.

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
| [Rohanbhandari9703/SignalIQ](https://github.com/Rohanbhandari9703/SignalIQ) | 20 Sep (new) | PySide6 | RF classifier (92.5 % CV 📄); K=7 + RS(255,223); FEC × interleaver grid search; eye diagram | 14 | Mid |
| [NirmitSingh-main/SYNAPS](https://github.com/NirmitSingh-main/SYNAPS) | 25 Sep | React/TS + FastAPI + **LLM copilot** | CNN / transformer / SSL-MAE models; **6,666 IQ files committed (938 MB repo)** | 20 | README is 12 lines; hard to judge |
| [tejaswi-jain2007/SIGNEX](https://github.com/tejaswi-jain2007/SIGNEX) | 22 Sep | React + FastAPI + Tkinter | ResNet-18, 11 classes incl. APSK/OFDM 📄 | 17 | **README folder layout doesn't match the code**; built `dist/` committed |
| [RohithvijayR/SIGNALX](https://github.com/RohithvijayR/SIGNALX) | 10 Sep (new) | React/TS | Paired IQ + WAV "fusion"; provenance labels | 2 | Low–mid |
| [aayushkasurde112-cell/RF_MVP](https://github.com/aayushkasurde112-cell/RF_MVP) | 17 Sep (new) | Python functions | SigMF writer; CFAR; Gardner + Farrow + Costas | 3 | Clean but early |
| [harikesh2709-creator/spectra-signal-analyzer](https://github.com/harikesh2709-creator/spectra-signal-analyzer) | 26 Sep (new) | FastAPI + web | ">95% at −10 dB SNR" CNN-Transformer 📄; "SIH 2026 Finalist" badge | 2 | **Overclaim; no model files found.** Team FUTURISTICS |
| [Shivanshgh/Spectra-Sense](https://github.com/Shivanshgh/Spectra-Sense) | 16 Sep | React/TS client-side DSP, Vercel | Orchestration over GNU Radio / URH; `UNRESOLVED` state | 0 | Concept; no FEC code |
| [Selvamurugan-hub/SpectraSense-AI](https://github.com/Selvamurugan-hub/SpectraSense-AI) | 9 Sep (new) | Web | Fingerprints, anomaly detection | 4 | Analytics only; no demod/FEC |
| [DevWithShubham18/SAGE-RF](https://github.com/DevWithShubham18/SAGE-RF) | 10 Sep (new) | Firebase, Vercel, Render, LLM | Hosted workstation | 5 | Cloud-dependent; no FEC |
| [Akshat030307/SIH](https://github.com/Akshat030307/SIH) | 1 Sep | Python, spec in `CLAUDE.md` | I/O done; detector in progress (phase 3 of 8) | 9 | **Stalled.** Multi-signal analysis is *planned*, not built |
| [mks-Roald/ps26147_toolkit](https://github.com/mks-Roald/ps26147_toolkit) | 29 Sep | CLI + Streamlit, Next.js front end | Random Forest on RadioML 2016.10a (4 mods), low-confidence fallback, regression ledger | 20 | Live again (a 404 on 26 Sep) |
| [Akhil-0911/SigIQ](https://github.com/Akhil-0911/SigIQ) | 25 Sep (new) | Tkinter | BPSK/QPSK/16QAM/2FSK/4FSK; joint search over 4 interleavers × Viterbi/RS/concatenated/LDPC; sync false-alarm test; provenance labels | 4 | Has a LICENSE; broad claims, few tests |
| [pranav21122007-hackathon/SIG-Sense](https://github.com/pranav21122007-hackathon/SIG-Sense_Blind_Signal_Intelligence_for_Unknown_RF_Transmissions) | 27 Sep (new) | React/D3 | "Zero-prior" pipeline: GF(2) rank de-interleaving, ONNX ResNet1D + cumulants, RS, Viterbi | 0 | Claims unverified; no tests |
| [yoganandasp15/SIH_2026_Signal-Analyser](https://github.com/yoganandasp15/SIH_2026_Signal-Analyser) | 26 Sep (new) | Python | Rule-based modulation families, multi-window stability gate, 95 % bounds; no FEC | 19 | Honesty-focused, shallow decode |
| [richennacht/demod](https://github.com/richennacht/demod) | 27 Sep (new) | Python | WAV/IQ measurements, ranked hypotheses, JSON report; explicitly no blind FEC | 9 | Honest, early |
| [kunal-shetty/SIH2026_Signal_Intelligence_Recognition_Engine](https://github.com/kunal-shetty/SIH2026_Signal_Intelligence_Recognition_Engine) | 13 Sep (new) | FastAPI + React | ResNet-18 on RadioML 2016.10a (11 classes) | 0 | AMC only |
| [Venkata-Manoj/RF-signal-analysis](https://github.com/Venkata-Manoj/RF-signal-analysis) | 25 Sep (new) | PyQt6 desktop + web dashboard + CLI | Block/Forney/diagonal/pseudo-random de-interleaving; CRC-16/32, Viterbi, RS, LDPC, concatenated, all from scratch; sweeps 30 FEC × interleaver combinations gated on CRC-16 (420-case sweep); tested on two real PySDR captures (GPS L1, NTSC), honestly reporting no decode | 56 | **Strongest newcomer**; catalogue sweep rather than blind identification; no licence |
| [Kush11318/IQWAVE](https://github.com/Kush11318/IQWAVE) (DAWC) | 29 Sep (new) | FastAPI + JS lab UI | LLRs, blind FEC ID, CRC-16/32 by GF(2) division, rank-profile de-interleaver; "258/258 tests" 📄 | 15 | MIT; claims broad, verify before quoting |
| [GSRaghav/Analysis-of-signal-files](https://github.com/GSRaghav/Analysis-of-signal-files) (AutoSig-Intel) | 26 Sep (new) | Streamlit, 9 tabs | 4 interleaver families; Viterbi K=7/K=3, RS, concatenated, Gallager (12,6) LDPC; blind LDPC disclosed as not implemented; "127 tests" 📄 | 17 | Honest disclosure; toy LDPC |
| [anshumanarchit-crypto/SIH_Wavemindss](https://github.com/anshumanarchit-crypto/SIH_Wavemindss) (SpectralQ) | 29 Sep (new) | Streamlit | Cyclic baud, M2M4 SNR, cumulants, ML + rule AMC; matrix and convolutional de-interleavers; Viterbi K=7, RS(255,223), BCH; CRC-16/32 | 17 | Solid mid-tier |
| [dev-mat-4522/spectra-sense-signal-parameter-extraction](https://github.com/dev-mat-4522/spectra-sense-signal-parameter-extraction) (SpectraSense) | 28 Sep (new) | Python | Burst extraction, multi-voter baud rate, CNN-heuristic AMC incl. 64QAM/AFSK, 4 phase rotations, block/diagonal/convolutional de-interleavers, Viterbi + RS probing; float32 IQ only | 10 | Mid |
| [lileshkatre01/DrishtiRF](https://github.com/lileshkatre01/DrishtiRF) | 29 Sep (new) | FastAPI + Celery + React | Parameter estimation incl. fs, AMC, joint de-interleaving + FEC, bitstream correlation; "real captured waveforms" in `sample_data/` 📄 | 11 | Claims unverified; heavy stack |
| [rajivdey2/Wave](https://github.com/rajivdey2/Wave) | 28 Sep (new) | FastAPI, hosted on Render | Multi-signal detection (CFAR), parameters, classical + ML classification with evidence per field, JSON + SigMF output; publishes accuracy vs SNR (100 % at ≥ 5 dB, UNKNOWN at −5 dB) | 12 | No FEC; honest numbers |
| [rezowanhussain02/SignalScope](https://github.com/rezowanhussain02/SignalScope) | 28 Sep (new) | React + FastAPI | Random Forest AMC (BPSK/QPSK/2-FSK/16QAM), block de-interleaving, Viterbi | 6 | Mid–low |
| [iamsayandas2-blip/IQWAV](https://github.com/iamsayandas2-blip/IQWAV) | 6 Sep (new) | Python + notebooks | Heuristic detection of spectrally significant candidates; FEC and interleaving planned | 29 | Early but tested |

### 5.4 Early stage or placeholder

15 files or fewer, or no README: [gourabde7/Spectra](https://github.com/gourabde7/Spectra) (★1), [Muizzahmed786/SIH26147](https://github.com/Muizzahmed786/SIH26147), [xarjunpatil/SIH26147-…](https://github.com/xarjunpatil/SIH26147-Automated-model-for-analysis-of-IQ-and-wav-files-along-with-signal), [Jagzz-Coder/sigscope](https://github.com/Jagzz-Coder/sigscope), [sautiksamui-tech/SIH2026](https://github.com/sautiksamui-tech/SIH2026), [dharsankumar250053-spec/SignalLens](https://github.com/dharsankumar250053-spec/SignalLens), [dasmahapatrapranati-rgb/Signal_Analyzer](https://github.com/dasmahapatrapranati-rgb/Signal_Analyzer), [26147-alt/index](https://github.com/26147-alt/index), [harideskzone-hue/SIH26147-Border](https://github.com/harideskzone-hue/SIH26147-Border) (empty); new since 26 Sep: sumitsawant562-source/SIH-PROJECT---SIH26147, hn260/signalscope, VASANTH-Balaji/signal-analyzer-webapp, AtharvaSharma27/.IQ-.WAV-signal-analyzer-, and empty Ardcode12/IQ_WAV, shreyxshh/iq-and-wav, deepanshushrivas/.IQ-and-.wav-signal. UI or analytics only, no decoding: [25A31A0454/SpectrumX](https://github.com/25A31A0454/SpectrumX) (React dashboard, `node_modules` committed), [GaurangJagtap/Radio-Frequency-Signal-Analyzer](https://github.com/GaurangJagtap/Radio-Frequency-Signal-Analyzer) (PyQt5 UI on mock data), [SrishtiPriya27/signalscope](https://github.com/SrishtiPriya27/signalscope) (frontend with simulated results), [adityabisoyee28-cpu/SignalLens-AI](https://github.com/adityabisoyee28-cpu/SignalLens-AI) (Random Forest on 6 analog classes, Supabase), [palanisamysantosh2-creator/SIGNAL-ANALYZER](https://github.com/palanisamysantosh2-creator/SIGNAL-ANALYZER) (Streamlit wrapper).

### 5.5 Status changes and corrected claims since the first scan

| Repo or earlier claim | Now |
|---|---|
| `SumitKumar00113/sigma-signal-analysis` ("PySide6 GUI; ingestion; IQ-imbalance checks") | Renamed `sigma-signal-analysis-SIH-2026` (the old URL redirects); the **most capable repo in the field** (§5.2) |
| `mks-Roald/ps26147_toolkit` (CLI + Streamlit, RF on RadioML 2016.10a) | A 404 on 26 Sep (deleted, renamed or private); live again on 30 Sep (§5.3) |
| `harikesh2709-creator/FUTURISTICS` ("full DSP chain") | Now **FreightForecast Pro**, a maritime freight app for another PS; the team's SIH26147 repo is `spectra-signal-analyzer`, created 25 Sep |
| `Akshat030307/SIH` ("now does multi-signal scene analysis") | Only planned: phase 3 of 8 in progress, last push 1 Sep |
| "Real over-the-air validation is a differentiator" | Already done by sigma, ICHNOVA and IQWAV |
| "14+ repos" | **35 live repos** on 26 Sep, about 26 with substantive code; about 60 and 40 by 30 Sep (§1) |

---

## 6. Engineering lessons from rivals (free bug reports)

Bugs other teams found by testing against ground truth; design them out. Credit to the repo named.

1. **Silent sample-rate defaults.** One repo shipped with the rate defaulting to 1 Hz; Nova-Signum defaults raw `.iq` to 1 MHz. *Rule:* an unresolved rate means frequency-dependent stages are skipped with a stated reason. (Devansh-567, Pinpoint)
2. **SNR and detection unit errors.** Comparing a PSD-per-Hz noise floor against total time-domain power put the detection threshold about 30 dB too low. *Rule:* integrate over bandwidth and unit-test the dimensions. (Devansh-567 #1, #13)
3. **RRC needs a matched filter.** A single RRC is not zero-ISI; after matched filtering the correct sampling phase was 0, not `sps//2`. (Devansh-567 #2, #3)
4. **QAM breaks naive M-th-power carrier recovery.** Gate it on peak-to-median ratio, or skip it. (Devansh-567 #5)
5. **`reedsolo.RSCodec` does not pad to n:** it appends n−k parity bytes to any payload length. (Devansh-567 #11)
6. **A successful RS decode with a weaker preset can be wrong.** An `rs_255_239` decode of `rs_255_223` data reported success with 0 corrections and returned the wrong bytes. *Rule:* prefer more parity, and always cross-check with CRC or sync. (Devansh-567 #12)
7. **scikit-commpy's `Trellis` overflows for K ≥ 8** under current NumPy. (Devansh-567)
8. **False FEC from repetition and half-element sampling:** such streams satisfy parity checks by chance. *Rule:* reject a candidate when a trial decode leaves more than about 12 % channel errors, or more than the EVM allows. (sigma)
9. **False framing from idle patterns.** *Rule:* require at least 64-bit frames with varying payload, and significance-test any counters. (sigma, RadioFry)
10. **Symbol-rate harmonics beat the fundamental** on long captures. *Rule:* rank candidates by their harmonic comb. (sigma)
11. **FM carrying audio looks like FSK/PSK.** *Rule:* check the FM discriminator output first. (sigma)
12. **FastAPI route order:** `/analyses/{id}` registered before `/analyses/compare` swallows `compare`. (Devansh-567 #18)
13. **Benchmark hygiene:** a "sealed" set inspected during development is only a regression tripwire; keep a truly held-out set. (ICHNOVA)
14. **Quadrature is evidence, not proof:** stereo audio can pass the IQ check. Record the heuristic and let the analyst override it. (Pinpoint)

---

## 7. Table stakes vs open differentiators

**Table stakes** (do all or lose credibility): SigMF in/out; raw cf32/ci16/ci8/cu8 with explicit format; honest mono-WAV handling; per-parameter provenance and evidence levels, no silent defaults; spectrum, waterfall, constellation, eye diagram; PSK/QAM/FSK demodulation with real sync loops; all four interleaver families; Viterbi, RS, concatenated and LDPC; CRC/sync-word/re-encode verification; JSON/PDF/SigMF reports; offline operation; a pytest suite and CI.

**Open differentiators** (no public rival does these as of the 30 Sep scan):

| # | Differentiator | Closest rival and its gap |
|---|---|---|
| D1 | **Deep-learning AMC evaluated on public datasets** (RadioML 2018.01A, TorchSig/Sig53, HisarMod) with a full −20 to +30 dB curve, calibration and open-set noise rejection | sigma and Devansh evaluate only on their own synthetic data; RadioFry's RadioML models are "experimental, not production" |
| D2 | **Web GUI (React/TS, WebGL) with sigma-level blind decoding depth**, running air-gapped | The deepest decoders are desktop apps (sigma, Vertex); the web apps (Devansh, SignalScope, Pinpoint) decode far less |
| D3 | **Open sealed benchmark plus head-to-head results** against public rival tools, including a null set for false-accept rate | ICHNOVA's sealed set is 30 files, BPSK/QPSK only; nobody benchmarks rivals |
| D4 | **Committed, licensed, Indian over-the-air recordings** with protocol-level ground truth (Indian NAVTEX and other HF via KiwiSDR, ADS-B CRC once pulse-position demodulation exists, AIS CRC, Meteor-M LRPT; NOAA APT and FM RDS only if confirmed on air in India) | sigma's recordings aren't in its repo; ICHNOVA's are mostly foreign time stations |
| D5 | **Analyst-in-the-loop:** correct any stage and every later stage re-runs automatically, with a before/after diff | Devansh re-runs 3 overrides and only records feedback; sigma's workbench is manual |
| D6 | **Multi-GB streaming through the entire chain**, not just detection | Pinpoint streams 2 GiB (detection only); sigma stops at 10 M samples |
| D7 | **Overlapping co-channel and frequency-hopping signals** (detect and label, even when decoding isn't possible) | No rival attempts this |
| D8 | **Transparent hypothesis accounting in the UI:** how many code/interleaver guesses were tried, the corrected threshold, the empirical false-alarm rate on shuffled bits, why each was rejected | ICHNOVA and sigma compute it but don't expose it as an analyst view |
| D9 | **An open, benchmarked implementation of the literature's blind code and interleaver identification methods, chained from raw IQ:** GJETP/dual-code for convolutional and punctured codes, GFFT for RS, rank-drop and KS tests for interleavers, soft syndrome scoring for LDPC. Blind FEC itself is *not* unique (sigma; R&S CA250 for conv/RS/BCH); the claim is the open, benchmarked implementation plus automatic interleaver recovery in the same chain | sigma uses its own methods, unbenchmarked against the literature; vendors document no automatic interleaver recovery; deep-learning papers release no code |

**Talking point for judges:** RadioML, the dataset most rivals cite, has SNR labels off by tens of dB, a noise-only AM-SSB class (2016.10a), a wrong class-name mapping in 2018.01A, and a non-commercial licence. We train on our own impaired generator and use RadioML only as a benchmark, with corrected labels.

---

## 8. Our bar — measurable targets

**Targets, not claims.** A number moves into the deck only after a `bench/` script reproduces it.

| Area | Metric | Best public rival today | Our target |
|---|---|---|---|
| Ingestion | Formats and input routes | Full SigMF vocabulary (Devansh-567) | Full SigMF vocabulary; raw files in all 28 datatypes, LE/BE; WAV mono/stereo with a quadrature check, including RF64/Wave64; `.sdriq`, MIDAS Blue, VITA 49 recordings, compressed audio; path, upload, folder, sequence, CLI and local receiver capture; **0 silent defaults** (tested) |
| Known systems | Public systems matched after blind analysis | Not published | Every 1.0 catalogue entry (CCSDS TM coding and TM LDPC, Meteor-M LRPT, AIS, NAVTEX, MF/HF DSC, POCSAG; PLAN M6) VERIFIED on its synth preset; **0 false system matches** on the null set; real-capture agreement with reference decoders reported in PLAN M8 |
| Scale | Largest file processed | 2 GiB, detection only (Pinpoint) | **≥ 4 GiB** streamed through detection, and the full chain on every selected signal |
| Detection | Recall / false detections on a multi-signal bench | Not published | ≥ 95 % recall, ≤ 5 % false detections at ≥ 6 dB in-band SNR |
| Estimation | Symbol rate / SNR / CFO error | sigma: SNR within 0.3 dB, rate within 1 Hz on its own files | Rate ≤ 0.1 % at ≥ 10 dB; SNR ±1 dB over 0–20 dB; CFO ≤ 1 % of Rs, per SNR bucket |
| AMC, public data | RadioML 2018.01A, 24 classes, held-out, **corrected SNR labels** | None published; ~10K-parameter models reach about 58–60 % averaged / 92–96 % peak in papers | ≥ 93 % at SNR ≥ +10 dB; ≥ 55 % averaged over all 26 SNRs (stretch 60 %); full curve published with a ≤ 50K-parameter model |
| AMC, open set | Held-out modulations as unknowns, per SNR bin | None published | AUROC ≥ 0.90 at ≥ 6 dB; FPR@95 %TPR and OSCR reported |
| AMC, real signals | Accuracy on labelled real captures (PLAN M8) | None published; papers show about 96 % → 35 % sim-to-real drops | Report before/after fine-tuning; target ≥ 85 % at ≥ 10 dB |
| AMC, in scope | ≥ 12 digital classes, TorchSig-impaired, **independent** generator | sigma: 99 % at 4 dB, own synthetic | ≥ 95 % at ≥ 6 dB; ≥ 80 % at 0 dB; noise-only rejection ≥ 99 % (unseen modulations: the open-set row) |
| FEC ID: convolutional | Code + generators + puncturing, soft decisions | sigma: works "at several percent BER" | ≥ 95 % at raw channel BER ≤ 2 % (K ≤ 7), with LLR input |
| FEC ID: RS | n, k, field polynomial, first root, alignment | sigma: identifies with errors present | ≥ 95 % at symbol-error rate after the inner decoder ≤ 1 % (or on uncoded-inner streams at channel BER ≤ 10⁻³) |
| FEC ID: LDPC | Catalogue matrix + alignment | sigma: standards catalogue | ≥ 95 % at Es/N0 ≥ the code's decoding threshold + 1 dB, via soft syndrome scoring |
| False accepts | Accepted decodes on a null set (noise, uncoded, random) | ICHNOVA: 0 on 130 files | **0 on ≥ 1,000 null files** (95 % upper bound ≤ 0.3 %) |
| Interleaver ID | Block / diagonal / convolutional with an inner code | sigma (not quantified) | ≥ 90 %; pseudo-random either matched to a standard permutation (3GPP, LTE QPP, 802.11, DVB-S2) or UNKNOWN with its measured period, **never a false VERIFIED** |
| Framing | Blind sync-discovery false alarm | sigma: 10⁻⁶ | ≤ 10⁻⁶ per stream, reported |
| Real signals | Committed over-the-air recordings | ICHNOVA: 7 stations | ≥ 10 recordings, ≥ 6 services, ≥ 4 captured in India, each with SigMF provenance and a licence |
| Speed | Full chain, 10 M samples, 4-core laptop CPU | sigma: ≈ 2 s on a 2.5 s multi-burst file | ≤ 10 s, excluding blind LDPC catalogue search |
| Offline | Outbound connections at runtime | Most claim it; none test it | 0, enforced by a socket-blocking test |
| Quality | Automated tests / CI | IQWAV: 861 claimed; RadioFry: 79 test files | ≥ 300 tests + Playwright E2E; CI green on every PR |

**Why FEC targets are per family:** a flat "95 % at 3 % BER" can't be met for long codes. Hard-decision rank methods need error-free rows, and at 3 % BER a 2,040-bit RS(255,223) row is clean with probability 0.97²⁰⁴⁰ ≈ 10⁻²⁷.

---

## 9. Competitive matrix — draft for the idea deck

Our column shows **targets** and must say so on the slide; the point is to show we know the field better than anyone.

| | Us (target) | sigma | ICHNOVA | Devansh-567 | Team Vertex | Krypto500 |
|---|---|---|---|---|---|---|
| Open source & indigenous | ✅ | ✅ MIT | ✅ | ✅ | ✅ | ❌ ITAR |
| Web GUI, air-gapped | ✅ | Desktop | ✅ | ✅ | Desktop + web | Desktop |
| Blind FEC (conv + RS + LDPC) | ✅ | ✅ | Conv only | Conv + RS | Catalogue | Not documented |
| Automatic interleaver recovery chained to FEC | ✅ | ✅ (incl. PR seed search) | Block | ✅ | Catalogue | Not documented |
| Verified decode + false-accept rate published | ✅ | Partial | ✅ | ❌ | Partial | ? |
| DL AMC on public datasets | ✅ | ❌ | ❌ | ❌ | ❌ | ? |
| Committed Indian off-air recordings | ✅ | ❌ | AIR carriers | ❌ | ❌ | — |
| Analyst correction → automatic re-run | ✅ | Manual | ❌ | Partial | ❌ | ? |
| Literature blind-ID methods (GJETP / GFFT / rank-drop), open + benchmarked | ✅ | Own methods | Syndrome test | Trial search | Catalogue | ? |
| Multi-GB full-chain streaming | ✅ | ❌ | ❌ | ❌ | ❌ | ? |

---

## 10. How to refresh this document

- **Automated:** the `rival-scan` custom skill ([CLAUDE_SKILLS_MCP §7](../.claude/CLAUDE_SKILLS_MCP.md#7-custom-project-skills); not created yet) will re-run the searches and diff the results against this file. Until then, run the queries below by hand.
- **Queries used on 26 and 30 Sep:** `SIH26147`, `SIH 26147`, `26147`, `26147 in:readme`, `iq wav signal`, `iq wav analysis`, `blind signal analysis`, `signal parameter extraction`, `blind fec`, `interleaver identification`, `NTRO`, `rf signal intelligence created:>2026-08-15`, `26147 in:name,description,readme`, `iq wav signal parameter extraction`, `NTRO signal analysis`, `automated model analysis .IQ .wav`, `modulation classification iq wav created:>2026-08-15`, `sigmf created:>2026-08-20`.
- **Before each pitch:** re-check the top 8 (`gh api repos/OWNER/REPO/commits?per_page=15`); sigma, ICHNOVA, Pinpoint and arachknight66 were all pushed the day before the 30 Sep scan.
- **Unauthenticated GitHub API limit:** 60 requests/hour; `gh auth login` raises it.

---

## 11. References

Verified against publisher records (Crossref, arXiv, vendor PDFs) on 29–30 Sep 2026. Plan methods cite these by author and year.

**Methods**
1. O'Shea, Roy & Clancy, "Over-the-Air Deep Learning Based Radio Signal Classification", IEEE JSTSP 12(1):168–179, 2018, doi:10.1109/JSTSP.2018.2797022 — deep AMC; RadioML baseline.
2. Marazin, Gautier & Burel, "Blind recovery of k/n rate convolutional encoders in a noisy environment", EURASIP JWCN 2011:168, doi:10.1186/1687-1499-2011-168 — dual-code convolutional recovery. Punctured codes: Marazin et al., IET Signal Processing 6(2):122–131, 2012, doi:10.1049/iet-spr.2010.0343.
3. Su et al., Scientific World Journal 2014, doi:10.1155/2014/798612 — correlation search over the dual vector (convolutional identification, M5).
4. Sicot, Houcke & Barbier, "Blind detection of interleaver parameters", Signal Processing 89(4):450–462, 2009, doi:10.1016/j.sigpro.2008.09.012 — GF(2) rank: interleaver period and frame sync.
5. Wee, Choi & Jeong, "Blind Interleaver Parameters Estimation Using Kolmogorov–Smirnov Test", *Sensors* 21(10):3458, 2021, doi:10.3390/s21103458 (not *Entropy*; not the similarly titled Kim et al., J. KICS 2020).
6. Swaminathan, Madhukumar, Wang & Kee, "Blind Reconstruction of Reed-Solomon Encoder and Interleavers Over Noisy Environment", IEEE Trans. Broadcasting 64(4):830–845, 2018, doi:10.1109/TBC.2018.2795461.
7. Moosavi & Larsson, "Fast Blind Recognition of Channel Codes", IEEE Trans. Commun. 62(5):1393–1405, 2014, doi:10.1109/TCOMM.2014.050614.130297 — soft syndrome test for catalogue codes (LDPC).
8. Xu, Zhong & Huang, IEEE Access 7:101775–101784, 2019, doi:10.1109/ACCESS.2019.2930663 — convolutional (Forney) interleavers.
9. Jeong, Yoon, Lee & Choi, ICICS 2011, doi:10.1109/ICICS.2011.6174276 — helical-scan (diagonal) interleavers.
10. Qin et al., PLoS ONE 2015, doi:10.1371/journal.pone.0132114 — blind frame sync by column constancy (M6).
11. G. Ewing, "Reverse-Engineering a CRC Algorithm" (2010), https://www.csse.canterbury.ac.nz/greg.ewing/essays/CRC-Reverse-Engineering.html — the differential (XOR) method behind blind CRC recovery (M6). CRC RevEng implements it but is GPL: method reference only.
12. No paper recovers an absolute sampling rate from samples alone (time and rate scale together); Sanket ranks candidates and promotes one only by a structural match.

**Standards**
- CCSDS 131.0-B-5 (Sep 2023), TM synchronisation and channel coding: ASM `1ACFFC1D`, K=7 (171,133 octal), RS(255,223)/(255,239), interleave depths 1–5 and 8. CCSDS 132.0-B-3 (Oct 2021), TM space data link.
- ITU-R M.1371-6 (02/2026) AIS; M.493-16 (12/2023) DSC; M.540-2, M.476-5, M.625-4 NAVTEX; M.584-2 paging (POCSAG).
- SigMF v1.2.6 (Dec 2025), spec CC BY-SA 4.0.
- Meteor-M LRPT has no official public specification. Community decoder documentation gives QPSK 72 kBd and an 80 kBd interleaved OQPSK mode (36 branches × 2,048 symbols, 8-bit sync every 80 symbols) over CCSDS coding ([usradioguy](https://usradioguy.com/meteor-satellite/), [Libre Space forum](https://community.libre.space/t/oqpsk-for-meteor-mn2-2-lrpt/4383), [SatNOGS DB M2-4](https://db.satnogs.org/satellite/VSVI-4798-5613-4587-2414/)). Confirm on real recordings before relying on it.

**Datasets**
- RadioML 2018.01A (DeepSig): synthetic with simulated channel effects (not over-the-air), 24 classes, 26 SNRs (−20…+30 dB), 2,555,904 × 1,024 IQ, CC BY-NC-SA 4.0. Documented flaws (SNR labels off by tens of dB, a noise-only AM-SSB class in 2016.10a, a wrong `classes.txt` in 2018.01A) from C. Spooner's CSP Blog (Aug and Sep 2020) and radioML/dataset GitHub issue #25.
- TorchSig (MIT): Sig53/WidebandSig53 (Boegner et al., arXiv:2207.09918) renamed Narrowband/Wideband in v0.6.0; 2.x is a configurable generator.
- HisarMod2019.1: 26 classes, 5 channel types, 780,000 × 1,024 IQ, −20…18 dB, doi:10.21227/8k12-2g70 (label quality questioned).
- Real Meteor-M2-4 LRPT CF32 recordings with decoded images: [Kishore-T20/meteor-m2-4-cf32-dataset](https://github.com/Kishore-T20/meteor-m2-4-cf32-dataset) (Sep 2026), relevant to the M8 satellite target but **no licence**, so usable only with the author's permission. [LakeShark Signal Corpus](https://github.com/SAMS0N1TE/LakeShark-Signal-Corpus) (MIT repo, CC0/CC-BY recordings, reviewed SigMF `cu8`) was still empty on 13 Sep.
- Real-World IQ (Mendeley Data, Jan 2026): 7 classes, 1,024-sample frames, over the air, CC BY 4.0, doi:10.17632/tjzsbph49x.2. "CORAL" is a domain-adaptation method, not a dataset.

**Law (India)**
- Telecommunications Act 2023 (No. 44): §20 (lawful interception) in force 26 Jun 2024 (S.O. 2408(E)); §3(1) (authorisation, incl. possessing radio equipment) reportedly notified 23 Jun 2026 (secondary report; S.O. number not found); Interception Rules 2024, G.S.R. 754(E). The Feb 2025 draft rules, which replace the 1965 possession rules, don't clearly exempt a hobby SDR receiver, so our own over-the-air capture is a grey area; whether final rules have replaced the draft is unconfirmed.
