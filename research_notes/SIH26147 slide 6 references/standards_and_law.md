# Standards and Compliance Frameworks for SIH26147 (slide 6): current versions as of 29 Sep 2026

Research date: 29 September 2026. "Confirmed" means read on the publisher's own page or document in this session, unless the note says it came from a secondary source. Anything not confirmed is marked **UNCONFIRMED**.

## 1. CCSDS telemetry coding: 131.0-B and 132.0-B

### Takeaway
The current issue is **CCSDS 131.0-B-5, "TM Synchronization and Channel Coding", Recommended Standard (Blue Book), Issue 5, September 2023**, published by CCSDS in Washington DC. It supersedes Issue 4 (April 2022). The same document specifies the ASM `1ACFFC1D`, the K=7 rate-1/2 convolutional code (171/133 octal) and RS(255,223) with interleave depth I = 1 to 5 or 8. It cites **CCSDS 132.0-B-3, "TM Space Data Link Protocol", Issue 3, October 2021** as the current data-link-layer standard.

### Cited Findings
- Cover page reads: "Recommendation for Space Data System Standards, TM SYNCHRONIZATION AND CHANNEL CODING, RECOMMENDED STANDARD, CCSDS 131.0-B-5, BLUE BOOK, September 2023". The Authority page reads: "Issue: Recommended Standard, Issue 5. Date: September 2023. Location: Washington, DC, USA". — [CCSDS 131.0-B-5 PDF](https://ccsds.org/Pubs/131x0b5.pdf)
- The document's change log says 131.0-B-4 (Issue 4, April 2022) is "superseded", and 131.0-B-5 (Issue 5, September 2023) is the "Current issue: provides a revised pseudo-randomizer (section 10) for the purpose of obviating spectral spikes in high-data-rate links". — [CCSDS 131.0-B-5 PDF](https://ccsds.org/Pubs/131x0b5.pdf)
- **ASM:** section 9 NOTE: "ASM for uncoded data, convolutional, Reed-Solomon, concatenated, rate-7/8 LDPC for Transfer Frame, and all LDPC with SMTF stream coded data: 1ACFFC1D". The 64-bit ASM `034776C7272895B0` is used for rate-1/2 Turbo and for rate-1/2, 2/3 and 4/5 LDPC. — [CCSDS 131.0-B-5 PDF](https://ccsds.org/Pubs/131x0b5.pdf)
- **Convolutional code (§3.3, "Basic Convolutional Code Specification"):** "Code rate (r): 1/2 bit per symbol. Constraint length (K): 7 bits. Connection vectors: G1 = 1111001 (171 octal); G2 = 1011011 (133 octal). Symbol inversion: On output path of G2." Punctured codes are in §3.4. — [CCSDS 131.0-B-5 PDF](https://ccsds.org/Pubs/131x0b5.pdf)
- **Reed-Solomon (§4):** g(x) "characterize[s] a (255,223) Reed-Solomon code when E = 16 and a (255,239) Reed-Solomon code when E = 8". §4.3.5.1: "The allowable values of interleaving depth are I=1, 2, 3, 4, 5, and 8." — [CCSDS 131.0-B-5 PDF](https://ccsds.org/Pubs/131x0b5.pdf)
- The standard covers convolutional, RS, concatenated (convolutional inner plus RS outer), Turbo and LDPC codes, and the pseudo-randomizer. — [CCSDS 131.0-B-5 PDF](https://ccsds.org/Pubs/131x0b5.pdf)
- ESA/ECSS adopted it as ECSS-E-AS-50-21C Rev.2 on 5 December 2024: "Adoption Notice of CCSDS 131.0-B-5 TM Synchronization and Channel Coding". — [ECSS](https://ecss.nl/standard/ecss-e-as-50-21c-rev-1-adoption-notice-of-ccsds-131-0-b-5-tm-synchronization-and-channel-coding-5-december-2024/)
- **132.0-B-3:** reference [1] of 131.0-B-5 reads "TM Space Data Link Protocol. Issue 3. Recommendation for Space Data System Standards (Blue Book), CCSDS 132.0-B-3. Washington, D.C.: CCSDS, October 2021." — [CCSDS 131.0-B-5 PDF](https://ccsds.org/Pubs/131x0b5.pdf)
- ECSS adopted 132.0-B-3 as ECSS-E-AS-50-22C Rev.1 (3 January 2023). — [ECSS](https://ecss.nl/standard/ecss-e-as-50-22c-rev-1-adoption-notice-of-ccsds-132-0-b-3-tm-space-data-link-protocol-3-january-2023/)

### Inferences
- Suggested slide citation: "CCSDS 131.0-B-5 (Sep 2023), TM Synchronization and Channel Coding" and "CCSDS 132.0-B-3 (Oct 2021), TM Space Data Link Protocol". Publisher: Consultative Committee for Space Data Systems. Relevance: the ASM, K=7 r½ Viterbi, RS(255,223) with interleave depth and the pseudo-randomizer are exactly the FEC and interleaver stack Sanket decodes and verifies; the ASM recurrence and the frame CRC give the VERIFIED proofs.
- The convolutional code and RS code are unchanged across issues -4 and -5. Only the pseudo-randomizer changed in -5, so either issue supports the ASM/conv/RS claim.

### Gaps
- I could not render the live CCSDS publications index (ccsds.org/publications/allpubs is JS-rendered). **UNCONFIRMED** whether a 131.0-B-6 or a 132.0-B-4 appeared between Sep 2023 and Sep 2026. None turned up in searches, and ECSS's Dec 2024 adoption still cites -5.
- Meteor-M LRPT using CCSDS framing and coding: not checked against a primary source in this session (**UNCONFIRMED** here, though widely documented). Note that LRPT uses the CCSDS K=7 code and RS but with its own parameters (e.g. interleaving and randomizer details), so on the slide say "CCSDS-based" rather than "CCSDS-compliant".

## 2. ITU-R Recommendations (M.540, M.476, M.625, M.584, M.493, M.1371)

### Takeaway
All in force per the ITU-R recommendation pages as of this session. The only item changed recently is M.1371, now **M.1371-6 (02/2026)**. The latest DSC version is **M.493-16 (12/2023)**. The NAVTEX- and paging-related Recommendations are old but still in force.

### Cited Findings
- **ITU-R M.540-2 (06/1990)**, in force: "Operational and technical characteristics for an automated direct-printing telegraph system for promulgation of navigational and meteorological warnings and urgent information to ships". This is the NAVTEX system Recommendation. — [ITU-R M.540](https://www.itu.int/rec/R-REC-M.540/en)
- **ITU-R M.476-5 (10/1995)**, in force: "Direct-printing telegraph equipment in the maritime mobile service". This is the SITOR / NBDP 7-unit constant-ratio code with FEC mode B. — [ITU-R M.476](https://www.itu.int/rec/R-REC-M.476/en)
- **ITU-R M.625-4 (03/2012)**, in force: "Direct-printing telegraph equipment employing automatic identification in the maritime mobile service". — [ITU-R M.625](https://www.itu.int/rec/R-REC-M.625/en)
- **ITU-R M.584-2 (11/1997)**, in force: "Codes and formats for radio paging". It supersedes M.584-1 (07/1986), "Standard codes and formats for international radio paging". — [ITU-R M.584](https://www.itu.int/rec/R-REC-M.584/en)
- **ITU-R M.493-16 (12/2023)**, in force: "Digital selective-calling system for use in the maritime mobile service". There is no newer version on the ITU page. — [ITU-R M.493](https://www.itu.int/rec/R-REC-M.493/en); PDF: [R-REC-M.493-16-202312-I](https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.493-16-202312-I!!PDF-E.pdf)
- **ITU-R M.1371-6 (02/2026)**, in force: "Technical characteristics for VHF automatic identification system using time division multiple access in the maritime mobile service". It supersedes M.1371-5 (02/2014). — [ITU-R M.1371](https://www.itu.int/rec/R-REC-M.1371/en); PDF: [R-REC-M.1371-6-202602-I](https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.1371-6-202602-I!!PDF-E.pdf)
- A secondary summary says M.1371-6 introduced "Mobile AIS AtoN". — [search summary citing Accuris preview](https://store.accuristech.com/products/preview/3097114) (secondary, not verified in the PDF)

### Inferences
- Suggested slide lines (all published by ITU Radiocommunication Sector, Geneva):
  - AIS: ITU-R M.1371-6 (2026). Relevance: GMSK 9.6 kbit/s, NRZI, HDLC framing, CRC-16 check used as the VERIFIED proof.
  - DSC: ITU-R M.493-16 (2023). Relevance: 100 Bd 2-FSK, 10-bit check code, time diversity.
  - NAVTEX: ITU-R M.540-2 (1990) plus M.476-5 (1995) and M.625-4 (2012). Relevance: SITOR-B 100 Bd FSK, 4-of-7 constant-ratio code, time-diversity repetition.
  - POCSAG: ITU-R M.584-2 (1997). Relevance: the sync codeword and BCH(31,21) codewords.
- If the slide cites M.1371 without a suffix, "M.1371-6 (02/2026)" is the current form. The project docs (PLAN.md, QandA.md) cite M.1371 without a suffix, so they are consistent.

### Gaps
- **UNCONFIRMED in this session** (from general knowledge, not fetched): that POCSAG is specifically "Radiopaging Code No. 1" in Annex 1 of M.584-2, and that the POCSAG sync word is 0x7CD215D8. Check the M.584-2 PDF before putting the annex number on the slide.
- **UNCONFIRMED:** whether NAVTEX operation is also covered by an IMO document (the IMO NAVTEX Manual) worth citing; not researched.

## 3. SigMF specification

### Takeaway
The latest released spec is **SigMF v1.2.6, released 21 December 2025**. It is published on GitHub at github.com/sigmf/SigMF, with the rendered spec on sigmf.org. The spec repository is licensed **CC BY-SA 4.0**. The sigmf-python reference library is separate (LGPL-3.0) and is not shipped in Sanket.

### Cited Findings
- The GitHub API release list gives: v1.2.6, published 2025-12-21T22:07:40Z; v1.2.5, 2025-05-16; v1.2.3, 2024-11-22. — [GitHub API: sigmf/SigMF releases](https://api.github.com/repos/sigmf/SigMF/releases?per_page=3)
  - Conflict note: the HTML releases page, as summarised by the fetch tool, showed "December 21, 2024" for v1.2.6. The API timestamp (2025-12-21) is authoritative. A WebSearch snippet also said Dec 21, 2025. — [GitHub releases page](https://github.com/sigmf/SigMF/releases)
- v1.2.6 added the `emitter_label` string field and relaxed the sample-rate validation to accept any value above zero. — [GitHub releases page](https://github.com/sigmf/SigMF/releases)
- The rendered spec PDF on sigmf.org is titled "SigMF Specification Version v1.2.6". — [sigmf.org spec PDF](https://sigmf.org/sigmf-spec.pdf) (search-result title; the PDF was not opened)
- The repository licence is CC-BY-SA-4.0. — [github.com/sigmf/SigMF](https://github.com/sigmf/SigMF)
- The python module is licensed LGPLv3, and the spec version is separate from the python module's version. — [GitHub releases page](https://github.com/sigmf/SigMF/releases)
- Earlier release history: v1.0.0, v1.1.0 and v1.2.0 were all tagged 14 April 2023, and v0.0.1 on 17 July 2019. — [GitHub releases page](https://github.com/sigmf/SigMF/releases)

### Inferences
- Slide line: "SigMF v1.2.6 (Dec 2025), Signal Metadata Format, SigMF project (github.com/sigmf; which organisation hosts it was not checked), CC BY-SA 4.0 — sigmf.org". Relevance: Sanket reads and writes `.sigmf-meta` / `.sigmf-data` / `.sigmf` archives and stores ground truth in annotations.
- Because the spec is CC BY-SA 4.0, implementing the format is fine. Only verbatim spec text copied into shipped docs would carry the share-alike obligation.

### Gaps
- I did not confirm whether any release after v1.2.6 (e.g. v1.3) exists as of Sep 2026. The API list returned v1.2.6 as the newest, which suggests there is none.

## 4. ITU-R Handbook on Spectrum Monitoring

### Takeaway
The latest published edition on the ITU site is the **2011 edition** (R-HDB-23-2011). Earlier editions were 2002 and 1995. A revised edition is reportedly being prepared; **UNCONFIRMED** whether it was published by Sep 2026.

### Cited Findings
- ITU publication page R-HDB-23 lists editions 2011, 2002 and 1995, with no 2026 edition. — [ITU-R Handbook on Spectrum Monitoring](https://www.itu.int/pub/R-HDB-23)
- 2011 edition page. — [ITU R-HDB-23-2011](https://www.itu.int/pub/R-HDB-23-2011)
- A search-result summary said "A revised ITU-R Spectrum Monitoring Handbook is being prepared ... and will be published in the public domain after June 2026". I could not trace this to a primary ITU page. — (secondary, source not identified; treat as **UNCONFIRMED**)

### Inferences
- Slide line: "ITU-R Handbook on Spectrum Monitoring, Edition 2011, ITU-R (Geneva)". Relevance: the reference practice for monitoring stations, including signal analysis and identification, the kind of work NTRO/WMO do.

### Gaps
- Whether a new edition (2025/2026) is out as of 29 Sep 2026 is not confirmed. Recheck itu.int/pub/R-HDB-23 before the deck is final.

## 5. India: Telecommunications Act, 2023 and rules under it

### Takeaway
**The Telecommunications Act, 2023 (No. 44 of 2023)** received Presidential assent on **24 December 2023**, gazetted the same day. **Section 3(1)(c)** requires an authorisation from the Central Government to *possess radio equipment*. **Section 20(2)(a)** is the interception power ("shall be intercepted or detained, or shall be disclosed in intelligible format"). Section 20 came into force on **26 June 2024**. Section 3(1) came into force only on **23 June 2026**, per law-firm reporting. Interception procedure is set by the **Telecommunications (Procedures and Safeguards for Lawful Interception of Messages) Rules, 2024 (G.S.R. 754(E), 6 Dec 2024)**, according to secondary sources.

### Cited Findings
- Gazette of India Extraordinary, Part II Section 1, No. 52, New Delhi, Sunday, December 24, 2023: "The following Act of Parliament received the assent of the President on the 24th December, 2023". Title: "THE TELECOMMUNICATIONS ACT, 2023, NO. 44 OF 2023 [24th December, 2023.]" (CG-DL-E-24122023-250880). — [eGazette PDF](https://egazette.gov.in/WriteReadData/2023/250880.pdf)
- s.1(3): the Act "shall come into force on such date as the Central Government may, by notification in the Official Gazette, appoint and different dates may be appointed for different provisions". — [eGazette PDF](https://egazette.gov.in/WriteReadData/2023/250880.pdf)
- **s.3(1):** "Any person intending to— (a) provide telecommunication services; (b) establish, operate, maintain or expand telecommunication network; or (c) possess radio equipment, shall obtain an authorisation from the Central Government, subject to such terms and conditions, including fees or charges, as may be prescribed." s.3(3) allows exemptions, and s.3(4) continues exemptions granted under the Indian Telegraph Act 1885 / Indian Wireless Telegraphy Act 1933. — [eGazette PDF](https://egazette.gov.in/WriteReadData/2023/250880.pdf)
- **s.20** (marginal heading "Provisions for public emergency or public safety"). s.20(1) covers taking temporary possession of services or networks and priority routing. **s.20(2)** reads: "On the occurrence of any public emergency or in the interest of public safety, the Central Government or a State Government or any officer specially authorised ... may, if satisfied that it is necessary or expedient so to do, in the interest of the sovereignty and integrity of India, defence and security of the State, friendly relations with foreign States, public order, or for preventing incitement to the commission of any offence, subject to such procedure and safeguards as may be prescribed, and for reasons to be recorded in writing, by order— (a) direct that any message or class of messages ... shall not be transmitted, or shall be intercepted or detained, or shall be disclosed in intelligible format to the officer mentioned in such order; or (b) [suspension of services]". — [eGazette PDF](https://egazette.gov.in/WriteReadData/2023/250880.pdf)
- **Commencement, phase 1:** sections 1, 2, 10–30, 42–44, 46, 47, 50–58, 61 and 62 were brought into force from 26 June 2024, via notification S.O. 2408(E) (notified around 21 June 2024). Section 20 is therefore in force; section 3 was not included. — [SCC Online](https://www.scconline.com/blog/post/2024/06/24/enforcement-date-for-partial-enforcement-of-the-telecommunications-act-2023-notified-legal-news/); [Mondaq](https://www.mondaq.com/india/telecoms-mobile-cable-communications/1518566/partial-notification-of-the-telecommunications-act-2023) (secondary; the S.O. itself was not opened)
- **Commencement of s.3:** "On June 23, 2026, the Department of Telecommunications ('DoT') notified Section 3(1) and Section 3(6) of the Telecommunications Act, 2023, along with certain operative rules". The rules are the Principal, Miscellaneous and Captive Telecommunication Services Authorisation Rules, 2026 and the Terms and Conditions for Migration Rules, 2026. — [Mondaq](https://www.mondaq.com/india/telecoms-mobile-cable-communications/1823106/notification-of-section-31-and-section-36-of-telecommunications-act-2023-and-operative-rule) (secondary; no S.O. number given)
- **Radio equipment possession:** a *draft* "Telecommunications (Radio Equipment Possession Authorisation) Rules, 2025" was published 27 Feb 2025 for 30 days' comment under s.3(1)(c). Draft rule text: "No person shall possess radio equipment except under and in accordance with Radio Equipment Possession Authorisation granted under rule 6, unless exempted." — [LegitQuest](https://www.legitquest.com/act/telecommunications-radio-equipment-possession-authorisation-rules-2025/10A13) (secondary; draft)
- **Interception Rules:** "Telecommunications (Procedures and Safeguards for Lawful Interception of Messages) Rules, 2024", notified by DoT on 6 December 2024 as G.S.R. 754(E), in effect from publication. Interception orders are valid for up to 60 days, renewable, with a 180-day total cap. — [TaxGuru](https://taxguru.in/corporate-law/telecom-rules-2024-lawful-interception-procedures-safeguards.html); [IFF first read](https://internetfreedom.in/first-read-telecom-interception-rules-2024/); an "as amended" copy is on [India Code](https://www.indiacode.nic.in/ViewFileUploaded?path=AC_CEN_37_58_00002_202344_1721027001853%2Frulesindividualfile%2F&file=telecommunications_%28procedures_and_safeguards_for_lawful_interception_of_messages%29_rules%2C_2024_%28as_amended%29_%282%29.pdf) (not opened)
- Official full text is also on India Code as A2023-44. — [India Code PDF](https://www.indiacode.nic.in/bitstream/123456789/20101/1/A2023-44.pdf) (returned 403 to the fetcher; the eGazette copy was read instead)

### Inferences
- Slide lines:
  - "Telecommunications Act, 2023 (No. 44 of 2023; assent 24 Dec 2023), Ministry of Law & Justice / DoT: s.20(2) lawful interception (in force 26 Jun 2024); s.3(1)(c) authorisation to possess radio equipment (s.3(1) in force 23 Jun 2026)". Relevance: Sanket analyses recordings made by an authorised agency. It does no interception itself and no live capture from network receivers.
  - "Telecommunications (Procedures and Safeguards for Lawful Interception of Messages) Rules, 2024, G.S.R. 754(E), 6 Dec 2024". Relevance: governs how the captures Sanket analyses are lawfully obtained and how intercepted records are held and destroyed.
- Section 20(2) is about *messages transmitted by telecommunication services/networks*. Blind analysis of RF recordings by NTRO sits within that authorised-agency framework, but the slide should avoid saying the tool "performs interception".
- Precise wording for s.3: the Act requires authorisation to possess radio equipment. Whether a receive-only SDR is covered, or exempt, depends on rules and exemptions (s.3(3), s.3(4)) that were still being finalised (the possession rules were only a draft as of Feb 2025).

### Gaps
- **UNCONFIRMED:** the S.O. number and gazette date for the 23 June 2026 notification of s.3(1)/(6). I also did not confirm whether s.3(1)(c) (radio-equipment possession) took operative effect then, or only the service/network limbs with their rules.
- **UNCONFIRMED:** whether the Radio Equipment Possession Authorisation Rules were notified in final form after the Feb 2025 draft.
- G.S.R. 754(E) was not opened on egazette.gov.in. Date and number are from multiple secondary legal sources that agree.

## 6. India: National Frequency Allocation Plan (NFAP)

### Takeaway
The latest edition is **NFAP-2025**, released by DoT (prepared by the WPC Wing) and effective **30 December 2025**. It covers 8.3 kHz to 3000 GHz and succeeds NFAP-2022 (and NFAP-2018 before it).

### Cited Findings
- A PIB press release is titled "The National Frequency Allocation Plan 2025 (NFAP-2025) released ..." (PRID 2209717). — [PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2209717&reg=3&lang=1) (title from search results; the page returned 403 to the fetcher)
- "India DoT Publishes the National Frequency Allocation Plan (NFAP) 2025, effective December 30, 2025". — [CSA Group regulatory update](https://www.csagroup.org/global-certification-regulatory-update/india-dot-publishes-the-national-frequency-allocation-plan-nfap-2025-effective-december-30-2025/) (title from search results; page returned 403)
- NFAP-2025 covers 8.3 kHz–3000 GHz, is prepared by the WPC Wing of DoT, and identifies 6425–7125 MHz for IMT. — search-result summaries of [PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2209717&reg=3&lang=1) and [Tribune India](https://www.tribuneindia.com/news/5g-networks/dot-releases-national-frequency-allocation-plan-2025-to-power-5g-6g-satellite-based-services)
- Previous editions: [NFAP 2022 (DoT PDF)](https://dot.gov.in/sites/default/files/NFAP%202022%20Document%20for%20e-release.pdf?download=1) and [NFAP 2018 (DoT PDF)](https://dot.gov.in/sites/default/files/NFAP%202018.pdf?download=1). The WPC landing page is at [wpc.dot.gov.in NFAP](http://www.wpc.dot.gov.in/Static/NFAP.asp).

### Inferences
- Slide line: "National Frequency Allocation Plan 2025 (NFAP-2025), DoT / WPC Wing, effective 30 Dec 2025". Relevance: the band plan used to form centre-frequency and service hypotheses (e.g. maritime VHF for AIS/DSC, 518/490 kHz NAVTEX, VHF paging bands) when a recording's metadata gives a frequency.

### Gaps
- Exact PIB release date (probably mid/late December 2025) not confirmed, because the page returned 403. The direct URL of the NFAP-2025 PDF was not found.

## 7. Optional context figures: Lok Sabha GPS interference answer; WMO station count

### Takeaway
**1,951** GPS-interference reports (Nov 2023–Nov 2025) came from MoS Civil Aviation Murlidhar Mohol's written reply in the **Lok Sabha**, reported around early to mid December 2025 (confirmed via press, not the Sansad PDF). A later reply gives **2,354** (Nov 2023–Dec 2025). The **Wireless Monitoring Organisation** network is 22 Wireless Monitoring Stations + 5 International Monitoring Stations + 1 International Satellite Monitoring Earth Station (Jalna) = **28**.

### Cited Findings
- Quote: "Total GPS interference issues reported (November 2023 to November 2025) are 1,951 after publication of DGCA circular". Given in the Lok Sabha by MoS Civil Aviation Murlidhar Mohol; article dated 12 December 2025. — [Millennium Post](https://www.millenniumpost.in/big-stories/1951-issues-of-aircraft-gps-interference-reported-in-2-yrs-639406); also [The Patriot](https://thepatriot.in/delhi-ncr/govt-says-1951-issues-of-aircraft-gps-interference-reported-in-2-years-79465), [Swarajya](https://swarajyamag.com/news-brief/nearly-2000-gps-interference-cases-reported-at-major-airports-in-india-since-2023-centre)
- The reporting rise followed the DGCA advisory circular of 24 Nov 2023. AAI asked the Wireless Monitoring Organisation to identify the interference source. — [Deccan Herald](https://www.deccanherald.com/india/aviation-ministry-confirms-gps-spoofing-incidents-at-airports-outlines-measures-taken-to-address-threat-3815897); [The Register, 3 Dec 2025](https://www.theregister.com/2025/12/03/india_gps_spoofing/)
- A separate figure: 2,354 GPS-interference reports from Nov 2023 to Dec 2025, also attributed to Mohol in a Lok Sabha written reply. — search summary citing [India TV](https://www.indiatvnews.com/news/india/some-flights-reported-gps-spoofing-near-delhi-airport-government-tells-parliament-2025-12-01-1019784) / [Swarajya](https://swarajyamag.com/news-brief/nearly-2000-gps-interference-cases-reported-at-major-airports-in-india-since-2023-centre) (the exact source of the 2,354 figure is **UNCONFIRMED**)
- Also: 623 GPS-interference incidents around Delhi in Jan–Feb 2026. — [The Hawk](https://www.thehawk.in/news/india/airlines-report-623-incidents-of-gps-spoofing-in-delhi-airspace-during-january-february)
- The WMO, a field unit of the WPC Wing, runs "1 International Satellite Monitoring Earth Station (ISMES), 5 International Monitoring Stations (IMSs), and 22 Wireless Monitoring Stations (WMSs)". The ISMES is at Jalna (Maharashtra), set up 1992-93 with SAC/ISRO. — [DoT (C-DOT-hosted) WMO page](https://dotws.cdot.in/wireless-monitoring-organisation); [DoT WMO page](https://dot.gov.in/hi/node/6879); [Jalna district ISMES page](https://jalna.gov.in/en/departments/ismes/)

### Inferences
- 22 + 5 + 1 = 28 monitoring facilities. The DoT page gives the components, not the total "28", so on the slide write "22 WMS + 5 IMS + 1 ISMES".
- For the GPS figure, cite "Lok Sabha written reply, MoS Civil Aviation, Dec 2025: 1,951 GPS-interference reports, Nov 2023–Nov 2025". Relevance: it shows demand for offline analysis of recorded RF interference. Note the 2,354 figure covers a longer window, so the two are not in conflict.

### Gaps
- **UNCONFIRMED:** the Lok Sabha question number and exact reply date. The sansad.in PDF was not located, so the figure is confirmed only via multiple press reports quoting the reply.
- The date on the DoT WMO page's station count was not checked, so the count could be dated.
