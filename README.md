# Sanket — blind signal analysis, with evidence

**Sanket** (संकेत, "signal") is an **offline, CPU-only** workstation for unknown radio recordings, built by **Team Abhedya** for Smart India Hackathon 2026 problem **SIH26147** (NTRO): *"Automated model for analysis of .IQ and .wav files along with signal parameter extraction."*

Give it an `.iq`, `.wav`, SigMF or other recorder file. Sanket finds every signal in it, works out how each was transmitted (sample format, bandwidth, SNR, symbol rate, modulation, interleaver, error-correction code, framing), then undoes each layer to recover the bits, split into header and payload. Every value says how it was found and how sure it is, and a result is **VERIFIED** only when the recording itself proves it: a CRC passes, a sync word recurs, or re-encoding reproduces what was received.

## Try it in five minutes

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and git. uv fetches Python 3.12 itself. On Windows, clone into a **short path** such as `C:\sanket`: a deep folder pushes Numba's cache files past Windows' 260-character path limit and the first analysis fails.

```bash
git clone https://github.com/ved-jadhav-10/iq-wav-analysis sanket
cd sanket
uv sync                                          # install (first time: a few minutes)
uv run python tools/make_demo.py                 # write 9 synthetic recordings, decode each, check every frame against the truth
uv run sanket analyse data/demo --out out --summary --pdf
```

`make_demo.py` ends with **`all checks passed`**: it decoded every sample and matched every CRC-passing frame byte for byte against what was transmitted. `sanket analyse` prints one line per signal and writes, for each recording, `out/<name>.results.json` (every value with its evidence), `<name>.summary.txt` (plain English), `<name>.report.pdf` and `<name>.run.json` (timings). On our laptop: install 10 s with a warm cache, `make_demo` 85 s, the whole folder 63 s; the first run on a machine also spends 10–20 s compiling the Numba kernels.

Expected output, abridged:

```
scene.sigmf-meta: 4 signal(s)
  signal_0: VERIFIED QPSK 50 kBd → Conv K=7 r½ (171,133)₈ → CCSDS ASM frames, 44/44 CRC pass · CCSDS telemetry coding
  signal_1: ESTIMATED Analog FM: not sent to the digital chain
  signal_2: VERIFIED BPSK 31.2 kBd → Conv K=7 r½ (171,133)₈ → CCSDS ASM frames, 24/24 CRC pass · CCSDS telemetry coding
  signal_3: ESTIMATED QPSK? 41.7 kBd, not decoded
scene_raw.cf32: 0 signal(s)
  the sample rate is UNKNOWN; pass --sample-rate to analyse the bands
scene_systems.sigmf-meta: 3 signal(s)
  signal_0: VERIFIED 2FSK 1.2 kBd → POCSAG paging: 4/5 frames pass its check
  signal_1: VERIFIED 2FSK 100 Bd → NAVTEX (SITOR-B): 1/1 frames pass its check
  signal_2: VERIFIED 2FSK 9.6 kBd → AIS: 26/70 frames pass its check
```

The headerless raw file stops on purpose: nothing in it states a sample rate, so Sanket refuses to invent one. Enter it and it decodes:

```bash
uv run sanket analyse data/demo/scene_raw.cf32 --sample-rate 1M --out out
```

### The interface

Needs **Node.js 22** as well:

```bash
npm ci --prefix frontend
npm run build --prefix frontend
uv run sanket --browser          # http://127.0.0.1:8765; the samples appear as cards on the start screen
```

Click a sample card, then look at the Dashboard (waterfall, spectrum, constellation, eye diagram), Evidence (every value, the frame table, the decoded bit stream), Hypotheses (every candidate tried and why it was rejected) and Summary. A guided tour is under Help. Without `--browser`, `uv sync --extra window` gives Sanket its own desktop window.

### For AI assistants

For Claude, Gemini, Codex or any other assistant asked to run or evaluate Sanket:

