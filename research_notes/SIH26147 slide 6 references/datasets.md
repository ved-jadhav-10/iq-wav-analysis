# Public RF machine-learning datasets (slide 6 "Datasets" references)

Research date: 29 September 2026. Anything not confirmed by a fetched source is marked UNCONFIRMED.

## RadioML 2018.01A (DeepSig): classes, SNR grid, size, format, licence, paper

### Takeaway
Confirmed: 24 classes, 26 SNR levels from -20 to +30 dB in 2 dB steps, exactly 2,555,904 examples of 1,024 complex samples each, HDF5, CC BY-NC-SA 4.0. DeepSig's own page rounds the size to "2 million" and calls the data synthetic with simulated channel effects.

### Cited Findings
- DeepSig lists RADIOML 2018.01A as "synthetic dataset with simulated channel effects", "24 digital and analog modulation types", "2 million" examples, 1024 samples per example, HDF5 of complex floating-point values, licence "Creative Commons Attribution – NonCommercial – ShareAlike 4.0 License". The page does not give the SNR range. — [DeepSig datasets](https://www.deepsig.ai/datasets/)
- Exact structure (from an analysis of the downloaded file `2018.01.OSC.0001_1024x2M.h5`): 2,555,904 records; `/X` is 2,555,904 × 1,024 × 2 (I/Q), `/Y` is one-hot 2,555,904 × 24, `/Z` is the SNR parameter; 26 SNR levels from -20 to +30 dB in 2 dB steps; 4,096 records per (class, SNR); each class occupies 106,496 consecutive records (4,096 × 26). — [CSP Blog, C. Spooner, "DeepSig's 2018 Data Set", 24 Sep 2020, updated Feb 2021](https://cyclostationary.blog/2020/09/24/deepsigs-2018-data-set-2018-01-osc-0001_1024x2m-h5-tar-gz/)
- Check: 24 × 26 × 4,096 = 2,555,904, so the counts agree with each other (arithmetic, not a separate source).
- Paper: O'Shea, Roy & Clancy, "Over-the-Air Deep Learning Based Radio Signal Classification", arXiv:1712.04578. — [arXiv PDF](https://arxiv.org/pdf/1712.04578). DeepSig's page cites it as IEEE Journal of Selected Topics in Signal Processing, dated 2017. — [DeepSig datasets](https://www.deepsig.ai/datasets/). The repo's existing reference gives IEEE JSTSP 12(1):168–179, 2018, DOI 10.1109/JSTSP.2018.2797022 (docs/SIHPS_ANALYSIS.md); not re-verified against IEEE Xplore in this pass.
- Kaggle mirror: "DeepSig Dataset: RadioML 2018.01A". — [Kaggle](https://www.kaggle.com/datasets/pinxau1000/radioml2018)

### Inferences
- On the slide, give the size as "2,555,904 (≈2.56 M)", not DeepSig's rounded "2 million".
- Year: use JSTSP 2018 (vol. 12, 2018) for the journal and arXiv Dec 2017 for the preprint. DeepSig's "2017" refers to the preprint or dataset year.
- One search-engine summary described 2018.01A as "captured over-the-air using USRP devices". DeepSig's own page calls it synthetic with simulated channel effects, so don't claim it is over-the-air.

### Gaps
- Volume, issue, pages and DOI were not re-fetched from IEEE Xplore in this session (the values come from the repo's docs). UNCONFIRMED here.
- File size of the archive: not found.

## Known RadioML quality problems (with citations)

### Takeaway
Four problems are documented, mostly by Chad Spooner on the CSP Blog, with a supporting 2024 overview from Panoradio: SNR labels far below the true in-band SNR, a noise-only AM-SSB class in 2016.10a, a wrong classes.txt mapping in 2018.01A, and roll-off and symbol rate that barely vary in 2018.01A. The "Sathyanarayanan" attribution in the brief could not be confirmed; no source by that name was found.

### Cited Findings
- **SNR labels:** "the SNR parameter does not correspond to any definition known", and using it as SNR puts you "off by tens of dB – the signals are much stronger than indicated by the parameter". Signals labelled SNR 18 measured about 40 dB in-band SNR. Using the label as SNR makes ML results "look much better than they really are". — [CSP Blog, "More on DeepSig's RML Data Sets", C. Spooner, 17 Aug 2020](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/)
- **AM-SSB is noise only (2016.10a):** "the signals in the dataset labeled as analog amplitude-modulated single sideband (AM-SSB) were absent: these signals were only noise." — [CSP Blog, 17 Aug 2020](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/)
- **Bimodal low-SNR data:** at SNR parameter -2, about half the examples show an obvious signal and half look like noise only. — [CSP Blog, 17 Aug 2020](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/)
- **2018.01A class mapping:** "the mapping provided by DeepSig in classes.txt is incorrect". PSD analysis gives a different order, for example OOK rather than 32PSK as the first class. — [CSP Blog, "DeepSig's 2018 Data Set", 24 Sep 2020](https://cyclostationary.blog/2020/09/24/deepsigs-2018-data-set-2018-01-osc-0001_1024x2m-h5-tar-gz/). A commenter also noted that the name-to-label mapping "does not match what they published in the paper". — [CSP Blog, 17 Aug 2020](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/)
- The same question was raised publicly on DeepSig's repository: GitHub issue #25, "Order of Modulation 2018 Dataset", opened 8 Aug 2019 by carlosrivera22, still open with no maintainer reply. — [radioML/dataset issue #25](https://github.com/radioML/dataset/issues/25)
- Community code works around the problem with a corrected `classes-fixed.json` so that the numeric labels match the class order (from a search-result summary, not opened directly). — [search result referencing leena201818/radioml](https://github.com/leena201818/radioml/blob/master/rml2018_01.py)
- **2018.01A diversity:** "It does not *appear* that the roll-off was actually varied as stated in Table I" (the paper claims 10–40 % excess bandwidth). Symbol rate and carrier offset "never significantly change". — [CSP Blog, 24 Sep 2020](https://cyclostationary.blog/2020/09/24/deepsigs-2018-data-set-2018-01-osc-0001_1024x2m-h5-tar-gz/)
- Panoradio's 2024 overview rates RadioML 2018 as "Flawed" and says that "several severe flaws of the data have become public over time" and that the datasets are "marked as erratic on their official website". — [Panoradio SDR, "Overview of Open Datasets for RF Signal Classification", 3 Nov 2024](https://panoradio-sdr.de/overview-of-open-datasets-for-rf-signal-classification/)
- Further CSP Blog posts on RML: "All BPSK Signals" (29 Apr 2020) and "One Last Time" (23 Nov 2021). — [CSP Blog](https://cyclostationary.blog/2020/04/29/all-bpsk-signals/), [CSP Blog](https://cyclostationary.blog/2021/11/23/one-last-time/)

### Inferences
- The slide can say that RadioML's SNR labels understate the true SNR by tens of dB, that 2016.10a's AM-SSB class is noise only, that 2018.01A's classes.txt mapping is wrong, and that the data is non-commercial. Each claim has a citable CSP Blog source.

### Gaps
- The "erratic" label on DeepSig's site is UNCONFIRMED. It did not appear in the text fetched from deepsig.ai/datasets today and is reported only by Panoradio.
- No peer-reviewed paper dedicated to RadioML label errors was found in this pass. The main sources are blog analyses and a GitHub issue. The "Sathyanarayanan" name in the brief could not be tied to any source (UNCONFIRMED).
- The exact corrected 24-class order is not reproduced here. It is in the CSP Blog 2018 post and should be copied from there if needed.

## RML2016.10a / RML2016.10b

### Takeaway
10a: 11 classes, 220,000 examples of 128 complex samples, 20 SNR levels from -20 to +18 dB in 2 dB steps, Python pickle, CC BY-NC-SA 4.0. 10b: 10 classes (10a without AM-SSB), about 1.2 M examples, same SNR grid and example length; its licence is not listed on DeepSig's current page.

### Cited Findings
- DeepSig: RADIOML 2016.10A is a synthetic dataset generated with GNU Radio, with 11 modulations (8 digital, 3 analog), in a pickle file under CC BY-NC-SA 4.0, presented at the 6th Annual GNU Radio Conference. RADIOML 2016.04C (11 modulations, variable SNR, LO drift, light fading) is also listed under CC BY-NC-SA 4.0. — [DeepSig datasets](https://www.deepsig.ai/datasets/)
- 10a: 220,000 records, 11 classes, 20 SNR levels from -20 to 18 dB in 2 dB steps, 128 complex samples per record, 1,000 examples per class per SNR. Classes: 8PSK, BPSK, QAM16, QAM64, QPSK, WBFM, CPFSK, GFSK, AM-DSB, AM-SSB, PAM4. — [search summary of arXiv:2103.14977 and arXiv:2304.00445](https://arxiv.org/pdf/2304.00445)
- 10b: 1.2 M examples, 10 classes (8PSK, AM-DSB, BPSK, CPFSK, GFSK, PAM4, QAM16, QAM64, QPSK, WBFM, so no AM-SSB), 20 SNR levels, length 128. — [AMC-Net, arXiv:2304.00445](https://arxiv.org/pdf/2304.00445); [search summary incl. zjwfufu/AWN](https://github.com/zjwfufu/AWN)
- A third-party re-release, "RadioML 2016.10a: Optimized and Validated Distribution", exists on Zenodo (not inspected). — [Zenodo 18397070](https://zenodo.org/records/18397070)

### Inferences
- 11 × 20 × 1,000 = 220,000 checks. 10b is probably 6,000 per class per SNR (10 × 20 × 6,000 = 1.2 M), but that is inference and UNCONFIRMED.

### Gaps
- 10b's licence is UNCONFIRMED: DeepSig's historical page, as fetched, lists 2018.01A, 2016.10A and 2016.04C but not 10b. It was likely also CC BY-NC-SA 4.0.
- Paper for 10a: O'Shea & West, "Radio Machine Learning Dataset Generation with GNU Radio", GRCon 2016. The title and authors are from memory; DeepSig confirms only "6th Annual GNU Radio Conference". UNCONFIRMED.
- The numbers above come from search-result summaries of papers, not from opening the files or DeepSig text. Treat the 10b size as lightly confirmed.

## HisarMod2019.1

### Takeaway
26 classes in 5 families; 5 channel types (ideal/AWGN, static, Rayleigh, Rician k=3, Nakagami-m m=2); 20 SNR levels from -20 to 18 dB; 780,000 signals of 1,024 I/Q samples; CSV in a 5.13 GB zip on IEEE DataPort (DOI 10.21227/8k12-2g70). Paper: Tekbıyık et al., IEEE VTC2020-Spring. Licence not stated on the page.

### Cited Findings
- IEEE DataPort, "HisarMod: A new challenging modulated signals dataset": 26 classes across 5 families (analog, FSK, PAM, PSK, QAM) through 5 wireless fading channels; 1,500 signals per modulation type at 1,024 I/Q samples each; 780,000 signals in total; SNR from -20 to 18 dB (20 levels); 2× oversampling, raised-cosine pulse with 0.35 roll-off; files HisarMod2019.1.zip (5.13 GB, CSV) plus readme.txt; DOI 10.21227/8k12-2g70; created 27 Oct 2019, updated 23 Mar 2020. Authors: Kürşat Tekbıyık, Cihat Keçeci, Ali Rıza Ekti, Ali Görçin, Güneş Karabulut Kurt. No licence stated on the page. — [IEEE DataPort](https://ieee-dataport.org/open-access/hisarmod-new-challenging-modulated-signals-dataset)
- Classes: BPSK, QPSK, 8/16/32/64PSK, 4/8/16/32/64/128/256QAM, 2/4/8/16FSK, 4/8/16PAM, AM-DSB, AM-DSB-SC, AM-USB, AM-LSB, FM, PM. Channels: ideal, static, Rayleigh, Rician (k = 3), Nakagami-m (m = 2), with various numbers of channel taps. — [Tekbıyık et al., arXiv:1911.04970](https://arxiv.org/pdf/1911.04970)
- Paper: K. Tekbıyık, A. R. Ekti, A. Görçin, G. Karabulut Kurt, C. Keçeci, "Robust and Fast Automatic Modulation Classification with CNN under Multipath Fading Channels", IEEE VTC2020-Spring. — [arXiv:1911.04970](https://arxiv.org/abs/1911.04970)
- Panoradio rates HisarMod "Flawed": "Multiple severe issues, including questionable label assignment, strange waveforms and absence of modulated data". — [Panoradio SDR, 3 Nov 2024](https://panoradio-sdr.de/overview-of-open-datasets-for-rf-signal-classification/)

### Inferences
- 26 × 1,500 = 39,000, not 780,000. 780,000 = 26 × 20 SNR × 1,500, so "1,500 per modulation" must mean per modulation per SNR level. The SNR step is 2 dB (20 levels from -20 to 18). Both are arithmetic inferences.
- "Ideal" is the AWGN-only case, so the brief's "AWGN, static, Rayleigh, Rician, Nakagami-m" matches.

### Gaps
- Licence UNCONFIRMED: none is shown on the DataPort page. DataPort "open access" datasets are often CC BY 4.0, but this was not verified.
- The train/test split was not found.

## Sig53 / WidebandSig53 (TorchSig) and TorchSig's status in 2026

### Takeaway
Sig53 has 53 classes and 4,096 complex samples per example. The impaired set spans Es/N0 from -2 to 30 dB (uniform). "5 million" is the headline figure, but the paper body lists 1 M clean training, 106 k clean validation, 5.3 M impaired training and 106 k impaired validation examples. WidebandSig53 has 550 k examples containing about 2 M signals. TorchSig renamed Sig53 to "Narrowband" and WidebandSig53 to "Wideband" in v0.6.0, and 2.x replaced the fixed datasets with one configurable generator. Sig53 is no longer the current official name. TorchSig code is MIT.

### Cited Findings
- Boegner, Gulati, Vanhoy, Vallance, Comar, Kokalj-Filipovic, Lennon, Miller, "Large Scale Radio Frequency Signal Classification", arXiv:2207.09918 (20 Jul 2022). The abstract describes Sig53 as "5 million synthetically-generated samples from 53 different signal classes and expertly chosen impairments". arXiv shows a CC BY 4.0 licence, which likely applies to the paper, not the dataset. — [arXiv:2207.09918](https://arxiv.org/abs/2207.09918)
- Body of the paper: four subsets, Clean Training (1M), Clean Validation (106k), Impaired Training (5.3M), Impaired Validation (106k), so "over 6 million examples" in total. 4,096 complex samples per example. The impaired set's SNR is uniform over Es/N0 -2 to 30 dB; the clean set has no noise. Families: ASK, PAM, PSK, QAM, FSK, OFDM. Sig53 "can be generated using the TorchSig toolkit, or ... downloaded through the TorchSig website". — [ar5iv HTML of 2207.09918](https://ar5iv.labs.arxiv.org/html/2207.09918)
- Boegner, Vanhoy, Vallance, Gulati, Feitzinger, Comar, Miller, "Large Scale Radio Frequency Wideband Signal Detection & Recognition", arXiv:2211.10335 (4 Nov 2022): WidebandSig53 has "550 thousand synthetically-generated samples from 53 different signal classes containing approximately 2 million unique signals". — [arXiv:2211.10335](https://arxiv.org/abs/2211.10335)
- Panoradio lists TorchSig as 53 classes, 4,096 IQ samples, 5.3 M examples, rated "OK". — [Panoradio SDR](https://panoradio-sdr.de/overview-of-open-datasets-for-rf-signal-classification/)
- TorchSig repo: "TorchSig is released under the MIT License"; "Support for 60+ signal types across all major modulation families (FSK, QAM, PSK, ASK, OFDM, Analog)"; "Unified Dataset Architecture: TorchSig features a single, flexible dataset system that supports both signal classification (single signal) and signal detection (multiple signals) tasks through configuration". The README no longer mentions Sig53 or WidebandSig53. Citations include a TorchSig 2.0 GNU Radio Conference 2025 paper. — [github.com/TorchDSP/torchsig](https://github.com/TorchDSP/torchsig)
- Releases: v0.6.0 renamed "Sig53 → Narrowband" and "WidebandSig53 → Wideband" and grew the signal library from 53 to 61 (FM, AM variants, chirp spread spectrum, LFM). Later releases: v1.1.0, v2.0.0 ("unified datasets and new transform system"), v2.1.0 (generalised label groupings), v2.1.1 and v2.2.0. v2.2.0 is dated "31 Aug" and adds geolocation, a config-based data module, multi-label classification and new signal builders (LoRa, GSM, 802.11a, Zigbee). — [TorchSig releases](https://github.com/TorchDSP/torchsig/releases), [v2.2.0](https://github.com/TorchDSP/torchsig/releases/tag/v2.2.0)

### Inferences
- The latest release is v2.2.0 (31 Aug). GitHub omits the year for dates in the current year, which suggests 31 Aug 2026. The fetch tool reported "2022", which conflicts with v2.x following v0.6.0 and v1.1.0. Treat the year as UNCONFIRMED; "TorchSig 2.2 (latest as of Sep 2026)" is the safe wording.
- On the slide, write "Sig53 / WidebandSig53 (TorchSig; now generated as Narrowband/Wideband datasets)" and cite the 2022 papers.

### Gaps
- Sig53 dataset licence UNCONFIRMED: the code is MIT, but no explicit data licence was found. The arXiv CC BY 4.0 notice covers the paper.
- The class count in TorchSig 2.x is UNCONFIRMED as an exact number. v0.6.0 gives 61, the README says "60+", and the repo's docs mention 57 (from an earlier pass). The 2.2.0 notes add further signal families without giving a count.
- Samples per example and SNR range for WidebandSig53 were not retrieved (the abstract doesn't state them).

## Real-world over-the-air labelled AMC datasets (incl. CORAL)

### Takeaway
No public dataset named "CORAL" for AMC was found (UNCONFIRMED or nonexistent under that name). One recent labelled over-the-air set is Belousov & Ronkin's "Real-World IQ Dataset for Automatic Radio Modulation Recognition under Multipath Channels" (Mendeley Data, 22 Jan 2026): 7 classes, 1,024-sample frames, HDF5, CC BY 4.0, DOI 10.17632/tjzsbph49x.2.

### Cited Findings
- Real-World IQ Dataset: 7 classes (BPSK, QPSK, QAM, GMSK, OFDM, NBFM, WBFM), 1,024 IQ samples per frame, HDF5, CC BY 4.0, DOI 10.17632/tjzsbph49x.2, published 22 Jan 2026. — [Mendeley Data](https://data.mendeley.com/datasets/tjzsbph49x/2)
- Other public sets found: Panoradio HF (18 HF modes, 2,048 IQ at 6 kHz, 173,000 examples, simulated with augmentations) and CSPB.ML.2018R2 (8 classes, 32,768 IQ, 112,000 examples, simulated; a clean alternative to RadioML). — [Panoradio SDR](https://panoradio-sdr.de/overview-of-open-datasets-for-rf-signal-classification/)

### Inferences
- Candidate one-liner for the slide: "Over-the-air: Real-World IQ (Mendeley 2026, 7 classes, CC BY 4.0)".

### Gaps
- The capture hardware and example count of the Real-World IQ dataset were not shown on the page.
- CORAL: nothing found. Don't put it on the slide.
