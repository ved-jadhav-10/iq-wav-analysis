# Blind Channel-Code Identification and Blind Interleaver Parameter Estimation (SOTA 2022–2026 + classics)

Scope note: research covered ~25 search/fetch operations. Many IEEE/Elsevier/Wiley full texts were paywalled (403) so several numbers come from abstracts or open-access (PMC/arXiv) versions. Where only an abstract was reachable, that is stated. Items labelled "Inference" are the researcher's engineering judgement, not sourced facts.

## Q1. Best algebraic methods (rank deficiency, GJETP, dual-code / parity-check search, Euclidean, LLR/soft) and the channel BER each tolerates

### Takeaway
The workhorse for all linear codes (block, convolutional, punctured convolutional, and interleaved streams) is the same primitive: fill a matrix with the intercepted bitstream at a candidate width, run Gaussian / Gauss-Jordan elimination over GF(2) (GJETP), and look for rank deficiency or for dual-code (parity-check) vectors. Hard-decision rank methods break down at roughly BER 1e-3 to 1e-2 for long codes. Soft-decision variants (reliability-sorted GJETP, syndrome posterior probability from LLRs) and iterated / "rank-iteration" or correlation-attack variants push the usable region to noisier channels. There is no single universal BER limit; it depends on codeword length n (the probability that a row of n bits is error-free is (1-p)^n).

