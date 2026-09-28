/**
 * The workspace's nav. A section decides which regions of the analysis are on screen and how
 * they're laid out, so a demo can give the waterfall the whole display without a route change or a
 * second window.
 *
 * Two of these are deliberately *not* page sections, because neither is a place you sit:
 * - the per-detection deep dive is a full-screen overlay (`SignalOverlay.tsx`);
 * - `assumptions` keeps its nav slot so the button has a home, but it opens the Settings /
 *   Assumptions modal rather than switching the workspace. The modal can be summoned over any
 *   section, which a section could not do. `TopBar` dispatches on it; `App` never renders a view
 *   for it.
 *
 * A nav item that does nothing is a dead control, so this list is the single place one is
 * declared: if an entry goes, remove it here and the nav loses the button with it.
 *
 * State lives in `App` above the recording-keyed `Workspace`, so opening another recording keeps
 * the section the analyst was on and only resets the analysis state (zoom, selection) that belongs
 * to the old recording.
 */

export const VIEWS = [
  {
    id: 'survey',
    label: 'Survey',
    /** Digit for Alt+<digit>, shown in the button's title. */
    digit: '1',
    hint: 'Waterfall, spectrum and the pipeline rail side by side',
  },
  {
    id: 'waterfall',
    label: 'Waterfall',
    digit: '2',
    hint: 'The spectrogram full width, with the power spectrum under it',
  },
  {
    id: 'assumptions',
    label: 'Assumptions',
    digit: '3',
    hint: 'Everything the analysis took as given, over the current view',
  },
] as const

export type ViewId = (typeof VIEWS)[number]['id']

export const DEFAULT_VIEW: ViewId = 'survey'

const IDS: readonly string[] = VIEWS.map((v) => v.id)

export function isViewId(value: string): value is ViewId {
  return IDS.includes(value)
}

/** Next/previous section, wrapping. Used by the arrow keys and the nav group's roving focus. */
export function stepView(current: ViewId, delta: number): ViewId {
  const i = IDS.indexOf(current)
  // `current` is always a valid ViewId, but a corrupted stored value must not index -1 and throw.
  const from = i < 0 ? 0 : i
  return IDS[(from + delta + IDS.length) % IDS.length] as ViewId
}

export function viewByDigit(digit: string): ViewId | undefined {
  return VIEWS.find((v) => v.digit === digit)?.id
}

/* localStorage keeps the section across reloads. A demo that reopens the tool on Survey and has to
 * be clicked back to Assumptions mid-talk costs a beat, and this build is local-only, so the try/catch
 * is for a browser with storage disabled rather than for a network failure. */

const STORAGE_KEY = 'sanket.view.v1'

export function loadStoredView(): ViewId {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw && isViewId(raw) ? raw : DEFAULT_VIEW
  } catch {
    return DEFAULT_VIEW
  }
}

export function storeView(view: ViewId): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, view)
  } catch {
    // Nothing to do: the section still works, it just won't survive a reload.
  }
}
