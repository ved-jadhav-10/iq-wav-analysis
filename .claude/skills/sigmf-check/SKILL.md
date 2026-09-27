---
name: sigmf-check
description: Validate a .sigmf-meta (or .sigmf archive) against the SigMF specification with the reference sigmf-python validator, and against what Sanket's reader makes of it. Use on SigMF files Sanket writes (dsp.synth, the TorchSig export, later "Save as SigMF"), and on third-party SigMF files that read oddly.
---

1. Spec check, dev-time only (the `sigmf` package is LGPL and is never a product dependency, so run it through `uvx`, which keeps it out of the workspace):
   `uvx --from sigmf sigmf_validate -v <file.sigmf-meta>`: a pass prints "Validated all N files OK!"; a failure prints `ERROR:root:` lines (read the output, not the exit code).
   Report every error verbatim. Extension keys (`sanket:*`, `torchsig:*`) are fine only if `core:extensions` declares them or they are optional; flag undeclared ones.
2. Sanket check: `uv run python tools/inspect_iq.py <file.sigmf-meta>`. Flag, with the fix:
   - `core:datatype` or `core:sample_rate` missing (the reader reports them UNKNOWN; SigMF requires both);
   - no `core:frequency` in the first capture (centre frequency UNKNOWN; fine for baseband exports, but say so);
   - a data-file size that isn't a whole number of samples (warning on the datatype);
   - `core:header_bytes`, `core:trailing_bytes` or `core:dataset` that leave the data offset UNKNOWN.
3. For files Sanket wrote, also check that annotations carry the truth the writer promised (`sanket:truth` in the global object for dsp.synth; `core:label` and `torchsig:*` per annotation for the TorchSig export).
4. Pass only when both checks are clean. Never "fix" a file by editing its metadata to match what the reader expects; fix the writer.