### Cited Findings
- GJETP-based dual-code method (Marazin, Gautier & Burel, 2009–2011) "completely solved the blind parameter recognition of k/n convolutional codes with low complexity"; it proceeds in three steps: (1) identify code length n, (2) identify a dual-code basis, (3) identify the generator matrix — [Su et al. 2014, Blind Identification of Convolutional Encoder Parameters (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4055125/)
- Su et al. (2014) add a soft-decision GJETP ("Soft-GJETP"): rows of the received matrix are reordered by each row's lowest reliability value so the most reliable rows are pivoted first; they also formalise n-estimation as "the most probable gap between two consecutive nonzero cardinals" and add codeword-synchronisation recognition, which earlier GJETP methods overlooked — [PMC4055125](https://pmc.ncbi.nlm.nih.gov/articles/PMC4055125/)
- For very low SNR, Su et al. propose a correlation-attack alternative that tests candidate parity-check vectors against the data with a threshold δ built from L/2 [1-(1-2τ)^w] plus λ times a standard-deviation term, with λ set experimentally to 6–8 and τ the BSC crossover probability (the formula was partly garbled in the extracted text; check the original before implementing). Baseline tests used an observation matrix of L = 200 rows; the false-recognition ratio drops significantly as L increases in soft-decision mode — [PMC4055125](https://pmc.ncbi.nlm.nih.gov/articles/PMC4055125/)
- Marazin, Gautier & Burel also published a two-stage algebraic method for punctured convolutional codes: reconstruct an equivalent (unpunctured-rate) encoder, then identify the mother code and puncturing pattern — [search summary citing "Algebraic method for blind recovery of punctured convolutional encoders from an erroneous bitstream"](https://www.researchgate.net/publication/260648020_Algebraic_method_for_blind_recovery_of_punctured_convolutional_encoders_from_an_erroneous_bitstream); a 2021 follow-up, "Blind reconstruction of punctured convolutional codes" (Physical Communication, 2021) — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1874490721000343)
- A 2023 IEEE Communications Letters paper, "A Rank-Iteration Based Blind Identification Method for Convolutional Codes", repeats GJETP several times so that the measured rank of a rank-deficient matrix under noise approaches its noiseless rank — [ResearchGate](https://www.researchgate.net/publication/369308477_A_Rank-iteration_Based_Blind_Identification_Method_for_Convolutional_Codes)
- Moosavi & Larsson ("Fast blind recognition of channel codes", IEEE Trans. Commun. 62:1393–1405, 2014) compute the syndrome posterior probability (SPP): the probability that all parity checks of a candidate code are satisfied, computed blindly from soft information (LLRs) without first decoding — [search summary / arXiv 2606.17705 related-work](https://arxiv.org/html/2606.17705); [DiVA full text (unreachable during this session)](https://www.diva-portal.org/smash/get/diva2:678868/FULLTEXT01.pdf)
- 2026 theory: Vedantam & Ganti, "Characterization of Blind Code Rate Recovery in Linear Block Codes", derive closed-form expressions for a rank-based code-rate recovery quality metric, an improved code-rate estimate for high noise, and optimal algorithmic parameters, validated on LDPC codes — [arXiv 2603.02031](https://arxiv.org/abs/2603.02031)
- 2026 theory: Singh, Krishnan & Yardi, "Blind Identification of Channel Codes: A Subspace-Coding Approach", propose a "minimum denoised subspace discrepancy decoder" for random linear codes over a BSC with guarantees for bounded-weight errors; they note most existing methods rely on special code structure and are "often computationally expensive" — [arXiv 2601.15903](https://arxiv.org/abs/2601.15903)
- Partial Gaussian elimination for identifying an unknown code (Designs, Codes and Cryptography, 2019) — [Springer](https://link.springer.com/article/10.1007/s10623-018-00593-7)
- Caution: a Jan-2025 arXiv paper proposing an LRT (BCJR-based likelihood) + DNN detector for convolutional codes was **withdrawn** by its authors because "the Markovian nature assumption of noise affected convolutional code outputs is incorrect" — [arXiv 2501.11487](https://arxiv.org/abs/2501.11487)

### Inferences
- Implementation core for the team (one Numba kernel reused everywhere): bit-packed GF(2) Gaussian elimination on a uint64 matrix (rows = L windows, cols = candidate width), returning rank and the transformation/kernel. Everything else (n search, sync search, interleaver period, puncturing, dual-code vectors) is a loop around it. This is very feasible in 8 weeks.
- Practical recipe for convolutional codes: for candidate widths l = 1..l_max build matrix of L×l, compute rank deficiency d(l)=l-rank; the gaps between widths with nonzero deficiency give n; slope gives k/n; kernel vectors are dual-code (parity-check) polynomials from which the generator is derived (Marazin). Punctured codes appear as a higher-rate code with period n·P; then search mother codes (e.g., K=7 (171,133)) × puncturing patterns in a small catalogue.
- Hard-decision limit rule of thumb: the method needs many rows with no error in a window of width l; since P(error-free) = (1-p)^l, for l≈100 and p=1e-2 only ~37% of rows are clean. That is why the literature shifts to soft/reliability ordering and iterated/correlation methods at BER ≳ 1e-2. Treat any numeric BER limit as code-dependent and measure it on the team's own simulator.
- The SPP / LLR approach is the best fit for "candidate catalogue" testing (known standards: DVB-S2 LDPC, 802.11 LDPC, CCSDS conv): per candidate, compute Σ over checks of log-prob(check satisfied) using the tanh rule; choose max. O(#checks × row weight × #frames) — cheap with Numba.

### Gaps
- Could not access full Moosavi–Larsson text (server refused connection), so the exact SPP formula and SNR thresholds are not quoted from source here.
- No reliable single table of "max tolerable BER" per algebraic method was found; the Euclidean-algorithm method (e.g., Wang/Huang style for rate-1/n conv codes) was not reached in this session.

## Q2. Deep-learning approaches for blind code/interleaver recognition, comparison with algebraic methods, public datasets/code

### Takeaway
DL classifiers (CNN, multiscale dilated CNN, ConvLSTM+attention, dual-branch CNN with handcrafted features) reach ~90–98% accuracy over closed candidate sets, and 2026 work classifies seven code families from hard bits with >85% accuracy even at BER 0.1. But they only choose among trained classes, do not recover parameters/generators outside the training set, and essentially none publish code or datasets. For a SIGINT tool, DL is a useful front-end "family classifier"; algebraic methods are needed for actual parameter recovery.

### Cited Findings
- Dehdashtian, Hashemi & Salehkaleybar (IEEE Wireless Commun. Letters, 2021; arXiv 2020): DL recognition of code parameters over candidate sets (LDPC, convolutional, turbo, polar) under AWGN and multipath, needs no CSI/SNR knowledge, reported to outperform related works; no code/dataset mentioned — [arXiv 2009.07774](https://arxiv.org/abs/2009.07774)
- Ma et al. 2026 (Scientific Reports), DBFCNN: branch 1 multiscale dilated conv (kernels 3/5/7, dilation 1/2/4), branch 2 handcrafted algebraic features (run length, entropy, autocorrelation, coding depth, block, linear, spectral features); classes Hamming, BCH, LDPC, RS, conv, turbo, polar; input 5000 hard bits; dataset 1.12 M samples (160k per class) over 20 BER levels 1e-5…1e-1; 98% average accuracy at BER<1e-3, 93.95% overall, >85% at BER 0.1; beats MSDCNN by 5.05% at BER 1e-3; data "available from the corresponding author on reasonable request" (no public repo); article CC-BY-4.0 — [PMC12881466](https://pmc.ncbi.nlm.nih.gov/articles/PMC12881466/)
- Xu et al. 2025 (ConvLSTM-TFN): soft-decision BPSK input, 256-bit samples, 17 convolutional code classes (rate 1/2 K=3–9, rate 1/3 K=2–6, rate 1/4 K=2–6), >90% on all classes and 98.7% average over 0–20 dB; data generated with MATLAB (1.785 M train / 1.428 M test, random start positions, −20…20 dB); outperforms TextCNN, 1-D CNN, DRN, CCR-Net; no code release stated — [PMC11858941](https://pmc.ncbi.nlm.nih.gov/articles/PMC11858941/)
- Multiscale dilated CNN (MSDCNN) for channel-code recognition (Physical Communication, 2024) reported higher average accuracy and lower complexity than other networks — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1874490724000831)
- Other DL papers: "Blind identification of convolutional codes based on deep learning" (Digital Signal Processing, 2021) — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1051200421001251); "Blind Channel Codes Recognition via Deep Learning" (IEEE, 2021) — [IEEE Xplore](https://ieeexplore.ieee.org/document/9467330/); Pan Deng 2025 CNN for conv code recognition — [Wiley](https://onlinelibrary.wiley.com/doi/10.1155/int/3183819); HMT-Net multi-task conv code recognition — [PMC12845578](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12845578/)
- 2024 interleaver DL work exists (ML-based blind interleaver parameter estimation, Aug 2024; DL blind interleaver identification, Aug 2024; DL interleaver classification over Rayleigh fading, Nov 2024) — [search summary only](https://www.researchgate.net/publication/347761936_Blind_Interleaver_Parameter_Estimation_From_Scant_Data) (titles surfaced by search engine; full papers not verified)
- Searches for GitHub implementations of blind channel-code recognition found none relevant (hits were blind *channel* identification / modulation recognition repos) — e.g. [LiuRuiQi/Blind-Channel-Identification](https://github.com/LiuRuiQi/Blind-Channel-Identification), [mn9891/blind-digital-demodulation](https://github.com/mn9891/blind-digital-demodulation)

### Inferences
- The datasets in these papers are all synthetic (random info bits → encoder → BPSK/AWGN → hard/soft bits), so the team can regenerate an equivalent dataset themselves with CPU encoders (e.g., `galois`, CommPy, own Numba encoders). A small 1-D CNN on CPU (PyTorch or even ONNX runtime) is trainable in hours.
- DBFCNN's handcrafted branch (entropy, run-length, autocorrelation, rank-based "linear features") is itself a strong non-DL baseline: a gradient-boosted tree on those features is cheaper and more explainable for a hackathon demo.
- No paper found directly compares DL vs GJETP on the same data with the same metric; DL accuracy claims are closed-set and should not be read as parameter-recovery capability.

### Gaps
- No public dataset or code for any DL code-recognition paper was found.
- Full text of the 2024 DL interleaver papers not retrieved.

## Q3. Blind identification of RS parameters (n, k, field polynomial, first root, symbol alignment) and LDPC parity-check matrices

### Takeaway
RS: two families — (a) binary-image rank methods (treat the RS code as a binary linear code of length n·m; rank deficiency reveals n·m and alignment; RREF over GF(2) or column Gaussian elimination over GF(2^m)), and (b) Galois-Field Fourier Transform (GFFT) methods that test each candidate primitive polynomial and look for consecutive spectral zeros (roots of the generator polynomial), which give n−k and the first root. LDPC: either score a catalogue of known H matrices with soft syndrome statistics (easy, robust) or reconstruct sparse parity checks via low-weight-codeword search (Cluzeau–Finiasz, Sicot–Houcke–Barbier, Tixier–Tillich; 2021–2023 fast variants) — hard, degrades at low SNR for long codes.

### Cited Findings
- RS without errors: coded length, primitive polynomial and generator polynomial obtained from the reduced row echelon form (RREF); with errors, obtained via RREF + fault-tolerant matrix decomposition (FTMD) + GFFT — [search summary of Parameter Identification of RS Codes Based on Probability Statistics and GFFT](https://www.researchgate.net/publication/331721453_Parameter_Identification_of_Reed-Solomon_Codes_Based_on_Probability_Statistics_and_Galois_Field_Fourier_Transform)
- Shi, Zhang et al. (IEEE, 2023) "Blind Recognition of RS Codes Based on GFFT and Reliability Verification": low-complexity GFFT (LC-GFFT) computes shortened spectra to cut complexity and improve codeword utilisation; >95% correct recognition at appropriate SNR and ≥7 dB SNR gain over existing algorithms (per abstract) — [IEEE Xplore 10149421](https://ieeexplore.ieee.org/document/10149421); [ResearchGate](https://www.researchgate.net/publication/371539412_Blind_Recognition_of_Reed-Solomon_Codes_Based_on_Galois_Field_Fourier_Transform_and_Reliability_Verification)
- Earlier GFFT method with an optimum decision threshold under a minimum-error-probability rule (IEEE conf., 2016) — [IEEE Xplore 7864274](https://ieeexplore.ieee.org/document/7864274/); GF column Gaussian elimination method — [ResearchGate](https://www.researchgate.net/publication/283812844_Blind_recognition_of_RS_codes_based_on_Galois_field_columns_Gaussian_elimination); BCH analogue via GFFT — [IEEE 7341243](https://ieeexplore.ieee.org/document/7341243/)
- Han et al. 2022, "A fast method for blindly identifying Reed-Solomon codes based on matrix analysis" (IET Communications) — [Wiley](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/cmu2.12493)
- "Blind Reconstruction of Reed-Solomon Encoder and Interleavers Over Noisy Environment" (joint RS + interleaver) — [ResearchGate](https://www.researchgate.net/publication/322244161_Blind_Reconstruction_of_Reed-Solomon_Encoder_and_Interleavers_Over_Noisy_Environment)
- LDPC: Ding et al. 2023 (IET Communications) study blind recognition of sparse LDPC parity-check matrices in noise, using an existing low-weight-codeword search to sparsify linearly independent parity checks; classic methods are Cluzeau–Finiasz and Sicot–Houcke–Barbier; approaches degrade at lower SNR because of long block lengths — [IET 2023 (abstract via search; full text 403)](https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/cmu2.12552)
- Fast LDPC H reconstruction in noise with bidirectional Gaussian column elimination (BGCE) to cut iterations (Computer Communications, 2021) — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0140366421002152)
- Tixier & Tillich exploit algebraic structure (e.g., quasi-cyclic) to improve LDPC reconstruction over noisy channels (ISIT 2019) — [ACM DL](https://dl.acm.org/doi/10.1109/ISIT.2019.8849756); iterative-decoding-based sparse H reconstruction (J. Beihang Univ., 2020) — [BUAA](https://bhxb.buaa.edu.cn/bhzk/en/article/doi/10.13700/j.bh.1001-5965.2020.0500); "Parity Check Matrix Recognition from Noisy Codewords" — [arXiv 1205.4641](https://arxiv.org/pdf/1205.4641)
- Cluzeau improved codeword detection for LDPC reconstruction by adapting the Canteaut–Chabaud low-weight-codeword algorithm with error correction during reconstruction — [search summary of Barbier et al. turbo overview](https://eprint.iacr.org/2009/068.pdf)
- Code length and synchronisation from a noisy bitstream (Sicot/Houcke/Barbier line of work) — [ResearchGate](https://www.researchgate.net/publication/224578725_Recovering_a_Code's_Length_and_Synchronization_from_a_Noisy_Intercepted_Bitstream)

### Inferences
- RS pipeline for the team: (1) binary rank scan over widths to find n·m and bit alignment (RS(255,223) over GF(2^8) → period 2040 bits with deficiency 32·8=256); (2) for each of the 16 primitive polynomials of degree 8 (fewer for smaller m) and symbol alignment (m offsets), map bits→symbols, compute GFFT (evaluate codeword polynomial at α^j) over many codewords, and find the run of indices j where spectra are ~always zero; run length = n−k, start = first consecutive root (b, e.g. 0 or 1 as in CCSDS b=112 with dual basis — CCSDS dual-basis representation is an extra hypothesis to include). `galois` provides GF arithmetic and RS encode/decode, so this is ~1–2 weeks of work.
- Shortened RS (e.g. RS(204,188) DVB) must be handled by treating the codeword as a length-n' polynomial of the full-length code; GFFT zero test still works since zeros are properties of the generator.
- LDPC: implement catalogue scoring (DVB-S2/T2, 802.11n/ac, 5G NR base graphs, CCSDS AR4JA) via soft syndrome check first — it is robust and cheap. Full sparse-H reconstruction for n≥1000 at realistic BER is research-grade; flag as stretch goal.
- Concatenated RS+conv (CCSDS/DVB-S): decode order is inner first — identify the conv code (Q1), Viterbi-decode (hard or soft), then run the RS pipeline on the decoded stream, usually after a convolutional (Forney) de-interleaver (Q4). Viterbi output errors are bursty, which the byte interleaver disperses.

### Gaps
- Exact BER limits for GFFT RS recognition were only available as relative "≥7 dB gain" and ">95%" from the abstract.
- No source reached in this session gives an explicit symbol-alignment algorithm; the inference above is the researcher's construction.

## Q4. Interleaver period, depth, synchronisation; convolutional (Forney), helical, and pseudo-random interleaver recovery

### Takeaway
Block-interleaver period and sync are found with the same rank-deficiency scan: normalised rank drops when the analysis width is a multiple of the interleaver period, and the drop is maximal at the right sync. Statistical refinements (Bernoulli/KLD/multinomial, Kolmogorov–Smirnov on rank distributions, Hamming-weight distributions, "scant data" methods) improve detection at higher BER. Convolutional (Forney) and helical interleavers have dedicated low-complexity GJETP-based estimators. Fully pseudo-random interleavers require permutation reconstruction (Cluzeau–Finiasz–Tillich for turbo codes, Tixier 2015 for interleaved conv codes) — feasible but advanced; a seed search is only viable if the generator family (e.g., LFSR, 3GPP QPP) is known.

### Cited Findings
- Rank criterion (Sicot, Houcke & Barbier, "Blind detection of interleaver parameters", Signal Processing 2009 / ICASSP 2005): normalised rank of the matrix whose columns are analysis blocks decreases when block size is a multiple of the interleaver period; maximal decrease when blocks are synchronised with interleaver blocks, and the decrease is linked to the code rate — [ACM DL](https://dl.acm.org/doi/10.1016/j.sigpro.2008.09.012); [IEEE 1415838](https://ieeexplore.ieee.org/document/1415838/) (summarised via search)
- Wee, Choi & Jeong 2021 (Entropy/PMC): use the Kolmogorov–Smirnov test comparing the empirical CDF of ranks of square matrices built from received data with the rank distribution of random sequences (no logarithms needed, unlike KLD); baselines Sicot et al., Burel & Gautier, and Yoon's group (Bernoulli trials, KLD, multinomial); multinomial probabilities give the probability that an observed rank distribution arises from random data, enabling thresholding; tested with Hamming(7,4) and BCH codes, superior detection probability vs BER, KLD-comparable complexity, much faster than max-difference selection — [PMC8155855](https://pmc.ncbi.nlm.nih.gov/articles/PMC8155855/)
- "Blind Interleaver Parameter Estimation From Scant Data" (IEEE Access 2020, Hanyang Univ.) — [IEEE Xplore 9274324](https://ieeexplore.ieee.org/document/9274324/) (full text not parseable in this session)
- Hamming-weight-distribution based interleaver estimation (Digital Signal Processing, 2021) — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1051200421002293); "Enhanced Blind Interleaver Parameters Estimation Algorithm for Noisy Environment" (IEEE Access 2017) — [IEEE 8047234](https://ieeexplore.ieee.org/document/8047234/)
- Convolutional interleaver: low-complexity blind estimation (Science China Inf. Sci., 2013) constructs the de-interleaver, converts the initial position of intercepted data to the interleaving delay deviation, and uses GJETP over GF plus linear-block-code properties — [Springer](https://link.springer.com/article/10.1007/s11432-012-4673-9)
- Helical interleavers: "Blind reconstruction of a helical scan interleaver" (IEEE, 2012) estimates interleaver period, rows/columns of the deinterleaver matrix, and codeword length — [IEEE 6174276](https://ieeexplore.ieee.org/document/6174276/); Huang, Chen et al. "Blind identification of helical interleaving of the first type" (2015) uses parity-check vector bases to locate codewords within interleaved blocks at the output of a BSC — [IEEE 7410351](https://ieeexplore.ieee.org/document/7410351/); rank criteria + GJETP for interleaver parameters at high BER (HPLPB 2015) — [HPLPB](https://www.hplpb.com.cn/en/article/doi/10.11884/HPLPB201527.103250)
- Pseudo-random: Cluzeau, Finiasz & Tillich (2010) give "the first algorithms able to recover the whole permutation of a turbo code in the presence of high noise levels", demonstrated on realistic sizes — [arXiv 1006.0259](https://arxiv.org/abs/1006.0259); overview of turbo-code reconstruction techniques (Barbier et al.) — [IACR ePrint 2009/068](https://eprint.iacr.org/2009/068.pdf)
- Tixier (2015) reconstructs an unknown block interleaver (no structural assumption) plus the convolutional code from several noisy interleaved codewords, effective "even with moderate noise" — [arXiv 1501.03715](https://arxiv.org/abs/1501.03715)
- Joint turbo parameter estimation in noisy, non-synchronised scenarios with a bit-position adjustment parameter (DSP 2019) — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1051200419301228)

### Inferences
- Block interleaver (rows R × cols C): scan width w; rank deficiency appears at w = multiples of R·C (period); then within the de-interleaved period, re-run the code-length scan to get n (and hence R or C). Sync = offset maximising deficiency. All reuse the Q1 GF(2) rank kernel; cost O(#widths × #offsets × L·w²/64) — fine with Numba up to periods of a few thousand bits.
- Convolutional (Forney, I branches, depth/increment J — e.g., DVB I=12, J=17 bytes): brute-force (I, J, commutator phase) over a small grid, de-interleave, and test the result for RS rank deficiency or GFFT zeros; the grid is small for standard systems.
- Pseudo-random interleavers: recommend (a) a catalogue of standard generators (3GPP turbo, LTE QPP f1/f2 table, 802.11 bit interleaver, DVB-S2 bit interleaver column-twist) tested by "de-interleave then check code structure", and (b) treat generic permutation reconstruction (Tillich/Tixier) as out-of-scope for 8 weeks.

### Gaps
- No 2022–2026 paper retrieved on generic pseudo-random interleaver seed search; LFSR-seed search is only an inference.
- Quantitative BER limits for convolutional/helical estimators not available from abstracts.

## Q5. Open-source implementations (with licences)

### Takeaway
No open-source repository implementing blind code or interleaver recognition was found. Building blocks exist: `galois` (NumPy/Numba-backed finite fields with BCH/RS) is the key dependency; everything blind must be written by the team.

### Cited Findings
- `galois` (mhostetter): NumPy extension for GF(p^m) arithmetic including BCH and ReedSolomon classes over GF(2^m) — [GitHub](https://github.com/mhostetter/galois); [docs](https://mhostetter.github.io/galois/latest/api/galois.ReedSolomon/); [PyPI](https://pypi.org/project/galois/)
- `unireedsolomon`: pure-Python universal errors-and-erasures RS codec — [GitHub](https://github.com/lrq3000/unireedsolomon)
- TurboAE (turbo autoencoder, interleaver options) is a DL code-design repo, not recognition — [GitHub](https://github.com/yihanjiang/turboae)
- DL recognition papers did not release code; DBFCNN data only "on reasonable request" — [PMC12881466](https://pmc.ncbi.nlm.nih.gov/articles/PMC12881466/); ConvLSTM-TFN no code statement — [PMC11858941](https://pmc.ncbi.nlm.nih.gov/articles/PMC11858941/)

### Inferences
- Licences were not verified in this session; from background knowledge `galois` is MIT-licensed and uses Numba JIT internally, CommPy (BSD-3) and AFF3CT (MIT, C++) provide encoders/decoders — the team should confirm LICENSE files before bundling.
- AFF3CT/Sionna-style libraries are useful for generating test vectors but Sionna is TensorFlow/GPU-oriented; for a CPU-only tool prefer `galois` + own Numba encoders/Viterbi.

### Gaps
- Could not find any GitHub implementation of GJETP, dual-code conv identification, GFFT RS recognition, or interleaver rank scans.

## Q6. Hypothesis testing / false-alarm control when many code/interleaver hypotheses are tested

### Takeaway
The literature mostly uses per-test thresholds derived from a null model of random (uncoded) data — Gaussian approximation of binomial counts of satisfied checks with a k-sigma margin (λ ≈ 6–8), multinomial/KLD/KS tests on rank distributions, and minimum-error-probability thresholds for GFFT zeros. Explicit multiple-comparison correction (Bonferroni/FDR) is rarely stated; the large-sigma thresholds act as an implicit Bonferroni correction.

### Cited Findings
- Correlation-attack threshold with λ = 6–8 standard deviations above the null mean for accepting a parity-check vector — [PMC4055125](https://pmc.ncbi.nlm.nih.gov/articles/PMC4055125/)
- Multinomial probability that an observed rank distribution arises from random data used as a threshold; KS test vs random-sequence rank distribution — [PMC8155855](https://pmc.ncbi.nlm.nih.gov/articles/PMC8155855/)
- GFFT RS recognition with an optimum threshold under the minimum-error-probability rule — [IEEE 7864274](https://ieeexplore.ieee.org/document/7864274/)
- Polar-code blind recognition analysed as hypothesis testing: soft metric equals a shifted LLR; under equal priors and costs a reference threshold ln 2 arises, unequal priors/costs shift it — [arXiv 2606.17705](https://arxiv.org/html/2606.17705)
- Vedantam & Ganti 2026 give closed-form expressions for rank-based rate-recovery quality vs parameters — [arXiv 2603.02031](https://arxiv.org/abs/2603.02031)

### Inferences
- Useful null model for rank tests: for a random binary L×w matrix (L ≥ w), P(rank deficiency ≥ 1) ≈ 2^{−(L−w+1)}, so demanding L ≥ w + 20..30 makes a random-data false rank drop negligible even over 10^4 hypotheses. For parity-check scoring, under H0 each check is satisfied with prob 1/2; under H1 with prob (1+(1−2p)^w)/2; use a binomial tail p-value and apply Bonferroni (α/N_hypotheses) or Benjamini–Hochberg across the whole candidate catalogue, then report the winning hypothesis with a margin to the runner-up.
- Report calibrated confidence in the UI: run the same pipeline on shuffled/random bits to empirically estimate the false-alarm rate per detector (cheap sanity check the team can demo).

### Gaps
- No source found that explicitly applies Bonferroni or FDR control in blind code recognition; the correction strategy above is inference.
