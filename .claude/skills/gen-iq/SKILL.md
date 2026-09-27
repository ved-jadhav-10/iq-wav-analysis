---
name: gen-iq
description: Generate a synthetic SigMF IQ recording with exact ground truth (modulation, samples per symbol, SNR, impairments, FEC, interleaver, CRC-framed payload, several signals) using dsp.synth. Use when a test, benchmark, bug reproduction or demo needs a signal with known answers.
---

1. Settle the scene: modulation (`dsp.synth.chain.MODULATIONS`), samples per symbol (non-integer allowed), pulse (`rrc`/`rect`) and roll-off, frame (`dsp.synth.bits.FrameSpec`, or `None`), optional scrambler / `outer` RS / `byte_interleaver` / `inner` code / bit `interleaver` (reuse the presets in `bench/src/bench/presets.py` `CHAINS` and `FRAMES` rather than inventing parameters), `Impairments`, power and noise. State SNR as per-sample SNR and, for digital signals, Es/N0 = SNR + 10 log10(sps); the truth records both.
2. Write a short script in the scratchpad (not the repo) and run it with `uv run python <script>`:

   ```python
   from pathlib import Path
   from dsp.synth.chain import Scene, SignalSpec, generate, write_sigmf
   from dsp.synth.impair import Impairments

   scene = Scene(
       1 << 16,
       (SignalSpec("qpsk", sps=4.3, impairments=Impairments(cfo=1e-3)),),
       noise_db=-15.0,
       sample_rate=2.4e6,
       center_frequency=433.92e6,
   )
   g = generate(scene, seed=12345)
   write_sigmf(Path("data/generated/qpsk-demo"), g, scene, "ci16_le")
   ```

   `data/` is git-ignored. Leave `sample_rate` or `center_frequency` as `None` only when the point is to test UNKNOWN handling.
3. Pick a seed that is not in `bench/sealed/manifest.json` (check it) and not a dev/null bench seed, unless reproducing a bench file on purpose (then use `bench.presets.dev_draw(seed)` / `null_draw(seed)` and say so).
4. Verify: `uv run python tools/inspect_iq.py data/generated/<name>.sigmf-meta` must show the datatype, rate and centre frequency MEASURED as written. The truth is in the metadata's `sanket:truth` and annotations; for exact bits use `g.signals[i]` (`payloads`, `framed`, `coded`, `symbols`).
5. Report the file paths, seed and the truth table (per signal: modulation, sps / symbol rate, SNR and Es/N0, offset, chain, frame, impairments). Tests built on it must compare against this truth, never "it didn't crash".
