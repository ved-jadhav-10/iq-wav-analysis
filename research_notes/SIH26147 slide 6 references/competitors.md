# Competitive analysis: commercial and open-source signal-analysis tools (SIH26147 slide 6)

Columns being filled: Auto Modulation ID | Blind FEC / De-interleave | Open & ITAR-free | Automated IQ -> Bits.
Research date: 29 Sep 2026. PDFs were downloaded and text-extracted locally; quotes below are verbatim from that text.

**Headline correction for the slide:** two rivals document automatic FEC-code recognition, so a "no rival does blind FEC" cell would be an overclaim:
- R&S CA250: "fully automated detection of convolutional, Reed-Solomon and BCH codes".
- Wavecom W-BitView: a "Convolutional Code Analysis" function that finds K, k, n and the generator polynomials.

No vendor documents *automatic* interleaver-parameter recovery. Their de-interleavers take parameters the analyst enters. Safe wording: "blind FEC + interleaver recovery chained automatically from IQ, with evidence" — not "only we do blind FEC".

---

## 1. Krypto500 / Krypto1000 (COMINT Consulting LLC, USA)

### Takeaway
Krypto500 is a narrowband (up to 48 kHz) known-modem classifier and decoder suite. Its vendor material says it is ITAR-controlled. The modem count differs by document: "nearly 4000" in the older brochure, "4000+" in the 2020 brochure, and "more than 3,000" on the current site. The US$7,400 price comes from a February 2012 magazine review, not from the vendor. No blind FEC or de-interleaving tool is documented: the "bit stream analysis" claims are generic.

