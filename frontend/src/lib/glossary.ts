import { LEVEL_INFO } from './evidence'

export interface GlossaryEntry {
  term: string
  /** One or two plain sentences. Never firmer than what the tool can prove. */
  short: string
  long?: string
}

/** Plain-language definitions for the terms the panels use. Keys are stable ids, not labels:
 * `glossaryKeyFor` maps a label the engine emits ("Es/N0", "Frame check") to one. */
export const GLOSSARY: Record<string, GlossaryEntry> = {
  esn0: {
    term: 'Es/N0',
    short: 'Signal energy per symbol relative to noise power in one hertz, in dB. Higher means cleaner symbols.',
    long: 'It is estimated from the samples, so it carries an uncertainty and says nothing on its own about whether the data can be decoded.',
  },
  snr: {
    term: 'SNR',
    short: 'How far the signal stands above the noise around it, in dB. Here it is a detector statistic, not a calibrated power measurement.',
  },
  evm: {
    term: 'EVM',
    short: 'Error vector magnitude: how far the received symbols land from their ideal constellation points, as a percentage of the symbol size. Lower is cleaner.',
  },
  symbolRate: {
    term: 'Symbol rate',
    short: 'How many symbols the transmitter sends each second, in baud (Bd). Each symbol carries one or more bits.',
    long: 'It is estimated from a spectral line in the signal. Without a known sample rate it can only be given per sample.',
  },
  crc: {
    term: 'CRC (frame check)',
    short: 'A short checksum at the end of a frame. If it matches, the frame was received and decoded without errors.',
    long: 'A match by chance is very unlikely for a long checksum, which is why a CRC pass is one of the three proofs that make a result Verified.',
  },
  asm: {
    term: 'Sync word',
    short: 'A fixed bit pattern at the start of every frame, also called an attached sync marker (ASM). Seeing it recur at a steady spacing shows where frames begin.',
  },
  fec: {
    term: 'Error-correcting code (FEC)',
    short: 'Extra bits the transmitter adds so the receiver can repair bit errors. Finding which code was used is needed before the data can be read.',
  },
  conv: {
    term: 'Convolutional code',
    short: 'An error-correcting code where each output bit depends on the last few input bits. "K=7 r½" means a memory of 7 bits and two output bits per input bit.',
  },
  viterbi: {
    term: 'Viterbi decoder',
    short: 'The standard method for decoding a convolutional code: it finds the most likely transmitted bit sequence given the received, noisy one.',
  },
  interleaver: {
    term: 'Interleaver',
    short: 'A fixed shuffling of bits before transmission, so that a burst of errors is spread out and the error-correcting code can repair it. It must be undone first.',
  },
  rs: {
    term: 'Reed-Solomon (RS)',
    short: 'An error-correcting code that works on whole bytes and can repair a fixed number of wrong bytes in each block. Often used as an outer code.',
  },
  ldpc: {
    term: 'LDPC code',
    short: 'A modern error-correcting code decoded by iterative message passing. Sanket tries the catalogued LDPC codes; a code outside the catalogue is not found.',
  },
  ledger: {
    term: 'Hypothesis ledger',
    short: 'The list of every guess the blind search tried (modulation, code, interleaver, sync word, CRC), including those never run, with the chance each could have scored this well by luck.',
  },
  pvalue: {
    term: 'p-value',
    short: 'The chance of a result at least this good if the data had no structure at all. A smaller p-value is stronger evidence, once compared with the corrected threshold.',
  },
  threshold: {
    term: 'Threshold',
    short: 'The p-value a hypothesis must beat to be accepted. It is made stricter in proportion to how many hypotheses were tried.',
  },
  fwer: {
    term: 'Family-wise error (α)',
    short: 'The chance that the search accepts at least one false hypothesis. Holm step-down correction keeps it at α however many hypotheses were tried.',
  },
  shuffled: {
    term: 'Shuffled-bit check',
    short: 'The best chains are re-run on the same bits in random order. A chain that still "succeeds" on shuffled bits was a false alarm and is rejected.',
  },
  iqOrder: {
    term: 'I/Q order',
    short: 'Whether the file stores the in-phase sample before the quadrature one or the other way round. Swapping them mirrors the spectrum and flips the signal.',
  },
  constellation: {
    term: 'Constellation',
    short: 'The received symbols plotted as points on a plane (in-phase against quadrature). Tight clusters at the ideal points mean a clean signal.',
  },
  eye: {
    term: 'Eye diagram',
    short: 'The in-phase and quadrature traces overlaid over one symbol each side of the symbol instant. A wide-open eye means clean timing and low noise.',
  },
  timingSync: {
    term: 'Sync (timing and carrier)',
    short: 'Locks onto the symbol clock and the carrier frequency and phase, so one sample per symbol can be read. Not to be confused with the frame sync word.',
  },
  framing: {
    term: 'Frame',
    short: 'Finds where each frame starts (by its sync word) and checks it with its CRC, so that headers and payloads can be read out.',
  },
  knownSystem: {
    term: 'Known-system match',
    short: 'Checks the recording against catalogued systems such as POCSAG or AIS. A match counts only when that system’s own check passes on this recording.',
  },
  rolloff: {
    term: 'Roll-off',
    short: 'How sharply the transmitted pulse is band-limited. A larger roll-off uses more bandwidth for the same symbol rate.',
  },
  phaseAmbiguity: {
    term: 'Phase ambiguity',
    short: 'Carrier recovery cannot tell which of a few rotations of the constellation is the true one. The search tries each; a CRC pass decides.',
  },
  verified: {
    term: LEVEL_INFO.VERIFIED.label,
    short: LEVEL_INFO.VERIFIED.meaning,
    long: 'This is the only level that counts as proof.',
  },
  measured: { term: LEVEL_INFO.MEASURED.label, short: LEVEL_INFO.MEASURED.meaning },
  estimated: { term: LEVEL_INFO.ESTIMATED.label, short: LEVEL_INFO.ESTIMATED.meaning },
  hypothesis: { term: LEVEL_INFO.HYPOTHESIS.label, short: LEVEL_INFO.HYPOTHESIS.meaning },
  unknown: { term: LEVEL_INFO.UNKNOWN.label, short: LEVEL_INFO.UNKNOWN.meaning },
}

