---
name: inspect-iq
description: Quick sanity report on any IQ or audio recording (raw, SigMF, WAV, .npy, .sdriq, Blue, VITA 49, FLAC/MP3/Ogg, .gz/.zip) - the reader that opens it, ranked format candidates, the Assumptions block, what is still UNKNOWN or listed for review, quadrature check, clipping, DC and I/Q balance. Use when a file behaves unexpectedly, before debugging a stage on it, or when asked "what is this file".
---

1. Run `uv run python tools/inspect_iq.py <file> [<file> ...]`. It picks the reader from the extension and header magic (a stand-in until the product has a dispatcher), sizes `.gz`/`.zip` without unpacking, and reads at most 2^20 samples for statistics.
2. Report the output as-is: the Assumptions table, the UNKNOWN and needs-review lines, every warning, and the statistics. Don't restate a HYPOTHESIS or UNKNOWN value as fact, and don't fill in a sample rate, centre frequency or format the report leaves UNKNOWN.
3. If the reader is wrong for the file, say which one it should be and why (extension vs header). For a raw file whose format is UNKNOWN, list the tied candidates the sniffer gave and what would settle them (a recorder name, a known carrier, the analyst).
4. Never inspect anything under `bench/sealed/` or files generated from its seeds.
