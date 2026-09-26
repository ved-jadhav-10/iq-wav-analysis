import { CircleDashed, CircleSlash, Ruler, ShieldCheck, Sigma, type LucideIcon } from 'lucide-react'
import type { EvidenceLevel } from '@/lib/evidence'

// Literal class strings so Tailwind can see them at build time.
export const LEVEL_ICON: Record<EvidenceLevel, LucideIcon> = {
  VERIFIED: ShieldCheck,
  MEASURED: Ruler,
  ESTIMATED: Sigma,
  HYPOTHESIS: CircleDashed,
  UNKNOWN: CircleSlash,
}

export const LEVEL_TEXT: Record<EvidenceLevel, string> = {
  VERIFIED: 'text-ev-verified',
  MEASURED: 'text-ev-measured',
  ESTIMATED: 'text-ev-estimated',
  HYPOTHESIS: 'text-ev-hypothesis',
  UNKNOWN: 'text-ev-unknown',
}

export const LEVEL_CHIP: Record<EvidenceLevel, string> = {
  VERIFIED: 'text-ev-verified bg-ev-verified/10 ring-ev-verified/30',
  MEASURED: 'text-ev-measured bg-ev-measured/10 ring-ev-measured/30',
  ESTIMATED: 'text-ev-estimated bg-ev-estimated/10 ring-ev-estimated/30',
  HYPOTHESIS: 'text-ev-hypothesis bg-ev-hypothesis/10 ring-ev-hypothesis/30',
  UNKNOWN: 'text-ev-unknown bg-ev-unknown/10 ring-ev-unknown/30',
}

export const LEVEL_BORDER: Record<EvidenceLevel, string> = {
  VERIFIED: 'border-ev-verified',
  MEASURED: 'border-ev-measured',
  ESTIMATED: 'border-ev-estimated',
  HYPOTHESIS: 'border-ev-hypothesis',
  UNKNOWN: 'border-ev-unknown',
}

export const LEVEL_FILL: Record<EvidenceLevel, string> = {
  VERIFIED: 'bg-ev-verified',
  MEASURED: 'bg-ev-measured',
  ESTIMATED: 'bg-ev-estimated',
  HYPOTHESIS: 'bg-ev-hypothesis',
  UNKNOWN: 'bg-ev-unknown',
}

export const LEVEL_CSS_VAR: Record<EvidenceLevel, string> = {
  VERIFIED: '--ev-verified',
  MEASURED: '--ev-measured',
  ESTIMATED: '--ev-estimated',
  HYPOTHESIS: '--ev-hypothesis',
  UNKNOWN: '--ev-unknown',
}
