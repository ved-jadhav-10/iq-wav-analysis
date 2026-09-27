---
name: bench-run
description: Run Sanket's benchmarks (format sniffer bench, bench v0 dev and null sets, the TorchSig export) and compare with the committed results in bench/results/. Use after changing ingest, the sniffer, dsp.synth, bench presets or any stage the bench scores, and before quoting a bench number anywhere.
---

1. Refuse to go on if the sealed set was touched: `git status --short bench/sealed` and `git diff main -- bench/sealed` must both be empty. Never run `bench run sealed` unless the user asks for a release measurement, and never look at per-file sealed results.
2. Regenerate data only if missing or if dsp.synth / bench presets changed since it was made (data in `bench/data/` is git-ignored; generation of dev takes ~5 min):
   `uv run bench generate dev` · `uv run bench generate null`
   The TorchSig export is regenerated only under WSL2: `~/torchsig-env/bin/python bench/torchsig/export.py` (see its docstring).
3. Score: `uv run python -m bench.sniffer`, `uv run bench run dev`, `uv run bench run null`, and `uv run bench run torchsig` if `bench/data/torchsig/` exists.
4. Compare with the last commit: `git diff --stat bench/results` and, per set, a table of old → new for every summary number (files, ingest mismatches, sniffer wrong, sniffer outcomes, true rate among candidates and median rank, VERIFIED values, accepted decodes). Any rise in "wrong", ingest mismatches, VERIFIED values or accepted decodes on the null set is a regression: stop and report it rather than committing the numbers.
5. If a result file changed only because the code changed as intended, say what changed and why. Numbers quoted in the README, deck or PLAN must come from these files.
