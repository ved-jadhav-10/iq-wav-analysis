# Blind Signal-Parameter Estimation and Wideband Multi-Signal Detection for Recorded IQ Files

Scope: CPU-only, offline, Python/NumPy/SciPy methods for (1) raw IQ format inference, (2) sample-rate inference, (3) symbol rate, (4) carrier/frequency offset, (5) SNR, (6) pulse shape/roll-off, (7) wideband detection and segmentation, including overlapping and frequency-hopping signals. Items under "Inferences" are engineering recommendations derived from the cited material plus standard DSP. They are not claims made by the sources.

## Q1. Blind symbol-rate estimation: which methods work best in practice, how accurate at low SNR and with RRC roll-off, and what open implementations exist?

### Takeaway
Second-order cyclostationary analysis is the most practical baseline. Symbol rate shows up as a cycle frequency alpha = Rs. Use a blind all-alpha estimator (SSCA or FAM) or, more cheaply, the FFT of |x|^2 (envelope/squaring spectral line), then refine with a fine cyclic-autocorrelation search. The main weakness is small roll-off: the symbol-rate feature strength scales with excess bandwidth and can disappear as beta approaches 0. That should be noted as a known failure mode.

### Cited Findings
- The autocorrelation of a linearly modulated sequence is periodic in time with period equal to the symbol period, which is the basis of cyclic-correlation symbol-rate estimators — [Cyclic correlation based symbol rate estimation (ResearchGate)](https://www.researchgate.net/publication/3840457_Cyclic_correlation_based_symbol_rate_estimation)
- Cyclic-correlation estimators "degrade for low SNRs and small roll-off factors and may totally fail when the roll-off factor approaches zero". They are also more robust to frequency offset and frequency-selective fading than matched-filter estimators, and simpler — [search summary of arXiv 2001.01692 / related literature](https://arxiv.org/pdf/2001.01692)
- ML approaches are more robust at low SNR but have a roll-off-dependent bias. Some autocorrelation/zero-crossing estimators are claimed to be insensitive to roll-off — [A Family of Blind Symbol Rate Estimators using Zero Crossing Detection (arXiv 2001.01692)](https://arxiv.org/pdf/2001.01692); [Blind symbol rate estimation using autocorrelation and zero crossing detection](https://www.researchgate.net/publication/261271634_Blind_symbol_rate_estimation_using_autocorrelation_and_zero_crossing_detection)
- Other published variants include Haar-wavelet plus cyclic correlation ([ResearchGate](https://www.researchgate.net/publication/251864759_Symbol_Rate_Estimation_Using_Cyclic_Correlation_and_Haar_Wavelet_Transform)), a band-pass-filter bank ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1051200420300439)), and joint symbol rate and CFO estimation for overlapped PCMA signals via cyclic correlations ([ResearchGate](https://www.researchgate.net/publication/349402147_Blind_Symbol_Rate_and_Frequency_Offset_Estimation_for_PCMA_Signals_via_Cyclic_Correlations))
- PySDR on symbol rate as a cycle frequency: for rectangular BPSK at 20 samples/symbol the cyclic feature is at alpha = 1/sps = 0.05 (normalized), with harmonics at integer multiples. Pulse-shaped (RC/RRC) signals give a "much cleaner" SCF with a single spike, and the spike broadens in frequency as beta rises from 0.3 to 0.6 to 0.9 — [PySDR ch. 22 Cyclostationary Processing](https://pysdr.org/content/cyclostationary.html)
- PySDR estimator trade-offs:
  - The direct CAF is expensive for fine alpha grids.
  - FSM uses one large FFT but needs many convolutions.
  - TSM uses many smaller FFTs.
  - FAM computes all cycle frequencies at once through a two-stage FFT. Its parameters are Np (channels, a power of 2, typically 512), L <= Np/4 (hop), and P (number of windows, a power of 2).
  - FSM and TSM need at least about 2/alpha_resolution samples.
  - Source: [PySDR](https://pysdr.org/content/cyclostationary.html)
- SSCA and FAM are the blind all-cycle-frequency estimators, from Gardner, Brown, Loomis and Roberts. SSCA finds the symbol-rate cycle frequency without prior knowledge, and the symbol interval is its inverse — [cyclostationary.blog Parameter Estimation tag](https://cyclostationary.blog/tag/parameter-estimation/)
- Chad Spooner (CSP blog) says time-smoothing implementations work well only when the searched alpha matches the true cycle frequency. For blind all-alpha estimation he recommends SSCA or FAM for computational reasons — [CSP Blog community spotlight](https://cyclostationary.blog/2022/11/17/csp-community-spotlight-a-publicly-available-python-based-scf-estimator/)
- Oerder–Meyr "digital filter and square" timing recovery (IEEE Trans. Commun. 36(5):605–612, 1988):
  - It is a feedforward, blind (non-data-aided) method that is insensitive to frequency offset.
  - It typically needs about 4x oversampling.
  - It is essentially the spectral line of |x|^2 at the symbol rate.
  - Source: [Optica OE performance analysis of blind timing estimators](https://opg.optica.org/oe/fulltext.cfm?uri=oe-22-6-6749&id=281906)
- Open implementations:
  - **libcsp.py** (Mike Markowski, AB3AP): blind SSCA/FAM to find the 500 strongest cycle frequencies, then TSM/FSM on the top 5, plus spectral coherence. Depends on numpy, scipy and matplotlib. [udel.edu/~mm/csp](https://udel.edu/~mm/csp/), [github.com/ab3ap/libcsp](https://github.com/ab3ap/libcsp). No licence was visible on either page (see Gaps).
  - **fchirono/cyclostationarity_analysis**: TSM-style SCF and coherence, with a known coherence-denominator bug reported on the CSP blog. [GitHub](https://github.com/fchirono/cyclostationarity_analysis), [CSP blog](https://cyclostationary.blog/2022/11/17/csp-community-spotlight-a-publicly-available-python-based-scf-estimator/)
  - **phwl/cyclostationary**: FAM SCD estimator. [GitHub](https://github.com/phwl/cyclostationary)
  - **SSTGroup/Cyclostationary-Signal-Processing**: cyclostationarity detection. [GitHub](https://github.com/SSTGroup/Cyclostationary-Signal-Processing)
  - **CycloTorch**: GPU-accelerated SSCA and others, aimed at rotating-machinery diagnostics. [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2352711026001901)
  - PySDR's in-page NumPy code for direct CAF, FSM, TSM and FAM. [PySDR](https://pysdr.org/content/cyclostationary.html)
  - Both FAM and SSCA have been ported to AMD Versal hardware, which confirms these are the standard estimators. [arXiv 2506.18003](https://arxiv.org/pdf/2506.18003)
- Symbol rate and number of subcarriers for OFDM at low SNR: [arXiv 2207.13385](https://arxiv.org/pdf/2207.13385)

### Inferences
- A practical pipeline, in order:
  1. Channelize the detected signal to baseband and decimate to about 4–8x its occupied bandwidth.
  2. Compute P(alpha) = |FFT(|x|^2 − mean)|. Also compute |FFT(x^2)| for BPSK/OQPSK-like signals, and x^4 for QPSK.
  3. Find the strongest non-DC peak in the plausible range alpha ∈ [0.3·BW, 1.0·BW]. An RRC signal has BW ≈ Rs(1+beta), so Rs ∈ [BW/2, BW].
  4. Refine with a zoom-FFT or Goertzel/golden-section search on |mean(|x|^2·e^{-j2πα n})| around the peak.
  5. Confirm with a libcsp/PySDR FAM or SSCA pass on a short segment.
  6. Validate by checking that the PSD −3 dB bandwidth is ≈ Rs.
- This takes seconds on a CPU for about 1e6 samples. FAM with Np=256–512 on about 1e5–1e6 samples is also feasible on a CPU if the output is max-pooled, as PySDR notes.
- For beta < ~0.1, fall back to the PSD-bandwidth estimate (Rs ≈ occupied BW) and label the confidence as low.
- FSK signals do not produce a clean |x|^2 line because the envelope is constant. Use the instantaneous-frequency signal, then an FFT of its derivative or of the squared IF, to find the symbol rate. The CSP blog has a dedicated post: [Cyclostationarity of FSK signals](https://cyclostationary.blog/2023/04/25/cyclostationarity-of-frequency-shift-keyed-signals/).
- Low-SNR accuracy: the spectral-line SNR grows with observation length N, so integrate over the whole recording for each detected signal. For hopping or bursty signals, estimate per burst and take the median.

### Gaps
- I found no source with a quantitative head-to-head comparison (RMSE versus SNR) of SSCA, FAM, the squaring line, Oerder–Meyr and wavelet methods across roll-off values. The numbers would have to come from our own simulation.
- Licences for libcsp, fchirono/cyclostationarity_analysis, phwl/cyclostationary and SSTGroup were not visible in the fetched pages. Check each repo's LICENSE file before copying code. Writing our own FAM/SSCA from PySDR's description is safer.

## Q2. How can a raw file's format be inferred statistically (int8/uint8/int16/float32, endianness, I/Q vs Q/I, interleaved vs planar, header), and do any tools already do this?

### Takeaway
None of the common tools that were checked (URH, PySDR guidance, the K3XEC article) does fully automatic format inference. They rely on file extensions (.cu8, .cs8, .cs16, .cf32) or SigMF metadata. We need to build a scoring heuristic ourselves: decode the bytes under each candidate hypothesis and score how physically plausible the resulting IQ stream is.

### Cited Findings
- URH picks the format from the extension: .complex16u (two uint8) and .complex16s (two int8). It also accepts uncompressed PCM WAV and has a CSV import wizard — [URH user guide](https://www.oldergeeks.com/downloads/files/userguide.pdf); [URH GitHub](https://github.com/jopohl/urh)
- Native device formats:
  - RTL-SDR: interleaved uint8, where (v − 127.5)/127.5 maps to ±1.
  - HackRF: interleaved int8, divide by 127.
  - PlutoSDR: int16 with 12-bit LSB-aligned samples.
  - float32 pairs (complex64) have range ±1.0.
  - The article gives no detection heuristics and does not cover endianness.
  - Source: [K3XEC Processing IQ data formats](https://k3xec.com/packrat-processing-iq/)
- The SigMF datatype strings are cf32_le, ci16_le, cu8 and so on, and _le/_be encodes endianness. SDR files are typically little-endian and interleaved IQIQ. Headerless binary files carry no metadata, so datatype, sample rate and center frequency must be tracked externally — [PySDR IQ Files & SigMF](https://pysdr.org/content/iq_files)
- A 12-bit ADC does not justify complex128. int16 is the preferred storage format, at 4 bytes per IQ sample — [PySDR IQ Files](https://pysdr.org/content/iq_files)

### Inferences
Recommended heuristic battery. Each check is cheap on a 1–4 MB chunk from the middle of the file.

1. **Header and container sniffing:**
   - Check magic bytes: `RIFF....WAVE` (read the fmt chunk: channels=2 means I/Q; bits 8/16/24/32 and format tag 1=PCM or 3=float), `.sigmf-meta` JSON next to the file, and the HDF5/`.mat` magic numbers.
   - Look for a leading ASCII/zero-padding region: compare the byte entropy of the first 512–4096 bytes with the rest of the file.
   - As a generic check, compute rolling byte entropy and flag an initial low-entropy or ASCII-heavy block as a header, then trim it and align to the sample size.
2. **Width and type candidates:** try uint8, int8, int16 LE/BE, int32 LE/BE, float32 LE/BE, float64 LE, and float16 if needed. Features for each:
   - **float32 validity:** fraction of NaN/Inf/denormal values and of |v| > 1e6 values. For the correct type this should be about 0%. Reading int16 data as float32 produces many denormals or huge exponents.
   - **uint8 vs int8:**
     - A uint8 histogram of RTL-SDR data is centered near 127.5.
     - The same bytes read as int8 have a bimodal histogram piled near ±128.
     - int8 data read as int8 is unimodal and centered at 0.
     - Test: the mean of the uint8 interpretation is ≈127, and the kurtosis of the int8 interpretation is anomalous.
   - **Endianness for 16/32-bit:**
     - Under the correct byte order, sample-to-sample differences are small relative to the value range (the signal is oversampled and smooth), and the high byte has low entropy compared with the low byte.
     - Score each order by lag-1 autocorrelation |ρ1| of the real stream, or by spectral flatness: wrong endianness gives an almost white spectrum.
     - For int16 holding 12-bit data, the correct order shows the top 4 bits mostly as sign extension, or the bottom 4 bits zero if MSB-aligned.
   - **Interleaved vs planar:** interleaved data has high cross-correlation between even and odd samples (I and Q of the same instant) and an lag-1 structure. Planar data (all I, then all Q) shows a statistic change at the file midpoint, and the first and second halves correlate strongly when aligned.
   - **I/Q vs Q/I:**
     - Swapping I and Q conjugates the signal, which mirrors the spectrum. The data alone cannot decide this.
     - Use asymmetric priors: a known pilot or carrier on a known side, the DC-spike position, or an LSB/USB voice convention. Otherwise report it as ambiguous and offer a toggle.
     - Consistency check: if CFO estimates are negative for every signal of a known standard (e.g. FM broadcast), flip.
   - **Real-only vs complex:** if the Q channel is uncorrelated or identically zero, or the spectrum is Hermitian-symmetric when read as complex, the recording is real (e.g. mono audio-rate WAV).
3. **Combined score:** for each hypothesis, compute the decoded complex stream and score it by:
   - (a) validity (no NaN/Inf, sane dynamic range),
   - (b) spectral non-whiteness (1 − spectral flatness of the Welch PSD),
   - (c) lag-1 autocorrelation magnitude,
   - (d) I/Q power balance (the correct pairing gives near-equal I and Q variance and near-zero I–Q correlation for most signals),
   - (e) a clean-DC criterion.
   
   Pick the argmax and report the runner-up margin as a confidence value. This is a sound, easy-to-explain approach for judges.

### Gaps
- I found no published or open-source tool that automatically infers raw IQ datatype and endianness. URH, inspectrum and SDRangel appear to need the user to choose, or rely on extensions/SigMF. inspectrum and SDRangel were not verified directly in this session: inspectrum's documented approach is extension-based (.cu8/.cs8/.cs16/.cf32), per my background knowledge, which should be re-checked. "iqscan" was not found.
- There was no source for the accuracy of the statistical heuristics above. They need validating on our own synthetic corpus: generate all format permutations and measure the confusion matrix.

## Q3. How can the sample rate be inferred for headerless files from standard SDR rates and signal structure?

### Takeaway
The sample rate is not identifiable from the samples alone. Estimates only give ratios to it (normalized frequencies). A practical design combines (a) metadata/filename parsing, (b) snapping to a list of candidate standard device rates, and (c) structure-based validation: when a known standard is recognized, its known symbol rate, channel spacing or carrier spacing implies Fs. Otherwise output everything in normalized units plus a ranked candidate list.

### Cited Findings
- RTL-SDR supports 2.048, 2.56 and 3.2 MS/s among others, with a maximum of 3.2 MS/s. Many applications cap it at 2.4 MS/s, and the minimum USB rate is about 240 kS/s — [RTLSDR-Airband wiki](https://github.com/szpajder/RTLSDR-Airband/wiki/Tweaking-sampling-rate-and-FFT-size); [rtl-sdr.com](https://www.rtl-sdr.com/sdruno-updated-to-v1-1-now-supports-up-to-2-4-msps-for-the-rtl-sdr/); [vhs-decode wiki](https://github.com/oyvindln/vhs-decode/wiki/RTLSDR)
- HackRF One: up to 20 MS/s with 8-bit I/Q. At least 8 MS/s is recommended, and baseband-filter-related rates include 1.75, 2.5, 3.5, 5, 5.5, 6, 7, 8, 9, 10, 12, 14, 15 and 20 MHz — [HackRF docs: Sampling rate](https://hackrf.readthedocs.io/en/latest/sampling_rate.html); [HackRF One docs](https://hackrf.readthedocs.io/en/latest/hackrf_one.html)
- Headerless files carry no sample-rate information. SigMF exists to solve this — [PySDR](https://pysdr.org/content/iq_files)

### Inferences
- Candidate list:
  - RTL-SDR: 0.25, 0.9–1.024, 1.2, 1.4, 1.8, 1.92, 2.048, 2.4, 2.56, 2.88, 3.2 MS/s.
  - HackRF: the cited list, plus 2, 4, 8, 10, 16 and 20 MS/s.
  - PlutoSDR/USRP: common 1, 2, 5, 10, 20, 30.72, 61.44 MS/s.
  - LTE-related: 1.92, 3.84, 7.68, 15.36, 30.72 MS/s.
  - Audio-rate WAV IQ (SDR# and HDSDR baseband WAV): 48, 96, 192 kS/s.
  
  These are general knowledge; confirm per device.
- Also parse numbers in the filename such as `2400000`, `2.4M`, `_fs=`, `sr=`, `_2048k_` (gqrx/SDR# names include the rate and center frequency), plus the WAV header rate and any `auxi` chunk (SDR#/HDSDR store center frequency there).
- Structural validation:
  - If an FM broadcast signal appears, the ~200 kHz channel spacing and ±75 kHz deviation give Fs.
  - If a recognized symbol rate (e.g. GSM 270.833 kbaud, a common 9600 or 4800 baud for narrowband FSK, DVB-S rates) matches the estimated normalized Rs × Fs_candidate within about 0.1%, that candidate wins.
  - The anti-aliasing filter roll-off at the band edges (the PSD shape near ±Fs/2) is device-specific and can serve as a weak feature.
- File size and duration: if the user knows the duration, Fs = N/duration.

### Gaps
- I found no published algorithm that infers an absolute sample rate blindly. The sources did not verify SDR# and gqrx filename conventions; that is background knowledge.

## Q4. How should carrier frequency and frequency offset be estimated?

### Takeaway
Use a coarse-to-fine approach. Take the coarse center from the PSD centroid or band midpoint of the detected segment. Refine with the M-th power spectral line for PSK/QAM (x^2 for BPSK, x^4 for QPSK/QAM) or with cyclic features (the conjugate SCF at alpha = 2fc for BPSK). Use instantaneous-frequency averaging for FSK/FM.

### Cited Findings
- Second-order cyclostationary features give blind joint carrier and symbol-rate estimation, as applied to underwater acoustic communication — [IEEE Xplore 6364536](https://ieeexplore.ieee.org/document/6364536/)
- Joint blind symbol-rate and CFO estimation for overlapped PCMA signals via cyclic correlations — [ResearchGate 349402147](https://www.researchgate.net/publication/349402147_Blind_Symbol_Rate_and_Frequency_Offset_Estimation_for_PCMA_Signals_via_Cyclic_Correlations)
- CFO and timing estimation for CCSDS high-rate telemetry receivers (a practical survey of feedforward estimators) — [PMC8122673](https://pmc.ncbi.nlm.nih.gov/articles/PMC8122673/)

### Inferences
- Per detected signal:
  1. Coarse fc = power-weighted centroid of the PSD within the −10 dB band.
  2. For PSK, y = x^M. The peak of |FFT(y)| is at M·Δf, so Δf = peak/M. The unambiguous range is Fs/(2M). Zero-pad and use parabolic interpolation to get sub-bin accuracy.
  3. For FSK/FM, take the mean of the instantaneous frequency (np.angle(x[1:]·conj(x[:-1]))·Fs/2π) over the burst.
  4. For OFDM, use CP-correlation phase (the van de Beek approach; background knowledge).
- The M-th power detects the modulation order as a by-product: whichever M gives a strong line hints at BPSK (M=2), QPSK (M=4) or 8PSK (M=8).

### Gaps
- No quantitative low-SNR accuracy numbers were collected for the M-th-power estimator in this session.

## Q5. Which SNR estimators work at low SNR (M2M4, eigenvalue/MDL-based, EVM-based)?

### Takeaway
For a spectrum tool, the most robust blind SNR is a spectral estimate: in-band PSD power versus the noise floor estimated from out-of-band bins (median or noise-floor percentile), corrected for bandwidth. Moment-based M2M4 suits constant-modulus PSK. Eigenvalue/MDL estimators need no modulation knowledge but overestimate the signal subspace at low SNR. EVM needs synchronization and decisions and becomes biased at low SNR.

### Cited Findings
- M2M4 uses the 2nd and 4th moments. It is blind, low-complexity and phase-insensitive, but only strictly valid for MPSK (constant modulus). It tracks error-counting BER better than EVM at lower SNR — [PMC8347679 (Sensors, M2M4 asymptotic efficiency)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8347679/); [search summary incl. arXiv 2605.26063](https://arxiv.org/abs/2605.26063)
- Covariance-matrix eigenvalue SNR estimation uses MDL to split signal and noise eigenvalues. At low SNR the signal-subspace dimension is easily overestimated — [Samples Covariance Matrix Eigenvalues Based Blind SNR Estimation (ResearchGate)](https://www.researchgate.net/publication/270897440_Samples_Covariance_Matrix_Eigenvalues_Based_Blind_SNR_Estimation); [search summary](https://arxiv.org/pdf/2605.12086)
- Other recent work covers low-complexity blind SNR for mmWave multi-antenna systems ([arXiv 2605.12086](https://arxiv.org/pdf/2605.12086)) and deep-learning SNR estimation ([MDPI Electronics 8(10):1139](https://www.mdpi.com/2079-9292/8/10/1139))

### Inferences
- Implement three estimators and report them all, with agreement as a confidence measure:
  - **(a) PSD method:**
    - N0 = median PSD in a guard region next to the signal band (or the global noise floor via a percentile/minimum-statistics estimate).
    - S = Σ(PSD_in_band − N0)·Δf.
    - SNR = S/(N0·B), where B is the occupied bandwidth or Rs. Also report C/N0 in dB-Hz.
    - This works down to roughly −5 to −10 dB in-band given long integration.
  - **(b) M2M4:** SNR = sqrt(2·M2² − M4)/(M2 − sqrt(2·M2² − M4)) for complex constant-modulus signals. Apply it after channelization, matched filtering and decimation to 1 sps if possible.
  - **(c) Eigenvalue/MDL:** Hankel/covariance matrix with window L≈32–64, eigen-decomposition, then MDL for the number of signal eigenvalues. Noise = mean of the noise eigenvalues. Useful for SNR and as a "how many components" hint.
- Present EVM only after successful demodulation.

### Gaps
- There were no side-by-side bias/RMSE figures for these estimators under a common setup. We would need to simulate them ourselves.

## Q6. How can pulse shape and roll-off be estimated?

### Takeaway
After estimating Rs, fit the theoretical RRC/RC PSD, parameterized by (Rs, beta, fc, amplitude, noise floor), to the measured Welch PSD by least squares (scipy.optimize.least_squares). Alternatively, use the cyclic feature: its width and strength are proportional to beta. Both are cheap on a CPU.

### Cited Findings
- One published method: take the IFFT of the preprocessed power spectrum to get the magnitude of the raised-cosine pulse, then estimate beta from the ratio of the second peak to the main peak. It estimates symbol rate jointly — [Blind Roll-off Factor and Symbol Rate Estimation using IFFT and Least Squares (ResearchGate)](https://www.researchgate.net/publication/224288947_Blind_Roll-off_Factor_and_Symbol_Rate_Estimation_using_IFFT_and_Least_Squares_Estimator)
- Other methods fit the theoretical PSD or power to the empirical one — [Blind roll-off estimation for digital transmissions (Signal Processing, ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0165168416303553). See also [ACM ITCC 2023](https://dl.acm.org/doi/10.1145/3606843.3606846) and PCMA roll-off/noise estimation in [IEEE 10930489](https://ieeexplore.ieee.org/document/10930489/)
- Accurate roll-off helps spectrum supervision (checking the authorized roll-off), ISI mitigation and bandwidth estimation — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0165168416303553)
- In the SCF, RRC pulses produce a clean single cycle-frequency spike, while rectangular pulses give strong harmonics — [PySDR](https://pysdr.org/content/cyclostationary.html)

### Inferences
- Pulse-shape classification heuristic:
  - Strong cyclic harmonics at 2Rs and 3Rs plus sinc sidelobes in the PSD mean rectangular (NRZ) pulses.
  - A single Rs line plus a flat-top PSD with cosine skirts means RC/RRC.
  - A Gaussian PSD shape (for GFSK/GMSK) suggests fitting a Gaussian BT.
- Report beta ∈ {0.2, 0.25, 0.35, 0.5} snapped to common standard values, plus the raw fit and its residual.

### Gaps
- I found no open-source Python implementation of blind roll-off estimation. It has to be implemented from the papers, which is simple.

## Q7. Wideband detection and segmentation: CFAR, spectrogram detectors, deep-learning detectors, frequency hopping, and co-channel separation. What is realistic in a hackathon?

### Takeaway
The realistic CPU approach is a classical pipeline:
1. STFT spectrogram.
2. Noise-floor estimation (median/percentile per frequency bin).
3. 2-D CA/OS-CFAR or threshold on SNR.
4. Morphological cleanup.
5. Connected-component labeling (scipy.ndimage.label) to get time–frequency boxes.
6. Merge and split per box.
7. Per-box channelization and parameter estimation.

Frequency hopping becomes a clustering/tracking step over the boxes. An optional ML detector (TorchSig's MIT-licensed YOLO models, as used in gr-spectrumdetect) can run on a CPU for single spectrogram images. True co-channel separation is research-grade. Detect overlap (via cyclic features at distinct alphas, or MDL source count) instead of attempting separation, except for simple SIC on a strong constant-envelope or known-modulation signal.

### Cited Findings
- Energy detection needs little prior knowledge and has low complexity, but performs poorly at low SNR. STFT-based PSD-vs-time representations are standard for wideband sensing, and CNNs on spectrograms can outperform thresholding — [RF ROI CNN for wideband spectrum sensing (PMC10383786)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10383786/)
- Morphological operations with thresholding on the power spectrum give approximately CFAR behavior in colored noise — [MATEC 2021 wideband signal detection/extraction](https://www.matec-conferences.org/articles/matecconf/pdf/2021/05/matecconf_cscns20_04011.pdf)
- Cell-averaging CFAR used for real-time wideband spectrum sensing on low-cost SDRs (edge FPGA forwarding only signal-containing intervals) — [Sensors 2026, Edge CA-CFAR (PMC13417223)](https://pmc.ncbi.nlm.nih.gov/articles/PMC13417223/)
- **TorchSig** is MIT-licensed and needs a CPU with ≥4 cores (from its prerequisites) — [TorchSig GitHub](https://github.com/TorchDSP/torchsig)
- **gr-spectrumdetect**:
  - MIT licence.
  - GNU Radio out-of-tree block using a YOLO11-S model (single-class, detection only) trained on 1024×1024 grayscale spectrograms from TorchSig Wideband v0.6.1 with level-2 impairments.
  - Earlier versions used a YOLOv8x detect.pt. A spectrumPlot block labels detections.
  - Sources: [gr-spectrumdetect GitHub](https://github.com/TorchDSP/gr-spectrumdetect); [TorchSig GRCon2024 paper](https://events.gnuradio.org/event/24/contributions/628/attachments/190/473/TorchSig_GRCon2024_paper.pdf)
- TorchSig provides pretrained models: YOLO (Ultralytics) detection on spectrograms, then XCiT modulation recognition — [GRCon2024 talk](https://events.gnuradio.org/event/24/contributions/628/attachments/190/503/TorchSig_GRCon2024_talk.pdf); TorchSig 2.0 (custom datasets, new transforms) — [GRCon2025](https://events.gnuradio.org/event/26/contributions/752/attachments/220/586/TorchSig_GRCon2025.pdf); newer [agentic-spectrumdetect](https://github.com/TorchDSP/agentic-spectrumdetect)
- The WidebandSig53 dataset and YOLO-style detection with recognition over large-scale wideband spectrograms are described in [arXiv 2211.10335](https://ar5iv.labs.arxiv.org/html/2211.10335). Narrowband-in-broadband YOLO variant: [DFN-YOLO (PMC12252476)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12252476/)
- Frequency-hopping (FH) methods:
  - Spectrogram/time-frequency distributions with integration along parametric paths ([academia.edu](https://www.academia.edu/61854090/Parameter_estimation_of_spread_spectrum_frequency-hopping_signals_using_time_frequency_distributions)).
  - Wavelet hop-instant detection ([ResearchGate](https://www.researchgate.net/publication/261488394_Detection_and_estimation_of_frequency_hopping_signals_using_wavelet_transform)).
  - Piecewise-constant frequency models tracked with dynamic programming ([ResearchGate](https://www.researchgate.net/publication/260673596_Hopping_instants_detection_and_frequency_tracking_of_frequency_hopping_signals_with_single_or_multiple_channels)).
  - Compressed-domain atomic dictionaries ([PMC10255862](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10255862/)).
  - DTIC classic report ([ADA339336](https://apps.dtic.mil/sti/tr/pdf/ADA339336.pdf)).
  - Hop parameters of interest: hop time, hop frequency, dwell.
- Co-channel/PCMA (paired carrier multiple access) overlapped signals have dedicated blind estimators using cyclic correlations: symbol rate, CFO, roll-off and noise power — [ResearchGate 349402147](https://www.researchgate.net/publication/349402147_Blind_Symbol_Rate_and_Frequency_Offset_Estimation_for_PCMA_Signals_via_Cyclic_Correlations); [IEEE 10930489](https://ieeexplore.ieee.org/document/10930489/)
- Blind SINR estimation under non-cooperative interference using eigenvalue and steering-vector decoupling needs multiple antennas — [Electronics 15(14):3074](https://doi.org/10.3390/electronics15143074)

### Inferences
- **Classical detector recipe:**
  - STFT with nfft 1024–4096, 50–75% overlap, Hann/Blackman-Harris window, in dB.
  - Noise-floor map: per-bin 20th-percentile over time (robust to bursts), or a 2-D median filter.
  - 2-D OS-CFAR with guard and training cells, e.g. scipy.ndimage.percentile_filter on a ring kernel, threshold at +6 to +10 dB.
  - Hysteresis thresholding (skimage.filters.apply_hysteresis_threshold, BSD) to connect faint edges.
  - Binary closing/opening, then scipy.ndimage.label, then boxes (t0, t1, f_lo, f_hi), with peak/mean SNR per box.
  - Merge boxes with the same frequency span and small time gaps to form one continuous or bursty emitter.
- **Multi-resolution:** run it at two or three FFT sizes. Small nfft catches short bursts and hops; large nfft catches narrowband signals at low SNR. Fuse the results with NMS.
- **Frequency-hopping tracking:**
  1. Cluster the box list with DBSCAN (sklearn, BSD) on (bandwidth, dwell duration, power, symbol-rate estimate).
  2. A cluster with many short boxes of equal bandwidth and dwell, at different center frequencies, that are time-contiguous or near-periodic is an FH emitter.
  3. Estimate hop rate = 1/median(dwell), the hop set (unique center frequencies) and the hop sequence.
  4. Optionally apply a DP/Viterbi track when several hoppers overlap.
- **Overlap/co-channel handling:**
  - (a) Detect: within a box, run FAM/SSCA or |x|^2 lines. Two distinct symbol-rate lines, or two M-th-power CFO lines, indicate two co-channel signals. The eigenvalue MDL source count > 1 is another indication.
  - (b) Separate only in easy cases:
    - Frequency-partial overlap: channel filters.
    - Power-disparate signals: SIC, meaning demodulate and remodulate the strong constant-modulus or PSK signal, then subtract.
    - Cyclostationary FRESH filtering is possible, but is advanced and should be treated as a stretch goal.
  - Single-channel BSS (ICA needs multiple channels) is not realistic for a hackathon from a single-antenna recording.
- **ML option:** the TorchSig/gr-spectrumdetect YOLO weights (MIT) could run on CPU via Ultralytics or ONNX Runtime on 1024×1024 images. CPU latency is unverified (probably sub-second to a few seconds for small models; see Gaps). The Ultralytics package itself is AGPL-3.0 (background knowledge, to verify), which matters for licensing. Exporting to ONNX and running with onnxruntime (MIT) avoids shipping Ultralytics code. The classical CFAR pipeline should stay the primary path, with ML as an optional cross-check.

### Gaps
- CPU inference latency for the TorchSig YOLO11-S / YOLOv8x detectors was not documented in the pages fetched.
- The Ultralytics licence (believed AGPL-3.0) and the licence of the pretrained weights were not verified in this session.
- RF-DETR applied to RF spectrograms: no sources found in this session.
- No open-source Python frequency-hopping tracker was found. Papers only.
- No quantitative Pd/Pfa comparison of CFAR variants versus YOLO on WidebandSig53 was collected.
