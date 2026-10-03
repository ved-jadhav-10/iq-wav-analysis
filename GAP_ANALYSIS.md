# Sanket — Gap Analysis vs SIH26147 Rivals

> Snapshot: **2 Oct 2026**. Based on [STANDARDS_TO_BEAT.md](file:///d:/Coding/Projects/Personal/iq-wav-analysis/docs/STANDARDS_TO_BEAT.md) (re-scanned 30 Sep) and the current codebase tree.

---

## 1. What Sanket Already Has (Verified in Code)

| Area | What's built |
|---|---|
| **Ingest** | All 28 SigMF datatypes, WAV (RIFF/RF64/Wave64 mono+stereo), SigMF archives, `.sdriq`, MIDAS Blue, VITA 49, FLAC/MP3/Ogg, `.gz`/`.zip`, `.npy`, numbered sequences. **0 silent defaults** tested. |
| **Evidence model** | `Parameter{level, confidence, method, proof, ...}` in [`dsp/evidence.py`](file:///d:/Coding/Projects/Personal/iq-wav-analysis/dsp/src/dsp/evidence.py); 5-level taxonomy (VERIFIED / MEASURED / ESTIMATED / HYPOTHESIS / UNKNOWN); `needsReview` surfaced automatically |
| **Detection** | OS-CFAR + split-sample significance (Bonferroni), morphology, multi-FFT merge; **0 false detections on 600 pure-noise scenes** (fixed 2 Oct) |
| **Estimation** | Symbol rate (|x|² line), SNR (PSD-moments + M2M4 + EVM), CFO (M-th power, gated for QAM), RRC roll-off fit, cumulants, capture quality (clipping / DC / IQ imbalance / gaps) |
| **Demodulation** | BPSK / QPSK / 8PSK / 16QAM / 64QAM (Gray LLRs); Offset-QPSK (Meteor-M LRPT); 2/4/8-FSK (non-coherent, max-log LLRs); eye diagram |
| **FEC** | Viterbi K=7 r½ (soft), blind rate-1/n convolutional identification (`convident.py`), RS(255,223) (Numba decoder), LDPC catalogue (802.11n, CCSDS TC/TM — 7 codes in the chain), punctured-code grid |
| **De-interleaving** | Block (catalogue + blind), Helical, 802.11, QPP, Convolutional/Forney (catalogue grid); blind block-interleaver search (`blind_interleaver.py`) |
| **Framing** | CCSDS ASM sync word, 31-entry CRC catalogue, blind framing (`blind_framing.py`), shuffled-bit false-alarm runs; Bonferroni-corrected over all hypotheses tried |
| **Known systems** | CCSDS TM coding, CCSDS TM LDPC, POCSAG, NAVTEX/SITOR-B, MF/HF DSC, AIS/GMSK — each VERIFIED by its own check, Holm-corrected at α = 10⁻⁶ |
| **Hypothesis ledger** | Every blind search writes every candidate + p-value + corrected threshold + outcome → rendered in the UI (D8 differentiator) |
| **Scale** | 4 GiB streamed, RSS < 512 MiB |
| **Null safety** | **0 accepted decodes on 1,000 null files** (noise / uncoded / repetition / idle) after each widening of the blind search |
| **GUI** | React 19 + TS + Tailwind 4; WebGL2 waterfall; uPlot PSD; constellation / eye / FSK; evidence cards; ledger; frames; Assumptions modal; guided tour; WCAG AA; dark + light themes |
| **Build** | PyInstaller one-folder (Windows tested), pywebview desktop window, offline `sanket.exe` smoke-tested |
| **CI** | GitHub Actions (Windows + Ubuntu); ruff + pyright + pytest + Playwright; licence check fails on GPL/AGPL |
| **Demo scenes** | 9 synthetic SigMF recordings bundled; ground truth verified frame-by-frame |

---

## 2. Shortcomings — Open Gaps vs the PS and Rivals

### 2.1 Critical (blocks PS requirements R1–R5)

| # | Gap | Rival that does it | Evidence in code |
|---|---|---|---|
| **G1** | **ML/AMC model not built.** `ml/src/ml/__init__.py` is the only file in the ML package. Modulation classification is cumulant-ranking only; no CNN, no ONNX model, no open-set rejection. | sigma (gradient boosting, 18 types); Devansh-567 (1D CNN, 68–70%); RadioFry | [`ml/src/ml/__init__.py`](file:///d:/Coding/Projects/Personal/iq-wav-analysis/ml/src/ml/__init__.py) is empty — no model code at all |
| **G2** | **No over-the-air (real) recordings committed.** Benchmark and demo are 100% synthetic. sigma decodes real NAVTEX/RTTY/APT; ICHNOVA commits 7 real stations with GPS timestamps. | sigma, ICHNOVA, IQWAV | README §68–82 lists *synthetic* recordings only |
| **G3** | **Analyst overrides (`POST /jobs/{id}/overrides`) not yet wired.** The API endpoint is planned in PLAN §3 but not in the built endpoint list (§126). Correcting a stage does not re-run downstream. | Devansh-567 (3 overrides, partial) | [`backend/src/backend/app.py`](file:///d:/Coding/Projects/Personal/iq-wav-analysis/backend/src/backend/app.py) — only `PUT /recordings/{id}/assumptions` exists |
| **G4** | **Export menu incomplete.** JSON/CSV/PDF/SigMF exports listed in PLAN §3 but only the JSON schema exists; the PDF and SigMF annotation exports are not built. | Devansh-567, sigma | [`backend/src/backend/app.py`](file:///d:/Coding/Projects/Personal/iq-wav-analysis/backend/src/backend/app.py) — no `GET /jobs/{id}/export.*` routes |

### 2.2 Important (weakens competitiveness vs top-8 rivals)

| # | Gap | Detail | Who fills it |
|---|---|---|---|
| **G5** | **Blind LDPC not in the chain.** The 7 catalogue codes are tried but CCSDS C2, DVB-S2 and 5G NR are listed as "still open" in PLAN §0. Soft syndrome scoring (Moosavi & Larsson) not implemented. | PLAN §0 item 2 | sigma (DVB-S2, 5G NR, CCSDS, Wi-Fi) |
| **G6** | **Convolutional interleaver found blind not implemented.** The Forney grid is catalogue-only; blind Forney (Xu et al. 2019) is listed as open. | PLAN §0 item 1 | sigma (incl. PR seed search) |
| **G7** | **FSK symbol rate fails at low SNR (< 10 dB Es/N0) and on crowded channels.** This is an explicit open gate in PLAN §0. Needed for robust 2-FSK decode (NAVTEX, RTTY). | PLAN §0 M-FSK open gate | sigma, ICHNOVA |
| **G8** | **No closed-loop sync (Gardner/Costas).** Feed-forward only. Doppler-drifting signals (LEO passes ±3.5 kHz) lose frames above 10⁻⁸ cycles/sample² drift. | PLAN §0 M3 open item | sigma (Gardner + Farrow + Costas); arachknight66 (Costas) |
| **G9** | **No Drift tracking.** Frequency drift rate as an ESTIMATED parameter is listed as open (M2). | PLAN §0 M2 | arayush-RF_MVP, sigma |
| **G10** | **No structured bit-stream correlation view** (header/payload field identification). The Frames tab shows raw bits + ASCII but no pattern-based field finder. | PS R5 ("bit stream correlation for identification of header and payload") | Devansh-567, SignalScope |
| **G11** | **Sealed benchmark not yet run.** PLAN §1 says "sealed set never run during development." A head-to-head comparison against rivals (D3) is thus impossible right now. | ICHNOVA (0 false accepts, 30-file sealed set); Pinpoint (170-capture frozen set) | — |
| **G12** | **SSB / CW / analog audio measurements incomplete.** FM demodulation measurements are built; SSB and CW synth generators listed as open. Audio playback is explicitly out-of-scope for 1.0 but rivals offer it. | sigma (NAVTEX text, RTTY text, APT images) | — |

### 2.3 Engineering / Robustness

| # | Gap | Detail |
|---|---|---|
| **G13** | **First tile > 2 s** (open gate). `RecordingStore.open` builds the whole pyramid before returning. | PLAN §0 |
| **G14** | **Wide-channel decimation-1 leak.** Neighbours not filtered out at decimation-1; filtering breaks `snr_psd`. | PLAN §0 |
| **G15** | **Real/complex tie carried as two branches** not yet implemented — the complex-by-convention rule remains. | PLAN §0 |
| **G16** | **OpenAPI-generated frontend types** not done — hand-written `lib/api.ts` drifts from the schema. | PLAN §0 |
| **G17** | **Blind code search decodes cells that share bits** (speed hole: punctured grid runs redundant decodes). Partially addressed by the Viterbi per-step change, but the grid restructuring is open. | PLAN §0 null-bench notes |

---

## 3. Feature-by-Feature Table vs the PS (R1–R5)

| PS Requirement | Sanket state | Gap |
|---|---|---|
| **R1** Sampling frequency, modulation, FEC, interleaving identification | **Partial.** Format sniffer, cumulant modulation ranking, convolutional/RS/LDPC (catalogue), 4 interleaver families. | No ML model (G1); blind LDPC not fully chained (G5); blind convolutional interleaver (G6) |
| **R2** Demodulate FSK, QAM, PSK | **Mostly built.** BPSK/QPSK/8PSK/16QAM/64QAM/OQPSK + 2/4/8-FSK with LLRs. | No closed-loop sync (G8); FSK rate fragile at low SNR (G7) |
| **R3** De-interleaving: Block, Convolutional, Diagonal (helical), Pseudo-random | **Block/helical/QPP/802.11 in catalogue; blind block implemented.** Convolutional (Forney) catalogue only. | Blind convolutional interleaver (G6); pseudo-random seed search not implemented |
| **R4** FEC: short conv (Viterbi), RS block, concatenated, LDPC | **Viterbi K=7 soft ✅; RS(255,223) ✅; concatenated RS+conv ✅; LDPC 7-code catalogue ✅.** | DVB-S2 / 5G NR / CCSDS C2 LDPC not in blind chain (G5) |
| **R5** Bit stream correlation (header / payload identification) | **Partial.** Frames tab shows bits + sync-word recurrence; blind CRC recovery. | No structured field-finder / pattern correlator (G10) |

---

## 4. Differentiators That Are Genuinely Ahead of All Rivals

| # | Sanket advantage | Status |
|---|---|---|
| **D2** | Web GUI (React/TS/WebGL) with sigma-level blind decoding depth (the deepest decoders are all desktop apps) | ✅ Built and running |
| **D8** | Transparent hypothesis ledger in the UI: tried count, corrected threshold, shuffled-bit false-alarm rate, per-rejection reason | ✅ Built |
| **D9** | Open, benchmarked blind-ID methods (GJETP dual-code, GFFT RS, rank-drop interleaver, soft syndrome LDPC) chained from raw IQ | Partially built; GFFT RS and soft-syndrome LDPC open |
| **D6** | ≥ 4 GiB full-chain streaming | ✅ Detection/estimation built; decoding chain not yet streamed at this scale |
| **D3** | Open sealed benchmark | ❌ Sealed set never run |
| **D1** | DL AMC on public datasets (RadioML 2018.01A, full SNR curve) | ❌ No ML code yet |
| **D4** | Committed Indian off-air recordings | ❌ Not started |
| **D5** | Analyst correction → automatic downstream re-run | ❌ Override API not wired |

---

## 5. Priority Order for the Next Sprint

1. **Wire analyst overrides** (G3) — judges will demo it; Devansh-567 gets credit for doing 3.
2. **Run the sealed benchmark** (G11) — needed before any pitch; current null-bench pass is necessary but insufficient.
3. **Build the AMC/CNN model** (G1) — the biggest capability gap vs rivals and the PS.
4. **Commit ≥ 10 real recordings** (G2) — ICHNOVA's committed recordings with GPS metadata are highly credible to judges.
5. **Close FSK rate at low SNR** (G7) — needed for NAVTEX/RTTY ground-truth demos.
6. **Complete export menu** (G4) — PDF + SigMF annotation are table stakes.
7. **Blind LDPC in the chain** (G5) — DVB-S2 is the flagship for LDPC demos.
8. **Bit-stream field correlator** (G10) — directly addresses PS R5.

---

> [!NOTE]
> The null-bench result (0 false accepts on 4,373 detections across 1,000 noise/uncoded files) is the strongest verified safety property in any public SIH26147 repo. That number must be kept green after every expansion of the blind search.

> [!WARNING]
> The ML package (`ml/`) is completely empty. If judges ask for an AMC demo, there is nothing to show. This is the single largest credibility risk.
