import { afterEach, describe, expect, it, vi } from 'vitest'
import { hasSeenOnboarding, markOnboardingSeen, resetOnboarding } from './onboarding'

const KEY = 'sanket.onboarding.v1'

function store() {
  const data = new Map<string, string>()
  vi.stubGlobal('window', {
    localStorage: {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => void data.set(k, v),
      removeItem: (k: string) => void data.delete(k),
    },
  })
  return data
}

describe('onboarding memory', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('has not been seen by default', () => {
    store()
    expect(hasSeenOnboarding()).toBe(false)
  })

  it('remembers once marked, and forgets on reset', () => {
    const data = store()
    markOnboardingSeen()
    expect(data.has(KEY)).toBe(true)
    expect(hasSeenOnboarding()).toBe(true)
    resetOnboarding()
    expect(data.has(KEY)).toBe(false)
    expect(hasSeenOnboarding()).toBe(false)
  })

  it('survives storage that throws', () => {
    const boom = () => {
      throw new Error('storage disabled')
    }
    vi.stubGlobal('window', {
      localStorage: { getItem: boom, setItem: boom, removeItem: boom },
    })
    expect(hasSeenOnboarding()).toBe(false)
    expect(() => markOnboardingSeen()).not.toThrow()
    expect(() => resetOnboarding()).not.toThrow()
  })

  it('survives a window with no storage at all', () => {
    vi.stubGlobal('window', {})
    expect(hasSeenOnboarding()).toBe(false)
    expect(() => markOnboardingSeen()).not.toThrow()
  })
})