- **Don't change any code or commit anything.** The `.claude/` folder is the team's own development workflow (build plans, commit rules); ignore it when you are only running or evaluating.
- Run the commands in **Try it in five minutes** in order. They work the same in bash and PowerShell. If `uv` is missing, install it from the link above.
- **Success:** `make_demo.py` exits 0 with `all checks passed`, and `sanket analyse` reports the levels in the sample table below. Each recording's ground truth is in `data/demo/<name>.truth.json`.
- **Output files are UTF-8.** Windows PowerShell 5.1 shows `→` and `½` as `â†’` and `Â½` unless you read them with `-Encoding utf8`.
- **If something fails:** a `FileNotFoundError` inside `numba\core\caching.py` means the path is too long (move the clone to a short path); `uv run ruff`/`pyright` failing with a "trampoline" error on Windows is fixed by `uv run python -m ruff` / `-m pyright`; if pytest runs out of memory, lower `-n`.
- **The full test suite** (`uv run python -m pytest -n 4 --dist worksteal`) takes several minutes.
- **To judge the claims:** the project's status is in [PLAN §0](docs/PLAN.md#0-progress); the measured numbers are in [`bench/results/`](bench/results/). Report what you observe, including anything that did not work.

## Planned

- The neural modulation classifier, with open-set rejection
- Analyst overrides that re-run every later stage, with a before/after diff
- Reusable profiles of a solved chain
- Capture from a local receiver
- Tracking loops for timing and carrier
- Blind Reed-Solomon parameter recovery
- SSB and Morse
- Tests on real over-the-air recordings
- The Linux build

[PLAN §0](docs/PLAN.md#0-progress) keeps the full list and the build order.

## Measured

Every number below is reproduced by a script in `bench/`; results are in [`bench/results/`](bench/results/).

| Test | Result |
|---|---|
| Format sniffer, 864 raw files across all 28 formats | 0 wrong formats ([sniffer.md](bench/results/sniffer.md)) |
| Null set: 1,000 files of noise, uncoded, repetition and idle data, through the whole decode chain | 0 accepted decodes, 0 VERIFIED values, 0 known-system matches on 4,373 detections ([bench-v0-null.md](bench/results/bench-v0-null.md)) |
| 84 files from TorchSig, an independent generator the code was never tuned on | 0 wrong formats ([bench-v0-torchsig.md](bench/results/bench-v0-torchsig.md)) |
| A 4 GiB recording streamed with a burst planted in it | memory growth under 512 MiB, burst found (`tests/dsp/test_scale.py`, `-m slow`) |

## Evidence levels

Every value carries one level, plus a confidence, the method and its evidence:

| Level | Meaning | Example |
|---|---|---|
| **VERIFIED** | Proven by one of three checks only: a CRC pass, a sync word recurring at the frame period, or a re-encode match | "Conv K=7: all frames pass CRC" |
| **MEASURED** | Read from metadata, or entered by the analyst | Sample rate from a SigMF or WAV header |
| **ESTIMATED** | Computed from the samples, with an uncertainty | Symbol rate 9,600 Bd ± 0.1 % |
| **HYPOTHESIS** | A ranked candidate that isn't confirmed | "QPSK (0.71) or 8PSK (0.24)" |
| **UNKNOWN** | Can't be determined; says why and what would settle it | "Pseudo-random interleaver: period 2,048 bits; permutation not in the catalogue" |

When the evidence can't decide and a convention must (a raw file doesn't say whether I or Q comes first), the value is a HYPOTHESIS that names its convention and is listed under `needsReview` at the top of every result. Blind searches count every hypothesis they try and raise the acceptance bar to match; a chain is accepted only if it also fails to pass when its bits are shuffled.

## Limits, by design

- **Sampling frequency** is MEASURED from a header or entered by the analyst. No method recovers an absolute rate from samples alone, so for a headerless file Sanket ranks candidates and promotes one only when a structural match supports it; otherwise it reports normalised units. Centre frequency is handled the same way.
- **Blind code and interleaver identification is catalogue-bounded and probabilistic.** Only CRC, sync-word or re-encode proof makes a result VERIFIED.
- **Pseudo-random interleavers** are matched against standard permutations only; anything else is UNKNOWN with its measured period.
- **LDPC** is matched against a catalogue of standard codes, never reconstructed.
- **Mono and lossy audio** (mono WAV, MP3, Ogg) can't carry true IQ, so digital labels from them are HYPOTHESIS at most.
- **Never:** decrypting, transmitting, real-time streams, or network-attached receivers. Sanket recovers bits, not plaintext.

## Sample recordings

`tools/make_demo.py` writes these to `data/demo/` with exact ground truth. All are synthetic, and the UI labels them so.

