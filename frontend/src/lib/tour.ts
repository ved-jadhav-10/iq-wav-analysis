import { driver, type DriveStep } from 'driver.js'
import 'driver.js/dist/driver.css'
import type { SectionId } from './views'

interface TourStep {
  /** Matches `data-tour="<anchor>"` on the element the step points at. */
  anchor: string
  title: string
  description: string
  /** The section the element lives in. Absent for the top bar, which every section shows. */
  section?: SectionId
}

export const TOUR_STEPS: readonly TourStep[] = [
  {
    anchor: 'open',
    title: 'Open any recording',
    description:
      'Choose files, or type a path to a file or folder. Dropping files anywhere on the window works too. IQ, WAV and SigMF all open.',
  },
  {
    anchor: 'section-nav',
    title: 'Sections',
    description:
      'Dashboard shows the plots. Evidence, Hypotheses and Summary go deeper into one signal or the whole recording. History keeps finished analyses. Assumptions opens over any of them.',
  },
  {
    anchor: 'detections',
    title: 'Signals and pipeline',
    description:
      'One card per signal, with how sure Sanket is. The stages below show how far the decode got; click one to read its evidence.',
    section: 'dashboard',
  },
  {
    anchor: 'waterfall',
    title: 'Waterfall and spectrum',
    description: 'Time runs down, frequency across. Boxes mark each signal found.',
    section: 'dashboard',
  },
  {
    anchor: 'constellation',
    title: 'Constellation',
    description:
      'The received symbols after timing and phase recovery. Tight clusters mean a clean signal. FSK and analog signals have none, and it says why.',
    section: 'dashboard',
  },
  {
    anchor: 'eye',
    title: 'Eye diagram',
    description: 'I and Q overlaid over one symbol. A wide-open eye is a clean signal. It says so when there is no eye to draw.',
    section: 'dashboard',
  },
  {
    anchor: 'evidence',
    title: 'Evidence',
    description:
      'Every value shows its level and method; unknowns say what would settle them. The Frames and Bit stream tabs hold the recovered frames with their CRC results.',
    section: 'evidence',
  },
  {
    anchor: 'hypotheses',
    title: 'Hypotheses',
    description: 'Every guess the blind search tried, with the corrected threshold and why each was kept or rejected.',
    section: 'hypotheses',
  },
  {
    anchor: 'summary',
    title: 'Plain-language summary',
    description: 'What was proved, what was only estimated, and what is still unknown. Written once the analysis finishes.',
    section: 'summary',
  },
  {
    anchor: 'export',
    title: 'Download',
    description: 'JSON, CSV, summary, PDF or run record, each carrying the recording’s SHA-256.',
  },
  {
    anchor: 'assumptions',
    title: 'Assumptions',
    description: 'Everything taken as given: sample rate, format, IQ order.',
  },
]

/** The anchor names the app must place as `data-tour` attributes. */
export const TOUR_ANCHORS: readonly string[] = TOUR_STEPS.map((s) => s.anchor)

const selector = (anchor: string) => `[data-tour="${anchor}"]`
const present = (anchor: string) => document.querySelector(selector(anchor)) !== null

/**
 * Where the Open step's popover goes: beside the button, never under it, because that is where the
 * Open menu drops down and the analyst may open it mid-tour. From 1280px the menu hangs from the
 * button's left edge, so the popover goes left of the button; below that it is fixed to the window's
 * left edge (OpenMenu's `max-xl`), so the popover goes right.
 */
function openPlacement(): Pick<NonNullable<DriveStep['popover']>, 'side' | 'align'> {
  return { side: window.matchMedia('(min-width: 1280px)').matches ? 'left' : 'right', align: 'start' }
}

/** Two animation frames: the next section is in the DOM and laid out. */
function settled(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
}

interface Options {
  onDone(): void
  /** The section on screen now; the tour returns to it when it ends. */
  section?: SectionId
  /** Switches the workspace to a section. Without it only what is on screen is toured. */
  showSection?: (section: SectionId) => void
  /** Leaves for the start screen. While the tour dims the page, a click on the element marked
   * `data-home` ends the tour and calls it, instead of just closing the tour. */
  onHome?: () => void
}

/**
 * Steps for what is on screen now, plus (when `showSection` is given and a recording is open) the
 * steps that live in other sections, which the tour switches to as it reaches them.
 */
function tourSteps(opts: Options): TourStep[] {
  const canSwitch = Boolean(opts.showSection) && present('section-nav')
  return TOUR_STEPS.filter((s) => (canSwitch && s.section && s.section !== opts.section) || present(s.anchor))
}

export function startTour(opts: Options): void {
  const steps = tourSteps(opts)
  if (steps.length === 0) {
    opts.onDone()
    return
  }
  let shown = opts.section
  let moving = false
  let finished = false

  /** Back to the section the analyst started on, then done; once only. */
  function finish() {
    if (finished) return
    finished = true
    if (opts.onHome) document.removeEventListener('click', onHomeClick, true)
    if (opts.showSection && opts.section && shown !== opts.section) opts.showSection(opts.section)
    opts.onDone()
  }

  /** driver.js switches pointer events off for everything but its own elements, so the home
   * control is found by where the click landed, not by its target. A click on the popover is the
   * popover's, even where it covers the control. */
  function onHomeClick(e: MouseEvent) {
    const home = document.querySelector('[data-home]')?.getBoundingClientRect()
    if (!home) return
    const inside = (r: DOMRect) => e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom
    const popover = document.querySelector('.driver-popover')?.getBoundingClientRect()
    if (!inside(home) || (popover && inside(popover))) return
    e.preventDefault()
    e.stopImmediatePropagation() // before driver.js reads it as a click on the overlay
    tour.destroy()
    finish()
    opts.onHome?.()
  }

  /** Moves to the next (or previous) step whose element exists, switching section on the way. */
  async function go(direction: 1 | -1) {
    if (moving) return
    moving = true
    try {
      for (let j = tour.getActiveIndex()! + direction; j >= 0 && j < steps.length; j += direction) {
        const target = steps[j]!
        if (target.section && target.section !== shown && opts.showSection) {
          opts.showSection(target.section)
          shown = target.section
          await settled()
        }
        if (present(target.anchor)) {
          tour.moveTo(j)
          return
        }
      }
      if (direction === 1) {
        tour.destroy()
        finish()
      }
    } finally {
      moving = false
    }
  }

  const driveSteps: DriveStep[] = steps.map((s) => ({
    element: selector(s.anchor),
    popover: { title: s.title, description: s.description, ...(s.anchor === 'open' ? openPlacement() : {}) },
  }))
  const tour = driver({
    steps: driveSteps,
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
    onNextClick: () => void go(1),
    onPrevClick: () => void go(-1),
    // driver.js only calls `onDestroyed` once the current step has finished animating in, so a
    // quick Done or Esc would end the tour without it: closing goes through `finish` as well.
    onDestroyStarted: () => {
      tour.destroy()
      finish()
    },
    onDestroyed: finish,
  })
  if (opts.onHome) document.addEventListener('click', onHomeClick, true)
  tour.drive()
}
