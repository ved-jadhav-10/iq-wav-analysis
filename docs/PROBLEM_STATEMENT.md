# Problem Statement

## Problem Statement ID
**26147**

## Problem Statement Title
**Automated model for analysis of .IQ and .wav files along with signal parameter extraction**

---

## Description

### • Background

The raw data for analysis of signal collected off the air typically range from few Khz to Ghz bands. The analysis is being carried out manually to identify the signal parameters and the resultant data is then utilised for processing signals in the designated sensors. This data is often insufficient for fine grain analysis for parameter extraction such as modulation type, sampling rate, FEC, interleaving, etc. This creates a need for advanced data processing to extract the observation data.

### • Description

The terrestrial signals received from various sources includes data in HF, VHF and UHF bands. The raw data collected in the form of .wav or .IQ format to retain the characteristics of wave form. The analysis of signals is primarily dependent on the basic characteristics of data points selected during recording of these signals. Since the data point are recorded from different sensors and different locations, the parameters may vary. Therefore, the data available for analysis is often insufficient to clearly identify fine details such as sampling rate, modulation type, interleaving, FEC etc. This limitation reduces the accuracy and confidence of interpretation and data analysis that require detailed information. The data saved as .IQ and .wav have different parameters and therefore they store the raw information in different format. These files have to be processed in different ways for signal analysis to extract signal parameters. The problem can be addressed using advanced models such as GNU Radio, python, C++ to enhance the parameter extraction capability and more information rich inputs. The spectral relationship from training data containing both .IQ and .wav formats can be utilised for identifying signal parameters and carry out deeper analysis. The expected solution should be able to demodulate signals.

The GUI based model will have features to take .IQ or .wav file as input data and perform following tasks.

1. Identify signal parameters (Sampling frequency, Modulation, FEC, Interleaving). Additional features if feasible may be included.

2. Demodulate signals (FSK, QAM PSK)

3. Carry out de-interleaving (Block, Convolution, Diagonal, Pseudo Random).

4. FEC (short-constrained convolution codes with Viterbi decoding, RS block codes, Concatenated codes, LDPC).

5. Bit stream correlation.

### • Expected Solution

The expected system should improve feature visibility of signals with the help of GUI, enable automated signal analysis to identify spectral features such as sampling frequency, constellation plot, water fall (time-frequency domain), demodulate signals, carry out de-interleaving and error correction. The output can then be used to carry out correlation of bit stream for identification of header and payload.

---

## Organization
**National Technical Research Organisation (NTRO)**

## Department
**National Technical Research Organisation (NTRO)**

## Category
**Software**

## Theme
**Space Technology**

---

## Requirements, as Sanket reads them

Everything else in the docs cites these IDs instead of re-summarising the PS. "Milestone" is the [PLAN](PLAN.md#5-milestones) milestone that delivers the item.

| ID | PS wording | How we read it | Milestone |
|---|---|---|---|
| R1 | Identify signal parameters (sampling frequency, modulation, FEC, interleaving) | Every value is a `Parameter` with an evidence level. **Sampling frequency:** from the header when there is one (SigMF, WAV, `.sdriq`, Blue, VITA 49); for a headerless file, ranked candidates (file name, device rates), promoted to HYPOTHESIS only by a structural match; otherwise normalised units and an analyst prompt. No method recovers an absolute rate from samples alone, so none is claimed. | M1, M2, M4, M5 |
| R2 | Demodulate FSK, QAM, PSK | BPSK/QPSK/8PSK, 16/64-QAM, 2/4/8-FSK to soft bits. Analog AM/FM/SSB/CW is detected and labelled, never forced into a digital label. | M3 |
| R3 | De-interleave block, convolution, diagonal, pseudo-random | Block, convolutional (Forney) and diagonal (helical) found blind. Pseudo-random: the period is measured, then matched against a catalogue of **standard** permutations (802.11, LTE, DVB-S2); anything else is UNKNOWN with its period. Recovering an arbitrary permutation is an open research problem. | M5 |
| R4 | FEC: short-constraint convolutional + Viterbi, RS, concatenated, LDPC | Convolutional codes identified blind (K, generators, puncturing); RS parameters identified; concatenated chains inner code first; LDPC matched against a catalogue of standard codes (no generic LDPC reconstruction). | M5 |
| R5 | Bit-stream correlation to identify header and payload | Known and blind sync-word discovery with a significance test, frame length, constant and counter header fields, CRC checks; a frame table split into header and payload. | M6 |
| G1–G3 | GUI showing sampling frequency, constellation plot, waterfall | Local web GUI (desktop window in the build): waterfall, PSD, constellation, eye diagram, evidence per value, the hypothesis ledger and frames. | M0, M2, M3, M7 |
| — | "Training data containing both .IQ and .wav" | The classifier is trained on our own generator (`dsp.synth`), where every label is exact. Organiser data, if supplied, is used to evaluate and fine-tune, never as the sealed test set. | M4 |
| — | "GNU Radio, python, C++" | Python with Numba kernels. GNU Radio is GPL, so it is used only at development time. | — |

Beyond the PS: offline operation, evidence levels, known-system verification, analyst profiles and receiver capture ([PLAN §1](PLAN.md#1-what-10-is)).

## SIH 2026 facts

Checked 30 Sep 2026 against the [SIH 2026 Guidelines](https://sih.gov.in/letters/2026/SIH%202026%20Guidelines.pdf) and the [idea template](https://sih.gov.in/letters/2026/SIH2026-IDEA-Presentation-Format.pptx).

- **Idea submission:** closed 30 Sep 2026, with no extension. Each PS accepts at most 500 ideas, and a team may enter at most 2 PSs. The template allows at most 6 slides, submitted as PDF: title, proposed solution, technical approach, feasibility and viability, impact and benefits, research and references.
- **Evaluation criteria** (Guidelines p.13): novelty, complexity, clarity and detail in the prescribed format, feasibility, practicability, sustainability, scale of impact, user experience, future potential.
- **Shortlist:** 4–5 teams per PS, posted on the portal and emailed. No date is published.
- **Grand finale:** "proposed to be organized in December 2026", offline at nodal centres. Exact dates are not published.
- **Organiser data:** none published for SIH26147 as of 30 Sep, and no clarifications.