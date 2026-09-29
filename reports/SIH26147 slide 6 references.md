# Rebuild slide 6 on verified, defensible citations

Slide 6 can be filled entirely with facts checked against primary sources, but four items on the current slide and in the repo docs have to change first. The six research references that fit the problem statement (PS) best are O'Shea 2018 (modulation), Marazin 2011 (convolutional codes), Sicot 2009 and Wee 2021 (interleavers), Swaminathan 2018 (Reed–Solomon plus interleavers) and Moosavi 2014 (LDPC and soft code testing). All six were confirmed from publisher Crossref records, and **Wee et al. is in *Sensors* 21(10):3458, not *Entropy*** ([Crossref](https://api.crossref.org/works/10.3390/s21103458)). The current standard versions are **CCSDS 131.0-B-5 (Sep 2023)**, **ITU-R M.1371-6 (02/2026)**, **M.493-16 (12/2023)** and **SigMF v1.2.6 (Dec 2025)**. **Section 3(1) of the Telecommunications Act 2023 has reportedly been in force since 23 Jun 2026**, a secondary report still to be checked in the Gazette. The competitive table needs the biggest fix. **Rohde & Schwarz CA250 advertises "fully automated detection of convolutional, Reed-Solomon and BCH codes"**, and **Wavecom W-BitView documents an automatic convolutional-code parameter search**, so "no rival does blind FEC" would be false. What no vendor documents is *automatic interleaver recovery* chained to blind FEC, starting from raw IQ, with stated evidence, and that is the claim Sanket should make. Four more fixes follow from the same sources. The Krypto500 price of US$7,400 comes from a 2012 magazine review, not the vendor. Sig53 has since been renamed. "CORAL" is a domain-adaptation method, not a dataset. RadioML's documented flaws trace to Chad Spooner's CSP Blog, not to "Sathyanarayanan". Everything below fits the template's space limits. Section 1 is ready to paste, and sections 3–5 give the evidence and the items still open.

## Section 1 — slide content sized to the template's space limits

### (a) Research Material — 6 numbered references

```
1. O'Shea, Roy & Clancy, "Over-the-Air Deep Learning Based Radio Signal Classification,"
   IEEE JSTSP 12(1):168–179, 2018 → deep AMC on raw IQ; RadioML baseline
2. Marazin, Gautier & Burel, "Blind recovery of k/n rate convolutional encoders in a noisy
   environment," EURASIP JWCN 2011:168 → dual-code convolutional-code recovery
3. Sicot, Houcke & Barbier, "Blind detection of interleaver parameters,"
   Signal Processing 89(4):450–462, 2009 → GF(2) rank: interleaver period + frame sync
4. Wee, Choi & Jeong, "Blind Interleaver Parameters Estimation Using Kolmogorov–Smirnov Test,"
   Sensors 21(10):3458, 2021 → rank-distribution KS test with false-alarm control
5. Swaminathan, Madhukumar, Wang & Kee, "Blind Reconstruction of Reed-Solomon Encoder and
   Interleavers Over Noisy Environment," IEEE Trans. Broadcast. 64(4):830–845, 2018 → RS(n,k) + interleaver
6. Moosavi & Larsson, "Fast Blind Recognition of Channel Codes," IEEE Trans. Commun.
   62(5):1393–1405, 2014 → soft syndrome test for catalogue codes (LDPC)
```

If the slide has room for DOIs, add them from the verification table in section 3. If it is tighter than two lines per item, drop the titles and keep authors, venue, year and the arrow. Three verified reserves can replace an item without further checking. **Xu, Zhong & Huang, IEEE Access 7:101775–101784, 2019** covers convolutional (Forney-type) interleavers. **Jeong, Yoon, Lee & Choi, ICICS 2011** covers helical-scan interleavers, which answers the PS's "Diagonal". **Marazin, Gautier & Burel, IET Signal Processing 6(2):122–131, 2012** covers punctured convolutional codes.

### (b) Standards And Compliance Frameworks — 3 bullets

```
• CCSDS 131.0-B-5 (Sep 2023) TM Sync & Channel Coding + 132.0-B-3 (Oct 2021): ASM 1ACFFC1D,
  K=7 r½, RS(255,223), interleave depth I=1–5, 8 → reference coding chain & VERIFIED checks
• ITU-R M.1371-6 (AIS), M.493-16 (DSC), M.540-2 + M.476-5 (NAVTEX), M.584-2 (paging);
  SigMF v1.2.6 (Dec 2025) for recording I/O and ground-truth annotations
• Telecommunications Act 2023 (No. 44): §20 lawful interception, §3(1)(c) radio-equipment
  authorisation; Interception Rules 2024 (G.S.R. 754(E)); NFAP-2025 band plan
```

