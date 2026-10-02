/* localStorage remembers that the welcome dialog has been shown. Every access is wrapped: a browser
 * with storage disabled (or a private window) just shows the welcome again on each launch. */

const STORAGE_KEY = 'sanket.onboarding.v1'

export function hasSeenOnboarding(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'seen'
  } catch {
    return false
  }
}

export function markOnboardingSeen(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, 'seen')
  } catch {
    // Nothing to do: the welcome simply shows again next time.
  }
}

export function resetOnboarding(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Nothing to do.
  }
}
