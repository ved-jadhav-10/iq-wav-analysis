# Academic papers for the SIH26147 "Research and References" slide

Method: all bibliographic fields below were pulled from publisher-deposited Crossref records (api.crossref.org/works/{DOI}), cross-checked against Semantic Scholar / OpenAlex / arXiv / HAL / PMC where noted. Crossref records are the publisher's own metadata deposit, so they count as primary for title/authors/volume/issue/pages/DOI. Checked 29 Sep 2026.

## 1. O'Shea, Roy & Clancy — Over-the-Air Deep Learning Based Radio Signal Classification

### Takeaway
All details the user believed are CONFIRMED: IEEE JSTSP vol. 12, no. 1, pp. 168–179, Feb 2018, DOI 10.1109/JSTSP.2018.2797022.

### Cited Findings
- Authors (Crossref order): Timothy James O'Shea, Tamoghna Roy, T. Charles Clancy — [Crossref](https://api.crossref.org/works/10.1109/JSTSP.2018.2797022)
- Title: "Over-the-Air Deep Learning Based Radio Signal Classification" — [Crossref](https://api.crossref.org/works/10.1109/JSTSP.2018.2797022)
- Venue: IEEE Journal of Selected Topics in Signal Processing, vol. 12, issue 1, pp. 168–179, issued Feb 2018 — [Crossref](https://api.crossref.org/works/10.1109/JSTSP.2018.2797022)
- DOI: 10.1109/JSTSP.2018.2797022; arXiv preprint 1712.04578 — [Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/JSTSP.2018.2797022)
- Content: deep-learning modulation classification compared against a higher-order-moment + boosted-tree baseline, across carrier frequency offset, symbol rate and multipath fading in simulation, plus over-the-air tests with software radios — [Semantic Scholar abstract](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/JSTSP.2018.2797022)
- Citation count ~1,497 on Semantic Scholar (as of the lookup) — [Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/JSTSP.2018.2797022)

### Inferences
- Slide note: "Deep CNN/ResNet modulation classification of raw IQ, benchmarked against expert-feature (higher-order moment) classifiers, incl. over-the-air data; origin of the RadioML 2018 dataset." (The RadioML 2018 link is widely known but was not re-checked in this pass; drop it from the slide if unsure.)

### Gaps
- Semantic Scholar lists the year as 2017 (arXiv preprint date); cite 2018 (journal issue date per Crossref).

## 2. Marazin, Gautier & Burel — (a) k/n convolutional encoder recovery, (b) punctured convolutional encoders

### Takeaway
(a) EURASIP JWCN 2011, article 168, DOI 10.1186/1687-1499-2011-168. (b) IET Signal Processing vol. 6, no. 2, pp. 122–131, 2012, DOI 10.1049/iet-spr.2010.0343. Both CONFIRMED.

### Cited Findings
- (a) Title: "Blind recovery of k/n rate convolutional encoders in a noisy environment"; authors Mélanie Marazin, Roland Gautier, Gilles Burel; EURASIP Journal on Wireless Communications and Networking, vol. 2011, article no. 168 (published 14 Nov 2011); DOI 10.1186/1687-1499-2011-168 — [Crossref](https://api.crossref.org/works/10.1186/1687-1499-2011-168)
- (a) Content: an iterative algorithm, based on dual-code properties, that blindly recognises convolutional encoders in the general k/n rate case in a noisy context — [Semantic Scholar abstract](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1186/1687-1499-2011-168)
- (b) Title: "Algebraic method for blind recovery of punctured convolutional encoders from an erroneous bitstream"; authors M. Marazin, R. Gautier, G. Burel; IET Signal Processing, vol. 6, issue 2, pp. 122–131; Crossref issued date 10 Apr 2012; DOI 10.1049/iet-spr.2010.0343 — [Crossref](https://api.crossref.org/works/10.1049/iet-spr.2010.0343)
- (b) Content: an algebraic method that blindly identifies punctured convolutional encoders, i.e. the mother code and the puncturing pattern used to raise the code rate — [Semantic Scholar abstract](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1049/iet-spr.2010.0343)

### Inferences
- Slide note (a): "Blind identification of k/n convolutional encoders from noisy bitstreams via dual-code (parity-check) search."
- Slide note (b): "Extends blind encoder recovery to punctured convolutional codes: recovers the mother code and puncturing pattern."
- EURASIP JWCN uses article numbers, not page ranges; cite as "2011:168".

### Gaps
- None for the bibliographic fields.

## 3. Sicot, Houcke & Barbier — Blind detection of interleaver parameters

### Takeaway
CONFIRMED: Signal Processing (Elsevier) vol. 89, no. 4, pp. 450–462, April 2009, DOI 10.1016/j.sigpro.2008.09.012.

### Cited Findings
- Authors: Guillaume Sicot, Sébastien Houcke, Johann Barbier; title "Blind detection of interleaver parameters"; Signal Processing vol. 89, issue 4, pp. 450–462, issued April 2009; DOI 10.1016/j.sigpro.2008.09.012 — [Crossref](https://api.crossref.org/works/10.1016/j.sigpro.2008.09.012); matches [HAL record hal-02117763](https://api.archives-ouvertes.fr/search/?q=halId_s:hal-02117763&fl=title_s,authFullName_s,journalTitle_s,volume_s,issue_s,page_s,producedDateY_i,doiId_s)
- Content: blindly estimates the interleaver size, its starting position (frame synchronisation) and some information about the interleaver function at the output of a binary symmetric channel, with an improvement when soft information is available — [HAL abstract](https://api.archives-ouvertes.fr/search/?q=halId_s:hal-02117763&fl=abstract_s)
- Open-access copy on HAL: https://hal.science/hal-02117763/document — [OpenAlex](https://api.openalex.org/works/doi:10.1016/j.sigpro.2008.09.012)

### Inferences
- Slide note: "Foundational rank-deficiency method: blind estimation of interleaver period, frame sync and permutation structure from a hard- or soft-decision bitstream."

### Gaps
- Semantic Scholar conflates this journal paper with an earlier ICASSP 2005 conference paper of the same title (listed there as 2005, ICASSP venue). The ICASSP 2005 version's own details were not checked; cite the 2009 journal version.

## 4. Moosavi & Larsson — Fast Blind Recognition of Channel Codes

### Takeaway
CONFIRMED: IEEE Trans. Communications vol. 62, **issue 5**, pp. 1393–1405, May 2014, DOI **10.1109/TCOMM.2014.050614.130297**.

### Cited Findings
- Authors: Reza Moosavi, Erik G. Larsson; title "Fast Blind Recognition of Channel Codes"; IEEE Transactions on Communications, vol. 62, issue 5, pp. 1393–1405, May 2014; DOI 10.1109/TCOMM.2014.050614.130297 — [Crossref](https://api.crossref.org/works/10.1109/TCOMM.2014.050614.130297)
- Content: a fast algorithm that computes the syndrome posterior probability (the probability that all of a code's parity checks hold) directly from soft information without decoding, used in a statistical hypothesis test for "was code C used?" and in a sequential test that reduces blind-decoding complexity — [OpenAlex abstract](https://api.openalex.org/works/doi:10.1109/TCOMM.2014.050614.130297)
- Related earlier conference version: "A Fast Scheme for Blind Identification of Channel Codes", GLOBECOM 2011, DOI 10.1109/GLOCOM.2011.6133507 — [Crossref search](https://api.crossref.org/works/10.1109/GLOCOM.2011.6133507)

### Inferences
- Slide note: "Soft-decision syndrome posterior probability: fast hypothesis testing of candidate channel codes (e.g., LDPC, conv.) without decoding."

### Gaps
- None.

## 5. Wee, Choi & Jeong 2021 — Kolmogorov–Smirnov test for blind interleaver parameters (PMC8155855)

### Takeaway
CORRECTION: the paper is in **Sensors** (MDPI), not Entropy. Sensors 2021, 21(10), 3458, DOI 10.3390/s21103458, PMC8155855, PMID 34063544.

### Cited Findings
- PMC8155855 maps to DOI 10.3390/s21103458 and PMID 34063544 — [PMC ID converter](https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?ids=PMC8155855&format=json)
- Authors: Seungwoo Wee, Changryoul Choi, Jechang Jeong; title "Blind Interleaver Parameters Estimation Using Kolmogorov–Smirnov Test"; Sensors vol. 21, issue 10, article 3458, published 15 May 2021 — [Crossref](https://api.crossref.org/works/10.3390/s21103458)
- Content: exploits the difference between rank distributions of square matrices built from linear-code data and from random sequences; the K–S test value picks the most different rank distribution, and a multinomial distribution controls the false-alarm rate — [Semantic Scholar abstract](https://api.semanticscholar.org/graph/v1/paper/DOI:10.3390/s21103458)

### Inferences
- Slide note: "Replaces hard rank thresholds with a K–S test on rank distributions, with explicit false-alarm control, for blind interleaver-period estimation." (This fits Sanket's "multiple-testing corrected thresholds" rule.)

### Gaps
- A different 2020 Korean paper has an almost identical title ("Blind Interleaver Parameter Estimation Using Kolmogorov-Smirnov Test", Yoonji Kim, Geunbae Kim, Unseob Jung, Dongweon Yoon, J. KICS 45(3):584–592, DOI 10.7840/kics.2020.45.3.584) — [Crossref](https://api.crossref.org/works/10.7840/kics.2020.45.3.584). Don't mix up the two.

## 6. Boegner et al. — Large Scale Radio Frequency Signal Classification (arXiv:2207.09918)

### Takeaway
CONFIRMED: 8 authors, arXiv preprint posted 20 Jul 2022; it introduced the Sig53 dataset and the TorchSig toolkit. No journal reference is listed on arXiv.

### Cited Findings
- Authors (arXiv order): Luke Boegner, Manbir Gulati, Garrett Vanhoy, Phillip Vallance, Bradley Comar, Silvija Kokalj-Filipovic, Craig Lennon, Robert D. Miller — [arXiv API](https://export.arxiv.org/api/query?id_list=2207.09918)
- Title "Large Scale Radio Frequency Signal Classification"; first version 2022-07-20; DOI 10.48550/arXiv.2207.09918 — [arXiv API](https://export.arxiv.org/api/query?id_list=2207.09918); [Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/arXiv:2207.09918)
- Contributions: Sig53 dataset of 5 million synthetically generated samples across 53 signal classes with chosen impairments; TorchSig open-source signals-ML toolkit that generates it; experiments show Transformers outperform ConvNets without extra regularisation or a ConvNet teacher; domain-specific augmentations help training — [arXiv abstract](https://export.arxiv.org/abs/2207.09918)

### Inferences
- Slide note: "Introduced TorchSig (open-source RF-ML toolkit) and Sig53 (5M samples, 53 classes); a modern large-scale modulation-classification benchmark."

### Gaps
- No peer-reviewed venue confirmed; cite as arXiv preprint.

## 7. ONE strong paper on blind Reed–Solomon parameter identification

### Takeaway
Recommended: Swaminathan, Madhukumar, Wang & Kee, "Blind Reconstruction of Reed-Solomon Encoder and Interleavers Over Noisy Environment", IEEE Trans. Broadcasting 64(4):830–845, Dec 2018, DOI 10.1109/TBC.2018.2795461. It is a well-cited journal paper and also covers the RS + block-interleaver chain. For a paper that is specifically about the Galois-field Fourier transform, the alternative is Liu, Pan & Lei, IEEE Access 2019.

### Cited Findings
- Primary pick: R. Swaminathan, A. S. Madhukumar, Guohua Wang, Ting Shang Kee; "Blind Reconstruction of Reed-Solomon Encoder and Interleavers Over Noisy Environment"; IEEE Transactions on Broadcasting vol. 64, issue 4, pp. 830–845, Dec 2018; DOI 10.1109/TBC.2018.2795461 — [Crossref](https://api.crossref.org/works/10.1109/TBC.2018.2795461)
- Content: blind estimation of RS code parameters, plus block-interleaver parameters from RS-coded and interleaved streams, with synchronisation compensation, in both error-free and noisy cases; reported to outperform prior algorithms in noise — [OpenAlex abstract](https://api.openalex.org/works/doi:10.1109/TBC.2018.2795461); ~41 citations on OpenAlex, 34 on Semantic Scholar; open-access copy at NTU DR-NTU: https://dr.ntu.edu.sg/bitstream/10356/144731/2/Blind%20reconstruction%20of%20Reed-Solomon%20encoder%20and%20interleavers%20over%20noisy%20environment.pdf
- GFFT alternative: Pengtao Liu, Zhipeng Pan, Jing Lei; "Parameter Identification of Reed-Solomon Codes Based on Probability Statistics and Galois Field Fourier Transform"; IEEE Access vol. 7, pp. 33619–33630, 2019; DOI 10.1109/ACCESS.2019.2904718 — [Crossref](https://api.crossref.org/works/10.1109/ACCESS.2019.2904718)
  - Content: a probability-statistics threshold skips wrong candidate parameters and the GFFT (spectral zeros) cuts the misidentification probability; derives an upper bound on the correct-recognition rate as a function of codeword length, BER and bits per symbol — [Semantic Scholar abstract](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/ACCESS.2019.2904718)
- GF(q) rank alternative from the Brest (Marazin/Gautier) group: Yasamine Zrelli, Roland Gautier, Eric Rannou, Mélanie Marazin, Emanuel Radoi; "Blind identification of code word length for non-binary error-correcting codes in noisy transmission"; EURASIP JWCN 2015, article 43; DOI 10.1186/s13638-015-0294-5 — [Crossref](https://api.crossref.org/works/10.1186/s13638-015-0294-5); method: Gauss–Jordan elimination in GF(2^m) that uses the mean number of zeros per column — [Semantic Scholar abstract](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1186/s13638-015-0294-5)
- A newer GFFT paper also exists: Shi, Zhang, Chang, Wang, Liu, "Blind Recognition of Reed-Solomon Codes Based on Galois Field Fourier Transform and Reliability Verification", IEEE Commun. Letters 27(8):2137–2141, 2023, DOI 10.1109/LCOMM.2023.3285607 — [Crossref](https://api.crossref.org/works/10.1109/LCOMM.2023.3285607)

### Inferences
- Slide note (Swaminathan 2018): "Blind recovery of RS (n, k) and block-interleaver parameters from noisy, unsynchronised RS-coded streams."
- Slide note (Liu 2019, if a GFFT citation is wanted): "RS (n, k) identification via Galois-field Fourier transform spectral zeros with a statistical threshold and a proven accuracy bound."

### Gaps
- I did not find a single canonical, highly cited "RS via GFFT" journal paper that predates 2016; the GFFT line in the literature is mostly Chinese conference and journal papers (e.g., Zhang et al., CyberC 2016, DOI 10.1109/CyberC.2016.89).

## 8. ONE strong paper on blind convolutional (Forney) / helical interleaver identification

### Takeaway
Recommended journal paper: Xu, Zhong & Huang, "An Improved Blind Recognition Method of the Convolutional Interleaver Parameters in a Noisy Channel", IEEE Access 7:101775–101784, 2019, DOI 10.1109/ACCESS.2019.2930663. For helical interleavers specifically: Jeong, Yoon, Lee & Choi, ICICS 2011, DOI 10.1109/ICICS.2011.6174276.

### Cited Findings
- Primary: Yiyao Xu, Yang Zhong, Zhiping Huang; IEEE Access vol. 7, pp. 101775–101784, 2019; DOI 10.1109/ACCESS.2019.2930663 — [Crossref](https://api.crossref.org/works/10.1109/ACCESS.2019.2930663)
  - Content: analyses how bit errors affect Gauss–Jordan elimination through pivoting (GJTEP), shows that errors on the principal diagonal of the data matrix dominate, and proposes a denoising variant that markedly improves convolutional-interleaver recognition at high BER — [OpenAlex abstract](https://api.openalex.org/works/doi:10.1109/ACCESS.2019.2930663); open access (IEEE Access)
- Foundational convolutional-interleaver paper: Liru Lu, Kwok Hung Li, Yong Liang Guan; "Blind identification of convolutional interleaver parameters"; 2009 7th Int. Conf. on Information, Communications and Signal Processing (ICICS), pp. 1–5, Dec 2009; DOI 10.1109/ICICS.2009.5397564 — [Crossref](https://api.crossref.org/works/10.1109/ICICS.2009.5397564); blindly determines the interleaver period, depth and number of stages per shift register, then de-interleaves — [OpenAlex abstract](https://api.openalex.org/works/doi:10.1109/ICICS.2009.5397564)
- Helical: Jeonghoon Jeong, Dongweon Yoon, Jubyung Lee, Sunghwan Choi; "Blind reconstruction of a helical scan interleaver"; 2011 8th ICICS, pp. 1–4, Dec 2011; DOI 10.1109/ICICS.2011.6174276 — [Crossref](https://api.crossref.org/works/10.1109/ICICS.2011.6174276); uses Gaussian elimination on channel-code linearity to estimate the helical-scan period, the deinterleaver matrix dimensions and the codeword length — [OpenAlex abstract](https://api.openalex.org/works/doi:10.1109/ICICS.2011.6174276)
- Journal alternative (Science China): Lu Gan, Dan Li, ZongHui Liu, LiPing Li; "A low complexity algorithm of blind estimation of convolutional interleaver parameters"; Science China Information Sciences 56(4), 2013 issue (online 28 Sep 2012); DOI 10.1007/s11432-012-4673-9 — [Crossref](https://api.crossref.org/works/10.1007/s11432-012-4673-9)
- Broader, highly cited (~70–79 citations): R. Swaminathan, A. S. Madhukumar; "Classification of Error Correcting Codes and Estimation of Interleaver Parameters in a Noisy Transmission Environment"; IEEE Trans. Broadcasting 63(3):463–478, Sep 2017; DOI 10.1109/TBC.2017.2704436 — [Crossref](https://api.crossref.org/works/10.1109/TBC.2017.2704436); jointly classifies block-coded, convolutionally coded and uncoded data and estimates interleaver parameters, with analytical and histogram thresholds — [OpenAlex abstract](https://api.openalex.org/works/doi:10.1109/TBC.2017.2704436)

### Inferences
- Slide note (Xu 2019): "Noise-robust blind recognition of convolutional (Forney) interleaver parameters via denoised Gauss–Jordan elimination."
- Slide note (Jeong 2011): "Blind reconstruction of helical-scan (diagonal) interleavers: period, matrix size and codeword length."
- The Xu 2019 abstract says "convolutional interleaver" but does not use the word "Forney"; label it "convolutional (Forney-type)" on the slide only if comfortable with that equivalence.

### Gaps
- Crossref gives Science China 56(4) with page "1-9"; the exact article/page numbering was not checked further. The issued date in Crossref is 2012-09-28 (online), and the issue is 2013 — cite with care or skip.
- Whether Swaminathan & Madhukumar 2017 handles convolutional *interleavers* (as opposed to convolutional *codes*) was not confirmed from the abstract.

## 9. (Optional) Cluzeau, Finiasz & Tillich 2010 — turbo-code permutation recovery

### Takeaway
CONFIRMED: "Methods for the reconstruction of parallel turbo codes", IEEE ISIT 2010, pp. 2008–2012, DOI 10.1109/ISIT.2010.5513365; arXiv:1006.0259.

### Cited Findings
- Authors: Mathieu Cluzeau, Matthieu Finiasz, Jean-Pierre Tillich; "Methods for the reconstruction of parallel turbo codes"; 2010 IEEE International Symposium on Information Theory (ISIT), pp. 2008–2012, June 2010; DOI 10.1109/ISIT.2010.5513365 — [Crossref](https://api.crossref.org/works/10.1109/ISIT.2010.5513365)
- arXiv:1006.0259 (posted 1 Jun 2010), title capitalised "Methods for the Reconstruction of Parallel Turbo Codes"; two algorithms that reconstruct turbo codes from a noisy intercepted bitstream, described as the first able to recover the whole turbo-code permutation at high noise levels — [arXiv API](https://export.arxiv.org/api/query?id_list=1006.0259)
- Related: Cluzeau & Finiasz, "Reconstruction of punctured convolutional codes", IEEE ITW 2009, pp. 75–79, DOI 10.1109/ITW.2009.5351168 — [Crossref](https://api.crossref.org/works/10.1109/ITW.2009.5351168)

### Inferences
- Slide note: "First algorithms to recover a full turbo-code interleaver permutation from a noisy intercepted bitstream." This is a known-code-structure method, not generic pseudo-random seed recovery, so it fits Sanket's rule of never claiming generic PRNG recovery.

### Gaps
- None.

## Suggested compact slide list (all confirmed above)

1. T. J. O'Shea, T. Roy, T. C. Clancy, "Over-the-Air Deep Learning Based Radio Signal Classification," IEEE JSTSP, 12(1):168–179, 2018. doi:10.1109/JSTSP.2018.2797022
2. L. Boegner, M. Gulati, G. Vanhoy, P. Vallance, B. Comar, S. Kokalj-Filipovic, C. Lennon, R. D. Miller, "Large Scale Radio Frequency Signal Classification," arXiv:2207.09918, 2022.
3. M. Marazin, R. Gautier, G. Burel, "Blind recovery of k/n rate convolutional encoders in a noisy environment," EURASIP JWCN, 2011:168. doi:10.1186/1687-1499-2011-168
4. M. Marazin, R. Gautier, G. Burel, "Algebraic method for blind recovery of punctured convolutional encoders from an erroneous bitstream," IET Signal Processing, 6(2):122–131, 2012. doi:10.1049/iet-spr.2010.0343
5. R. Moosavi, E. G. Larsson, "Fast Blind Recognition of Channel Codes," IEEE Trans. Commun., 62(5):1393–1405, 2014. doi:10.1109/TCOMM.2014.050614.130297
6. G. Sicot, S. Houcke, J. Barbier, "Blind detection of interleaver parameters," Signal Processing, 89(4):450–462, 2009. doi:10.1016/j.sigpro.2008.09.012
7. S. Wee, C. Choi, J. Jeong, "Blind Interleaver Parameters Estimation Using Kolmogorov–Smirnov Test," Sensors, 21(10):3458, 2021. doi:10.3390/s21103458
8. Y. Xu, Y. Zhong, Z. Huang, "An Improved Blind Recognition Method of the Convolutional Interleaver Parameters in a Noisy Channel," IEEE Access, 7:101775–101784, 2019. doi:10.1109/ACCESS.2019.2930663
9. R. Swaminathan, A. S. Madhukumar, G. Wang, T. S. Kee, "Blind Reconstruction of Reed-Solomon Encoder and Interleavers Over Noisy Environment," IEEE Trans. Broadcasting, 64(4):830–845, 2018. doi:10.1109/TBC.2018.2795461
10. M. Cluzeau, M. Finiasz, J.-P. Tillich, "Methods for the reconstruction of parallel turbo codes," Proc. IEEE ISIT 2010, pp. 2008–2012. doi:10.1109/ISIT.2010.5513365
