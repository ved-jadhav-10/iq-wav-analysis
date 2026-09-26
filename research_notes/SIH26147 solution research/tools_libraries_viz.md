# Open-source tools, libraries and visualization approaches for an offline IQ/WAV analysis web app (React+TS / FastAPI / Python DSP, air-gapped, Windows + Linux CPU)

Method note: version/date/licence metadata below was pulled on 2026-09-27 directly from the PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`) and the npm registry (`https://registry.npmjs.org/<pkg>`), plus GitHub README pages. The GitHub REST API was rate-limited (403) from this machine, so GitHub "last release" dates for C/C++ tools (decoders, liquid-dsp, aff3ct) could NOT be pulled programmatically — flagged in Gaps. The "Windows wheel = True" results below are reliable; a "no Windows wheel" result for a pure-Python package just means it ships a universal `py3-none-any` wheel/sdist (my script's pure-wheel check was unreliable, so I don't report it).

## Q1. Python DSP / comms / FEC libraries — licence, maintenance, Windows installability, suitability

### Takeaway
A permissive, actively-maintained, Windows-pip-installable core exists: NumPy/SciPy + numba (BSD) for hot loops, galois (MIT) for BCH/RS/finite fields, reedsolo (public domain/MIT-0) for byte RS, sigmf (LGPL-3, OK to import unmodified) for metadata, ONNX Runtime (MIT) for ML. komm is the most active "comms toolbox" but is GPL-3.0-only (licence red flag); scikit-commpy (BSD) and pyldpc (MIT) are stale since 2022/2020 and should be vendored/used for reference only. Sionna has moved to a PyTorch backend (v2.x) and is heavy for a CPU air-gapped install.

