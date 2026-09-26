/** Sanket mark: a waveform resolving into a four-point constellation — signal in, symbols out. */
export function Logo({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} role="img" aria-label="Sanket">
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path
        d="M4.5 16c2-7 5-7 7 0s5 7 7 0"
        fill="none"
        className="stroke-primary-foreground"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <g className="fill-primary-foreground">
        <circle cx="22.5" cy="11.5" r="2" />
        <circle cx="27.5" cy="11.5" r="2" />
        <circle cx="22.5" cy="20.5" r="2" />
        <circle cx="27.5" cy="20.5" r="2" />
      </g>
    </svg>
  )
}
