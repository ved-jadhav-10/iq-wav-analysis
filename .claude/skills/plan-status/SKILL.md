---
name: plan-status
description: Check the repository against the progress checklists in docs/PLAN.md §0 and update them. Use after finishing a milestone item, before reporting progress, or when asked "where are we" on Sanket.
---

1. Read `docs/PLAN.md` §0 (Progress: the stage table and Open gates) and §5's per-milestone checklists, starting with the current milestone and its exit gate. If [`docs/PROTOTYPE_PLAN.md`](../../../docs/PROTOTYPE_PLAN.md) exists, prototype mode is active: check its phases (P0–P4) alongside the milestone checklists, since the demo sprint is the current work.
2. For each checklist item you're asked about (or, with no target given, the current milestone's), find evidence in the repo, not in memory or the plan text — but don't re-run the whole suite just to check status:
   - the file or directory exists (`git ls-files`, Glob) for "was this built";
   - only run the specific command a claim rests on (e.g. `uv run pytest tests/dsp/test_slice.py` for one test file, not the full `pytest`), or reuse a result already reported this session;
   - for CI or bench-gate items, the latest recorded run (`gh run list --branch main --limit 1`, or a `bench/results/*.md` file) rather than re-running CI or bench locally.
3. Tick an item in §5 only with evidence; untick one whose evidence no longer holds. Never tick an exit gate that CI or `bench/` hasn't measured — a missed gate number is recorded in §0's Open gates table, not left unticked with no explanation.
4. Update §0: the stage table (Built / Gate met), the Open gates table, the "Checked against the repository on" date, the prototype-mode line if it changed, and the **Next** line (at most five bullets). Keep entries short; don't add sprint dates or owner names.
5. Report what changed and what evidence each change rests on.
