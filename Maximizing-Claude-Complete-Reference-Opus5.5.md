# Maximizing Claude — Complete Reference (Opus 5.5 Edition, September 25, 2026)

A consolidated guide covering official and community skills, MCP connectors, GitHub repositories, extensions, platform features, UI/design resources, the complete Claude Code reference, token/cost-saving strategies, an implementation walkthrough, and a fully verified caveats & advanced token-saving addendum.

***

## How to use this document

This is a merged, deduplicated version of everything researched in this conversation, organized into one reference. Where later research corrected earlier findings (e.g., Opus 5.5 superseding Opus 5 as the Claude Code default), **the corrected version is what appears in the main body** — superseded claims are preserved only in the dedicated "Caveats Resolved" section (Part 9) for transparency. Confidence markers are used throughout:

- ✅ **Confirmed** — verified against an official Anthropic source or a vendor's own documentation.
- 🔧 **Corrected** — an earlier claim in this research process was wrong; the corrected fact is shown.
- ◐ **Secondary/unverified** — reported by credible secondary sources but not confirmed against a primary source.
- ❓ **Unverified/unconfirmed** — could not be checked in the time available; treat as a lead, not a fact.

***

## TL;DR — the six highest-impact takeaways

1. **Model routing has changed with Opus 5.5.** Released September 22, 2026 at $4/$20 per million tokens, Opus 5.5 is now the default Opus everywhere, including on Claude Code's Pro and Team Standard plans (which previously defaulted to Sonnet). It performs near Fable 5.1 level at roughly 40% lower cost than Opus 5. Default to Opus 5.5 at its default (medium) effort; use Sonnet 5 for routine work and Haiku 4.5 for subagents/bulk tasks; reserve Fable 5.1 for rare escalations.
2. **Prompt caching is the single biggest cost lever**, by a wide margin — Anthropic's own measurements show 2.7–5.3× cost reduction in agent loops, with one case falling 83%. Never let volatile text (timestamps, changing tool sets, per-request IDs) sit ahead of your cached prefix, and never change model/effort/tools mid-session — any of these silently busts the cache.
3. **Popular "token-saving" third-party tools mostly underdeliver or backfire.** Independent JetBrains benchmarks found the caveman skill saved 8.5% against an advertised 65%; rtk actually *increased* cost 7.6% at low effort against an advertised 60–90% saving. Only the Ponytail minimalism skill showed a real, statistically solid signal (−10.3% cost against an advertised −20%). Validate any such tool yourself before trusting its own savings counter.
4. **Skills, MCP connectors, and Claude Code plugins are the practical unlock for "maximizing" Claude.** Install Anthropic's 17 official skills (document creation, frontend-design, skill-creator, etc.), a small set of high-value MCP servers (Context7, Playwright, GitHub, and any dev-platform servers you use), and adopt Claude Code's memory/hooks/subagents/plugins system deliberately rather than ad hoc.
5. **For UI/frontend work**, pair the official `frontend-design` skill with a shadcn-compatible animated component registry (Magic UI, Aceternity, Motion Primitives, Watermelon UI, coss ui, etc.), install the shadcn MCP server, and close the loop with a Playwright screenshot-verification cycle rather than trusting one-shot generation.
6. **Session hygiene in Claude Code compounds with caching.** `/clear` between unrelated tasks (free), `/compact` only at natural breaks with focus instructions, a lean CLAUDE.md (under ~200 lines) with skills carrying the detail, and disabling unused MCP servers together routinely cut real-world spend well below Anthropic's own benchmark of "$13/developer/active day, $150–250/developer/month."

***

## Table of contents

- **Part 1 — Official Anthropic resources:** GitHub repos, the Skills system, MCP fundamentals
- **Part 2 — Skills, organized by category:** UI/design, Claude Code/engineering, research, writing, planning, documents, data, learning, productivity, meta, and token-saving skills
- **Part 3 — MCP servers, organized by category:** docs/code context, browser/testing, UI/design, dev platforms, databases, web search/scraping, research/academic, knowledge/productivity, memory/reasoning, cloud/DevOps, plus discovery registries
- **Part 4 — GitHub repositories** for each category above, with star counts and status where verified
- **Part 5 — Extensions:** browser, IDE, Office add-ins, Desktop Extensions, chat integrations, launchers, mobile
- **Part 6 — UI component libraries & design resources:** the full "Ponytail / Watermelon UI / Motion Primitives and friends" catalog, plus AI UI generators, icons, animation libraries, and design-inspiration sources
- **Part 7 — Claude Code: the complete reference:** every official feature, official guidance, community frameworks and orchestrators, and power-user workflows
- **Part 8 — Anything else Claude can be used for:** claude.ai features, plan comparison, current pricing
- **Part 9 — Caveats resolved:** a full verification table against the original research pass
- **Part 10 — Token & cost-saving playbook (consolidated + advanced):** API-level, Claude Code–level, claude.ai–level, and prompting-level techniques, each rated by evidence quality
- **Part 11 — What NOT to do:** tools and habits independently shown to backfire
- **Part 12 — Step-by-step implementation guide:** a concrete, ordered walkthrough with exact commands and config snippets
- **Part 13 — Prioritized checklists**
- **Part 14 — Final caveats and what remains unverified**

***

# Part 1 — Official Anthropic Resources

## 1.1 Current model lineup (verified September 25, 2026)

| Model | API ID | Input / Output per MTok | Cache read | Notes |
|---|---|---|---|---|
| **Claude Opus 5.5** | `claude-opus-5-5` | **$4 / $20** | **$0.20** | Released Sep 22, 2026. 1M context. 5-min cache write $5, 1-hour write $8. Fast mode (research preview) $8/$40, up to 2.5× faster, first-party API only, no Batch. Adaptive thinking always on — controlled via effort levels (default: medium), cannot be disabled. |
| Claude Fable 5.1 | `claude-fable-5-1` | $10 / $50 | $0.25 | Released Sep 1, 2026 alongside Mythos 5.1. Extra safety classifiers for biology, cybersecurity, and AI R&D. Cache write: $12.50 (5-min) / $20 (1-hour). |
| Claude Opus 5 | `claude-opus-5` | $5 / $25 | $0.50 | Released Jul 24, 2026. Still available pinned; no longer the default Opus. |
| Claude Sonnet 5 | `claude-sonnet-5` | $2 / $10 | $0.20 | Native 1M context window. Uses a newer tokenizer producing ~30% more tokens than Sonnet 4.6 for the same text (official). Cache write: $2.50/$4. |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | $1 / $5 | $0.10 | Cache write: $1.25/$2. Haiku 5.5 announced as "coming weeks" but **not yet released** as of Sep 25, 2026. |
| Claude Mythos 5.1 / Mythos Preview | restricted | n/a | n/a | Only available to vetted organizations via Project Glasswing, Claude Security, and verification programs. |

Sonnet 5.5 and Haiku 5.5 were **not released** as of this writing; Anthropic's launch post says they will follow "in the coming weeks." Re-check pricing and routing advice once they ship.

**Fable/Mythos access timeline** (for context): released Jun 9, 2026 → suspended Jun 12 under a U.S. Department of Commerce export-control directive → partially restored Jun 26 → controls lifted Jun 30 → full access restored Jul 1 → Fable 5 became a standard higher-tier feature Jul 20 → Fable 5.1/Mythos 5.1 released Sep 1. Anthropic's official statement: anthropic.com/news/fable-mythos-access.

## 1.2 Official Anthropic GitHub repositories

**Core developer tools:**
- **anthropics/claude-code** — the agentic coding CLI (terminal, IDE, desktop, web). ~145k★, 23.1k forks (community-reported; re-verify before citing).
- **anthropics/claude-agent-sdk-python** / **-typescript** — SDKs for building custom agents on the same harness that powers Claude Code.
- **anthropics/anthropic-sdk-python / -typescript / -go / -java / -csharp / -ruby / -php** — official API client libraries.
- **anthropics/anthropic-cli** — Go-based CLI for the Claude API.

**Learning & examples:**
- **anthropics/claude-cookbooks** (formerly anthropic-cookbook) — recipes for RAG, tool use, vision, embeddings, context engineering, prompt caching.
- **anthropics/courses** — API fundamentals, Prompt Engineering Interactive Tutorial, Real World Prompting, Prompt Evaluations, Tool Use.
- **anthropics/prompt-eng-interactive-tutorial** — the standalone 9-chapter prompt-engineering tutorial.
- **anthropics/claude-quickstarts** — deployable starter apps (customer support agent, financial data analyst, computer-use demo).

**Skills & plugins:**
- **anthropics/skills** — the official public Agent Skills repo. **17 skills** (confirmed count; see Part 2.1). ~178k★ (community-reported).
- **anthropics/claude-plugins-official** — Anthropic-managed plugin marketplace for Claude Code, added automatically on first interactive launch. Plugin count not officially published (~101 reported March 2026; ~222 per third-party index claudemarketplaces.com — treat as approximate).
- **anthropics/claude-plugins-community** — read-only mirror of the community plugin marketplace.
- **anthropics/knowledge-work-plugins** — role-based plugin bundles for knowledge workers in Claude Cowork.

**CI/CD & automation:**
- **anthropics/claude-code-action** / **claude-code-base-action** — GitHub Actions to run Claude Code in CI/CD and power `@claude` tagging on issues/PRs.
- **anthropics/claude-tag-plugins** — plugins powering the `@claude` GitHub/Slack tagging integration.

