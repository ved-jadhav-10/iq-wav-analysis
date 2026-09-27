# SIH 2026 NTRO Dossier --- SIH26147 --- Annotated Edition (Every Term Explained)
 
Sep 21, 2026 · \@Someone · SIH26147 edition, updated Sep 23, 2026
 
> **Trimmed edition.** This document originally covered two SIH 2026 problem statements. Everything specific to the other one (SIH26053, DRDO LiDAR mapping) has been removed; only SIH26147 (.IQ/.wav signal analysis) and generic material remain. Section letter B and its numbering (B1--B7) are unchanged from the original two-PS edition, so cross-references still match.

> **How this relates to our other documents (27 September 2026).** This dossier is a source snapshot from 23 September and is kept as written. Newer documents supersede it where they differ. The B2 solution plan and the B4 risk table are superseded by [PLAN.md](PLAN.md), and the rival list and "14+ repos" count in B6 by [STANDARDS_TO_BEAT.md](STANDARDS_TO_BEAT.md), which found 35 and lists its corrections in §5.5. The method choices are superseded by the [research report](../reports/SIH26147%20solution%20research.md). The B7 judge questions are still current.
 
## Start here: how to read this document
 
This edition covers **SIH26147** (NTRO --- analysis of .IQ and .wav radio recordings). Every technical term, abbreviation and name is explained where it appears. You need no background in radio or signal processing to follow it.
 
Four reading aids are used throughout:
 
-   **Inline explanations** appear in square brackets right after a term the first time it matters, e.g. SNR \[Signal-to-Noise Ratio --- how strong a signal is compared with background noise\].
-   **Glossaries** at the end define every term again in more depth: Glossary A (general computing and data terms), Glossary B (radio, signals, coding), Glossary C (organisations, laws, SDGs, business and hackathon terms).
-   **Primers** in this section give you the mental picture first, so the details make sense later.
-   **Update labels** --- anything added or corrected in the 23 September 2026 update starts with **\[Sep 2026 update\]** (or has it in the heading), so you can see at a glance what is new.
## What changed in this edition (Sep 2026 update)
 
This edition was produced by re-checking the problem statement online (official portal mirrors, GitHub, YouTube, papers and tool releases) on 23 September 2026 and merging anything new into the existing text. Sections with nothing new are unchanged.
 
-   **No official change to the PS.** As of 23 September 2026 no revised description, FAQ, dataset link or video has been published for SIH26147. The PS details already in this dossier still match the public PS text.
-   **Deadline.** Idea submission and team nomination close on **30 September 2026**, the one national deadline; the PS stops accepting ideas once 500 have been submitted.
-   **The competition has moved.** At least 14 public GitHub repositories now target SIH26147. Several already ship ideas this dossier had listed as differentiators, so section B2 and the repository list (B6) were updated with what still sets a team apart.
-   **New material added:** latest-status notes (B1); newer tools and research (TorchSig 2.0, transformer-based modulation classifiers and others); extra risk rows; video resources; and a new \"pitfalls and judge questions\" section (B7). New terms were added to Glossaries B and C.
-   **Section letters unchanged.** Dossier B keeps its original letter so every section number and cross-reference still matches the earlier edition.
## Primer 1: Radio signals, IQ files and decoding
 
Radios, phones, walkie-talkies, satellites and aircraft all communicate using **radio waves**. A wave repeats many times per second; this rate is its **frequency**, measured in **Hertz (Hz)** \[cycles per second\]. kHz = thousand Hz, MHz = million, GHz = billion.
 
The problem statement covers three bands \[ranges of frequencies\]:
 
