/**
 * The downloads of a finished analysis and what each one is for. `sigmf` is the server's own
 * statement of what SigMF output the recording supports (`RecordingInfo.sigmf`): the annotated
 * metadata only exists for a raw file or a SigMF recording, and Save as SigMF only for a raw file.
 */
import type { RecordingInfo } from './api'

export type ResultFormat = 'json' | 'csv' | 'txt' | 'pdf' | 'run' | 'sigmf'

export interface ResultLink {
  format: ResultFormat
  label: string
  hint: string
}

const COMMON: readonly ResultLink[] = [
  {
    format: 'json',
    label: 'JSON',
    hint: 'The results document: every value with its evidence level, the ledger and the frames (the file sanket analyse writes)',
  },
  { format: 'csv', label: 'CSV', hint: 'One row per reported value, with its level, proof and convention' },
  { format: 'txt', label: 'Summary', hint: 'A plain-language summary: what was proved, what was only estimated, what is unknown' },
  { format: 'pdf', label: 'PDF', hint: 'A report that opens with the plain-language summary, then every value, the ledger and the frames, tied to the recording by its SHA-256' },
  {
    format: 'run',
    label: 'Run record',
    hint: 'How the run went: time per phase, peak memory and machine class, tied to the results by their SHA-256',
  },
]

const SIGMF_LINK: ResultLink = {
  format: 'sigmf',
  label: 'SigMF',
  hint: "The recording's SigMF metadata with Sanket's findings added as annotations (a SigMF file's own metadata is kept as it is). Downloads a file; nothing is written next to the recording",
}

export const SAVE_SIGMF_HINT =
  'Write a small .sigmf-meta file next to the original raw file, describing it and the findings as annotations. The samples are never touched or copied, and an existing metadata file is never overwritten'

/** The download links for a recording, the SigMF one only where the server can describe it. */
export function resultLinks(sigmf: RecordingInfo['sigmf']): ResultLink[] {
  return sigmf === 'none' ? [...COMMON] : [...COMMON, SIGMF_LINK]
}

/** Whether a Save as SigMF control belongs: only for a raw file. */
export function canSaveSigmf(sigmf: RecordingInfo['sigmf']): boolean {
  return sigmf === 'save'
}

/** How long a Save as SigMF message stays before it clears itself (it can also be dismissed). */
export const SAVE_MESSAGE_MS = 12_000
