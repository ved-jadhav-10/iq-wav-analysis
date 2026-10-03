import { useTheme } from '@/hooks/theme'
import logoDark from '@/assets/sanket-logo-dark.svg'
import logoLight from '@/assets/sanket-logo-light.svg'
import markDark from '@/assets/sanket-mark-dark.svg'
import markLight from '@/assets/sanket-mark-light.svg'

/**
 * Sanket's mark: the Devanagari letter स (the first letter of संकेत). The spectrogram strip is its
 * headline, the curled body its left stroke, and the figure-8 trace its vertical stroke. The light
 * or dark file follows the theme. `mark` is the simplified version (coarse strip, no glow) that stays
 * readable from the favicon up to about 48px; `full` is the detailed artwork, for larger sizes.
 */
export function Logo({ className = '', variant = 'mark' }: { className?: string; variant?: 'mark' | 'full' }) {
  const { theme } = useTheme()
  const dark = theme === 'dark'
  const src = variant === 'full' ? (dark ? logoDark : logoLight) : dark ? markDark : markLight
  return <img src={src} alt="Sanket" draggable={false} className={className} />
}
