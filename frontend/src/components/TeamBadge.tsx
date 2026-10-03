import { useTheme } from '@/hooks/theme'
import teamFullDark from '@/assets/team-abhedya-dark.png'
import teamFullLight from '@/assets/team-abhedya-light.png'
import teamMarkDark from '@/assets/team-abhedya-mark-dark.png'
import teamMarkLight from '@/assets/team-abhedya-mark-light.png'

/** Team Abhedya's logo in the variant that suits the theme (the files carry their own backdrop, so
 * they sit in a rounded tile). `mark` is the shield alone, for the top bar; `full` adds the name. */
export function TeamLogo({ variant, className = '', alt = 'Team Abhedya' }: { variant: 'mark' | 'full'; className?: string; alt?: string }) {
  const { theme } = useTheme()
  const dark = theme === 'dark'
  const src = variant === 'mark' ? (dark ? teamMarkDark : teamMarkLight) : dark ? teamFullDark : teamFullLight
  return <img src={src} alt={alt} draggable={false} className={`rounded-md ${className}`} />
}

/** The top bar's team credit: the shield, and the name where there is room for it. */
export function TeamBadge() {
  return (
    <div className="flex shrink-0 items-center gap-1.5 max-xl:hidden" title="Team Abhedya">
      <TeamLogo variant="mark" alt="" className="size-8" />
      <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase max-3xl:sr-only">
        Team Abhedya
      </span>
    </div>
  )
}
