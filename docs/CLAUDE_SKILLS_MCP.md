# Claude Code skills & MCP servers for this project

This covers the Claude Code setup that helps a six-person team build SIH26147: built-in skills worth using, MCP servers to add, custom project skills to write, and the `CLAUDE.md` rules and hooks that keep Claude's output consistent with the [plan](PLAN.md).

MCP server details were checked against their repos on **26 September 2026**.

> **Dev-time only.** Everything here helps us *build* the tool. The shipped product must never depend on an MCP server, an LLM, or any network service, because it has to run air-gapped. Two rival repos ship LLM copilots and cloud auth; we deliberately don't.

---

## 0. Machine setup first

The main dev machine has Node 22, npm, Git and `gh`. **Python isn't installed** and `gh` isn't logged in. Several MCP servers below need Python/uv.

```powershell
winget install Python.Python.3.12
winget install astral-sh.uv
gh auth login                          # raises the GitHub API limit from 60/hr; needed for rival scans
wsl --install -d Ubuntu-22.04          # TorchSig requires Ubuntu >= 22.04
# GNU Radio on Windows: install radioconda (github.com/ryanvolz/radioconda) — optional, for synthetic flowgraphs
```

---

## 1. Built-in skills to use (already available)

Invoke these by name, e.g. `/code-review`, or just describe the task and Claude loads the matching skill.

