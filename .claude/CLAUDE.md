# Sanket (SIH26147) — IQ/WAV blind signal analysis

- **Start here:** [../docs/PLAN.md](../docs/PLAN.md) — progress (§0), 1.0 scope, the production bar (§2), architecture (§3), product identity (§4) and milestones M0–M8 (§5). Work toward the current milestone's exit gate, and when an item lands, tick it in §5 and update the §0 table and Open gates.
- **Prototype mode** ([../docs/PROTOTYPE_PLAN.md](../docs/PROTOTYPE_PLAN.md)): when it's active, the honesty rules below still apply in full, but the check cadence is lighter — run only the one ground-truth test file for the phase you're on while iterating, and run the full check list once at the end of the phase, not after every change. No review agents, no bench runs, no gate chasing while it's active; a missed number becomes an Open gate in PLAN §0 instead.
- **The official problem statement:** [../docs/PROBLEM_STATEMENT.md](../docs/PROBLEM_STATEMENT.md) — check scope questions against its wording.
- **Competitive claims and numeric targets:** [../docs/STANDARDS_TO_BEAT.md](../docs/STANDARDS_TO_BEAT.md) — never restate a rival claim or a target without checking it here first. Targets are not claims until `bench/` reproduces them.
- **Claude Code tooling (skills/plugins/MCP servers):** [CLAUDE_SKILLS_MCP.md](CLAUDE_SKILLS_MCP.md) — §1 maps what to use in each milestone.
- **Repo state:** `frontend/` (Vite + React 19 + TS strict + Tailwind 4) runs on a synthetic demo capture. The uv workspace has `dsp/`, `ml/`, `backend/`, `bench/` (each `<pkg>/src/<pkg>/`); `backend/` has the FastAPI app and the `sanket` command; `dsp/` has the evidence model, the results document and its generated JSON schema (`tools/results_schema.py` regenerates it), ingest (SigMF datatypes plus a 24-bit PCM extension; one segment-based chunked reader; readers for SigMF incl. archives and multi-capture, raw files with the format sniffer, WAV/RF64/Wave64 with the stereo quadrature check, `.npy`, `.sdriq`, MIDAS Blue, VITA 49, FLAC/MP3/Ogg, `.gz`/`.zip` decompression and numbered sequences; sample-rate candidates and the structural-match test in `rate.py`; recorder file extensions as sniffer hints; no dispatcher yet, so callers pick the reader), and `synth/`, the ground-truth generator (bits → frames/CRC → FEC → interleavers → modulation → impairments, SigMF with the truth in annotations). `bench/` has the sniffer bench (`uv run python -m bench.sniffer`) and bench v0 (`uv run bench generate|run dev|null|sealed`, plus `run torchsig` for the TorchSig export that `bench/torchsig/export.py` writes under WSL2 in `~/torchsig-env`); results in `bench/results/`, generated data in `bench/data/` (not committed). `tools/inspect_iq.py` prints what the readers make of any file. `ml/` is empty. Python tests live in `tests/<pkg>/`. Don't assume code exists just because the plan describes it.
- **Checks before calling work done** (the same as CI): `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run pytest -n auto --dist loadfile`, `uv run python tools/third_party.py --check` (rerun without `--check` after changing dependencies); in `frontend/`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run e2e`. For UI work, also look at it in a browser in both themes.
- **Python tests may only open loopback connections** (pytest-socket); don't loosen that to make a test pass.
- **Identity is fixed:** name in `frontend/src/brand.ts`, all colours as tokens in `frontend/src/styles/index.css`, evidence-level glyphs/colours in `frontend/src/components/levelStyles.ts`. Follow the UI rules in PLAN §4 — evidence is never colour-only, no dead controls, demo data always labelled.
- **Never silently assume** a sample rate, datatype, byte order or IQ order: state it as an assumption or UNKNOWN. VERIFIED only from a CRC pass, sync-word recurrence or re-encode match.
- **Air-gapped product:** nothing shipped may depend on the network, an MCP server or an LLM at runtime. No GPL/AGPL/non-commercial code in the product; never copy code from rival SIH repos.

## Project rules (SIH26147)
- Never assume a sample rate, datatype, byte order or IQ order silently. Unknown -> Assumptions block + UNKNOWN or an analyst prompt.
- Every value a stage outputs is a `dsp.evidence.Parameter`; its validator enforces the honesty rules, so never bypass it (no `model_construct`).
- VERIFIED requires CRC pass, sync-word recurrence, or re-encode BER consistent with EVM. Nothing else.
- Blind searches count every hypothesis; acceptance thresholds are multiple-testing corrected.
- Tests compare against exact ground truth from dsp.synth — never "it didn't crash".
- Don't touch bench/sealed/ or its seeds. Numbers in README/deck must come from bench/results/.
- Readers and detectors are chunked/streaming; no whole-file loads.
- The product runs offline: no network calls, CDNs, telemetry or LLMs at runtime.
- Don't copy code from rival SIH repos (most are unlicensed). Every shipped dependency appears in THIRD_PARTY.md (generated).
- GPL tools (GNU Radio, gr-mcp, URH, komm, readsb, AIS-catcher, rtl_433, multimon-ng, SatDump) are dev-time references or subprocess-only test tools; never vendor or import their code. PySDR code is CC BY-NC-SA: learn from it, don't copy it.
- Use `galois` for finite fields and RS. scikit-commpy and pyldpc are stale: vendor small functions with attribution; don't depend on them.
- Blind FEC/interleaver work goes through the shared GF(2) kernel (dsp/gf2); don't write a second elimination routine. Rank matrices need L >= w + 30 rows; every detector also runs on shuffled bits.
- Never claim generic pseudo-random seed recovery; only the standard-permutation catalogue.
- Known-system and profile matches never overwrite blind results. A match is VERIFIED only when that system's own check passes on this recording, expressed as one of the three existing proof kinds (crc, sync_recurrence, reencode); every entry tried goes in the ledger.
- Profile values count as analyst-entered and are checked on every recording; profiles hold no samples and are data, never code.
- SDR drivers (librtlsdr, libhackrf, UHD) are GPL: capture runs their command-line recorders as subprocesses with an argument list, never a shell; never import or link them. No capture from network-attached receivers.
- RadioML is a benchmark only, with corrected labels; train on dsp.synth.
- When a milestone item lands, tick it in docs/PLAN.md §5 and update the §0 table and Open gates.