**MCP org (modelcontextprotocol/*):**
- **modelcontextprotocol/servers** — reference MCP servers. **Many original reference implementations (GitHub, Postgres, Slack, Brave, Puppeteer) were archived in 2025** — use vendor-official servers instead. Still-maintained reference servers: **Fetch, Filesystem, Git, Memory, Sequential Thinking, Time, Everything**.
- **modelcontextprotocol/registry** — the official, API-first MCP server registry (registry.modelcontextprotocol.io), community-governed under the Linux Foundation's Agentic AI Foundation (MCP was donated there Dec 9, 2025; co-founded by Anthropic, Block, and OpenAI, with platinum members AWS, Bloomberg, Cloudflare, Google, Microsoft).

## 1.3 What "Skills" are — the mechanism

A skill is a folder containing a `SKILL.md` file (YAML frontmatter with `name` + `description`, followed by markdown instructions), optionally bundled with scripts and reference files. Claude uses **three-level progressive disclosure**:
1. Only the ~100-token metadata (name + description) loads at session start.
2. The full instruction body (kept under ~5,000 words) loads only when a task matches the description.
3. Bundled resources (scripts, references, assets) load only on demand.

This means installing many skills carries minimal token overhead — the cost is in the quality of the *description* (which determines whether Claude picks the right skill), not in raw count. Skills work identically across claude.ai, Claude Code, and the API (via the Skills API with code execution). They require a paid plan with code execution enabled.

## 1.4 What MCP is — the mechanism

MCP (Model Context Protocol) is an open standard, originally authored by Anthropic and now a Linux Foundation / Agentic AI Foundation project, defining how AI applications connect to external tools and data via "servers." As of Anthropic's December 2025 donation announcement, MCP had "over 97 million monthly SDK downloads, 10,000 active servers, and first-class client support across major AI platforms." Servers can be **local** (run on your machine, configured via `claude mcp add` or `claude_desktop_config.json`) or **remote/hosted** (reached over HTTPS, added as custom connectors — note that a remote server behind your VPN/firewall won't connect from Anthropic's cloud).

**Adding connectors in claude.ai/Desktop:** Settings → Connectors → Browse (directory) or Add custom connector (paste a remote MCP URL, optionally with OAuth credentials). Pro/Max users add their own; Team/Enterprise requires an Owner to add org-wide first. Free users are limited to one custom connector.

**In Claude Code:** `claude mcp add <name> [--transport http|sse] [--scope local|project|user] -- <command or URL>`. Scopes: local (just you, this machine), project (`.mcp.json`, committed to the repo), user (all your projects). Debug with `/mcp`.

***
# Part 2 — Skills, Organized by Category

## 2.1 Official Anthropic skills (anthropics/skills — 17 skills, confirmed)

| Skill | Category | What it does |
|---|---|---|
| `docx` | Documents | Creates/edits Word files, including tracked changes, comments, formatting. Source-available, not fully OSS. |
| `pdf` | Documents | Extracts text/tables, merges/splits, fills forms, OCR, watermarks. |
| `pptx` | Documents | Builds decks from templates or from scratch, with layouts and speaker notes. |
| `xlsx` | Documents / Data | Formulas, charts, pivot tables, cleaning messy data. |
| `frontend-design` | UI/Design | Distinctive, production-grade interfaces; explicitly counters "AI slop" aesthetics (generic gradients, default fonts). |
| `web-artifacts-builder` | UI/Design | Multi-component artifacts built with React + TypeScript + Tailwind + shadcn/ui. |
| `webapp-testing` | Engineering | Tests local web apps with Playwright. |
| `theme-factory` | UI/Design | Applies consistent visual themes to artifacts and documents. |
| `canvas-design` | Design | Layout-based visual designs output as PNG/PDF. |
| `algorithmic-art` | Creative | Generative art with p5.js. |
| `brand-guidelines` | Writing/Design | Applies brand colors/fonts; usable as a template for your own brand kit. |
| `slack-gif-creator` | Productivity | GIFs sized/optimized for Slack. |
| `doc-coauthoring` | Writing | Structured collaborative document-drafting workflow. |
| `internal-comms` | Writing | Status updates, newsletters, FAQs in your organization's formats. |
| `mcp-builder` | Engineering/Meta | Guides building high-quality MCP servers. |
| `claude-api` | Engineering | Current Claude API/SDK usage patterns across 8 languages; bundled with Claude Code. |
| `skill-creator` | **Meta** | Writes, tests (with evals), and improves your own skills — the highest-leverage skill once basics are covered. |

**Newer official "skills-as-plugins":** a Salesforce plugin (37 pre-built sales skills, beta, org-approved); `anthropics/knowledge-work-plugins` (role-based bundles for sales/finance/data/productivity, e.g. `/plugin install brand-voice@knowledge-work-plugins`); Enterprise admins can enable automatic security scanning of third-party skills/plugins.

## 2.2 UI / Design & frontend skills

- **`frontend-design`** (official, above) — the foundational skill for non-generic UI.
- **`web-artifacts-builder`** (official, above) — for building shadcn/React artifacts directly.
- **`avoid-ai-design`** (community, `funboy322/avoid-ai-design`) — audits and rewrites existing UI to remove AI "tells" (purple-to-blue gradients, default Inter font, unmodified default shadcn). The de-slop counterpart to frontend-design.
- **`pbakaus-impeccable`** (community) — skills-only plugin for iterating production-grade frontend interfaces with real code.
- **shadcn-compatible registry skills** — pair with the shadcn MCP server (see Part 3) rather than a standalone skill.

## 2.3 Claude Code / software engineering skills

- **`obra/superpowers`** — the most widely adopted engineering-discipline skill pack. Covers brainstorming → planning → TDD → systematic debugging → verification-before-completion → code review, using an "Iron Laws" methodology (tests first, strict red-green-refactor) with isolated git worktrees. ~290k★ (community-reported).
- **Official `claude-plugins-official` bundles:** `feature-dev`, `code-review`, `commit-commands`, `security-guidance`, `frontend-design`, plus ~12 language-server (LSP) plugins for precise symbol navigation. Install: `/plugin install code-review@claude-plugins-official`.
- **`wshobson/agents`** and **`davila7/claude-code-templates`** — large collections of subagents, commands, and skills (see Part 4 for repo details).

## 2.4 Research skills

- No dedicated "research" skill exists in anthropics/skills; the strongest options are claude.ai's built-in **Research mode** (Part 8) and research-oriented MCP servers (Part 3).
- Opus 5.5 shows markedly better citation fidelity: in Anthropic's own testing, "16 out of 18 of Opus 5.5's reports cleared our quality bar, where any invented figure or quote would have failed. Neither Fable 5.1 nor Opus 5 cleared that bar in any attempt."
- Build your own fact-check skill with `skill-creator`, e.g., "every number needs a URL plus a verbatim quote."

## 2.5 Writing skills

- **`doc-coauthoring`**, **`internal-comms`**, **`brand-guidelines`** (official, above).
- **De-AI-ifying prose:** no single dominant, actively-maintained community skill was confirmed. Two approaches work better than hunting for one: (1) put a banned-phrases/style list directly in claude.ai Styles or a custom skill — Opus 5.5 follows explicit style rules more reliably than earlier models; (2) pair a terse-output style with the caveman skill for shorter prose (modest, independently measured gains — see Part 10).

## 2.6 Planning / project management / spec-driven development skills

- **BMAD-METHOD** (`bmad-code-org/BMAD-METHOD`) — agile agent personas (analyst, PM, architect, dev, QA) producing versioned artifacts from PRD through architecture through stories. Reported #1 on GitHub Trending Aug 13, 2026; install via `npx bmad-method install`.
- **GitHub Spec Kit** (`github/spec-kit`) — lightweight spec-driven toolkit (`/specify`, `/plan`, `/tasks`); bring your own agent.
- **Claude Task Master** (`eyaltoledano/claude-task-master`) — turns a PRD into ordered tasks, e.g. `task-master parse-prd prd.txt`. ~26k★ (community-reported).

## 2.7 Documents & office files

`docx`, `pptx`, `xlsx`, `pdf` (all official, Part 2.1). Work identically on claude.ai, Claude Code, and the API.

## 2.8 Data & analytics

`xlsx` (official). Also the knowledge-work "data" plugin bundle, and third-party agent tools like Hex (which now runs on Opus 5.5).

## 2.9 Learning / education

No standalone skill; use claude.ai's built-in **Learning mode** and Claude Code's **Explanatory/Learning output styles**, which leave `TODO(human)` tasks for you to complete rather than fully solving problems (Part 8, Part 7.6).

## 2.10 Productivity & knowledge work

`slack-gif-creator`, `internal-comms`, `knowledge-work-plugins` bundle, the Salesforce-in-Claude plugin.

## 2.11 Meta-skills

`skill-creator` and `mcp-builder` (official). The Agent Skills spec lives at agentskills.io and in `anthropics/skills/spec`.

## 2.12 Token-saving skills — independently verified evidence

This is the category most prone to inflated marketing claims. Every figure below comes from Denis Shiryaev's paired A/B benchmark series on the JetBrains AI blog (July 2026), run on Claude Code with claude-sonnet-5:

| Skill | Link | Advertised savings | **Independently measured** | Verdict |
|---|---|---|---|---|
| **Ponytail** | github.com/DietrichGebert/ponytail (~145.5k★, MIT, created Jun 12 2026) | −54% code, −20% cost, −27% time | **−15% code, −10.3% cost (p=0.004), −11% time**, over 80 paired tasks — "the first tool in this series with a statistically solid cost-saving signal." Gains concentrate on larger builds (−31% code on 300+ line tasks). | ✅ **Install.** The only tool with a solid signal. |
| **caveman** (terse output style) | community | −65% | **−8.5%**, even with the skill forcibly activated ("the ceiling, not the usual-case result"), 86/87 SkillsBench tasks, ~$106 spend. Affects prose, not code/tool-call volume. | ◐ Small, real gains — not the advertised figure. |
| **rtk** ("Rust Token Killer") | community | −60–90% | **+7.6% cost at low effort** (p=0.004, worse than baseline), ±0% at high effort, 425 trials (~$320 spend). Its own "tokens saved" counter claims 99.8% by counting raw untruncated output as the counterfactual — Claude Code already truncates large tool results, so this inflates the claim. Also bypassed by Claude Code's built-in Read/Grep tools. | ❌ **Do not install.** Makes costs worse. |

**How Ponytail actually works:** before writing anything, it walks a "ladder" — does this need to exist? is it already in the codebase? is it in the stdlib? is there a native platform feature? an installed dependency? can it be one line? Validation, error handling, security, and accessibility are explicitly excluded from the cuts. Install: `claude mcp/plugin marketplace add DietrichGebert/ponytail` then `/plugin install ponytail@ponytail`. Also available for Codex, Gemini CLI, Copilot CLI. Deactivate with "stop ponytail" / "normal mode."

**Lesson for this whole category:** treat every self-reported "tokens saved" dashboard as marketing until validated against your own bill with `/usage` or ccusage in a paired before/after test (see Part 10 and Part 11).

***
# Part 3 — MCP Servers, Organized by Category

**Before adding any server:** every MCP tool description consumes context. Claude Code caps each server's tool descriptions and instructions at 2,048 characters by default (override with `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH`, added in v2.1.280). Tool *definitions* are deferred by default (only names/server instructions load until a tool is actually used). MCP output is capped at 25,000 tokens by default (`MAX_MCP_OUTPUT_TOKENS`), with a 10,000-token warning. Run `/context` after adding servers to see the real overhead, and prefer a CLI (`gh`, `aws`, `sentry-cli`) over an MCP server when one exists — Claude Code's own cost docs say CLIs "are still more context-efficient than MCP servers because they don't add any per-tool listing."

Legend: **[O]** = official/vendor-maintained. **[C]** = community-maintained. ✅ = install command verified against vendor docs this pass. ⚠ = documented elsewhere but not re-verified this pass — check the vendor README before use.

## 3.1 Documentation & code context

- **Context7 [O, Upstash]** — github.com/upstash/context7 (~62.4k★). Pulls current, version-specific library docs into the prompt to reduce hallucinated APIs.
  ✅ `claude mcp add --scope user --header "Authorization: Bearer YOUR_API_KEY" --transport http context7 https://mcp.context7.com/mcp`
  *(Note: Context7's own docs are inconsistent — the quickstart shows a `CONTEXT7_API_KEY` header instead. Local alternative: `npx -y @upstash/context7-mcp --api-key YOUR_API_KEY`. Newer README also suggests `npx ctx7 setup --claude`.)*
- **Serena [C, oraios]** — github.com/oraios/serena. Symbol-level semantic code retrieval/editing via LSP — Claude reads functions instead of whole files. A major token saver in large repos.
  ✅ `serena setup claude-code` (recommended), or `claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd`. *(The README warns against marketplace installs; older `uvx ... --context ide-assistant` commands circulating online are outdated.)*

## 3.2 Browser automation & testing

- **Playwright MCP [O, Microsoft]** — github.com/microsoft/playwright-mcp (~36.8k★). Drives a real browser via accessibility snapshots.
  ✅ `claude mcp add playwright npx @playwright/mcp@latest`. Also installable as a plugin: `playwright@claude-plugins-official`. *(Microsoft's README now also recommends a Playwright-CLI-plus-skills route for coding agents, which uses fewer tokens than a persistent MCP server — see Part 3.11.)*
- **Chrome DevTools MCP [O, Google]** — github.com/ChromeDevTools/chrome-devtools-mcp. Performance traces, console/network inspection.
  ✅ `claude mcp add chrome-devtools --scope user npx chrome-devtools-mcp@latest`, or as a plugin: `/plugin marketplace add ChromeDevTools/chrome-devtools-mcp` then `/plugin install chrome-devtools-mcp@chrome-devtools-plugins`.
- **vercel-labs/agent-browser [O, Vercel Labs]** — a browser-automation CLI for agents, shipped as a plugin.

## 3.3 UI / design

- **shadcn MCP [O]** — Browse/install components from the shadcn registry and any shadcn-compatible registry (Magic UI, coss ui, etc.).
  ✅ `.mcp.json`: `{"mcpServers":{"shadcn":{"command":"npx","args":["shadcn@latest","mcp"]}}}` — generated by `npx shadcn@latest mcp init --client claude`. *(No separate `claude mcp add` form is vendor-documented.)*
- **Figma Dev Mode MCP [O]** — developers.figma.com. Pulls real design tokens (not pixels) from Figma files.
  ✅ Remote: `claude plugin install figma@claude-plugins-official`, or `claude mcp add --transport http figma https://mcp.figma.com/mcp`. Desktop-local server is different: `http://127.0.0.1:3845/mcp` (needs the Figma desktop app's Dev Mode enabled).
- **21st.dev Magic MCP [C/vendor]** and **Magic UI MCP [vendor]** — component search/generation directly in the editor. ⚠ Install commands not re-verified this pass — check 21st.dev and magicui.design docs.

## 3.4 Dev platforms & version control

- **GitHub MCP [O]** — github.com/github/github-mcp-server (~32.6k★).
  ✅ `claude mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp","headers":{"Authorization":"Bearer YOUR_GITHUB_PAT"}}'`. Docker alternative: `claude mcp add github -e GITHUB_PERSONAL_ACCESS_TOKEN=YOUR_GITHUB_PAT -- docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server`. *(On Windows, `add-json` may return "Invalid input" — use `claude mcp add --transport http ...` instead.)*
- **Linear [O]** — linear.app/docs/mcp.
  ✅ `claude mcp add --transport http linear-server https://mcp.linear.app/mcp`, then `/mcp` to authenticate. Read-only endpoint at `/mcp/readonly`. The older SSE endpoint is being phased out.
- **Sentry [O]** — sentry.io/cookbook.
  ✅ `claude mcp add --transport http sentry https://mcp.sentry.dev/mcp`.
- **Atlassian (Rovo/Jira/Confluence) [O]** — github.com/atlassian/atlassian-mcp-server.
  ⚠ **Unconfirmed endpoint.** One source shows `claude mcp add --transport http atlassian https://mcp.atlassian.com/v2/mcp`; other official pages reference `v1/mcp/authv2`. **Check the current README before use.**
- **GitLab, Prisma** — not re-verified this pass; no vendor command confirmed.

## 3.5 Databases & backend

- **Supabase [O]** — supabase.com/docs/guides/getting-started/mcp.
  ✅ `claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp?features=docs%2Caccount%2Cdatabase%2Cdebugging%2Cdevelopment%2Cfunctions%2Cbranching"`, then `/mcp` → Authenticate. Supports `read_only=true` and `project_ref=` query params.
- **Neon [O]** — neon.com guide.
  ✅ `claude mcp add --transport http neon https://mcp.neon.tech/mcp`. Local alternative: `claude mcp add neon -- npx -y @neondatabase/mcp-server-neon start "<KEY>"`.
- **Postgres** — the original archived reference server should **not** be used; prefer a vendor-official or actively maintained community server.
- **AWS (awslabs/mcp), Docker MCP Toolkit/Gateway, Kubernetes** — not re-verified this pass.

## 3.6 Web search & scraping

- **Fetch [O reference, maintained]** — fetches a URL, converts to markdown.
- **Exa [O]** — github.com/exa-labs/exa-mcp-server.
  ✅ `claude mcp add --transport http exa https://mcp.exa.ai/mcp`. Restrict tools with a `?tools=...` query param to save context.
- **Firecrawl [O]** — endpoints exist (`https://mcp.firecrawl.dev/v2/mcp` with a Bearer key, or local `npx -y firecrawl-mcp` with `FIRECRAWL_API_KEY`), but a specific Claude Code `claude mcp add` one-liner was **not confirmed** against docs.firecrawl.dev this pass.
- **Brave Search, Tavily, Perplexity** — not re-verified this pass; the original Brave reference server in modelcontextprotocol/servers was archived, so use the vendor's own package.
- Claude.ai's built-in web search and Claude Code's WebSearch/WebFetch tools often make a separate search MCP unnecessary.

## 3.7 Research & academic

- arXiv, Semantic Scholar, and PubMed community servers exist, but **maintenance status was not verified this pass.** Check the official MCP Registry for recently-updated entries before installing.
- For biology-related work on Opus 5.5, apply to the **Life Sciences Verification Program** — otherwise safety classifiers will reroute some requests to Fable-level safeguards or refuse more often.

## 3.8 Knowledge / notes & productivity

- **Notion, Google Drive, Gmail, Google Calendar, Slack, Microsoft 365 [O Connectors]** — add via claude.ai → Settings → Connectors. The Microsoft 365 connector gained write tools on July 7, 2026 (per secondary source, Vantaige).
- **Obsidian [C]** — several community servers exist; maintenance not verified this pass.

## 3.9 Memory & reasoning

- **Memory [O reference]** — knowledge-graph-based persistent memory.
- **Sequential Thinking [O reference]** — still maintained, but with Opus 5.5's always-on adaptive thinking, it adds little value; mainly useful on Haiku-driven subagents.

## 3.10 Cloud / DevOps

- **Vercel [O]** — vercel.com docs (Beta). ✅ `claude mcp add --transport http vercel https://mcp.vercel.com`.
- **Cloudflare [O]** — developers.cloudflare.com. ✅ Plugin route: `/plugin marketplace add cloudflare/skills` then `/plugin install cloudflare@cloudflare`. Generic URL `https://mcp.cloudflare.com/mcp` exists, but no vendor-documented `claude mcp add` form was found.
- **AWS, Kubernetes** — not re-verified this pass.

## 3.11 Token-saving MCP patterns

- **Serena** and **Context7** (above) reduce context by retrieving only what's needed instead of whole files/pages.
- **Playwright CLI + skills**, instead of a persistent Playwright MCP server — Microsoft's own README now recommends this route for coding agents specifically because it uses fewer tokens.
- **"context-mode" and similar "96–98% savings" MCP servers:** treat these claims skeptically. The commonly-cited 96% figure comes from the vendor's own 21-scenario fixture benchmark; **no independent verification was found.** ComputingForGeeks installed but did not independently benchmark it, and flagged both uncited enterprise-logo claims and a non-OSI Elastic License v2. Given that a similarly-marketed tool (rtk) was independently shown to *increase* cost, do not install any "token saver" MCP server without measuring it yourself first.

## 3.12 MCP discovery registries

- **Official MCP Registry** — registry.modelcontextprotocol.io (also mirrored at github.com/mcp). The canonical, API-first, community-governed catalog under the Linux Foundation's Agentic AI Foundation.
- **Smithery** (smithery.ai) — registry + hosting/runtime with managed OAuth and a "Toolbox" meta-MCP; ~7,000+ servers.
- **Glama** (glama.ai/mcp) — largest by index (auto-crawls GitHub), with quality tiers.
- **mcp.so** — broad marketplace with a playground.
- **PulseMCP** (pulsemcp.com) — curated, hand-reviewed directory with weekly-visitor estimates.
- **GitHub awesome lists:** `punkpeye/awesome-mcp-servers`, `wong2/awesome-mcp-servers`, `appcypher/awesome-mcp-servers`, `win4r/Awesome-Claude-MCP-Servers`.
- **Anthropic Connectors Directory** — claude.com/connectors and Settings → Connectors inside claude.ai; Anthropic-reviewed remote connectors.
- **Claude Code plugin directories** — claude.com/plugins (official); claudemarketplaces.com and claudepluginhub.com (third-party; the latter offers a "safe" feed excluding code-execution hooks).

> **Caveat on server counts:** directory totals in the tens of thousands are inflated by unmaintained experiments and duplicates. Anthropic itself cited ~10,000 *active* servers as of December 2025 — the set of genuinely maintained, vendor-official servers is far smaller. Prefer vendor-official entries.

***
# Part 4 — GitHub Repositories by Category

*Star counts marked "community-reported" were surfaced by secondary sources during research and were not independently re-verified against the live GitHub page in every pass — treat as approximate and re-check before citing publicly. Repos with no star count shown were not measured at all.*

## 4.1 Official Anthropic (see also Part 1.2)

anthropics/claude-code · anthropics/skills (~178k★) · anthropics/claude-plugins-official · anthropics/claude-plugins-community · anthropics/knowledge-work-plugins · anthropics/claude-cookbooks (~51k★) · anthropics/courses · anthropics/prompt-eng-interactive-tutorial (~35k★+) · anthropics/claude-quickstarts (~17k★) · anthropics/claude-agent-sdk-python / -typescript · anthropics/claude-code-action · anthropics/claude-code-base-action · anthropics/claude-tag-plugins

## 4.2 modelcontextprotocol org

modelcontextprotocol/servers (reference servers; many archived — see Part 1.2/3) · modelcontextprotocol/registry · MCP TypeScript/Python SDKs and spec

## 4.3 Claude Code workflows & frameworks (community)

| Repo | Stars | Status / note |
|---|---|---|
| obra/superpowers | ~290k (community-reported) | Active, v6.4.1 latest. Engineering-discipline skills. |
| DietrichGebert/ponytail | ~145.5k (community-reported) | Active. Minimalism plugin — the one token-saving tool with solid independent evidence. |
| bmad-code-org/BMAD-METHOD | ~52.8k (star-history.com, global rank #451) | Active (v6.x). Hit #1 GitHub Trending Aug 13, 2026. |
| github/spec-kit | not measured | Spec-driven development toolkit. |
| SuperClaude-Org/SuperClaude_Framework | ~23k (community-reported) | Command/persona framework; overlaps with superpowers — pick one. |
| ruvnet/claude-flow | not measured | Multi-agent swarm orchestration; advanced/heavy. |
| wshobson/agents | not measured | Large subagent + plugin collection (75+ plugins, 174+ skills reported). |
| VoltAgent/awesome-claude-code-subagents | not measured | Curated subagent definitions (100+ reported). |
| davila7/claude-code-templates | ~24.2k (community-reported) | CLI for installing agents/commands/MCPs + usage dashboard. Site: aitmpl.com. |
| Yeachan-Heo/oh-my-claudecode | ~24.9k (community-reported) | Multi-agent orchestration. |
| eyaltoledano/claude-task-master | ~26.4k (community-reported) | PRD → ordered task breakdown. |
| BloopAI/vibe-kanban | ~27.2k (community-reported) | ⚠ **Company (bloop) shut down Apr 10, 2026.** Continues as Apache-2.0, community-maintained, **transitioning to fully local architecture** (remote services, kanban issues/comments/projects/orgs being removed per the "Goodbye bloop" post). |

## 4.4 Token-saving / monitoring tools

- **ryoppippi/ccusage** — zero-setup CLI (`npx ccusage@latest`) parsing local Claude Code logs for daily/monthly/session/5-hour-block cost reports, with per-model and cache breakdowns; has a statusline mode.
- **sirmalloc/ccstatusline** — customizable, powerline-style statusline (model, context %, cost).
- **jarrodwatts/claude-hud** — ~27.5k (community-reported). Statusline HUD showing context health, tools, agents, todos.
- **phuryn/claude-usage** — local web dashboard for token usage/cost/session history.
- **getAsterisk/claudia** (formerly "opcode") — open-source Tauri GUI: session browser, checkpoints, custom agents, sandboxed execution, usage analytics, MCP management.

## 4.5 Awesome-lists

hesreallyhim/awesome-claude-code · punkpeye/awesome-mcp-servers (and wong2/, appcypher/, win4r/ variants) · travisvn/awesome-claude-skills · ComposioHQ/awesome-claude-skills (1000+ skills/plugins reported) · BehiSecc/awesome-claude-skills · abubakarsiddik31/claude-skills-collection · VoltAgent/awesome-claude-code-subagents · alvinunreal/awesome-claude (webfuse-com) · subinium/awesome-claude-code

*Quality varies across these lists — prefer ones that link back to original repos rather than re-hosting content.*

## 4.6 UI component libraries (pair with the shadcn MCP)

| Library | Status |
|---|---|
| shadcn-ui/ui | Active. The base registry ecosystem underlying most others below. |
| magicuidesign/magicui | Active. Animated components, shadcn-compatible. |
| **coss ui** (cosscom/coss) | ✅ Active successor to **Origin UI**, now built on Base UI. Mixed AGPLv3/MIT — `apps/origin` and `apps/ui` are MIT. Origin UI itself remains as a legacy snapshot with limited support. |
| tremorlabs/tremor | ◐ Vercel-owned, free/OSS, 35+ components/300 blocks — **no confirmed recent release activity**; treat as slow-moving. |
| ibelick/motion-primitives | Active. MIT. Animated React kit built on Motion + Tailwind. |
| Aceternity UI, Cult UI, Kokonut UI, React Bits, Watermelon UI | Popular animated/shadcn-style libraries — maintenance and star counts not re-verified this pass. |
| Tailwind Plus / Tailwind UI | ❌ **Closed to new customers** as of Shopify's Sep 9, 2026 acquisition of Tailwind Labs (existing buyers keep access; Tailwind CSS itself stays MIT). |

*(Full catalog of ~30 libraries, marketplaces, AI UI generators, icon sets, and animation libraries is in Part 6.)*

***
# Part 5 — Extensions

## 5.1 Browser

- **Claude in Chrome** (claude.com/claude-in-chrome) [Official] — a browsing agent that reads, clicks, and fills forms in your browser; supports multi-tab and scheduled tasks. Not available on mobile or non-Chrome browsers. Requires a paid plan (exact eligibility not re-verified this pass — check the product page).
- Claude Code can also drive Chrome via the Chrome DevTools MCP server (Part 3.2).

## 5.2 IDE

- **Claude Code for VS Code** [Official] — native panel, diffs, session management; v2.1.280 added session archiving. Auto permission mode is the default here too on Pro/Max/Team.
- **Claude Code [Beta] for JetBrains** [Official] — plugins.jetbrains.com/plugin/27310. ⚠ **Stale beta**: latest version 0.1.14-beta dated December 5, 2025 (no update in ~10 months as of this writing), rated ~2.3–2.4/5 from ~467 reviews, ~4.74M downloads. Requires the CLI installed separately.
- **Cursor / Windsurf** — both are VS Code forks; install the VS Code extension directly, or run `claude` in their integrated terminal.
- **GitHub Copilot** — Opus 5.5 is available in Copilot (Pro+, Max, Business, Enterprise) at list pricing.

## 5.3 Office / productivity add-ins (official, verified)

- **Claude for Excel, PowerPoint, and Word** — **generally available** on Pro, Max, Team, and Enterprise. Installed as one combined listing from Microsoft AppSource.
- **Claude for Outlook** — **beta** on paid plans, a separate AppSource listing.
- **Cross-app mode ("Let Claude work across files")** — lets one conversation span all four Office apps. On by default for Pro and Max; Team/Enterprise owners enable it under Organization settings → Office agents.
- **Requirements:** a Microsoft 365 subscription (perpetual Office 2016/2019 licenses are not supported). Cross-app mode does not work through Bedrock, Vertex, or Foundry deployments.

## 5.4 Claude Desktop extensions

- **Desktop Extensions (`.mcpb`, formerly `.dxt`)** — one-click local MCP server bundles, installed from the extensions directory inside Claude Desktop → Settings → Extensions. ❓ Current directory size/status not re-verified this pass.

## 5.5 Chat / work integrations

- **@Claude (Claude Tag)** [Official product] — mention Claude directly in Slack; org admins install it.
- **Microsoft Teams** — ❓ no official first-party Anthropic Teams app was confirmed this pass; third-party agents (e.g., "Viktor") run on Claude inside Teams.

## 5.6 Launcher / OS tools

- **Raycast / Alfred** — community extensions reportedly exist but were **not verified** this pass.
- The official Claude Desktop app has its own quick-entry hotkey and screenshot/highlight capture (per release notes).

## 5.7 Mobile

- **Claude iOS and Android apps** — full chat client, voice mode.
- **Claude Code Remote Control** — monitor and respond to a local Claude Code session from your phone (documented in Claude Code's model-config docs).

***
# Part 6 — UI Component Libraries & Design Resources

*This section answers the original "Ponytail, Watermelon UI, Motion Primitives and things like that" question in full.*

## 6.0 First: what those three names actually refer to

- **"Ponytail"** — **Not a UI library.** It is the Claude Code minimalism skill/plugin covered in Part 2.12 and Part 4.3 (`DietrichGebert/ponytail`, ~145.5k★, MIT). It is the only prominent tool by this name in the Claude/AI-coding context, so it's most likely what was meant — but note it belongs in the "token-saving skills" category, not "UI libraries."
- **Watermelon UI** (ui.watermelon.sh, `WatermelonCorp/watermelon-platform`) — an **open-source React 19 UI platform**: animated components, copy-paste blocks, dashboards, and templates built on **Tailwind CSS 4 + Motion + Vite**. Ships a zero-lock-in shadcn registry (`npx shadcn@latest add https://registry.watermelon.sh/r/<name>.json`) and a hosted MCP server (`mcp.watermelon.sh`), installed via `npx @watermelon-ui/cli init --client claude`. Machine-readable endpoints (`/llms.txt`, `/openapi.json`, `/api/catalog`) make it especially agent-friendly. Free/community.
- **Motion Primitives** (motion-primitives.com, `ibelick/motion-primitives`) — an **open-source (MIT) UI kit of reusable animated React components** built with **Motion (formerly Framer Motion) + Tailwind CSS**, by Julien Thibeaut (ibelick). Positioned as "shadcn/ui, but for animated components" — subtler and more production-appropriate than the more cinematic Aceternity style. A paid "Motion-Primitives Pro" tier adds more blocks/templates; also published on 21st.dev (34 components).

## 6.1 shadcn-style animated component libraries (copy-paste / registry-installable — the sweet spot for Claude)

**Why this matters for AI coding:** shadcn/ui is now a *distribution mechanism*, not just a library. Any project can publish a `registry.json`, and `npx shadcn add <url>` fetches source directly into your repo — the ideal architecture for Claude, because it can read and modify the actual files. The shadcn MCP server (Part 3.3) works with *any* shadcn-compatible registry out of the box.

- **shadcn/ui** (ui.shadcn.com) — the de facto standard: accessible components (now defaulting to Base UI, also Radix/React Aria) + Tailwind, copied into your codebase. MIT. Official MCP server.
- **Magic UI** (magicui.design) — 150+ free animated components/effects for landing pages (marquees, bento grids, beams, shimmer buttons). React/TS/Tailwind v4/Motion. MIT + paid Magic UI Pro. shadcn CLI + official MCP server.
- **Aceternity UI** (ui.aceternity.com) — ~266 bold, cinematic animated components (aurora backgrounds, 3D cards, sparkles, lamp effect). React/Next/Tailwind/Motion (some three.js). Freemium (Aceternity UI Pro). shadcn CLI + MCP server.
- **Watermelon UI** — see 6.0. shadcn registry + MCP.
- **Motion Primitives** — see 6.0. Copy-paste; also on 21st.dev.
- **coss ui** (formerly Origin UI, coss.com/origin) — hundreds of copy-paste application-UI components. React/Tailwind v4, now built on Base UI. Mixed AGPLv3/MIT. shadcn CLI.
- **Cult UI** (cult-ui.com) — curated shadcn-compatible, tastefully animated interaction components (dynamic island, family drawer, 3D carousel) + 100+ AI SDK agent patterns. Free core + Cult Pro. shadcn CLI + MCP server.
- **Kokonut UI** (kokonutui.com) — 100+ animated components strong on AI input surfaces, buttons, backgrounds. MIT + Kokonut UI Pro. shadcn CLI; works via shadcn MCP.
- **React Bits** (reactbits.dev) — 200+ animated/interactive components (text effects, WebGL backgrounds). JS/TS + CSS or Tailwind, uses GSAP + ogl. Free + React Bits Pro. jsrepo CLI and shadcn registry protocol.
- **Animata** (animata.design) — 156+ free hand-crafted, theme-aware animated components. MIT. shadcn-registry style.
- **Skiper UI** (skiper-ui.com) — animation-focused components built on shadcn/ui. Freemium. shadcn CLI + MCP server.
- **Eldora UI** (eldoraui.site) — 150+ free animated components/blocks/templates. MIT. shadcn-compatible + MCP server.
- **Syntax UI** (syntaxui.com) — free prebuilt React elements. Freemium. Copy-paste (shadcn CLI/MCP support unverified).
- **Luxe** (luxeui.com, `guhrodrrigues/luxe`) — elegant copy-paste components with variant props. MIT. Uses its **own** CLI (`npx luxe add`), not shadcn.
- **Hover.dev** — prebuilt animated components/templates. Freemium. Copy-paste only.
- **Uiverse** (uiverse.io) — 4,000+ community-made free UI elements. Plain CSS or Tailwind (HTML/CSS, not React components). Copy-paste.
- **SmoothUI, 8bitcn (retro/pixel), Neobrutalism Components, assistant-ui (AI chat surfaces), Velora UI, Tailark, Spectrum UI** — additional notable shadcn-ecosystem registries, most MIT and CLI-installable.

## 6.2 Full UI frameworks / design systems (installed dependencies)

- **HeroUI** (heroui.com, formerly NextUI; now `@heroui/react`) — accessible React library built on React Aria + Tailwind v4 + Motion. Free (v3 Apache-2.0) + HeroUI Pro. Has an official MCP server + agent skills/llms.txt.
- **Mantine** — 100+ components + 50+ hooks. Free/MIT.
- **Chakra UI** — v3 rewrote onto Panda CSS + Ark UI. Free/MIT.
- **MUI (Material UI)** — batteries-included, huge catalog. Free core + paid X/Pro.
- **Ant Design** — dominant B2B/enterprise catalog. Free/MIT.
- **Park UI** (park-ui.com) — framework-agnostic (React/Solid/Vue) on Ark UI + Panda CSS (not Tailwind), by the Chakra team. MIT.
- **Radix UI / Base UI / React Aria / Ark UI** — headless, accessible primitives for building your own design system; shadcn/ui is built on these.
- **DaisyUI** — a Tailwind *plugin* adding semantic classes plus 35+ themes, zero JS. Free/MIT.
- **HyperUI, Preline, Flowbite** — Tailwind component/marketing libraries (free + paid tiers).
- **Untitled UI React** — large React + React Aria component/Figma system. Paid.

## 6.3 Component marketplaces, registries & MCP servers

- **21st.dev** — YC-backed React component marketplace on shadcn+Tailwind. Its **21st MCP** (formerly Magic MCP) lets Claude search the catalog and write components in place. Install: `claude plugin marketplace add 21st-dev/magic-mcp` then `/plugin install 21st`.
- **Official shadcn MCP server** — works with any shadcn-compatible registry (Part 3.3).
- **shadcn.io** — AI-native aggregator: 6,000+ shadcn blocks + 285k+ React icons across 222 libraries, one shadcn CLI command, 15-tool MCP.
- **shadcn Studio** (shadcnstudio.com) — components/blocks/templates + a live theme generator + MCP server + "copy prompt to v0/Bolt/Lovable."
- **shadcnblocks / Shadcnspace (WrapPixel)** — large block/template marketplaces (Shadcnspace: 371+ blocks, MCP server + Figma kit).
- **registry.directory + registry-directory-mcp** (`Microck/registry-directory-mcp`) — an MCP server indexing 40+ shadcn registries with 150+ pre-indexed premium components — a single discovery point.
- **How to use any of these with Claude (in order of preference):** (1) add the library's MCP server so Claude can search+install; (2) give Claude the registry URL and let it run `npx shadcn add <url>`; (3) use Context7 or paste `llms.txt`; (4) copy-paste the component source.

## 6.4 AI UI generators (complementary to Claude)

- **v0 by Vercel** (v0.dev) — generates full React/Next + shadcn/Tailwind pages from prompts in-browser; export or `npx shadcn add` the generation.
- **Lovable** (lovable.dev) — full-app generation with Supabase/Stripe wiring; popular for first-pass UI then refine in Claude/Cursor.
- **Bolt.new** (StackBlitz) — in-browser full-stack app generation and deploy.
- **21st.dev Magic** — library-backed generation *inside* your editor — the closest fit to Claude Code workflows.
- **Typical pattern:** PRD in Claude → first UI in Lovable/v0 → refine in Claude Code/Cursor → components from shadcn Studio → styling via tweakcn → deploy on Vercel.

## 6.5 Theme / token tools

- **tweakcn** (tweakcn.com) — open-source visual theme editor/generator for shadcn/ui tokens (color, typography, radius); export CSS variables. The fastest way to escape the default-shadcn look.
- **shadcn Studio theme generator** — visual token editor with icon-library selection, Figma import/export.

## 6.6 Icon libraries

Lucide (lucide.dev, the shadcn default) · Phosphor Icons · Tabler Icons (4,000+, used in Aceternity) · Heroicons (by the Tailwind team) · Hugeicons · Remix Icon · Iconify (200k+ icons across libraries via one API) · shadcn.io/icons (285k+ across 222 libraries, shadcn CLI/MCP installable).

## 6.7 Animation libraries

- **Motion** (formerly Framer Motion; motion.dev) — best overall for React UI: declarative, layout animations, gestures, exit animations. Import from `motion/react`.
- **GSAP** — best for complex timelines, scroll-triggered choreography, SVG morphing. **Now 100% free to all users**, including previously paid Club plugins (SplitText, MorphSVG, DrawSVG, ScrollTrigger, ScrollSmoother), per Webflow's official Apr 30, 2026 announcement (Webflow acquired GreenSock Oct 15, 2024). Pair with **Lenis** for smooth scroll.
- **React Spring** — physics/spring-based React animation (pmndrs ecosystem).
- **Lottie / dotLottie** — plays designer-authored vector animations (After Effects → JSON); dotLottie up to ~80% smaller.
- **Rive** (rive.app) — interactive motion graphics with real state machines.
- **AutoAnimate** (FormKit) — one-line automatic list/DOM transitions, tiny footprint.
- Native CSS/WAAPI, `@starting-style`, scroll-driven animations, and View Transitions cover many cases library-free — always respect `prefers-reduced-motion`.

## 6.8 Design inspiration & reference sites

- **Mobbin** — largest library of real mobile/web product flows. Free tier + Pro (~$25/mo).
- **Refero** — real web/SaaS UI by page type/component; a styles beta outputs a `design.md` for AI agents (pair with a screenshot — markdown gives structure, screenshot gives visual evidence).
- **Godly** (godly.website) — curated editorial/typographic inspiration.
- **Land-book, Lapa Ninja, One Page Love** — landing-page galleries.
- **SaaSFrame, Saaspo, SaaSUI** — SaaS marketing pages/app screens by screen type.
- **Awwwards, SiteInspire** — award-winning site galleries.
- **Page Flows, Screensdesign** — recorded user journeys / shipped app screens.
- **Typewolf, Fonts in Use** (typography) · **Brand New** (branding) · **Coolors** (palettes).
- **How to use with Claude:** screenshots beat text. Provide a reference screenshot (or a Refero `design.md` + screenshot), name a concrete aesthetic direction, then iterate visually via the Playwright loop below.

## 6.9 Getting non-generic, polished UI out of Claude

- **Use the official `frontend-design` skill** (Part 2.1/2.2). Anthropic's own framing: *"You tend to converge toward generic, 'on distribution' outputs. In frontend design, this creates what users call the 'AI slop' aesthetic. Avoid this... Avoid generic fonts like Arial and Inter; opt instead for distinctive choices."* It has Claude commit to a bold, named aesthetic direction (brutalist, editorial, luxury, retro-futuristic, etc.) *before* coding.
- **`avoid-ai-design`** (Part 2.2) — the de-slop counterpart; use frontend-design to write, avoid-ai-design to fix.
- **Provide references, not just words** — screenshots, a design system, brand tokens, or a `design.md`. Text-only prompts yield generic output.
- **Set the design system up front** in CLAUDE.md ("UI components: always use shadcn/ui; theme = <tokens>").
- **The Playwright screenshot loop (visual self-correction):** add the Playwright MCP server (Part 3.2); have Claude boot the dev server, navigate the route, screenshot at target breakpoints, and diff against a reference (a Figma frame via Figma MCP, or a saved "golden image"). Make verification mandatory in CLAUDE.md — this is the single highest-leverage habit for visual fidelity.
- **Figma-to-code pipeline:** Figma MCP (real tokens, not pixels) → map to a token-driven design system → implement → Playwright screenshot diff.
- **Claude Artifacts / Claude Design** — for quick standalone UI generation and preview outside the codebase.
- **tweakcn / shadcn Studio themes** — generate a cohesive token set first so the whole app looks intentional rather than default-shadcn.

***
# Part 7 — Claude Code: The Complete Reference

Claude Code is Anthropic's agentic coding tool (terminal, desktop app, IDE, web). It is a programmable platform built from six layers — **Memory, Slash commands, Subagents, Skills, Hooks, MCP** — packaged and shared via **Plugins**. Anthropic describes it as "intentionally low-level and unopinionated, providing close to raw model access without forcing specific workflows."

## 7.1 Installation & surfaces

**Verified install commands:**
```bash
# macOS / Linux / WSL (native installer)
curl -fsSL https://claude.ai/install.sh | bash
# Windows PowerShell
irm https://claude.ai/install.ps1 | iex
# Homebrew
brew install --cask claude-code
```
npm (`npm install -g @anthropic-ai/claude-code`) is **deprecated** (since v2.1.15, Jan 21, 2026, per secondary sources) — migrate existing installs with `claude install`.

```bash
claude --version   # need ≥2.1.280 for Opus 5.5 as the default Opus
claude update
cd your-project && claude   # sign in with your Claude account (or ANTHROPIC_API_KEY)
/init                        # generates CLAUDE.md — then trim it
```

**Surfaces:** terminal CLI · VS Code / JetBrains / Cursor IDE integrations (Part 5.2) · Claude Code desktop app · Claude Code on the web (runs in isolated cloud VMs) · mobile/Remote Control · GitHub Actions / `@claude` tagging.

## 7.2 Memory: the CLAUDE.md hierarchy

**Hierarchy:** enterprise/managed → **user** (`~/.claude/CLAUDE.md`) → **project** (`./CLAUDE.md`, committed) → **local** (`./CLAUDE.local.md`, gitignored). All in scope are concatenated. Reference other files with `@path/to/file` imports.

**Best practice:** keep it **concise and high-signal** — Anthropic's own guidance: "aim to keep CLAUDE.md under 200 lines." Larger files waste attention on low-value instructions; move procedures into **skills** instead, and convert enforceable rules into **hooks**. Edits apply only on next restart or `/compact`.

There is **no officially documented `.claudeignore`** — use `permissions.deny` Read rules in settings.json instead (Part 7.7).

## 7.3 Slash commands

**Built-in (representative):** `/init`, `/clear`, `/compact`, `/model`, `/context`, `/cost`, `/usage`, `/review`, `/security-review`, `/resume`, `/continue`, `/rename`, `/agents`, `/plugin`, `/mcp`, `/doctor`, `/effort`, `/rewind`, `/insights`, plus bundled skill commands like `/code-review`, `/verify`, `/run`.

**Custom commands:** Markdown files in `.claude/commands/` (project) or `~/.claude/commands/` (user) become `/your-command`. In 2026, custom commands increasingly overlap in purpose with Skills — use a slash command for a prompt template, a skill for domain logic/helper files.

## 7.4 Subagents

Defined as Markdown files in `.claude/agents/` (project) or `~/.claude/agents/` (user), each with its own context window, tools, and optionally its own model. Create interactively with `/agents` → Library → create → scope → "Generate with Claude."

**Use for:** isolated/parallel work and **context isolation** — e.g., a read-only "Explore" agent to map a repo, or a research agent that reads verbose logs and returns only a clean summary (a major token saver — keeps noise out of your main thread). Subagents can run in the **background**. Subagents **inherit** the session's model unless you set one explicitly (`model: haiku` or `model: sonnet` in the agent file) — a switch to Opus mid-session cascades to every subagent too.

Collections: `wshobson/agents`, `VoltAgent/awesome-claude-code-subagents` (Part 4.3).

## 7.5 Hooks

Deterministic scripts (or HTTP/MCP/prompt/subagent triggers) firing at lifecycle events — they **execute code, so they can't hallucinate**, making them the right place for *enforceable* rules.

**Key events:** `UserPromptSubmit`, `PreToolUse` (primary security checkpoint — block dangerous commands/writes), `PostToolUse` (auto-format/lint/typecheck after edits, or filter noisy output), `PermissionRequest` (auto-approve/deny), `Stop`/`SubagentStop` (run tests when done), plus notification hooks.

**Verified official config format:**
```json
{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"..."}]}]}}
```
A hook can return JSON like `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","updatedInput":{...}}}` to rewrite a tool call in flight — this is the mechanism used to filter noisy test/build output before it enters context (see the worked example in Part 10.2, method C6). Exit-code-2 semantics were referenced but not re-verified in full this pass.

**Common recipes:** run Prettier after every edit; block `rm -rf` or writes outside the repo; redact secrets in every shell command; run the test suite on Stop; desktop notification when input is needed; truncate huge test-runner/build-log output before it enters context.

## 7.6 Skills, output styles, statusline

**Skills** in Claude Code = a folder + `SKILL.md`, loaded on demand when the description matches; can run in-context or in a subagent. **Decision rule:** slash command = prompt template; skill = domain logic/helper files; subagent = isolated/parallel work; hook = enforce a rule with code; CLAUDE.md = short always-on guidance.

**Output styles** change how Claude communicates — e.g., Explanatory/Learning styles leave `TODO(human)` tasks for you to complete rather than solving everything; a terse/"caveman" style measurably reduces prose length (Part 2.12).

**Statusline:** customize via `statusLine` in settings.json; `sirmalloc/ccstatusline` gives a powerline-style, themeable statusline showing model, context %, and cost.

## 7.7 Plugins & marketplaces

A **plugin** is a versioned bundle of skills + subagents + slash commands + hooks + output styles + MCP definitions, installed as one unit via `/plugin`. Add a marketplace: `claude plugin marketplace add <owner/repo>`, then `/plugin install <name>`. Official: `anthropics/claude-plugins-official`, added automatically on first interactive launch. Community hubs: claudemarketplaces.com, aitmpl.com, claudepluginhub.com (which offers a "safe" feed excluding code-execution hooks).

## 7.8 Settings, permissions, sandboxing, safety

`settings.json` (user/project/local) holds permissions, allowlists, `defaultMode`, hooks, statusline, model, MCP config.

**Permission modes (verified):** `default` (shown as "Manual" in the UI; `manual` is accepted as an alias), `acceptEdits`, `plan`, `dontAsk`, `bypassPermissions`, `auto`.

🔧 **Correction:** on **Pro, Max, and Team plans, the built-in starting permission mode is now `auto`** — this became the default across those plans on August 14, 2026. Enterprise and API/cloud deployments remain opt-in for auto mode. If you want the older manual-approval flow, set `"permissions": {"defaultMode": "default"}` explicitly.

**Sandboxes** exist for isolated execution. `--allowedTools` scopes permissions for batch/headless runs.

**Deny-rule example** (replacing the non-existent `.claudeignore`):
```json
{"permissions":{"deny":["Read(./.env*)","Read(./secrets/**)","Bash(rm -rf:*)","Bash(git push --force:*)"]}}
```
Note this is *advisory*: Claude Code already truncates oversized tool results by default, so the main win from deny rules is avoiding *repeated* partial reads, not a hard block on all access.

## 7.9 Model selection, thinking/effort, and 2026 defaults

**Current defaults (verified, corrects the earlier "Opus 5 is default" claim):** as of Claude Code v2.1.280, the `opus` alias resolves to **Opus 5.5**, and **Pro and Team Standard plans now default to Opus** (previously Sonnet), matching Max/Team Premium/Enterprise which already defaulted to Opus. Confirm your session's actual model with `/model`.

**Adaptive thinking:** Opus 5.5 and Fable models cannot have thinking fully disabled — it's controlled via **effort level** (`/effort low|medium|high|xhigh`), not a token budget. Default effort is **medium**. `MAX_THINKING_TOKENS` only affects fixed-budget (non-adaptive) models — it's ignored by Opus 5.5.

**`opusplan`** (Opus for planning, Sonnet for execution) — ⚠ as of Sep 4, 2026 (v2.1.260), there is an **open, unresolved bug** (github.com/anthropics/claude-code/issues/92007) where `/model opusplan` returns "Unsupported model" in the Windows desktop app's Code tab. `opusplan[1m]` requires v2.1.265+.

## 7.10 Productivity features

- **Checkpoints / `/rewind`** — revert if Claude goes off track; press Escape twice or run `/rewind`.
- **Background tasks / background bash**, **git worktrees** for parallel sessions, **plan mode** (Shift+Tab — separates exploration/planning from editing, preventing wasted tokens on wrong paths), **image/screenshot input**, **Vim mode**, **`/resume` & `/continue`**.
- **Headless mode (`claude -p`)** — one-shot, non-TTY; powers GitHub Actions, scheduled jobs, pre-commit hooks, batch loops (`for task in ...: claude -p ...`). Supports `--output-format json` and, per the official cost docs, a `--max-budget-usd` cap that includes any data-residency price multiplier.
- **Claude Agent SDK** (Python/TypeScript) — build custom agents on the same harness.
- **Cloud/Agent features (2026):** run sessions on Anthropic-managed infra; **Agent view** (research preview — dispatch background sessions, watch from one screen, confirmed to exist in the docs); **Agent teams** (experimental, off by default via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — confirmed to exist, but **use "approximately 7x more tokens than standard sessions when teammates run in plan mode,"** so keep teams small, use Sonnet teammates, and shut them down promptly). Cross-session messaging. **Claude Cowork** is a GUI sibling for non-technical knowledge work, included from Pro.
- **AutoDream / `/dream`** — ❓ **partially verified.** GitHub issue #38493 confirms a flag-gated auto-dream mechanism exists in the codebase; community write-ups describe a `/memory` toggle and a trigger after ~24h/5 sessions, but it does not appear in the official Claude Code docs pages reviewed. Distinct from the confirmed, officially-announced **"Dreaming"** feature of **Claude Managed Agents** (a research preview on the Claude Platform, announced May 6, 2026 at Code with Claude): it takes 1–100 prior sessions plus an existing memory store and outputs a *separate, curated* memory store (duplicates merged, stale entries replaced) without touching the original — access by request.

## 7.11 MCP configuration in Claude Code

`claude mcp add <name> -- <command>` or `--transport http <url>`; scopes: **local**, **project** (`.mcp.json`, committed), **user**. Debug with `/mcp`. Cap verbose server descriptions with `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` (2,048-char default, added v2.1.280). MCP output is capped at `MAX_MCP_OUTPUT_TOKENS` (25,000 default, warning at 10,000). Tool definitions are **deferred by default** — only names/instructions load until a tool is actually invoked. Audit your MCP loadout with `/context`; every loaded tool's schema consumes tokens even unused.

## 7.12 Official Anthropic guidance (source documents)

- **"Claude Code: Best practices for agentic coding"** (anthropic.com/engineering/claude-code-best-practices) — foundational post.
- **Official docs:** code.claude.com/docs (best-practices, features-overview, costs, common workflows) and docs.claude.com.
- **"Manage costs effectively"** (code.claude.com/docs/en/costs) — the single richest source for cost guidance; extensively cited throughout Part 10.
- **"How Claude Code works in large codebases"** and **"How Anthropic engineering teams use Claude Code"** — internal teams use auto-accept mode for peripheral features from a clean git state, reviewing the ~80%-complete result; Security Engineering cut infra-debugging time from 10–15 minutes to 5 by feeding stack traces directly in. The pattern works best on a product's edges, not core business logic.
- **"Improving frontend design through Skills"** (claude.com/blog) — origin of the frontend-design skill and the "AI slop" framing.
- **"Optimizing for cost and intelligence"** (platform.claude.com/docs) — the primary source for API-level cost guidance (Part 10.1).

## 7.13 Community frameworks & methodologies

- **Superpowers** (`obra/superpowers`, Part 2.3/4.3) — TDD-first "Iron Laws" methodology.
- **BMAD-METHOD** (Part 2.6/4.3) — role-agent, artifact-driven method; best for regulated/traceability-heavy work, overkill for bug fixes.
- **GitHub Spec Kit** (Part 2.6) — lightweight spec toolkit; best for formalizing requirements without process overhaul.
- **OpenSpec** — "delta specs" for brownfield repos (specify only what changes).
- **SuperClaude** (Part 4.3) — config framework adding commands/personas/methodologies.
- **claude-flow** (ruvnet, Part 4.3) — multi-agent orchestration/swarm framework.
- **ccpm** (~8k reported) — project management via GitHub Issues + git worktrees for parallel agents.
- **Task Master AI** (Part 2.6) — task breakdown/management for agents.
- **claude-code-router** — routes Claude Code requests to different/cheaper model backends.
- **openskills** (~10k reported) — universal skills loader; **context-mode/claude-context-mode** — an MCP server claiming to sandbox tool output (see the caution in Part 3.11); **Graft** (~8k reported) — codebase-aware context/code-graph tool.
- **Spec-kitty** — Spec Kit + per-package git worktrees + local kanban with human-gated merge.

## 7.14 Parallel-agent orchestrators & UIs

- **Conductor** — macOS app; each agent gets an isolated git worktree + diff/PR flow (Claude Code + Codex).
- **Vibe Kanban** (`BloopAI/vibe-kanban`) — cross-platform kanban for running agents in parallel worktrees with visual diff review; supports Claude Code/Codex/Gemini/Amp. ⚠ **Parent company shut down Apr 10, 2026** — continues as Apache-2.0 community OSS, transitioning to a fully-local architecture (remote/collaborative features being removed). Evaluate as a local tool, not a supported SaaS product.
- **Crystal** — Electron app for parallel Claude Code sessions in worktrees.
- **Claude Squad, Nimbalyst, Paneflow, VibeTree, Dmux** — additional multi-agent/worktree managers (terminal or GUI).
- **Happy** — mobile/remote client for Claude Code; **claudecodeui** — web/mobile UI.
- **opcode / Claudia** (Part 4.4) — GUI command center.
- **claude-code-templates / aitmpl.com** (Part 4.4) — 1000+ agents/commands/skills/MCP configs, plus a usage dashboard.

## 7.15 Power-user workflows

- **Explore → Plan → Code → Commit:** use Plan mode to separate exploration/planning from implementation.
- **TDD with Claude:** one agent writes tests, another writes code to pass them; pass expected outputs for self-verification.
- **Writer/Reviewer pattern:** a fresh-context agent reviews code it didn't write (less bias).
- **Multi-agent parallelism:** git worktrees + an orchestrator (Conductor/Vibe Kanban); label GitHub issues and assign each to an agent; compare implementations side by side.
- **Spec-driven development:** Spec Kit/BMAD to turn vague prompts into reviewable specs that persist across sessions.
- **Screenshot-driven UI iteration:** the Playwright loop (Part 6.9).
- **Non-coding uses (research/learning/writing):** Explore/research subagents that read many sources and return summaries; Claude Code as a repo-aware research assistant; Claude Cowork for non-technical writing/planning; the Anthropic Prompt Library and Console Workbench prompt improver for better prompting generally.

***
# Part 8 — Anything Else Claude Can Be Used For / Maximized

## 8.1 Plan comparison (claude.com/pricing, verified September 2026)

| Plan | Price | Key access |
|---|---|---|
| Free | $0 | Chat on web/desktop/mobile with tight limits. **No Claude Code.** |
| Pro | $20/mo (or $17/mo billed annually, $200/yr) | Opus 5.5 (now the default), Claude Code, Cowork, Projects, Research, M365 add-ins. Fable only via usage credits. |
| Max 5x / 20x | $100 / $200 per month | 5x or 20x Pro's usage. Fable **included** in the subscription (reported at 50% of weekly limits). |
| Team | Standard: $20/seat annual ($25 monthly); Premium: $100 annual ($125 monthly); 2–150 seats | Standard gets "more than Pro" usage; Premium gets "5x more than Standard" (pricing page's own wording — secondary sources quote 1.25× Pro and 6.25× Pro respectively). Admin controls. |
| Enterprise | ~$20/seat (annual) + usage billed at API rates (secondary-sourced) | SSO, SCIM, audit logs, Compliance API, self-serve HIPAA configuration. |

All paid-plan usage is metered by a **rolling five-hour window plus a weekly cap**, shared across chat and Claude Code. Limits rose 20% from September 22, 2026 (alongside the Opus 5.5 launch), plus a **one-time banked rate-limit reset** you can save and spend later on a high-demand day.

## 8.2 Feature checklist

- **Projects** — persistent instructions plus files per workstream; the more you reuse the same project content, the more benefit from caching.
- **Memory** — chat memory plus search across past chats. Keep on for learning/research continuity; use incognito for one-off chats.
- **Research / web search** — multi-step cited research; Opus 5.5's citation fidelity is the best it has been (Part 2.4).
- **Artifacts & published apps** — interactive React/HTML artifacts, including AI-powered artifacts that call Claude and bill the viewer's own usage.
- **Claude Docs / Claude Slides** — ✅ **confirmed launched in beta on September 16, 2026**, alongside merging Cowork into the main Claude interface. Rollout reaches Pro and Max first (web/desktop/mobile), with Team and Free following "in the coming weeks"; Enterprise admins control timing. Docs export to Word/Google Docs; Slides export to PowerPoint/PDF.
- **Claude Design, Claude Cowork, Claude Science, Claude Security** — all official products. Cowork is the desktop agent for knowledge work, included from Pro. Claude Security includes Mythos 5.1 access for security teams.
- **Claude Code on web, desktop, mobile**, background sessions (Agent view), agent teams, Remote Control, scheduled/background work.
- **File creation** — docx, pptx, xlsx, pdf via the document skills (Part 2.7).
- **Styles & preferences** — put writing rules here; Opus 5.5 follows them more reliably than earlier models.
- **Voice mode** — on the mobile apps.
- **Education / Learning mode** — institution-wide Education plans; Learning-style responses in claude.ai; Learning/Explanatory output styles in Claude Code.
- **Financial Services / Life Sciences** — industry solutions; the Life Sciences Verification Program specifically unlocks fuller biology capability on Opus 5.5 (Part 3.7).
- **Developer platform (platform.claude.com):** Workbench and prompt improver · Batch API (−50%) · prompt caching · Files API · Citations · structured outputs · code execution · Managed Agents including Dreams (research preview, Part 7.10) · US-only inference at 1.1× price.

## 8.3 High-value and unexpected use cases

- **Coding:** overnight unattended migrations and audits. Anthropic's Opus 5.5 launch post quotes Clio staff developer Sean Heintz: Opus 5.5 "stayed on task for over 18 hours"; a tester's 200,000-line audit finished in "under three hours, where Opus 5 took over 20 hours and used 2.5x as many tokens." Performance passes: "cut load times" succeeded 39/40 times.
- **Research:** "earnings-style" reports where every figure must carry a source (pair with the citation-fidelity note in Part 2.4).
- **Learning:** ask for a Learning-style session that leaves exercises for you, then a spaced-repetition artifact.
- **Writing:** a Style built from your own best samples plus a "banned phrases" rule list.

***
# Part 9 — Caveats Resolved (Full Verification Table)

*This section documents the verification pass done against the original research, so the corrected facts above can be traced back to what was fixed and why. If a fact appears differently earlier in this document than in this table, the version earlier in the document (which reflects this verification pass) is the current, corrected one.*

| # | Original claim | Status | Verified fact | Source |
|---|---|---|---|---|
| 1 | Pro / Team Standard default model in Claude Code | ✅ Confirmed corrected | v2.1.280 "Changed the default model on Pro and Team Standard plans from Sonnet to Opus, matching Max, Team Premium, and Enterprise." Opus 5.5 is now the default Opus. An effort level saved before `/effort` became per-model does not carry over to Opus 5.5. | Claude Code CHANGELOG |
| 2a | Fable 5.1 cache read price | ✅ Confirmed | $0.25/MTok (0.025× base input; Fable 5/Mythos 5 remain at $1/MTok). Fable 5.1 full pricing: $10 in / $50 out, $12.50 5-min write, $20 1-hour write. | platform.claude.com pricing table |
| 2b | Opus 5.5 1-hour cache write | ✅ Confirmed | $8/MTok (2× input). 5-min write $5, read $0.20 (0.05×, half the usual 10%). | Same |
| 3 | Team seat multipliers/pricing | ✅ Confirmed with nuance | Pricing page: "Standard seats give more than Pro and Premium seats give 5x more than Standard." Secondary sources quoting the help center: Standard = 1.25× Pro, Premium = 6.25× Pro (consistent with the above). Standard $20/seat/mo annual ($25 monthly); Premium $100 annual ($125 monthly); 2–150 seats. Enterprise reported (secondary) as $20/seat + API-rate usage. | claude.com/pricing; secondary sources |
| 4 | Claude Docs/Slides beta ~Sep 16 | ✅ Confirmed with nuance | Announced Sep 16, 2026, alongside merging Cowork into the main interface. Reaches Pro/Max first; Team/Free follow "in the coming weeks"; Enterprise admin-controlled. | TechCrunch, VentureBeat, The Next Web, tbreak (Sep 16–17) |
| 5 | Sonnet 5 tokenizer ~30% more tokens | ✅ Confirmed official | Anthropic's own docs: "the new tokenizer produces approximately 30% more tokens for the same text" (range ~1.0–1.35×). Same tokenizer introduced with Opus 4.7; Simon Willison independently measured Opus 4.7's system prompt at 1.46× Opus 4.6's token count via the count_tokens API, while a 30-page PDF came out at only 1.08×. | platform.claude.com; simonwillison.net |
| 5b | Does Opus 5.5 share this tokenizer? | ❓ Still unverified officially | Very likely (per one secondary source verifying against real bills for Opus 5 and Fable 5.1), but no official statement confirms it for Opus 5.5 specifically. | playcode.io (secondary) |
| 6 | GitHub star counts across listed repos | ❓ Still unverified | Not systematically re-checked. One confirmed datapoint: anthropics/claude-code shows ~145k★/23.1k forks (community-reported, re-verify before citing). | — |
| 7 | MCP install commands | 🔧 Partially resolved | 11 of the requested servers verified from vendor docs (Part 3). AWS, Docker, Kubernetes, GitLab, Prisma, Brave, Tavily, Perplexity, 21st.dev Magic, Magic UI, arXiv/Semantic Scholar/PubMed, and Obsidian servers were **not** verified. | Vendor docs (Part 3) |
| 8a | Official JetBrains plugin | ✅ Confirmed, stale | "Claude Code [Beta]" by Anthropic PBC, JetBrains Marketplace plugin 27310. Latest version 0.1.14-beta, dated Dec 5, 2025 — no update in ~10 months. ~2.3–2.4★ from ~467 reviews, ~4.74M downloads. Requires the CLI installed separately. | plugins.jetbrains.com; code.claude.com/docs/en/jetbrains |
| 8b | Raycast/Alfred extensions; Microsoft Teams app | ❓ Still unverified | Not verified. | — |
| 9a | AutoDream / `/dream` in Claude Code | ❓ Partially verified | Official GitHub issue #38493 confirms a flag-gated auto-dream mechanism exists. Third-party write-ups describe a `/memory` toggle, a ~24h/5-session trigger, and occasional "Unknown skill" errors from `/dream`. Not documented on official docs pages reviewed — treat as an unannounced, possibly flag-gated feature. | GitHub issue #38493; community write-ups |
| 9b | Anthropic "Dreams" (Managed Agents) | ✅ Confirmed | Research-preview feature of Claude Managed Agents, announced May 6, 2026 at Code with Claude. Takes an existing memory store plus 1–100 prior sessions, outputs a *separate* curated memory store (duplicates merged, stale entries replaced); the input store is untouched. Access by request. | claude.com/blog; The New Stack; VentureBeat |
| 10 | Independent measurements of token-saving tools | ✅ Resolved | The JetBrains series covers caveman, rtk, and ponytail (full results in Part 2.12/11). No independent benchmark was found for context-mode; its 96% figure is self-reported. | blog.jetbrains.com/ai |
| 11a | Install commands | ✅ Confirmed | See Part 7.1 for exact commands. npm deprecated since v2.1.15 (Jan 21, 2026, per secondary sources); Node version requirements for npm conflict across sources (18+ vs 22+). | support.claude.com; secondary sources |
| 11b | `permissions.defaultMode` values | 🔧 Corrected | Valid values: `default` ("Manual" in UI; `manual` accepted as alias), `acceptEdits`, `plan`, `dontAsk`, `bypassPermissions`, `auto`. **On Pro/Max/Team, the built-in starting mode is `auto`.** | code.claude.com/docs/en/permission-modes |
| 11c | Hooks syntax | ✅ Partially confirmed | Verified example format and JSON-output rewrite mechanism (Part 7.5). Exit-code-2 semantics referenced but not fully re-verified. | code.claude.com/docs/en/costs |
| 11d | `.claudeignore` | ❓ Unverified — treat as unsupported | No official documentation found. Use `permissions.deny` Read rules instead. | — |
| 11e | Auto-compaction threshold on 1M models | 🔧 Partially confirmed | Compaction triggers at a configurable "auto-compact window" (`/autocompact`); a community reference documents an override pattern (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`) that can treat a 1M model as, e.g., 500K for compaction purposes. Exact default percentage not verified. | code.claude.com/docs/en/costs; secondary |
| 11f | `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH`, tool search | ✅ Confirmed | Added in v2.1.280; changes the 2,048-char cap on MCP tool descriptions/server instructions for every server in the session. MCP tool definitions deferred by default. MCP output warns at 10,000 tokens, capped at 25,000 by default (`MAX_MCP_OUTPUT_TOKENS`). | CHANGELOG; code.claude.com/docs/en/costs and /mcp |
| 12a | `.mcpb` Desktop Extensions directory; Claude in Chrome eligibility | ❓ Still unverified | Not verified. | — |
| 12b | `opusplan` issue #92007 | ✅ Confirmed open | Opened Sep 4, 2026 (v2.1.260, Windows desktop app Code tab): `/model opusplan` returns "Unsupported model." Still open as checked. Model-config docs still document `opusplan` and `opusplan[1m]` (the latter requires v2.1.265+ via `/model`). | github.com/anthropics/claude-code/issues/92007; model-config docs |
| 13 | Sonnet 5.5 / Haiku 5.5 released? | ✅ Confirmed: not yet | Launch post: "will follow in the coming weeks." Official pricing table lists neither as of Sep 25, 2026. Haiku 4.5 remains current Haiku. | TechCrunch (Sep 22); platform.claude.com pricing |

**Additional Opus 5.5 launch facts folded into the corrected sections above:** fast mode ($8/$40, up to 2.5× speed, research preview, first-party API only, not available with Batch); US-only inference adds 1.1×; output limits 128k standard / 300k on Batch (beta header); subscription five-hour limits rose 20% from Sep 22 plus a one-time banked reset.

***
# Part 10 — Token & Cost-Saving Playbook (Consolidated + Advanced)

Evidence levels used throughout: **Official-measured** (Anthropic published numbers) > **Official** (documented guidance, no numbers) > **Independent** (third-party controlled test) > **Anecdotal/vendor** (self-reported).

## 10.0 Pricing reference (per million tokens, September 2026)

| Model | Input | Output | 5-min cache write (1.25×) | 1-hour cache write | Cache read | Batch (−50%, input/output) |
|---|---|---|---|---|---|---|
| Opus 5.5 | $4 | $20 | $5 | $8 (2×) | **$0.20 (0.05×)** | $2 / $10 |
| Fable 5.1 | $10 | $50 | $12.50 | $20 | $0.25 | $5 / $25 |
| Opus 5 | $5 | $25 | $6.25 | $10 | $0.50 | $2.50 / $12.50 |
| Sonnet 5 | $2 | $10 | $2.50 | $4 | $0.20 | $1 / $5 |
| Haiku 4.5 | $1 | $5 | $1.25 | $2 | $0.10 | $0.50 / $2.50 |

Batch figures are derived from the documented 50% discount, applied to input and output separately, and stack with cache multipliers.

## 10.1 API / developer platform

**A1. Turn on caching first.** A single top-level `cache_control` caches everything up to the last cacheable block, moving forward as the conversation grows.
```python
client.messages.create(model="claude-opus-5-5", max_tokens=4096,
    cache_control={"type": "ephemeral"},  # or {"type":"ephemeral","ttl":"1h"}
    system=SYSTEM, messages=history)
```
**Savings:** cut agent-loop cost 2.7–5.3× and one triage agent's bill by 83% (88% with input trimming). On DeepResearch Bench II, Fable 5.1 fell from $37.94 to $7.12/task, Sonnet 5 from $3.20 to $1.20. *Evidence: Official-measured.*
**Pitfalls:** automatic caching places the breakpoint on the *last* block — if that block changes every request, you write every time and never read. Use an explicit breakpoint on the last stable block instead. Lookback window is 20 blocks; add a second breakpoint if a turn adds 20+ blocks. Max 4 breakpoints.

**A2. Benchmark your cache hit rate.** Total input = `cache_read_input_tokens + cache_creation_input_tokens + input_tokens`. Anthropic's fleet data: agent loops read a median 84% of input from cache, top 10% at ≥94%. Below ~80% usually means something is breaking the cache. **Silent failure:** if both cache fields read 0, the prompt was below the minimum (512 tokens for Opus 5.5/Opus 5/Fable 5.1; 1,024 for Sonnet 5; 4,096 for Haiku 4.5) — no error is raised. *Evidence: Official-measured.*

**A3. Never put volatile text before the cached prefix.** Measured cost: a 25-token status line at the front of the system prompt raised a run from $0.59 to $4.24. **What breaks the cache:** editing tools (invalidates everything); toggling web search/citations; switching to fast mode; changing effort or thinking config (always invalidates messages, sometimes system/tools too); changing structured-output format; changing a task budget mid-run; adding/removing images. **Fixes:** put per-request text in the newest user turn; on Opus 5.5, Opus 5, Fable 5.1, and Opus 4.8, append `{"role":"system"}` mid-conversation messages instead of editing `system` (not available on Sonnet 5); to add tools mid-conversation, use the `inline-tools-2026-09-15` beta so `tools` stays byte-identical. **Cost of one break on a 100k prefix:** $0.50 instead of $0.02 on Opus 5.5 (25×); $1.25 instead of $0.03 on Fable 5.1 (50×). *Evidence: Official-measured.*

**A4. Pick the TTL by measuring gaps between requests.** Stay on 5-minute if turns are seconds apart (1-hour TTL cost 15–18% more on Sonnet 5/Opus 5.5 when nothing paused). Move to 1-hour if roughly 1 in 20 gaps falls between 5 min and an hour, and hour-plus gaps are rare; stay on 5-minute if ≥60% of long pauses exceed an hour. **On Opus 5.5 and Fable 5.1, cheap reads make keep-alives attractive:** keep-alives beat the 1-hour TTL by 8–13% on Opus 5.5 with only 1–2/20 turns after a pause of up to ~30 min, and by 13–20% on Fable 5.1 whenever pauses run for minutes.
**Keep-alive recipe (official):** within 4 minutes of the previous request's *start*, re-send it with `max_tokens: 0`, no `stream`:
```bash
jq '.max_tokens = 0 | del(.stream)' last_request.json | curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" --data-binary @-
```
**Pitfalls:** `max_tokens: 0` is rejected with `thinking.type: "enabled"`, structured outputs, a forced tool choice, or `compaction` — buy 1-hour instead for those. Never use `max_tokens: 1`. Cache lifetime counts from request start, so long generations eat the window. *Evidence: Official-measured.*

**A5. Batch API plus caching.** Batch is 50% off input and output; identical `cache_control` blocks per request let cache multipliers stack. Batch cache hits are best-effort (30–98% hit rate range reported, secondary); fast mode unavailable with Batch. *Evidence: Official (discount, stacking); secondary (hit-rate range).*

**A6. Tune effort before switching models.** Opus 5.5 defaults to `medium`; thinking can't be disabled. Sweep effort *down* first — if quality drops, try the next tier up at `low` before reaching for a bigger model. On verifiable tasks, run everything at `low` and re-run only failures at `high`; Anthropic's coding benchmark held the pass rate at about half the cost this way. **Pitfall:** changing effort mid-conversation invalidates the cache unless using the per-message system trick (A3); setting effort explicitly to the model's own default does not invalidate. *Evidence: Official-measured.*

**A7. Right-size `max_tokens`, task budgets, time awareness.** `max_tokens: 64,000` covered all but 2 of 14,000 measured turns; 128,000 cost nothing extra per solved task — truncation retries cost more than generous caps. Set a task budget (beta) only on the *first* request. Showing the model elapsed time cut run time 33–69% and cost per task 28–54% (with scores up to 1.9 points lower). *Evidence: Official-measured.*

**A8. Keep intermediate data out of context.** Tool search with `defer_loading`, programmatic tool calling, and web-fetch dynamic filtering. Programmatic tool calling reports 24% fewer input tokens on agentic search with a higher score. Worth tool search with ≥10 tools or >10k tokens of definitions — keep your 3–5 most-used tools non-deferred; deferred tools sit outside the cached prefix, so caching stays intact. *Evidence: Official-measured (PTC); Official (tool search).*

**A9. Context editing and compaction: batch them.** Every context-editing pass invalidates the prefix from the clearing point onward — clear in a few large batches, not many small ones. Make cache-invalidating changes on the first request *after* compaction, not the request that triggers it ($0.75/session after compaction vs $0.92 on the triggering request vs $0.95 mid-session). Anthropic itself notes context editing "cost more than it saved in the run measured." *Evidence: Official-measured.*

**A10. Audit prompts written for older models.** Instructions like "verify twice" or "be maximally thorough," and hand-rolled scratchpads, cause extra tool rounds on newer models with no accuracy gain. Run the Claude API skill's prompt-audit command in Claude Code (`/claude-api`). *Evidence: Official.*

**A11. Multi-model strategies.** *Advisor* pattern: a frontier model consulted only on hard decisions — pays off only if priced well above the executor and actually consulted (measure the consult rate). *Orchestrator* pattern: a frontier coordinator dispatches bulk work to cheaper workers (Sonnet 5), so most tokens bill at worker rates — see the Claude Cookbook "Coordinator pattern" recipe. *Evidence: Official-measured (narrow gains).*

**A12. Compare models on cost per completed task, not per token.** The tokenizer shift (~30% more tokens on Sonnet 5 vs 4.6) makes per-token comparisons misleading — recount real prompts with the token-counting endpoint per target model. Anthropic reports each newer model solves at least as many tasks as its predecessor, usually for less per solved task; Opus 5.5 specifically "performs at the level of Claude Fable 5.1 for most tasks, and costs 40% less to run than Opus 5" — comparing each model at its own default effort (medium on Opus 5.5, high on Opus 5). *Evidence: Official-measured; Official (launch claim).*

**A13. Semantic caching, routers, prompt compression** (LLMLingua, RouteLLM, GPTCache) — legitimate options for high-volume apps, but **no Claude-specific 2026 measurements were verified.** Treat as experiments behind your own A/B harness; exact-prefix prompt caching at 5% of input price (Opus 5.5) shrinks the upside of lossy compression considerably. *Evidence: Unverified.*

## 10.2 Claude Code

**C1. `/clear`, don't `/compact`, when switching tasks.** `/clear` costs nothing; `/compact` reads the conversation it summarizes, so compacting a large context is itself a large request. Use `/rename` then `/clear` and return later with `/resume`. Guide compaction: `/compact Focus on code samples and API usage`, or add a "# Compact instructions" section to CLAUDE.md. *Evidence: Official.*

**C2. Understand the subscription cache TTL.** On a subscription the cache lifetime is 1 hour, but **drops to 5 minutes once you draw on usage credits**; API keys default to 5 minutes. Your first message after a longer break reprocesses the full context — accept the "resume from a summary" offer for large idle sessions on Pro/Max. *Evidence: Official.*

**C3. Watch the cache line in `/usage`.** Since v2.1.251, `/usage` shows `Prompt cache (main)` — percentage from cache, misses, warm/cold state; from v2.1.260, it names a likely miss cause (e.g., "tool definitions changed"). Subscribers get attribution by skill/subagent/plugin/MCP server, plus flags for behaviors at ≥10% of usage. `/insights` generates a friction-pattern HTML report (itself consumes tokens). *Evidence: Official.*

**C4. Hunt hidden idle consumers** — each resends full context even while a session sits idle: scheduled `/loop` tasks; cross-session messages (`"crossSessionInbound":"hold"` to disable); goal check-ins (`CLAUDE_CODE_GOAL_CHECKIN_MINUTES=0` to disable); agent teammates (consume tokens until they exit); prompt suggestions (mostly cache reads, but toggle off if needed). Background summarization typically runs under $0.04/session. *Evidence: Official.*

**C5. Lean CLAUDE.md, skills for procedures.** CLAUDE.md loads every session; skills load only when invoked. "Aim to keep CLAUDE.md under 200 lines." Move PR-review/migration procedures into skills; a "codebase-overview" skill prevents exploratory reads. *Evidence: Official.*

**C6. Filter noisy output with a hook** (official example):
```json
{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"~/.claude/hooks/filter-test-output.sh"}]}]}}
```
```bash
#!/bin/bash
input=$(cat); cmd=$(echo "$input" | jq -r '.tool_input.command')
if [[ "$cmd" =~ ^(npm test|pytest|go test) ]]; then
  filtered_cmd="$cmd 2>&1 | grep -A 5 -E '(FAIL|ERROR|error:)' | head -100"
  echo "$input" | jq --arg filtered "$filtered_cmd" \
   '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",updatedInput:(.tool_input + {command:$filtered})}}'
else echo "{}"; fi
```
Verify with `/hooks`, or `claude --debug-file ./claude-debug.txt` and look for `modified tool input keys`. **Pitfall:** this is exactly the mechanism the (independently discredited) rtk tool uses — JetBrains found Claude Code's built-in Read/Grep already bypass Bash hooks, and Claude Code already truncates huge tool results by default. Filter only output that's genuinely large *and* routinely read in full (test runs, logs) — see Part 11 before building anything more elaborate. *Evidence: Official (mechanism); Independent (limits).*

**C7. Match the model to the task; keep Opus for hard work.** Even with Opus now the default everywhere, Anthropic's own cost docs still say: "Sonnet handles most coding tasks well and costs less than Opus. Reserve Opus for complex architectural decisions." Set `/model sonnet` or a default in `/config` for routine work. Subagents inherit an Opus switch — set `model: haiku` for simple subagents. Avoid mid-session switches (model, effort, speed all break the cache); `opusplan` switches reportedly re-read the conversation uncached. *Evidence: Official.*

**C8. Effort, not thinking budgets, on adaptive models.** Thinking can't be disabled on Opus 5.5/Fable. Use `/effort low|medium` for routine edits; reserve `xhigh`/`max` per session — Anthropic's power-user tips note max effort "burns through usage limits faster." `MAX_THINKING_TOKENS` is ignored on adaptive models. *Evidence: Official.*

**C9. Reduce MCP overhead.** Deferred loading by default; `/context` shows real occupancy; `/mcp` disables unused servers; `CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` caps verbose descriptions; keep `MAX_MCP_OUTPUT_TOKENS` at its default. Prefer CLIs (`gh`, `aws`, `gcloud`, `sentry-cli`) over MCP servers when one exists. *Evidence: Official.*

**C10. Code intelligence plugins for typed languages.** One "go to definition" call replaces a grep plus several candidate-file reads; type errors surface automatically after edits. Serena (Part 3.1) is the third-party equivalent. *Evidence: Official mechanism, no numbers.*

**C11. Delegate verbose work to subagents; be careful with agent teams.** Subagents keep test/log/doc output in their own context, returning only a summary. Agent teams use ~7× tokens in plan mode — keep teams small, on Sonnet, focused prompts, shut down when done. *Evidence: Official.*

**C12. Plan mode and early course-correction.** Shift+Tab into plan mode for complex tasks; Escape (or `/rewind`) to stop and roll back a wrong path early. Give verification targets (tests, expected output) and test incrementally. *Evidence: Official.*

**C13. Headless guardrails and reporting.** `--max-budget-usd` caps spend per run (includes the 1.1× data-residency multiplier if applicable). Admins can set `modelPricing` in managed settings so `/usage` and OpenTelemetry reflect contracted rates. OpenTelemetry is the only setup-agnostic way to stream per-user cost. **Anthropic's own benchmark:** "Across enterprise deployments, the average cost is around $13 per developer per active day and $150-250 per developer per month, with costs remaining below $30 per active day for 90% of users." *Evidence: Official.*

**C14. Deny reads of huge files.** No official `.claudeignore` — use `permissions.deny` Read rules for lockfiles, `node_modules`, build outputs, data dumps. Since Claude Code already truncates oversized results, the win is mostly avoiding *repeated* partial reads. *Evidence: Official (permissions); inference.*

## 10.3 claude.ai (subscription limits)

- **How limits work:** rolling five-hour window plus weekly limits, shared across web/desktop/mobile/Claude Code — no fixed message count. Usage depends on "the length and complexity of your conversations, the features you use, which Claude model... and the effort level" (official, support.claude.com).
- **Official tips:** lower effort for routine tasks; turn off connected apps/tools/connectors you don't need ("tools and connectors are token-intensive"); ask Claude not to search the web when current info isn't needed.
- **Projects:** put reusable documents in project knowledge — "the more you use the same content, the more benefit you get from caching."
- **Front-load context:** send full context and full texts in one well-structured message rather than drip-feeding.
- **Start fresh chats for new topics** — every turn re-reads the whole conversation.
- **Edit instead of following up** — revising the last prompt avoids stacking a failed exchange into history (anecdotal, savings unquantified but widely recommended).
- **Ask for targeted fixes, not full regenerations** — a full redo re-generates every output token.
- **Default to Sonnet or lower effort** for everyday work; reserve Opus 5.5 at high effort, Research mode, and Docs/Slides generation for tasks that actually need them.

## 10.4 Prompting techniques

- **Ask for diffs or targeted edits, not whole files** — output costs 5× input on every current model ($20 vs $4 on Opus 5.5), so output reduction pays the most.
- **Constrain format:** "≤5 bullets," "no preamble," "return only the JSON." Use structured outputs to avoid parse-and-retry loops; set the format once, since changing it invalidates the cache.
- **Remove legacy over-instruction** ("verify twice," mandatory scaffolds) — see A10.
- **Few-shot examples** belong inside the cached prefix, where re-reads are cheap, not in the variable suffix.
- **Terse personas have a ceiling** — in agentic work, most output is tool calls and code, which style instructions don't touch (why caveman saved only 8.5%, not 65%).
- **Be specific about scope** — "add input validation to the login function in auth.ts" beats "improve this codebase," which triggers broad scanning.

***
# Part 11 — What NOT to Do: Myths and Tools Shown to Backfire

- **rtk ("Rust Token Killer").** JetBrains AI blog (July 2026), 425 billed trials (~$320), Claude Code 2.1.201 + claude-sonnet-5: cost went **up 7.6%** at low effort (p=0.004), unchanged at high effort, quality unchanged. Its own "gain" counter claimed 96.2M tokens saved (99.8%) on the same trials — inflated by counting full raw output as the counterfactual (a 1.2 MB CSV "saved" 320k tokens Claude Code would have truncated anyway) and by chars÷4 estimates. Bypassed by the built-in Read/Grep tools.
- **caveman skill.** JetBrains AI blog, 86/87 SkillsBench tasks, ~$106 spend, claude-sonnet-5 at low effort: "Advertised saving: 65%. Measured saving: 8.5%… with the skill forcibly activated. This is the ceiling, not the usual-case result."
- **ponytail skill.** The one exception — a real, statistically solid signal (80 paired tasks): "Advertised: −54% code, -22% tokens, -20% cost, -27% time. Measured: −15% code, −10.3% cost, -11% time" (p=0.004). Savings concentrate in larger builds (−31% code on 300+ line tasks). Never self-activates without its SessionStart hook.
- **context-mode and similar "96–98% savings" MCP servers.** The figure is the vendor's own 21-scenario fixture benchmark; no independent test was found. Given that a similarly-marketed tool (rtk) independently *increased* cost, don't trust any "token saver" without measuring it yourself.
- **Timestamps or status lines at the top of the system prompt.** Measured as costlier than no caching at all ($4.24 vs $0.59).
- **Mid-session model/effort/speed/tool changes**, including toggling fast mode or bouncing through `opusplan`. Each rewrites the cached prefix.
- **1-hour TTL for rapid-fire agent loops with no pauses.** Costs 15–18% more when there's no idle time; conversely, don't stay on 5-minute if users routinely pause 10–30 minutes between turns.
- **Many small context-edit passes** — each re-caches everything after the clearing point; batch them instead.
- **`max_tokens: 1` keep-alives** — samples a token for nothing; use `max_tokens: 0`.
- **`MAX_THINKING_TOKENS` or "/effort none" on Opus 5.5.** Adaptive models ignore fixed budgets and thinking can't be disabled — use effort levels instead. Advice recommending `/effort none` predates adaptive-thinking models and doesn't apply here.
- **Casual agent teams.** ~7× tokens in plan mode — reserve for genuinely parallel, high-value work.
- **Trusting any tool's built-in "tokens saved" dashboard.** Validate independently with `/usage`, ccusage, or the Console bill in a paired before/after test — this is the single biggest lesson from this whole research pass.

***

# Part 12 — Step-by-Step Implementation Guide

**Step 1 — Choose a plan and set up claude.ai (~15 min).**
Pro is enough for light-to-moderate Claude Code use; Max 5x if you hit Pro limits weekly or want Fable included. In Settings: fill in Profile/Preferences (role, expertise, output conventions); create a "My Writing" Style from 2–3 samples plus a "Terse" style; turn on chat memory and past-chat search; create Projects per workstream (Coding, Research, Learning, Writing), each with a short instruction block; add Connectors you need (Google Drive/Gmail/Calendar, Notion, GitHub) under Settings → Connectors.

**Step 2 — Install Claude Code (~10 min).**
```bash
curl -fsSL https://claude.ai/install.sh | bash   # macOS/Linux/WSL
irm https://claude.ai/install.ps1 | iex           # Windows PowerShell
claude --version   # need ≥2.1.280 for Opus 5.5 default
claude update
cd your-project && claude   # sign in
/init                        # generates CLAUDE.md — then trim it
```
Lean CLAUDE.md template:
```markdown
# Project: <name>
Stack: <e.g., Next.js 15, TS, Tailwind, Postgres>
## Commands
- Dev: `pnpm dev` · Test: `pnpm test` · Lint: `pnpm lint`
## Rules
- Smallest correct change; no new deps without asking.
- Run tests + lint before declaring done.
- Never read or edit .env*, secrets/, or migrations/ without asking.
## Conventions
- Components in src/components (shadcn); server code in src/server.
```

**Step 3 — Model routing and settings.json.**
`~/.claude/settings.json`:
```json
{
  "model": "opus",
  "permissions": {
    "defaultMode": "default",
    "allow": ["Bash(pnpm test:*)", "Bash(pnpm lint)"],
    "deny": ["Read(./.env*)", "Read(./secrets/**)", "Bash(rm -rf:*)", "Bash(git push --force:*)"]
  }
}
```
`"defaultMode":"default"` restores manual approval (the pre-Aug-14 behavior); remove that line to keep the new default `auto` mode. Switch models with `/model` (`s` for session-only); `ANTHROPIC_DEFAULT_MODEL` sets a default for new sessions (v2.1.236+); pin exact versions with `claude-opus-5-5` or `ANTHROPIC_DEFAULT_OPUS_MODEL`.

**Step 4 — Core skills.**
```bash
/plugin marketplace add anthropics/skills          # → install document-skills + example-skills
/plugin marketplace add DietrichGebert/ponytail
/plugin install ponytail@ponytail
/plugin install code-review@claude-plugins-official
/plugin install security-guidance@claude-plugins-official
```
Optional: superpowers or BMAD — pick one methodology, not several.

**Step 5 — Core MCP servers.**
```bash
claude mcp add --scope user --header "Authorization: Bearer $CONTEXT7_KEY" --transport http context7 https://mcp.context7.com/mcp
claude mcp add playwright npx @playwright/mcp@latest
claude mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp","headers":{"Authorization":"Bearer '"$GITHUB_PAT"'"}}'
claude mcp list
```
Run `/context` after adding servers to check overhead. In claude.ai: Settings → Connectors → Browse.

**Step 6 — Extensions.**
Install Claude in Chrome (claude.com/claude-in-chrome); Claude Code for VS Code (Marketplace); for Office, install Claude for Microsoft 365 (Excel/Word/PowerPoint) and Claude for Outlook from AppSource, sign in once per app, enable "Let Claude work across files." Optional: Desktop Extensions (`.mcpb`) for local tools.

**Step 7 — Hooks, slash commands, subagents.**
`.claude/settings.json`:
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{ "type": "command", "command": "jq -r '.tool_input.file_path' | xargs -I{} npx prettier --write {}" }]
    }],
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{ "type": "command", "command": "jq -r '.tool_input.command' | grep -Eq 'rm -rf /|git push --force|DROP TABLE' && { echo 'Blocked dangerous command' >&2; exit 2; } || exit 0" }]
    }]
  }
}
```
Custom command `.claude/commands/review.md`:
```markdown
Review the staged diff for bugs, over-engineering, and missing tests. Output: numbered findings, severity, fix.
```
Subagent `.claude/agents/explorer.md`:
```markdown
***
name: explorer
description: Fast codebase search and summarization. Use for "where is X", "how does Y work".
tools: Read, Grep, Glob
model: haiku
***
Find the relevant files, quote the key lines, and return a ≤15-line summary. Never edit.
```

**Step 8 — UI workflow.**
1. `npx shadcn@latest init`, then add the shadcn MCP.
2. Add an animated registry — Magic UI, coss ui, Watermelon UI, or Motion Primitives — via shadcn registry URLs.
3. Enable the `frontend-design` skill.
4. Prompt: "Build X with shadcn + frontend-design; after each change, use Playwright to screenshot at 375px and 1440px, compare against the spec, and iterate until it matches."
5. Don't start new projects on Tailwind Plus (closed to new buyers). For dashboards, Tremor still works but is slow-moving — check activity first.

**Step 9 — Research, writing, learning workflows.**
Research: a claude.ai Project + Research mode + a custom skill (built with skill-creator) requiring every figure to carry a URL and verbatim quote; export via the docx/pdf skills. Writing: your custom Style + doc-coauthoring skill + a banned-phrase list; ask Opus 5.5 to "lead with the conclusion." Learning: Learning-style responses in claude.ai, `/output-style` Learning in Claude Code, quiz artifacts.

**Step 10 — Token monitoring and habits.**
```bash
npx ccusage@latest daily
```
Set a statusline (ccstatusline or claude-hud) showing context % and cost. Habits: `/clear` per task, a subagent model in every agent file, `/context` after adding MCP servers, keep the saved rate-limit reset for crunch time.

**Step 11 — Advanced (optional).**
Plugins/marketplaces: `/plugin marketplace add <owner/repo>` — prefer claude-plugins-official, scan third-party plugins before installing. Spec-driven development: Spec Kit, BMAD, or Task Master for large features. Parallel agents: `git worktree add ../feat-a -b feat-a`, run one `claude` per worktree with its own `--model`; agent teams and background sessions are built in; Vibe Kanban works but is now community-maintained. Headless mode: `claude -p "run tests and summarize failures" --output-format json`, and read `modelUsage` to confirm which model actually ran. GitHub Actions: install `anthropics/claude-code-action` (`/install-github-app` in Claude Code), then mention `@claude` in PRs/issues.

***

# Part 13 — Prioritized Checklists

## 13.1 Top-15 token-saving checklist (impact ÷ effort)

1. **API: turn on caching** (top-level `cache_control`); confirm ≥80% of input served from cache.
2. **Move all volatile text** (timestamps, IDs, per-request context) after the last stable cache breakpoint.
3. **Claude Code: `/clear` between unrelated tasks**, not `/compact`.
4. **Reset the model after v2.1.280:** set Sonnet as the default for routine work if you're on Pro/Team Standard; escalate to Opus 5.5 per task.
5. **Lower effort to `low`/`medium` for routine work**, re-run failures at `high` where verifiable.
6. **Never change model, effort, speed, or tools mid-session** — do it at natural breaks or right after compaction.
7. **Pick TTL from measured gaps** — 1-hour for human-paced chats; consider `max_tokens: 0` keep-alives on Opus 5.5/Fable 5.1.
8. **Trim CLAUDE.md to under 200 lines**; move procedures into skills.
9. **Disable unused MCP servers** (`/mcp`); prefer CLIs (`gh`, `aws`, `sentry-cli`).
10. **Batch API (50% off, stacks with caching)** for anything that can wait 24 hours.
11. **Check `/usage` weekly** for cache misses, idle loops, MCP/skill attribution; kill idle consumers.
12. **Plan mode + specific prompts** for multi-file work; Escape/`/rewind` early.
13. **Delegate verbose operations to subagents on `model: haiku`/Sonnet**; avoid agent teams unless the ~7× parallelism is worth it.
14. **claude.ai: switch off connectors/web search when not needed**; use Projects for reused documents; new chats per topic.
15. **Run the prompt audit** (`/claude-api` prompt-audit) after every model change; recount tokens on the new tokenizer.

## 13.2 General quick-start checklist (setup priority)

1. ☐ `claude update` to v2.1.280+, confirm `/model` shows Opus 5.5.
2. ☐ Decide permissions: keep auto mode, or set `defaultMode: default`; add deny rules for secrets.
3. ☐ Write a lean CLAUDE.md (≤200 lines).
4. ☐ Install `anthropics/skills` (document + example skills) and Ponytail.
5. ☐ Add Context7, Playwright, GitHub MCP; audit with `/context`.
6. ☐ Create explorer and test-runner subagents pinned to `haiku`/`sonnet`.
7. ☐ Add prettier + dangerous-command hooks.
8. ☐ Set up claude.ai Projects, Styles, Memory, Connectors.
9. ☐ Install Claude in Chrome, VS Code extension, M365 add-ins if relevant.
10. ☐ Set up ccusage + a statusline; review spend weekly.
11. ☐ API users: enable prompt caching, move non-urgent jobs to the Batch API.
12. ☐ Optional: superpowers or BMAD, worktrees, GitHub Action.

***

# Part 14 — Final Caveats and What Remains Unverified

- **Unverified this pass:** GitHub star counts and maintenance dates for most listed repos (a few spot-checks exist, marked "community-reported" throughout — re-check before citing publicly). MCP install commands for AWS (awslabs/mcp), Docker MCP Toolkit/Gateway, Kubernetes, GitLab, Prisma, Brave, Tavily, Perplexity, 21st.dev Magic, Magic UI, arXiv/Semantic Scholar/PubMed, and Obsidian servers. The Atlassian endpoint (v1 vs v2) and Firecrawl's Claude Code command are unconfirmed. Raycast/Alfred extensions, a Microsoft Teams app, `.mcpb` directory status, and Claude in Chrome plan eligibility. Hook exit-code-2 full semantics. Default auto-compaction percentage on 1M models. Whether `.claudeignore` is supported (assume not).
- **Opus 5.5 tokenizer:** very likely the same one used by Opus 5 and Fable 5.1, but not officially confirmed for Opus 5.5 specifically.
- **AutoDream in Claude Code:** evidence comes from a GitHub issue and third-party write-ups, not official docs — may be flag-gated, experimental, or changed by the time you read this.
- **Team seat multipliers:** the specific 1.25×/6.25× figures come from secondary sources quoting the help center; the pricing page itself only says "more than Pro" and "5x more than Standard."
- **Anthropic's own cost measurements are "directional, not guarantees."** Anthropic's own docs frame their savings figures this way. The JetBrains independent tests used Sonnet 5 on SkillsBench specifically and may not transfer cleanly to Opus 5.5 or to your own codebase — validate any lever with a paired before/after on your own bill before trusting it at scale.
- **Pending model releases:** Sonnet 5.5 and Haiku 5.5 are due "in the coming weeks" as of this writing and will likely change model-routing and cost advice throughout this document. Re-check pricing and defaults when they ship.
- **Fast-moving surface generally:** Claude Code ships extremely fast — model names/defaults, Auto mode behavior, and 2026 cloud/agent features (Agent view, Agent teams, Dreams/AutoDream) were changing or in preview as of writing. Verify against code.claude.com/docs before treating anything time-sensitive here as permanent.
- **Some cited figures are vendor-reported or benchmark-specific**, including Ponytail's README claims (vs. the independently measured, lower figures used in the corrected version of this document), BMAD's star count and Trending rank, and Anthropic's own Opus 5.5 benchmark table (GPT-6 Astra led on Terminal-Bench-Science and AutomationBench specifically — Opus 5.5 is not uniformly ahead of every competitor on every benchmark).

*This document reflects a multi-pass research and verification process completed September 25, 2026. Treat anything marked ❓ as a lead to re-check yourself, not a settled fact.*