| Skill | Use it for | When |
|---|---|---|
| `pptx` | The SIH idea deck (6 slides) and the finale deck | Phase 0, Phase 9 |
| `dataviz` | Accuracy-vs-SNR curves, confusion matrices, reliability diagrams, benchmark charts, the competitive matrix; consistent palette in light and dark | Phases 3, 8 |
| `deep-research` | Literature sweeps on blind code reconstruction (Marazin, Barbier, Cluzeau–Tillich, Sendrier, Valembois), interleaver identification, low-SNR AMC | Phases 3, 5 |
| `pdf` | Reading paper PDFs and standards (CCSDS, DVB-S2 LDPC tables); checking our generated PDF reports | Phases 5, 7 |
| `xlsx` | Benchmark result sheets and the rival matrix as a spreadsheet for the team | Phase 8 |
| `init` | Generate the first `CLAUDE.md` once the repo is scaffolded, then merge in the rules in [§4](#4-claudemd-rules-to-add) | Phase 1, day 1 |
| `code-review` | Bug-focused review of every PR (`/code-review high` on FEC and sync code) | Every PR |
| `simplify` | Clean-up passes on merged code | Weekly |
| `security-review` | Upload handling, path traversal in export filenames (a rival hit this), parser fuzzing gaps | Phase 7 |
| `run` | Launch the app and confirm a change works end to end | Phase 7+ |
| `update-config` | Set up the hooks and permissions in [§5](#5-hooks--permissions) correctly | Phase 1 |
| `fewer-permission-prompts` | After a week of work, build an allowlist of safe read-only commands | Phase 1+ |
| `skill-creator` | Build and evaluate the custom skills in [§3](#3-custom-project-skills-to-create) | Phase 1 |
| `loop` / `schedule` | Re-run `rival-scan` periodically, e.g. every morning until the finale | Phase 0 → 9 |
| `artifact-design` / `artifact-diagramming` | A shareable page for the competitive matrix or the architecture diagram | Phases 0, 9 |
| `chrome-browser` | Read sih.gov.in in *your own* Chrome session. The portal blocks automated fetches, so this is the reliable way to confirm PS details and deadlines. | Phase 0 |

Not needed: `claude-api` (there's no LLM in the product), `computer-use`, `morning`, `import-memory`.

---

## 2. MCP servers to add

Use **project scope** (`--scope project`, written to `.mcp.json` and committed) for servers without secrets, so the whole team gets them. Use **user scope** for anything that needs a token. Never commit tokens.

| Server | Why we need it | Install | Notes |
|---|---|---|---|
| **GitHub** (official, [github/github-mcp-server](https://github.com/github/github-mcp-server)) | Rival scans (repo trees, READMEs, commits), our own issues and PRs, Actions logs | `claude mcp add --transport http github https://api.githubcopilot.com/mcp/ --header "Authorization: Bearer <FINE_GRAINED_PAT>"` | User scope. Use a fine-grained PAT with read-only access for scanning. The local Docker image supports `--read-only`. |
| **Context7** ([upstash/context7](https://github.com/upstash/context7)) | Up-to-date docs for FastAPI, React, Vite, PyTorch, ONNX Runtime, SciPy, `sigmf` | `claude mcp add --scope project --transport http context7 https://mcp.context7.com/mcp` | An API key from context7.com is optional (higher limits): add `--header "Authorization: Bearer <KEY>"` at user scope |
| **Playwright** ([microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)) | Drive the React GUI: upload a bench file, check the waterfall and evidence cards, take screenshots for the deck, debug E2E tests | `claude mcp add --scope project playwright npx @playwright/mcp@latest` | Works on the accessibility tree, so no vision model is needed |
| **Jupyter** ([datalayer/jupyter-mcp-server](https://github.com/datalayer/jupyter-mcp-server), ★1.3k, BSD-3) | DSP experiments in notebooks (estimator sweeps, constellation checks) with Claude running cells and reading outputs | In Claude Code: `/plugin marketplace add datalayer/jupyter-mcp-server`, then `/plugin install datalayer` | Needs a running JupyterLab (Python) |
| **Hugging Face** ([official](https://huggingface.co/docs/hub/en/hf-mcp-server)) | Find RF datasets and models, check dataset cards and licences | `claude mcp add hf-mcp-server -t http "https://huggingface.co/mcp?login"` | Read-only token. **Never upload real captures.** |
| **arXiv** ([blazickjp/arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server), ★3.2k, Apache-2.0) | Read AMC and blind-FEC papers section by section; export BibTeX for the deck's references | `claude mcp add --transport stdio --scope user arxiv -- uvx arxiv-mcp-server` | Needs uv |
| **GNU Radio** ([yoelbassin/gr-mcp](https://github.com/yoelbassin/gr-mcp), ★50, **GPL-3.0**), *optional* | Build and run reference flowgraphs to cross-check our synthetic generator | `/plugin marketplace add yoelbassin/gr-mcp`, then `/plugin install marconi` | Needs GNU Radio 3.10+ to run pipelines. GPL: keep it dev-only and never copy its code into the product. |

**Community skill (optional):** [briannasywa/sdr-skills](https://github.com/briannasywa/sdr-skills) (MIT) is an SDR knowledge skill covering DSP, modulation, IQ formats/SigMF and GNU Radio 3.10, with 8 small Python tools. Install with `npx skills add briannasywa/sdr-skills --skill software-defined-radio`. **It is 10 days old with 0 stars, so read its `SKILL.md` and tools before enabling it.**

**Deliberately not added:**
- filesystem MCP: built-in tools already cover this
- database or cloud MCPs: we use SQLite locally, and the product is air-gapped
- any MCP that would upload recordings

---

## 3. Custom project skills to create

Put each skill in `.claude/skills/<name>/SKILL.md` and commit them so the whole team shares them. Build and test them with `skill-creator`.

| Skill | What it does | Runs | Output |
|---|---|---|---|
| `gen-iq` | Generate a synthetic recording with exact ground truth: modulation, symbol rate, SNR, impairments, FEC, interleaver, framing with CRC | `uv run python -m dsp.synth …` | `.sigmf-data` + `.sigmf-meta`, with the truth stored as annotations |
| `inspect-iq` | Quick sanity report on any file: ranked format candidates, channel count, quadrature check, clipping, DC, IQ balance, what's still UNKNOWN | `dsp.ingest` sniffer | Markdown summary with the assumptions block |
| `sigmf-check` | Validate `.sigmf-meta` against the spec with the `sigmf` package; flag missing `core:sample_rate` or `core:datatype` | `sigmf` validate | Pass/fail with fixes |
| `bench-run` | Run the sealed benchmark and null set; compare with the last committed results; refuse to update numbers if the sealed set was touched | `uv run python -m bench run` | `bench/results/<date>.json` + a diff table |
| `eval-amc` | Evaluate an AMC checkpoint on RadioML 2018.01A, our in-scope set and the null set | `ml.evaluate` | Accuracy-vs-SNR chart (via `dataviz`), confusion matrix, reliability diagram, a model-card update |
| `fec-catalogue` | Add or verify a catalogue entry (conv/RS/LDPC): encode → channel → blind ID → decode round trip, plus a licence/source note | pytest on that entry | Catalogue YAML + test |
| `decoder-truth` | For a real capture, run the matching reference decoder (readsb, AIS-catcher, rtl_433, multimon-ng, SatDump, redsea) as a **subprocess**; keep only CRC-passing frames and write them as SigMF annotations | subprocess + `sigmf` | `.sigmf-meta` with protocol-level ground truth |
| `rival-scan` | Re-run the GitHub searches from [STANDARDS §10](STANDARDS_TO_BEAT.md#10-how-to-refresh-this-document); fetch trees and READMEs of new or changed repos; diff against the matrix | GitHub MCP or `gh api` | Proposed edits to `STANDARDS_TO_BEAT.md` |
| `claim-check` | Scan the README, deck and docs for numbers; match each to a `bench/` result or a dossier citation; flag anything unsupported | grep + bench results | List of unsupported claims |
| `judge-drill` | Quiz a team member on the six §B7 questions plus random module questions; score their answers against the docs | — | Drill transcript with gaps |

Minimal `SKILL.md` shape:

```markdown
---
name: gen-iq
description: Generate a synthetic SigMF IQ recording with exact ground truth (modulation, symbol rate, SNR, impairments, FEC, interleaver, CRC-framed payload). Use when a test, benchmark or demo needs a signal with known answers.
---

1. Ask for (or default from bench/presets.yaml): modulation, sps, symbol rate, SNR (state Es/N0 vs per-sample), impairments, FEC, interleaver, frame layout.
2. Run `uv run python -m dsp.synth --preset <name> --out data/generated/<name>`.
3. Verify the round trip: `uv run python -m dsp.synth.verify data/generated/<name>.sigmf-meta`.
4. Report the file paths and the truth table. Never reuse a sealed-bench seed.
```

**Optional subagents** (`.claude/agents/`):
- `dsp-reviewer`: checks unit consistency (PSD vs power), sample-rate assumptions, and the matched-filter/timing phase on DSP PRs.
- `evidence-auditor`: confirms every new output field carries an evidence level and that no stage defaults silently.

---

## 4. `CLAUDE.md` rules to add

After `/init` generates the base file, paste in these rules:

```markdown
## Project rules (SIH26147)
- Never assume a sample rate, datatype, byte order or IQ order silently. Unknown -> Assumptions block + UNKNOWN or an analyst prompt.
- Every value a stage outputs is a Parameter with level (VERIFIED/MEASURED/ESTIMATED/HYPOTHESIS/UNKNOWN), confidence, method, evidence[], alternatives[].
- VERIFIED requires CRC pass, sync-word recurrence, or re-encode BER consistent with EVM. Nothing else.
- Blind searches count every hypothesis; acceptance thresholds are multiple-testing corrected.
- Tests compare against exact ground truth from dsp.synth — never "it didn't crash".
- Don't touch bench/sealed/ or its seeds. Numbers in README/deck must come from bench/results/.
- Readers and detectors are chunked/streaming; no whole-file loads.
- The product runs offline: no network calls, CDNs, telemetry or LLMs at runtime.
- Don't copy code from rival SIH repos (most are unlicensed). Credit every third-party library in THIRD_PARTY.md.
- GPL tools (GNU Radio, gr-mcp, URH, komm, readsb, AIS-catcher, rtl_433, multimon-ng, SatDump) are dev-time references or subprocess-only test tools; never vendor or import their code. PySDR code is CC BY-NC-SA: learn from it, don't copy it.
- Use `galois` for finite fields and RS. scikit-commpy and pyldpc are stale: vendor small functions with attribution; don't depend on them.
- Blind FEC/interleaver work goes through the shared GF(2) kernel (dsp/gf2); don't write a second elimination routine. Rank matrices need L >= w + 30 rows; every detector also runs on shuffled bits.
- Never claim generic pseudo-random seed recovery; only the standard-permutation catalogue.
- Python: 3.12, uv, ruff, pyright strict on dsp/. Frontend: TS strict, ESLint, Vitest.
```

---

## 5. Hooks & permissions

Ask Claude to use the `update-config` skill to add these to `.claude/settings.json`; it gets the hook schema right.

- **Format and lint on edit (Python):** a `PostToolUse` hook on `Edit|Write` that runs `uv run ruff check --fix --quiet` and `uv run ruff format --quiet` on the edited `.py` file.
- **Format and lint on edit (frontend):** the same pattern for `frontend/**/*.{ts,tsx}` with ESLint `--fix` and Prettier.
- **Optional `Stop` hook:** `uv run pytest -q -x --lf` so a turn doesn't end with failing tests. Turn it off during large refactors.
- **Allowlist**, to cut down permission prompts:
  - `Bash(uv run pytest:*)`, `Bash(uv run ruff:*)`, `Bash(uv run pyright:*)`, `Bash(uv run python -m bench:*)`
  - `Bash(npm run test:*)`, `Bash(npm run build:*)`, `Bash(npx tsc:*)`
  - `Bash(gh api:*)` (read-only)

  Later, run `fewer-permission-prompts` to extend it from real usage.

---

## 6. Suggested setup order

1. **Day 1 (Phase 0):** install Python/uv, run `gh auth login`, add GitHub + Context7, and use `chrome-browser` to confirm the PS on sih.gov.in. Use `pptx` for the deck.
2. **Phase 1:**
   - `/init` → merge in the §4 rules
   - `update-config` hooks
   - add Playwright
   - create the `gen-iq`, `inspect-iq`, `sigmf-check` and `bench-run` skills
3. **Phase 3:** add Jupyter, Hugging Face and arXiv; create `eval-amc`.
4. **Phase 5:** create `fec-catalogue`; use `deep-research` for the blind-FEC literature.
5. **Phases 8–9:** create `decoder-truth` for real captures; use `rival-scan` on a `loop`, plus `claim-check` and `judge-drill`.

The research behind the latest plan changes is in [`reports/SIH26147 solution research.md`](../reports/SIH26147%20solution%20research.md), with source notes in `research_notes/`.