### (c) Competitive Analysis

| Solution | Auto Modulation ID | Blind FEC / De-interleave | Open & ITAR-Free | Automated IQ → Bits |
|---|---|---|---|---|
| Krypto500/1000 (COMINT, USA) | ✔ >3,000 known modems | Not publicly documented | ✘ Closed; ITAR-controlled (vendor brochure) | Known modems only |
| R&S CA120 + CA250 (Germany) | ✔ CA120 classifier | FEC ✔ (vendor: auto conv/RS/BCH detection, CA250); de-interleave not stated as automatic | ✘ Closed, quote-only | Known systems; unknown codings go to a separate bitstream tool |
| GNU Radio / URH (open source) | ✘ (URH: auto parameters for simple ASK/FSK/PSK) | ✘ Not documented | ✔ Open (GPL-3.0) | Partial (URH, simple signals); otherwise hand-built |
| **Sanket (ours)** | ✔ PSK/QAM/FSK classifier + open-set "unknown" | ✔ Conv/RS/concatenated/catalogue LDPC + block, convolutional, helical and standard pseudo-random interleavers, chained, with false-alarm control | ✔ Open, Indian-built, offline; permissive dependencies | ✔ One chain: IQ/WAV → bits → frames; VERIFIED only by CRC, sync or re-encode |

Footnote line under the table: `Rivals: vendors' public documents, Sep 2026. "Not documented" ≠ "absent".`

The table keeps a tick-or-cross glyph plus words in every cell, so a black-and-white print or a colour-blind judge still reads it correctly. Two verified rows can be swapped in:

| Solution | Auto Modulation ID | Blind FEC / De-interleave | Open & ITAR-Free | Automated IQ → Bits |
|---|---|---|---|---|
| PROCITEC go2signals (Germany) | ✔ Classifier + >470-modem database | Analyst tool: tests codes from a list (Hamming/RS/BCH/Golay/CRC); de-interleave with set parameters | ✘ Closed; German export permit for MIL/PMR packages | Known modems; unknown signals are manual ("often hours!") |
| Wavecom W-CODE + W-BitView (Switzerland) | ✔ W-Classifier | Partial: auto conv-code search (K = 2–14) in W-BitView; de-interleave with user parameters | ✘ Closed; export status not public | Known modes only |

### (d) Important Links

```
• Demo: <link> — synthetic demo capture (labelled as synthetic)
• Prototype photos: <link>
```

### (e) Datasets — 4 bullets

```
• Own ground truth — dsp.synth (NumPy): PSK/QAM/FSK × conv/RS/LDPC × interleavers × CRC
  frames + impairments; exact truth in SigMF annotations → training set
• RadioML 2018.01A (DeepSig): 24 classes, 26 SNRs (−20…+30 dB), 2,555,904 × 1,024 IQ;
  CC BY-NC-SA 4.0 → benchmark only, with corrected class labels
• TorchSig (MIT; Sig53/WidebandSig53, now "Narrowband/Wideband"): 53 classes,
  4,096-sample IQ, Es/N0 −2…30 dB → independent test generator
• HisarMod2019.1 (IEEE DataPort): 26 classes, 5 channel types (AWGN…Nakagami-m),
  780,000 × 1,024 IQ, −20…18 dB → fading benchmark
```