-   **HF** --- High Frequency, 3--30 MHz. Travels very long distances by bouncing off the upper atmosphere. Used by ships, military, amateur radio.
-   **VHF** --- Very High Frequency, 30--300 MHz. FM radio, aircraft voice, marine radio.
-   **UHF** --- Ultra High Frequency, 300 MHz--3 GHz. Mobile phones, GPS, TV, walkie-talkies.
To send data by radio, a transmitter changes some property of the wave in a pattern. That is **modulation**. Changing the frequency is **FSK** (Frequency Shift Keying); changing the phase \[the position within a wave\'s cycle\] is **PSK** (Phase Shift Keying); changing both phase and strength is **QAM** (Quadrature Amplitude Modulation). Recovering the data from the wave is **demodulation**. (\"Modem\" = modulator-demodulator.)
 
A **Software-Defined Radio (SDR)** is a radio whose processing is done in software on a computer, not in fixed hardware. An SDR records the airwaves as numbers called **samples** \[snapshots of the signal taken many times per second\]. How many snapshots per second is the **sampling rate** or **sampling frequency**.
 
Each sample is stored as two numbers, **I** (In-phase) and **Q** (Quadrature). Together they capture both the strength and the phase of the wave at that instant. A file of these pairs is an **IQ file** (.iq). A **.wav** file is the standard audio file format; it can also hold IQ data by putting I in the left channel and Q in the right.
 
Real transmitters protect data against noise in two more ways:
 
-   **FEC** --- Forward Error Correction. Extra, cleverly chosen bits are added so the receiver can fix errors without asking for a resend. Examples: convolutional codes, Reed-Solomon, LDPC.
-   **Interleaving** --- shuffling the order of bits before sending, so a burst of noise damages bits scattered across the message instead of a whole block. The receiver must **de-interleave** \[un-shuffle\] before FEC can repair errors.
**The SIH26147 idea in one line:** take an unknown recording, and automatically work out how it was transmitted (modulation, rate, FEC, interleaving), then undo each layer to recover the actual bits and find where each message starts.
 
**Blind** in this document means \"without being told the settings in advance\". Blind decoding is much harder than normal decoding, because you must guess the settings from the data itself.
 
## TL;DR (Too Long; Didn\'t Read --- the short summary)
 
-   **SIH26147 targets a real gap.** Its blind FEC and de-interleaver identification is an unsolved research area, and India today relies on *export-controlled* \[restricted from being sold abroad by the maker\'s government\] foreign COMINT software \[Communications Intelligence --- tools for intercepting and decoding communications\]. Example: Krypto500 costs about US\$7,400 and is *ITAR-controlled* \[covered by the US International Traffic in Arms Regulations\]; Rohde & Schwarz and PROCITEC sell only on quotation. This aligns with **Atmanirbhar Bharat** \[\"Self-reliant India\", the government\'s push to build technology domestically\] and **Make in India**.
-   **The scale is large and measured.** India logged 1,951 **GPS interference** incidents \[jamming or faking of satellite navigation signals\] between November 2023 and November 2025, and runs 28 monitoring stations under **WMO/WPC** \[Wireless Monitoring Organisation / Wireless Planning and Coordination wing, the government\'s radio-spectrum regulators\].
-   **Buildable by a 6-member AI/ML + full-stack team as a software-only project.** \[AI/ML = Artificial Intelligence / Machine Learning; full-stack = building both the user-facing app and the server behind it.\] The hard limits must be stated honestly: the absolute sample rate cannot be worked out from an IQ file with no *header* \[the descriptive information at the start of a file\]; blind FEC identification is *probabilistic* \[gives likely answers with a confidence level, not certainties\]. The winning strategy is to beat the many existing SIH GitHub *repos* \[code repositories, public project folders\] on rigour, *ground-truth validation* \[testing against data where the correct answer is known for certain\], and an India-specific report and dashboard.
-   \[Sep 2026 update\] **Nothing official has changed, but the field has.** There are now 14+ public repos for SIH26147, and the best already implement ideas this dossier once treated as differentiators (CRC / sync-word / re-encode verification). Submit by **30 September 2026**, and win on measured, honest evaluation rather than architecture diagrams.
# DOSSIER B --- SIH26147 \".IQ/.wav Signal Analysis\"
 
## B1. Abstract / problem understanding
 
*Full title: \"Automated model for analysis of .IQ and .wav files along with signal parameter extraction\". Signal parameters = the technical settings used to transmit a signal. Extraction = working them out from the recording.*
 
### What the problem is
 
Build a **GUI** system \[Graphical User Interface --- windows, buttons and charts rather than typed commands\] that takes .IQ or .wav recordings of HF, VHF and UHF signals (from a few kHz up to GHz) and performs five tasks:
 
1.  **Identify signal parameters**: sampling frequency, modulation, FEC and interleaving.
2.  **Demodulate** FSK, QAM and PSK.
3.  **De-interleave** four schemes:
    -   *Block* --- bits written into a grid row by row and read out column by column.
    -   *Convolutional* --- bits delayed by different amounts through a bank of memory lines.
    -   *Diagonal* (also called helical) --- bits read along diagonals of a grid.
    -   *Pseudo-random* --- bits reordered by a fixed, random-looking pattern.
4.  **FEC-decode** four code types:
    -   *Convolutional codes with Viterbi decoding* --- codes where each output depends on recent input bits; the **Viterbi algorithm** finds the most likely original sequence.
    -   *Reed-Solomon (RS)* --- codes working on groups of bits, excellent at fixing burst errors; used in CDs, QR codes and satellites.
    -   *Concatenated codes* --- two codes stacked, typically RS outside and convolutional inside; used in classic space links.
    -   *LDPC* --- Low-Density Parity-Check codes, modern powerful codes used in 5G, Wi-Fi and satellite TV.
5.  **Bitstream correlation** --- comparing the recovered bits against patterns to find where each **frame** \[one packaged message\] begins, and to separate the **header** \[the label at the start\] from the **payload** \[the actual content\].
The GUI must show a **constellation plot** and a **waterfall** display. A *constellation plot* draws each received symbol as a dot on a 2D chart; clean PSK or QAM shows tight clusters in a recognisable pattern. A *waterfall* (or *spectrogram*) is a scrolling colour image of which frequencies are active over time.
 
### Why it matters and the scale
 
The radio **spectrum** \[the full range of usable radio frequencies\] is crowded and contested. **SIGINT** \[Signals Intelligence --- gathering intelligence from intercepted signals\] work was historically manual. Isolating and classifying a single **signal of interest** often took 12--18 **person-hours** \[hours of one person\'s work\]. Trained SIGINT analysts are chronically in short supply.
 
India\'s **WMO** \[Wireless Monitoring Organisation, a field unit of WPC set up in 1952\] watches the spectrum through 22 Wireless Monitoring Stations, 5 International Monitoring Stations and 1 International Satellite Monitoring Earth Station. It works with police to raid illegal **repeaters** \[unauthorised transmitters that re-broadcast signals, often boosting mobile coverage illegally and causing interference\].
 
### Hard statistics and India context
 
-   **GPS interference**: the Minister of State for Civil Aviation, Murlidhar Mohol, told the **Lok Sabha** \[India\'s lower house of Parliament\] on 11 December 2025 that 1,951 GPS interference issues were reported from November 2023 to November 2025. This followed **DGCA** \[Directorate General of Civil Aviation, India\'s aviation regulator\] Advisory Circular ANSS AC 01 of 2023 (24 November 2023). Affected airports include Delhi, Mumbai and Amritsar. DGCA now requires reporting within 10 minutes and has asked WMO to locate the sources. \[GPS = Global Positioning System. **Jamming** drowns the signal in noise; **spoofing** broadcasts fake signals to mislead receivers.\]
-   **Digital economy**: 11.74% of national income (₹31.64 lakh crore, about US\$402 billion) in 2022--23, projected toward one-fifth of **GDP** \[Gross Domestic Product, the total value of a country\'s economic output\] by 2029--30 (**MeitY** \[Ministry of Electronics and Information Technology\] / **ICRIER** \[Indian Council for Research on International Economic Relations\]). Radio spectrum underpins all of it.
-   **5G**: **GSMA Intelligence** \[research arm of the GSM Association, the global mobile-industry body\] estimates 5G could benefit India\'s economy by ₹36.4 trillion (US\$455 billion) between 2023 and 2040. \[5G = fifth-generation mobile networks.\] This is a forecast, not a realised figure.
### Import dependence and the Atmanirbhar angle
 
The leading **COMINT decoders** \[software that identifies and decodes intercepted communications\] are all foreign, expensive and export-controlled:
 
-   **Krypto500 / Krypto1000** --- by COMINT Consulting. Krypto500 was reported at about US\$7,400, is ITAR-controlled, and has no trial or light version.
-   **Wavecom W-CODE** --- Swiss professional decoder suite.
-   **PROCITEC go2DECODE / go2MONITOR** --- German signal-analysis and monitoring suites.
-   **Rohde & Schwarz GX430** --- signal-analysis software from the large German test-equipment maker.
-   **Decodio** --- Swiss signal-analysis software.
An indigenous tool fits **Atmanirbhar Bharat**, the Ministry of Defence\'s **Positive Indigenisation Lists** \[lists of defence items the forces must buy from Indian suppliers; 5 lists, 4,666+ items\] and **iDEX** \[Innovations for Defence Excellence, the MoD scheme funding start-ups\].
 
### Dual-use civilian applications
 
*Dual-use* = useful for both defence and civilian purposes. Civilian uses: spectrum management, **interference hunting** \[finding the source of an unwanted signal\], telecom regulation by WPC and **TRAI** \[Telecom Regulatory Authority of India\], satellite operations, amateur (\"ham\") radio, and disaster and emergency communications.
 
### Empathy factors (who is actually hurt)
 
-   Air passengers endangered by GPS spoofing near borders.
-   Citizens whose licensed spectrum is jammed.
-   The overloaded WMO analyst doing hours of manual work per signal.
-   Defence operators dependent on foreign, licence-locked software.
### Latest status of SIH26147 (Sep 2026 update)
 
-   **Official:** no revised description, FAQ, dataset link or video has been published as of 23 September 2026. Organisation: NTRO; category: Software.
-   **Theme:** early portal mirrors listed it under \"Miscellaneous\"; a 7 September 2026 catalogue (BlinkNBuild) lists it under \"Space Technology\". Confirm on sih.gov.in before submitting; the theme does not change the technical scope.
-   **Idea count:** no reliable figure found. One online \"40--90 ideas\" number is an estimate, not data.
-   **Deadline:** 30 September 2026 (one older mirror snapshot showed 20 September --- verify on the portal).
-   **Scope wording:** team repositories paraphrase the PS as terrestrial RF signals captured from *different sensors and locations*. Expect recordings in several formats and sample rates, which makes robust file ingestion (B3) part of the problem, not an afterthought.
## B2. Solution plan
 
### How it solves the problem
 
An operator uploads an .IQ or .wav file. The tool then:
 
1.  **Visualises** it as a spectrogram/waterfall and constellation.
2.  **Detects** signals present in the recording.
3.  **Estimates parameters**:
    -   *Bandwidth* --- how wide a slice of frequencies the signal occupies.
    -   *SNR* (Signal-to-Noise Ratio) --- how strong the signal is compared with background noise, measured in **dB** \[decibels, a logarithmic scale; +3 dB ≈ double the power, negative SNR means noise is stronger than the signal\].
    -   *Symbol rate* (or **baud rate**) --- how many **symbols** \[individual wave-states, each carrying one or more bits\] are sent per second.
    -   *Centre-frequency offset* --- how far the signal sits from the centre of the recording.
4.  **Classifies modulation** with a deep-learning **AMC** model \[Automatic Modulation Classification --- AI that looks at raw samples and names the modulation type\].
5.  **Demodulates**, then attempts **de-interleaving** and **FEC identification and decoding**.
6.  **Correlates the bitstream** to find frame boundaries and headers.
7.  Outputs a report plus a **SigMF annotation** \[a standard metadata file describing what was found where; explained in B3\].
### Novelty versus incumbents
 
Modulation classification alone is not novel; deep-learning AMC is mature. O\'Shea et al. (IEEE JSTSP 2018) showed about 95% accuracy at high SNR. \[IEEE JSTSP = *IEEE Journal of Selected Topics in Signal Processing*; IEEE = Institute of Electrical and Electronics Engineers.\]
 
The differentiator is an **open, indigenous, ground-truth-verified** pipeline that treats blind FEC identification and blind de-interleaving as first-class features. These remain active research problems, not solved engineering.
 
What is unique:
 
-   Results verified by **hard ground truth** rather than guessed percentages:
    -   **CRC check** \[Cyclic Redundancy Check --- a checksum inside a frame; if it matches, the decoded bits are almost certainly correct\],
    -   **sync-word correlation** \[finding a known fixed bit pattern that marks the start of each frame\], and
    -   **re-encode BER** \[re-apply the identified FEC to the decoded bits and compare with what was received; a low **Bit Error Rate** proves the code guess was right\].
-   **SigMF-native** metadata throughout.
-   Runs **fully offline / air-gapped on a CPU** \[the ordinary main processor, no special graphics card needed\].
**\[Sep 2026 update\] What still sets a team apart now that rivals have caught up.** The verification idea above is no longer unique: Team Vertex (Gururaghavendra123/sihps2-2026) accepts a decode only with CRC-16, sync-word correlation and re-encode BER; Devansh-567/hackathon labels every output with one of five honesty states (detected, estimated, inferred, hypothesised, unknown); ICHNOVA accepts a code guess only if it stays statistically significant after allowing for how many guesses were tried; and several repos already export SigMF. Treat these as *table stakes* \[features every serious competitor already has\] and compete on:
 
-   **Real over-the-air validation** --- test on genuine recordings (for example your own RTL-SDR captures of FM broadcast, aircraft ADS-B or weather satellites, or public SigMF archives), not only synthetic data.
-   **Published accuracy-versus-SNR curves**, including the low-SNR region where most tools quietly fail.
-   **Multi-signal recordings** --- detect and cut out several transmitters in one file (wideband detection), not just one clean signal.
-   **Open multiple-hypothesis correction** --- show the number of code and interleaver guesses tried and how the acceptance threshold was raised to match.
-   **Analyst-in-the-loop** --- let the analyst confirm or correct a label and have every later stage re-run automatically.
### \"Wow\" features
 
-   Deep-learning AMC showing its **confidence** \[how sure it is, 0--100%\] plus human-readable evidence.
-   Automatic SigMF annotation of every detected signal.
-   Interactive **WebGL** waterfall \[WebGL uses the graphics chip in a browser for smooth, fast drawing\].
-   **Catalogue-bounded** blind FEC and interleaver identification with honest confidence. \[*Catalogue-bounded* = choose the best match from a fixed list of known code settings, rather than reconstructing any possible code from scratch.\]
### Everyday-utility features
 
-   Batch processing of many files.
-   Parameter export.
-   Constellation and **eye diagrams** \[overlaid traces of the signal around each symbol; a wide-open \"eye\" means clean, well-timed symbols\].
-   Per-signal JSON reports.
-   An **impairment / failure-testing harness** \[a test rig that deliberately adds noise, frequency drift and distortion to check how the tool copes\].
## B3. Technical approach
 
**DSP** = Digital Signal Processing: using maths in software to filter, analyse and transform sampled signals. Most of this project is DSP.
 
### DSP libraries
 
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Library                     What it is                                                                                         Role here
  --------------------------- -------------------------------------------------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------
  GNU Radio                   Free toolkit of signal-processing **blocks** you wire together into flowgraphs                     Demodulators, filters, synthetic data generation
 
  GNU Radio **OOT modules**   *Out-Of-Tree* add-ons written by the community                                                     Extra decoders and blocks not in the core
 
  liquid-dsp                  Fast C library of communications DSP building blocks                                               Modems, filters, synchronisers
 
  scikit-dsp-comm             Python library of communications DSP examples and functions                                        Quick prototyping
 
  komm / CommPy               Python libraries for modulation, channel coding and simulation                                     FEC encoding/decoding, test signals
 
  NumPy / SciPy               Core Python maths and scientific libraries                                                         Array maths, **FFT** \[Fast Fourier Transform --- converts a signal from time into its frequency components\], filters
 
  CuPy                        NumPy-like library that runs on an NVIDIA **GPU** \[graphics processor, fast at parallel maths\]   Optional speed-up
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
### Machine learning
 
**PyTorch** or **TensorFlow** \[Google\'s deep-learning library\] trains the AMC model on:
 
-   **RadioML 2018.01A** --- a public dataset by DeepSig: 24 modulation types, 26 SNR levels from −20 dB to +30 dB, 2.56 million examples, each 1,024 I/Q sample pairs.
-   **Synthetic GNU Radio data** --- signals we generate ourselves, so the true answer is known exactly.
```{=html}
<!-- -->
```
-   \[Sep 2026 update\] **TorchSig 2.0** --- an open-source PyTorch toolkit for radio-frequency machine learning, released in summer 2025. It generates synthetic signals of 57 analogue and digital modulation variants with realistic hardware *impairments* \[imperfections such as frequency drift, phase noise and IQ imbalance\], uses real-world units (Hz, seconds) and can write datasets to disk. Use it to create labelled training data well beyond RadioML.
-   \[Sep 2026 update\] **Sig53 / WidebandSig53** --- TorchSig\'s public datasets: 5 million narrowband examples across 53 classes, and 550,000 wideband recordings containing about 2 million signals, for detecting and classifying several signals in one recording.
### IQ files and metadata
 
-   **SigMF** (Signal Metadata Format) --- an open standard that pairs a raw data file (.sigmf-data) with a JSON description file (.sigmf-meta) recording sample rate, centre frequency, data type and annotations. It solves the \"headerless IQ file\" problem.
-   **NumPy memory-mapped readers** --- read huge files piece by piece without loading them fully into memory.
```{=html}
<!-- -->
```
-   \[Sep 2026 update\] **Headerless sample formats** --- raw .iq files usually store **cf32_le** \[complex 32-bit floating point, little-endian\] or **ci16_le** \[complex 16-bit integers, little-endian\]. *Little-endian* is the byte order most PCs use. Guessing the format or sample rate wrongly turns everything into noise, so read SigMF or ask the operator, and print the assumption in every report. (One public SIH26147 repo documents a real bug where the sample rate silently defaulted to 1 Hz.)
-   \[Sep 2026 update\] **Mono versus stereo WAV** --- only a stereo WAV with I in the left channel and Q in the right is true IQ. A mono WAV is real-valued audio; turning it into IQ with a **Hilbert transform** \[maths that builds a complex signal from a real one\] is an approximation, so label modulation results from mono files as hypotheses, not findings.
### Visualisation
 
-   **pyqtgraph** --- fast, responsive plotting for desktop Python apps.
-   **WebGL** in a browser --- suits the team\'s web and UI strengths.
-   **matplotlib** --- the standard Python plotting library, for static report images.
### GUI framework
 
Recommended: **web-based** --- **React** with **TypeScript** \[JavaScript with type checking, which catches bugs early\] for the interface, **FastAPI** Python backend, Python DSP core. This plays to the team\'s full-stack skills.
 
Alternative: **PyQt / PySide** --- Python bindings for **Qt**, a native desktop GUI toolkit.
 
### Synchronisation and estimation algorithms
 
A receiver must lock onto the signal\'s exact frequency and symbol timing before it can read bits. That is **synchronisation**.
 
-   **Oerder-Meyr** --- a classic method to estimate symbol timing and rate by squaring the signal and finding the resulting tone.
-   **Cyclostationary analysis** --- exploits the fact that man-made signals repeat statistically at their symbol rate, revealing hidden periodicities.
-   **Wavelet methods** --- detect symbol transitions using short localised wave shapes.
-   **Costas loop** --- a feedback loop that tracks and corrects the carrier\'s frequency and phase (**carrier recovery**). The *carrier* is the base wave the data rides on.
-   **Gardner** and **Mueller-Muller** --- timing-error detectors that find the best moment to sample each symbol (**timing recovery**).
```{=html}
<!-- -->
```
-   \[Sep 2026 update\] **M2M4 SNR estimator** --- estimates SNR from the second and fourth statistical *moments* \[averages of the signal\'s power and of its power squared\], without knowing the transmitted data.
-   \[Sep 2026 update\] **Higher-order cumulants (C20, C40, C42)** --- statistical fingerprints of a constellation. BPSK, QPSK and 16-QAM have different theoretical values, giving an explainable modulation check to cross-examine the neural network.
### FEC libraries
 
-   **AFF3CT** --- A Fast Forward Error Correction Toolbox, a high-performance C++ library of many codes.
-   **CommPy Viterbi** --- Python Viterbi decoder for convolutional codes.
-   **reedsolo** --- Python Reed-Solomon encoder/decoder.
-   **pyldpc** and **ldpc-toolbox** --- LDPC encoding and decoding.
```{=html}
<!-- -->
```
-   \[Sep 2026 update\] **scikit-commpy** (Viterbi) and **reedsolo** are what the most complete public SIH26147 pipeline uses. A **syndrome test** \[a quick check of whether bits are consistent with a guessed code, without fully decoding them\] lets you screen many code guesses cheaply before running full decoders.
### End-to-end pipeline
 
flowchart TD\
A\[IQ / WAV input + metadata\] \--\> B\[Spectrum + detection\]\
B \--\> C\[Parameter estimation\]\
C \--\> D\[Channelise + sync\]\
D \--\> E\[AMC classify\]\
E \--\> F\[Demodulate to bits\]\
F \--\> G\[De-interleave + FEC\]\
G \--\> H\[Correlate: frame + header\]\
H \--\> I\[GUI + report + SigMF\]
 
**Channelise** = cut out just the one signal of interest from a wide recording. **Symbol-to-bit** mapping (inside \"demodulate\") converts each received symbol into its bits.
 
### AMC model
 
A **CNN** \[Convolutional Neural Network --- a network that learns local patterns, widely used for images\] or **ResNet** \[Residual Network --- a deeper CNN with shortcut connections that make it easier to train\] operating directly on I/Q samples, following the O\'Shea baseline.
 
Expected accuracy: about 95% at high SNR, about 90% at around 6 dB, collapsing below −6 dB. Train and validate on RadioML plus synthetic data, and publish **accuracy-versus-SNR curves** honestly.
 
**\[Sep 2026 update\] Newer models.** *Transformer* models \[neural networks that use \"attention\" to weigh which parts of the input matter most\] now match or beat CNNs on RadioML 2018.01A. AMC-Transformer reports 98.8% accuracy at SNR ≥ 10 dB. MobileRaT, a lightweight transformer for edge devices, reports 98.4% peak accuracy at +18 dB and 65.9% averaged over all SNRs. Harper, Thornton and Larson (SMU, 2023) report 98.9% peak and 63.7% overall. The takeaway: at high SNR, modulation classification is close to solved. Judges will care about low-SNR behaviour and the stages after classification. A small CNN plus a cumulant cross-check is enough if the accuracy-versus-SNR curve is shown honestly.
 
## B4. Feasibility and viability
 
### Technical feasibility
 
-   **AMC and demodulation**: high. Well-understood, with public data and libraries.
-   **Parameter estimation from headerless IQ**: partial. The absolute sample rate and centre frequency *cannot* be inferred from the samples alone. They must come from SigMF metadata or the user. Relative quantities (bandwidth as a fraction of the recording, symbol rate relative to sample rate) *can* be estimated.
-   **Blind FEC and blind de-interleaving**: partial and probabilistic. Scope it to catalogue-bounded identification with a confidence score. This is openly an active research area; leading researchers include Marazin, Gautier, Burel, Barbier, Cluzeau, Tillich, Sendrier and Valembois.
### Operational feasibility
 
It deploys offline and air-gapped for WMO and defence analysts. It fits existing SDR capture workflows through SigMF. Operators need moderate to high skill. Maintenance means extending the catalogue of modulations and FEC settings.
 
### Economic feasibility
 
Software-only, running on ordinary computers with only a CPU. Compare the incumbents:
 
  -------------------------------------------------------------------------------------------
  Product                             Price
  ----------------------------------- -------------------------------------------------------
  Krypto500                           About US\$7,400; quotation-only and export-controlled
 
  Wavecom W-CODE (entry level)        About US\$995 (reseller-listed)
 
  Rohde & Schwarz / PROCITEC          Quotation-only
  -------------------------------------------------------------------------------------------
 
An indigenous open tool removes licence fees and ITAR restrictions, a strong Atmanirbhar cost-saving case.
 
### Social and legal feasibility
 
-   **Telecommunications Act 2023** now governs interception, replacing the **Indian Telegraph Act 1885** and **Indian Wireless Telegraphy Act 1933**. Its **Section 20** limits lawful interception to authorised government agencies on specified grounds (e.g. national security, public order).
-   Possessing or operating an unlicensed transmitter is an offence (up to 3 years under the 1933 Act, carried into the new framework).
-   The tool analyses files that were already captured. Position it for lawful WMO, defence and research use.
### Risk and mitigation map
 
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Risk                                                                                                       Type                    Mitigation / contingency
  ---------------------------------------------------------------------------------------------------------- ----------------------- -----------------------------------------------------------------------------------------------------------------------------------------------
  Blind FEC / de-interleaving unsolved                                                                       Technical               Catalogue-bounded identification with confidence; verify with CRC and re-encode BER
 
  No absolute sample rate or centre frequency from IQ                                                        Data                    Require SigMF metadata or user input; document the assumption
 
  AMC collapses at low SNR                                                                                   Performance             Publish accuracy vs SNR; only show labels in validated SNR ranges
 
  Scope too broad for a hackathon                                                                            Scope                   Phase it: AMC and demodulation first, FEC and de-interleaving as stretch goals
 
  Legal sensitivity of interception                                                                          Legal                   Offline file analysis only; assume lawful authority; record data **provenance** \[where the recording came from\] in SigMF
 
  **Domain gap** from foreign datasets (models trained on one kind of data doing worse on real-world data)   Data                    Add synthetic GNU Radio ground-truth data and realistic impairments
 
  \[Sep 2026 update\] Wrong sample format or rate assumed for a headerless file                              Data                    Never guess silently; require SigMF or operator input; print the assumption in the report; test with deliberately wrong settings
 
  \[Sep 2026 update\] Mono WAV mistaken for IQ                                                               Data                    Detect the channel count; mark results from mono files as hypotheses
 
  \[Sep 2026 update\] False \"matches\" from trying many FEC and interleaver guesses                         Technical               Raise the acceptance threshold with the number of guesses (a Bonferroni-style correction); accept only with CRC, sync-word or re-encode proof
 
  \[Sep 2026 update\] Pseudo-random interleaver with an unknown seed                                         Technical               State that it is practically unrecoverable; report what can be bounded (e.g. period) and mark the result \"unknown\"
 
  \[Sep 2026 update\] Solution looks copied from public repos                                                Scope / legal           Write your own code, credit every library, and make sure each member can explain every module; expect deep questioning
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
## B5. Impact and benefits
 
### Target audiences
 
  ------------------------------------------------------------------------------------------------------------------------------------------------------
  Audience                             Who they are                                                       Why they need it
  ------------------------------------ ------------------------------------------------------------------ ----------------------------------------------
  NTRO and defence SIGINT / EW units   EW = Electronic Warfare, using the spectrum to attack or protect   Faster, indigenous signal triage
 
  WMO / WPC                            Spectrum regulators with 28 monitoring stations                    Identify illegal or interfering transmitters
 
  DoT / TRAI                           DoT = Department of Telecommunications                             Enforce spectrum rules
 
  ISRO and satellite operators         ISRO = Indian Space Research Organisation                          Diagnose satellite link interference
 
  DGCA                                 Aviation regulator                                                 Hunt GPS interference sources
 
  Disaster-response agencies           e.g. NDRF, National Disaster Response Force                        Identify emergency signals quickly
 
  Academia and ham radio               Researchers, students, licensed amateur operators                  Open tool for learning and research
  ------------------------------------------------------------------------------------------------------------------------------------------------------
 
### Impact by type
 
-   **Social**: safer aviation and cleaner licensed spectrum.
-   **National security / strategic**: an indigenous, ITAR-free COMINT **triage** capability \[quickly sorting signals to decide which need expert attention\].
-   **Economic**: analyst time cut from 12--18 person-hours per signal toward automated triage, and **import substitution** \[replacing imported products with domestic ones\] against US\$7,400+ foreign licences.
-   **Research**: an open contribution to blind FEC and interleaver identification.
-   **Environmental**: negligible (software).
### SDG alignment
 
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  SDG target              What the target says (simplified)                                                     How the tool maps to it
  ----------------------- ------------------------------------------------------------------------------------- -----------------------------------------------------------
  9.1                     Quality, reliable, resilient infrastructure                                           Better-managed communications infrastructure and spectrum
 
  9.c                     Greatly increase access to ICT                                                        Protects spectrum that mobile and internet access rely on
 
  16.4                    Reduce illicit financial and arms flows, combat organised crime                       Detects illegal and hostile transmitters
 
  16.a                    Strengthen national institutions to prevent violence and combat terrorism and crime   Builds monitoring capacity in national agencies
 
  17.8                    Strengthen technology and innovation capacity                                         Indigenous technology capability
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
### National missions
 
Atmanirbhar Bharat, MoD Positive Indigenisation Lists, iDEX, Make in India and Digital India.
 
## B6. Research and references
 
### (a) Academic papers
 
-   **O\'Shea, Roy and Clancy, \"Over-the-Air Deep Learning Based Radio Signal Classification\", IEEE JSTSP 12(1):168--179, 2018. DOI 10.1109/JSTSP.2018.2797022.** \[12(1) = volume 12, issue 1; 168--179 = page numbers; **DOI** = Digital Object Identifier, a permanent link to a paper.\] The landmark deep-learning AMC paper and the source of RadioML 2018.
-   **Blind code-reconstruction literature** --- Marazin, Gautier and Burel; Barbier; Cluzeau and Tillich; Sendrier; Valembois. These researchers developed algebraic and statistical methods to recover unknown code and interleaver settings from intercepted bits.
```{=html}
<!-- -->
```
-   \[Sep 2026 update\] Boegner et al., \"Large Scale Radio Frequency Signal Classification\", arXiv:2207.09918, 2022 --- introduces TorchSig and Sig53.
-   \[Sep 2026 update\] Boegner et al., \"Large Scale Radio Frequency Wideband Signal Detection & Recognition\", arXiv:2211.10335, 2022 --- WidebandSig53.
-   \[Sep 2026 update\] Oh, \"TorchSig 2.0: Dataset Customization, New Transforms and Future Plans\", GNU Radio Conference (GRCon) 2025.
-   \[Sep 2026 update\] \"AMC-Transformer: Automatic Modulation Classification based on Enhanced Attention Model\" --- patch-tokenised raw IQ with self-attention; 98.8% at SNR ≥ 10 dB on RadioML 2018.01A.
-   \[Sep 2026 update\] MobileRaT (lightweight radio transformer for drone communications), MDPI *Drones* 7(10):596, 2023.
-   \[Sep 2026 update\] Harper, Thornton and Larson, transformer-based AMC, MDPI *Electronics* 12:3962, 2023.
### (b) Standards
 
-   **SigMF specification** --- the open metadata standard for recorded signals.
-   **ITU-R Handbook on Spectrum Monitoring** --- the international reference manual for monitoring stations. \[ITU-R = the radio sector of the International Telecommunication Union, the UN\'s telecoms agency.\]
-   **NFAP** --- National Frequency Allocation Plan, India\'s official table of which services may use which frequencies.
### (c) Datasets
 
  -------------------------------------------------------------------------------------------------------------------------------------------------
  Dataset                                             What it contains
  --------------------------------------------------- ---------------------------------------------------------------------------------------------
  RadioML 2018.01A (DeepSig)                          24 modulations, 26 SNR levels, 2.56 million examples
 
  RML2016.10a / 10b                                   Earlier, smaller RadioML sets, 11 modulations
 
  HisarMod2019.1                                      26 modulations across varied channel conditions (from Hisar Lab, Turkey)
 
  Self-generated GNU Radio corpus                     Our own signals with exact known modulation, FEC and interleaving
 
  \[Sep 2026 update\] Sig53 (TorchSig)                5 million narrowband examples, 53 classes
 
  \[Sep 2026 update\] WidebandSig53 (TorchSig)        550,000 wideband recordings with about 2 million signals, for detection plus classification
 
  \[Sep 2026 update\] TorchSig 2.0 generated corpus   Your own impaired, labelled data in 57 modulation variants, in real-world units
  -------------------------------------------------------------------------------------------------------------------------------------------------
 
### (d) Tools and prior art
 
-   **Open-source**: GNU Radio, liquid-dsp, komm, CommPy, AFF3CT, pyldpc.
```{=html}
<!-- -->
```
-   \[Sep 2026 update\] **New or newly relevant open-source:** TorchSig 2.0; **gr-spectrumdetect** (embeds a YOLOv8x detector trained with TorchSig inside GNU Radio for real-time signal detection; *YOLO* = \"You Only Look Once\", a fast object-detection network); **Inspectrum** (visual IQ-file inspector); **Universal Radio Hacker (URH)** (demodulation and protocol-analysis tool); the **SigMF** Python package; scikit-commpy; reedsolo.
```{=html}
<!-- -->
```
-   **Commercial**: Krypto500/1000, Wavecom W-CODE, PROCITEC go2DECODE/go2MONITOR, Rohde & Schwarz GX430, Decodio.
### (e) Competitive gap
 
Incumbents are closed, export-controlled and expensive. None is open, SigMF-native, ground-truth-verified and indigenous at the same time.
 
### (f) Existing SIH GitHub repositories (the baseline to beat)
 
Andro-HM/IQWAV, Akshat030307/SIH, karurravishankermohit-stack/-SignalX, arunkumarmeda27/SpectraSync, Devansh-567/hackathon, Gururaghavendra123/sihps2-2026 (Team Vertex, which uses Oerder-Meyr plus CRC-16, sync-word and re-encode-BER verification), pranshu1141-sharma/Pinpoint, and tejaswi-jain2007/SIGNEX. Most are early prototypes with AMC and partial pipelines. The bar to clear is honest FEC and de-interleaving handling plus hard-truth verification. \[CRC-16 = a 16-bit CRC checksum.\]
 
**\[Sep 2026 update\] The \"early prototypes\" description no longer fits the leaders.** New repositories found since the original list, and what each is worth studying for:
 
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Repository                                 What it does                                                                                                                                                                                                What to learn from it
  ------------------------------------------ ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ---------------------------------------------------------------------
  Devansh-567/hackathon (updated)            Complete backend: SigMF parser, synthetic generator, rule-based plus 1D-CNN classifier with calibration, Viterbi, Reed-Solomon, four interleaver types, JSON/CSV/PDF/SigMF reports; 188 of 188 tests pass   The most complete reference architecture; five-state honesty labels
 
  SomeNobody21112/ICHNOVA                    Blind search over frequency offset, symbol rate, BPSK/QPSK and phase; convolutional codes (K = 7/5/3) times block interleavers with a syndrome test and significance control                                Statistically rigorous decoding
 
  The-4Script/RadioFry                       Streamlit app; CNN trained on RML2016.10a plus interleaver and FEC classifiers                                                                                                                              Honest handling of mono WAV and phase ambiguity
 
  harikesh2709-creator/FUTURISTICS           Down-conversion, RRC, Gardner, Costas, M2M4, cumulant AMC, blind interleaver estimation, Viterbi/RS/LDPC                                                                                                    A complete DSP-chain checklist
 
  EDM-Fan/Nova-Signum\-\--Signal-Analyzer-   PySide6 desktop console; Random-Forest AMC; RS, LDPC and concatenated decoding; four de-interleavers                                                                                                        Desktop GUI reference
 
  Shivanshgh/Spectra-Sense                   Orchestration and evidence layer over GNU Radio, Inspectrum and URH; never forces a single answer                                                                                                           Positioning idea
 
  mks-Roald/ps26147_toolkit                  Command line plus Streamlit; Random Forest trained on RadioML 2016.10a                                                                                                                                      Minimal baseline
 
  SumitKumar00113/sigma-signal-analysis      PySide6 GUI; WAV/SigMF/raw ingestion; IQ-imbalance and clipping checks                                                                                                                                      Input-validation checks
 
  NirmitSingh-main/SYNAPS                    Early stage                                                                                                                                                                                                 Low value
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
Updated notes on repos already listed: Akshat030307/SIH now does multi-signal scene analysis (AM, FM, SSB, CW, FSK, PSK, QAM, OFDM, chirp) with SigMF annotations, offline on a CPU; pranshu1141-sharma/Pinpoint adds adaptive energy detection, pulse width and PRI measurement \[Pulse Repetition Interval\] and validated SigMF export; Andro-HM/IQWAV demodulated a real FM capture, showing the 19 kHz stereo pilot and 57 kHz RDS \[Radio Data System\] carrier --- a good example of real-signal validation.
 
### (g) Indian government documents
 
-   WPC and WMO publications.
-   Telecommunications Act 2023.
-   National Frequency Allocation Plan.
-   MoD Positive Indigenisation Lists.
### (h) Video and community resources (Sep 2026 update)
 
-   No video walkthrough dedicated to SIH26147 was found, and the PS lists no video link.
-   General SIH 2026 problem-selection videos: \"SIH 2026 Problem Statement Analysis... Do NOT Pick One Until You Watch This\" (youtube.com/watch?v=1pGiohRbBnc) and a 3× SIH evaluator on analysing problem statements (youtube.com/watch?v=dlPHrD0p_uE).
-   For learning: the GRCon 2025 TorchSig 2.0 talk and paper (events.gnuradio.org), GRCon talks on gr-spectrumdetect, and the free PySDR textbook (pysdr.org) for IQ fundamentals.
## B7. Pitfalls and likely judge questions (Sep 2026 update)
 
Pitfalls to avoid:
 
-   **Overclaiming** --- a \"97% confidence\" figure from synthetic data is easy for NTRO judges to expose. Use explicit uncertainty states.
-   **Promising the impossible** --- pseudo-random interleavers and unknown or proprietary FEC cannot be recovered blindly. Say so, and show what you can bound.
-   **Silent format errors** --- a wrong sample rate or data type corrupts every later estimate without an obvious error.
-   **Copying public repos** --- judges may have seen them; originality and understanding will be probed.
Questions to rehearse, with the answer to have ready:
 
1.  \"What happens if we give you a file with no metadata?\" --- show the operator prompt and how relative quantities are still estimated.
2.  \"How do you know your decode is correct?\" --- CRC, sync word or re-encode BER, never a bare percentage.
3.  \"How does accuracy change at 0 dB SNR?\" --- show the curve.
4.  \"Can it handle two overlapping signals?\" --- show wideband detection and channelisation.
5.  \"What if the interleaver is pseudo-random?\" --- state the limit and the bounded output.
6.  \"Does it run offline on an air-gapped machine?\" --- demo on a laptop with networking switched off.
# GLOSSARIES
 
## Glossary A --- General computing and data terms (A--Z)
 
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Term                                 Full form                           Plain-English meaning
  ------------------------------------ ----------------------------------- ----------------------------------------------------------------------------------------------------------
  Air-gapped                           ---                                 Physically disconnected from the internet
 
  Algorithm                            ---                                 A precise step-by-step procedure a computer follows
 
  API                                  Application Programming Interface   The defined way one program requests data or actions from another
 
  Backend                              ---                                 Server-side part of an application users don\'t see
 
  Baseline                             ---                                 A reference standard to compare against
 
  CSV                                  Comma-Separated Values              Simple text spreadsheet format
 
  Dashboard                            ---                                 A screen summarising data with charts and figures
 
  Docker                               ---                                 Tool that packages software into portable, isolated containers
 
  False positive                       ---                                 Something wrongly flagged as a problem
 
  Feature vector                       ---                                 A list of numbers describing an item, used as ML input
 
  Frontend                             ---                                 The part of an app users see and interact with
 
  Ground truth                         ---                                 Data where the correct answer is known for certain
 
  Header                               ---                                 Descriptive control information at the start of a message or file
 
  JSON                                 JavaScript Object Notation          Widely used machine-readable text data format
 
  ML                                   Machine Learning                    Software that learns patterns from data instead of following hand-written rules
 
  Open-source                          ---                                 Software whose code is public and free to use and modify
 
  Payload                              ---                                 The actual content being carried, as opposed to headers
 
  Pipeline                             ---                                 A chain of processing steps, each feeding the next
 
  Precision / Recall                   ---                                 Precision: share of flagged items that are truly bad. Recall: share of truly bad items that were flagged
 
  Python                               ---                                 Popular programming language for data and ML
 
  Supervised / unsupervised learning   ---                                 Supervised learns from labelled examples; unsupervised finds patterns without labels
 
  Triage                               ---                                 Sorting items by urgency
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
## Glossary B --- Radio, signal processing and error-correction (A--Z)
 
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Term                             Full form                                                        Plain-English meaning
  -------------------------------- ---------------------------------------------------------------- -------------------------------------------------------------------------------------------------------------------
  AMC / AMR                        Automatic Modulation Classification / Recognition                AI or algorithms that identify the modulation type from raw samples
 
  Amplitude                        ---                                                              Strength (height) of a wave
 
  Bandwidth                        ---                                                              Width of the frequency range a signal occupies
 
  Band (HF/VHF/UHF)                High / Very High / Ultra High Frequency                          3--30 MHz / 30--300 MHz / 300 MHz--3 GHz
 
  Baud / symbol rate               ---                                                              Symbols sent per second
 
  BER                              Bit Error Rate                                                   Fraction of bits received wrongly
 
  Bit / bitstream                  ---                                                              A single 0 or 1 / a continuous sequence of bits
 
  Blind estimation                 ---                                                              Working out settings without being told them
 
  Block interleaver                ---                                                              Writes bits into a grid by rows, reads by columns
 
  BPSK / QPSK / 8PSK               Binary / Quadrature / 8-level Phase Shift Keying                 PSK with 2, 4 or 8 phase states (1, 2 or 3 bits per symbol)
 
  Carrier                          ---                                                              The base radio wave that data is imposed on
 
  Carrier recovery                 ---                                                              Locking onto the exact carrier frequency and phase
 
  CCSDS                            Consultative Committee for Space Data Systems                    Body setting space-link standards, famous for RS + convolutional concatenated codes
 
  Centre frequency                 ---                                                              The frequency at the middle of a recording or signal
 
  cf32 / ci16                      complex float 32 / complex integer 16                            Common raw IQ sample formats; the wrong guess turns a file into noise
 
  Channelisation                   ---                                                              Isolating one signal\'s frequency slice from a wide recording
 
  CNN                              Convolutional Neural Network                                     Neural network learning local patterns; used for AMC
 
  Code rate                        ---                                                              Fraction of transmitted bits that are real data, e.g. rate 1/2 = half data, half protection
 
  COMINT                           Communications Intelligence                                      Intelligence from intercepted communications
 
  Concatenated code                ---                                                              Two codes stacked (outer RS + inner convolutional)
 
  Confidence score                 ---                                                              How sure a model is about its answer
 
  Constellation plot               ---                                                              2D chart of received symbols showing the modulation\'s pattern of dots
 
  Constraint length                ---                                                              How many past bits a convolutional encoder remembers; \"short-constrained\" = small memory, easy Viterbi decoding
 
  Convolutional code               ---                                                              FEC where each output depends on current and recent input bits
 
  Convolutional interleaver        ---                                                              Delays bits by different amounts using multiple memory lines
 
  Correlation                      ---                                                              Measuring how similar two signals or bit patterns are, used to find known patterns
 
  Costas loop                      ---                                                              Feedback circuit for carrier recovery in PSK
 
  CPU / GPU                        Central / Graphics Processing Unit                               Main processor / parallel processor good for ML
 
  CRC                              Cyclic Redundancy Check                                          Checksum confirming a frame decoded correctly
 
  Cumulants (C20, C40, C42)        ---                                                              Higher-order statistics that act as fingerprints of a modulation\'s constellation
 
  Cyclostationary analysis         ---                                                              Detecting hidden periodic statistics that reveal symbol rate and modulation
 
  dB                               Decibel                                                          Logarithmic ratio unit; +3 dB ≈ double power, +10 dB = 10×
 
  De-interleaving                  ---                                                              Reversing interleaving to restore original bit order
 
  Deep learning                    ---                                                              ML with many-layered neural networks
 
  Demodulation                     ---                                                              Recovering data from a modulated wave
 
  Diagonal / helical interleaver   ---                                                              Reads bits along diagonals of a grid
 
  Domain gap                       ---                                                              Drop in model accuracy when real data differs from training data
 
  DSP                              Digital Signal Processing                                        Software maths on sampled signals
 
  Dual-use                         ---                                                              Useful for both military and civilian purposes
 
  EW                               Electronic Warfare                                               Using the spectrum to attack, protect or gather intelligence
 
  Eye diagram                      ---                                                              Overlaid signal traces; an open \"eye\" means clean timing
 
  FEC                              Forward Error Correction                                         Redundant bits that let receivers fix errors themselves
 
  FFT                              Fast Fourier Transform                                           Algorithm converting a time signal into its frequency content
 
  Frame                            ---                                                              One packaged unit of data with header and payload
 
  Frame sync / sync word           ---                                                              Known bit pattern marking the start of each frame
 
  Frequency                        ---                                                              Wave cycles per second, in Hz
 
  FSK                              Frequency Shift Keying                                           Data carried by switching between frequencies
 
  Gardner / Mueller-Muller         ---                                                              Timing-error detectors for symbol timing recovery
 
  GNSS / GPS                       Global Navigation Satellite System / Global Positioning System   Satellite navigation (GPS is the US system; India\'s is NavIC)
 
  GNU Radio                        ---                                                              Free signal-processing toolkit built from connectable blocks
 
  GUI                              Graphical User Interface                                         Visual windows, buttons and charts
 
  Hilbert transform                ---                                                              Maths that builds a complex (IQ-like) signal from a real one; an approximation for mono audio
 
  Hz, kHz, MHz, GHz                Hertz and multiples                                              Cycles per second; thousand; million; billion
 
  I/Q                              In-phase / Quadrature                                            Two numbers per sample capturing amplitude and phase
 
  Interference                     ---                                                              Unwanted signals disrupting wanted ones
 
  Interleaving                     ---                                                              Reordering bits so burst errors get spread out
 
  .iq file                         ---                                                              Raw file of I/Q samples, often without any header
 
  Jamming / spoofing               ---                                                              Overpowering a signal with noise / transmitting fake signals
 
  LDPC                             Low-Density Parity-Check                                         Powerful modern FEC used in 5G, Wi-Fi, DVB-S2
 
  M2M4                             Second- and fourth-moment estimator                              A way to estimate SNR without knowing the transmitted data
 
  Matched filter                   ---                                                              Filter shaped like the expected pulse, maximising SNR before sampling
 
  Metadata                         ---                                                              Data describing data (sample rate, frequency, time)
 
  Modulation                       ---                                                              Changing a wave\'s properties to carry data
 
  Multiple-hypothesis correction   e.g. Bonferroni correction                                       Raising the bar for \"a match\" when many guesses are tried, so chance matches are not mistaken for real ones
 
  Neural network                   ---                                                              Layered model loosely inspired by the brain, trained on examples
 
  Oerder-Meyr                      ---                                                              Classic symbol-timing estimation method
 
  OTA                              Over-the-air                                                     A real recording captured from the airwaves, as opposed to synthetic data
 
  Phase                            ---                                                              Position within a wave\'s cycle, measured in degrees
 
  Pseudo-random interleaver        ---                                                              Reorders bits using a fixed random-looking permutation
 
  PSK                              Phase Shift Keying                                               Data carried by changing the wave\'s phase
 
  QAM                              Quadrature Amplitude Modulation                                  Data carried by changing both phase and amplitude (16-QAM, 64-QAM...)
 
  RadioML                          ---                                                              DeepSig\'s public AMC benchmark datasets
 
  Reed-Solomon (RS)                ---                                                              Block FEC strong against bursts; used in CDs, QR codes, satellites
 
  Repeater                         ---                                                              Device re-broadcasting a received signal
 
  ResNet                           Residual Network                                                 Deep CNN with shortcut connections
 
  RRC filter                       Root-Raised-Cosine                                               Standard pulse-shaping and matched filter in digital radio
 
  Sample / sampling rate           ---                                                              One snapshot of the signal / snapshots per second
 
  SDR                              Software-Defined Radio                                           Radio whose processing is done in software
 
  Sig53 / WidebandSig53            ---                                                              Large public RF datasets from the TorchSig project (53 signal classes)
 
  SIGINT                           Signals Intelligence                                             Intelligence from intercepted signals (includes COMINT)
 
  SigMF                            Signal Metadata Format                                           Open standard: data file + JSON metadata file
 
  Signal of interest               ---                                                              The particular signal an analyst wants to examine
 
  SNR                              Signal-to-Noise Ratio                                            Signal strength versus noise, in dB
 
  Spectrogram / waterfall          ---                                                              Image of frequency content over time
 
  Spectrum                         ---                                                              Full range of radio frequencies
 
  Symbol                           ---                                                              One transmitted wave-state carrying one or more bits
 
  Syndrome test                    ---                                                              A quick check of whether bits are consistent with a guessed code, without fully decoding
 
  Synthetic data                   ---                                                              Artificially generated data with known labels
 
  Timing recovery                  ---                                                              Finding the best instant to sample each symbol
 
  TorchSig                         ---                                                              Open-source PyTorch toolkit for RF machine learning and synthetic signal generation
 
  Transformer                      ---                                                              A neural network that uses \"attention\" to weigh which parts of the input matter most
 
  Turbo / Polar codes              ---                                                              Other modern FEC families (3G/4G and 5G control channels)
 
  URH / Inspectrum                 Universal Radio Hacker / ---                                     Free tools for inspecting IQ recordings and analysing radio protocols
 
  Viterbi algorithm                ---                                                              Finds the most likely transmitted sequence for convolutional codes
 
  .wav file                        Waveform Audio File Format                                       Standard audio file; stereo can hold I (left) and Q (right)
 
  Wavelet                          ---                                                              Short, localised wave shape used to analyse transitions
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
## Glossary C --- Organisations, laws, policies, SDGs and business/hackathon terms
 
### Indian organisations
 
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Acronym                 Full form                                                         Role
  ----------------------- ----------------------------------------------------------------- -----------------------------------------------------------------------------------------
  NTRO                    National Technical Research Organisation                          India\'s technical intelligence agency; issuer of SIH26147
 
  SIH                     Smart India Hackathon                                             National hackathon run by the Ministry of Education and AICTE
 
  AICTE                   All India Council for Technical Education                         Regulator of technical education; co-organises SIH
 
  PS                      Problem Statement                                                 A challenge posted in SIH, with an ID such as SIH26147
 
  MeitY                   Ministry of Electronics and Information Technology                Ministry for IT policy
 
  MoD                     Ministry of Defence                                               Defence ministry
 
  iDEX                    Innovations for Defence Excellence                                MoD scheme funding defence start-ups
 
  DoT                     Department of Telecommunications                                  Telecom policy and licensing
 
  WPC                     Wireless Planning and Coordination wing (of DoT)                  Allocates and licenses radio spectrum
 
  WMO                     Wireless Monitoring Organisation                                  WPC field unit monitoring the spectrum
 
  TRAI                    Telecom Regulatory Authority of India                             Telecom regulator
 
  ISRO                    Indian Space Research Organisation                                Space agency
 
  DGCA                    Directorate General of Civil Aviation                             Aviation safety regulator
 
  NDRF                    National Disaster Response Force                                  Disaster-response force
 
  ICRIER                  Indian Council for Research on International Economic Relations   Economic think tank
 
  Lok Sabha               ---                                                               Lower house of India\'s Parliament
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
### International organisations and sources
 
  -----------------------------------------------------------------------------------------------------------------------------------------------
  Acronym / name          Full form                                                               Role
  ----------------------- ----------------------------------------------------------------------- -----------------------------------------------
  IEEE                    Institute of Electrical and Electronics Engineers                       Major engineering association and publisher
 
  ITU / ITU-R             International Telecommunication Union / its Radiocommunication Sector   UN telecoms agency / its radio-spectrum arm
 
  GSMA                    GSM Association                                                         Global mobile-operator industry body
 
  DeepSig                 ---                                                                     US company that released the RadioML datasets
  -----------------------------------------------------------------------------------------------------------------------------------------------
 
### Laws, policies and regulations
 
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------
  Name                                                       What it is
  ---------------------------------------------------------- ------------------------------------------------------------------------------------------------------
  Telecommunications Act 2023                                New telecom law replacing the Telegraph and Wireless Telegraphy Acts; Section 20 covers interception
 
  Indian Telegraph Act 1885 / Wireless Telegraphy Act 1933   Older colonial-era telecom laws, now superseded
 
  NFAP                                                       National Frequency Allocation Plan
 
  ITAR                                                       International Traffic in Arms Regulations (US)
 
  Export control                                             Government restrictions on selling sensitive technology abroad
 
  Atmanirbhar Bharat                                         \"Self-reliant India\" initiative
 
  Make in India / Digital India                              Domestic manufacturing drive / national digitisation programme
 
  Positive Indigenisation Lists                              MoD lists of items that must be sourced from Indian suppliers
 
  Lawful interception                                        Legally authorised interception by approved agencies
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------
 
### SDG terms
 
The **SDGs** are 17 UN goals adopted in 2015 for 2030; each has numbered targets. The ones cited:
 
  -------------------------------------------------------------------------------------------------------------------------
  Target                              Meaning
  ----------------------------------- -------------------------------------------------------------------------------------
  SDG 9                               Industry, Innovation and Infrastructure
 
  9.1                                 Develop quality, reliable, sustainable and resilient infrastructure
 
  9.c                                 Significantly increase access to information and communications technology
 
  SDG 16                              Peace, Justice and Strong Institutions
 
  16.4                                Significantly reduce illicit financial and arms flows; combat organised crime
 
  16.a                                Strengthen national institutions to prevent violence and combat terrorism and crime
 
  SDG 17                              Partnerships for the Goals
 
  17.8                                Strengthen technology, science and innovation capacity (especially ICT)
  -------------------------------------------------------------------------------------------------------------------------
 
### Business, research and hackathon terms
 
  ------------------------------------------------------------------------------------------------------------------------
  Term                                Meaning
  ----------------------------------- ------------------------------------------------------------------------------------
  Abstract                            Short summary of a problem or paper
 
  Baseline (competitive)              The level existing solutions already reach
 
  Corpus                              Collection of data for study
 
  Et al.                              \"And others\" (co-authors)
 
  DOI                                 Digital Object Identifier, a permanent paper link
 
  Empirical                           Based on real-world observation or measurement
 
  Feasibility / viability             Can it be done / does it make sense to do and sustain
 
  GDP                                 Gross Domestic Product
 
  GitHub / repo                       Code-hosting site / a project\'s code repository
 
  ICT                                 Information and Communication Technology
 
  Idea cap / PS lock                  Each SIH problem statement stops accepting ideas after 500 submissions
 
  Import substitution                 Replacing imports with domestic products
 
  Incumbent                           Established existing product or company
 
  Indigenous                          Developed within India
 
  Lakh / crore                        100,000 / 10,000,000
 
  Median                              Middle value in a sorted list
 
  Mitigation / contingency            Action reducing a risk / fallback plan if it happens
 
  MVP / prototype                     Minimum Viable Product / early working version
 
  Novelty                             What is genuinely new
 
  Person-hours                        Hours of work by one person
 
  Prior art                           Everything already existing in a field
 
  Scope creep                         A project growing beyond its plan
 
  SDG                                 Sustainable Development Goal
 
  SME                                 Small and Medium Enterprise
 
  Stack                               Set of technologies used to build a product
 
  Table stakes                        Features every serious competitor already has, so they no longer set you apart
 
  TL;DR                               Too Long; Didn\'t Read --- a short summary
 
  USD / US\$ / INR / ₹                US dollar / Indian rupee
 
  Vendor-sourced                      A statistic published by a company selling related products, so potentially biased
 
  Whitespace                          An unoccupied gap in the market
  ------------------------------------------------------------------------------------------------------------------------
 
# RECOMMENDATIONS AND CAVEATS
 
## Recommendations
 
1.  **State each hard limit up front.** Disclose that absolute sample rate and centre frequency need metadata, and that blind FEC and de-interleaving are catalogue-bounded and probabilistic. NTRO judges reward honesty over **overclaiming** \[promising more than you can deliver\].
2.  **Win on the whitespace, not the crowded part.** Ground-truth verification (CRC, sync word, re-encode BER) and SigMF-native indigeneity remain your identity, but \[Sep 2026 update\] rivals now have them too, so add real over-the-air validation, low-SNR curves and multi-signal handling.
3.  **Build the ground-truth lab in weeks 1--2.** The project depends on labelled data you control: a synthetic GNU Radio / TorchSig corpus. A demonstrable labelled test set is the strongest credibility signal for evaluators.
4.  **Lead every pitch with India numbers**: 1,951 GPS-interference incidents, ₹31.64 lakh crore digital economy, and the Krypto500 import case (about US\$7,400, ITAR-controlled).
5.  **Benchmark explicitly against the named GitHub repos**, with a one-slide **competitive matrix** \[a table comparing your features against competitors\'\]. \[Sep 2026 update\] Name the leaders: Team Vertex, Devansh-567 and ICHNOVA.
6.  **Sequence the build for 6 members.**
    a.  DSP core + AMC + visualisation first; FEC and de-interleaving as the **stretch goal** \[an extra target attempted only after the core is done\].
    b.  Suits AI/ML + full-stack + UI/UX skills with no hardware fabrication.
7.  \[Sep 2026 update\] **Submit before 30 September 2026.** No official clarifications have appeared; do not wait for them.
8.  \[Sep 2026 update\] **Study, don\'t copy.** Use the leading repos as benchmarks to beat and keep novelty claims narrow and defensible.
9.  \[Sep 2026 update\] **Pre-stage all data and model weights offline** (RadioML / TorchSig sets). Finale connectivity is not guaranteed.
## Caveats (limits of the evidence)
 
-   Some statistics are **vendor-sourced** \[published by a company selling related products, so potentially biased\] or are forecasts: the 5G and digital-economy figures (GSMA \"could benefit\", MeitY projections) are projections, not achieved outcomes.
-   Beyond the 1,951 GPS-interference figure, clean annual counts of Indian radio-interference complaints could not be sourced. Only the monitoring-station count (28) and the GPS figure are firmly documented. A Parliament question or WPC annual report would be needed for more.
-   Commercial SIGINT pricing is mostly quotation-only or export-controlled. Only Krypto500 (\~US\$7,400) and Wavecom W-CODE entry (\~US\$995, reseller-listed) have public figures.
-   \[Sep 2026 update\] sih.gov.in blocked automated access during the September 2026 check, so PS text, theme and idea counts come from unofficial mirrors that sometimes disagree. Re-check the PS on the official portal before submitting.
-   \[Sep 2026 update\] Figures quoted from rival GitHub repos (test counts, accuracies) are the teams\' own claims and were not independently verified.
-   \[Sep 2026 update\] No video content specific to the PS exists yet; the linked videos are general or for learning.