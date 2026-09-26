import { useEffect, useState } from 'react'
import type { DemoProducts } from '@/lib/demoSignal'

/** Generates the synthetic capture off the main thread so first paint isn't blocked. */
export function useDemoProducts(): { products: DemoProducts | null; error: string | null } {
  const [products, setProducts] = useState<DemoProducts | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const worker = new Worker(new URL('../workers/demo.worker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = (e: MessageEvent<DemoProducts>) => setProducts(e.data)
    worker.onerror = (e) => setError(e.message || 'Signal generation failed')
    return () => worker.terminate()
  }, [])

  return { products, error }
}
