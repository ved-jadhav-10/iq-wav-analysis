import type { Box } from './box'
import type { EvidenceLevel } from './evidence'

/**
 * What `Waterfall` and `PsdPlot` need to draw and badge a detection. The demo `Detection` (a
 * superset, with modulation kind, per-stage evidence, the hypothesis ledger and frames - all
 * M3+/M4/M6) satisfies this structurally; so does a real recording's detection (PLAN §5 M2),
 * which has none of that yet - only a box and `detect`'s own evidence.
 */
export interface DetectionMarker {
  id: number
  label: string
  level: EvidenceLevel
  boxes: Box[]
}
