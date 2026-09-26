# Real, Licensed IQ Recordings for Validating a Signal-Analysis Tool (SIH26147) and Lawful Capture in India

Research date: 2026-09-27. Items marked "(background knowledge, verify)" in Inferences are not backed by a fetched source in this session.

## 1. Public SigMF archives and IQ collections (licences, formats)

### Takeaway
Several free IQ sources exist, but licences differ a lot. Recordings in the SigMF / IQEngine / LakeShark style are the cleanest to use (each file declares its own licence, often CC0 or CC-BY). The big ML datasets (DeepSig RadioML, WiSig) are CC BY-NC-SA 4.0, which is fine for a non-commercial hackathon but means you must give credit and share derivatives under the same terms. NIST's CBRS radar set is public but synthetic. The sigidwiki/Artemis clips are mostly compressed audio and waterfall images, not raw IQ.

### Cited Findings
**IQEngine / GNU Radio SigMF repo**
- IQEngine is an open-source web tool for uploading, sharing and analysing RF recordings, built around SigMF metadata and annotations — [Hackster.io](https://www.hackster.io/news/the-open-source-project-iqengine-lets-you-share-and-analyze-rf-recordings-bb97085584a6); [GitHub 777arc/IQEngine](https://github.com/777arc/IQEngine)
- The main instance at iqengine.org is hosted by GNU Radio. It is connected to the official SigMF examples repository and serves as the central store of example SigMF recordings — [rtl-sdr.com](https://www.rtl-sdr.com/iqengine-a-web-based-toolkit-for-sharing-and-analyzing-rf-iq-recordings/); [iqengine.org browser](https://iqengine.org/browser); [GNU Radio wiki: SigMF Recordings Repo](https://wiki.gnuradio.org/index.php?title=SigMF_Recordings_Repo) (the wiki returned 403 on fetch, so its contents were not checked)
- In SigMF, each recording declares its own licence in its metadata (the `core:license` field) — [search summary citing sigmf/LakeShark repos](https://github.com/sigmf/SigMF)
- The sigmf-python library is LGPL-3.0 — [sigmf-python](https://github.com/sigmf/sigmf-python)

**LakeShark-Signal-Corpus**
- Purpose: "short, reviewed IQ recordings for testing open radio decoders" such as P25, analog FM, POCSAG and ADS-B. Format: SigMF pairs under `captures/<name>/`. Data is interleaved unsigned 8-bit IQ (cu8), up to 64 MiB per file. Metadata includes sample rate, tuned frequency, UTC capture time, a SHA-512 checksum, and a description of the signal and antenna — [GitHub LakeShark-Signal-Corpus](https://github.com/SAMS0N1TE/LakeShark-Signal-Corpus)
- Per-recording licence is CC0-1.0 or CC-BY-4.0. The validation tooling is MIT. `tools/validate.py` checks structure and checksums but not RF content. Contributors are asked to "explain what a decoder should find" — [same](https://github.com/SAMS0N1TE/LakeShark-Signal-Corpus)
- **As fetched, the repository "starts empty": no recordings had been merged yet.** It is a new project that accepts contributions — [same](https://github.com/SAMS0N1TE/LakeShark-Signal-Corpus)

**NIST 3.5 GHz CBRS radar dataset**
- "RF Dataset of Incumbent Radar Systems in the 3.5 GHz CBRS Band": synthetically generated radar waveforms plus AWGN. There are 4 groups × 50 `.mat` files × 200 waveforms (40,000 records). Sample rate 10 MHz, duration 80 ms, noise power density −109 dBm/MHz. Complex IQ is provided with radar-status labels. v1.1.0 was released 2019-11-21 at DOI 10.18434/M32116, and the data are public — [NIST PDR mds2-2116](https://data.nist.gov/od/id/mds2-2116); [data.gov](https://catalog.data.gov/dataset/rf-dataset-of-incumbent-radar-systems-in-the-3-5-ghz-cbrs-band); [Data dictionary PDF](https://opendata.nist.gov/pdrsrv/mds2-2116/Data%20Dictionary%20of%203.5%20GHz%20Radar%20Waveforms.pdf)
- A spectrogram object-detection derivative is on Zenodo — [Zenodo 22005788](https://zenodo.org/records/22005788)

**DeepSig RadioML**
- All DeepSig datasets are CC BY-NC-SA 4.0. For other terms, contact info@deepsig.io — [DeepSig datasets](https://www.deepsig.ai/datasets/); [sofwerx mirror](https://github.com/sofwerx/deepsig_datasets)
- RadioML 2018.01A: 24 modulation types, 2.56 million labelled examples, each 1024 complex IQ samples. It comes from the paper "Over-the-air deep learning based radio signal classification" (IEEE JSTSP) — [Kaggle mirror](https://www.kaggle.com/datasets/pinxau1000/radioml2018); [KristynaPijackova README](https://github.com/KristynaPijackova/Radio-Modulation-Recognition-Networks/blob/main/README.md)

**ORACLE / WiSig / POWDER (RF fingerprinting)**
- ORACLE: 16 USRP X310 transmitters and a B210 receiver, sending IEEE 802.11a frames (MATLAB WLAN toolbox) at 5 MS/s with a 2.45 GHz centre frequency. Distances are 2–62 ft, with more than 20 M samples per radio. Format is SigMF, **but the data is actually complex128 even though the metadata says 32-bit**. There are two sets (over-the-air raw IQ, and over-cable demodulated symbols with 16 IQ-imbalance configurations), downloadable via handle.net links. Terms: cite the INFOCOM 2019 / IEEE TCCN paper — [GENESYS ORACLE](https://www.genesys-lab.org/oracle)
- WiSig: 10 M packets from 174 commercial Wi-Fi transmitters, captured by 41 USRP receivers over 4 captures spanning a month. Pre-processed subsets are available. Licence CC BY-NC-SA 4.0 — [WiSig licence page](https://cores.ee.ucla.edu/wisig/license/); [arXiv 2112.15363](https://arxiv.org/pdf/2112.15363v2)
- POWDER: raw over-the-air IQ from 4 base stations on the POWDER platform in Salt Lake City — [GENESYS POWDER](https://genesys-lab.org/powder) (licence not checked)

**Drone RF datasets**
- DroneRF: 227 recorded segments from 3 drones in several modes, plus background RF with no drone. Hosted on Zenodo, with a Data in Brief paper — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2352340919306675); [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6727013/)
- DroneDetect: 7 UAS models (DJI Mavic 2 Air S, Mavic Pro, Mavic Pro 2, Inspire 2, Mavic Mini, Phantom 4, Parrot Disco). Raw IQ recorded with a BladeRF and GNU Radio. Listed as open access on IEEE DataPort — [IEEE DataPort](https://ieee-dataport.org/open-access/dronedetect-dataset-radio-frequency-dataset-unmanned-aerial-system-uas-signals-machine)
- RFUAV benchmark: raw IQ for drone detection and identification; the repo says raw data is "free to use" after paper acceptance — [GitHub](https://github.com/alimp5/drone-rf-dataset)
- DroneRF2025 is on IEEE DataPort — [link](https://ieee-dataport.org/documents/dronerf2025)

**sigidwiki / Artemis**
- The Artemis DB (`db.csv`) is extracted from sigidwiki.com. Audio samples are OGG at the original rate, capped at 60 s; waterfalls are PNG. Artemis software is GPL-3. On the data: "there is no licensing for these materials, as they are 'of nature', recordings of an rf environment" — [AresValley/Artemis-DB](https://github.com/AresValley/Artemis-DB); [Artemis docs](https://aresvalley.github.io/Artemis/database/sigid/); [rtl-sdr.com Artemis 3](https://www.rtl-sdr.com/artemis-3-released-offline-signal-identification-database/)

**SatNOGS**
- All observation results and API data are CC BY-SA. Artifacts are audio, waterfall and decoded frames. **IQ data is not uploaded to SatNOGS Network**; some station owners publish it elsewhere or share on request — [SatNOGS Wiki: Artifacts](https://wiki.satnogs.org/Artifacts); [SatNOGS Wiki Operation](https://wiki.satnogs.org/Operation)
- One such external archive is SatNOGS IQ from the Dwingeloo radio telescope (CAMRAS) — [data.camras.nl/satnogs](https://data.camras.nl/satnogs/)
- There is a documented way to replay observations from the archived audio — [SatNOGS Wiki](https://wiki.satnogs.org/Wiki/Replay_observations_from_audio)

### Inferences
- Summary catalogue:

| Source | Real / synthetic | Format | Rate | Licence | Ground truth |
|---|---|---|---|---|---|
| IQEngine / SigMF examples | Real (mixed) | SigMF | varies | per-file `core:license` | SigMF annotations (some) |
| LakeShark corpus | Real (RTL-SDR) | SigMF cu8 | varies | CC0 / CC-BY-4.0 | text "what decoder should find"; currently empty |
| NIST CBRS radar | Synthetic + AWGN | .mat | 10 MS/s | public (US gov) | yes (radar params/status) |
| DeepSig RadioML 2018.01A | Mostly synthetic with channel effects, some OTA | HDF5 | 1024-sample frames | CC BY-NC-SA 4.0 | modulation + SNR labels |
| ORACLE | Real OTA / cable | SigMF (complex128) | 5 MS/s | cite paper | transmitter ID |
| WiSig | Real OTA | pickled subsets / raw | ~Wi-Fi | CC BY-NC-SA 4.0 | TX/RX ID |
| DroneDetect / DroneRF / RFUAV | Real | raw IQ / CSV | multi-MS/s | check DataPort/Zenodo | drone model and mode |
| sigidwiki / Artemis | Real | OGG audio + PNG | audio | "no licensing" (unclear) | human ID label only |
| SatNOGS | Real | audio/waterfall/frames (no IQ) | — | CC BY-SA | decoded frames (CRC) |

- The HDF5 format and the "mostly synthetic" nature of RadioML 2018.01A are background knowledge; verify before claiming.
- For a judge-facing demo, SigMF files with CC0 or CC-BY licences (IQEngine, and LakeShark once populated), plus your own captures, carry the least licensing risk.
- ORACLE's complex128 quirk is a good test that your SigMF loader validates the file size against the declared datatype.

### Gaps
- The exact list of recordings and licences in the GNU Radio / IQEngine SigMF repo could not be retrieved (wiki returned 403).
- Licences for DroneRF (Zenodo), POWDER and RFUAV were not confirmed.
- The sigidwiki page-level licence (the site's own content licence, as opposed to Artemis's statement) was not confirmed.
- No NTIA-specific IQ archive was researched beyond NIST CBRS.

## 2. Recordings with verifiable ground truth (CRC-bearing protocols)

### Takeaway
Protocols with CRCs or checksums (ADS-B CRC-24, AIS CRC-16, POCSAG BCH, AX.25 FCS, NAVTEX FEC/SITOR-B, RDS checkwords) give you self-verifying ground truth. Decode with a reference decoder, then count frames that pass the CRC. SatNOGS offers CRC-checked decoded frames (CC BY-SA) but no IQ. LakeShark explicitly invites ADS-B and POCSAG IQ. Own captures are the most reliable way to get paired IQ plus decoded truth.

### Cited Findings
- LakeShark invites P25, POCSAG and ADS-B captures and asks contributors to explain what a decoder should find — [LakeShark corpus](https://github.com/SAMS0N1TE/LakeShark-Signal-Corpus)
- SatNOGS artifacts include decoded data frames alongside audio and waterfall, all CC BY-SA — [SatNOGS Wiki Artifacts](https://wiki.satnogs.org/Artifacts)
- Indian NAVTEX stations (DGLL) broadcast English on 518 kHz and local languages on 490 kHz, with 250 NM coverage. The stations, with 518/490 IDs and 518 kHz UTC schedule, are:
  - Veraval H/P: 0110, 0510…
  - Vengurla Point J/R: 0130…
  - Muttam Point L/T: 0150…
  - Porto Novo O/E: 0220…
  - Vakalpudi Q/G: 0240…
  - Balasore S/I: 0300…
  - Keating Point (Andaman) V/K: 0330…

  Every station repeats at 4-hour intervals — [DGLL NAVTEX](https://www.dgll.nic.in/about-DGLL/Service-reminders/navtex)
- ADS-B broadcasts are unencrypted and receivable with a USB SDR dongle and antenna — [Wikipedia Flightradar24](https://en.wikipedia.org/wiki/Flightradar24)

### Inferences
- Validation recipe: record IQ, then run reference decoders on the same file, then count CRC-valid frames. Compare your tool's detected signal type, centre frequency, baud and modulation against the protocol spec. Reference decoders (background knowledge): dump1090/readsb for ADS-B, AIS-catcher/rtl_ais for AIS, multimon-ng for POCSAG/APRS/EAS, direwolf for AX.25, SatDump for NOAA APT and Meteor LRPT, redsea for RDS, fldigi or a NAVTEX decoder for SITOR-B.
- Protocol parameters useful as ground truth (background knowledge, verify):
  - ADS-B: 1090 MHz, PPM at 1 Mbit/s, 112-bit frames with CRC-24
  - AIS: 161.975 / 162.025 MHz, GMSK 9600 bd, HDLC CRC-16
  - POCSAG: 512/1200/2400 bd 2-FSK, BCH(31,21)
  - APRS: 144.390 MHz in the US; **India uses 144.390 MHz too per some sources, verify**. AFSK 1200 bd with AX.25 FCS
  - RDS: 57 kHz subcarrier, 1187.5 bps BPSK, 10-bit checkwords
  - NAVTEX: 100 bd FSK (170 Hz shift), SITOR-B FEC
  - Meteor LRPT: QPSK 72 ksym/s, with Reed-Solomon and Viterbi coding
- A NAVTEX broadcast at 518 kHz is an ideal HF test with a known schedule, known station ID letters, and India-specific content. It can be captured via KiwiSDR or with a direct-sampling RTL-SDR.

### Gaps
- I found no public dataset of paired IQ plus CRC-verified decodes for Indian signals. This would have to be self-generated.
- The status of NOAA-15/18/19 APT in 2026 was not verified. NOAA has been decommissioning POES satellites; treat APT as possibly unavailable. The Meteor-M N2-3 / N2-4 LRPT status was not verified.

## 3. KiwiSDR / WebSDR in India and recording IQ (kiwirecorder)

### Takeaway
Public KiwiSDR receivers exist in India, at least in Bangalore. You can record IQ with kiwirecorder.py (`-m iq --kiwi-wav`), which writes WAV files with GNSS timestamps. The bandwidth is narrow (about 12 kHz per channel), which suits HF voice and data modes, NAVTEX and HFDL, but not wideband signals.

### Cited Findings
- Multiple KiwiSDRs are listed in Bangalore, alongside UberSDR and OpenWebRX receivers there. Skywave Linux keeps an auto-updated (every 3 hours) list of Indian cities with KiwiSDRs covering MW and SW. The PDF returned 404 at fetch time, so this is from the search summary — [Skywave Linux MW list](https://skywavelinux.com/websdr-mediumwave-list.html)
- More than 300 public KiwiSDRs are listed at rx.kiwisdr.com / kiwisdr.com/public. rx.linkfanel.net and kiwisdr.com/public both refused connection during this session — [kiwisdr.com](http://kiwisdr.com/)
- kiwiclient/kiwirecorder.py receives audio, IQ and waterfall streams. For IQ with GNSS timestamps, the README says: "Use the option `-m iq --kiwi-wav --station=[name]`". Other options: `--netcat` streams to stdout, `--camp-chan` camps on an existing channel, and several Kiwis can be recorded at once. `--help` lists all options — [kiwiclient README](https://github.com/jks-prv/kiwiclient/blob/master/README.md); [kiwirecorder.py](https://github.com/jks-prv/kiwiclient/blob/master/kiwirecorder.py)
- kiwirecorder can be used to automate recordings and avoid the inactivity timeout — [Gough's Tech Zone](https://goughlui.com/2019/01/28/quick-tip-use-kiwirecorder-py-to-automate-recordings-evade-inactivity-time-outs/)
- A KiwiSDR forum thread discusses the limits of recording IQ wider than 20 kHz from a single Kiwi — [KiwiSDR forum](https://forum.kiwisdr.com/index.php?p=%2Fdiscussion%2F1450%2Frecording-iq-data-with-gt-20khz-bandwidth-from-a-single-kiwisdr); [What is an IQ file](https://forum.kiwisdr.com/index.php?p=%2Fdiscussion%2F2040%2Fwhat-is-an-iq-file-and-how-can-i-use-it)

### Inferences
- Example command (verify flags with `--help`): `python3 kiwirecorder.py -s <host> -p 8073 -f 518 -m iq --kiwi-wav --tlimit 600 --station=NAVTEX518`
- The Kiwi IQ rate is about 12 kS/s in the common configuration and about 20.25 kS/s in the wideband/3-channel firmware mode (background knowledge, verify).
- Etiquette: each Kiwi has a few user slots (about 4–8) and owners may set time limits or passwords. Keep recordings short, stay within the owner's stated limits, and credit the receiver owner. There are no formal uniform terms of use; owners set per-receiver policies. This is background knowledge; I did not retrieve a formal ToS.
- HF signals likely receivable from Indian Kiwis (background knowledge, verify):
  - AIR shortwave and MW, and DRM transmissions from AIR
  - Indian NAVTEX on 518/490 kHz
  - Mumbai/Kolkata/Delhi VOLMET on HF
  - HFDL ground stations in the Indian Ocean region
  - FT8 at 7.074 / 14.074 MHz, PSK31, RTTY contests
  - STANAG 4285 / MIL-STD-188-110 military modems (receivable, but outside the student scope)
  - Time signals

### Gaps
- An exact current list of KiwiSDRs in India (cities, URLs) could not be fetched because the map sites refused connection.
- No formal KiwiSDR terms-of-use document was found.
- The Indian VOLMET and HFDL frequencies were not verified in this session.

## 4. Legal position in India on receive-only SDR use

### Takeaway
The Telecommunications Act 2023 repealed the Indian Wireless Telegraphy Act 1933. Its Section 3 requires government authorisation to "possess radio equipment", with exemptions defined in rules. The draft Radio Equipment Possession Authorisation Rules (27 Feb 2025) replace the 1965 Possession Rules. I could not confirm the final text or whether a general-purpose receiver/SDR is exempt. **The position is grey: formally, possession may need authorisation or an exemption, and there is no explicit student/hobby carve-out I could verify.** Plane-spotting radio use reportedly needs WPC permission. The lowest-risk path is to use public datasets and remote KiwiSDRs, capture only unencrypted broadcast and safety signals, work under an institution/lab, and consult WPC or the NTRO organisers.

### Cited Findings
- The Telecommunications Act 2023 repeals the Indian Telegraph Act 1885, the Indian Wireless Telegraphy Act 1933 and the Telegraph Wires (Unlawful Possession) Act 1950. It received assent on 24 Dec 2023, and sections came into force on 26 Jun 2024 and 5 Jul 2024. Licences granted under the old Acts are deemed granted under the new one — [PHDCCI note](https://www.phdcci.in/wp-content/uploads/2024/06/New-Telecommunications-Act-2023-comes-into-force-repealing-the-Indian-Telegraph-Act-1885-and-Indian-Wireless-Telegraph-Act-1933.pdf); [Wikipedia](https://en.wikipedia.org/wiki/Telecommunications_Act,_2023); [Act text](https://www.indiacode.nic.in/bitstream/123456789/20101/1/A2023-44.pdf)
- The old IWTA 1933 prohibited possession of wireless telegraphy apparatus without a licence, subject to Central Government exemptions — [CIS India](https://cis-india.org/telecom/resources/indian-wireless-telegraphy-act); [India Code IWTA PDF](https://www.indiacode.nic.in/bitstream/123456789/15410/1/the_indian_wireless_telegraphy_act,_1933.pdf)
- Section 3 of the 2023 Act: any person intending to provide telecom services, run networks, **or possess radio equipment** must obtain authorisation — [Mondaq](https://www.mondaq.com/india/broadcasting-film-tv-radio/1625116/dot-releases-new-radio-equipment-possession-authorization-rules)
- The draft Telecommunications (Radio Equipment Possession Authorisation) Rules 2025 were published 27 Feb 2025 with 30 days for comment, and supersede the IWT (Possession) Rules 1965. Their text says: "No person shall possess radio equipment except under a Radio Equipment Possession Authorisation granted under rule 6, unless exempted ... under rule 4". There are two categories: Dealer (1–5 yr, ₹10,000/yr) and Special (up to 2 yr, ₹10,000/yr) — [Mondaq](https://www.mondaq.com/india/broadcasting-film-tv-radio/1625116/dot-releases-new-radio-equipment-possession-authorization-rules); [TeamLease RegTech](https://www.teamleaseregtech.com/updates/article/40042/draft-telecommunications-radio-equipment-possession-authorisation-rule/); [PublicNow DoT notice](https://www.publicnow.com/view/B4C91665CE82D70C8209155A5D872A68A827AEE2); [LegitQuest (rules listing)](https://www.legitquest.com/act/telecommunications-radio-equipment-possession-authorisation-rules-2025/10A13)
- Radio products made in or imported into India need a WPC Equipment Type Approval (ETA) — [DoT eServices import licence](https://eservices.dot.gov.in/import-license); [Vincular WPC](https://www.vincular.in/wpc)
- Amateur licensing is run by WPC, with General and Restricted grades and the ASOC exam (Radio theory, Regulations, and Morse practical for the General grade). The 1978 rules had a Short Wave Listener licence with no exam; the current SWL status is unspecified — [Wikipedia: Amateur radio licence categories in India](https://en.wikipedia.org/wiki/Amateur_radio_licence_categories_in_India)
- A search summary stated that "use of any category of radio equipment for plane-spotting requires permission from WPC". This comes from a Wikipedia/search aggregate and was not verified against a primary WPC source — [search result, Wikipedia amateur radio India pages](https://en.wikipedia.org/wiki/Amateur_radio_licence_categories_in_India)

### Inferences
- Whether the final rules exempt ordinary broadcast receivers or ETA-approved consumer devices is unknown. Historically, broadcast receivers were exempted from licensing by notification. A generic 24 MHz–1.7 GHz SDR is not obviously a "broadcast receiver", so possession is technically a grey area.
- Separately from possession, intercepting or disclosing private communications is a distinct risk. Restrict captures to broadcast, safety and public signals: FM/RDS, NAVTEX, ADS-B (reception only, with no public feeding of military data), AIS, weather satellites, and amateur transmissions. Record nothing encrypted, private or military.
- Recommendation for the team: (1) prefer public datasets and remote KiwiSDRs; (2) if capturing locally, do it under the college's lab or institutional umbrella and ask the NTRO/SIH organisers whether they supply sample IQ; (3) do not transmit (no HackRF TX); (4) document the licence and provenance of every file.

### Gaps
- The final (non-draft) Radio Equipment Possession Authorisation Rules and their rule-4 exemption list were not found. This is the key open legal question.
- No primary WPC source on plane-spotting or ADS-B permission was found.
- No enforcement case law against hobby receive-only SDR users in India was found.

## 5. RTL-SDR availability and price in India; receivable VHF/UHF signals

### Takeaway
The RTL-SDR Blog V4 is sold by Indian electronics retailers (Robu.in, ElectroPi, Fab.to.Lab) at roughly ₹5,800–₹12,000 (dongle only, about ₹6,000 typical). Receivable signals in Indian cities include FM with RDS (where used), ADS-B at 1090 MHz near airports, AIS on the coasts (Mumbai, Chennai, Kochi, Vizag), Meteor LRPT/NOAA APT (status to verify), and amateur satellites. With a direct-sampling mode, NAVTEX at 518 kHz is also reachable from the coasts.

### Cited Findings
- RTL-SDR Blog V4 (R828D, RTL2832U, 1 PPM TCXO, SMA) is sold in India by Robu.in, ElectroPi.in and Fab.to.Lab. Fab.to.Lab also offers a dipole antenna kit — [Robu.in](https://robu.in/product/rtl-sdr-blog-v4-r828d-rtl2832u-1ppm-tcxo-sma-software-defined-radio-with-dipole-antenna-kit/); [ElectroPi](https://www.electropi.in/rtl-sdr-blog-v4-r828d-rtl2832u-1ppm-tcxo-sma-software-defined-radio-dongle-only); [Fab.to.Lab](https://www.fabtolab.com/rtl-sdr-blog-v4-r828d-rtl2832u-1ppm-tcxo-sma-software-defined-radio-dongle-only)
- Price tracker: current ₹6,028, average ₹7,635, low ₹5,787, high ₹11,887 (dongle only). One result said the V4 was "discontinued" with V3 available. This is unverified and possibly a single retailer's listing status — [pricehistory.app](https://pricehistory.app/p/rtl-sdr-blog-v4-r828d-rtl2832u-1ppm-tWbCvAIm)
- NAVTEX coverage extends 250 NM from Indian coast stations (for coastal cities) — [DGLL](https://www.dgll.nic.in/about-DGLL/Service-reminders/navtex)
- DIY ADS-B receivers (for example the Flightradar24 Pi24 client) are a documented hobby setup — [Flightradar24 build-your-own](https://www.flightradar24.com/build-your-own)

### Inferences
Receivable signals (background knowledge, verify locally):
- **FM broadcast** at 88–108 MHz (AIR FM Rainbow/Gold, private FM). RDS use in India is sparse and inconsistent, so check before relying on it.
- **ADS-B** at 1090 MHz: dense near metro airports (Delhi, Mumbai, Bengaluru, Hyderabad, Chennai).
- **AIS** at 161.975 / 162.025 MHz: coastal cities only.
- **Weather satellites**: Meteor-M LRPT at 137 MHz with a V-dipole or QFH antenna. NOAA APT only if a satellite is still active.
- **Amateur satellites**: ISS APRS/SSTV, and cubesats (including Indian student sats when active) observable via SatNOGS.
- **Amateur VHF/UHF**: 144–146 and 434–438 MHz repeaters and APRS.
- **Other**: airband AM at 118–137 MHz (legally more sensitive; avoid), ISM 433 MHz sensors, and LoRa at 865–867 MHz (the Indian ISM band).

Suggested capture plan:
- (a) Budget kit: RTL-SDR V4 plus dipole kit, for about ₹6–8k in total.
- (b) Capture 30–120 s SigMF recordings in cu8 at 2.048–2.4 MS/s:
  - FM + RDS
  - ADS-B at 2 MS/s
  - AIS on the coast
  - Meteor pass via SatDump
  - 433 MHz sensors, decoded with rtl_433
  - NAVTEX via KiwiSDR
- (c) For each recording, store the reference-decoder output (CRC-valid frame count, decoded messages) as ground-truth annotations in the SigMF metadata.
- (d) Licence your own captures CC-BY-4.0 and optionally contribute them to LakeShark.

### Gaps
- No verified evidence of RDS deployment on Indian FM stations was found.
- The operational status of NOAA APT and Meteor satellites in 2026 was not verified.
- Whether the V4 is really discontinued in 2026 was not confirmed (conflicting retailer info).
- ISRO or Indian student cubesat downlinks active in 2026 were not researched.
