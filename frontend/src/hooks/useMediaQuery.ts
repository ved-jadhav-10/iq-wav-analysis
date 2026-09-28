import { useEffect, useState } from 'react'

/** `matchMedia` as reactive state. Used to switch between the draggable two-pane layout on wide
 * displays and the stacked one below, so the split is never applied where there's no room for it. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  )

  useEffect(() => {
    const mql = window.matchMedia(query)
    const onChange = () => setMatches(mql.matches)
    onChange()
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [query])

  return matches
}
