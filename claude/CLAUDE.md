# Sanket (SIH26147) — IQ/WAV blind signal analysis

- **Start here:** [../docs/PLAN.md](../docs/PLAN.md) — 1.0 scope, the production bar (§2), architecture (§3), product identity (§4) and milestones M0–M8 with their status. Work toward the current milestone's exit gate.
- **Competitive claims and numeric targets:** [../docs/STANDARDS_TO_BEAT.md](../docs/STANDARDS_TO_BEAT.md) — never restate a rival claim or a target without checking it here first. Targets are not claims until `bench/` reproduces them.
- **Claude Code tooling (skills/plugins/MCP servers):** [CLAUDE_SKILLS_MCP.md](CLAUDE_SKILLS_MCP.md).
- **Repo state:** `frontend/` exists (Vite + React 19 + TS strict + Tailwind 4) and runs on a synthetic demo capture. `dsp/`, `ml/`, `backend/`, `bench/` don't exist yet. Don't assume code exists just because the plan describes it.
- **Frontend checks before calling UI work done:** `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` in `frontend/`, then look at it in a browser in both themes.
- **Identity is fixed:** name in `frontend/src/brand.ts`, all colours as tokens in `frontend/src/styles/index.css`, evidence-level glyphs/colours in `frontend/src/components/levelStyles.ts`. Follow the UI rules in PLAN §4 — evidence is never colour-only, no dead controls, demo data always labelled.
- **Never silently assume** a sample rate, datatype, byte order or IQ order: state it as an assumption or UNKNOWN. VERIFIED only from a CRC pass, sync-word recurrence or re-encode match.
- **Air-gapped product:** nothing shipped may depend on the network, an MCP server or an LLM at runtime. No GPL/AGPL/non-commercial code in the product; never copy code from rival SIH repos.
- When `dsp/` and friends exist, merge the full rules block from [CLAUDE_SKILLS_MCP.md §7](CLAUDE_SKILLS_MCP.md#7-claudemd-rules-to-add) into this file.
