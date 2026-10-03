# Sanket — blind signal analysis, with evidence

**Sanket** (संकेत, "signal") is an **offline, CPU-only** workstation for unknown radio recordings, built for Smart India Hackathon problem **SIH26147** (NTRO): *"Automated model for analysis of .IQ and .wav files along with signal parameter extraction."*

Given an `.iq`, `.wav`, SigMF or other recorder file, Sanket works out how the signal was transmitted — sample format, bandwidth, SNR, symbol rate, modulation, interleaver, error-correction code and framing — then undoes each layer to recover the bits. Every result shows the evidence behind it and how sure it is. Nothing is guessed silently.

- **Problem statement and how we read it:** [docs/PROBLEM_STATEMENT.md](docs/PROBLEM_STATEMENT.md)
- **Plan and current status:** [docs/PLAN.md](docs/PLAN.md) (status in [§0](docs/PLAN.md#0-progress))

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
- **Analog signals** are detected, labelled and kept out of the digital chain.
- **Never:** decrypting, transmitting, real-time streams, or network-attached receivers. Sanket recovers bits, not plaintext.

## Getting started

You need **Node.js 22**, [uv](https://docs.astral.sh/uv/) and **Python 3.12** (`uv python install 3.12`).

```bash
uv sync                              # Python workspace + dev tools
npm ci --prefix frontend
npm run build --prefix frontend      # sanket serves this build
uv run sanket                        # Sanket's own window over http://127.0.0.1:8765
```

`sanket` opens a desktop window when pywebview is installed (`uv sync --extra window`; Windows uses the system's Edge WebView2, Linux GTK/WebKit) and otherwise your browser. `sanket --browser` forces the browser, `sanket --no-open` only serves, `sanket warm` compiles the Numba kernels ahead of the first analysis (the first run on a machine otherwise spends 10–20 s compiling). The window asks before closing while an analysis is running.

### One-folder build (Windows)

```bash
uv sync --extra window
uv run python tools/build.py         # frontend, sample recordings, then PyInstaller -> dist/sanket/sanket.exe
uv run python tools/smoke_frozen.py  # starts it, opens a bundled sample, checks the result
```

The folder runs with networking off and carries the built UI and the sample recordings below (listed at `GET /api/v1/samples`). CI builds and smoke-tests it on Windows; the Linux build runs in CI too but is not yet known to work.

Checks, as CI runs them (on a Windows machine where `uv run ruff`/`pyright` fail with a trampoline error, use `uv run python -m <tool>`; if `-n auto` runs out of memory, use `-n 8`):

```bash
uv run ruff check && uv run ruff format --check && uv run pyright && uv run pytest -n auto --dist worksteal
uv run python tools/third_party.py --check       # licences + THIRD_PARTY.md
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
npx playwright install chromium && npm run e2e   # offline smoke test against sanket
```

`npm run dev` in `frontend/` gives hot reload at http://localhost:5173. Run `uv run pre-commit install` once per clone. Nothing loads from the network.

### Sample recordings

`uv run python tools/make_demo.py` writes synthetic recordings (SigMF, a headerless raw file and a WAV) with exact ground truth to `data/demo/`, and checks every decoded frame against the transmitted bytes. They are bundled in the desktop build and shown as cards on the start screen (click one to open it); from a checkout, paste a file's full path into the path box in the top bar instead. The UI labels them "Synthetic recording".

| File | Contents | What Sanket shows |
|---|---|---|
| `scene.sigmf-meta` | QPSK and BPSK (conv K=7 r½, CCSDS frames, CRC-16), FM, uncoded QPSK | Both coded signals VERIFIED; FM labelled analog; the uncoded QPSK with its FEC UNKNOWN and the reason |
| `scene_widen.sigmf-meta` | 8PSK with a block interleaver; QPSK inside RS(255,223) | Both VERIFIED, with the de-interleave and RS stages shown |
| `scene_fsk.sigmf-meta` | Coded 2-FSK | VERIFIED frames |
| `scene_ldpc.sigmf-meta` | QPSK under the IEEE 802.11n n = 648 rate-½ LDPC code | The code named from the catalogue, VERIFIED by the frame CRC |
| `scene_coverage.sigmf-meta` | 16QAM with a helical interleaver; QPSK with a convolutional (Forney) interleaver; QPSK under a K=9 code that is not catalogued; frames carry readable text | All three VERIFIED; both interleavers recognised from the catalogue (helical 16×36, the Forney grid); the K=9 code identified blind and marked "(found blind)"; the Frames tab's ASCII column reads as words |
| `scene_fsk4.sigmf-meta` | Coded 4-FSK, frames carry readable text | Tone-based demodulation at four tones, VERIFIED frames (alone because the M-FSK symbol-rate estimate is an [open gate](docs/PLAN.md#0-progress) on crowded channels) |
| `scene_systems.sigmf-meta` | POCSAG paging (2-FSK), NAVTEX (SITOR-B) and AIS (GMSK) in one 48 kS/s recording | Each recognised blind and VERIFIED by its own check (BCH, four-of-seven repetition, CRC-16/X.25); the pages and the NAVTEX warning shown as text |
| `scene_wav.wav` | 48 kHz 16-bit stereo IQ WAV (I left, Q right), one coded QPSK signal | Sample rate MEASURED from the WAV header, quadrature check passes, VERIFIED frames |
| `scene_raw.cf32` | Headerless complex float32, one coded QPSK signal, no sample rate in the file or its name | Sample rate UNKNOWN and an analyst prompt; enter 1 MS/s and the signal decodes to VERIFIED |

What each view shows: [docs/UI.md](docs/UI.md#what-each-view-shows).

## Lawful use

Sanket analyses recordings offline, never transmits or decrypts, and is meant for authorised government, regulatory, defence and research use. In India, interception and possessing radio equipment are governed by the Telecommunications Act 2023 (sources in [STANDARDS §11](docs/STANDARDS_TO_BEAT.md#11-references)). Capturing from a receiver needs the same authorisation as the receiver itself. Recordings come from public licensed datasets first, then public receive-only receivers, then own captures only under an institutional umbrella. Every recording's provenance is kept in its SigMF metadata.

## Documentation

- [docs/PROBLEM_STATEMENT.md](docs/PROBLEM_STATEMENT.md) — the official PS, requirements R1–R5 and how we read them, SIH rules
- [docs/PLAN.md](docs/PLAN.md) — status, scope, production bar, architecture, identity, milestones
- [docs/STANDARDS_TO_BEAT.md](docs/STANDARDS_TO_BEAT.md) — vendors, prior art, rival repos, targets, references
- [docs/UI.md](docs/UI.md) — workspace layout, what each view shows, layout invariants

## Credits

Every shipped library is credited in [`THIRD_PARTY.md`](THIRD_PARTY.md), generated from the lockfiles; CI fails on GPL/AGPL, non-commercial or unrecognised licences. Public SIH26147 repositories were studied, never copied ([STANDARDS §5](docs/STANDARDS_TO_BEAT.md#5-sih26147-rival-repositories)).
