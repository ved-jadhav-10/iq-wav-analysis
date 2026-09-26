# SIH 2026 NTRO & DRDO Dossiers --- SIH26147 and SIH26053 --- Annotated Edition (Every Term Explained)
 
Sep 21, 2026 · \@Someone · Two-PS edition, updated Sep 23, 2026
 
## Start here: how to read this document
 
This edition covers only two problem statements: **SIH26147** (NTRO --- analysis of .IQ and .wav radio recordings) and **SIH26053** (DRDO --- adaptive variable-resolution 2.5D LiDAR mapping). Every technical term, abbreviation and name is explained where it appears. You need no background in radio, signal processing or robotics to follow it.
 
Four reading aids are used throughout:
 
-   **Inline explanations** appear in square brackets right after a term the first time it matters, e.g. SNR \[Signal-to-Noise Ratio --- how strong a signal is compared with background noise\].
-   **Four glossaries** at the end define every term again in more depth: Glossary A (general computing and data terms), Glossary B (radio, signals, coding), Glossary C (organisations, laws, SDGs, business and hackathon terms), Glossary D (LiDAR, robotics and autonomous vehicles).
-   **Primers** in this section give you the mental picture first, so the details make sense later.
-   **Update labels** --- anything added or corrected in the 23 September 2026 update starts with **\[Sep 2026 update\]** (or has it in the heading), so you can see at a glance what is new.
## What changed in this edition (Sep 2026 update)
 
This edition was produced by re-checking both problem statements online (official portal mirrors, GitHub, YouTube, papers and tool releases) on 23 September 2026 and merging anything new into the existing text. Sections with nothing new are unchanged.
 