| File | Contents | What Sanket shows |
|---|---|---|
| `scene.sigmf-meta` | QPSK and BPSK (conv K=7 r½, CCSDS frames, CRC-16), FM, uncoded QPSK | Both coded signals VERIFIED; FM labelled analog; the uncoded QPSK with its FEC UNKNOWN and the reason |
| `scene_widen.sigmf-meta` | 8PSK with a block interleaver; QPSK inside RS(255,223) | Both VERIFIED, with the de-interleave and RS stages shown |
| `scene_fsk.sigmf-meta` | Coded 2-FSK | VERIFIED frames |
| `scene_ldpc.sigmf-meta` | QPSK under the IEEE 802.11n n = 648 rate-½ LDPC code | The code named from the catalogue, VERIFIED by the frame CRC |
| `scene_coverage.sigmf-meta` | 16QAM with a helical interleaver; QPSK with a convolutional (Forney) interleaver; QPSK under a K=9 code that is not catalogued; frames carry readable text | All three VERIFIED; both interleavers recognised; the K=9 code identified blind and marked "(found blind)"; the frames read as words |
| `scene_fsk4.sigmf-meta` | Coded 4-FSK, frames carry readable text | Tone-based demodulation at four tones, VERIFIED frames |
| `scene_systems.sigmf-meta` | POCSAG paging (2-FSK), NAVTEX (SITOR-B) and AIS (GMSK) in one 48 kS/s recording | Each recognised blind and VERIFIED by its own check; the pages and the NAVTEX warning shown as text |
| `scene_wav.wav` | 48 kHz 16-bit stereo IQ WAV (I left, Q right), one coded QPSK signal | Sample rate MEASURED from the WAV header, quadrature check passes, VERIFIED frames |
| `scene_raw.cf32` | Headerless complex float32, one coded QPSK signal, no sample rate in the file or its name | Sample rate UNKNOWN; with `--sample-rate 1M` (or entered in the UI's prompt) it decodes to VERIFIED |

What each view shows: [docs/UI.md](docs/UI.md#what-each-view-shows).

## For developers

`npm run dev` in `frontend/` gives hot reload at http://localhost:5173. Run `uv run pre-commit install` once per clone. Nothing loads from the network. Checks, as CI runs them (on Windows use `uv run python -m <tool>`):

```bash
uv run ruff check && uv run ruff format --check && uv run pyright && uv run pytest -n auto --dist worksteal
uv run python tools/third_party.py --check       # licences + THIRD_PARTY.md
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
npx playwright install chromium && npm run e2e   # offline smoke test against sanket
```

**One-folder Windows build:** `uv sync --extra window`, then `uv run python tools/build.py` (frontend, samples, then PyInstaller to `dist/sanket/sanket.exe`) and `uv run python tools/smoke_frozen.py` (starts it, opens a bundled sample, checks the result). The folder runs with networking off. CI builds and smoke-tests it on Windows; the Linux build runs in CI but is not yet known to work. `sanket warm` compiles the Numba kernels ahead of the first analysis.

## Lawful use

Sanket analyses recordings offline, never transmits or decrypts, and is meant for authorised government, regulatory, defence and research use. In India, interception and possessing radio equipment are governed by the Telecommunications Act 2023 (sources in [STANDARDS §11](docs/STANDARDS_TO_BEAT.md#11-references)). Recordings come from public licensed datasets first, then public receive-only receivers, then own captures only under an institutional umbrella. Every recording's provenance is kept in its SigMF metadata.

## Documentation

- [docs/PROBLEM_STATEMENT.md](docs/PROBLEM_STATEMENT.md): the official PS, requirements R1–R5 and how we read them, SIH rules
- [docs/PLAN.md](docs/PLAN.md): status, scope, production bar, architecture, milestones
- [docs/STANDARDS_TO_BEAT.md](docs/STANDARDS_TO_BEAT.md): vendors, prior art, rival repos, targets, references
- [docs/UI.md](docs/UI.md): workspace layout, what each view shows

## Credits

Every shipped library is credited in [`THIRD_PARTY.md`](THIRD_PARTY.md), generated from the lockfiles; CI fails on GPL/AGPL, non-commercial or unrecognised licences. Public SIH26147 repositories were studied, never copied ([STANDARDS §5](docs/STANDARDS_TO_BEAT.md#5-sih26147-rival-repositories)).
