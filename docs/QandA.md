# Sanket — questions and answers

The questions we have asked about Sanket and the radio theory behind it, with the answers. Use it to learn the project or to explain it to someone else.

Status: see [PLAN §0](PLAN.md#0-progress), the only place progress is tracked; where this document says *built*, *planned* or *after 1.0*, PLAN is the authority. Rival and vendor facts come from [STANDARDS_TO_BEAT.md](STANDARDS_TO_BEAT.md); the problem statement is quoted from [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md).

**Contents**

1. [The project](#1-the-project)
2. [Radio theory](#2-radio-theory)
3. [Recognising and decoding signals](#3-recognising-and-decoding-signals)
4. [Inputs and outputs](#4-inputs-and-outputs)
5. [The screen](#5-the-screen)
6. [Technology choices](#6-technology-choices)
7. [The competition](#7-the-competition)
8. [Scope decisions](#8-scope-decisions)
9. [Questions judges are likely to ask](#9-questions-judges-are-likely-to-ask)

---

## 1. The project

### What is Sanket, in one line?

Sanket (संकेत, "signal") takes a radio recording nobody has explained to you, works out how the signal was built, and takes that construction apart layer by layer to get the original bits back. It shows the evidence for every answer and how sure it is.

It is our entry for Smart India Hackathon problem **SIH26147**, set by NTRO: *"Automated model for analysis of .IQ and .wav files along with signal parameter extraction."* The category is Software and the theme is Space Technology.

### Why does this matter? Who needs it?

- **The work is slow and manual today.** The problem statement says so: *"The analysis is being carried out manually to identify the signal parameters."* Our source dossier puts isolating and classifying one signal of interest at 12–18 person-hours. That figure is from the dossier and hasn't been re-verified.
- **The leading tools are foreign and restricted.** Krypto500 is ITAR-controlled (US arms-export law) with no trial version. Its German and Swiss competitors are export-controlled and mostly sold only on quotation. An open, Indian-built tool fits Atmanirbhar Bharat and the defence indigenisation lists.
- **The need is measurable.** India logged 1,951 GPS-interference incidents between November 2023 and November 2025 (Lok Sabha answer, via the dossier). WMO/WPC runs 28 monitoring stations that hunt illegal and interfering transmitters.
- **Who would use it:**
  - NTRO and defence signals-intelligence units
  - WMO/WPC, DoT and TRAI (spectrum enforcement)
  - DGCA (GPS jamming)
  - ISRO and satellite operators
  - disaster-response agencies
  - researchers and radio amateurs

### What does the problem statement ask for, and how well do we match it?

The PS asks for a GUI-based, automated model that takes an `.IQ` or `.wav` file and does five things:
1. identify the sampling frequency, modulation, FEC and interleaving
2. demodulate FSK, QAM and PSK
3. de-interleave block, convolutional, diagonal and pseudo-random interleavers
4. decode short-constraint convolutional codes (Viterbi), RS, concatenated codes and LDPC
5. correlate the bitstream to identify header and payload

The GUI must show sampling frequency, a constellation plot and a waterfall.

**Our design covers every requirement.** The prototype chain in [DEMO.md](DEMO.md) already runs every PS item end to end on synthetic recordings — sampling frequency, modulation and FEC identification, PSK/QAM/FSK demodulation, block de-interleaving, convolutional (Viterbi) and RS decoding, and bitstream correlation to header/payload — for the modulations and codes built so far. See [PLAN §0](PLAN.md#0-progress) for exactly what's built versus still open.

Where we deliberately deliver something different from a literal reading:

| PS item | What we do, and why |
|---|---|
| Sampling frequency | Read from the header when there is one. For headerless files, ranked candidates, promoted only by a structural match. Nothing guarantees an absolute rate for a raw file, so we identify it honestly rather than invent one. |
| Pseudo-random interleavers | Matched against a catalogue of *standard* permutations; anything else is UNKNOWN with its measured period. Recovering an arbitrary permutation is an open research problem. |
| LDPC | Matched against a catalogue of standard codes (CCSDS, DVB-S2, Wi-Fi, 5G). No generic LDPC reconstruction. |
| "Training data containing both .IQ and .wav" | Our classifier is trained on our own generator. If the organisers supply labelled data, we evaluate and fine-tune on it (PLAN M4). |
| "GNU Radio, python, C++" | Python with Numba-compiled kernels. GNU Radio is GPL, so it's used only at development time. |

**Our additions, which the PS doesn't ask for:** offline operation, evidence levels, known-system verification, analyst profiles and receiver capture.

### How do analysts do this work today?

From the vendors' own material, and matching the PS's "carried out manually":

1. **Spot the signal** on a monitoring receiver's waterfall.
2. **Try automatic recognition** against a library of known modems. Krypto500 advertises automatic classification of "nearly 4000 FSK & PSK modems". If the signal is known, it's decoded straight away.
3. **If it's unknown, record it and analyse it by hand.** PROCITEC's go2DECODE lists the tools used: spectrogram and baud-rate measurement, autocorrelation, constellation, amplitude/frequency/phase displays, and a raster display for coding analysis. The analyst tunes a universal demodulator by hand.
4. **Analyse the bitstream by hand** (PROCITEC go2ANALYSE, Wavecom W-BitView): look for sync words and repetitions, and try descramblers, de-interleavers and codes.
5. **Write a new decoder** and add it to the library.

**Sanket automates steps 3 and 4.** That's the core of the pitch. Analyst profiles (§3) cover step 5 for signals we've already worked out.

---

## 2. Radio theory

### Why is modulation needed at all?

- **Antennas need high frequencies.** An antenna works well when it's around a quarter of a wavelength long. A 1 kHz wave is 300 km long; a 435 MHz wave is 69 cm. So data rides on a high-frequency *carrier*.
- **Sharing the air.** Each transmitter gets its own carrier frequency, its own channel. A receiver tunes to one and ignores the rest.
- **A plain carrier says nothing.** A steady tone carries zero information. You have to *change* something about it to send data, and that change is modulation.

Analogy: a torch is the carrier; switching it on and off in Morse is modulation.

### What are ASK, FSK, PSK, QAM and CW?

A wave has three things you can vary: **amplitude** (height), **frequency** (how fast it cycles) and **phase** (where in its cycle it is).

| Scheme | What varies | Example |
|---|---|---|
| **ASK** (amplitude-shift keying) | Amplitude | Loud = 1, quiet = 0. **OOK** (on-off keying) is the extreme case. |
| **FSK** (frequency-shift keying) | Frequency | High tone = 1, low tone = 0 |
| **PSK** (phase-shift keying) | Phase | BPSK: 2 phases, 1 bit per symbol. QPSK: 4 phases, 2 bits. 8PSK: 8 phases, 3 bits. |
| **QAM** (quadrature amplitude modulation) | Amplitude **and** phase | 16-QAM is a 4×4 grid, 4 bits per symbol; 64-QAM carries 6 bits. Used by Wi-Fi, 4G/5G and cable TV; it needs a clean signal. |
| **CW** (continuous wave) | Nothing | A pure, steady tone: pilot tones, beacons, test carriers. In amateur radio, "CW" also means Morse sent by keying that tone on and off, which is really OOK. |

Sanket doesn't *use* any of these; it never transmits. It *recognises* what someone else used.

### Why isn't ASK in scope?

- The PS names only FSK, QAM and PSK.
- Plain ASK is the weakest scheme against noise, fading and amplifier distortion, so serious links avoid it.
- QAM already contains amplitude levels.

ASK/OOK is still common in cheap devices (garage remotes, 433 MHz sensors, RFID) and in ADS-B, so it's on the **after-1.0** list.

### What is FM?

**Frequency modulation**, the analog cousin of FSK. The carrier's frequency follows the audio smoothly, rather than jumping between fixed tones. FM broadcast (88–108 MHz), walkie-talkies and aircraft ground links use it.

It matters to us because FM carrying voice can fool a digital classifier into saying "FSK". Sanket checks for analog signals before digital classification (PLAN M2).

### What are I and Q? Is Q the phase?

**No, Q isn't the phase.**
- **I** (in-phase) is the cosine part of the wave.
- **Q** (quadrature) is the sine part, the same wave shifted 90°.

Think of a point on a map: I is how far east, Q is how far north. From the two you get:
- **amplitude** = √(I² + Q²), the distance from the centre
- **phase** = atan2(Q, I), the compass bearing
- **frequency** = how fast the phase turns from one sample to the next

**Why record two numbers per sample?** With only one, you can't tell a signal above the tuned frequency from one below it, and the phase, where PSK and QAM carry their data, is lost.

**How it happens:** the receiver multiplies the incoming wave by a cosine and by a sine at the tuned frequency. That produces I and Q and **removes the carrier**. A signal at 435.040 MHz, with the receiver tuned to 435.000 MHz, appears in the file at +40 kHz.

### How is a signal "measured" at all, especially with many signals in the air?

The physical chain:
- **Transmitter:** a microphone turns sound into a varying voltage. The transmitter uses that voltage (or data bits) to modulate a carrier, and the antenna radiates it as a radio wave.
- **Receiver:** the wave induces a tiny voltage in the receiving antenna. The receiver amplifies and filters it, mixes it down to I and Q, and an analog-to-digital converter measures the voltage millions of times per second.

**A recording is a list of voltage measurements.** Everything else is maths on those numbers.

**Many signals at once.** The antenna receives the *sum* of every signal plus noise, so each sample is one mixed number. They're separated like this:
- **By frequency.** A Fourier transform (FFT) splits the mixture into frequency components, like a prism splitting white light. That's what the waterfall shows.
- **Channelisation.** To isolate one signal: shift it to 0 Hz, filter away everything else, and reduce the sample rate. Amplitude, phase and frequency are then computed on that signal alone.
- **By time.** Signals that take turns are separated by detecting when each is on.
- **Overlapping in time *and* frequency** (co-channel) is hard. Detecting that an overlap exists is a stretch goal; separating the signals isn't promised.

**Levels are relative.** Without the receiver's calibration we can say "14 dB above the noise", not "−87 dBm". That's why the waterfall is labelled *relative and uncalibrated*.

### What does "how the signal was built" mean?

Every digital transmitter runs an assembly line, usually a modem chip or radio software following a published standard:

```
message bytes
  → FRAMING      sync word at the start, header (counter, ID), CRC checksum at the end
  → FEC ENCODE   add redundancy so errors can be fixed (a rate-½ code doubles the bits)
  → INTERLEAVE   shuffle the bit order
  → MAP          bits → symbols (QPSK: 2 bits → one of 4 phases)
  → PULSE-SHAPE  smooth each symbol (RRC filter) to limit bandwidth
  → UPCONVERT    shift to the carrier frequency
  → amplifier → antenna
```

Each choice on that line is a **parameter**. Sanket receives only the finished wave, works out every choice, and runs the line backwards.

Note that QPSK, FSK and CW are **different transmitters**, not steps in one signal. The demo recording simply contains all three.

### Why interleave? Isn't it overcomplicating things?

**The PS requires it** (task iii). It's also unavoidable, because real transmitters do it:
- Radio errors come in **bursts**: a fade or a lightning crash wipes out 50 bits in a row.
- Error-correcting codes fix *scattered* errors, but fail on a long burst.
- Shuffling before sending, and un-shuffling after receiving, turns one burst into 50 scattered single errors, which the code fixes easily.

A scratched CD survives the same way. If a signal was interleaved and we skip de-interleaving, decoding fails and there are no bits at all.

### What exactly are the "parameters", and why do we need them?

They're the transmitter's settings:

| Parameter | Plain meaning |
|---|---|
| Sample rate | Samples per second in the file; needed to turn anything into real Hz |
| Centre offset / carrier frequency | Where the signal sits |
| Bandwidth | How wide a slice of spectrum it occupies |
| SNR | How far the signal sits above the noise |
| Symbol rate (baud) | Symbols per second |
| Roll-off (β) | How the pulses are shaped |
| CFO | How far off frequency the transmitter or receiver is |
| Modulation | QPSK, FSK, … |
| Interleaver | Type and size of the shuffle |
| FEC code | Which error-correcting code, at what rate |
| Sync word, frame length, CRC | How the message is packaged |

Two reasons they matter:
- **Each stage needs the ones before it.** You can't demodulate without the symbol rate, or decode without the code.
- **The parameters are an answer in themselves.** They fingerprint the system: "QPSK, 25 kBd, conv K=7, CCSDS sync word" says *satellite telemetry*.

### What do we get from knowing all this?

- **The content:** recovered bits, frames, headers and payloads.
- **Identification:** which system or emitter it is, or that it's something unusual.
- **Enforcement:** is it licensed, is it interference, is it a jammer?
- **Monitoring:** once the parameters are known, the signal can be decoded routinely. Sanket's analyst profiles do exactly this.
- **Triage:** analysts spend their time on the recordings that matter.

---

## 3. Recognising and decoding signals

### How do you tell QPSK from FSK from CW?

Each leaves distinctive fingerprints:

| Signal | Amplitude | Frequency | Phase | Spectral clue |
|---|---|---|---|---|
| CW | constant | constant | steady | one razor-thin line; no symbol-rate pattern |
| FSK | constant | jumps between 2/4/8 levels | follows the frequency | humps at the tone frequencies |
| PSK | roughly constant | constant | jumps between M angles | raise the signal to the power M and a sharp line appears (x² for BPSK, x⁴ for QPSK) |
| QAM | several levels | constant | jumps | the constellation is a grid |

Sanket combines three independent methods:
1. **Maths rules.** Statistical fingerprints called cumulants have known values; for QPSK, C40 ≈ −1 and C42 ≈ −1. These rules are explainable.
2. **A small neural network**, trained on generated examples (§6).
3. **Proof from further down the chain.** If demodulating as QPSK produces frames whose CRCs pass, it *was* QPSK, and the label is promoted to VERIFIED.

When methods 1 and 2 disagree, both rankings are shown and the label is a HYPOTHESIS.

### What are the evidence levels?

Every value Sanket reports carries one level, shown as glyph + label + colour, never colour alone:

| Level | Meaning | Example |
|---|---|---|
| **VERIFIED** | Proven by a hard check. Only three kinds of proof count: a CRC pass, a sync word recurring at the frame period, or a re-encode match. | "Conv K=7: 20/20 frames pass CRC" |
| **MEASURED** | From metadata, or entered by the analyst | Sample rate from a SigMF header |
| **ESTIMATED** | Computed from the samples, with an uncertainty | "25,000 Bd ± 0.05 %" |
| **HYPOTHESIS** | A ranked candidate that isn't confirmed | "2-FSK (0.64) or GFSK: classifiers disagree" |
| **UNKNOWN** | Can't be determined; says why and what would settle it | "No interleaver found; a longer capture would settle it" |

Two more rules:
- **Conventions are listed.** A value taken on a convention (e.g. a raw file's IQ order) is a HYPOTHESIS and appears in the `needsReview` list at the top of every result.
- **Guesses are counted.** Blind searches count every guess and raise the acceptance bar to match (Holm correction). Every detector is also rerun on shuffled bits, where nothing should ever be found.

### Can we train a model to find pseudo-random interleavers?

**Not to recover the pattern.** A pseudo-random interleaver over N bits could be any of N! orderings; for N = 1,024 that number has over 2,600 digits. A good interleaver's output looks statistically random, so there's nothing for a model to learn. It's a combinatorial problem, not a learning one.

What we can do:
- **Detect that interleaving exists and measure its period**, using rank tests.
- **Test the standard permutations** that real systems publish (3GPP turbo, LTE QPP, Wi-Fi, DVB-S2).
- **Report anything else as UNKNOWN**, with its measured period.

We never claim generic seed recovery.

### Can we get automatic modem classification like the commercial tools?

**Yes, for a small set of known public systems. This is the known-system verification in PLAN M6.**

After the blind chain, a **Match** stage compares the results with a catalogue:

| System | Specification |
|---|---|
| CCSDS telemetry coding (also used by Meteor-M LRPT) | CCSDS 131.0-B, 132.0-B |
| AIS | ITU-R M.1371 |
| NAVTEX | ITU-R M.540, M.476/M.625 |
| MF/HF DSC | ITU-R M.493 |
| POCSAG | ITU-R M.584 |

How a match is judged:
- It is VERIFIED only when that system's own check passes on this recording (CRC, sync recurrence, or agreement of its time-diversity or check bits).
- Every system checked is counted in the hypothesis ledger.
- Blind results are never overwritten.

AIS needs the GMSK demodulator, a stretch goal in M3, and moves after 1.0 if that slips.

**This isn't a protocol library.** Krypto500 classifies thousands of modems, built over decades. Our catalogue is small by design: independent proof that the blind analysis found a real system. More entries (MIL-STD-188-110, STANAG 4285, ACARS, ADS-B) are after-1.0 work.

### Can we write new decoders?

Two kinds:
- **Analyst profiles (PLAN M7).** When an analysis is accepted, the analyst saves the chain it found as a profile: sample format, channel, modulation, sync settings, interleaver, code, frame layout and named header fields. No samples are stored.
  - Applying it to a new recording, or a folder of them, skips the rediscovery but not the checks.
  - Profile values count as analyst-entered and are checked against the data.
  - The decode is VERIFIED only by the new recording's own proof. If the profile doesn't fit, Sanket says so and runs the blind chain.
  - Profiles are versioned and move between air-gapped stations as files.

  This is our equivalent of the decoder-description files in commercial tools, and it matches the PS's "the resultant data is then utilised for processing signals in the designated sensors".
- **Protocol payload decoders**, which turn payload bits into content such as a NAVTEX message. Each needs the protocol's public specification, so they come one at a time, after 1.0.

---

## 4. Inputs and outputs

### How do recordings get into Sanket? Can someone connect a machine?

**Every kind of input except a real-time stream.** Whatever the route, Sanket analyses a file on this machine.

| Route | How |
|---|---|
| Open a file | By path; nothing is copied, which matters for multi-GB files |
| Upload | Drag and drop. It goes to Sanket's own local server, not the internet. |
| Folder or sequence | A folder becomes a batch; a numbered sequence of files becomes one recording |
| Command line | `sanket analyse <paths…>` for scripts and batches |
| Connected receiver | Record a set duration from a USB SDR (RTL-SDR, HackRF, Airspy, USRP), or from a sound-card input carrying a receiver's audio or IQ output. It's saved as SigMF, then analysed. |

Capture needs the same legal authorisation as owning the receiver (Telecommunications Act 2023 §3). The UI says so.

**Not supported:**
- **Network-attached receivers such as KiwiSDR**, because they would break the no-network rule. Record with the receiver's own tool, then open the file.
- **Real-time analysis of a live stream.** The design (streaming, reproducible results, cheap re-runs after corrections) assumes a finished file.

All of this is planned (M1 formats, M7 routes and capture). Today the code reads SigMF and raw files.

### If files already have a file type, why do we have to "work out the format"?

**Because the extension doesn't describe the contents.**
- **`.iq` isn't a standard.** It's just bytes with no header. The same bytes could be 8-bit, 16-bit or 32-bit float; little- or big-endian; I-then-Q or Q-then-I; complex or real. That's 28 combinations, and read the wrong way, a perfect signal looks like noise.
- **Nothing in a raw file records the sample rate.**
- **A WAV** gives the sample rate and bit depth, but not whether its two channels are I/Q or ordinary stereo audio, or what the centre frequency was.
- **Metadata can be wrong.** A public dataset (ORACLE) declares 32-bit samples while its data is 64-bit.

Rival tools shipped bugs where an unknown sample rate silently defaulted to 1 Hz or 1 MHz. So Sanket's first rule is: work out the format, and never assume.

### What is a "sniffer"?

The **format sniffer** inspects a headerless file and ranks the likely ways to read it.
- It reads sample blocks from across the file in each of the 28 formats and asks how predictable the resulting numbers are.
- Read correctly, a real signal is smooth and each sample is predictable from the ones before. Read wrongly, it looks like random bytes.
- The best reading wins. It reports its margin over the runner-up, and says UNKNOWN if two formats tie.

**It's built, and it scored 0 wrong formats on an 864-file benchmark** ([bench/results/sniffer.md](../bench/results/sniffer.md)).

### What are SigMF files? Can other files be converted to SigMF?

**SigMF** (Signal Metadata Format) is an open standard that labels a recording with two files:
- `.sigmf-data` holds the raw samples.
- `.sigmf-meta` is a small JSON label: datatype, sample rate, centre frequency, time, hardware, and annotations ("QPSK here, 80–950 ms").

It fixes the "unlabelled raw file" problem. It doesn't replace `.iq` and `.wav`, which Sanket reads directly as the PS requires.

**Conversion:** once a non-SigMF file's format is confirmed, **Save as SigMF** (PLAN M7) writes a `.sigmf-meta` next to it. The samples stay untouched, and the next open reads the format as MEASURED instead of guessing it.

### Which file formats are supported?

All of these are planned for M1; SigMF and raw are already built.

- **SigMF:** the full datatype vocabulary, archives and multi-capture recordings.
- **Raw headerless files** in all 28 SigMF datatypes. Recorder extensions like `.cfile` or `.cu8` are only hints, never taken as fact.
- **WAV:** mono or stereo, integer or float, RF64/Wave64 over 4 GiB, and the `auxi` metadata chunk written by SDR#, HDSDR and SDRuno.
- **Compressed audio:** FLAC, MP3, Ogg. Lossy formats distort phase, so digital labels from them are capped at HYPOTHESIS.
- **Recorder containers:** SDRangel `.sdriq`, MIDAS Blue, VITA 49 packet recordings.
- **Other:** NumPy `.npy`, and `.gz`/`.zip` recordings.
- **Anything else:** read as raw bytes with a header offset, then sniffed.

### Can the analyst tell Sanket what they already know?

**Yes: analyst context (PLAN M7).** The analyst can enter:
- known parameters (sample rate, centre frequency, symbol rate, modulation, bandwidth)
- a suspected standard, which can name a known system or a saved profile
- capture details (receiver, location, time)

How Sanket uses it:
- Entered values are MEASURED ("entered by the analyst") but are **still checked against the data**. A conflict (entered 9,600 Bd, measured 4,800 Bd) shows as a warning.
- A suspected standard only reorders the searches; it never skips them, so a wrong hint can't hide the true answer.

### What is the final result? Do we get a decrypted file or audio?

**No decryption, ever.** It's out of scope; if the payload is encrypted, you get the encrypted bits. *We recover bits, not plaintext.*

**Audio isn't in 1.0.** Playable audio from analog AM/FM/SSB is on the after-1.0 list. Digital voice (DMR, P25) needs patented codecs and stays out.

**What you do get:**
1. **The on-screen analysis:** what each signal is, with the evidence.
2. **The recovered data:** a frame table with each frame's start, header and payload, exportable as bits, hex or JSON, plus soft bits for the analyst's own experiments.
3. **The known-system verdict**, e.g. "POCSAG 1200, VERIFIED".
4. **A PDF report** for people and case files.
5. **SigMF annotations**, so other tools show our findings.
6. **Profiles**, to reuse the analysis.
7. **`results.json`**, for machines rather than people: scripts, batches and databases. It's byte-identical across runs, so results are reproducible and auditable.

The PS's requirement ends at item 2: identifying header and payload.

### What about analog signals?

The PS's demodulation list is digital, but real HF/VHF recordings are full of AM, FM and SSB voice, and Morse. So:
- **Detected, labelled and measured (PLAN M2):** carrier, bandwidth, FM deviation, Morse speed. They're kept out of the digital chain.
- **Never given a digital label:** the classifier has an "analog" outcome (M4).
- **Playable audio** is after 1.0.

OFDM (Wi-Fi, LTE, DVB-T) is labelled unknown for now; estimating its parameters is after-1.0 work.

### When will we test on real-world recordings?

**In M8, as planned.** Sources come in this legal order:
1. public licensed datasets
2. public remote KiwiSDR receivers; Indian NAVTEX from the seven DGLL stations is the main Indian ground truth
3. our own captures, only under an institutional umbrella after checking with the organisers or WPC

Real recordings of catalogued systems (NAVTEX, AIS, POCSAG, Meteor-M LRPT) must be VERIFIED by Sanket and, where a reference decoder exists, agree with it frame by frame.

---

## 5. The screen

Before a file is opened, the workspace runs on a **synthetic demo recording** generated in the browser from a fixed seed, labelled *Synthetic demo* on screen:
- The waterfall, spectrum and constellation are really computed from that signal.
- The analysis results (evidence cards, hypotheses, frames) are **scripted placeholders** showing what the real engine will output.

Opening a real recording — including the synthetic ones in [DEMO.md](DEMO.md) — replaces all of this with the real engine's output: real detections, a real pipeline rail, and for VERIFIED signals, real frames whose payload matches the transmitted bytes.

### What's in the demo recording?

250,000 samples per second, about 1.05 s long, with three transmitters mixed over noise:
- **#1 QPSK** at +40 kHz, 25 kBd, on from 80 to 950 ms. The success story: decoded end to end, with CRCs passing.
- **#2 2-FSK** at −70 kHz, 4.8 kBd, tones ±6 kHz, three bursts. The honest partial answer: the modulation is a HYPOTHESIS, and the coding is UNKNOWN with reasons.
- **#3 CW** at +95 kHz for the whole recording. Correctly recognised as nothing to decode.

### What does each panel show?

- **Top bar:**
  - The logo: a waveform turning into four dots, signal in and symbols out.
  - The file name with a **SYNTHETIC DEMO** badge.
  - An **Offline build** pill.
  - The theme toggle.
- **Left column:**
  - **Detections** lists every signal found, with its overall evidence badge.
  - **Pipeline** lists the stages for the selected signal, each with its evidence glyph. Stages that don't apply are greyed out, e.g. "Not applicable — no bits".
- **Waterfall** (centre, required by the PS):
  - Across is frequency, shown as the distance from the capture centre because the centre frequency is unknown. Down is time. Colour is power.
  - The QPSK is a wide band, the FSK three blocks, and the CW a thin vertical line.
  - Boxes mark detections. You can change the colormap and contrast, and scroll, drag and double-click to navigate.
- **PSD strip:** the waterfall averaged over time. Signals are bumps above a flat noise floor.
- **Bottom tabs:**
  - **Hypotheses** is the guess ledger. For QPSK: 1,284 tried, Holm-corrected at α = 0.01, strictest threshold about 7.8 × 10⁻⁶, and 0 accepts on 10,000 shuffled-bit runs. Each candidate is listed with why it was accepted or rejected.
  - **Frames:** 21 frames with sync word `0x1ACFFC1D`. 20 pass their CRC; the last is truncated by the end of the burst and says so.
  - **Assumptions:** container, datatype, sample rate, duration, **centre frequency UNKNOWN**, **IQ order HYPOTHESIS**, clipping and DC offset.
- **Right column:**
  - The **constellation**: four tight clouds for QPSK. Their spread is the EVM, about 20 %, consistent with the measured SNR.
  - For FSK, an **instantaneous-frequency** view instead: the signal hopping between two tones.
  - Below that, **evidence cards**: every parameter with its value, level, confidence, method, evidence, alternatives, warnings, and for UNKNOWN, what would settle it.

### Why aren't the waterfall and constellation shown together?

**They are.** The waterfall is in the centre and the constellation at the top right, at the same time. Two things can make it look otherwise:
- Below 1,280 px wide, the panels stack and the constellation drops below the waterfall.
- The constellation shows **one signal at a time**, the one selected, because a constellation only makes sense for one isolated, synchronised signal. FSK shows instantaneous frequency instead, since an FSK constellation is a featureless ring. CW shows nothing, since it has no symbols.

### Why a constellation and a waterfall? Are there better views?

**Both are required by the PS, and both are industry standards,** because each answers a different question:
- **Waterfall:** what is on, where in frequency, and when? It's the only view that shows bursts, hopping and several transmitters at once.
- **Constellation:** what are the symbols, and how clean are they? A grid means QAM, four clouds mean QPSK, and a spinning ring means the carrier isn't locked.

They're complemented by:

| View | Status | What it shows |
|---|---|---|
| PSD | built | exact levels and widths |
| Instantaneous frequency | built | FSK tone changes |
| Eye diagram | planned (M3) | symbol timing quality |
| I/Q, amplitude, phase and frequency against time | after 1.0 | the standard analyst display, which go2DECODE also has |

### Can signals be split into amplitude, phase and frequency, and shown as sine waves?

**The split: yes.** All three come straight from I/Q, and they're on the after-1.0 list as time-domain views:

| Signal | Amplitude | Phase | Frequency |
|---|---|---|---|
| CW | flat | smooth | flat |
| FSK | flat | smooth | steps |
| PSK | flat | steps | spikes |
| QAM | steps | steps | spikes |

**Sine waves: only as a labelled illustration.** The recording holds no carrier, because the receiver removed it, and a 435 MHz wave can't be drawn cycle by cycle anyway. The after-1.0 **explain mode** redraws the signal on a slow toy carrier as sine and cosine, so phase flips, tone changes and amplitude steps are visible. It's always labelled *illustrative*.

---

## 6. Technology choices

### Are we using AI/ML?

**Yes, but deliberately narrowly** (PLAN M4; the `ml/` folder is still empty).
- **Modulation classification** uses a tiny 1-D neural network, about 10,000 parameters, so it's fast on a CPU.
  - It's trained on our own signal generator, where every answer is known exactly.
  - It's tested on independent public datasets.
  - It rejects signals it hasn't seen instead of forcing a label.
  - It runs through ONNX Runtime, offline.
- **Optional:** a model that decides the *order* of the error-correction catalogue search.
- **No LLM** runs anywhere in the product.

Everything else is classical signal processing and algebra, because **ML can't provide proof**. A network can say "93 % QPSK"; only a CRC pass can say "definitely". ML suggests; maths confirms.

### How can a web-based tool run offline?

"Web-based" means the *interface* runs in a browser, not that anything is online.
- `sanket` starts a server **on your own machine** (127.0.0.1), and the browser talks to it there.
- All code, fonts and icons are bundled.
- CI runs the app with every non-local request blocked and fails if anything tries to reach out.

Jupyter notebooks work the same way.

### Would a desktop app or a PWA suit us better?

**A PWA doesn't fit.** Its benefits are installing and working offline from the browser's cache, but our heavy lifting is Python (NumPy, Numba, ONNX) running as a local server, which a PWA can't run. Running it in the browser via WebAssembly would be slow and would lose Numba. A local server can also read a 4 GB file straight from disk, which a browser can't do well.

**We ship as a desktop window over the local server** (PLAN §1 and M8). The installed build opens Sanket in its own window through pywebview, using the same React UI and the same local server, so there's no second frontend.
- **Windows** uses Edge WebView2. Its fixed-version runtime is bundled, because air-gapped machines may not have it.
- **Linux** uses WebKit2GTK. The GPL Qt backend is avoided.
- **Fallback:** with no usable webview, Sanket opens the default browser instead, and `sanket --browser` does that on purpose.

It feels like a desktop app and keeps the offline guarantee: the window may only load 127.0.0.1. Electron would bundle a whole second browser runtime for no gain.

### Why not GNU Radio, which the PS mentions?

The PS says the problem *can* be addressed with GNU Radio, Python or C++; it doesn't require any of them. GNU Radio is GPL-licensed, and linking it would put GPL code into the product. We use it only at development time, for test signals and reference receivers. The product is Python with Numba-compiled kernels where speed matters.

---

## 7. The competition

### What is Krypto500? How is Sanket different from a US$7,400 product?

The US$7,400 figure is from our dossier and is **unverified**: no vendor publishes a price.

**Krypto500**, from the vendor's own brochure and site:
- **Maker:** COMINT Consulting (USA). Windows software; works with standard sound cards and "400+ receivers, SDRs, digitizers".
- **Scope:** narrowband signals up to 48 kHz wide. Its sibling Krypto1000 handles wideband.
- **Scale:** automatic classification of "nearly 4000 FSK & PSK modems" and hundreds of decoders.
- **Extra tools:** radio fingerprinting, traffic and network analysis, and outputs that support cryptanalysis.
- **Access:** ITAR-controlled; no demo, trial or light version.

**Similar tools:**
- **PROCITEC go2signals** (Germany): monitoring, automatic recognition including digital voice, manual analysis displays, a decoder-writing language, and forensic bitstream analysis.
- **Wavecom W-CODE** (Switzerland): 300+ modes including military ones, a classifier, a bitstream viewer.
- **Hoka Code300-32** (Netherlands).
- **Free tools:** SigDigger, Inspectrum, URH, GNU Radio.

**The difference:** commercial tools are a huge **library of known modems** plus **manual toolsets** for everything else. Sanket targets the manual part.

| | Commercial decoders | Sanket |
|---|---|---|
| Known, named protocols | Thousands, decoded end to end | A few, for verification. **They win, by far.** |
| Unknown signals | An expert drives tools by hand | Automated blind identification, with evidence |
| Transparency | Answers come from a closed product | Evidence, method and hypothesis count for every claim |
| Access | Export-controlled, quote-only | Open, Indian-built, free, auditable |
| Maturity | Decades | Pre-alpha |

**Pitch line:** *"Commercial decoders recognise what's already in their library. When a signal isn't, an analyst spends hours on it by hand. Sanket automates those hours, shows its evidence, and is ours."*

Their public material documents blind code and interleaver work only as manual tools. We have no evidence either way on whether they automate it, so we don't say they can't.

### What are other SIH26147 teams doing, and what are we missing?

As of 26 September we found 35 public repos, about 26 with real code. Details are in [STANDARDS §5](STANDARDS_TO_BEAT.md#5-sih26147-rival-repositories).

| Team | What stands out |
|---|---|
| **sigma** | Technical leader, desktop app. 18 modulations; blind identification of convolutional codes, RS and catalogued LDPC; real NAVTEX, RTTY, radiosonde and weather-satellite decodes. |
| **ICHNOVA** | Rigour leader. Sealed benchmark with 0 false accepts and corrected statistics. BPSK/QPSK only. |
| **Devansh-567** | Honesty labels, full SigMF support, exports |
| **Team Vertex** | CRC + sync + re-encode verification |
| **Pinpoint** | 2 GiB streaming, detection only |
| **RadioFry** | Most test files; publishes its false-positive rates |

**What we're missing, honestly:**
- **Working signal processing.** Rivals have pipelines that decode; we have ingest and the evidence model. This is the big gap.
- **Real-world recordings** analysed.
- **The eye diagram and burst separation** (both planned).

**Where we lead or plan to lead:**
- the web GUI with deep decoding
- honesty enforced in code
- the visible hypothesis ledger
- whole-chain multi-GB streaming
- a classifier benchmarked on public data
- analyst correction with automatic re-run
- known-system verification and profiles
- a CI-tested offline guarantee

---

## 8. Scope decisions

Decisions made while working through these questions. [PLAN](PLAN.md) holds the authoritative version.

| Decision | Where |
|---|---|
| Every input except real-time streams: files of every format we can name, path, upload, folder, sequence, CLI, and capture from local USB SDRs and sound cards | PLAN §1, M1, M7 |
| No capture from network-attached receivers; no real-time analysis | PLAN §1 (out of scope) |
| Analyst context: entered values checked against the data; hints only reorder searches | PLAN M7 |
| Save as SigMF for any non-SigMF recording | PLAN M7 |
| Known-system verification: CCSDS TM, AIS, NAVTEX, MF/HF DSC, POCSAG; VERIFIED only by each system's own check | PLAN M6 |
| Analyst profiles: save, apply, suggest, share; always re-checked | PLAN M7 |
| Analog signals detected and labelled, kept out of the digital chain | PLAN M2, M4 |
| Organiser training data used for evaluation and fine-tuning if supplied | PLAN M4 |
| After 1.0: playable audio, time-domain views, illustrative sine/cosine mode, ASK/OOK and ADS-B, OFDM parameters, payload text, more known systems | PLAN §1 |
| Real-world validation stays in M8; no rushing the milestones | PLAN M8 |
| Ship as a desktop window (pywebview) over the local server, with the browser as fallback | PLAN §1, M8 |

---

## 9. Questions judges are likely to ask

From [dossier §B7](SIHPS_ANALYSIS.md), with the answers as they now stand:

1. **"What if a file has no metadata?"** The sniffer ranks candidate formats, and the Assumptions tab shows what's UNKNOWN. Relative quantities are still estimated, and the analyst can enter what they know; it's checked, not trusted.
2. **"How do you know a decode is correct?"** A CRC pass, sync-word recurrence or a re-encode match, never a bare percentage. For known systems, that system's own check.
3. **"What's the accuracy at 0 dB SNR?"** Show the accuracy-vs-SNR curve once the classifier exists (M4). Labels are suppressed outside the validated range.
4. **"Can it handle two overlapping signals?"** Multi-signal detection with each signal isolated; the demo shows three. Overlap in both time and frequency is detected at best, not separated.
5. **"What if the interleaver is pseudo-random?"** State the limit: we match standard permutations, and otherwise report UNKNOWN with the measured period.
6. **"Does it run offline?"** Demo it with networking switched off; CI already enforces it.
7. **"Why not just use Krypto500?"** It's export-controlled and closed. Its strength is recognising known modems; unknown signals are still analysed by hand. Sanket automates that manual work, shows its evidence, and is Indian-owned.
8. **"Why not GNU Radio?"** Its GPL licence; we use it at development time only.