-   **Scope narrowed to two PS.** Dossier A (SIH26159 \"SecureMailScope\"), the email primer, the email-only glossary entries and the email parts of the TL;DR, recommendations and caveats were removed. Glossary A now keeps only general computing terms still used in this document.
-   **No official change to either PS.** As of 23 September 2026 no revised description, FAQ, dataset link or video has been published for SIH26147 or SIH26053. The PS details already in this dossier still match the public PS text.
-   **Deadline.** Idea submission and team nomination close on **30 September 2026**, the one national deadline; each PS stops accepting ideas once 500 have been submitted.
-   **The competition has moved.** At least 14 public GitHub repositories now target SIH26147 and at least 12 target SIH26053. Several already ship ideas this dossier had listed as differentiators, so sections B2, C2 and both repository lists (B6, C6) were updated with what still sets a team apart.
-   **New material added:** a LiDAR primer; latest-status notes (B1, C1); newer tools and research (TorchSig 2.0, transformer-based modulation classifiers, elevation_mapping_cupy v2.2.0, FreeDOM, Adaptive-LIO and others); extra risk rows; video resources; and new \"pitfalls and judge questions\" sections (B7, C7). New terms were added to Glossaries B, C and D.
-   **Section letters unchanged.** The two dossiers keep their original letters (B for SIH26147, C for SIH26053) so every section number and cross-reference still matches the earlier edition.
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
 
## Primer 2: LiDAR, point clouds and 2.5D maps (Sep 2026 update)
 
A **LiDAR** sensor \[Light Detection And Ranging\] fires laser pulses and times how long each takes to bounce back. Every pulse that returns gives one 3D **point**: its x, y, z position plus **intensity** \[how strongly the surface reflected the laser\]. One full sweep around the vehicle is a **frame** or **scan**; hundreds of thousands to millions of points per second together form a **point cloud**.
 
A spinning LiDAR stacks a fixed number of lasers vertically --- 16, 32, 64 or 128 **beams** (also called **channels**). Each beam traces a circle on the ground called a **ring**. Near the vehicle the rings are close together; far away they land metres apart, so distant ground is sampled only sparsely. This is why storing fine detail far from the vehicle is mostly wasted memory.
 
There are three common ways to store what the sensor sees:
 
-   **3D voxel grid** --- space cut into small cubes \[voxels\]; accurate but very memory-hungry.
-   **2D occupancy grid** --- a flat top-down map saying only \"free\" or \"blocked\" per cell; cheap, but loses height, so curbs, potholes and overhangs disappear.
-   **2.5D elevation map** --- a top-down grid where each cell also stores height (and here, a label for what is there). The middle ground, and the format SIH26053 asks for.
To know *what* each point is, a neural network performs **semantic segmentation** \[labelling every point with a class such as road, wall or person\]; accuracy is scored with **mIoU** \[mean Intersection over Union, explained in C3\]. To stitch scans together while the vehicle moves, the system also needs **odometry** \[estimating the vehicle\'s own motion from its sensors\].
 
**The SIH26053 idea in one line:** turn each LiDAR scan into a labelled top-down height map that is sharp near the vehicle and coarse far away, and prove it saves memory without losing safety-critical detail.
 
## TL;DR (Too Long; Didn\'t Read --- the short summary)
 
-   **Both problems target real gaps.** SIH26147\'s blind FEC and de-interleaver identification is an unsolved research area, and India today relies on *export-controlled* \[restricted from being sold abroad by the maker\'s government\] foreign COMINT software \[Communications Intelligence --- tools for intercepting and decoding communications\]. Example: Krypto500 costs about US\$7,400 and is *ITAR-controlled* \[covered by the US International Traffic in Arms Regulations\]; Rohde & Schwarz and PROCITEC sell only on quotation. For SIH26053 (DRDO), no open system combines point-by-point semantic labelling, moving-object separation and a distance-adaptive 2.5D map with a *measured* memory saving. Both align with **Atmanirbhar Bharat** \[\"Self-reliant India\", the government\'s push to build technology domestically\] and **Make in India**.
-   **The scale is large and measured.** India logged 1,951 **GPS interference** incidents \[jamming or faking of satellite navigation signals\] between November 2023 and November 2025, and runs 28 monitoring stations under **WMO/WPC** \[Wireless Monitoring Organisation / Wireless Planning and Coordination wing, the government\'s radio-spectrum regulators\]. On the roads, **MoRTH** \[Ministry of Road Transport and Highways\] recorded 4,61,312 accidents and 1,68,491 deaths in 2022 --- about 461 deaths a day --- and potholes alone caused 4,446 accidents and 1,856 deaths.
-   **Both are buildable by a 6-member AI/ML + full-stack team as software-only projects.** \[AI/ML = Artificial Intelligence / Machine Learning; full-stack = building both the user-facing app and the server behind it.\] The hard limits must be stated honestly: the absolute sample rate cannot be worked out from an IQ file with no *header* \[the descriptive information at the start of a file\]; blind FEC identification is *probabilistic* \[gives likely answers with a confidence level, not certainties\]; and off-road LiDAR segmentation is hard (about 43% mIoU is state of the art on RELLIS-3D). The winning strategy is to beat the many existing SIH GitHub *repos* \[code repositories, public project folders\] on rigour, *ground-truth validation* \[testing against data where the correct answer is known for certain\], and an India-specific report and dashboard.
-   \[Sep 2026 update\] **Nothing official has changed, but the field has.** There are now 14+ public repos for SIH26147 and 12+ for SIH26053, and the best already implement ideas this dossier once treated as differentiators (CRC / sync-word / re-encode verification for 26147; uncertainty-preserving ring grids with ghost removal for 26053). SIH26053 shows only 24 of 500 idea slots used (23 September, unofficial portal mirror), but low idea counts hide strong entries. Submit by **30 September 2026**, and win on measured, honest evaluation rather than architecture diagrams.
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
# DOSSIER C --- SIH26053 \"Adaptive Variable Resolution 2.5D Lidar Mapping\" (DRDO)
 
## C1. Abstract / problem understanding
 
*Full title: \"Adaptive Variable Resolution 2.5D Lidar Mapping for Dynamic Environment Perception\". Organization: DRDO (Defence Research and Development Organisation). Adaptive = automatically adjusting. Variable resolution = detail level that changes depending on where you look. Perception = a robot or vehicle sensing and understanding its surroundings.*
 
### What the problem is, in plain terms
 
A self-driving vehicle or robot \"sees\" its surroundings using **LiDAR** \[Light Detection And Ranging --- a spinning sensor that fires laser pulses and measures how long they take to bounce back\]. This produces a **point cloud**: millions of 3D dots per second describing the shape of everything around the vehicle.
 
Raw point clouds are huge and mostly wasteful to store and process in full 3D. A **3D voxel grid** \[dividing space into tiny cubes called *voxels*, short for \"volume pixel\"\] is accurate but needs enormous memory and computing power. A flat **2D occupancy grid** \[a top-down map that only says \"blocked\" or \"free\" per cell\] is cheap but throws away height, so it cannot tell a small curb from a tall wall, and misses potholes or low overhanging branches.
 
The middle ground is a **2.5D map** --- a top-down grid where each cell also stores height (an **elevation map**) plus, here, a label for what is there. The PS borrows an idea from human eyesight called **foveation** \[named after the *fovea*, the sharp-focus centre of the human retina\]: keep very fine detail (5 cm cells) close to the vehicle within 10 m, where a small obstacle can be dangerous, and let the cells grow coarser (up to 50 cm) out to 100 m, where only the general shape of the world matters.
 
The system must do three things: (1) **Terrain Analysis** --- tell drivable ground apart from non-drivable terrain; (2) **Object Detection** --- identify and label static obstacles (walls, poles) and dynamic objects (pedestrians, other vehicles); (3) **Adaptive Spatial Representation** --- build the non-uniform grid itself, using a data structure that avoids **alignment errors** \[cells from different resolutions not lining up correctly\] or data loss when projecting 3D points down into the 2.5D grid.
 
### Why the data volumes make this urgent (verified numbers)
 
Common LiDAR sensors and how much data they produce:
 
-   **Velodyne HDL-64E:** the S3 datasheet states it \"generates a point cloud of up to 2,200,000 points per second with a range of up to 120 m,\" at a \"5--20 Hz user-selectable frame rate\" \[Hz = times per second\].
-   **Ouster OS1-128:** per Clearpath Robotics, \"the OS1-128 offers up to 128 channels \... and a scanning speed of 5-20 Hz \... this translates to 5.2 million points per second.\"
-   **General rule:** most spinning LiDARs (8--128 lasers, 5--20 Hz) capture \"about a million points per second.\"
At 10 scans per second, a sensor producing \~1.3 million points/second delivers around 130,000 points every tenth of a second. Each point (x, y, z position plus intensity --- four numbers) takes 16 bytes, so a single frame is already \~2 MB, and naively turning that into a dense 3D grid explodes far larger. This is exactly the \"computational bottleneck and memory latency\" the PS describes.
 
### The worked memory example (the core selling point of a demo)
 
-   *Uniform 5 cm 3D voxel grid, 100 m radius:* a 200 m × 200 m footprint with a \~10 m vertical span at 5 cm cubes works out to about **3.2 billion voxels ≈ 3.2 GB** (1 byte each).
-   *Uniform 5 cm 2.5D grid, same footprint:* about **16 million cells ≈ 128 MB** (8 bytes each: height, class, count).
-   *Variable-resolution 2.5D ring grid* (5 cm inside 10 m, 50 cm out to 100 m): about **250,000 cells ≈ 2 MB**.
-   **Result: roughly 50× smaller than the uniform 2.5D grid, and over 1,000× smaller than the full 3D voxel grid**, while keeping full detail exactly where safety needs it most. A supporting fact: at 50 m range, consecutive LiDAR laser rings land about 10.8 m apart on the ground, so almost none of a uniform fine-grained far-field grid ever receives a laser return in a single frame --- proving that fine detail far away is largely wasted.
**\[Sep 2026 update\] Cross-check against a rival\'s published numbers.** Team Chronicles.exe\'s VRgrid reports a fixed memory bound of **8.94 MB** --- about 21.5× less than a uniform 5 cm 2.5D grid and about 286× less than a dense 5 cm 3D voxel grid --- and calculates that 99.87% of a uniform 5 cm grid\'s cells cannot receive a return in a single frame. Their ratios are smaller than ours because they store more per cell and use more rings, so always state exactly what each cell stores and what the baseline is. A second team (LiFovea) found that 78% of returns fell within 25 m for its sensor, so thinning far-field points saved little computation: the big saving is in *map memory*, not per-frame point processing. Present both honestly.
 
### Why it matters --- road safety in India
 
Per **MoRTH\'s** \[Ministry of Road Transport and Highways\] \"Road Accidents in India --- 2022\" report: \"A total of 4,61,312 road accidents have been reported \... which claimed 1,68,491 lives and caused injuries to 4,43,366 persons,\" an increase of 11.9% in accidents and 9.4% in deaths versus the year before --- roughly 461 deaths every single day. Pedestrians accounted for 32,825 deaths and two-wheeler riders 74,897. Separately, potholes alone \"caused 4,446 accidents in 2022, leading to 1,856 deaths\" --- precisely the kind of small vertical hazard a flat 2D map misses but a 2.5D elevation map catches.
 
### Why it matters --- defence (DRDO relevance)
 
DRDO has built **UGVs** \[Unmanned Ground Vehicles --- robotic vehicles with no onboard driver\] since the early 1990s across four labs: **CAIR** \[Centre for Artificial Intelligence & Robotics, Bengaluru\], **CVRDE** \[Combat Vehicles Research and Development Establishment, Chennai --- famous for **Project MUNTRA**, converting tank-like BMP-II carriers into remote-controlled/autonomous vehicles for surveillance, mine detection and CBRN reconnaissance\], **R&DE(E)** \[Research & Development Establishment (Engineers), Pune\], and **VRDE** \[Vehicle Research and Development Establishment, Ahmednagar\]. A perception system that is both memory-light and detail-rich near the vehicle directly serves off-road autonomy in Ladakh\'s high-altitude terrain, desert borders, mine-clearing and border patrol --- keeping soldiers out of danger from IEDs \[Improvised Explosive Devices\] and hazardous terrain.
 
### Why Western datasets don\'t transfer
 
Indian roads are **unstructured** \[without reliable, consistent markings or rules that most Western datasets assume\]: unreliable lane markings, mixed traffic including autorickshaws, hand carts, motorcycles and cattle, and undefined road edges. A model trained only on European or American driving data will misclassify an autorickshaw or a cow, because those simply don\'t appear in that training data.
 
### Empathy factors
 
Soldiers exposed to IEDs and treacherous, off-road terrain; the roughly 461 Indians who die on the roads every single day; pedestrians and two-wheeler riders, who are the most vulnerable road users; and rural communities where a pothole hidden in shadow is a lethal, invisible hazard.
 
### Latest status of SIH26053 (Sep 2026 update)
 
-   **Official:** no revised text, FAQ, dataset or video link as of 23 September 2026. The public PS text (checked via a mirror of the official page) matches this dossier: 5 cm cells within 10 m growing to 50 cm up to 100 m; \"PointNet++ or a Sparse Convolutional Neural Network\"; a real-time dashboard showing memory reduction against a uniform high-resolution 3D map; and metrics showing high FPS and high accuracy across distances.
-   **The judging checklist** is those four deliverables: a segmentation model, a variable-resolution grid engine, a dashboard with a memory comparison, and latency/accuracy metrics by distance.
-   **Idea count:** 24 of 500 as of 23 September 2026 (up 7 in two days), roughly 167th of 240 PS by count --- low volume, but see the competition notes in C2 and C6.
-   **Theme:** mirrors disagree (\"Smart Vehicles\" versus \"Transportation & Logistics\"); category: Software. Organisation: DRDO.
-   **Deadline:** 30 September 2026.
## C2. Solution plan
 
### How it solves the problem, end to end
 
1.  A LiDAR frame arrives (a fresh point cloud).
2.  A deep-learning **semantic segmentation** model \[an AI that labels every point with a category\] classifies each point as terrain, static obstacle, or dynamic object.
3.  A **moving-object module** compares consecutive frames to work out which points are actually in motion, not just relatively moving because the sensor itself moved.
4.  The **variable-resolution grid engine** projects the labelled points down into the 2.5D ring grid, storing per-cell height statistics, the dominant class, how many points landed there, and a confidence value.
5.  A **live dashboard** renders the colour-coded map, alongside a running comparison of memory used versus a uniform grid.
6.  A **metrics panel** reports accuracy, latency and memory.
### What already exists, and where the gap is
 
-   **ETH Zurich / ANYbotics elevation_mapping and grid_map** --- the standard 2.5D multi-layer map library (storing elevation, variance, traversability per cell), with a GPU-accelerated version (elevation_mapping_cupy). It is *uniform resolution* and not semantically aware of moving objects.
-   **OctoMap / UFOMap** --- **octree**-based \[a tree structure that recursively splits 3D space into eight smaller cubes, letting resolution vary\] multi-resolution *3D* occupancy maps; multi-resolution but full 3D, not 2.5D or semantic.
-   **NVIDIA nvblox** --- GPU-based 3D mapping (30 Hz at 1 cm resolution on a Jetson Orin edge computer); handles dynamic objects but stores a full 3D volume, not a foveated 2.5D map.
-   **Polar/cylindrical learning grids (Cylinder3D, PolarNet)** --- use range-dependent grid partitioning for *segmentation* (hinting at foveation) but don\'t output a distance-adaptive 2.5D *map*.
-   **Moving-object segmentation (LMNet, 4DMOS, MotionBEV)** --- solve the \"is this moving\" problem well, but output labels on individual points, not a compact map.
-   **Existing SIH26053 GitHub attempts** --- several teams already prototype the ring-grid idea; most stop at simple height-threshold heuristics rather than trained models, and lack uncertainty scoring or off-road classes (see Section C6).
**\[Sep 2026 update\] The \"simple height-threshold heuristics\" picture is out of date.** The leading entries now include VRgrid (uncertainty-preserving coarsening, ghost removal, planner-regret evaluation), pushpam2404/sih_053 (a full ROS 2 stack with FAST-LIO2 and Nav2, aimed at Jetson Orin), kaushik521645/lidar-2.5D-mapping-main (RandLA-Net, Kalman-filter anti-ghosting, a fovea that stretches with speed and bends into turns) and LiFovea (Bayesian elevation fusion, CPU-only). Details in C6(f).
 
### The unique differentiator: what nobody ships together
 
A single real-time pipeline combining **semantic segmentation + moving-vs-static labelling + a distance-adaptive 2.5D ring grid**, with a **measured memory-reduction number**, plus:
 
1.  **Concentric-ring grid with seamless boundaries** --- cell size grows with distance, matching how sparse real LiDAR returns actually are far away, with no gaps or misalignment where ring sizes change.
2.  **Per-cell uncertainty/confidence** --- each cell carries a height-variance and a semantic-confidence score, so a planner downstream knows which cells to trust.
3.  **Temporal fusion for moving-object separation** --- removing \"ghost trails\" that moving vehicles otherwise leave behind in an accumulated map.
4.  **Indian/off-road traversability classes** --- beyond simple drivable/non-drivable: gravel, mud, grass, puddle, curb, pothole, cattle, autorickshaw.
**\[Sep 2026 update\] Which of these still set you apart.** Points 1--3 (seamless rings, per-cell uncertainty, ghost removal) now exist in at least one public repo, so treat them as table stakes and beat rivals on *measured* quality. Point 4 (Indian and off-road classes) is still rare --- keep it central. Add:
 
1.  **Planner-level proof** --- show a path planner picks the same route on your compressed map as on the full-resolution map (*planner regret* close to zero).
2.  **Per-range-band accuracy from a genuinely trained model** --- mIoU for 0--10, 10--25, 25--50 and 50--100 m.
3.  **Off-road evaluation on RELLIS-3D** --- DRDO vehicles are not only city cars.
4.  **Degraded-sensor tests** --- dropped beams, rain and dust noise.
5.  **Speed- and heading-adaptive fovea** --- only one public repo does this so far.
### Feature list
 
-   *\"Wow\" features:* a live shrinking memory bar (2 MB vs 128 MB vs 3.2 GB) on the dashboard; a \"foveation\" toggle showing the rings visibly tighten and loosen; a pothole/overhang detector overlay; a before/after slider showing ghost-trail removal; a confidence heat-map layer.
-   *Everyday-utility features:* **ROS 2** \[Robot Operating System 2, the standard robot-software middleware\] output so any robot stack can consume the map; import of standard point-cloud file formats; record-and-replay of frames; an accuracy report broken down by distance; one-click export of the 2.5D map as an image.
## C3. Technical approach
 
### Stack (named libraries + justification)
 
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Tool                                                             What it is                                                                                                                                                                                                     Role here
  ---------------------------------------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ---------------------------------------------------------------------------------------------------------------
  PyTorch                                                          Standard deep-learning framework                                                                                                                                                                               Model training and inference
 
  spconv / MinkowskiEngine / TorchSparse                           **Sparse convolution** \[neural-network math that only computes on cells that actually contain data, skipping empty space\] libraries                                                                          Efficient processing of point clouds turned into voxels
 
  PointNet++ (via Open3D-ML / OpenPCDet / MMDetection3D)           Pioneering point-cloud deep-learning model, plus ready model libraries                                                                                                                                         Fine-tune existing configs rather than build from scratch
 
  Open3D & PCL (Point Cloud Library)                               Point-cloud reading, filtering, ground-fitting tools                                                                                                                                                           Data preprocessing
 
  ROS 2 + rviz2                                                    Robot software middleware + its 3D viewer                                                                                                                                                                      Real robot integration and testing
 
  grid_map library                                                 The ETH Zurich 2.5D grid-map message format                                                                                                                                                                    Output format any robot stack can read
 
  NumPy / CuPy / Numba                                             CPU and GPU array-math libraries                                                                                                                                                                               The grid engine\'s number-crunching
 
  TensorRT / ONNX                                                  NVIDIA\'s inference-speedup toolkit / a portable model format                                                                                                                                                  Making the model run fast enough for real time on edge hardware
 
  Three.js/WebGL or deck.gl + FastAPI                              Browser 3D graphics libraries + a Python web backend                                                                                                                                                           The live dashboard (plays to the team\'s web strengths)
 
  CARLA, NVIDIA Isaac Sim, Gazebo                                  Robotics/driving **simulators**                                                                                                                                                                                Generate synthetic labelled LiDAR data covering Indian/off-road scenes cheaply, without needing real hardware
 
  \[Sep 2026 update\] RandLA-Net (pretrained, via Open3D-ML)       Light, fast point-cloud segmentation network with SemanticKITTI weights available                                                                                                                              The quickest route to a working, trained segmentation baseline
 
  \[Sep 2026 update\] FAST-LIO2 / KISS-ICP                         LiDAR(-inertial) odometry                                                                                                                                                                                      Ego-motion compensation and stitching scans into one map
 
  \[Sep 2026 update\] elevation_mapping_cupy v2.2.0 (ETH Zurich)   GPU 2.5D elevation mapping with visibility cleanup, traversability and semantic layers; ROS 2 Jazzy, CUDA 12; core callback p95 latency cut 55--64%; the core library is MIT-licensed and usable without ROS   The uniform-grid baseline to beat on memory at equal near-field accuracy
 
  \[Sep 2026 update\] Nav2 (Hybrid-A\*, MPPI)                      The ROS 2 navigation stack                                                                                                                                                                                     Planner for the planner-regret test
 
  \[Sep 2026 update\] Rerun                                        Recording and replay viewer for robotics data                                                                                                                                                                  Frame-by-frame debugging and demo replay
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
### Recommended model choice, with realistic benchmark numbers
 
**mIoU** \[mean Intersection over Union --- the standard accuracy score for this kind of task; it measures, on average across all classes, how much a model\'s predicted area overlaps with the true area\] on the standard **SemanticKITTI** benchmark:
 
-   **PointNet++** --- simplest to understand and explain, but lower accuracy and slower on full scans; good for an early prototype.
-   **RangeNet++** --- \~50% mIoU, \~12 FPS \[frames per second\]; converts the scan into a flat \"range image\" for speed.
-   **SalsaNext** --- a published paper (Cortinhal, Tzelepis & Aksoy, 2020) reports \"the highest mean IoU score (59.5%)\" on the SemanticKITTI test set, real-time (\~24 FPS), and *uncertainty-aware* \[it reports how confident it is per prediction\] --- a strong default choice balancing speed and accuracy.
-   **PolarNet** --- \~54--57% mIoU; uses a polar (ring-based) grid, which fits naturally with the foveation idea.
-   **Cylinder3D** --- \~61.8--67% mIoU; more accurate but heavier and slower.
-   **MinkUNet / SPVNAS** --- \~62--66% mIoU; efficient sparse-voxel networks.
-   **Point Transformer V3** --- currently the most accurate, but the heaviest to run.
```{=html}
<!-- -->
```
-   \[Sep 2026 update\] **RandLA-Net** --- light and fast, with pretrained SemanticKITTI weights in Open3D-ML; two public SIH26053 repos already use it. Warning from a rival\'s honest report: an *untrained* segmentation head scored 5.01% mIoU against a 6.64% random baseline. Never demo an untrained model --- judges will ask for your mIoU.
```{=html}
<!-- -->
```
-   **Recommendation:** prototype with PointNet++ for clarity, then move to SalsaNext or MinkUNet for the real-time demo, and compile the final model with TensorRT for speed.
### Determining moving vs static objects
 
Use a dedicated **moving-object segmentation** \[MOS\] module: **LMNet** (compares range images between frames, \~62.5% accuracy on the moving class), **4DMOS** (uses sparse 4D --- space plus time --- convolutions, \~65.2% accuracy, generalises well), or lighter options like **MotionBEV**. Apply **ego-motion compensation** first \[correcting for the vehicle\'s own movement between frames using IMU/odometry, so \"moving\" means moving in the real world, not just relative to the sensor\]. A simpler fallback is comparing frames directly plus a basic object tracker.
 
**\[Sep 2026 update\] Newer and complementary methods.** **FreeDOM** (arXiv:2504.11073, 2025) removes dynamic objects online using *conservative free-space estimation* and reports state-of-the-art results on SemanticKITTI and HeLiMOS. **Ray casting** \[tracing each laser line from the sensor to where it hit and clearing every cell it passed through, because if the beam went through, the space is empty\] removes \"ghost\" trails cheaply, and a **Kalman filter** tracker \[predicts where each moving object will be next frame from its speed\] helps separate moving from static objects.
 
### The variable-resolution grid data structure (detailed design)
 
-   **Concentric rings (recommended):** several rings around the vehicle, each with its own cell size (5 cm → 10 cm → 20 cm → 50 cm), all indexed against one shared fine 5 cm lattice, so a coarse cell is always an exact block of fine cells. This design **eliminates alignment errors and seam gaps** where ring sizes change. Empty cells are stored in a hash map so they cost nothing.
-   **Quadtree** \[a tree that recursively splits 2D space into four quarters\] --- a natural alternative that coarsens hierarchically, though trickier for neighbour lookups.
-   **Log-polar grid** --- cells naturally grow with distance by construction, but is awkward for planners expecting a normal grid layout.
-   **Per-cell data stored:** minimum/maximum/mean height, height variance, point count, dominant semantic class, moving/static flag, and a confidence value.
```{=html}
<!-- -->
```
-   \[Sep 2026 update\] **Welford\'s online algorithm** --- updates a cell\'s mean and variance of height one point at a time without storing every point; numerically stable and cheap.
-   \[Sep 2026 update\] **Uncertainty-preserving coarsening** --- when merging fine cells into a coarse one, keep min, max and variance, not just the average; otherwise a curb vanishes in the far field.
-   \[Sep 2026 update\] **Bayesian elevation fusion** --- treat each cell\'s height as an estimate with uncertainty and update it with every scan, so noisy points do not overwrite good estimates.
-   \[Sep 2026 update\] **Fixed, preallocated memory** --- one rival uses 40-byte cells in a preallocated *spatial hash* \[a lookup table keyed by cell position\]; another guarantees a fixed memory bound. A fixed bound is a strong claim for an embedded vehicle computer.
-   \[Sep 2026 update\] **Prove the seams** --- sih_053 reports zero mismatches over 4 million positions using a 1:2:10 nested lattice. Run the same kind of test on your ring boundaries and show the result.
### End-to-end workflow
 
flowchart LR\
A\[LiDAR frame\] \--\> B\[Ego-motion compensation\]\
B \--\> C\[Ground removal + downsample\]\
C \--\> D\[Segmentation model\]\
D \--\> E\[Moving-object module\]\
E \--\> F\[Class remap: terrain/static/dynamic\]\
F \--\> G\[Project into ring grid\]\
G \--\> H\[Temporal fusion + ghost removal\]\
H \--\> I\[Dashboard + metrics\]
 
### Training, validation and metrics
 
Train on **SemanticKITTI** (plus **nuScenes-lidarseg**), then fine-tune on India-specific and off-road datasets (**IDD-3D**, **RELLIS-3D** --- see Section C6). Report: overall mIoU and per-class accuracy; **accuracy broken down by distance bin** (0--10 m, 10--30 m, 30--100 m) to prove the foveation trade-off is acceptable; latency (milliseconds) and FPS; memory (MB) compared against the two uniform baselines computed in Section C1; and moving-object accuracy separately. (Reality check: off-road perception is genuinely hard --- published state-of-the-art models reach only around 43% mIoU on RELLIS-3D\'s LiDAR data, so set realistic expectations for the off-road split.)
 
**\[Sep 2026 update\] Add these metrics:** memory per ring (not just in total); FPS on CPU and on GPU separately; and **planner regret** \[how much worse a planned route becomes on the compressed map compared with the full-resolution map\]. For RELLIS-3D, the published LiDAR baselines are SalsaNext 43.07% and KPConv 19.07% mIoU --- quote these when you set expectations.
 
## C4. Feasibility and viability
 
### Technical feasibility
 
High. Every component (segmentation models, sparse convolution, ring-grid data structures, moving-object detection) has mature open-source reference implementations and public labelled data. No custom hardware is required to build a strong hackathon prototype --- public datasets and simulators are enough.
 
### Operational feasibility
 
For real vehicle deployment, the target is an **NVIDIA Jetson Orin** --- a small, power-efficient AI computer used in robotics (the top-end AGX Orin model can deliver up to 275 trillion operations per second at low precision; the entry Orin Nano dev kit is around US\$249). NVIDIA\'s own nvblox mapping software already runs at 30 Hz on this class of device, showing the workload is realistic for such hardware. Because the output uses the standard grid_map **ROS 2** message format, it plugs directly into existing robot navigation software.
 
### Economic feasibility
 
-   *LiDAR sensors (optional beyond the hackathon):* prices range from a few hundred dollars for compact solid-state units (e.g., Livox Mid-360, roughly US\$720--765) up to several thousand dollars for high-end spinning sensors (Ouster OS1-32, roughly US\$2,499--4,599). The team needs **none of these** to build and demo the project --- public datasets replace them entirely.
-   *Compute:* model training fits on a single ordinary GPU; the edge target (Jetson Orin) ranges from about US\$249 (Orin Nano) upward.
-   Compared with commercial perception stacks (NVIDIA DRIVE, Applied Intuition, Baidu Apollo), an open, indigenous, memory-light module is both a cost saving and a step toward technology self-reliance.
### Social and legal feasibility
 
India\'s **Motor Vehicles Act, 1988 has no provision for fully autonomous vehicles**, and testing self-driving cars on Indian public roads is not currently legally enabled; the government has stated it will not allow driverless cars in order to protect millions of driving jobs. This actually strengthens the project\'s framing here: it targets **defence UGVs, off-road use, and industrial/mapping applications** --- not public-road robotaxis, which remain legally barred. LiDAR point clouds capture shapes, not faces, so privacy concerns around pedestrians are limited but should still follow good data-handling practice.
 
### Risk and mitigation table
 
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Risk                                                                                                                                                           Likelihood        Impact            Mitigation
  -------------------------------------------------------------------------------------------------------------------------------------------------------------- ----------------- ----------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Domain gap** \[a model trained on one kind of data performing worse on different real-world data\] between Western datasets and Indian/off-road conditions   High              High              Fine-tune on IDD-3D and RELLIS-3D; add synthetic Indian scenes from CARLA/Isaac Sim
 
  Real-time performance too slow                                                                                                                                 Medium            High              Use SalsaNext/MinkUNet; compile with TensorRT/ONNX; use sparse convolutions; reduce detail far away
 
  Boundary artefacts or data loss at ring seams                                                                                                                  Medium            Medium            Shared global lattice so coarse cells are exact blocks of fine cells; blend across seams
 
  False positives from the moving-object detector (\"ghosts\")                                                                                                   Medium            Medium            Ego-motion compensation, temporal fusion, confidence gating
 
  No real LiDAR hardware available                                                                                                                               High              Low               Public datasets plus simulators cover the whole build; borrow a low-cost sensor only if a live demo is wanted
 
  Class imbalance (rare classes like cattle or potholes)                                                                                                         High              Medium            Weighted loss functions; oversampling; synthetic data injection
 
  Scope creep across 6 team members                                                                                                                              Medium            Medium            Fixed module interfaces (a clear data contract) agreed early
 
  \[Sep 2026 update\] Solution looks copied from public repos                                                                                                    Medium            High              Write your own code; credit libraries and papers; make every member able to explain their module. Several rival repos include AI-assistant build specs, so judges may probe understanding
 
  \[Sep 2026 update\] Demoing an untrained or weak model                                                                                                         Medium            High              Use pretrained weights; show a real, per-distance mIoU
 
  \[Sep 2026 update\] Far-field savings smaller than claimed                                                                                                     Medium            Medium            Measure on your sensor model; report map-memory savings separately from compute savings
 
  \[Sep 2026 update\] Large datasets and unreliable finale internet                                                                                              High              Medium            Pre-stage dataset subsets and model weights offline (VRgrid alone uses about 40 GB for three SemanticKITTI sequences)
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
## C5. Impact and benefits
 
### Target audiences
 
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Audience                      Who they are                                                                         Why they need it
  ----------------------------- ------------------------------------------------------------------------------------ ------------------------------------------------------------
  DRDO labs & Indian Army       CAIR, CVRDE, R&DE(E), VRDE and the units they equip                                  UGVs for border patrol, mine-clearing, CBRN reconnaissance
 
  CRPF/BSF                      Central Reserve Police Force / Border Security Force, India\'s paramilitary forces   Border and internal-security robots
 
  ISRO                          Indian Space Research Organisation                                                   Planetary rover terrain mapping (the same core problem)
 
  Mining & agriculture robots   Off-road industrial vehicles                                                         Identical traversability challenge
 
  Indian AV/robotics startups   e.g. Minus Zero, Swaayatt Robots, Flux Auto, Ati Motors, Ottonomy                    An open perception building block
 
  Warehouse/logistics robots    Automated warehouse vehicles                                                         Efficient, low-memory mapping for indoor/outdoor use
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
### Impact by type
 
-   **Social:** fewer road and terrain-related deaths; soldiers kept out of direct danger.
-   **Research:** an open, India-context benchmark for foveated 2.5D mapping and off-road perception classes.
-   **Economic:** indigenous intellectual property reduces dependence on imported perception software.
-   **National security:** a home-grown perception stack for unmanned ground vehicles.
-   **Environmental:** lower memory and compute use means lower power draw on battery-powered robots.
### SDG alignment
 
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  SDG target              What the target says (simplified)                                            How the project maps to it
  ----------------------- ---------------------------------------------------------------------------- --------------------------------------------------------------------
  3.6                     Halve the number of global deaths and injuries from road traffic accidents   Directly: pothole and obstacle detection supports safer navigation
 
  9.1                     Develop quality, reliable, resilient infrastructure                          Supports indigenous perception R&D infrastructure
 
  9.5                     Enhance scientific research and technological capabilities                   Advances India\'s own perception/robotics research base
 
  11.2                    Provide safe, accessible transport systems for all                           Safer autonomous and assisted mobility
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
### Indian mission alignment
 
**Atmanirbhar Bharat** and **Make in India** (indigenous defence technology); **iDEX** \[Innovations for Defence Excellence, the scheme funding defence startups\]; the **DRDO Technology Development Fund** (grants for emerging-tech projects); **NM-ICPS** \[National Mission on Interdisciplinary Cyber-Physical Systems\]; and the **Positive Indigenisation Lists** \[government lists of defence items that must be sourced domestically\], where autonomous systems and robotics are explicit priority areas.
 
## C6. Research and references
 
### (a) Foundational papers
 
-   Qi et al., \"PointNet: Deep Learning on Point Sets for 3D Classification and Segmentation,\" CVPR 2017, arXiv:1612.00593.
-   Qi et al., \"PointNet++: Deep Hierarchical Feature Learning on Point Sets in a Metric Space,\" NeurIPS 2017, arXiv:1706.02413.
-   Zhou & Tuzel, \"VoxelNet,\" CVPR 2018, arXiv:1711.06396.
-   Yan et al., \"SECOND: Sparsely Embedded Convolutional Detection,\" Sensors 2018, 18(10):3337, DOI:10.3390/s18103337.
-   Lang et al., \"PointPillars,\" CVPR 2019, arXiv:1812.05784.
-   Choy et al., \"4D Spatio-Temporal ConvNets: Minkowski Convolutional Neural Networks,\" CVPR 2019, arXiv:1904.08755.
-   Milioto et al., \"RangeNet++,\" IROS 2019, DOI:10.1109/IROS40897.2019.8967762.
-   Cortinhal et al., \"SalsaNext,\" ISVC 2020, arXiv:2003.03653.
-   Zhu et al., \"Cylinder3D,\" CVPR 2021, arXiv:2011.10033.
-   Zhang et al., \"PolarNet,\" CVPR 2020, arXiv:2003.14032.
-   Hornung et al., \"OctoMap: An Efficient Probabilistic 3D Mapping Framework Based on Octrees,\" Autonomous Robots 2013, 34(3):189--206, DOI:10.1007/s10514-012-9321-0.
-   Fankhauser et al., \"Robot-Centric Elevation Mapping with Uncertainty Estimates,\" CLAWAR 2014; Fankhauser & Hutter, \"A Universal Grid Map Library,\" Springer 2016.
-   Mersch et al., \"4DMOS --- Receding Moving Object Segmentation in 3D LiDAR Data Using Sparse 4D Convolutions,\" RA-L 2022, arXiv:2206.04129.
-   Chen et al., \"Moving Object Segmentation in 3D LiDAR Data (LMNet / LiDAR-MOS),\" RA-L 2021, arXiv:2105.08971.
-   Behley et al., \"SemanticKITTI,\" ICCV 2019, arXiv:1904.01416.
-   Caesar et al., \"nuScenes,\" CVPR 2020, arXiv:1903.11027.
-   Jiang et al., \"RELLIS-3D Dataset: Data, Benchmarks and Analysis,\" arXiv:2011.12954.
```{=html}
<!-- -->
```
-   \[Sep 2026 update\] Hu et al., \"RandLA-Net: Efficient Semantic Segmentation of Large-Scale Point Clouds,\" CVPR 2020, arXiv:1911.11236.
-   \[Sep 2026 update\] Thomas et al., \"KPConv: Flexible and Deformable Convolution for Point Clouds,\" ICCV 2019, arXiv:1904.08889.
-   \[Sep 2026 update\] Xu et al., \"FAST-LIO2: Fast Direct LiDAR-Inertial Odometry,\" IEEE T-RO 2022, arXiv:2107.06829.
-   \[Sep 2026 update\] Vizzo et al., \"KISS-ICP,\" RA-L 2023, arXiv:2209.15397.
-   \[Sep 2026 update\] Miki et al., \"Elevation Mapping for Locomotion and Navigation using GPU,\" IROS 2022, arXiv:2204.12876 --- the paper behind elevation_mapping_cupy.
-   \[Sep 2026 update\] Reijgwart et al., \"Wavemap: Efficient volumetric mapping of multi-scale environments using wavelet-based compression,\" RSS 2023.
-   \[Sep 2026 update\] \"Adaptive-LIO,\" arXiv:2503.05077, 2025 --- adaptive multi-resolution maps (0.2 / 0.5 / 1.2 m) outperform a fixed 0.5 m map; published evidence that adaptive resolution helps.
-   \[Sep 2026 update\] \"FreeDOM: Online Dynamic Object Removal Framework for Static Map Construction Based on Conservative Free Space Estimation,\" arXiv:2504.11073, 2025.
### (b) Standards
 
-   **SAE J3016** --- defines the 6 levels (0--5) of driving automation, from no automation to full self-driving.
-   **ISO 26262** --- the international standard for functional safety of automotive electronics.
-   **ASPRS LAS** and **PCD** --- standard file formats for storing point-cloud data.
-   **ROS REP conventions** --- official ROS documents defining coordinate-frame and unit conventions robots should follow.
### (c) Datasets
 
  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Dataset                             What it contains
  ----------------------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  SemanticKITTI                       \~43,000 LiDAR scans, \~19--25 classes, includes moving-object labels; free for non-commercial research
 
  KITTI                               The original detection/odometry driving benchmark
 
  nuScenes / nuScenes-lidarseg        1,000 driving scenes, 32-beam LiDAR, 16 segmentation classes
 
  Waymo Open Dataset                  Large-scale driving data with 64-beam LiDAR
 
  RELLIS-3D                           Off-road dataset (Texas A&M); \"13,556 LiDAR scans and 6,235 images\" across 20 classes including grass, bush, mud and puddle; state-of-the-art models reach only \~43% mIoU here
 
  TartanDrive                         Off-road driving dynamics dataset
 
  IDD-3D (India)                      From IIIT-Hyderabad; \~223,000 3D bounding boxes across 17 categories including autorickshaw and animal, over 5 hours of Hyderabad driving --- the India-specific dataset. Note: it provides 3D bounding boxes, not dense per-point labels, so some extra work (pseudo-labelling) is needed to use it for full segmentation training
  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
### (d) Existing tools and prior art
 
*Open-source:* ANYbotics elevation_mapping/grid_map, OctoMap, UFOMap, Voxblox, NVIDIA nvblox, Autoware (an open self-driving software stack --- its occupancy-grid module has \"no special support for moving objects,\" a gap this project fills), OpenPCDet, MMDetection3D, Open3D-ML. *Commercial:* NVIDIA DRIVE, Applied Intuition, Baidu Apollo.
 
**\[Sep 2026 update\] Tool updates:** elevation_mapping_cupy v2.2.0 (github.com/leggedrobotics/elevation_mapping_cupy) adds ROS 2 Jazzy and CUDA 12 support and cuts core callback p95 latency by 55--64%; its core is published separately without ROS (leggedrobotics/elevation_mapping_cupy_core, MIT licence), and a Jetson Orin / ROS 2 Humble port exists (iit-DLSLab/elevation_mapping_gpu_ros2). Also useful: FAST-LIO2, KISS-ICP, Nav2 and Rerun.
 
### (e) Competitive gap
 
No open system currently delivers semantic segmentation + moving-object detection + distance-adaptive 2.5D mapping, with a measured memory-reduction claim, in one real-time pipeline tuned for Indian/off-road terrain.
 
### (f) Existing SIH26053 GitHub repositories (the baseline to beat)
 
Multiple public repos already target this exact problem statement: Stxtics03/vrgrid and victorysingh/vrgrid-26 (Team \"Chronicles.exe\" --- a deterministic, memory-bounded foveated 2.5D grid with uncertainty preservation and dynamic-ghost removal; currently the most advanced), saxenaatharv/3D\--2.5D-LIDAR (RandLA-Net via Open3D-ML, three super-classes, sparse ring grid), p3iyanshu/RakshaSetu and Xxnil-nxX/RrakshaSetu (Team \"JanSetu\" --- PointNet++ plus a FastAPI/React dashboard), AbhayVerma628/SIh26053_Lidar, sih26053/LiDAR, and sstharun08/Adaptive-Variable-Resolution-2.5D-LiDAR-Mapping. The concept is not novel by itself; the way to win is through rigour --- real trained models rather than simple height rules, off-road and Indian-specific classes, per-cell uncertainty, and a polished, quantified memory demonstration.
 
**\[Sep 2026 update\] New repositories found since the original list** (reported figures are the teams\' own claims):
 
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Repository                                                          What it does                                                                                                                                                         What to learn from it
  ------------------------------------------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------- ------------------------------------------
  Stxtics03/vrgrid (updated)                                          Fixed 8.94 MB bound; uncertainty-preserving coarsening; ghost removal; planner-regret evaluation; Rerun dashboard; SemanticKITTI sequences 00, 07, 08; MIT licence   Still the strongest benchmark to beat
 
  pushpam2404/sih_053                                                 ROS 2: Ouster OS1-64 → FAST-LIO2 → dynamic-obstacle node → foveated 2.5D engine → Nav2; Jetson Orin, CUDA/TensorRT, Docker                                           Deployment realism and honest metrics
 
  akumar4be26-crypto/LiFovea                                          CPU-only NumPy pipeline; 64-beam simulator with ground truth; Bayesian fusion; 0.8 m navigation tiles with A\*; 44 tests                                             Simulated ground truth; navigation tiles
 
  kaushik521645/lidar-2.5D-mapping-main                               RandLA-Net; Kalman anti-ghosting; speed- and steering-adaptive fovea; FastAPI + WebSocket + deck.gl at up to 30 FPS                                                  Dashboard and dynamic-fovea ideas
 
  darshan-stack/DRDO                                                  \"Feedback-foveated elevation mapping\" scaffold; uniform baseline first, adaptive features in stages                                                                Clean staging plan
 
  siddhantkadu0001/AVLM-Adaptive-Variable-resolution-Lidar-Mapping-   Quadtree grid; Streamlit dashboard; FPS measurement                                                                                                                  Quadtree alternative to rings
 
  heetkakaria45-bit/LiDAR_Syntrix                                     Semantic elevation grid; curbs, speed bumps, potholes; overhang handling                                                                                             Hazard-focused framing
 
  huggingface.co/spaces/prachiee/sih-26053-lidar-mapping              Browser demo with camera boxes and a 3D point cloud                                                                                                                  Hosted demos are appearing
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
### (g) Indian government/DRDO publications
 
DRDO\'s \"Technologies for Autonomous Unmanned Ground Vehicle\" project page; MoRTH\'s \"Road Accidents in India\" annual reports; PIB releases on iDEX, the DRDO Technology Development Fund, and the Positive Indigenisation Lists; DRDO CAIR/CVRDE/R&DE(E)/VRDE UGV programme materials.
 
### (h) Video and community resources (Sep 2026 update)
 
-   No video walkthrough dedicated to SIH26053 was found, and the PS lists no video link.
-   General SIH 2026 problem-selection videos are the same as in B6(h).
-   For learning, search for talks and tutorials on elevation_mapping_cupy, SemanticKITTI with RandLA-Net, and FAST-LIO2 on ROS 2.
## C7. Pitfalls and likely judge questions (Sep 2026 update)
 
Pitfalls to avoid:
 
-   **Assuming far-field foveation saves compute** --- measure it; most returns are near the vehicle.
-   **Demoing an untrained model** --- use pretrained weights and show the real number.
-   **Unstaged data** --- SemanticKITTI is tens of gigabytes; stage it before the finale.
-   **Copying public repos** --- originality and understanding will be probed.
Questions to rehearse:
 
1.  \"What is your mIoU at 50 m versus 5 m?\"
2.  \"How much memory do you save, and measured against what baseline?\"
3.  \"Show us that a curb or pothole survives coarsening.\"
4.  \"What happens at the ring boundaries?\"
5.  \"How do you remove a car that drove through the scene?\"
6.  \"Will it run on an embedded board such as a Jetson Orin?\"
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
  NTRO                    National Technical Research Organisation                          India\'s technical intelligence agency; issuer of SIH26147 (SIH26053 is issued by DRDO)
 
  SIH                     Smart India Hackathon                                             National hackathon run by the Ministry of Education and AICTE
 
  AICTE                   All India Council for Technical Education                         Regulator of technical education; co-organises SIH
 
  PS                      Problem Statement                                                 A challenge posted in SIH, with an ID such as SIH26147
 
  MeitY                   Ministry of Electronics and Information Technology                Ministry for IT policy
 
  MoD                     Ministry of Defence                                               Defence ministry
 
  DRDO                    Defence Research and Development Organisation                     India\'s defence R&D agency
 
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
  SDG 3                               Good health and well-being
 
  3.6                                 Halve global deaths and injuries from road traffic accidents
 
  SDG 9                               Industry, Innovation and Infrastructure
 
  9.1                                 Develop quality, reliable, sustainable and resilient infrastructure
 
  9.c                                 Significantly increase access to information and communications technology
 
  9.5                                 Enhance scientific research and technological capabilities
 
  SDG 11                              Sustainable cities and communities
 
  11.2                                Safe, affordable, accessible transport systems for all
 
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
 
## Glossary D --- LiDAR, robotics and autonomous-vehicle terms (A--Z)
 
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Term                        Full form                                                  Plain-English meaning
  --------------------------- ---------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------------
  2.5D map                    ---                                                        A top-down grid where each cell also stores height information (partway between a flat 2D map and a full 3D model)
 
  3D voxel grid               ---                                                        Space divided into tiny cubes (voxels); accurate but memory-heavy
 
  ADAS                        Advanced Driver-Assistance Systems                         Features like automatic braking or lane-keeping (SAE Level 1--2)
 
  Autoware                    ---                                                        An open-source self-driving software stack
 
  Bayesian elevation fusion   ---                                                        Treating each cell\'s height as an estimate with uncertainty and refining it with each new scan
 
  BEV                         Bird\'s-Eye View                                           A top-down representation of a scene
 
  CAIR                        Centre for Artificial Intelligence & Robotics              DRDO lab in Bengaluru working on AI and robotics
 
  CARLA                       ---                                                        An open-source driving simulator used to generate synthetic sensor data
 
  CBRN                        Chemical, Biological, Radiological, and Nuclear            Category of hazards requiring special reconnaissance
 
  CVRDE                       Combat Vehicles Research and Development Establishment     DRDO lab in Chennai; ran Project MUNTRA
 
  CUDA                        ---                                                        NVIDIA\'s programming platform for running code on GPUs
 
  CuPy                        ---                                                        A NumPy-like library that runs array math on NVIDIA GPUs
 
  Dynamic object              ---                                                        An object that can move (e.g. a pedestrian or vehicle), as opposed to static terrain or obstacles
 
  Ego-motion compensation     ---                                                        Correcting sensor data for the vehicle\'s own movement between frames, so \"motion\" reflects the real world, not the sensor
 
  Elevation map               ---                                                        A grid storing terrain height per cell
 
  elevation_mapping_cupy      ---                                                        ETH Zurich\'s open-source GPU 2.5D elevation-mapping library
 
  FAST-LIO2 / KISS-ICP        ---                                                        Open-source LiDAR(-inertial) odometry methods that estimate the vehicle\'s own motion
 
  FPS                         Frames Per Second                                          How many sensor frames the pipeline processes each second; higher means more real-time
 
  Foveated / foveation        ---                                                        Named after the eye\'s fovea (sharp-focus centre): high detail near the centre of attention, lower detail further away
 
  Ghost (dynamic ghost)       ---                                                        A stale height trail left in a map by a moving object; looks like a phantom wall to a planner
 
  GNSS / RTK                  Global Navigation Satellite System / Real-Time Kinematic   Satellite positioning; RTK adds centimetre-level accuracy
 
  GUI                         Graphical User Interface                                   Software with windows, buttons and charts rather than typed commands
 
  iDEX                        Innovations for Defence Excellence                         India\'s scheme funding defence startups and MSMEs
 
  IED                         Improvised Explosive Device                                A homemade or non-standard bomb
 
  IMU                         Inertial Measurement Unit                                  A sensor measuring acceleration and rotation, used to track motion
 
  Isaac Sim                   ---                                                        NVIDIA\'s robotics simulator
 
  Jetson (Orin)               ---                                                        NVIDIA\'s family of small, power-efficient AI computers used in robots
 
  Kalman filter               ---                                                        A method that predicts an object\'s next position from its motion and corrects it with each measurement
 
  LiDAR                       Light Detection And Ranging                                A sensor that fires laser pulses and measures their return time to build a 3D point cloud
 
  mIoU                        mean Intersection over Union                               The average accuracy score across all classes in a segmentation task
 
  MoRTH                       Ministry of Road Transport and Highways                    The Indian ministry publishing annual road-accident statistics
 
  MOS                         Moving Object Segmentation                                 Separating moving objects from static ones in sensor data
 
  MUNTRA                      ---                                                        A DRDO/CVRDE project converting BMP-II carriers into unmanned ground vehicles
 
  Nav2 / MPPI                 Navigation 2 / Model Predictive Path Integral              The ROS 2 navigation stack / a sampling-based controller that follows the planned path
 
  Nested lattice              ---                                                        Coarse cell sizes chosen as whole multiples of the finest cell so every fine cell sits inside exactly one coarse cell
 
  Occupancy grid              ---                                                        A 2D map where each cell records whether space is free or occupied
 
  Octree                      ---                                                        A tree structure recursively splitting 3D space into eight cubes, enabling multi-resolution 3D maps
 
  Odometry                    ---                                                        Estimating a vehicle\'s own movement from its sensors
 
  Planner regret              ---                                                        How much worse a planned route becomes on a compressed map than on the full-resolution map
 
  Point cloud                 ---                                                        A set of 3D points describing surfaces in a scene, produced by LiDAR
 
  Quadtree                    ---                                                        A tree structure recursively splitting 2D space into four quadrants, enabling multi-resolution 2D/2.5D grids
 
  R&DE(E)                     Research & Development Establishment (Engineers)           DRDO lab in Pune working on lighter UGVs
 
  RandLA-Net                  ---                                                        A light, fast neural network for segmenting large point clouds
 
  Ray casting                 ---                                                        Tracing each laser beam from sensor to hit point and clearing the cells it passed through
 
  RELLIS-3D                   ---                                                        An off-road LiDAR and camera dataset from Texas A&M with classes such as grass, mud and puddle
 
  Rerun                       ---                                                        A tool for logging, visualising and replaying robotics data
 
  Ring / range band           ---                                                        A circular zone around the sensor with its own cell size
 
  ROS 2                       Robot Operating System 2                                   The standard software middleware connecting a robot\'s sensors, processing and actuators
 
  SAE levels                  SAE J3016                                                  The standard scale (0--5) for how automated a vehicle\'s driving is
 
  Semantic segmentation       ---                                                        Labelling every point or pixel with a category (e.g. road, wall, person)
 
  SemanticKITTI               ---                                                        The standard labelled LiDAR driving dataset for point-cloud segmentation
 
  Sparse convolution          ---                                                        Neural-network math that only computes on cells that actually contain data, skipping empty space
 
  Spatial hash                ---                                                        A lookup table keyed by cell position, so empty cells take no memory
 
  Static obstacle             ---                                                        A fixed object that does not move (e.g. a wall or pole)
 
  Terrain analysis            ---                                                        Determining which parts of the ground are safe/possible to drive on
 
  TensorRT / ONNX             ---                                                        NVIDIA\'s model-speedup toolkit / a portable format for trained models
 
  Traversability              ---                                                        How easily a robot or vehicle can drive over a given piece of terrain
 
  UGV                         Unmanned Ground Vehicle                                    A robotic ground vehicle with no onboard driver
 
  Voxel                       ---                                                        A 3D pixel; a small cube of space
 
  VRDE                        Vehicle Research and Development Establishment             DRDO lab in Ahmednagar working on wheeled UGVs
 
  Welford\'s algorithm        ---                                                        A stable way to update a running mean and variance one value at a time
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 
# RECOMMENDATIONS AND CAVEATS
 
## Recommendations
 
1.  **Pursue both, but state each hard limit up front.** For SIH26147, disclose that absolute sample rate and centre frequency need metadata, and that blind FEC and de-interleaving are catalogue-bounded and probabilistic. For SIH26053, disclose that off-road segmentation accuracy is modest (about 43% mIoU is state of the art on RELLIS-3D) and report accuracy by distance band. NTRO and DRDO judges reward honesty over **overclaiming** \[promising more than you can deliver\].
2.  **Win on the whitespace, not the crowded part.** For 26147, ground-truth verification (CRC, sync word, re-encode BER) and SigMF-native indigeneity remain your identity, but \[Sep 2026 update\] rivals now have them too, so add real over-the-air validation, low-SNR curves and multi-signal handling. For 26053, lead with a measured memory reduction, Indian and off-road classes, and a planner-regret proof that compression costs nothing that matters.
3.  **Build the ground-truth labs in weeks 1--2.** Both projects depend on labelled data you control: a synthetic GNU Radio / TorchSig corpus for 26147, and dataset subsets plus CARLA or Isaac Sim scenes for 26053. Demonstrable labelled test sets are the strongest credibility signal for evaluators.
4.  **Lead every pitch with India numbers**: 1,951 GPS-interference incidents, ₹31.64 lakh crore digital economy, and the Krypto500 import case (about US\$7,400, ITAR-controlled) for 26147; 1,68,491 road deaths in 2022 and 4,446 pothole accidents, plus DRDO\'s UGV programme, for 26053.
5.  **Benchmark explicitly against the named GitHub repos**, with a one-slide **competitive matrix** \[a table comparing your features against competitors\'\]. \[Sep 2026 update\] Name the leaders: Team Vertex, Devansh-567 and ICHNOVA for 26147; VRgrid, sih_053 and LiFovea for 26053.
6.  **Sequence the build for 6 members.**
    a.  26147: DSP core + AMC + visualisation first; FEC and de-interleaving as the **stretch goal** \[an extra target attempted only after the core is done\].
    b.  26053: pretrained segmentation + grid engine + memory dashboard first; moving-object and ghost removal plus off-road fine-tuning second; Jetson / TensorRT optimisation last.
    c.  Both suit AI/ML + full-stack + UI/UX skills with no hardware fabrication.
7.  \[Sep 2026 update\] **Submit before 30 September 2026.** No official clarifications have appeared; do not wait for them.
8.  \[Sep 2026 update\] **Study, don\'t copy.** Use the leading repos as benchmarks to beat and keep novelty claims narrow and defensible --- as VRgrid does by stating it does not claim to invent foveated or multi-resolution mapping.
9.  \[Sep 2026 update\] **Pre-stage all data and model weights offline** (RadioML / TorchSig sets, SemanticKITTI and RELLIS-3D subsets, pretrained RandLA-Net). Finale connectivity is not guaranteed.
## Caveats (limits of the evidence)
 
-   Some statistics are **vendor-sourced** \[published by a company selling related products, so potentially biased\] or are forecasts: the 5G and digital-economy figures (GSMA \"could benefit\", MeitY projections) are projections, not achieved outcomes.
-   Beyond the 1,951 GPS-interference figure, clean annual counts of Indian radio-interference complaints could not be sourced. Only the monitoring-station count (28) and the GPS figure are firmly documented. A Parliament question or WPC annual report would be needed for more.
-   Commercial SIGINT pricing is mostly quotation-only or export-controlled. Only Krypto500 (\~US\$7,400) and Wavecom W-CODE entry (\~US\$995, reseller-listed) have public figures.
-   The SIH26053 memory figures in C1 are worked estimates that depend on what each cell stores; rival repos use different accounting.
-   \[Sep 2026 update\] sih.gov.in blocked automated access during the September 2026 check, so PS text, themes and idea counts come from unofficial mirrors that sometimes disagree (on themes and on the total number of PS: 226 to 240 at different dates). Re-check both PS on the official portal before submitting.
-   \[Sep 2026 update\] Figures quoted from rival GitHub repos (memory ratios, test counts, accuracies) are the teams\' own claims and were not independently verified.
-   \[Sep 2026 update\] No video content specific to either PS exists yet; the linked videos are general or for learning.