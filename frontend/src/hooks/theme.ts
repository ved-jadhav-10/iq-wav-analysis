import { createContext, useContext } from 'react'

export type Theme = 'dark' | 'light'

export const THEME_STORAGE_KEY = 'sanket-theme'

export const ThemeContext = createContext<{ theme: Theme; toggle: () => void } | null>(null)

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}
