# Sanket (SIH26147) — IQ/WAV blind signal analysis

- **Start here:** [../docs/PLAN.md](../docs/PLAN.md) — progress (§0), 1.0 scope, the production bar (§2), architecture (§3), product identity (§4) and milestones M0–M8 (§5). Work toward the current milestone's exit gate, and update §0 when an item lands.
- **Competitive claims and numeric targets:** [../docs/STANDARDS_TO_BEAT.md](../docs/STANDARDS_TO_BEAT.md) — never restate a rival claim or a target without checking it here first. Targets are not claims until `bench/` reproduces them.
- **Claude Code tooling (skills/plugins/MCP servers):** [CLAUDE_SKILLS_MCP.md](CLAUDE_SKILLS_MCP.md) — §1 maps what to use in each milestone.
- **Repo state:** `frontend/` (Vite + React 19 + TS strict + Tailwind 4) runs on a synthetic demo capture. The uv workspace has `dsp/`, `ml/`, `backend/`, `bench/` (each `<pkg>/src/<pkg>/`); `backend/` has the FastAPI app and the `sanket` command; `dsp/` has the evidence model and ingest (SigMF datatypes, chunked reader, SigMF metadata). `ml/` and `bench/` are empty. Python tests live in `tests/<pkg>/`. Don't assume code exists just because the plan describes it.
- **Checks before calling work done** (the same as CI): `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run pytest`, `uv run python tools/third_party.py --check` (rerun without `--check` after changing dependencies); in `frontend/`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run e2e`. For UI work, also look at it in a browser in both themes.
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
- RadioML is a benchmark only, with corrected labels; train on dsp.synth.
- When a milestone item lands, update docs/PLAN.md §0.