### Cited Findings
**Core numeric / JIT**
- numba 0.67.0, released 2026-08-11, BSD licence, requires Python >=3.10, ships Windows wheels; companion llvmlite 0.49.0 (2026-08-11, BSD-2-Clause AND Apache-2.0 WITH LLVM-exception), Windows wheels — [PyPI numba JSON](https://pypi.org/pypi/numba/json); [PyPI llvmlite JSON](https://pypi.org/pypi/llvmlite/json)
- numpy 2.5.3 released 2026-09-06, requires Python >=3.12, Windows wheels — [PyPI numpy JSON](https://pypi.org/pypi/numpy/json)
- Known Windows/freezing issue: numba/llvmlite frozen with PyInstaller produced `ModuleNotFoundError` for `numba.core.types.old_scalars` / `numba.core.datamodel.old_models` (numba 0.61rc/llvmlite 0.44rc, CPython 3.13) — [pyinstaller #8989](https://github.com/pyinstaller/pyinstaller/issues/8989); [numba #9844](https://github.com/numba/numba/issues/9844)
- Older reported llvmlite failure when frozen on Windows: `OSError: [WinError 126] The specified module could not be found` — [pyinstaller #2180](https://github.com/pyinstaller/pyinstaller/issues/2180); pip/uv llvmlite install errors on Windows historically occurred when no wheel matched the Python version — [numba #7656](https://github.com/numba/numba/issues/7656), [uv #9898](https://github.com/astral-sh/uv/issues/9898)
- `@jit(cache=True)` persists compiled code to disk for later runs — [Numba FAQ](http://numba.pydata.org/numba-doc/0.38.0/user/faq.html)

**Comms toolboxes**
- komm 0.34.0 released 2026-09-16, **GPL-3.0-only**, Python >=3.11, maintainer Roberto W. Nobrega, self-described "under development" (API may change); inspired by MATLAB Comms Toolbox, GNU Radio, CommPy, SageMath — [PyPI komm](https://pypi.org/project/komm/); [PyPI komm JSON](https://pypi.org/pypi/komm/json); [komm.dev](https://komm.dev/)
- scikit-commpy (CommPy) 0.8.0, released 2022-10-10 (no release since), BSD-3-Clause; features: convolutional codes, Viterbi/MAP decoders, turbo codes, LDPC with belief propagation, PSK/QAM/OFDM, RRC/Gaussian filters, PN/Zadoff-Chu sequences, SISO/MIMO channels, 802.11 simulation — [PyPI scikit-commpy](https://pypi.org/project/scikit-commpy/); [PyPI JSON](https://pypi.org/pypi/scikit-commpy/json)
- Sionna 2.1.0 released 2026-09-09, Apache-2.0, **backend PyTorch (2.9+)**, Python >=3.11, packages Sionna PHY (link-level), SYS (system-level), RT (ray tracing; CPU needs LLVM); `sionna-no-rt` install variant exists; recommended OS Ubuntu 24.04, Windows not explicitly supported/excluded — [PyPI sionna](https://pypi.org/project/sionna/); [PyPI JSON](https://pypi.org/pypi/sionna/json)
- (Older Sionna 0.x releases were TensorFlow-based, Apache-2.0) — [PyPI sionna 0.17.0](https://pypi.org/project/sionna/0.17.0/)

**FEC / finite fields**
- galois 0.4.11 released 2026-05-02, MIT, depends on NumPy + Numba; implements BCH and Reed-Solomon codes, GF(p^m) arithmetic, polynomials over GF, LFSRs (FLFSR/GLFSR), NTT; stated as intended for research/education, not production security — [PyPI galois](https://pypi.org/project/galois/); [PyPI JSON](https://pypi.org/pypi/galois/json)
- reedsolo 1.7.0 released 2023-01-17 (latest stable), licence MIT-0 / Unlicense (public domain); pure Python with optional Cython build; errors-and-erasures RS, any GF above 2^3, corrects up to floor(nsym/2) errors or nsym erasures; Cython build on Windows needs MSVC 14.x — [PyPI reedsolo](https://pypi.org/project/reedsolo/)
- pyldpc 0.7.9 released 2020-02-29, MIT (stale ~6 years) — [PyPI pyldpc JSON](https://pypi.org/pypi/pyldpc/json)
- AFF3CT is MIT-licensed, a fast multi-threaded C++ FEC simulator/library for SDR; a separate Python wrapper `py_aff3ct` exists on GitHub (built from source via its own `configure.py`) — [aff3ct.github.io](https://aff3ct.github.io/); [aff3ct repo](https://github.com/aff3ct/aff3ct); [py_aff3ct repo](https://github.com/aff3ct/py_aff3ct)
- `py-aff3ct` is NOT on PyPI (PyPI returned 404 for `py-aff3ct`) — [PyPI query](https://pypi.org/pypi/py-aff3ct/json)

**Metadata / I/O / hardware**
- sigmf (sigmf-python) 1.13.0 released 2026-08-19, licence metadata "GNU LESSER GENERAL PUBLIC LICENSE" (LGPL), Python >=3.10 — [PyPI sigmf JSON](https://pypi.org/pypi/sigmf/json)
- SoapySDR is not published on PyPI under that name (404) — [PyPI query](https://pypi.org/pypi/SoapySDR/json)

**liquid-dsp**
- liquid-dsp (C library, MIT per upstream) has only third-party Python wrappers: `umireon/pyliquiddsp` and `michelp/pyliquid-dsp` (CFFI); no Windows install instructions found; liquid-dsp itself must be built first — [pyliquiddsp](https://github.com/umireon/pyliquiddsp); [pyliquid-dsp](https://github.com/michelp/pyliquid-dsp); [liquid-dsp](https://github.com/jgaeddert/liquid-dsp)

**PySDR**
- PySDR is a textbook (not a pip library), licensed **CC BY-NC-SA 4.0** (NonCommercial, ShareAlike) — copying its code into a product carries NC/SA obligations — [PySDR cyclostationary chapter](https://pysdr.org/content/cyclostationary.html)

**ONNX Runtime**
- onnxruntime 1.30.0 released 2026-09-10, MIT, Microsoft; Python >=3.11; wheels for CPython 3.11–3.14 including Windows x86-64 and ARM64 (~14 MB each) — [PyPI onnxruntime](https://pypi.org/project/onnxruntime/); onnxruntime-web 1.30.0 (MIT) also exists for in-browser inference — [npm onnxruntime-web](https://registry.npmjs.org/onnxruntime-web)

### Inferences
- Recommended permissive core: numpy + scipy + numba + galois + reedsolo + sigmf + onnxruntime. All have Windows wheels or are pure Python, so a Windows wheelhouse is feasible.
- Python version pin matters: numpy 2.5 needs >=3.12, onnxruntime/komm/sionna need >=3.11 → pin **CPython 3.12** (or 3.13) for the whole stack.
- komm (GPL-3.0-only): use only as an offline cross-check in a dev/test environment, or accept GPL for the distributed backend. If the product must stay permissive, re-implement (Viterbi, conv codes) with numba, using CommPy (BSD) as a reference.
- CommPy and pyldpc are stale; vendor the specific functions you need (BSD/MIT allow this) and add tests, not a pinned dependency.
- Sionna 2.x pulls in PyTorch (hundreds of MB). It's overkill for an air-gapped CPU tool unless you already ship torch for ML; its LDPC/polar (5G) decoders are its main draw.
- aff3ct gives the best FEC performance but needs a C++ build per platform (MSVC on Windows); treat it as optional/advanced.
- sigmf is LGPL: importing it unmodified as a separate package is normally fine for a closed or permissive app; modifying it triggers LGPL obligations.
- numba in frozen apps: pin a numba/llvmlite pair known to work with the chosen PyInstaller hooks, add hidden imports for `numba.core.*`, and pre-warm or AOT the kernels. `cache=True` writes to `__pycache__` next to the source, which may be read-only in a frozen app → set `NUMBA_CACHE_DIR` to a writable user directory (inference, not verified in sources).

### Gaps
- Could not get GitHub release dates for liquid-dsp, aff3ct/py_aff3ct or CommPy master activity (GitHub API rate-limited).
- The "known bugs" list per library isn't comprehensive; the only issues found and cited are numba/PyInstaller ones.
- No benchmark numbers found comparing komm/CommPy/galois/aff3ct decoding throughput.
- No `pysdr` pip package was verified; PySDR is treated as reference material only.
- SoapySDR Python bindings availability on Windows (via conda-forge / PothosSDR installer) was not verified this session; for a file-based offline analyser SoapySDR isn't needed anyway.

## Q2. Cyclostationary / signal-analysis Python packages

### Takeaway
There's no mature, maintained, permissive pip package for cyclostationary analysis. The options are small reference implementations (PySDR NC-licensed code; phwl/cyclostationary FAM notebooks) and a 2026 PyTorch GPU library (CycloTorch, not on PyPI under that name). Plan to implement FAM/SSCA in NumPy+numba yourself.

### Cited Findings
- CycloTorch: Python library implementing cyclic spectral correlation estimators and frequency-shift filters, using PyTorch for GPU acceleration (SoftwareX 2026 article) — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2352711026001901)
- `cyclotorch` returned 404 on PyPI — [PyPI query](https://pypi.org/pypi/cyclotorch/json)
- phwl/cyclostationary: estimates Spectral Correlation Density using FAM, with Jupyter examples for different modulations — [GitHub phwl/cyclostationary](https://github.com/phwl/cyclostationary)
- University of Delaware "Cyclostationary Signal Processing in Python" resource — [udel.edu/~mm/csp](https://udel.edu/~mm/csp/); a publicly available Python SCF estimator was highlighted on the CSP blog — [cyclostationary.blog](https://cyclostationary.blog/2022/11/17/csp-community-spotlight-a-publicly-available-python-based-scf-estimator/)
- PySDR gives Python code for the Frequency Smoothing Method, Time Smoothing Method and FAM; SSCA is mentioned but not implemented; FAM output has "an enormous number of pixels" needing max/mean pooling for display; FSM needs at least `2/alpha_resolution` samples; licence CC BY-NC-SA 4.0 — [PySDR cyclostationary](https://pysdr.org/content/cyclostationary.html)
- FAM and SSCA are orders of magnitude cheaper than looping time-smoothing approaches, and both compute all cycle frequencies at once — [PySDR](https://pysdr.org/content/cyclostationary.html); [cyclostationary.blog SCF tag](https://cyclostationary.blog/tag/spectral-correlation-function/)
- Hardware FAM/SSCA implementations (AMD Versal) are documented in a 2025 arXiv paper, useful for algorithm structure — [arXiv 2506.18003](https://arxiv.org/pdf/2506.18003)

### Inferences
- Implement FAM (and optionally SSCA) in NumPy with numba-accelerated channelization. Re-derive from papers or the MIT/unknown-licensed repos rather than copying PySDR code (NC licence).
- For display, apply server-side max-pooling to the SCF (alpha × f) image before sending it to the browser, as PySDR suggests.

### Gaps
- Licence of phwl/cyclostationary and the udel.edu code wasn't verified.
- CycloTorch's licence and repo URL weren't retrieved (article only).

## Q3. Web waterfall / spectrogram / constellation rendering

### Takeaway
IQEngine (MIT, React+TypeScript client + Python FastAPI API) is almost exactly the target architecture, so its components and its MIT `webfft` npm package are the prime candidates to fork or borrow from. OpenWebRX is AGPL-3.0 (avoid copying code). For rendering, use a WebGL texture-based spectrogram (regl/twgl or raw WebGL2; deck.gl BitmapLayer/tiles for pan/zoom) fed by a server-side multi-resolution FFT pyramid. Use uPlot (MIT) for fast 1-D PSD/time plots, and a WebGL point/density layer (regl/deck.gl, or a server-computed 2-D histogram texture) for constellations.

### Cited Findings
**IQEngine**
- IQEngine: MIT-licensed; React/TypeScript client and Python FastAPI backend (`api` folder); Docker deployment; GNU Radio plugin support; ~988 commits, active — [GitHub IQEngine](https://github.com/IQEngine/IQEngine)
- Features: spectrogram + time + freq + IQ plots with zoom and adjustable scales; a table of recordings in a directory or blob storage with spectrogram thumbnails; can visualize local files with processing done client-side; built on SigMF; deployable as a private instance — [IQEngine README](https://github.com/IQEngine/IQEngine/blob/main/README.md); [rtl-sdr.com](https://www.rtl-sdr.com/iqengine-a-web-based-toolkit-for-sharing-and-analyzing-rf-iq-recordings/)
- IQEngine created its own client-side FFT library "WebFFT" (npm); supports FIR filtering and arbitrary Python snippets prior to FFT, all client-side — [GitHub IQEngine](https://github.com/IQEngine/IQEngine)
- npm `webfft` 1.0.3, MIT, last published 2024-01-01 — [npm registry webfft](https://registry.npmjs.org/webfft)
- Docker image published as a GitHub package — [ghcr IQEngine](https://github.com/orgs/IQEngine/packages/container/package/iqengine)

**Other SDR web UIs**
- OpenWebRX: **AGPL-3.0** (also available commercially); uses HTML5 canvas, WebSocket, Web Audio; sdr.js (libcsdr compiled to JS); compressed waterfall stream; 3D waterfall display — [ha7ilm/openwebrx](https://github.com/ha7ilm/openwebrx); [jketterl/openwebrx](https://github.com/jketterl/openwebrx)
- Reference minimal pattern: bastibe/WebGL-Spectrogram — WebGL animated spectrogram, FFT in Python/Tornado backend — [GitHub bastibe/WebGL-Spectrogram](https://github.com/bastibe/WebGL-Spectrogram)

**JS rendering libraries (npm registry, 2026-09-27)**
- uPlot 1.6.32 (MIT), last publish 2025-03-14 — [npm uplot](https://registry.npmjs.org/uplot)
- regl 2.1.1 (MIT), last publish 2024-11-12 — [npm regl](https://registry.npmjs.org/regl)
- twgl.js 7.0.0 (MIT), 2025-07-16 — [npm twgl.js](https://registry.npmjs.org/twgl.js)
- deck.gl 9.4.0 (MIT), 2026-09-05 — [npm deck.gl](https://registry.npmjs.org/deck.gl)
- plotly.js-dist-min 4.1.1 (MIT), 2026-09-14 — [npm plotly.js-dist-min](https://registry.npmjs.org/plotly.js-dist-min)
- three 0.186.1 (MIT), 2026-09-24; pixi.js 8.21.0 (MIT), 2026-09-17; echarts 6.1.0 (Apache-2.0), 2026-05-19; @kitware/vtk.js 37.3.1 (BSD-3), 2026-09-26 — [npm three](https://registry.npmjs.org/three); [npm pixi.js](https://registry.npmjs.org/pixi.js); [npm echarts](https://registry.npmjs.org/echarts); [npm vtk.js](https://registry.npmjs.org/@kitware/vtk.js)
- Commercial (flag): SciChart 6.0.1 (proprietary EULA) and LightningChart JS @arction/lcjs 5.2.1 ("SEE LICENSE") — [npm scichart](https://registry.npmjs.org/scichart); [npm @arction/lcjs](https://registry.npmjs.org/@arction/lcjs)
- JS FFTs: fft.js 4.0.4 (MIT, 2021), kissfft-js 0.1.8 (MIT, 2017), ml-fft (2016) — all stale — [npm fft.js](https://registry.npmjs.org/fft.js); [npm kissfft-js](https://registry.npmjs.org/kissfft-js)

**WebGPU notes**
- In WebGPU, GPUBuffers and GPUTextures hold most of the data; buffers act as staging for texture uploads — [Toji.dev WebGPU buffer uploads](https://toji.dev/webgpu-best-practices/buffer-uploads.html); [WebGPU fundamentals textures](https://webgpufundamentals.org/webgpu/lessons/webgpu-textures.html)
- `maxStorageBufferBindingSize` limits constrain very large single buffers in WebGPU — [Ayoob AI](https://ayoob.ai/blog/webgpu-maxstoragebufferbindingsize-limits-enterprise)

### Inferences (recommended design)
- **Spectrogram:** compute the STFT on the server (numpy/scipy, numba), store it as a multi-resolution pyramid (for example per level: decimate in time by max/mean over frames, optionally in frequency; quantize to uint8 dB after a colormap-independent normalization). Serve tiles (for example 256–1024 × 256 px) by `(level, t_tile, f_tile)` over HTTP (binary `application/octet-stream` or PNG). On the client, upload each tile as a single-channel `R8`/`R32F` WebGL2 texture and apply the colormap in a fragment shader via a 256×1 LUT texture, so contrast/colormap changes need no re-fetch. A deck.gl `TileLayer`+`BitmapLayer` in an orthographic view gives LOD/pan/zoom for free, and regl/raw WebGL2 is lighter if you want full control.
- **Live/stream waterfall:** use a ring-buffer texture (write one row per FFT frame with `texSubImage2D` and offset the UV y-coordinate in the shader), which avoids copying the whole texture each frame.
- **1-D plots (PSD, time, magnitude):** uPlot (MIT, very fast canvas2D) with server-side min/max decimation per pixel column.
- **Constellation:** for <~1e6 points, draw a regl/deck.gl `ScatterplotLayer` with additive blending (as a density effect). For large captures, compute a 2-D histogram (e.g. 512×512) server-side with `numpy.histogram2d` and render it as a log-scaled heat texture (same LUT shader as the spectrogram). Scales to any sample count and is air-gap friendly.
- Plotly WebGL (`scattergl`, `heatmap`) is fine for quick prototypes but heavy (~3+ MB) and slower for streaming/very large heatmaps. It's MIT, so there's no licence problem.
- IQEngine can be forked (MIT) or used as a design reference. Check its current dependency on Azure blob storage and client-side processing, and strip cloud bits for air-gapped use.
- Don't copy OpenWebRX/SDRangel web code (AGPL/GPL). Use them only for behaviour/UX reference.

### Gaps
- IQEngine's exact spectrogram rendering technique (canvas2D vs WebGL) and last release date weren't confirmed (GitHub API blocked; README excerpt silent).
- SDRangel web (GPL-3 per general knowledge, not verified this session), WebSDR (closed-source) and the "Pinpoint" approach weren't researched in depth. No reliable source was retrieved.
- No public benchmark was found comparing WebGL vs WebGPU spectrogram tile throughput.

## Q4. Offline packaging (FastAPI + SPA) and Windows gotchas

### Takeaway
All mainstream options are current as of Sept 2026. PyInstaller (GPL with bootloader exception, so shipping a proprietary app is OK), Nuitka (**AGPL-3.0 compiler**; its output isn't AGPL-bound per Nuitka's own terms, but verify), Briefcase, conda-pack (BSD) and pywebview (BSD). Tauri (Apache/MIT) and Electron (MIT) wrappers are current too. The simplest robust path is a wheelhouse or PyInstaller one-folder backend that serves the built SPA as static files, optionally wrapped in pywebview or Tauri.

### Cited Findings
- PyInstaller 6.22.3, 2026-09-12, "GPLv2-or-later with a special exception", Python 3.8–<3.16, Windows wheels — [PyPI pyinstaller JSON](https://pypi.org/pypi/pyinstaller/json)
- Nuitka 4.2.2, 2026-09-22, licence metadata "GNU Affero General Public License v3" — [PyPI nuitka JSON](https://pypi.org/pypi/nuitka/json)
- Briefcase 0.4.5, 2026-09-08, BSD-3-Clause, Python >=3.11 — [PyPI briefcase JSON](https://pypi.org/pypi/briefcase/json)
- conda-pack 0.9.2, 2026-06-16, BSD-3-Clause — [PyPI conda-pack JSON](https://pypi.org/pypi/conda-pack/json)
- pywebview 6.2.1, 2026-04-15, BSD-3-Clause — [PyPI pywebview JSON](https://pypi.org/pypi/pywebview/json)
- @tauri-apps/api 2.12.0 (Apache-2.0 OR MIT), 2026-09-26; electron 44.4.5 (MIT), 2026-09-23 — [npm @tauri-apps/api](https://registry.npmjs.org/@tauri-apps/api); [npm electron](https://registry.npmjs.org/electron)
- numba/llvmlite freezing issues with PyInstaller (missing `numba.core.*` modules; WinError 126 DLL load) — [pyinstaller #8989](https://github.com/pyinstaller/pyinstaller/issues/8989); [pyinstaller #2180](https://github.com/pyinstaller/pyinstaller/issues/2180)

### Inferences
- Recommended: (1) **Dev/air-gapped install:** `pip download -d wheelhouse -r requirements.txt --platform win_amd64 --python-version 3.12 --only-binary=:all:` (plus a manylinux run), then `pip install --no-index --find-links wheelhouse`. (2) **End-user bundle:** PyInstaller `--onedir` (not onefile: faster startup, fewer AV false positives, numba cache friendlier) with FastAPI+uvicorn serving `dist/` of the Vite build via `StaticFiles`, bound to 127.0.0.1. (3) Optional desktop shell: pywebview (small, uses Edge WebView2 on Windows) or a Tauri sidecar. Electron adds ~100+ MB.
- Windows gotchas (general engineering knowledge, not source-verified this session): WebView2 runtime may be missing on older/air-gapped Windows 10, so bundle the fixed-version runtime; MSVC runtime DLLs (vcruntime140) must be present; long paths (>260 chars) in deep wheel trees; Defender false positives on onefile PyInstaller; uvicorn `--reload`/multiprocessing needs `multiprocessing.freeze_support()` in frozen apps; use `NUMBA_CACHE_DIR` in a writable directory.
- conda-pack is a good alternative if you use conda-forge builds (e.g., SoapySDR, GNU Radio), but it roughly doubles package size.

### Gaps
- Nuitka's licence exception wording for compiled output wasn't retrieved. Verify on nuitka.net before choosing it.
- No source retrieved on WebView2 offline installer requirements or the MSVC runtime for ONNX Runtime (the PyPI page says nothing about it).

## Q5. Protocol decoders reusable offline as validation ground truth

### Takeaway
All major decoders accept recorded files and have usable machine-readable output, but almost all are **GPL** (rtl_433 GPL-2.0, multimon-ng GPL-2.0, readsb GPL-3.0, AIS-catcher GPL-3.0, SatDump GPL-3.0). The exception is redsea (MIT). Run them as separate executables (subprocess, arm's length) in a test/validation harness, not linked into the product, to avoid licence contamination.

### Cited Findings
- **rtl_433**: GPL-2.0; `-r` reads saved files in cu8, cs16, cf32 and am.s16; `-F json` output; portable C99, builds on Linux, FreeBSD, macOS, Windows; year.month versioning — [GitHub merbanan/rtl_433](https://github.com/merbanan/rtl_433)
- **readsb** (ADS-B, dump1090 fork): GPL-3.0; file input via `--device-type ifile --ifile=<path>` with UC8, SC16, SC16Q11 formats; outputs JSON, Beast, SBS/BaseStation, raw, VRS JSON, Prometheus; Linux/macOS focus, Windows not mentioned; README warns "expect bugs, segfaults" — [GitHub wiedehopf/readsb](https://github.com/wiedehopf/readsb)
- **AIS-catcher**: GPL-3.0; outputs NMEA (screen/UDP/HTTP/TCP) and JSON; file input documented for raw files and WAV files; has Windows installation docs; docs copyright 2021–2026 — [GitHub AIS-catcher](https://github.com/jvde-github/AIS-catcher); [AIS-catcher docs](https://jvde-github.github.io/AIS-catcher-docs/)
- **multimon-ng**: GPL-2.0; input is raw 22050 Hz s16 (WAV via sox `-t raw`, stdin); decoders include POCSAG512/1200/2400, FLEX, DTMF, EAS, AFSK1200/2400, more; builds on Windows (MSYS2/MinGW, Cygwin, MSVC) — [GitHub multimon-ng](https://github.com/EliasOenal/multimon-ng)
- **SatDump** (NOAA APT/HRPT, Meteor LRPT, MetOp, etc.): GPL-3.0; CLI offline pipelines, e.g. `satdump pipeline metop_ahrpt baseband file.cs16 outdir --samplerate 6e6 --baseband_format cs16`; formats cs16, cf32, cs32, cs8, others; Windows installer/portable builds; GUI `satdump-ui.exe` and CLI `satdump.exe` — [GitHub SatDump](https://github.com/SatDump/SatDump)
- **redsea** (FM RDS): **MIT**; inputs: MPX PCM on stdin, WAV files (auto sample-rate), hex (.spy/.rds), raw via `-f`; newline-delimited JSON per RDS group (PI, PS, RadioText, PTY, TA/TP); Windows via Cygwin or MSYS2/MinGW — [GitHub windytan/redsea](https://github.com/windytan/redsea)
- **dump1090** (FlightAware fork) is the upstream of readsb; its licence (GPL-2.0) wasn't verified this session — [GitHub flightaware/dump1090](https://github.com/flightaware/dump1090)

### Inferences
- Validation harness design: generate/record IQ → run the decoder executable via `subprocess` with file input → parse JSON/NMEA → compare with the app's decoder output (message-level precision/recall, CRC pass rate). Keeping the GPL tools out of the shipped binary (test-only, or shipped as separate unmodified executables with source offers) avoids GPL obligations on the main app.
- Format conversion needed: rtl_433/readsb expect cu8/cs16 at specific rates (readsb: 2.4 MS/s typical), multimon-ng expects 22.05 kHz s16 audio (FM-demodulated), and redsea expects 171 kHz MPX (or WAV). The app should export these via a "resample + write raw" utility.
- On Windows, the easiest are rtl_433, AIS-catcher and SatDump (prebuilt binaries/installers). readsb needs WSL/MSYS2 (Windows unverified). redsea and multimon-ng need MSYS2 builds.

### Gaps
- Latest release versions/dates for these decoders weren't retrieved (GitHub API rate-limited; README pages didn't show them).
- AIS-catcher's exact raw-file sample formats and the CLI flag weren't confirmed (docs index only).
- dump1090 licence not directly verified.
