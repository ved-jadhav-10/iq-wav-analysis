# Sanket — progress log

A dated history of what landed, newest first. It is append-only: current status lives only in [PLAN §0](PLAN.md#0-progress), and each entry here is written once, when its work lands. Numbers link to `bench/results/`.

## 30 Sep 2026 — docs consolidated, rivals re-scanned

- One plan: the separate prototype/demo track is gone, and its work is recorded as built items in PLAN's milestones. The dossier, Q&A, prototype plan, demo guide and research reports were folded into PLAN, PROBLEM_STATEMENT, STANDARDS, UI and README, then deleted.
- PROBLEM_STATEMENT gained requirement IDs R1–R5 and G1–G3, our reading of each, and the confirmed SIH 2026 facts.
- STANDARDS got the 29 Sep research corrections: the Krypto500 price is from a 2012 review; the W-CODE price was dropped; R&S CA250 and Wavecom W-BitView automate convolutional/RS code detection, so our claim narrowed to automatic interleaver recovery chained to blind FEC from IQ; CCSDS and ITU issue numbers were added; CORAL is a method, not a dataset. It also got the 30 Sep rival re-scan (about 60 public SIH26147 repos, up from 35; the strongest newcomer is Venkata-Manoj/RF-signal-analysis) and a references section.
- Plan additions taken from the rival scan and research, each adopted only where it beats what we had:
  - blind CRC recovery (M6)
  - a Meteor-M LRPT entry, whose 80k mode is a real convolutional interleaver (M3 OQPSK, M5, M6)
  - drift and Doppler tracking in 1.0 (M2, M3)
  - verified NAVTEX/POCSAG text (M6)
  - capture-quality parameters (M2)
  - recording and results SHA-256 in results and exports (§2, M7)
  - a chain-matrix bench (M5)
  - independent decoder oracles in tests (M5)
  - real-recording expectations committed before the first run, and every real-recording failure turned into a synth regression test (M8)
- Build order set: PS coverage first (M7 inputs, M5, M6, M3), then M4, then real recordings. A code audit added six Open gates (PLAN §0).

## 28 Sep 2026 — workspace sections and layout

- The workspace was split into Survey and Waterfall sections, with the Assumptions modal, a full-screen per-detection deep dive and a draggable, persisted split ([UI.md](UI.md)).
- Three layout bugs were fixed, all a container sizing itself to its content: a grid with no `grid-template-rows`, a missing `flex-1` on the plot column, and the waterfall canvas ratchet (the `ResizeObserver` wrote a grown size back and held the plot at 2,681 px inside a 956 px box). The lesson, now in the UI.md invariants: verify layout by measuring the DOM, not from screenshots.

## 28 Sep 2026 — first end-to-end decode chain

- `dsp/analyse.py` runs per detection:
  - channelise, then symbol rate, the analog check and the 2-FSK path
  - RRC matched filter with Oerder-Meyr timing and M-th-power carrier recovery
  - cumulant ranking over BPSK/QPSK/8PSK/16QAM, trying every rotation
  - soft Viterbi, K=7 r½
  - an 8-entry block-interleaver catalogue aligned by the code's parity syndrome
  - RS(255,223) CCSDS via `galois`
  - CCSDS ASM framing with a CRC-16 catalogue
  - a Bonferroni-corrected ledger and shuffled-bit re-runs

  It returns a `DetectionReport` (`dsp/report.py`), which the backend runs on open and the UI draws.
- `tools/make_demo.py` writes three synthetic sample recordings and checks every frame against the truth. The coded QPSK and BPSK decode to VERIFIED (44/44 and 24/24 frames), FM is labelled analog, and uncoded QPSK stays UNKNOWN with the reason.
- A browser run-through fixed the waterfall time axis (one row is `hop` samples), the "Real recording" badge on synthetic files (now read from SigMF `core:recorder`), a `NaN` in an empty ledger, and unrounded values.
- pytest-xdist and a CI Playwright cache were added.

## 28 Sep 2026 — M2 DSP, bench and real tiles

- Built:
  - the reader dispatcher
  - streaming Welch spectrogram/PSD
  - OS-CFAR detection with a split-sample significance test
  - channelisation
  - estimation: symbol rate, CFO, bandwidth, SNR, roll-off, cumulants
  - analog AM/FM with a kurtosis gate
  - the server tile pyramid
  - detections as `Parameter`s with boxes on the real waterfall
- [Detection bench](../bench/results/bench-v0-detect.md): recall 100 % in every bucket, rate error ≤ 0.1 % at ≥ 10 dB, CFO ≤ 1 % of Rs. SNR error misses ±1 dB below 15 dB, and false detections miss ≤ 0.05/scene (both Open gates). A 4 GiB file streams with RSS growth < 512 MiB.
- The `dsp-reviewer` found three real bugs, all fixed:
  - a real recording's mirror image survived when no decimation was needed
  - `welch()` always treated input as complex
  - `SnrEstimate.signal_power` was off by a factor of `nfft`
- The M-FSK false detections were traced to unshaped tone splatter in `dsp.synth`. A Gaussian premod filter sweep over bt 0.02–2.0 found a three-way conflict: small bt merges the splatter but breaks the analog kurtosis gate and the FSK rate estimate, and large bt changes nothing. `fsk_bt` stays at 0.

## 27 Sep 2026 — M1: ingest, evidence model, ground truth, bench v0

- Built:
  - the evidence model with honesty rules at construction
  - the generated results schema with `needsReview`
  - all 28 SigMF datatypes round-tripped
  - readers for WAV/RF64/Wave64 (with the stereo quadrature check), SigMF archives, `.npy`, `.sdriq`, Blue, VITA 49, FLAC/MP3/Ogg, `.gz`/`.zip` and numbered sequences
  - the format sniffer, with [0 wrong formats on 864 files](../bench/results/sniffer.md)
  - sample-rate candidates
  - `dsp.synth`
  - TorchSig (WSL2) as an independent generator
  - bench v0: [dev](../bench/results/bench-v0-dev.md) 200 files and [null](../bench/results/bench-v0-null.md) 1,000 files, with 0 ingest mismatches and 0 wrong formats; [TorchSig](../bench/results/bench-v0-torchsig.md) 84 files, likewise
- The 0-silent-defaults test found two gaps, both fixed: an `.sdriq` header with a bad CRC still called its data offset MEASURED, and SigMF metadata without a rate offered no candidates.

## 27 Sep 2026 — M0: foundations and identity

- Built:
  - the identity and the workspace on an in-browser synthetic capture
  - the uv workspace
  - the FastAPI app and `sanket` on 127.0.0.1
  - pytest-socket (loopback only)
  - generated `THIRD_PARTY.md` with a licence gate
  - pre-commit
  - a Playwright smoke test that fails on any outside request
- CI is green on Windows and Ubuntu.
