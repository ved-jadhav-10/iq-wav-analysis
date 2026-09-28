import type { DetectionInfo } from '@/lib/api'
import { ParameterCard } from './EvidencePanel'

/** A real detection's own evidence (PLAN §5 M2): the same `Parameter` cards `EvidencePanel`
 * uses for a demo stage, since `detect`'s findings carry the same honesty rules. There is no
 * per-stage rail yet - only this one stage exists for a real recording so far. */
export function DetectionEvidencePanel({ detection, index }: { detection: DetectionInfo; index: number }) {
  return (
    <div className="space-y-2 px-3 py-3">
      <h2 className="eyebrow">Detect · #{index + 1}</h2>
      <div className="space-y-2">
        {detection.parameters.map((p) => (
          <ParameterCard key={p.id} param={p} />
        ))}
      </div>
      <p className="pt-2 text-xs text-muted-foreground">
        Synchronisation, demodulation and per-stage evidence beyond this aren't built yet (PLAN M3
        onward).
      </p>
    </div>
  )
}
