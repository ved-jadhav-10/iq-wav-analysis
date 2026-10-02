import { driver, type DriveStep } from 'driver.js'
import 'driver.js/dist/driver.css'

interface TourStep {
  /** Matches `data-tour="<anchor>"` on the element the step points at. */
  anchor: string
  title: string
  description: string
}

export const TOUR_STEPS: readonly TourStep[] = [
  {
    anchor: 'open',
    title: 'Open any recording',
    description: 'Type a path, upload a file, or drop one on the window. IQ, WAV and SigMF all work.',
  },
  {
    anchor: 'section-nav',
    title: 'Sections',
    description:
      'Survey shows everything at once. Waterfall gives the whole display to the spectrogram. History keeps finished analyses.',
  },
  {
    anchor: 'waterfall',
    title: 'Waterfall and spectrum',
    description: 'Time runs down, frequency across. Boxes mark each signal found.',
  },
  {
    anchor: 'detections',
    title: 'Signals found',
    description: 'One card per signal, with how sure Sanket is. The stages below show how far the decode got.',
  },
  {
    anchor: 'evidence',
    title: 'Evidence',
    description: 'Every value shows its level and method. If it is unknown, it says what would settle it.',
  },
  {
    anchor: 'symbols',
    title: 'Constellation / eye',
    description: 'The received symbols after timing and phase recovery. Tight clusters mean a clean signal.',
  },
  {
    anchor: 'bottom-tabs',
    title: 'Hypotheses and frames',
    description:
      'Every guess the blind search tried, with the corrected threshold, and the frames recovered with CRC result, header and payload.',
  },
  {
    anchor: 'summary',
    title: 'Plain-language summary',
    description: 'What was proved, what was estimated, and what is still unknown.',
  },
  {
    anchor: 'export',
    title: 'Export',
    description: 'JSON, CSV, summary or PDF, each carrying the recording’s SHA-256.',
  },
  {
    anchor: 'assumptions',
    title: 'Assumptions',
    description: 'Everything taken as given: sample rate, format, IQ order.',
  },
]

/** The anchor names the app must place as `data-tour` attributes. */
export const TOUR_ANCHORS: readonly string[] = TOUR_STEPS.map((s) => s.anchor)

/** Steps whose element is in the DOM right now; a section that is not showing is skipped. */
function presentSteps(): DriveStep[] {
  return TOUR_STEPS.filter((s) => document.querySelector(`[data-tour="${s.anchor}"]`)).map((s) => ({
    element: `[data-tour="${s.anchor}"]`,
    popover: { title: s.title, description: s.description },
  }))
}

export function startTour(opts: { onDone(): void }): void {
  const steps = presentSteps()
  if (steps.length === 0) {
    opts.onDone()
    return
  }
  const tour = driver({
    steps,
    showProgress: true,
    progressText: '{{current}} of {{total}}',
    allowClose: true,
    overlayClickBehavior: 'close',
    popoverClass: 'sanket-tour',
    nextBtnText: 'Next',
    prevBtnText: 'Back',
    doneBtnText: 'Done',
    animate: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    smoothScroll: false,
    stagePadding: 4,
    allowKeyboardControl: true,
    onDestroyed: () => opts.onDone(),
  })
  tour.drive()
}