/** Label patterns, tried in order against the trimmed lower-case label. */
const RULES: [RegExp, string][] = [
  [/^es\s*\/\s*n0\b/, 'esn0'],
  [/^snr\b/, 'snr'],
  [/^evm\b/, 'evm'],
  [/^symbol[\s-]*rate\b/, 'symbolRate'],
  [/^(crc\b|frame check\b)/, 'crc'],
  [/^(sync[\s-]*word\b|asm\b|attached sync)/, 'asm'],
  [/^sync(hronisation|hronization)?$/, 'timingSync'],
  [/\bconvolutional\b|^conv\b/, 'conv'],
  [/\bviterbi\b/, 'viterbi'],
  [/^(de)?interleav/, 'interleaver'],
  [/^rs\b|reed[\s-]*solomon|^outer code\b/, 'rs'],
  [/\bldpc\b/, 'ldpc'],
  [/^(fec$|code$|error[\s-]correct)/, 'fec'],
  [/^(frame|framing)$/, 'framing'],
  [/^(match|known system)$/, 'knownSystem'],
  [/ledger|^hypotheses|^tried$/, 'ledger'],
  [/^p(-?\s?value)?$/, 'pvalue'],
  [/^(strictest\s+)?threshold$/, 'threshold'],
  [/family[\s-]*wise|^alpha$|^α|holm/, 'fwer'],
  [/shuffled/, 'shuffled'],
  [/^i\s*\/?\s*q\s+order\b/, 'iqOrder'],
  [/^constellation$/, 'constellation'],
  [/^eye(\s+diagram)?$/, 'eye'],
  [/^roll[\s-]*off\b/, 'rolloff'],
  [/^phase ambiguity\b/, 'phaseAmbiguity'],
  [/^verified$/, 'verified'],
  [/^measured$/, 'measured'],
  [/^estimated$/, 'estimated'],
  [/^hypothesis$/, 'hypothesis'],
  [/^unknown$/, 'unknown'],
]

/** The glossary key for a parameter, stage or column label ("Es/N0", "Frame check", "RS", ...), or
 * null when nothing matches. Case-insensitive; a null never invents a definition. */
export function glossaryKeyFor(label: string): string | null {
  const text = label.trim().toLowerCase()
  if (!text) return null
  for (const [re, key] of RULES) if (re.test(text)) return key
  return null
}
