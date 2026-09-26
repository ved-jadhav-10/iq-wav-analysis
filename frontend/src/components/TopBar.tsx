import { FileAudio, Moon, Sun, WifiOff } from 'lucide-react'
import { BRAND } from '@/brand'
import { RECORDING } from '@/data/demoAnalysis'
import { useTheme } from '@/hooks/theme'
import { Logo } from './Logo'

export function TopBar() {
  const { theme, toggle } = useTheme()
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b bg-surface px-3">
      <div className="flex items-center gap-2.5">
        <Logo className="size-7" />
        <div className="flex items-baseline gap-2">
          <span className="text-[15px] font-semibold tracking-tight">{BRAND.name}</span>
          <span lang="hi" className="font-deva text-xs text-subtle-foreground max-sm:hidden">
            {BRAND.nativeName}
          </span>
        </div>
      </div>

      <div className="h-5 w-px bg-border max-sm:hidden" aria-hidden />

      <div className="flex min-w-0 items-center gap-2">
        <FileAudio className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="num truncate text-xs">{RECORDING.fileName}</span>
        <span className="shrink-0 rounded-[3px] border border-dashed border-border-strong px-1.5 text-2xs font-medium text-muted-foreground uppercase">
          Synthetic demo
        </span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <span
          className="flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-2xs font-medium text-muted-foreground max-md:hidden"
          title="This build loads nothing from the network: fonts, code and data are all bundled."
        >
          <WifiOff className="size-3" aria-hidden />
          Offline build
        </span>
        <button
          type="button"
          onClick={toggle}
          className="grid size-8 place-items-center rounded-md text-muted-foreground hover:bg-surface-2 hover:text-foreground"
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        >
          {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
      </div>
    </header>
  )
}
