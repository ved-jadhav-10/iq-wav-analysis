# Claude Code tooling for building Sanket

The Claude Code skills, plugins, MCP servers, custom project skills, subagents and hooks we use to build Sanket (SIH26147), and **when** each is used. Timing follows milestones M0–M8 ([PLAN §5](../docs/PLAN.md#5-milestones)) plus the external SIH dates ([PLAN §9](../docs/PLAN.md#9-external-dates-sih)); status is in [PLAN §0](../docs/PLAN.md#0-progress).

- **Verified:** MCP servers against their repos on 26 Sep 2026; plugins, skills and the machine (§2) on 27 Sep. The 27 Sep revision moved everything onto milestone timing without re-checking external repos; `.mcp.json` and `.claude/settings.json` re-read on 3 Oct.
- **Dev-time only:** all of this helps us *build* the tool. The shipped product never depends on an MCP server, an LLM or any network service (air-gapped). Two rival repos ship LLM copilots and cloud auth; we deliberately don't.

## 1. Tooling by milestone

**Set up** = install, configure or create at the start of the stage; **Use** = what does the work. *(custom)* = a project skill (§7).

| Stage | Set up | Use |
|---|---|---|
| **Every change** | — | `code-review` (`/code-review high` on sync, `gf2` and FEC code); `ponytail` on; `run` to see a change working; Context7 for library docs; `simplify` before a milestone's exit gate |
| **Pitches** (finale deck, before every pitch) | `gh auth login`; GitHub MCP (read-only token); `sanket-brand` *(custom)* | `chrome-browser` to check sih.gov.in for dates and templates; `rival-scan` *(custom)* or the [STANDARDS §10](../docs/STANDARDS_TO_BEAT.md#10-how-to-refresh-this-document) queries by hand; Playwright MCP for workspace screenshots, labelled *synthetic* where they are; `pptx` for the deck; `artifact-diagramming` for the architecture diagram; `claim-check` *(custom)* on every number |
| **M0** | Done: Python 3.12 via uv; Playwright and Context7 MCP (`.mcp.json`); permissions and pre-commit (§8); `plan-status` *(custom)*; plugins `ponytail` and `frontend-design` (project scope) | Context7 for uv, FastAPI, GitHub Actions; `run` to check `sanket` serves the UI; `plan-status` for PLAN §0; `fewer-permission-prompts` once there is usage history |
| **M1** | Done: the project rules in `.claude/CLAUDE.md`; `gen-iq`, `inspect-iq` (on `tools/inspect_iq.py`), `sigmf-check` (reference validator via `uvx`) and `bench-run` *(custom)*, written by hand rather than through `skill-creator`'s eval loop; the `evidence-auditor` subagent; plugin `superpowers` (project scope); TorchSig 2.2.0 in WSL2 (`~/torchsig-env`) | `superpowers` test-first against `dsp/synth` truth; `gen-iq`, `inspect-iq`, `sigmf-check` on every format and container round trip; `dataviz` for the sniffer confusion matrix; optional GNU Radio MCP to cross-check the generator; optional `sdr-skills` after reading it |
| **M2** | Done: Serena MCP (`serena-agent` 1.7.0 via `uv tool`, user scope); Chrome DevTools MCP (`.mcp.json`); the `dsp-reviewer` subagent | `superpowers` for detectors and estimators; `frontend-design` for the tiled level-of-detail waterfall; Chrome DevTools to measure first tile ≤ 2 s and 60 fps pan/zoom; `dataviz` for per-SNR results; `bench-run`; IQEngine as the reference for tiles |
| **M3** | — | `superpowers`; `dsp-reviewer`; `/code-review high`; `dataviz` for BER-vs-theory curves (gate: within 1 dB); `frontend-design` for the eye diagram |
| **M4** | Jupyter, Hugging Face and arXiv MCP; `eval-amc` *(custom)* | `deep-research` and arXiv on low-SNR and open-set AMC; Jupyter for training and evaluation; Hugging Face for dataset cards and licences; `eval-amc` (drives `dataviz` for accuracy-vs-SNR, confusion matrices, reliability diagrams) |
| **M5** | `fec-catalogue` *(custom)* | `superpowers`; `deep-research` and arXiv on blind code and interleaver identification; `pdf` for CCSDS, DVB-S2 and 802.11 tables; `fec-catalogue` per entry; `bench-run` on the null set (gate: 0 false accepts); `/code-review high` |
| **M6** | `system-catalogue` *(custom)* | `superpowers`; `bench-run` for the blind-sync false-alarm rate (≤ 10⁻⁶ per stream) and false system matches on the null set (gate: 0); `pdf` for the ITU-R and CCSDS specifications; `system-catalogue` per entry |
| **M7** | Motion (npm) only if a transition needs it; shadcn MCP only if we adopt shadcn/ui (§5) | `frontend-design` for context entry, capture, profiles, overrides, before/after diff, batch and compare views; `@playwright/test` (`frontend/e2e/`) for the open → analyse → override → save profile → apply → export E2E, Playwright MCP to debug it; `pdf` to check generated reports; `sanket-brand` for report styling; `security-review` on uploads, archive extraction, profile import, capture subprocesses and export names; Chrome DevTools for regressions |
| **M8** | `decoder-truth` and `judge-drill` *(custom)* | `decoder-truth` for real-capture ground truth; `bench-run` on the sealed set; `dataviz` and `xlsx` for `bench/VALIDATION.md` and the head-to-head; `security-review` for the release; `rival-scan` on `loop` or `schedule` until the finale; `claim-check` on README, deck and docs; `/ponytail-audit` before the release freeze; `pptx` and `artifact-design` for finale material; `judge-drill` before the finale |

## 2. Machine setup

The main dev machine on 27 Sep 2026: Node.js 22.13; Git; uv 0.12.19; Python 3.12.14 through uv (3.14 also present; `python` is not on PATH, so use `uv run`); GitHub CLI logged in; WSL2 `Ubuntu` 26.04 with uv and TorchSig 2.2.0 + CPU PyTorch in `~/torchsig-env`; Serena 1.7.0 via `uv tool install -p 3.13 serena-agent`, user scope.

```powershell
wsl -d Ubuntu -- ~/torchsig-env/bin/python -c "import torchsig; print(torchsig.__version__)"
# Optional, M1: radioconda (github.com/ryanvolz/radioconda) for GNU Radio reference flowgraphs
```

## 3. Built-in skills

Invoke by name (e.g. `/code-review`) or describe the task.

| Skill | Use it for | Milestones |
|---|---|---|
| `code-review` | Bug-focused review of every change; `high` on sync, `gf2` and FEC code | Every change |
| `simplify` | Clean-up pass on finished code | Before each exit gate |
| `run` | Launch the app and confirm a change works end to end | M0 on |
| `init` | Refresh `.claude/CLAUDE.md` from the codebase, keeping its project rules | When the repo map drifts |
| `update-config` | Permissions or hooks in `.claude/settings.json` (§8) | When needed |
| `fewer-permission-prompts` | An allowlist of safe read-only commands from real usage | Once there is history |
| `skill-creator` | Build and evaluate the custom skills (§7) | Pitches, M4, M5, M8 |
| `chrome-browser` | Read sih.gov.in in your own Chrome (the portal blocks automated fetches) to confirm PS details and dates | Pitches; when the finale date is announced |
| `pptx` | The finale deck (the idea deck was submitted 30 Sep 2026) | Pitches, M8 |
| `artifact-design` / `artifact-diagramming` | A shareable competitive-matrix page; the architecture diagram | Pitches, M8 |
| `dataviz` | Confusion matrices, per-SNR results, BER and accuracy-vs-SNR curves, reliability diagrams, benchmark charts, one palette in both themes | M1–M5, M8 |
| `deep-research` | Literature sweeps: low-SNR and open-set AMC; blind code reconstruction (Marazin, Barbier, Cluzeau–Tillich, Sendrier, Valembois); interleaver identification | M4, M5 |
| `pdf` | Papers and standards (CCSDS, DVB-S2 LDPC tables); checking our PDF reports | M5, M7 |
| `xlsx` | Benchmark results and the rival matrix as a spreadsheet | M8 |
| `security-review` | Upload handling, path traversal in export names (a rival hit this), parser-fuzzing gaps | M7, M8 |
| `loop` / `schedule` | Re-run `rival-scan` on a schedule until the finale | M8 |

Not needed: `claude-api` (no LLM in the product), `computer-use`, `built-in-browser`, `morning`, `import-memory`, `docx`, `docs`, `artifact-capabilities`, `keybindings-help`. Considered and dropped: `webapp-testing` (the E2E tests use `@playwright/test` directly), `brand-guidelines` (it applies **Anthropic's** brand) and `theme-factory` (preset themes would override our fixed identity, [PLAN §4](../docs/PLAN.md#4-product-identity-fixed)); `sanket-brand` replaces both.

## 4. Plugins

Checked 27 Sep 2026. Install with `/plugin marketplace add <owner>/<repo>`, then `/plugin install <plugin>@<marketplace>`, unless noted. All three are enabled in `.claude/settings.json`.

| Plugin | Why | When | Install | Notes |
|---|---|---|---|---|
| **`ponytail`** ([DietrichGebert/ponytail](https://github.com/dietrichgebert/ponytail), MIT) | A "does this need to exist, or is it already in the codebase or stdlib" check before new code, matching the plan's anti-abstraction rule. Independently measured at about 10–15 % less code and cost on real sessions: smaller than its marketing, but real | M0 on, every change; `/ponytail-audit` before the M8 freeze | `/plugin marketplace add DietrichGebert/ponytail`, then `/plugin install ponytail@ponytail` (both prompts are required) | Needs Node.js on PATH. `/ponytail [lite\|full\|ultra\|off]` |
| **`frontend-design`** (official, `anthropics/claude-code`) | Non-generic UI: keeps new screens consistent instead of drifting into default layouts (the M0 workspace was built without it) | New UI in M2 (tiled waterfall), M3 (eye diagram), M7 (analyst workflow) | `/plugin install frontend-design@claude-plugins-official` | First-party, no secrets. New screens still follow PLAN §4 |
| **`superpowers`** ([obra/superpowers](https://github.com/obra/superpowers)) | Brainstorm → plan → test-first → review, matching exact-ground-truth testing and the Definition of Done ([PLAN §6](../docs/PLAN.md#6-quality-system)) | Algorithm-heavy milestones (trial in M1, then M2, M3, M5, M6); not for scaffolding or UI | `/plugin install superpowers@claude-plugins-official`, or `/plugin marketplace add obra/superpowers-marketplace` then `/plugin install superpowers@superpowers-marketplace` | Large and opinionated (14+ skills); must not override CLAUDE.md's rules (no silent defaults, VERIFIED only from proof). Keep only while it helps |

Not added: `commit-commands` and `feature-dev` (`/code-review`, `/simplify` and CLAUDE.md cover them).

## 5. MCP servers

**Project scope** (`--scope project`, written to `.mcp.json`, committed) for servers without secrets, so every clone gets them; **user scope** for anything with a token. Never commit tokens. `.mcp.json` today: Playwright, Context7, Chrome DevTools.

| Server | Why | When | Install | Notes |
|---|---|---|---|---|
| **GitHub** ([github/github-mcp-server](https://github.com/github/github-mcp-server)) | Rival scans (trees, READMEs, commits); later our issues, PRs and Actions logs | Pitches on | `claude mcp add --transport http github https://api.githubcopilot.com/mcp/ --header "Authorization: Bearer <FINE_GRAINED_PAT>"` | User scope, read-only fine-grained PAT. The local Docker image supports `--read-only` |
| **Context7** ([upstash/context7](https://github.com/upstash/context7)) | Current docs for uv, FastAPI, React, Vite, PyTorch, ONNX Runtime, SciPy, `sigmf` | M0 on | In `.mcp.json` | Optional API key (higher limits) at user scope: `--header "Authorization: Bearer <KEY>"` |
| **Playwright** ([microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)) | Drive the GUI: deck screenshots, checking UI changes, uploading a bench file, debugging E2E | Pitches, M2, M7 | In `.mcp.json` | Works on the accessibility tree, so no vision model is needed. `cmd /c npx` is for native Windows; on Linux/macOS override at user scope with plain `npx`. CI uses `@playwright/test`, not this |
| **Chrome DevTools** ([ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)) | Performance traces, console and network for the WebGL2 waterfall (frame budget, GPU memory, tile fetches), which the accessibility tree can't see | M2 (first-tile and 60 fps gates), M7, M8 | In `.mcp.json` (`cmd /c npx -y chrome-devtools-mcp@latest`); elsewhere `claude mcp add chrome-devtools-mcp -- npx -y chrome-devtools-mcp`, or `/plugin marketplace add ChromeDevTools/chrome-devtools-mcp` then `/plugin install chrome-devtools-mcp` | Needs Chrome remote debugging locally |
| **Serena** ([oraios/serena](https://github.com/oraios/serena)) | LSP symbol-level reading and editing: read one function instead of a whole file, which keeps DSP and FEC review cheaper | M2 on | `claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd` | Older `uvx … --context ide-assistant` instructions are outdated |
| **Jupyter** ([datalayer/jupyter-mcp-server](https://github.com/datalayer/jupyter-mcp-server), BSD-3) | Notebook experiments with Claude running cells: AMC training and evaluation, estimator sweeps | M4 (optionally M2) | `/plugin marketplace add datalayer/jupyter-mcp-server`, then `/plugin install datalayer` | Needs a running JupyterLab |
| **Hugging Face** ([official](https://huggingface.co/docs/hub/en/hf-mcp-server)) | Find RF datasets and models; check cards and licences | M4 | `claude mcp add hf-mcp-server -t http "https://huggingface.co/mcp?login"` | Read-only token. **Never upload recordings** |
| **arXiv** ([blazickjp/arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server), Apache-2.0) | AMC and blind-FEC papers section by section; BibTeX for deck references | M4, M5 | `claude mcp add --transport stdio --scope user arxiv -- uvx arxiv-mcp-server` | Needs uv |
| **shadcn** ([ui.shadcn.com/docs/mcp](https://ui.shadcn.com/docs/mcp)), *conditional* | Live shadcn/ui component data (props, variants, structure) instead of hallucinated APIs | M7, **only if** we adopt shadcn/ui (today only the token names are shadcn-compatible) | `pnpm dlx shadcn@latest mcp init --client claude`, or `.mcp.json`: `{"mcpServers":{"shadcn":{"command":"npx","args":["shadcn@latest","mcp"]}}}` | Project scope, no secret |
| **GNU Radio** ([yoelbassin/gr-mcp](https://github.com/yoelbassin/gr-mcp), **GPL-3.0**), *optional* | Reference flowgraphs to cross-check `dsp/synth` | M1 | `/plugin marketplace add yoelbassin/gr-mcp`, then `/plugin install marconi` | Needs GNU Radio 3.10+. Dev-time only; never copy its code |

**Optional community skill (M1 on):** [briannasywa/sdr-skills](https://github.com/briannasywa/sdr-skills) (MIT; DSP, modulation, IQ formats, SigMF, GNU Radio 3.10, 8 small tools): `npx skills add briannasywa/sdr-skills --skill software-defined-radio`. On 27 Sep it was 10 days old with 0 stars: read its `SKILL.md` and tools first.

**Personal, user scope only:** a persistent-memory MCP such as [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem); shared context lives in CLAUDE.md and the docs. Cost: [ryoppippi/ccusage](https://github.com/ryoppippi/ccusage) reads local session logs (`npx ccusage@latest` for a one-off daily/per-session report, `npx ccusage@latest monthly` for the aggregate), no API key.

**Deliberately not added:** a filesystem MCP (built-in tools cover it); database or cloud MCPs (local SQLite, air-gapped product); any MCP that would upload recordings; Task Master (PLAN §0 is the tracker, `plan-status` keeps it current); generic "token-saving"/"context mode" servers claiming 90 %+ savings (independent benchmarks found some *increase* cost; `ponytail` is the one with a validated gain, so measure before adding another).

## 6. UI/design toolkit notes

The frontend is an analyst instrument with a fixed identity (PLAN §4), so the animated shadcn kits (Magic UI, Aceternity, Watermelon UI, Motion Primitives, coss ui/Origin UI) are skipped: licensing and visual-noise risk for no benefit.

- **IQEngine** ([GitHub](https://github.com/IQEngine/IQEngine), MIT): the reference for tiled spectrogram rendering (M2) and recording management (M7); see [PLAN §3](../docs/PLAN.md#3-architecture) and [STANDARDS §3](../docs/STANDARDS_TO_BEAT.md#3-open-source-prior-art).
- **Motion** (`motion.dev`, MIT): a plain npm package, not installed. Add in M7 only if the before/after diff or stage transitions need it, respecting reduced motion (PLAN §2).
- **tweakcn:** retired once M0 fixed the palette in `frontend/src/styles/index.css`; contrast is checked by axe in E2E.

## 7. Custom project skills

Each skill is `.claude/skills/<name>/SKILL.md`, committed; build and test with `skill-creator`. **Exist:** `plan-status` (repo vs PLAN §0, never ticking without evidence), `gen-iq` (a scratch script calling `dsp.synth.chain.generate` and `write_sigmf`: `.sigmf-data` + `.sigmf-meta` with the truth as annotations), `inspect-iq` (`tools/inspect_iq.py`), `sigmf-check` (`uvx --from sigmf sigmf_validate -v`), `bench-run` (`uv run bench run …`, `uv run python -m bench.sniffer`: `bench/results/bench-v0-<set>.{json,md}` plus a diff table; refuses if the sealed set was touched). Read their files for the steps. **To create** in the milestone shown:

| Skill | What it does | Runs | Output | Create in |
|---|---|---|---|---|
| `sanket-brand` | Applies the PLAN §4 identity outside the app (decks, artifacts, PDF reports): tokens from `index.css`, IBM Plex, evidence as glyph + label + colour, *synthetic* labels | Reads `brand.ts`, `styles/index.css`, `levelStyles.ts` | Output matching the GUI | Pitches |
| `rival-scan` | Re-runs the [STANDARDS §10](../docs/STANDARDS_TO_BEAT.md#10-how-to-refresh-this-document) searches; fetches trees and READMEs of new or changed repos; diffs against the matrix | GitHub MCP or `gh api` | Proposed edits to STANDARDS | Pitches |
| `claim-check` | Finds every number in README, deck and docs and matches it to a `bench/` result, a STANDARDS target (labelled as one) or a [STANDARDS §11](../docs/STANDARDS_TO_BEAT.md#11-references) reference | grep + `bench/results/` | Unsupported claims | Pitches |
| `eval-amc` | Evaluates an AMC checkpoint on our in-scope set, TorchSig, HisarMod, RadioML 2018.01A (corrected labels) and the null set | `ml.evaluate` | Accuracy-vs-SNR chart, confusion matrix, reliability diagram, open-set AUROC/FPR@95/OSCR per SNR bin, model-card update | M4 |
| `fec-catalogue` | Adds or verifies a conv/RS/LDPC entry: encode → channel → blind ID → decode round trip, with a licence/source note | pytest on that entry | Catalogue entry + test | M5 |
| `system-catalogue` | Adds or verifies a known-system entry: specification and licence note, a `dsp/synth` preset, blind chain → Match gives VERIFIED, near-miss null files that must not match | pytest + `bench-run --null` | `catalogue.toml` entry + synth preset + tests | M6 |
| `decoder-truth` | Runs the matching reference decoder (readsb, AIS-catcher, rtl_433, multimon-ng, SatDump, redsea) on a real capture as a **subprocess**; keeps only CRC-passing frames as SigMF annotations | subprocess + `sigmf` | `.sigmf-meta` with protocol-level truth | M8 |
| `judge-drill` | Quizzes the presenter on likely judge questions (no metadata, how a decode is proven, accuracy at 0 dB, overlapping signals, pseudo-random interleavers, offline, why not Krypto500 or GNU Radio) plus random module questions, scored against PROBLEM_STATEMENT, the README limits and STANDARDS | — | Transcript with gaps | M8 |

**Subagents** (`.claude/agents/`, both exist): `evidence-auditor` (from M1: every new output a Parameter with the right level, no silent defaults, VERIFIED only from proof) and `dsp-reviewer` (from M2: units, sample-rate assumptions, matched-filter and timing phase on DSP changes).

## 8. Hooks and permissions

- **Formatting:** a `PostToolUse` hook (`.claude/hooks/format_python.sh`, in `.claude/settings.json`) runs `ruff format` and `ruff check --fix` on a `.py` file right after Claude edits it, and never fails the edit. **pre-commit** (`.pre-commit-config.yaml`: large-file guard, merge-conflict, TOML and YAML checks, ruff check and format, ESLint, licence check) applies to every commit whoever wrote it; install once per clone with `uv run pre-commit install`. CI runs the same checks.
- **Permissions:** `.claude/settings.json` (committed) allows the test, lint, typecheck, build, e2e, licence, pre-commit and read-only `gh` commands without prompting; extend with `fewer-permission-prompts` or edit with `update-config`. Personal overrides go in the git-ignored `.claude/settings.local.json`.
- **Optional `Stop` hook**, not set up: `uv run python -m pytest -q -x --lf`, so a turn doesn't end red. Add it with `update-config` if turns start ending with failing tests.

The research behind the plan is summarised as references in [STANDARDS §11](../docs/STANDARDS_TO_BEAT.md#11-references); the full research notes are in git history (removed 30 Sep 2026).