### Cited Findings
- **Bandwidth:** "Krypto500 is for Narrowband (NB) signals up to 48 kHz in bandwidth principally found between ELF-SHF"; "Its companion suite, Krypto1000 is for wideband signals 48 kHz and wider" — [Krypto500 brochure (datatec.es mirror)](https://datatec.es/wp-content/uploads/2016/04/Krypto500.pdf). The 2020 brochure says the same but "principally found in HF" — [Krypto500 brochure 2020 (aventasinc.com mirror)](https://aventasinc.com/wp-content/uploads/2021/08/Krypto500.pdf).
- **Classification count, older brochure:** "AUTOMATIC CLASSIFICATION OF NEARLY 4000 FSK & PSK MODEMS AND USERS" — [datatec.es brochure](https://datatec.es/wp-content/uploads/2016/04/Krypto500.pdf). The PDF metadata dates to 2012, and it lists Windows 8.1 support, so the text is from roughly 2013–2015. It is hosted in a 2016/04 folder.
- **Classification count, 2020 brochure:** "AUTOMATIC PRECISION CLASSIFICATION OF 4000+ TARGET MODEMS" — [aventasinc.com brochure, PDF created 30 Aug 2020](https://aventasinc.com/wp-content/uploads/2021/08/Krypto500.pdf).
- **Classification count, current site:** "Real-time precision modem classification of more than 3,000 modems" — [comintconsulting.com/krypto500](https://www.comintconsulting.com/krypto500). The three documents give different numbers; the current site is the most conservative.
- **Decoders:**
  - Brochure: "COMINT Consulting offers hundreds of decoders for current, on-air modes ranging from ELF to SHF", and "decoding and parsing tools and receiver control for several hundred signals" — [datatec.es brochure](https://datatec.es/wp-content/uploads/2016/04/Krypto500.pdf).
  - Site: "325+ more HF signal decoders than any other digital signals decoder software" — [comintconsulting.com/krypto500](https://www.comintconsulting.com/krypto500). This is a comparative marketing claim, not an absolute count.
- **ITAR, 2020 brochure:** "Krypto500 is controlled by the US International Traffic in Arms Regulations (ITAR) 22 CFR §120-130. It may not be exported or transferred to any other foreign person, foreign country or foreign entity without prior written approval from the U.S. Department of State and COMINT Consulting LLC." — [aventasinc.com brochure](https://aventasinc.com/wp-content/uploads/2021/08/Krypto500.pdf).
- **ITAR, older brochure:** the older Krypto500 brochure's footer names *Krypto1000* as ITAR-controlled, with the same wording — [datatec.es brochure](https://datatec.es/wp-content/uploads/2016/04/Krypto500.pdf). No ITAR statement was found on the current Krypto500 web page (WebFetch summary of [comintconsulting.com/krypto500](https://www.comintconsulting.com/krypto500)).
- **Inputs and outputs:**
  - Inputs: "Baseband Audio", "Numerous file formats (WAV, RF64, QVRT, etc)", "I&Q (numerous formats)", "VITA49 I&Q input", "DoD RedHawk SDR support".
  - Outputs: "Demodulate bitstream to screen / … to ASCII file / … to hexadecimal", "VITA49", "MidasBlue (XMidas)".
  - Source: [aventasinc.com brochure](https://aventasinc.com/wp-content/uploads/2021/08/Krypto500.pdf).
- **Analysis claims:**
  - 2020 brochure: "A comprehensive set of spectrum and parametric analysis tools for external and internal measurements, identification of complex synchronization, timing and cryptographic systems"; "FLEXIBLE VARIETY OF OUTPUTS TO SUPPORT CRYPTANALYSIS" — [aventasinc.com brochure](https://aventasinc.com/wp-content/uploads/2021/08/Krypto500.pdf).
  - Site: "bit stream ANALYSIS software and advanced SIGINT tools" — [comintconsulting.com/krypto500](https://www.comintconsulting.com/krypto500).
  - Neither the brochures nor the Krypto500 page mentions FEC-code recognition, error-correction analysis or de-interleaving.
- **Licensing on the site:** "1 License / 10+ Instances / 32 Modules/instance / ~320 Channels" — [comintconsulting.com/krypto500](https://www.comintconsulting.com/krypto500). No price is shown there.
- **Where the US$7,400 figure comes from:** Nils Schiffhauer (DK8OK), *Monitoring Quarterly* no. 1, February 2012: "The most recent one is named Krypto500. It has been developed in the Czech Republic, and is distributed by their website. At a price tag of US-$ 7400 or nearly 6000 Euros, it plays in the same league as e.g. Wavecom's W-PC or Hoka's Code300-32P. In this realm of decoders, GX430 of Rohde & Schwarz reigns king." — [addx.org archive PDF](https://www.addx.org/textarchiv/Krypto500-1.pdf).
- **The same 2012 review on classifiers:** "Only GX430 and W-PC (with options) do offer a general and automatic classification. GX430 does the best job ever seen in this respect"; "automatic classification with all decoders without GX430 is giving you nothing more than a bit of assistance" — [addx.org archive PDF](https://www.addx.org/textarchiv/Krypto500-1.pdf).

### Inferences
- The US$7,400 figure is **third-party and 14 years old** (2012), from before the current licensing model. Do not present it as a current price. If it's used at all, cite it as: "US$7,400 in 2012 (Monitoring Quarterly review); no current public price".
- "Hundreds of decoders" is safe. "~4,000 modems classified" is supported by brochures, but the vendor's own current site says ">3,000", so ">3,000 modems" is the safest wording.
- For "Blind FEC / De-interleave": "not documented publicly".
- For "Automated IQ -> Bits": yes, for known modems (classification, then decode or bitstream output). For unknown modems there's no documented automated path.

### Gaps
- No vendor-published price was found anywhere. A current price is UNCONFIRMED.
- Whether the "more than 3,000" count on the current site replaces the older "nearly 4000" or counts differently isn't explained.
- The 2012 review says Krypto500 was "developed in the Czech Republic". How that relates to the current US LLC wasn't researched.

---

## 2. Wavecom W-CODE / W-BitView (Wavecom Elektronik AG, Switzerland)

### Takeaway
W-CODE has an automatic modulation classifier plus a table-driven "Classifier Code Check" for known modes, and more than 226 modes in the 2015 brochure. W-BitView is a manual bitstream workbench, but it includes an **automatic convolutional-code parameter search**. De-interleaving takes parameters the user enters. No public price appears on Wavecom's own material. The US$995 figure traces only to low-quality pages.

### Cited Findings
- **Scope and classification:** "Automatic classification, code check, demodulation and decoding to content level of known signals"; "Automatic code check of known signals and unknown, pre-defined signals"; "Supports more than 226 HF, VHF, UHF and satellite decoder modes and protocols without additional, costly licensing" — [W-CODE brochure 2015 (hik-consulting.pl mirror)](https://www.hik-consulting.pl/files/brochure_w-code.pdf).
- **Classifier parameters:** "Modulation type", "Baud rate or symbol rate", "Signal center frequency", "Number of carriers", "Frequency shift", "Carrier spacing or distance". Bandwidths: "8 kHz bandwidth (W-Classifier-NB…)" and "Bandwidth up to 96 kHz" / "Baud rates up to 60 kBd" (W-Classifier-WB) — [W-CODE brochure](https://www.hik-consulting.pl/files/brochure_w-code.pdf).
- **How the Classifier Code Check works:** "The classifier attempts to classify the input signals according to their modulation formats. The table check will check the signal against the entries of the selected mode list. The code check will attempt to synchronize against classified modes, finally the signal will be forwarded to a decoder for output." — [W-CODE brochure](https://www.hik-consulting.pl/files/brochure_w-code.pdf).
- **Analysis functions:** "Autocorrelation up to 200.000 bits"; "Automatic CRC recognition of all PACTOR-II and PACTOR-II-FEC systems"; "Bit correlation analysis. Raw FSK analysis - graphical display of demodulated data on a raster time line"; "Synchronized PSK and FSK raw bitstream available" — [W-CODE brochure](https://www.hik-consulting.pl/files/brochure_w-code.pdf).
- **Price in the brochure:** "Prices http://www.wavecom.ch/contact-us.php" — [W-CODE brochure](https://www.hik-consulting.pl/files/brochure_w-code.pdf). That is, quotation-only in vendor material.
- **W-BitView purpose:** "WAVECOM-BitView (W-BV) enables the user to analyze any bit stream… The tools are targeted at users with experience in bit stream analysis. To understand some of the functions a comprehensive mathematical knowledge is a prerequisite." — [W-BitView Manual V2.5.00 (2012)](https://www.wavecom.ch/content/pdf/manual_w-bitview-v2-5-00.pdf).
- **W-BitView blind convolutional-code search:** "Convolutional Code Analysis … Find the parameters of convolutional encoded bit streams. The function returns constraint length (K), number of input bits per shift cycle (k), number of output bits per shift cycle (n) and generator polynomials. The function will search for K = 2..14, and n = 2..4." — [W-BitView Manual V2.5.00](https://www.wavecom.ch/content/pdf/manual_w-bitview-v2-5-00.pdf).
- **W-BitView de-interleaving is parameter-driven:**
  - "De-Interleaving Block … Change the bit order according to the settings of Block length, Frame length and Interleaving distance."
  - "Bit Sync Analysis is designed to find the starting position of a frame … all bits are displayed in a graphical view with an adjustable number of bits per line; this makes it easier to find periodic sequences." (a manual raster aid)
  - Source: [W-BitView Manual V2.5.00](https://www.wavecom.ch/content/pdf/manual_w-bitview-v2-5-00.pdf).
- **Other W-BitView functions** (table of contents): "BCH-Decoding", "General Reed Solomon Decoding" (the user configures k, n–k and the primitive polynomial), "CRC (1..32)", "Descrambler (PN)", "Autocorrelation", "STANAG-4285 Deinterleaver" — [W-BitView Manual V2.5.00](https://www.wavecom.ch/content/pdf/manual_w-bitview-v2-5-00.pdf).
- **Company:** "More than 95% of all units sold are exported. The majority of the customers are government agencies, defense organizations and the telecommunication industry." "Source code is available for government bodies." — [W-BitView Manual V2.5.00](https://www.wavecom.ch/content/pdf/manual_w-bitview-v2-5-00.pdf).
- **Search provenance of US$995:** the figure appeared only in a search-engine summary of a sites.google.com page titled "Wavecom W Code Digital Data Software Decoder" — [sites.google.com page](https://sites.google.com/view/wavecom-w-code-digital-data-s). That page type is typically SEO or "download" spam, not a reseller listing. The US reseller Computer International ([computerint.com/WAVECOM-W-CODE](https://computerint.com/WAVECOM-W-CODE)) could not be fetched (DNS failure).

### Inferences
- "Auto Modulation ID": yes, documented (W-Classifier).
- "Blind FEC": **partly**. W-BitView documents automatic convolutional-code parameter recovery (as of a 2012 manual). RS and BCH are decode-with-given-parameters. Say "blind conv-code search in a separate manual tool", not "no blind FEC".
- "Blind de-interleave": not documented as automatic; the user sets the parameters.
- "Automated IQ -> Bits": for known modes, yes (classify → code check → decode). For unknown signals, the analyst drives W-BitView by hand.

### Gaps
- The US$995 price is UNCONFIRMED; the source is low quality. Do not put it on the slide.
- No Wavecom export-control statement was found. The wavecom.ch homepage fetch returned no specs, and the brochure and manual carry none. Export status is UNCONFIRMED; don't claim either "controlled" or "uncontrolled".
- The current mode count wasn't found: the 2015 brochure says ">226", and older in-repo notes say "300+", unverified here. Whether the current W-BitView adds features beyond V2.5.00 (2012) wasn't checked.

---

## 3. PROCITEC go2signals (go2MONITOR, go2DECODE, go2signal-analyzer, go2ANALYSE; Germany)

### Takeaway
go2DECODE and go2signal-analyzer do automatic modulation classification and modem recognition against a known-modem database ("more than 470 modems" in the July 2026 specs). They also give manual displays for unknown signals, including a raster ("Hell") display for coding analysis. go2ANALYSE is an analyst-driven bitstream tool. It has automatic periodic- and non-periodic-sequence search and "testing against codes" (Hamming, RS, BCH, Golay, CRC), plus parameter-driven de-interleaving, Viterbi and Berlekamp-Massey. Export permission is required for the MIL and PMR decoder packages and for go2key.

### Cited Findings
- **Product positioning (July 2026 specs):** go2DECODE STANDARD: "Software for detection, demodulation, decoding and analysis of known and unknown radio signals", "Knowledge based recognition approach", "Automatic production of signal content" — [PROCITEC Analysis Suite Technical Specifications v26.2, July 2026](https://procitec.com/application/files/3217/8297/2729/PRO_Analysis_Suite_Tech.Specs._26.2.pdf).
- **go2signal-analyzer:** "Integrated automatic modulation classifier with modem classification feature"; "Multiple analysis displays like waterfall, spectrum, histogram, autocorrelation, constellation, scatter, bit, etc."; "High performance blind equalizer supporting many different PSK and QAM modulation types from PSK2, 4, 8, 16, 32 up to QAM4, 8,16, 32, 64, 128"; "Database with more than 470 modems and their different modes"; classifier "Max. signal bandwidth 50 kHz"; a footnote marks some classifier entries "Includes ML/AI technology" — [Tech Specs v26.2](https://procitec.com/application/files/3217/8297/2729/PRO_Analysis_Suite_Tech.Specs._26.2.pdf).
- **go2DECODE recognition:** "Working in changing signal scenarios needs a decoder with automatic modem recognition … go2DECODE checks the input signal for the predefined modem types" — [go2DECODE brochure 22.1](https://procitec.com/file_access/6816/4250/3024/PRO_Broschure_go2DECODE_22.1_lres.pdf).
- **go2DECODE unknown signals:** "New and unidentified signals can be automatically or manually recorded. These recordings are used for signals analysis, measuring modulation and coding parameters." The tools are "Spectrogram and spectrum displays for FFT analysis and baud rate measurement", "Autocorrelation display to highlight signal repetitions", "Constellation display for phase modulation analysis", "Analysis display to measure amplitude, frequency and phase behavior" and "Raster ('Hell') display for coding analysis" — [go2DECODE brochure 22.1](https://procitec.com/file_access/6816/4250/3024/PRO_Broschure_go2DECODE_22.1_lres.pdf).
- **go2ANALYSE, specs v26.2:** "Software for analysis, evaluation and manipulation of recorded bitstreams to determine the characteristics of the coding used".
  - Analysis: "Automatic search for periodic sequences", "Automatic search for non-periodic sequences", "Testing against codes: Hamming, Reed-Solomon, BCH, Golay, CRC".
  - Manipulation: "Deinterleaving", "Demultiplexing", "Viterbi correction", "Descrambling".
  - "Tools for LFSR".
  - Source: [Tech Specs v26.2](https://procitec.com/application/files/3217/8297/2729/PRO_Analysis_Suite_Tech.Specs._26.2.pdf).
- **go2ANALYSE, 2021 brochure:** "Check and verify unidentified bitstreams against [known & existing decoders]", "Identify previously unrecovered coding details and parameters", "Berlekamp-Massey", "Linear complexities". Also: "Data Signals Analysts and technical experts must use their expertise (and often hours!) and manual bitstream analysis techniques to develop a functional signal / protocol decoder as solution. For these manual bitstream analysis and development initiatives, go2analyse is the tool of choice." — [go2ANALYSE brochure (2021)](https://procitec.com/file_access/3616/2195/5265/PROCITEC_Broschure_go2ANALYSE.pdf).
- **Export conditions:** "MIL decoder package¹" and "PMR decoder package²" are options. "1) In case of an export from the Federal Republic of Germany an export permission must be granted by the German authorities. Enduser certificate is required." "2) In case of an export from the European Union an export permission must be granted by the German authorities. Enduser certificate is required." go2key "Requires export approval prior to supply". Licence: "USB-Dongle (CodeMeter) as default" — [Tech Specs v26.2](https://procitec.com/application/files/3217/8297/2729/PRO_Analysis_Suite_Tech.Specs._26.2.pdf).

### Inferences
- "Auto Modulation ID": yes.
- "Blind FEC": PROCITEC's own wording is "testing against codes" from a catalogue plus "identify previously unrecovered coding details and parameters". That is analyst-assisted code testing, not a documented automatic code-parameter estimator. Say "code testing in an analyst tool; automatic blind recovery not documented publicly".
- "Blind de-interleave": listed as a manipulation function; automatic parameter recovery is not documented.
- "Automated IQ -> Bits": for known modems, yes. PROCITEC itself describes unknown signals as manual, taking "often hours". That is the strongest vendor-sourced quote for the problem Sanket targets.
- "Open & ITAR-free": proprietary and dongle-licensed. It is not ITAR (German), but it's under German/EU export permission for the MIL and PMR packages.

### Gaps
- No public price.
- Whether the base go2DECODE or go2ANALYSE (without the MIL/PMR packages) needs export permission isn't stated explicitly.

---

## 4. Rohde & Schwarz (GX430 legacy; R&S CA120; R&S CA250)

### Takeaway
R&S CA120 does automatic modulation and transmission-system classification and flags unrecognised signals as "unknown" for recording. R&S CA250 is a bitstream-analysis tool that claims **"fully automated detection of convolutional, Reed-Solomon and BCH codes"**. This is the strongest rival claim against the "Blind FEC" column. CA250 works on demodulated bitstreams, so it is a separate step after demodulation.

### Cited Findings
- **R&S CA250 code detection:** "R&S®CA250 features fully automated detection of convolutional, Reed-Solomon and BCH codes." Its functions include "autocorrelation and cross-correlation, configurable pattern search, entropy tests (Tsallis, Maurer, chi-square)" and "descrambling and deinterleaving" — [R&S CA250 product page](https://www.rohde-schwarz.com/us/products/aerospace-defense-security/technical-signal-analysis/rs-ca250-bitstream-analysis-software_63493-9990.html) (WebFetch summary quotes). The search summary of the same page also mentions "bit-error-tolerant convolutional code analysis", and describes CA250 as analysing "demodulated signals with unknown codings".
- **CA250 inputs:** "import of files in different symbol stream and bitstream formats". The page doesn't say that interleaver detection is automatic — [R&S CA250 product page](https://www.rohde-schwarz.com/us/products/aerospace-defense-security/technical-signal-analysis/rs-ca250-bitstream-analysis-software_63493-9990.html).
- **R&S CA120 classifier:** "automatic detection and recognition [of] modulation type and transmission system". It "can detect known signal types and will report any signals that it does not recognize as 'unknown'". Price via "Get a Quote" — [R&S CA120 product page](https://www.rohde-schwarz.com/us/products/aerospace-defense-security/online-signal-analysis/rs-ca120-multichannel-signal-analysis-software_63493-52993.html). The search summary also says the classifier handles "wideband signals with 22 MHz bandwidth" and has a spectral shape detector.
- **GX430 (legacy):** rated the best automatic classifier in the 2012 review ("GX430 does the best job ever seen in this respect") — [Monitoring Quarterly 2012, addx.org](https://www.addx.org/textarchiv/Krypto500-1.pdf).

### Inferences
- "Auto Modulation ID": yes (CA120).
- "Blind FEC": **yes, as vendor-claimed** for conv/RS/BCH detection in CA250, a separate bitstream tool. Automatic de-interleaver recovery is not documented. The slide must not claim R&S lacks blind FEC.
- "Automated IQ -> Bits": for known systems, yes (CA120). For unknown codings, the chain from CA120 to CA250 as one automatic flow isn't documented.
- "Open & ITAR-free": proprietary, quote-only.

### Gaps
- No export-control statement was retrieved for CA120 or CA250. A German defence product is likely controlled, but this is UNCONFIRMED.
- The CA250 product brochure PDF wasn't read in full. The quotes come from WebFetch summaries of the product page, so re-check the exact wording before putting it on a slide.
- GX430's current status (discontinued or replaced by CA120?) wasn't confirmed.

---

## 5. Open-source tools (one line each)

### Takeaway
None of the open-source analysers documents automatic modulation classification or blind FEC/interleaver recovery. All of them except TorchSig are copyleft (GPL-3.0 or LGPL-3.0).

### Cited Findings
- **GNU Radio:** licence GPL-3.0 (GitHub SPDX) — [github.com/gnuradio/gnuradio](https://github.com/gnuradio/gnuradio). It's a DSP framework in which you build flowgraphs. No automatic modulation ID or blind FEC was found documented in core (the gr-fec wiki page returned HTTP 403, so this wasn't verified).
- **Universal Radio Hacker (URH):** licence GPL-3.0 — [github.com/jopohl/urh](https://github.com/jopohl/urh). Its README says: "easy demodulation of signals combined with an automatic detection of modulation parameters", "customizable decodings" (user-configured, e.g. CC1101 whitening), and "automatically infer protocol fields with a rule-based intelligence" — [URH README](https://github.com/jopohl/urh). It estimates parameters for simple ASK/FSK/PSK. No blind FEC or de-interleaving is documented.
- **SigDigger:** GitHub SPDX licence is **LGPL-3.0** (not GPL) — [github.com/BatchDrake/SigDigger](https://github.com/BatchDrake/SigDigger). README: "designed to extract information of unknown radio signals… allows adjustable demodulation of FSK, PSK and ASK signals" — [SigDigger README](https://github.com/BatchDrake/SigDigger). Demodulation is manual and adjustable; no automatic modulation ID or blind FEC is documented.
- **inspectrum:** licence GPL-3.0 — [github.com/miek/inspectrum](https://github.com/miek/inspectrum). Features: "Cursors for measuring period, symbol rate and extracting symbols", "Export of selected time period, filtered samples and demodulated data"; reads SigMF and many raw IQ formats — [inspectrum README](https://github.com/miek/inspectrum). It's a manual viewer and measurer.
- **TorchSig:** licence **MIT** (GitHub SPDX) — [github.com/TorchDSP/torchsig](https://github.com/TorchDSP/torchsig). "TorchSig is an open-source signal processing machine learning toolkit based on the PyTorch data handling pipeline." It's an ML research toolkit and dataset generator for classification and detection, not an IQ-to-bits analyser.

### Inferences
- "Auto Modulation ID": none of these documents a general modulation classifier. URH estimates modulation *parameters*, and TorchSig enables training classifiers but isn't an analyst tool.
- "Blind FEC / De-interleave": none documents it.
- "Open & ITAR-free": open, but GPL-3.0 (GNU Radio, URH, inspectrum) or LGPL-3.0 (SigDigger). TorchSig is MIT.
- "Automated IQ -> Bits": URH is the closest, for simple OOK/FSK/PSK with automatic parameter detection. The others are manual.

### Gaps
- **RadioML (DeepSig datasets):** licence not verified in this pass. It's commonly cited as CC BY-NC-SA 4.0 — UNCONFIRMED here, so check deepsig.ai before stating it.
- The GNU Radio FEC module's documentation couldn't be fetched (403).

---

## Suggested table cells (evidence-safe wording)

| Tool | Auto Modulation ID | Blind FEC / De-interleave | Open & ITAR-free | Automated IQ → Bits |
|---|---|---|---|---|
| Krypto500/1000 (US) | Yes — ">3,000 modems" (site) | Not documented publicly | No — closed; ITAR (vendor brochure) | Known modems only |
| Wavecom W-CODE + W-BitView (CH) | Yes — W-Classifier | Partial — conv-code parameter search in W-BitView (manual tool); de-interleave with user-set parameters | Closed; export status not stated publicly | Known modes only |
| PROCITEC go2signals (DE) | Yes — classifier + ">470 modems" DB | Analyst tool: test against code catalogue; de-interleave with parameters | Closed; German/EU export permission (MIL/PMR packages) | Known modems; unknown = manual ("often hours!") |
| R&S CA120 + CA250 (DE) | Yes — CA120 | Yes (vendor claim) — CA250 automated conv/RS/BCH detection; de-interleave not stated as automatic | Closed; quote-only | Known systems; CA250 is a separate bitstream step |
| GNU Radio / URH / inspectrum / SigDigger | No (URH: auto parameter estimation) | Not documented | Open, but GPL-3.0 / LGPL-3.0 | URH partly; others manual |
| TorchSig | Research datasets/models only | No | Yes — MIT | No |