If the team wants one over-the-air benchmark on the slide, the verified candidate is the **Real-World IQ Dataset (Mendeley Data, Jan 2026): 7 classes, 1,024-sample frames, HDF5, CC BY 4.0** ([Mendeley Data](https://data.mendeley.com/datasets/tjzsbph49x/2)). It would replace HisarMod, which the Panoradio overview rates "Flawed" for "questionable label assignment, strange waveforms and absence of modulated data" ([Panoradio SDR](https://panoradio-sdr.de/overview-of-open-datasets-for-rf-signal-classification/)).

## Section 2 — every choice answers a phrase in the problem statement

The PS asks the tool to "identify signal parameters (Sampling frequency, Modulation, FEC, Interleaving)", demodulate "FSK, QAM PSK", de-interleave "Block, Convolution, Diagonal, Pseudo Random", and handle "short-constrained convolution codes with Viterbi decoding, RS block codes, Concatenated codes, LDPC". It then asks for "correlation of bit stream for identification of header and payload". The six references were chosen so that each PS noun has a peer-reviewed method behind it. O'Shea covers modulation ([Crossref](https://api.crossref.org/works/10.1109/JSTSP.2018.2797022)). Marazin's dual-code algorithm covers the convolutional codes ([Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1186/1687-1499-2011-168)). Swaminathan covers RS together with block interleavers from noisy, unsynchronised streams ([OpenAlex](https://api.openalex.org/works/doi:10.1109/TBC.2018.2795461)). Moosavi–Larsson's syndrome posterior probability, computed from soft information without decoding, is the established way to test a catalogue of LDPC codes ([OpenAlex](https://api.openalex.org/works/doi:10.1109/TCOMM.2014.050614.130297)). Sicot–Houcke–Barbier is the foundational rank-deficiency method for interleaver size and frame synchronisation ([HAL](https://api.archives-ouvertes.fr/search/?q=halId_s:hal-02117763&fl=abstract_s)). Wee et al. replace hard rank thresholds with a Kolmogorov–Smirnov test under a multinomial false-alarm model ([Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/DOI:10.3390/s21103458)). That last one matters beyond coverage: it is the literature's version of Sanket's rule that blind searches count their hypotheses and correct their thresholds. The one PS parameter without a slide reference is sampling frequency. It is inferred structurally rather than from a single canonical paper, and section 5 lists it as a gap.

The standards bullets do two jobs. The first is to show that the known-system checks rest on current, citable specifications. The PS theme is **Space Technology**, and CCSDS 131.0-B-5 is the one document that defines, in one place, the sync marker `1ACFFC1D`, the K=7 rate-½ code (171/133 octal), RS(255,223), interleave depths I = 1–5 and 8, and the concatenated scheme ([CCSDS 131.0-B-5](https://ccsds.org/Pubs/131x0b5.pdf)). It is the natural "header/payload" and "concatenated codes" reference. The ITU-R maritime and paging recommendations anchor the FSK and GMSK systems (DSC, NAVTEX, AIS, POCSAG) that Sanket checks against. The second job is compliance. NTRO is an interception-adjacent agency, and judges from it will look for the lawful framing: Sanket analyses recordings made by authorised agencies under §20 and the 2024 Interception Rules, and does no interception itself. Section 3(1)(c) matters because capturing test data requires authorisation to *possess* radio equipment.

The competitive table is built so that no rival cell can be contradicted by the rival's own brochure. Krypto500 stays because it is the ITAR anchor of the team's Atmanirbhar argument. The vendor states in writing that it "is controlled by the US International Traffic in Arms Regulations (ITAR) 22 CFR §120-130" ([Krypto500 brochure 2020](https://aventasinc.com/wp-content/uploads/2021/08/Krypto500.pdf)). R&S belongs on the slide *because* it is the strongest rival in the blind-FEC column. Leaving it off invites a judge to raise it. Putting it on with a ✔ shows the team knows the field, and the gap remains visible: automatic de-interleaving is not stated, and CA250 is a separate bitstream tool downstream of CA120, not one chain from IQ. GNU Radio/URH is the row the PS itself invites, since it names "GNU Radio, python, C++". It also shows that the open tools available today automate neither modulation ID nor code recovery. The Sanket row describes the planned 1.0 scope in PLAN §1: block, convolutional, helical and catalogued pseudo-random interleavers, and convolutional (including punctured), RS, concatenated and catalogued LDPC codes. The pseudo-random cell says "standard", and LDPC says "catalogue", because generic seed recovery and generic LDPC reconstruction are not claimable. The literature recovers full permutations only for specific code structures such as turbo codes ([Cluzeau, Finiasz & Tillich](https://export.arxiv.org/api/query?id_list=1006.0259)).

The datasets bullets put the training source first, because Sanket's credibility rests on training with exact labels. The public sets follow as independent benchmarks, each with its licence. RadioML goes on the slide as "benchmark only, with corrected class labels", and the reason is documented. Its SNR parameter is "off by tens of dB" (label 18 measured about 40 dB in-band). Its 2016.10a AM-SSB class is noise only. And "the mapping provided by DeepSig in classes.txt is incorrect" for 2018.01A ([CSP Blog 2020a](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/); [CSP Blog 2020b](https://cyclostationary.blog/2020/09/24/deepsigs-2018-data-set-2018-01-osc-0001_1024x2m-h5-tar-gz/)). The dataset is also CC BY-NC-SA 4.0 ([DeepSig](https://www.deepsig.ai/datasets/)), which rules it out as shipped training data for a product. TorchSig's MIT licence ([GitHub](https://github.com/TorchDSP/torchsig)) makes it the right independent generator.

## Section 3 — verification table

| # | Item | Verified fact | Source |
|---|---|---|---|
| 1 | O'Shea, Roy, Clancy | IEEE JSTSP 12(1):168–179, Feb 2018; doi:10.1109/JSTSP.2018.2797022 (arXiv 1712.04578) | [Crossref](https://api.crossref.org/works/10.1109/JSTSP.2018.2797022) |
| 2 | Marazin, Gautier, Burel (k/n) | EURASIP JWCN 2011, article 168 (14 Nov 2011); doi:10.1186/1687-1499-2011-168 | [Crossref](https://api.crossref.org/works/10.1186/1687-1499-2011-168) |
| 3 | Marazin et al. (punctured; reserve) | IET Signal Processing 6(2):122–131, 2012; doi:10.1049/iet-spr.2010.0343 | [Crossref](https://api.crossref.org/works/10.1049/iet-spr.2010.0343) |
| 4 | Sicot, Houcke, Barbier | Signal Processing 89(4):450–462, Apr 2009; doi:10.1016/j.sigpro.2008.09.012; open copy hal-02117763 | [Crossref](https://api.crossref.org/works/10.1016/j.sigpro.2008.09.012) |
| 5 | Wee, Choi, Jeong | *Sensors* 21(10):3458, 15 May 2021; doi:10.3390/s21103458; PMC8155855; PMID 34063544 | [Crossref](https://api.crossref.org/works/10.3390/s21103458); [PMC idconv](https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?ids=PMC8155855&format=json) |
| 6 | Swaminathan, Madhukumar, Wang, Kee | IEEE Trans. Broadcasting 64(4):830–845, Dec 2018; doi:10.1109/TBC.2018.2795461 | [Crossref](https://api.crossref.org/works/10.1109/TBC.2018.2795461) |
| 7 | Moosavi, Larsson | IEEE Trans. Commun. 62(5):1393–1405, May 2014; doi:10.1109/TCOMM.2014.050614.130297 | [Crossref](https://api.crossref.org/works/10.1109/TCOMM.2014.050614.130297) |
| 8 | Xu, Zhong, Huang (reserve) | IEEE Access 7:101775–101784, 2019; doi:10.1109/ACCESS.2019.2930663 | [Crossref](https://api.crossref.org/works/10.1109/ACCESS.2019.2930663) |
| 9 | Jeong, Yoon, Lee, Choi (reserve, helical) | ICICS 2011, pp. 1–4; doi:10.1109/ICICS.2011.6174276 | [Crossref](https://api.crossref.org/works/10.1109/ICICS.2011.6174276) |
| 10 | Boegner et al. (TorchSig/Sig53) | arXiv:2207.09918, 20 Jul 2022; 8 authors; preprint only | [arXiv API](https://export.arxiv.org/api/query?id_list=2207.09918) |
| 11 | CCSDS 131.0-B-5 | Blue Book Issue 5, Sep 2023; supersedes -4 (Apr 2022); ASM 1ACFFC1D; K=7, G1=171, G2=133 octal; RS(255,223)/(255,239); I = 1, 2, 3, 4, 5, 8 | [CCSDS PDF](https://ccsds.org/Pubs/131x0b5.pdf) |
| 12 | CCSDS 132.0-B-3 | TM Space Data Link Protocol, Issue 3, Oct 2021 (cited as ref [1] of 131.0-B-5; ECSS adoption Jan 2023) | [CCSDS PDF](https://ccsds.org/Pubs/131x0b5.pdf); [ECSS](https://ecss.nl/standard/ecss-e-as-50-22c-rev-1-adoption-notice-of-ccsds-132-0-b-3-tm-space-data-link-protocol-3-january-2023/) |
| 13 | ITU-R M.1371 (AIS) | M.1371-6 (02/2026) in force; supersedes -5 (02/2014) | [ITU-R](https://www.itu.int/rec/R-REC-M.1371/en) |
| 14 | ITU-R M.493 (DSC) | M.493-16 (12/2023) in force | [ITU-R](https://www.itu.int/rec/R-REC-M.493/en) |
| 15 | NAVTEX recs | M.540-2 (06/1990), M.476-5 (10/1995), M.625-4 (03/2012), all in force | [M.540](https://www.itu.int/rec/R-REC-M.540/en); [M.476](https://www.itu.int/rec/R-REC-M.476/en); [M.625](https://www.itu.int/rec/R-REC-M.625/en) |
| 16 | ITU-R M.584 (paging) | M.584-2 (11/1997), "Codes and formats for radio paging", in force | [ITU-R](https://www.itu.int/rec/R-REC-M.584/en) |
| 17 | SigMF | v1.2.6 released 2025-12-21; spec licence CC BY-SA 4.0 | [GitHub API](https://api.github.com/repos/sigmf/SigMF/releases?per_page=3); [repo](https://github.com/sigmf/SigMF) |
| 18 | Telecommunications Act 2023 | No. 44 of 2023, assent 24 Dec 2023; §3(1)(c) "possess radio equipment"; §20(2)(a) interception | [eGazette](https://egazette.gov.in/WriteReadData/2023/250880.pdf) |
| 19 | §20 commencement | In force 26 Jun 2024 (S.O. 2408(E)) | [SCC Online](https://www.scconline.com/blog/post/2024/06/24/enforcement-date-for-partial-enforcement-of-the-telecommunications-act-2023-notified-legal-news/) |
| 20 | §3(1) commencement | Notified by DoT on 23 Jun 2026 with the authorisation rules (secondary) | [Mondaq](https://www.mondaq.com/india/telecoms-mobile-cable-communications/1823106/notification-of-section-31-and-section-36-of-telecommunications-act-2023-and-operative-rule) |
| 21 | Interception Rules 2024 | G.S.R. 754(E), 6 Dec 2024 (secondary, multiple sources agree) | [TaxGuru](https://taxguru.in/corporate-law/telecom-rules-2024-lawful-interception-procedures-safeguards.html); [IFF](https://internetfreedom.in/first-read-telecom-interception-rules-2024/) |
| 22 | NFAP-2025 | Released by DoT (WPC Wing), effective 30 Dec 2025 (title-level only; pages returned 403) | [PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2209717&reg=3&lang=1); [CSA Group](https://www.csagroup.org/global-certification-regulatory-update/india-dot-publishes-the-national-frequency-allocation-plan-nfap-2025-effective-december-30-2025/) |
| 23 | ITU-R Spectrum Monitoring Handbook | Latest listed edition 2011 | [ITU](https://www.itu.int/pub/R-HDB-23) |
| 24 | RadioML 2018.01A | 24 classes; synthetic with simulated channel effects; 1,024 samples; HDF5; CC BY-NC-SA 4.0 | [DeepSig](https://www.deepsig.ai/datasets/) |
| 25 | RadioML 2018.01A counts | 2,555,904 records; 26 SNRs −20…+30 dB step 2; 4,096 per class-SNR | [CSP Blog](https://cyclostationary.blog/2020/09/24/deepsigs-2018-data-set-2018-01-osc-0001_1024x2m-h5-tar-gz/) |
| 26 | RadioML flaws | SNR labels off by tens of dB; AM-SSB noise-only (2016.10a); classes.txt wrong (2018.01A); unanswered GitHub issue #25 | [CSP Blog](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/); [GitHub #25](https://github.com/radioML/dataset/issues/25) |
| 27 | Sig53 | 53 classes; 4,096 samples; impaired Es/N0 −2…30 dB; 1M clean + 5.3M impaired training, 106k + 106k validation | [ar5iv 2207.09918](https://ar5iv.labs.arxiv.org/html/2207.09918) |
| 28 | WidebandSig53 | 550k samples, ~2M signals, 53 classes | [arXiv 2211.10335](https://arxiv.org/abs/2211.10335) |
| 29 | TorchSig status | MIT; v0.6.0 renamed Sig53 → Narrowband, WidebandSig53 → Wideband; 2.x unified configurable datasets; latest v2.2.0 | [Releases](https://github.com/TorchDSP/torchsig/releases); [README](https://github.com/TorchDSP/torchsig) |
| 30 | HisarMod2019.1 | 26 classes, 5 families, 5 channels, 780,000 × 1,024 IQ, −20…18 dB, doi:10.21227/8k12-2g70 | [IEEE DataPort](https://ieee-dataport.org/open-access/hisarmod-new-challenging-modulated-signals-dataset); [arXiv 1911.04970](https://arxiv.org/abs/1911.04970) |
| 31 | Real-World IQ (OTA option) | 7 classes, 1,024-sample frames, HDF5, CC BY 4.0, doi:10.17632/tjzsbph49x.2 | [Mendeley Data](https://data.mendeley.com/datasets/tjzsbph49x/2) |
| 32 | Krypto500 ITAR | "controlled by the US International Traffic in Arms Regulations (ITAR) 22 CFR §120-130" | [2020 brochure](https://aventasinc.com/wp-content/uploads/2021/08/Krypto500.pdf) |
| 33 | Krypto500 scope | ">3,000 modems" (current site); 48 kHz narrowband; "hundreds of decoders" | [COMINT site](https://www.comintconsulting.com/krypto500); [older brochure](https://datatec.es/wp-content/uploads/2016/04/Krypto500.pdf) |
| 34 | Krypto500 price origin | "US-$ 7400", *Monitoring Quarterly* no. 1, Feb 2012 (third-party) | [addx.org PDF](https://www.addx.org/textarchiv/Krypto500-1.pdf) |
| 35 | R&S CA250 | "fully automated detection of convolutional, Reed-Solomon and BCH codes"; descrambling and deinterleaving functions | [R&S CA250](https://www.rohde-schwarz.com/us/products/aerospace-defense-security/technical-signal-analysis/rs-ca250-bitstream-analysis-software_63493-9990.html) |
| 36 | R&S CA120 | Automatic modulation and transmission-system recognition; unknowns reported as "unknown" | [R&S CA120](https://www.rohde-schwarz.com/us/products/aerospace-defense-security/online-signal-analysis/rs-ca120-multichannel-signal-analysis-software_63493-52993.html) |
| 37 | Wavecom W-BitView | Convolutional Code Analysis returns K, k, n and generators, searching K = 2–14, n = 2–4; de-interleaving from user-set parameters | [W-BitView manual V2.5.00](https://www.wavecom.ch/content/pdf/manual_w-bitview-v2-5-00.pdf) |
| 38 | Wavecom W-CODE | Automatic classification; ">226" modes (2015); prices via contact | [W-CODE brochure](https://www.hik-consulting.pl/files/brochure_w-code.pdf) |
| 39 | PROCITEC | ">470 modems"; go2ANALYSE "testing against codes"; export permission for MIL/PMR packages and go2key | [Tech Specs v26.2](https://procitec.com/application/files/3217/8297/2729/PRO_Analysis_Suite_Tech.Specs._26.2.pdf) |
| 40 | PROCITEC on unknowns | analysts use "manual bitstream analysis techniques" taking "often hours!" | [go2ANALYSE brochure](https://procitec.com/file_access/3616/2195/5265/PROCITEC_Broschure_go2ANALYSE.pdf) |
| 41 | GNU Radio / URH | Both GPL-3.0; URH: "automatic detection of modulation parameters" | [GNU Radio](https://github.com/gnuradio/gnuradio); [URH](https://github.com/jopohl/urh) |
| 42 | CORAL | A domain-adaptation method (61.47% recovery in one synthetic-to-OTA study), not a dataset | [arXiv 2510.00589](https://arxiv.org/html/2510.00589) |

## Section 4 — corrections to the current slide and the repo docs

The research contradicts the team's current slide and repo docs in the places below. Line numbers are as of 29 Sep 2026.

| Where | Currently says | Should say | Source |
|---|---|---|---|
| Current slide 6, Research Material | Wee, Choi & Jeong in *Entropy* | *Sensors* 21(10):3458, 2021, doi:10.3390/s21103458. A different 2020 Korean paper (Kim et al., J. KICS 45(3)) has a near-identical title; don't mix them up. | [Crossref](https://api.crossref.org/works/10.3390/s21103458); [KICS](https://api.crossref.org/works/10.7840/kics.2020.45.3.584) |
| `docs/STANDARDS_TO_BEAT.md` §2 l.47; `docs/SIHPS_ANALYSIS.md` l.97, 291, 359, 919, 931; `docs/QandA.md` l.523–525 | Krypto500 "about US$7,400" (dossier) | "US$7,400 in a Feb 2012 third-party review (*Monitoring Quarterly*); no current public price." Keep it off the slide, because the ITAR fact carries the argument on its own. | [addx.org](https://www.addx.org/textarchiv/Krypto500-1.pdf) |
| STANDARDS §2 l.48; SIHPS l.293, 931 | Wavecom W-CODE "about US$995" | Remove. It traces only to an SEO-type sites.google.com page, and the vendor brochure gives prices via contact only. | [W-CODE brochure](https://www.hik-consulting.pl/files/brochure_w-code.pdf) |
| STANDARDS §2 l.67 | Public material "documents blind FEC and interleaver work only as manual tools" | R&S CA250 claims fully automated conv/RS/BCH detection, and W-BitView has an automatic conv-code search. Only automatic *interleaver* recovery is undocumented. The differentiator is "blind FEC + interleaver recovery chained automatically from IQ, with evidence". | [R&S CA250](https://www.rohde-schwarz.com/us/products/aerospace-defense-security/technical-signal-analysis/rs-ca250-bitstream-analysis-software_63493-9990.html); [W-BitView](https://www.wavecom.ch/content/pdf/manual_w-bitview-v2-5-00.pdf) |
| STANDARDS §9 l.375 | Krypto500 "Blind FEC ✅" | "Not documented publicly". Neither brochure nor the site mentions FEC recognition or de-interleaving. | [2020 brochure](https://aventasinc.com/wp-content/uploads/2021/08/Krypto500.pdf); [site](https://www.comintconsulting.com/krypto500) |
| QandA l.72 | Krypto500 "nearly 4000 FSK & PSK modems" | That is the older brochure. The 2020 brochure says "4000+", and the current site says "more than 3,000". Quote ">3,000". | [COMINT site](https://www.comintconsulting.com/krypto500) |
| STANDARDS §2 l.65 | Wavecom "300+ modes" | The 2015 brochure says ">226". "300+" is unverified. | [W-CODE brochure](https://www.hik-consulting.pl/files/brochure_w-code.pdf) |
| STANDARDS §2 l.49, 51; SIHPS l.432 | PROCITEC and GX430 "export-controlled"; R&S listed as GX430 | PROCITEC needs export permission for its MIL/PMR packages and go2key; the base product is not stated. R&S's current products are CA120/CA250, whose export status is unconfirmed. GX430 appears only as the 2012 benchmark. | [Tech Specs v26.2](https://procitec.com/application/files/3217/8297/2729/PRO_Analysis_Suite_Tech.Specs._26.2.pdf); [R&S CA120](https://www.rohde-schwarz.com/us/products/aerospace-defense-security/online-signal-analysis/rs-ca120-multichannel-signal-analysis-software_63493-52993.html) |
| SIHPS l.206, 415–419; STANDARDS §3 l.83 | "Sig53: 5 million examples, 53 classes"; TorchSig "57 modulation variants" | TorchSig v0.6.0 renamed Sig53 → Narrowband and WidebandSig53 → Wideband (53 → 61 signals). 2.x is a configurable generator with "60+ signal types". The paper's split is 1M clean + 5.3M impaired training. | [Releases](https://github.com/TorchDSP/torchsig/releases); [ar5iv](https://ar5iv.labs.arxiv.org/html/2207.09918) |
| `docs/PLAN.md` l.414 | "AMC is fine-tuned on labelled real captures (e.g. CORAL)" | CORAL (correlation alignment) is an unsupervised domain-adaptation method, not a dataset, and no AMC dataset of that name exists. Suggested wording: "fine-tuned, or CORAL-adapted, on labelled real captures such as Real-World IQ (Mendeley 2026)". | [arXiv 2510.00589](https://arxiv.org/html/2510.00589); [Mendeley Data](https://data.mendeley.com/datasets/tjzsbph49x/2) |
| SIHPS l.302, 470, 803; `README.md` l.200 | Act cited for §20 only (SIHPS); README cites the Feb 2025 draft possession rules as the current state | Add that §20 has been in force since 26 Jun 2024 and §3(1) since 23 Jun 2026 (secondary report), and cite the Interception Rules 2024 (G.S.R. 754(E)). Whether the final possession rules are notified is still unconfirmed. | [SCC Online](https://www.scconline.com/blog/post/2024/06/24/enforcement-date-for-partial-enforcement-of-the-telecommunications-act-2023-notified-legal-news/); [Mondaq](https://www.mondaq.com/india/telecoms-mobile-cable-communications/1823106/notification-of-section-31-and-section-36-of-telecommunications-act-2023-and-operative-rule) |
| SIHPS l.303 | "up to 3 years under the 1933 Act, carried into the new framework" | No source for this was found in this research. Verify it or remove it. | — |
| PLAN l.337; QandA l.265 | "CCSDS 131.0-B, 132.0-B" (no issue number) | 131.0-B-5 (Sep 2023); 132.0-B-3 (Oct 2021) | [CCSDS PDF](https://ccsds.org/Pubs/131x0b5.pdf) |
| PLAN l.338; QandA l.266 | "ITU-R M.1371" | M.1371-6 (02/2026) on the slide; unsuffixed in the docs is acceptable | [ITU-R](https://www.itu.int/rec/R-REC-M.1371/en) |
| SIHPS l.399–401 | SigMF, ITU Handbook and NFAP with no versions | SigMF v1.2.6 (Dec 2025); Handbook 2011 edition; NFAP-2025 (effective 30 Dec 2025) | [GitHub API](https://api.github.com/repos/sigmf/SigMF/releases?per_page=3); [ITU](https://www.itu.int/pub/R-HDB-23) |
| Team brief (RadioML flaws) | Attributed to "Sathyanarayanan" | No source by that name was found. Attribute the flaws to C. Spooner, CSP Blog (Aug and Sep 2020), and GitHub issue #25. | [CSP Blog](https://cyclostationary.blog/2020/08/17/more-on-deepsigs-rml-data-sets/); [GitHub #25](https://github.com/radioML/dataset/issues/25) |
| Any slide or doc calling RadioML 2018 "over-the-air" | Over-the-air captures | DeepSig: "synthetic dataset with simulated channel effects". Cite O'Shea as 2018 (journal issue), even though DeepSig's page says 2017. | [DeepSig](https://www.deepsig.ai/datasets/) |

Two framing issues fall outside the tables but still need a decision. First, PLAN l.315 and STANDARDS §7 D9 say that "no public implementation" of the literature methods exists, while STANDARDS §0 item 3 records that the SIH repo `sigma-signal-analysis` already identifies convolutional, RS and catalogue LDPC codes blindly. D9 holds only in its narrow form: an open, *benchmarked* implementation of GJETP, GFFT and rank/KS methods. The slide must not turn that into "only Sanket does blind FEC". Second, STANDARDS §9 says the team's column "shows targets and must say so on the slide". That conflicts with the team's decision to show planned features as the product. The honest minimum is a small "Sanket 1.0" label on the row. It costs no space and keeps the deck consistent with the rule that deck numbers come from `bench/results/`.

## Section 5 — items still unconfirmed before the deck ships

Nothing in section 1 depends on an unconfirmed fact, except the three items flagged in the first paragraph below. The rest of this section lists what the notes could not close, so that nobody fills the gaps from memory.

- **Slide items that still depend on an unconfirmed fact.**
  - The exact R&S CA250 wording came from fetched summaries of the product page; the brochure was not read in full. Re-read the page before quoting it verbatim.
  - The §3(1) commencement on 23 Jun 2026 rests on one law-firm report, with no S.O. number. It is also unconfirmed whether §3(1)(c) (possession) became operative then or only the service and network limbs, and whether the Radio Equipment Possession Authorisation Rules were finalised after the Feb 2025 draft.
  - G.S.R. 754(E) was confirmed only through agreeing secondary sources.
- **Standards.**
  - The CCSDS index is JavaScript-rendered, so a 131.0-B-6 or 132.0-B-4 after Sep 2023 cannot be ruled out. ECSS's Dec 2024 adoption still cites -5.
  - That POCSAG is "Radiopaging Code No. 1" in M.584-2, and its sync word, were not checked in the PDF. Keep the slide at "M.584-2 (paging)".
  - A revised ITU Spectrum Monitoring Handbook was rumoured for after June 2026 but not found.
  - The NFAP-2025 press pages returned 403, so only titles and summaries were read.
- **Rivals.**
  - No current Krypto500 price exists anywhere, and the 2012 review's statement that it was "developed in the Czech Republic" was not reconciled with the US LLC.
  - Wavecom's and R&S's export status is unstated.
  - W-BitView features added after the 2012 manual were not checked.
  - GNU Radio's gr-fec documentation returned 403. "Not documented" is the right cell text, but it is not a proven absence.
- **Datasets.**
  - No explicit licence was found for HisarMod, for the Sig53 *data* (as opposed to TorchSig code), or for RML2016.10b.
  - The TorchSig v2.2.0 release year shows no year on GitHub; it is probably 2026.
  - TorchSig 2.x's exact class count is unknown ("60+").
  - DeepSig's reported "erratic" label for RadioML appears only in Panoradio's overview.
  - The Real-World IQ set's capture hardware and example count were not shown on its page.
- **Coverage gap.** None of the six references addresses **sampling-frequency inference**, the first parameter the PS names. The notes contain no verified bibliographic record for a rate or symbol-rate paper. If a judge asks, the defensible answer is that the sampling rate cannot be identified from samples alone. Sanket ranks candidates from metadata and device rate lists and promotes one only on a structural match. It does not cite a paper for a claim no paper makes.

## Conclusion

The research shifts slide 6's argument from exclusivity to chaining. The commercial field already automates modulation recognition and, in R&S's case, convolutional/RS/BCH code detection. So the defensible gap is narrower and more concrete. No documented product recovers interleaver parameters automatically, chains that recovery to blind FEC starting from raw IQ, and reports which results carry proof (CRC, sync recurrence, re-encode). None does it openly, offline and outside ITAR. That framing costs nothing in impact and makes the slide survive a judge who knows the CA250 datasheet.

The references carry the same lesson. The stale figures (the 2012 price, the renamed dataset, the misplaced journal, the method mistaken for a dataset) all entered the docs through secondary summaries. Each was caught by going back to a Crossref record, a vendor PDF or a Gazette copy. The same discipline should cover the three open legal and vendor items before the deck is submitted, because on a slide addressed to NTRO an out-of-date statute date damages credibility more than a missing reference.
