# How to work in this repo (read every session)

- **Keep working on your own.** Take the next item from [PLAN §0](../docs/PLAN.md#0-progress) "Next" and carry on; don't stop to ask which one or to confirm. Ask only when blocked on something that is the user's to decide.
- **Commit and push as work lands**, once the checks in [CLAUDE.md](CLAUDE.md) pass. Commits go through the user's own git identity only: no `Co-Authored-By`, no "Generated with Claude" lines, in commits or PR text.
- **Commit messages are 1–2 short lines.** No bodies, no lists.
- **Update the docs when an item lands:** tick it in PLAN §5, update the §0 table and Open gates. No new planning or explainer docs.
- **Subagents (Sonnet, high effort) only when they make things faster:** a self-contained chunk that doesn't touch the files you're editing (a UI section, a report generator, a review). Tell them not to commit or edit PLAN.md. Do small or tightly coupled work yourself.
- **Mind the context.** Past about 50 % of the window, run `/compact` or start a new session; PLAN §0 and this file are enough to pick up.
- **Tests are slow:** run only the touched test files while iterating and the full suite before a commit, in the background (the commands are in CLAUDE.md).
