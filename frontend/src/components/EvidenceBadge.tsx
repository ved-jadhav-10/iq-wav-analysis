import { LEVEL_INFO, type EvidenceLevel } from '@/lib/evidence'
import { LEVEL_CHIP, LEVEL_ICON } from './levelStyles'

/** Evidence level as glyph + label + colour. Never colour alone. */
export function EvidenceBadge({ level, className = '' }: { level: EvidenceLevel; className?: string }) {
  const Icon = LEVEL_ICON[level]
  return (
    <span
      title={LEVEL_INFO[level].meaning}
      className={`inline-flex shrink-0 items-center gap-1 rounded-[3px] px-1.5 py-px text-2xs font-semibold tracking-wide uppercase ring-1 ring-inset ${LEVEL_CHIP[level]} ${className}`}
    >
      <Icon className="size-3" strokeWidth={2.25} aria-hidden />
      {LEVEL_INFO[level].label}
    </span>
  )
}
