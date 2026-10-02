import { useEffect, useState } from 'react'
import { loadSummary, type SummaryState } from '@/lib/summary'

interface Settled {
  id: string
  attempt: number
  state: SummaryState
}

/** The plain-language summary of a finished recording, fetched once when `id` is set (the caller
 * passes it only after the analysis has finished) and again on `retry`. While the answer for the
 * current `id` and attempt has not arrived the state is `loading`, so a stale answer is never
 * shown for a different recording. */
export function useSummary(id: string): { state: SummaryState; retry: () => void } {
  const [attempt, setAttempt] = useState(0)
  const [settled, setSettled] = useState<Settled | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    loadSummary(id, { signal: controller.signal }).then(
      (text) => setSettled({ id, attempt, state: { status: 'ready', text } }),
      (e: unknown) => {
        if (controller.signal.aborted) return
        setSettled({ id, attempt, state: { status: 'error', message: e instanceof Error ? e.message : String(e) } })
      },
    )
    return () => controller.abort()
  }, [id, attempt])

  const current = settled && settled.id === id && settled.attempt === attempt ? settled.state : null
  return { state: current ?? { status: 'loading' }, retry: () => setAttempt((n) => n + 1) }
}
