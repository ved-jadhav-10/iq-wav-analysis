---
name: plan-status
description: Check the repository against the progress checklists in docs/PLAN.md §0 and update them. Use after finishing a milestone item, before reporting progress, or when asked "where are we" on Sanket.
---

1. Read `docs/PLAN.md` §0 (Progress) and the §5 definition of the current milestone and its exit gate.
2. For every checklist item, find evidence in the repo, not in memory or the plan text:
   - the file or directory exists (`git ls-files`, Glob);
   - the command passes now: `uv run pytest`, `uv run ruff check`, `uv run pyright`, `npm test` / `npm run lint` / `npm run typecheck` / `npm run build` / `npm run e2e` in `frontend/`, `uv run python tools/third_party.py --check`;
   - for CI items, the latest run on `main` (`gh run list --branch main --limit 1`).
3. Tick an item only with evidence; untick one whose evidence no longer holds. Never tick an exit gate that CI or `bench/` hasn't measured.
4. Update the stage table, the "Checked against the repository on" date and the **Next** line. Keep entries short; don't add sprint dates or owner names.
5. Report what changed and what evidence each change rests on.
