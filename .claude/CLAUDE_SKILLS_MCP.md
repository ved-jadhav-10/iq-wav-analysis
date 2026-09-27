# Claude Code tooling for building Sanket

This lists the Claude Code skills, plugins, MCP servers, custom project skills, `CLAUDE.md` rules and hooks we use to build Sanket (SIH26147). It also says **when and where** each one is used. Timing uses the milestones **M0–M8** from [PLAN §5](../docs/PLAN.md#5-milestones), plus **idea submission**, the external SIH deadline in [PLAN §9](../docs/PLAN.md#9-external-dates-sih). Current status is in [PLAN §0](../docs/PLAN.md#0-progress).

- **Verification dates:** MCP server details were checked against their repos on 26 September 2026, and plugins and skills on 27 September 2026. Machine facts in [§2](#2-machine-setup) were checked on 27 September 2026. The 27 September revision moved everything onto milestone timing; it did not re-check external repos.
- **Dev-time only:** everything here helps us *build* the tool. The shipped product must never depend on an MCP server, an LLM, or any network service, because it has to run air-gapped. Two rival repos ship LLM copilots and cloud auth; we deliberately don't.

---

## 1. Tooling by milestone

**Set up** means install, configure or create it at the start of that stage. **Use** lists what does the work during the stage. Custom project skills are marked *(custom)*; see [§8](#8-custom-project-skills).

| Stage | Set up | Use |
|---|---|---|
| **Every change, from M0** | — | `code-review` on every change (`/code-review high` on sync, `gf2` and FEC code); `ponytail` left on; `run` to see a change working in the app; Context7 for current library docs; `simplify` before closing a milestone's exit gate |
| **Idea submission** (now → 30 Sep) | `gh auth login`; GitHub MCP (read-only token); `sanket-brand` *(custom)* | `chrome-browser` to confirm the PS, template and theme on sih.gov.in; `rival-scan` *(custom)*, or the [STANDARDS §10](../docs/STANDARDS_TO_BEAT.md#10-how-to-refresh-this-document) queries by hand, to refresh the rival matrix; Playwright MCP for workspace screenshots, labelled *synthetic demo data*; `pptx` for the deck; `artifact-diagramming` for the architecture diagram; `claim-check` *(custom)* on every number in the deck |
| **M0** Foundations | Done: Python 3.12 via uv; Playwright and Context7 MCP (`.mcp.json`); permissions and pre-commit ([§10](#10-hooks-and-permissions)); `plan-status` *(custom)*; plugins `ponytail` and `frontend-design`, project scope ([§5](#5-plugins)) | Context7 for uv, FastAPI and GitHub Actions; `run` to check that `sanket` starts one process serving the UI; `plan-status` to update PLAN §0; `fewer-permission-prompts` once there is some usage history |
| **M1** Ingest, evidence, ground truth, bench v0 | Merge the [§9](#9-claudemd-rules) rules into `.claude/CLAUDE.md`; `skill-creator`, then create `gen-iq`, `inspect-iq`, `sigmf-check` and `bench-run` *(custom)*; `evidence-auditor` subagent; plugin `superpowers` (installed, project scope; trial it here: M1 is the first milestone with exact ground truth) | `superpowers` test-first against `dsp/synth` truth; `gen-iq`, `inspect-iq` and `sigmf-check` on every format round trip; `dataviz` for the sniffer confusion matrix (an exit-gate artifact); optional GNU Radio MCP to cross-check the generator; optional `sdr-skills` after reading it |
| **M2** Spectrum, detection, estimation, tiles | Serena MCP; Chrome DevTools MCP; `dsp-reviewer` subagent | `superpowers` for detectors and estimators; `frontend-design` for the tiled level-of-detail waterfall; Chrome DevTools to measure first tile ≤ 2 s and 60 fps pan/zoom; `dataviz` for per-SNR-bucket detection and estimation results; `bench-run`; IQEngine as the reference for tiles |
| **M3** Sync and demodulation | — | `superpowers`; `dsp-reviewer`; `/code-review high`; `dataviz` for BER-vs-theory curves (exit gate: within 1 dB); `frontend-design` for the eye diagram |
| **M4** Modulation classification | Jupyter, Hugging Face and arXiv MCP; `eval-amc` *(custom)* | `deep-research` and arXiv on low-SNR and open-set AMC; Jupyter for training and evaluation experiments; Hugging Face for dataset cards and licences; `eval-amc`, which drives `dataviz` for accuracy-vs-SNR curves, confusion matrices and reliability diagrams |
| **M5** GF(2), interleavers, FEC | `fec-catalogue` *(custom)* | `superpowers`; `deep-research` and arXiv on blind code and interleaver identification; `pdf` for CCSDS, DVB-S2 and 802.11 tables; `fec-catalogue` for each catalogue entry; `bench-run` on the null set (exit gate: 0 false accepts); `/code-review high` |
| **M6** Framing | — | `superpowers`; `bench-run` to measure the blind-sync false-alarm rate (≤ 10⁻⁶ per stream) |
| **M7** Analyst workflow and reports | Motion (npm package) only if a transition needs it; shadcn MCP only if we adopt shadcn/ui components ([§7](#7-uidesign-toolkit-notes)) | `frontend-design` for the open-recording flow, overrides, before/after diff, history, batch and compare views; `@playwright/test` (`frontend/e2e/`) for the open → analyse → override → export E2E, with Playwright MCP for debugging it; `pdf` to check generated PDF reports; `sanket-brand` for report styling; `security-review` on uploads and export filenames; Chrome DevTools for regressions |
| **M8** Hardening, validation, 1.0 | `decoder-truth` and `judge-drill` *(custom)* | `decoder-truth` for real-capture ground truth; `bench-run` on the sealed set; `dataviz` and `xlsx` for `bench/VALIDATION.md` and the head-to-head; `security-review` for the release review; `rival-scan` on `loop` or `schedule` until the finale; `claim-check` on the README, deck and docs; `/ponytail-audit` before the release freeze; `pptx` and `artifact-design` for finale material; `judge-drill` before the finale |

---

## 2. Machine setup

State of the main dev machine on 27 September 2026:

| Tool | State |
|---|---|
| Node.js | 22.13 ✓ |
| Git | ✓ |
| uv | 0.12.19 ✓ |
| Python | 3.12.14 installed through uv ✓ (3.14 is also present; `python` is not on PATH, so use `uv run`) |
| GitHub CLI | logged in ✓ |
| WSL | an `Ubuntu` distro exists; TorchSig needs Ubuntu ≥ 22.04 |

```powershell
wsl -d Ubuntu -- lsb_release -rs       # confirm >= 22.04 before M4 TorchSig work
# Optional, M1: radioconda (github.com/ryanvolz/radioconda) for GNU Radio reference flowgraphs
```

---

## 3. Built-in skills

These are already available in Claude Code. Invoke one by name (e.g. `/code-review`), or describe the task and Claude loads the matching skill.

| Skill | Use it for | Milestones |
|---|---|---|
| `code-review` | Bug-focused review of every change; `/code-review high` on sync, `gf2` and FEC code | Every change |
| `simplify` | Clean-up pass on finished code | Before each exit gate |
| `run` | Launch the app and confirm a change works end to end | M0 onward |
| `init` | Refresh `.claude/CLAUDE.md` from the codebase once `dsp/` and `backend/` exist, keeping the [§9](#9-claudemd-rules) rules | M1 |
| `update-config` | Change the permissions or add hooks in `.claude/settings.json` ([§10](#10-hooks-and-permissions)) | When needed |
| `fewer-permission-prompts` | Build an allowlist of safe read-only commands from real usage | M0, once there is history |
| `skill-creator` | Build and evaluate the custom skills in [§8](#8-custom-project-skills) | Idea submission, M0, M1, M4, M5, M8 |
| `chrome-browser` | Read sih.gov.in in your own Chrome session. The portal blocks automated fetches, so this is the reliable way to confirm PS details and dates. | Idea submission; again when the finale date is announced |
| `pptx` | The idea deck and the finale deck | Idea submission, M8 |
| `artifact-design` / `artifact-diagramming` | A shareable page for the competitive matrix; the architecture diagram | Idea submission, M8 |
| `dataviz` | Confusion matrices, per-SNR results, BER curves, accuracy-vs-SNR, reliability diagrams, benchmark charts; consistent palette in light and dark | M1–M5, M8 |
| `deep-research` | Literature sweeps: low-SNR and open-set AMC; blind code reconstruction (Marazin, Barbier, Cluzeau–Tillich, Sendrier, Valembois); interleaver identification | M4, M5 |
| `pdf` | Reading papers and standards (CCSDS, DVB-S2 LDPC tables); checking our generated PDF reports | M5, M7 |
| `xlsx` | Benchmark results and the rival matrix as a spreadsheet | M8 |
| `security-review` | Upload handling, path traversal in export filenames (a rival hit this), parser fuzzing gaps | M7, M8 |
| `loop` / `schedule` | Re-run `rival-scan` on a schedule until the finale | M8 |

Not needed: `claude-api` (there's no LLM in the product), `computer-use`, `built-in-browser`, `morning`, `import-memory`, `docx`, `docs`, `artifact-capabilities`, `keybindings-help`.

---

## 4. Skills considered and dropped

- `webapp-testing`: the E2E tests use `@playwright/test` directly (`frontend/e2e/`, run by CI), so a skill for writing Playwright scripts adds nothing.
- `brand-guidelines` applies **Anthropic's** brand, not ours.
- `theme-factory` applies preset themes, which would override our fixed identity.
- `sanket-brand` *(custom, [§8](#8-custom-project-skills))* replaces both. The identity was fixed in M0 ([PLAN §4](../docs/PLAN.md#4-product-identity-fixed)).

---

## 5. Plugins

Checked against their repos on 27 September 2026. Install with `/plugin marketplace add <owner>/<repo>`, then `/plugin install <plugin>@<marketplace>`, unless noted otherwise.

| Plugin | Why we need it | When | Install | Notes |
|---|---|---|---|---|
| **`ponytail`** ([DietrichGebert/ponytail](https://github.com/dietrichgebert/ponytail), MIT) | Adds a "does this need to exist, or is it already in the codebase or stdlib" check before new code is written. This matches the plan's anti-abstraction rule. Independently measured at about 10–15 % less code and cost on real sessions: smaller than its own marketing, but a real, positive signal (unlike similar "token saver" tools; see [§6](#6-mcp-servers)). | Install in M0; on for every change; `/ponytail-audit` before the M8 release freeze | `/plugin marketplace add DietrichGebert/ponytail`, then `/plugin install ponytail@ponytail` (two separate prompts; its install note says both are required) | Needs Node.js on PATH. Toggle with `/ponytail [lite\|full\|ultra\|off]`. |
| **`frontend-design`** (official, `anthropics/claude-code`) | Anthropic's skill for non-generic UI, packaged as a plugin. Keeps new screens consistent instead of drifting into default layouts. The M0 workspace was built without it. | Install in M0; used for new UI in M2 (tiled waterfall), M3 (eye diagram) and M7 (analyst workflow) | `/plugin install frontend-design@claude-plugins-official` | First-party, no secrets. Verify with `/plugin` after install. New screens must still follow the [PLAN §4](../docs/PLAN.md#4-product-identity-fixed) UI rules. |
| **`superpowers`** ([obra/superpowers](https://github.com/obra/superpowers)) | A brainstorm → plan → test-first → review workflow that matches our rules: exact ground truth over "it didn't crash", and the Definition of Done in [PLAN §6](../docs/PLAN.md#6-quality-system). | Trial in M1, the first milestone with `dsp/synth` ground truth; then M2, M3, M5 and M6, the algorithm-heavy milestones. Not useful for M0 scaffolding or UI. | `/plugin install superpowers@claude-plugins-official` if the official marketplace is enabled; otherwise `/plugin marketplace add obra/superpowers-marketplace`, then `/plugin install superpowers@superpowers-marketplace` | Large and opinionated (14+ skills). It must not override the project rules in [§9](#9-claudemd-rules), e.g. "no silent defaults" or VERIFIED only from proof. Keep it only if the M1 trial shows it helps. |

Not added: the `commit-commands` and `feature-dev` bundles from `claude-plugins-official`. `/code-review`, `/simplify` and the `CLAUDE.md` rules already cover that ground.

---

## 6. MCP servers

Use **project scope** (`--scope project`, written to `.mcp.json` and committed) for servers without secrets, so every clone gets them. Use **user scope** for anything that needs a token. Never commit tokens.

| Server | Why we need it | When | Install | Notes |
|---|---|---|---|---|
| **GitHub** (official, [github/github-mcp-server](https://github.com/github/github-mcp-server)) | Rival scans (repo trees, READMEs, commits); later our own issues, PRs and Actions logs | Idea submission onward | `claude mcp add --transport http github https://api.githubcopilot.com/mcp/ --header "Authorization: Bearer <FINE_GRAINED_PAT>"` | User scope. Use a fine-grained PAT with read-only access for scanning. The local Docker image supports `--read-only`. |
| **Context7** ([upstash/context7](https://github.com/upstash/context7)) | Up-to-date docs for uv, FastAPI, React, Vite, PyTorch, ONNX Runtime, SciPy, `sigmf` | M0 onward | Configured in `.mcp.json` | An API key from context7.com is optional (higher limits): add `--header "Authorization: Bearer <KEY>"` at user scope. |
| **Playwright** ([microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)) | Drive the React GUI: take screenshots for the deck, check the waterfall and evidence cards, upload a bench file, debug E2E tests | Idea submission (screenshots), M2 and M7 (checking UI changes, debugging E2E) | Configured in `.mcp.json` | Works on the accessibility tree, so no vision model is needed. Uses `cmd /c npx` because native Windows needs the wrapper; on Linux or macOS, override it in user scope with plain `npx`. The CI E2E tests use `@playwright/test`, not this server. |
| **Serena** ([oraios/serena](https://github.com/oraios/serena)) | LSP-based, symbol-level code retrieval and editing: Claude reads the one function it needs instead of whole files, which keeps DSP and FEC review cheaper | M2 onward, once `dsp/` is big enough to benefit | `claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd` | Older `uvx … --context ide-assistant` instructions circulating online are outdated. |
| **Chrome DevTools** (official, [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)) | Performance traces and console/network inspection for the WebGL2 waterfall: frame budget, GPU memory and tile fetches, which Playwright's accessibility tree can't see | M2 (first-tile and 60 fps gates), M7, M8 | `claude mcp add chrome-devtools-mcp -- npx -y chrome-devtools-mcp`, or `/plugin marketplace add ChromeDevTools/chrome-devtools-mcp`, then `/plugin install chrome-devtools-mcp` | Needs Chrome remote debugging enabled locally. The waterfall already renders on demo data, so it can be used as soon as it's installed. |
| **Jupyter** ([datalayer/jupyter-mcp-server](https://github.com/datalayer/jupyter-mcp-server), ★1.3k, BSD-3) | Notebook experiments with Claude running cells and reading outputs: AMC training and evaluation, estimator sweeps | M4 (optionally M2) | `/plugin marketplace add datalayer/jupyter-mcp-server`, then `/plugin install datalayer` | Needs a running JupyterLab. |
| **Hugging Face** ([official](https://huggingface.co/docs/hub/en/hf-mcp-server)) | Find RF datasets and models; check dataset cards and licences | M4 | `claude mcp add hf-mcp-server -t http "https://huggingface.co/mcp?login"` | Read-only token. **Never upload recordings.** |
| **arXiv** ([blazickjp/arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server), ★3.2k, Apache-2.0) | Read AMC and blind-FEC papers section by section; export BibTeX for deck references | M4, M5 | `claude mcp add --transport stdio --scope user arxiv -- uvx arxiv-mcp-server` | Needs uv. |
| **shadcn** (official, [ui.shadcn.com/docs/mcp](https://ui.shadcn.com/docs/mcp)), *conditional* | Live shadcn/ui component data (props, variants, structure) instead of hallucinated APIs | M7, **only if** we adopt shadcn/ui components | `pnpm dlx shadcn@latest mcp init --client claude`, or add to `.mcp.json`: `{"mcpServers":{"shadcn":{"command":"npx","args":["shadcn@latest","mcp"]}}}` | The frontend doesn't use shadcn/ui today; its tokens only use shadcn-compatible names. Project scope, no secret. |
| **GNU Radio** ([yoelbassin/gr-mcp](https://github.com/yoelbassin/gr-mcp), ★50, **GPL-3.0**), *optional* | Build and run reference flowgraphs to cross-check `dsp/synth` | M1 | `/plugin marketplace add yoelbassin/gr-mcp`, then `/plugin install marconi` | Needs GNU Radio 3.10+. GPL: dev-time only; never copy its code into the product. |

**Community skill (optional, M1 onward):** [briannasywa/sdr-skills](https://github.com/briannasywa/sdr-skills) (MIT) is an SDR knowledge skill covering DSP, modulation, IQ formats, SigMF and GNU Radio 3.10, with 8 small Python tools. Install with `npx skills add briannasywa/sdr-skills --skill software-defined-radio`. **On 27 September it was 10 days old with 0 stars, so read its `SKILL.md` and tools before enabling it.**

**Personal and optional, never project scope:** a persistent-memory MCP such as [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) keeps your own session history across `/compact` and later sessions. The repo's shared context lives in `CLAUDE.md` and these docs, so a tool like this belongs in your own user scope only.

**Deliberately not added:**
- filesystem MCP: the built-in tools already cover this
- database or cloud MCPs: we use SQLite locally, and the product is air-gapped
- any MCP that would upload recordings
- Task Master: [PLAN §0](../docs/PLAN.md#0-progress) is the tracker, and `plan-status` keeps it current
- generic "token-saving" or "context mode" MCP servers advertising 90 %+ savings: independent benchmarks of similarly marketed tools found some *increase* cost. `ponytail` ([§5](#5-plugins)) is the one tool in this category with a validated gain. Don't install another without measuring it first.

---

## 7. UI/design toolkit notes

The frontend is an analyst instrument, not a marketing site, and its identity is fixed ([PLAN §4](../docs/PLAN.md#4-product-identity-fixed)). So we skip the animated shadcn kits (Magic UI, Aceternity, Watermelon UI, Motion Primitives, coss ui/Origin UI): they add licensing and visual-noise risk for no benefit here.

- **IQEngine** ([GitHub](https://github.com/IQEngine/IQEngine), MIT): the reference for tiled spectrogram rendering (M2) and recording management (M7). See the [README tech stack](../README.md#tech-stack) and [STANDARDS §3](../docs/STANDARDS_TO_BEAT.md#3-open-source-prior-art).
- **Motion** (`motion.dev`, MIT): a plain npm dependency, not a Claude tool. It isn't installed. Add it in M7 only if the before/after diff or stage transitions need it, and respect reduced-motion ([PLAN §2](../docs/PLAN.md#2-the-production-bar)).
- **shadcn MCP server:** conditional; see [§6](#6-mcp-servers).
- **tweakcn:** retired. It was for choosing the palette, and M0 fixed the palette in `frontend/src/styles/index.css`. Contrast is checked by axe in E2E, per PLAN §2.

---

## 8. Custom project skills

Put each skill in `.claude/skills/<name>/SKILL.md` and commit it. Build and test them with `skill-creator`. `plan-status` exists; the rest are created in the milestone shown.

| Skill | What it does | Runs | Output | Create in |
|---|---|---|---|---|
| `sanket-brand` | Applies the §4 identity to anything outside the app — decks, artifacts, PDF reports: colour tokens from `index.css`, IBM Plex fonts, evidence shown as glyph + label + colour, *synthetic demo data* labels | Reads `frontend/src/brand.ts`, `styles/index.css`, `components/levelStyles.ts` | Styled output that matches the GUI | Idea submission |
| `rival-scan` | Re-run the GitHub searches from [STANDARDS §10](../docs/STANDARDS_TO_BEAT.md#10-how-to-refresh-this-document); fetch trees and READMEs of new or changed repos; diff against the matrix | GitHub MCP or `gh api` | Proposed edits to `STANDARDS_TO_BEAT.md` | Idea submission |
| `claim-check` | Find every number in the README, deck and docs; match each to a `bench/` result, a STANDARDS target (labelled as a target) or a dossier citation; flag anything unsupported | grep + `bench/results/` | List of unsupported claims | Idea submission |
| `plan-status` | Compare the repo with the [PLAN §0](../docs/PLAN.md#0-progress) checklists and propose edits. Never tick an item without evidence: the file exists, or the test or check passes. | `git`, file checks, test and bench commands | Proposed edits to PLAN §0 | M0 |
| `gen-iq` | Generate a synthetic recording with exact ground truth: modulation, symbol rate, SNR, impairments, FEC, interleaver, framing with CRC | `uv run python -m dsp.synth …` | `.sigmf-data` + `.sigmf-meta`, with the truth stored as annotations | M1 |
| `inspect-iq` | Quick sanity report on any file: ranked format candidates, channel count, quadrature check, clipping, DC, IQ balance, what's still UNKNOWN | the `dsp/ingest` sniffer | Markdown summary with the assumptions block | M1 |
| `sigmf-check` | Validate `.sigmf-meta` against the spec with the `sigmf` package; flag a missing `core:sample_rate` or `core:datatype` | `sigmf` validate | Pass/fail with fixes | M1 |
| `bench-run` | Run the benchmark and null set; compare with the last committed results; refuse to update numbers if the sealed set was touched | `uv run python -m bench run` | `bench/results/<date>.json` + a diff table | M1 |
| `eval-amc` | Evaluate an AMC checkpoint on our in-scope set, TorchSig, HisarMod and RadioML 2018.01A (corrected labels), plus the null set | `ml.evaluate` | Accuracy-vs-SNR chart (via `dataviz`), confusion matrix, reliability diagram, open-set AUROC/FPR@95/OSCR per SNR bin, a model-card update | M4 |
| `fec-catalogue` | Add or verify a catalogue entry (conv/RS/LDPC): encode → channel → blind ID → decode round trip, plus a licence/source note | pytest on that entry | Catalogue YAML + test | M5 |
| `decoder-truth` | For a real capture, run the matching reference decoder (readsb, AIS-catcher, rtl_433, multimon-ng, SatDump, redsea) as a **subprocess**; keep only CRC-passing frames and write them as SigMF annotations | subprocess + `sigmf` | `.sigmf-meta` with protocol-level ground truth | M8 |
| `judge-drill` | Quiz the presenter on the six judge questions in [dossier §B7](../docs/SIHPS_ANALYSIS.md) plus random module questions; score the answers against the docs | — | Drill transcript with gaps | M8 |

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

**Subagents** (`.claude/agents/`):
- `evidence-auditor` (from M1): confirms every new output field carries an evidence level and that no stage defaults silently.
- `dsp-reviewer` (from M2): checks unit consistency (PSD vs power), sample-rate assumptions, and the matched-filter/timing phase on DSP changes.

---

## 9. `CLAUDE.md` rules

**Location:** [`.claude/CLAUDE.md`](CLAUDE.md), which Claude Code loads automatically. This block was merged into it in M1, when `dsp/` got code; that file is now the live copy, and this one is the reference:

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
- RadioML is a benchmark only, with corrected labels; train on dsp.synth.
- Python: 3.12, uv, ruff, pyright strict on dsp/. Frontend: TS strict, ESLint, Vitest.
- When a milestone item lands, update docs/PLAN.md §0.
```

---

## 10. Hooks and permissions

- **Lint and format:** done by **pre-commit** (`.pre-commit-config.yaml`: large-file guard, ruff check and format, ESLint, licence check) rather than Claude Code edit hooks, so it applies to every commit whoever or whatever wrote the code. Install once per clone with `uv run pre-commit install`. CI runs the same checks.
- **Permissions:** `.claude/settings.json` (committed) allows the test, lint, typecheck, build, e2e, licence and read-only `gh` commands without prompting. Extend it with `fewer-permission-prompts` once there is real usage, or edit it with `update-config`. Personal overrides go in `.claude/settings.local.json`, which is git-ignored.
- **Optional `Stop` hook**, not set up: `uv run pytest -q -x --lf`, so a turn doesn't end with failing tests. Add it with `update-config` if turns start ending red.

**Cost monitoring (optional, personal):** [ryoppippi/ccusage](https://github.com/ryoppippi/ccusage) reads local Claude Code session logs and reports daily, monthly and per-session cost, with no API key. `npx ccusage@latest` gives a one-off report; `npx ccusage@latest monthly` gives the aggregate.

---

The research behind the plan is in [`reports/SIH26147 solution research.md`](../reports/SIH26147%20solution%20research.md), with source notes in `research_notes/`.
