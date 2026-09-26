# SIH26147 — IQ/WAV signal analysis tool

- **Start here:** [docs/PLAN.md](docs/PLAN.md) for the current phase, owners and exit criteria. Check today's date against the phase table before assuming what week we're in.
- **Competitive claims and numeric targets:** [docs/STANDARDS_TO_BEAT.md](docs/STANDARDS_TO_BEAT.md) — never restate a rival claim or a target without checking it here first.
- **Claude Code tooling (skills/plugins/MCP servers) and how to set them up:** [docs/CLAUDE_SKILLS_MCP.md](docs/CLAUDE_SKILLS_MCP.md).
- **Project rules go here once `/init` runs and the codebase exists** — merge in the rules block from [CLAUDE_SKILLS_MCP.md §7](docs/CLAUDE_SKILLS_MCP.md#7-claudemd-rules-to-add) at that point rather than duplicating them now.
- The product ships **air-gapped**: nothing built for it may depend on an MCP server, an LLM, or network access at runtime. Tooling in CLAUDE_SKILLS_MCP.md is dev-time only.
