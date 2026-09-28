export const EVIDENCE_LEVELS = ['VERIFIED', 'MEASURED', 'ESTIMATED', 'HYPOTHESIS', 'UNKNOWN'] as const
export type EvidenceLevel = (typeof EVIDENCE_LEVELS)[number]

export const LEVEL_INFO: Record<EvidenceLevel, { label: string; meaning: string }> = {
  VERIFIED: { label: 'Verified', meaning: 'Proven by a hard check: CRC, sync-word recurrence or re-encode match.' },
  MEASURED: { label: 'Measured', meaning: 'Read from file metadata or entered by the analyst.' },
  ESTIMATED: { label: 'Estimated', meaning: 'Computed from the samples, with a stated uncertainty.' },
  HYPOTHESIS: { label: 'Hypothesis', meaning: 'A ranked candidate that is not confirmed.' },
  UNKNOWN: { label: 'Unknown', meaning: 'Cannot be determined from this data; the reason is stated.' },
}

export interface Alternative {
  value: string | number
  confidence: number | null
}

/** Mirrors the backend evidence model: every reported value carries its level, method and evidence. */
export interface Parameter {
  id: string
  name: string
  value: string | number | null
  unit?: string
  level: EvidenceLevel
  confidence: number | null
  method: string
  evidence: string[]
  alternatives: Alternative[]
  warnings: string[]
  /** For UNKNOWN: what additional input would settle it. */
  resolveHint?: string
  /** Required on an ESTIMATED numeric value; absent otherwise. */
  uncertainty?: number | null
  /** Set only on a HYPOTHESIS: the convention this value was taken on. */
  convention?: string | null
}

export type StageId = 'ingest' | 'detect' | 'estimate' | 'sync' | 'classify' | 'demod' | 'deinterleave' | 'fec' | 'frame'

export interface StageResult {
  id: StageId
  name: string
  status: 'done' | 'not-applicable'
  summary: string
  level: EvidenceLevel | null
  parameters: Parameter[]
}
