# Claude Code skills & MCP servers for this project

This covers the Claude Code setup that helps a six-person team build SIH26147: built-in skills worth using, MCP servers to add, custom project skills to write, and the `CLAUDE.md` rules and hooks that keep Claude's output consistent with the [plan](PLAN.md).

MCP server details were checked against their repos on **26 September 2026**; plugins and the additions in §3–§5 were checked on **27 September 2026**.

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
| `init` | Generate the first `CLAUDE.md` once the repo is scaffolded, then merge in the rules in [§7](#7-claudemd-rules-to-add) | Phase 1, day 1 |
| `code-review` | Bug-focused review of every PR (`/code-review high` on FEC and sync code) | Every PR |
| `simplify` | Clean-up passes on merged code | Weekly |
| `security-review` | Upload handling, path traversal in export filenames (a rival hit this), parser fuzzing gaps | Phase 7 |
| `run` | Launch the app and confirm a change works end to end | Phase 7+ |
| `update-config` | Set up the hooks and permissions in [§8](#8-hooks--permissions) correctly | Phase 1 |
| `fewer-permission-prompts` | After a week of work, build an allowlist of safe read-only commands | Phase 1+ |
| `skill-creator` | Build and evaluate the custom skills in [§6](#6-custom-project-skills-to-create) | Phase 1 |
| `loop` / `schedule` | Re-run `rival-scan` periodically, e.g. every morning until the finale | Phase 0 → 9 |
| `artifact-design` / `artifact-diagramming` | A shareable page for the competitive matrix or the architecture diagram | Phases 0, 9 |
| `chrome-browser` | Read sih.gov.in in *your own* Chrome session. The portal blocks automated fetches, so this is the reliable way to confirm PS details and deadlines. | Phase 0 |

Not needed: `claude-api` (there's no LLM in the product), `computer-use`, `morning`, `import-memory`.

---

## 3. Claude Code plugins to install

Checked against their repos on **27 September 2026**. Install with `/plugin marketplace add <owner>/<repo>` then `/plugin install <plugin>@<marketplace>`, unless noted otherwise.

| Plugin | Why we need it | Install | Notes |
|---|---|---|---|
| **`superpowers`** ([obra/superpowers](https://github.com/obra/superpowers)) | A brainstorm → plan → TDD → review methodology that matches this project's own rules: exact ground truth over "it didn't crash," and the Definition of Done checklist. Best fit for the algorithm-heavy phases (2 DSP, 5 FEC, 6 framing) where a red-green-refactor discipline against `dsp.synth` ground truth actually matters. | `/plugin install superpowers@claude-plugins-official` if the official marketplace is already enabled; otherwise `/plugin marketplace add obra/superpowers-marketplace` then `/plugin install superpowers@superpowers-marketplace` | Large, opinionated plugin (14+ skills). Don't let it override the project's own rules in [§6](#6-claudemd-rules-to-add) — e.g. it shouldn't relax the "no silent defaults" or VERIFIED-only rule. Try it on one phase before rolling out to the whole team. |
| **`frontend-design`** (official, `anthropics/claude-code`) | Anthropic's own skill for non-generic UI, now as a plugin. Directly useful for R5's waterfall/constellation/evidence-card/hypothesis-table work in Phase 7 — keeps a consistent palette and spacing instead of default AI-slop layouts. | `/plugin install frontend-design@claude-plugins-official` | First-party, no secrets. Verify with `/plugin` after install. |
| **`ponytail`** ([DietrichGebert/ponytail](https://github.com/dietrichgebert/ponytail), MIT) | Injects a "does this need to exist / is it already in the codebase or stdlib" decision ladder before writing new code. Matches the plan's own anti-abstraction rule ("three similar lines is better than a premature abstraction"). Independently measured around −10–15% code and cost on real sessions — smaller than its own marketing claims, but a real, positive signal (unlike similar "token saver" tools — see the caution in [§5](#5-mcp-servers-to-add)). | `/plugin marketplace add DietrichGebert/ponytail` then `/plugin install ponytail@ponytail` (two separate prompts — the plugin's own install note says this is required) | Needs Node.js on PATH (already on the dev machine). Toggle with `/ponytail [lite\|full\|ultra\|off]`; run `/ponytail-audit` before the Phase 9 freeze to catch scope creep. |

Not added: `commit-commands`/`feature-dev` bundles from `claude-plugins-official` — `/code-review`, `/simplify` and the CLAUDE.md rules already cover that ground; add only if the team finds commit-message drift across 6 people to be an actual problem.

---

## 4. UI/design toolkit notes

The frontend is an analyst tool (waterfall, constellation, evidence cards, hypothesis table), not a marketing site, so skip the flashy animated shadcn kits (Magic UI, Aceternity, Watermelon UI, Motion Primitives, coss ui/Origin UI) — they add licensing and visual-noise risk for no benefit here.

- **shadcn MCP server** (official, [ui.shadcn.com/docs/mcp](https://ui.shadcn.com/docs/mcp)) — listed in [§5](#5-mcp-servers-to-add). Gives Claude live access to real shadcn component APIs instead of hallucinating props.
- **Motion** (`motion.dev`, formerly Framer Motion, MIT) — a plain npm dependency (`npm install motion`), not an MCP/plugin. Use sparingly for the stage-timeline and before/after diff transitions in Phase 7; avoid it everywhere else per the plan's own restraint.
- **tweakcn** ([tweakcn.com](https://tweakcn.com), MIT) — a browser-only visual theme editor for shadcn/Tailwind tokens, not a Claude Code tool. Useful once, early in Phase 7, to pick an accessible light/dark palette (colorblind-safe evidence-level colors), then export the CSS variables into the repo. No install needed.
- **IQEngine** — already called out in [PLAN.md Phase 7](PLAN.md#phase-7--gui--api-w2w10-continuous--r4-r5) as the component/pattern source to study and borrow from (MIT).

---

## 5. MCP servers to add

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
| **shadcn** (official, [ui.shadcn.com/docs/mcp](https://ui.shadcn.com/docs/mcp)) | Live shadcn/ui component data (props, variants, structure) for R5's evidence cards, hypothesis table and stage timeline, instead of hallucinated component APIs | `pnpm dlx shadcn@latest mcp init --client claude`, or add to `.mcp.json`: `{"mcpServers":{"shadcn":{"command":"npx","args":["shadcn@latest","mcp"]}}}` | Project scope, no secret needed. See [§4](#4-uidesign-toolkit-notes) for what to skip. |
| **Serena** ([oraios/serena](https://github.com/oraios/serena)) | LSP-based symbol-level code retrieval/editing once `dsp/`, `backend/` and `frontend/` grow large — Claude reads the one function it needs instead of whole files, which keeps DSP/FEC review sessions cheaper and faster | `claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd` | Add from Phase 2 onward, once the codebase is big enough for it to pay off. Older `uvx ... --context ide-assistant` install instructions circulating online are outdated — use the `serena` CLI form above. |
| **Chrome DevTools** (official, [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)) | Performance traces and console/network inspection for the WebGL2 tiled-STFT waterfall — checks frame budget, GPU memory and tile-fetch behaviour that Playwright's accessibility-tree view can't see | `claude mcp add chrome-devtools-mcp -- npx -y chrome-devtools-mcp`, or `/plugin marketplace add ChromeDevTools/chrome-devtools-mcp` then `/plugin install chrome-devtools-mcp` | Phase 7, once the waterfall renders. Needs Chrome remote debugging enabled locally; dev-time only, same as Playwright. |

**Community skill (optional):** [briannasywa/sdr-skills](https://github.com/briannasywa/sdr-skills) (MIT) is an SDR knowledge skill covering DSP, modulation, IQ formats/SigMF and GNU Radio 3.10, with 8 small Python tools. Install with `npx skills add briannasywa/sdr-skills --skill software-defined-radio`. **It is 10 days old with 0 stars, so read its `SKILL.md` and tools before enabling it.**

**Personal, optional, never project scope:** a persistent-memory MCP such as [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) compresses your own Claude Code session history so it survives `/compact` and later sessions. This repo already carries the team's shared memory in `CLAUDE.md` and these docs, so treat any such tool as an individual's personal convenience (their own user scope, their own machine) rather than something the whole team installs.

**Deliberately not added:**
- filesystem MCP: built-in tools already cover this
- database or cloud MCPs: we use SQLite locally, and the product is air-gapped
- any MCP that would upload recordings
- generic "token-saving" or "context mode" MCP servers advertising 90%+ savings: independent benchmarks of similarly-marketed tools have found some *increase* cost rather than cut it (see the `ponytail` note in [§3](#3-claude-code-plugins-to-install) for the one tool in this category that was actually validated) — don't install one without measuring it yourself first

---

## 6. Custom project skills to create

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

## 7. `CLAUDE.md` rules to add

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

## 8. Hooks & permissions

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

## 9. Suggested setup order

1. **Day 1 (Phase 0):** install Python/uv, run `gh auth login`, add GitHub + Context7, and use `chrome-browser` to confirm the PS on sih.gov.in. Use `pptx` for the deck.
2. **Phase 1:**
   - `/init` → merge in the §7 rules
   - `update-config` hooks
   - install `frontend-design` and `ponytail` plugins; try `superpowers` on one phase before team-wide rollout
   - add Playwright and the shadcn MCP server
   - create the `gen-iq`, `inspect-iq`, `sigmf-check` and `bench-run` skills
3. **Phase 2:** add Serena once `dsp/` is big enough to benefit from symbol-level retrieval.
4. **Phase 3:** add Jupyter, Hugging Face and arXiv; create `eval-amc`.
5. **Phase 5:** create `fec-catalogue`; use `deep-research` for the blind-FEC literature.
6. **Phase 7:** add Chrome DevTools MCP once the waterfall renders; pick a palette with tweakcn.
7. **Phases 8–9:** create `decoder-truth` for real captures; use `rival-scan` on a `loop`, plus `claim-check` and `judge-drill`.

The research behind the latest plan changes is in [`reports/SIH26147 solution research.md`](../reports/SIH26147%20solution%20research.md), with source notes in `research_notes/`.
