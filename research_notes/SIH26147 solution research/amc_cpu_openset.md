# Low-SNR, Open-Set, CPU-Deployable Automatic Modulation Classification (2022-2026)

Research date: 2026-09-27. About 20 tool calls. Several primary PDFs (e.g. arXiv 2607.24831, MDPI Electronics review 2079-9292/15/10/2163) could not be parsed or returned 403, so some numbers below come from comparison tables in third-party papers, not from the original model papers. This is noted where it applies.

## Q1. Lightweight architectures: accuracy vs parameter/FLOP trade-off

### Takeaway
Ultra-light complex-valued or 1D CNNs of about 9-11K parameters (ULCNN, LDCVNN) match or beat MCLDNN (about 406K parameters) on the RadioML datasets. Averaged over the full SNR range they reach about 60-62%, peaking at about 91-96%. Performance on RML2016 is capped mainly by the low-SNR bins and by AM-SSB/WBFM and QAM16/QAM64 confusion, not by model capacity. On HisarMod2019.1, every light model sits at about 44% average and about 50% peak. On Sig53 (4096-sample inputs, 53 classes) you need a 3-7M-parameter EfficientNet or XCiT to get about 63-71%.

### Cited Findings
- **RML2016.10a** (avg over SNR / peak, params, FLOPs per sample): LDCVNN 62.41% / 92.36%, 9.0K, 0.60 MFLOPs; ULCNN 60.58% / 91.19%, 9.4K, 0.82 MFLOPs; MCLDNN 60.83% / 90.77%, 405.8K, 48.7 MFLOPs; CSDNN 58.66% / 88.09%, 327.1K; CDSN 50.59% / 76.55%, 1.34M — [LDCVNN, Sensors 2025 (PMC12031408)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12031408/)
- **RML2016.10b**: LDCVNN 63.97% / 93.18% (9.0K); ULCNN 63.09% / 92.46% (9.3K); CSDNN 65.82% / 91.73% (315K) — [PMC12031408](https://pmc.ncbi.nlm.nih.gov/articles/PMC12031408/)
- **RML2018.01A**: LDCVNN 60.17% / 96.12%, 11.2K, 6.6 MFLOPs; ULCNN 58.55% / 92.57%, 9.9K, 6.7 MFLOPs; CSDNN 57.91% / 90.82%, 333.8K — [PMC12031408](https://pmc.ncbi.nlm.nih.gov/articles/PMC12031408/)
- **HisarMod2019.1**: LDCVNN 43.97% / 53.08% (11.3K); ULCNN 43.85% / 49.77% (9.9K); CSDNN 43.33% / 50.35% (334.8K) — [PMC12031408](https://pmc.ncbi.nlm.nih.gov/articles/PMC12031408/). Note: these HisarMod numbers are far below other reports, which cite over 90% at high SNR. The split or SNR range may differ, so do not treat them as canonical.
- Other reports put MCLDNN at about 91% peak on RML2016.10a, and one paper reports 0.6101 average — [Lightweight temporal hybrid NN, PMC11679410](https://pmc.ncbi.nlm.nih.gov/articles/PMC11679410/)
- **PET-CGDNN** (parameter-estimation-and-transformation front end plus CNN-GRU) "has obvious advantages in time cost compared with GRU2, LSTM2, and MCLDNN, while sacrificing little recognition accuracy". It learns a phase/frequency-offset correction before the classifier — [PMC11679410 summary](https://pmc.ncbi.nlm.nih.gov/articles/PMC11679410/); original paper [arXiv 2110.04980](https://arxiv.org/pdf/2110.04980)
- **MobileRaT** (a lightweight radio transformer with entropy-based iterative pruning and multimodal inputs): 65.9% average / 98.4% peak on RML2018.01A (MobileRaT-A), and 62.3% average / 99.2% peak on RML2016.10A (MobileRaT-B). The pruned models are 67% and 38% of the original size — [MobileRaT, Drones 2023 (ADS abstract)](https://ui.adsabs.harvard.edu/abs/2023Drone...7..596Z/abstract). Caveat: a 99.2% peak on 2016.10a is unusually high given that dataset's known AM-SSB/WBFM label issues, so treat it with scepticism.
- **Sig53** (4096 IQ samples, 53 classes): EfficientNet-B0 3.9M params 62.75%; B2 7.5M 65.18%; B4 17.2M 67.46% (69.73% with online training data); XCiT-Nano 3.1M 67.97%; XCiT-Tiny12 6.7M 70.22% (71.16% online). The paper reports no inference latency — [Boegner et al., Large Scale RF Signal Classification, arXiv 2207.09918](https://arxiv.org/html/2207.09918v1)
- The code and repository benchmark for 14 models (CNN1/2, MCNET, IC-AMCNet, ResNet, DenseNet, GRU, LSTM, DAE, MCLDNN, CLDNN, CLDNN2, CGDNet, PET-CGDNN) across RML2016.10a/b, 2018.01a and HisarMod2019.1 is in Keras/TF 1.14, with results shown as figures — [AMR-Benchmark (Zhang et al., DSP 2022)](https://github.com/Richardzhangxx/AMR-Benchmark)
- Other 2025-2026 lightweight entries exist: a dual-path deep residual shrinkage network ([arXiv 2507.04586](https://arxiv.org/pdf/2507.04586)), "green ML" AMC ([arXiv 2604.10317](https://arxiv.org/pdf/2604.10317)) and efficient AMC for next-gen networks ([arXiv 2607.24831](https://arxiv.org/pdf/2607.24831)). I could not extract their numbers.

### Inferences
- For a CPU-only tool, a roughly 10-100K-parameter 1D-CNN (ULCNN/LDCVNN style), optionally with a small GRU or a PET-style phase/frequency-offset estimation front end, is the sweet spot. FLOPs are about 1-7M per 128- or 1024-sample frame, so CPU latency should be well under 1 ms per frame. That is an estimate from FLOPs; none of the sources measured it.
- Expect about 60% SNR-averaged accuracy on the -20 to +18 dB grids and about 90-96% above roughly +6 dB. Below about -6 dB, accuracy approaches chance on all models. For the product, report accuracy as a function of SNR, not a single number.
- For longer inputs (1024-4096 samples) with many classes, as in Sig53, a small patch transformer (XCiT-Nano, about 3M) is feasible on CPU, but it costs 100x or more the FLOPs of ULCNN.
- Multimodal inputs help. MobileRaT and PET-CGDNN use IQ plus amplitude/phase or learned phase correction. The cheap option is stacking channels [I, Q, |x|, angle(x) unwrapped or diff] for a 1D CNN.

### Gaps
- I found no measured CPU latency (ms per inference) for ULCNN, LDCVNN, MCLDNN or PET-CGDNN in the sources I read.
- I could not extract the exact parameter count for PET-CGDNN from a primary source. It is reportedly about 70K, but this is unverified.
- LightAMC was not found in this pass.
- I did not find a papers-with-code style leaderboard maintained after 2023.

## Q2. Dataset flaws and domain gap to real over-the-air signals; augmentation strategies

### Takeaway
RadioML datasets have documented flaws: the SNR labels are off by tens of dB, AM-SSB in 2016.10a/b is pure noise, some low-SNR examples are noise-only, and the 2018.01A class-name mapping is wrong. Models trained on clean synthetic data can fall from about 95% to about 35% on real SDR captures. Training on impaired data (frequency/phase/timing offsets, fading, IQ imbalance, resampling) and on moderately distorted sources, plus unsupervised domain adaptation, recovers much of that loss.

### Cited Findings
- The RML "SNR" parameter "does not correspond to any definition I know… you'll be off by tens of dB". For RML2016.10b at SNR label 18, the measured in-band SNR was about 40 dB. At label 0 it ranged from about 15 dB (BPSK) to 29 dB (QAM64) — [Spooner, Cyclostationary Signal Processing blog](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/)
- AM-SSB in 2016.10a and 2016.10b is only noise — [Cyclostationary blog](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/)
- At SNR label -2, about half of the PSK/QAM examples look like signal-plus-noise and half like noise only. The noise floor varies by about 25 dB in RML-B, against about 5 dB expected — [Cyclostationary blog](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/)
- "The signal name to label mapping in the 2018.01A dataset does not match what they published in the paper." Users must correct it manually — [Cyclostationary blog](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/)
- **Synthetic to OTA gap** (USRP at 916 MHz; BPSK/QPSK/8APSK/16QAM; 2-22 dB): at 10 dB, a model at about 95.65% in-domain drops to about 34.55% on OTA. Unsupervised domain adaptation recovers it to STAR 87.20%, JAN 81.15%, MCD 78.15%, CORAL 61.47% and DANN 48.75% (at 18 dB, SNR-matched). The causes are "hardware imperfections, unmodeled fading, varying interference, and inaccurate synchronization". Moderately distorted source data transferred best — [Signal Classification Recovery Across Domains Using UDA, arXiv 2510.00589](https://arxiv.org/html/2510.00589)
- Sig53 impairments: AWGN, phase shift, time shift, frequency shift, Rayleigh fading, IQ imbalance and random resampling, with SNR from -2 to 30 dB defined as Es/N0 — [arXiv 2207.09918](https://arxiv.org/html/2207.09918v1)
- Recent OTA work covers CNN-LSTM on SDR captures ([arXiv 2511.21040](https://arxiv.org/html/2511.21040v2)), curriculum fine-tuned CNN-Transformers for sub-6 GHz OTA ([arXiv 2609.07726](https://arxiv.org/html/2609.07726)) and dataset synthesis by multi-domain distribution matching ([MDM, arXiv 2408.02714](https://arxiv.org/pdf/2408.02714))

### Inferences
- Do not rely on RadioML 2016 as the only training set. Drop or relabel AM-SSB, and do not use its SNR labels as ground truth for SNR-conditional reporting. Generate your own data (TorchSig, or a GNU Radio/NumPy generator) with a well-defined Es/N0.
- The augmentation recipe should include random carrier frequency offset (for example ±5-10% of Fs), random phase, fractional timing offset, sps jitter/resampling, Rayleigh/Rician multipath, IQ imbalance, DC offset, phase noise, random gain and AGC, and per-frame power normalisation. Also add noise-only and partial-burst frames as explicit "noise" training examples.
- If a few real SDR captures are available, fine-tune on them or use a CORAL/JAN-style adaptation step. CORAL is trivial to add in PyTorch.

### Gaps
- I did not fetch published quantitative ablations of individual augmentations (which impairment matters most).
- I did not verify HisarMod2019.1-specific flaws.

## Q3. TorchSig status and licences/availability of datasets

### Takeaway
TorchSig is MIT-licensed and was heavily restructured in v2.x. It targets Linux (Ubuntu 22.04 or later recommended) with Python 3.10 or later, and on Windows it is effectively WSL-only. Sig53/WidebandSig53 were renamed "Narrowband/Wideband" and must be generated locally, which requires a lot of storage. The DeepSig RadioML datasets are CC BY-NC-SA 4.0 (non-commercial). The Sig53 paper states CC BY 4.0. I could not confirm HisarMod's licence.

### Cited Findings
- TorchSig uses the MIT licence. The v2.0.0 release has major structural changes and a migration guide from v1.1.0, and a TorchSig-GUI beta was released — [TorchSig releases](https://github.com/TorchDSP/torchsig/releases)
- Release notes as returned by the fetch tool (dates may be unreliable; check on GitHub):
  - **v2.0.0**: moved from Zarr to HDF5 and reorganised transforms.
  - **v2.1.0**: removed built-in models, moved to a separate torchsig-models repository, and added NumPy 2 compatibility.
  - **v2.1.1**: first PyPI publication and removed the Rust dependency.
  - **v2.2.0**: added LoRa, GSM, 802.11a, Zigbee, BLE, ADS-B, DVB-S2 and other signals, plus Numba acceleration.
  - The notes also record "Sig53" → "Narrowband" and "WidebandSig53" → "Wideband", with 61 signals — [TorchSig releases](https://github.com/TorchDSP/torchsig/releases)
- README: "60+ signal types across all major modulation families (FSK, QAM, PSK, ASK, OFDM, Analog)". Ubuntu 22.04 or later is highly recommended, with WSL or Git Bash on Windows. Requirements are Python 3.10 or later, 4 or more CPU cores, a recommended GPU, and 1 TB of storage recommended. I found no mention of pre-generated dataset downloads — [TorchSig GitHub](https://github.com/TorchDSP/torchsig)
- Sig53 has 53 classes across ASK/PAM/PSK/QAM/FSK/OFDM, more than 6M examples in 4 sub-datasets, 4096 complex samples per example, and is licensed CC BY 4.0 — [arXiv 2207.09918](https://arxiv.org/html/2207.09918v1)
- DeepSig datasets are "licensed under the Creative Commons Attribution - NonCommercial - ShareAlike 4.0 License (CC BY-NC-SA 4.0)" — [sofwerx/deepsig_datasets](https://github.com/sofwerx/deepsig_datasets). Mirrors exist on [Kaggle (2018.01A)](https://www.kaggle.com/datasets/pinxau1000/radioml2018) and [IEEE DataPort (2016.10A/B/C)](https://ieee-dataport.org/documents/radioml201610a10b10c)
- HisarMod2019.1 has 780,000 signals in 26 classes from 5 families (analog, FSK, PAM, PSK, QAM) — [KristynaPijackova/Radio-Modulation-Recognition-Networks README](https://github.com/KristynaPijackova/Radio-Modulation-Recognition-Networks/blob/main/README.md)

### Inferences
- For a Windows-based offline tool, generate the data once under WSL/Linux, or write a small custom NumPy generator for PSK/QAM/FSK/AM/FM. The latter avoids the heavy TorchSig dependency and the NC licence issues.
- The RadioML NC licence matters if the tool or the trained weights will be used commercially.

### Gaps
- I did not confirm the exact latest TorchSig version number or date as of 2026; the fetched release list may be stale or misdated.
- The HisarMod licence was not found. The original IEEE DataPort or Hisar University page would need checking.

## Q4. Open-set recognition / OOD detection for AMC and evaluation

### Takeaway
The AMC open-set literature (called AMOSR) evaluates known-class accuracy, unknown rejection accuracy, AUROC, normalised accuracy, F-measure, and "openness"-controlled splits in which some modulations are held out. Reconstruction-based and prototype/metric methods beat plain softmax thresholding. OpenMax remains a strong baseline, and cheap per-class distance thresholding also works.

### Cited Findings
- AMOSR is framed as two tasks: Known Class Classification (KCC) and Unknown Class Identification (UCI). The core challenges are inappropriate decision boundaries and sparse feature distributions — [CIR, arXiv 2312.13023](https://arxiv.org/html/2312.13023v1)
- **CIR** (Restormer denoiser plus a class-conditional autoencoder, so known classes reconstruct well and unknowns badly, trained with a mutual-information loss). At -2 dB it reaches unknown-rejection accuracy (AUS) 0.8985 and NA 0.9626, against OpenMax 0.8922/0.9608, CROSR 0.8793/0.9556, CGDL 0.8389/0.9409 and RPL 0.8375/0.9396. At -6 dB, CIR AUS is 0.8836 against CGDL 0.8338. Metrics are AKS, AUS, AUROC, NA and F-measure, with openness = 1 − √(N/(N+Nu)) varied from 0.15 to 0.70. Note that this work uses radar waveforms (LFM, Costas, polyphase codes) on time-frequency images, not comms PSK/QAM — [arXiv 2312.13023](https://arxiv.org/html/2312.13023v1)
- **AMEE**: deep metric learning with embedding enhancement for AMOSR — [IEEE Xplore](https://ieeexplore.ieee.org/iel8/24/11317936/11278852.pdf)
- **FSOS-AMC**: few-shot open-set AMC over multipath fading. A per-class distance-thresholding approach rejects unknowns using intra-class proximity in logit space — [arXiv 2410.10265](https://arxiv.org/html/2410.10265v2)
- The energy score is a parameter-free OOD score computed from logits ([Liu et al., arXiv 2010.03759](https://arxiv.org/pdf/2010.03759)). One RF unknown-signal study reported AUROC 0.9715 and an unknown recognition rate of 0.8583 (from a search snippet; I did not identify the primary source).
- Underwater acoustic open-set modulation recognition in sea trials reached 64.1% known accuracy and 74.4% unknown rejection, which shows real-world numbers fall well below simulation — [JASA, Multi-Path ResNet](https://pubs.aip.org/asa/jasa/article-abstract/159/5/4129/3391280/Open-set-modulation-recognition-for-underwater)

### Inferences
- For the tool, use a layered rejection scheme:
  1. **Energy or SNR gate.** An estimated-SNR or energy-detector threshold labels frames as "noise" before classification. Better still, train an explicit "noise" class.
  2. **Energy score on the logits** (logsumexp at temperature T). This is free at inference.
  3. **Class-prototype distance.** Compute the Mahalanobis or cosine distance of the penultimate embedding to class means, with per-class thresholds set at, say, 95% TPR on validation data.
- Evaluate with held-out modulations (for example, train without 8PSK/GFSK/QAM256), reporting AUROC, FPR@95TPR, known-class accuracy and OSCR per SNR bin.
- Reconstruction-based methods (CIR) are heavier and need an autoencoder. They are a later option, not the MVP.
- At low SNR, unknowns and knowns become indistinguishable. Report open-set metrics per SNR, and treat low-confidence output at low SNR as "unknown/insufficient SNR".

### Gaps
- I found no source that benchmarks energy scores specifically against OpenMax on RadioML-style comms modulations; the CIR numbers are for radar waveforms.
- I did not find a standard open-set AMC benchmark split protocol.

## Q5. Calibration and hybrid DSP-feature + DL fusion

### Takeaway
Temperature scaling, a single scalar fitted on validation NLL, is the standard post-hoc fix for overconfidence and does not change the argmax. I found no AMC-specific calibration study. Cumulant and spectral features fused with CNN features are a well-established way to add robustness at low SNR, but higher-order cumulants discriminate poorly between high-order QAMs.

### Cited Findings
- Temperature scaling "considerably reduces miscalibration", and for MC-dropout uncertainty it has been extended to calibrate model uncertainty — [Laves et al., arXiv 1909.13550](https://arxiv.org/abs/1909.13550)
- ECE: definitions and a visual explanation — [arXiv 2501.19047](https://arxiv.org/html/2501.19047v2). The limits of temperature scaling are discussed in [arXiv 2607.13423](https://arxiv.org/html/2607.13423), and the sklearn calibration docs are [here](https://scikit-learn.org/stable/modules/calibration.html)
- Higher-order cumulants are widely used because the cumulants of Gaussian noise vanish above second order. However, "HOCs provide limited discrimination for high-order constellations, such as 16QAM and 64QAM" — [search summary citing AMC fusion literature, e.g. Sensors 21(6):2117](https://doi.org/10.3390/s21062117)
- Deep feature fusion for high noise level and large dynamic input: FFT/Welch spectra plus CNN/SAE, fused with HOC statistical features — [Sensors 2021, 21(6), 2117](https://doi.org/10.3390/s21062117). Dual-modal feature-fusion CNN — [Entropy 2022, 24(5), 700](https://doi.org/10.3390/e24050700)

### Inferences
- Concatenate a small handcrafted vector with the CNN embedding before the final layer. Candidates are C20, C21, C40, C41, C42, C60-C63 magnitudes normalised by C21², the amplitude kurtosis and σ_aa, σ_ap, σ_dp (instantaneous amplitude/phase/frequency deviation), spectral flatness, and the peak of the squared/fourth-power spectrum (for BPSK/QPSK carrier lines). This is cheap on CPU and gives interpretable evidence, which also helps FSK and analog classes.
- Fit the temperature T on a held-out validation set that includes impairments. Report ECE per SNR bin (15 bins) before and after scaling. Reuse the same T in the energy score.

### Gaps
- I found no AMC paper that quantifies ECE on RadioML before and after temperature scaling.
- I did not obtain quantitative gains of cumulant+CNN fusion over pure CNN on RML2018.

## Q6. Variable samples-per-symbol / unknown symbol rate

### Takeaway
The literature handles unknown rate either with blind symbol-rate estimation followed by resampling to a canonical sps (as in super-constellation approaches), or by training with random resampling. Sig53 includes random resampling as an impairment. DNN symbol-rate estimators beat cumulant-based estimators but may need retraining for each modulation.

### Cited Findings
- One method estimates the symbol rate from received signals and downsamples, then builds constellation images for a CNN. DNN blind symbol-rate estimators "significantly outperform traditional cumulant-based estimators" but "may require extensive retraining for each modulation type" — [search synthesis; see Automated Symbol Rate Estimation Over Frequency-Selective Fading using DNN](https://www.researchgate.net/publication/349170338_Automated_Symbol_Rate_Estimation_Over_Frequency-Selective_Fading_Channel_by_Using_Deep_Neural_Network)
- Combining DL with linear processing: networks that learn to estimate and correct CFO and multipath before classification and symbol decoding — [arXiv 2006.00729](https://arxiv.org/pdf/2006.00729); [arXiv 2106.10543](https://arxiv.org/pdf/2106.10543)
- Real OTA captures show "temporal dilation" from synchronisation errors and frequency drift — [search synthesis; arXiv 2511.21040](https://arxiv.org/html/2511.21040v2)
- Sig53 uses random resampling as a training impairment — [arXiv 2207.09918](https://arxiv.org/html/2207.09918v1)
- RML2016.10a is fixed at 8 samples per symbol, so models trained on it are tuned to that rate. The MATLAB example also uses fixed sps — [MathWorks Modulation Classification with Deep Learning](https://www.mathworks.com/help/comm/ug/modulation-classification-with-deep-learning.html). The fixed 8 sps for RML2016 is from general knowledge and is not verified in the fetched text.

### Inferences
Recommended pipeline:
1. Coarse bandwidth or occupied-bandwidth estimate from the Welch PSD.
2. Symbol-rate estimate from the cyclic spectrum or the spectral line of |x|² (or |x|⁴ for QAM). Fall back to the bandwidth-derived estimate.
3. Coarse CFO removal (the peak of the x⁴ spectrum, or the PSD centroid).
4. Rational or polyphase resampling (for example `scipy.signal.resample_poly`) to a canonical 4 or 8 sps.
5. Classification on fixed-length windows (128-1024 samples) with the model trained under ±10-20% sps jitter so it tolerates estimation error.
6. Aggregation of logits over multiple windows (mean of log-probs), which greatly improves low-SNR accuracy for long captures.

For FSK and analog classes, the rate estimate is less meaningful. Train them with random sps and bandwidth.

### Gaps
- I found no benchmark that quantifies the accuracy loss of RML-trained models under sps mismatch.

## Q7. ONNX export and quantisation pitfalls

### Takeaway
ONNX Runtime recommends dynamic quantisation for RNNs and transformers and static QDQ quantisation for CNNs. LSTM/GRU quantisation support has historically been limited. On x86 AVX2/AVX512, U8S8 can saturate, so use reduce_range or per-channel quantisation. Preprocess with `onnxruntime.quantization.preprocess` and debug with `qdq_loss_debug`. For roughly 10-100K-parameter models, FP32 ONNX is already fast enough, so quantisation is optional.

### Cited Findings
- "Use dynamic quantization for RNNs and transformer-based models, and static quantization for CNN models." QDQ format is preferred for debugging. Preprocess (symbolic shape inference, graph optimisation) via `onnxruntime.quantization.preprocess`. On AVX2/AVX512, VPMADDUBSW with U8S8 "might suffer from saturation issues"; use reduce_range (7-bit) or U8U8. Per-channel quantisation helps when channel ranges vary. Debug with `onnxruntime.quantization.qdq_loss_debug` — [ONNX Runtime quantization docs](https://github.com/microsoft/onnxruntime/blob/gh-pages/docs/performance/model-optimizations/quantization.md)
- There is a long-standing ONNX Runtime issue about quantising LSTM — [onnxruntime issue #5747](https://github.com/microsoft/onnxruntime/issues/5747). Some operators remain FP32 after static quantisation — [onnxruntime discussion #24038](https://github.com/microsoft/onnxruntime/discussions/24038)
- Static quantisation can end up slower or less accurate when ops such as LayerNorm and Softmax lack efficient int8 kernels, forcing repeated dequantisation. Fixed calibration scales are also fragile under distribution shift — [Quantizing Whisper-small, arXiv 2511.08093](https://arxiv.org/pdf/2511.08093)

### Inferences
Practical pitfalls for AMC models:
- **Complex-valued layers** (LDCVNN, ULCNN) must be written as real-valued pairs of Conv1d layers. ONNX has no complex dtype support in most runtimes.
- **Signal-processing ops.** Avoid `torch.fft`/`torch.stft`, `atan2` and `unwrap` inside the exported graph. Compute amplitude/phase and cumulant features in NumPy before ONNX, or check opset support (STFT exists from opset 17, but runtime support varies).
- **Recurrent layers.** Export GRU/LSTM with a fixed sequence length and `dynamic_axes` only on batch. Check parity with `onnxruntime` against PyTorch outputs (atol about 1e-4).
- **Calibration data.** Static-quantisation calibration data must span the full SNR range and include noise frames. Otherwise activation ranges clip on high-SNR or large-amplitude inputs, so normalise input power per frame first.
- **What to quantise.** Keep the final logits and the energy-score computation in FP32. Quantisation shifts logits and can break OOD thresholds and temperature calibration, so re-fit T and thresholds after quantising.

### Gaps
- I did not find published INT8 accuracy numbers for MCLDNN, ULCNN or PET-CGDNN on ONNX Runtime CPU.
- I did not confirm whether current ONNX Runtime (2026) supports dynamic quantisation of LSTM/GRU.
