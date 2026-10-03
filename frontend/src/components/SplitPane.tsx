import type { CSSProperties, ReactNode } from 'react'
import { useSplit } from '@/hooks/useSplit'

interface Props {
  /** The fixed-width left column (the pipeline rail). */
  rail: ReactNode
  /** The main plot column. */
  main: ReactNode
  /** The resizable right column. `null` hides it and the gutter with it. */
  panel: ReactNode | null
  /** Keeps the separator's accessible name in step with whatever is in the panel. */
  panelLabel: string
  /** Width of the fixed left column, so the split measures the space that's actually resizable. */
  railWidth?: number
  minPanelPx?: number
}

const GUTTER_PX = 6

/** Two panes with a draggable, persisted split between them.
 *
 * The split lives here rather than in the page so the refs never cross a component boundary:
 * `react-hooks/refs` treats a `ref` prop on a custom component as a read during render, which is
 * right in general and wrong here, since these refs are the hook's own.
 *
 * Columns are built in pixels for the two resizable ones and `minmax(0, 1fr)` for the last, because
 * the fraction is of the space *after* the fixed rail - a percentage of the whole container would
 * hand the rail's width to the plot and leave the panel short.
 *
 * The separator is a focusable `role="separator"` with arrow-key support, so the split is reachable
 * without a pointer. Below the page's breakpoint this component isn't used at all, since a gutter
 * would have nothing to divide.
 */
export function SplitPane({ rail, main, panel, panelLabel, railWidth = 216, minPanelPx = 340 }: Props) {
  const { setContainer, setGutter, fraction, available } = useSplit(
    'sanket.split.v2',
    0.72,
    minPanelPx,
    railWidth,
  )
  const percent = Math.round(fraction * 100)

  // Before the first measurement `available` is 0. Falling back to `1fr` there rather than `0px`
  // means the first paint is a sane layout that the measurement then refines, instead of a
  // collapsed plot column that flashes.
  const style: CSSProperties = {
    gridTemplateColumns: panel
      ? available > 0
        ? `${railWidth}px minmax(0, ${available * fraction}px) ${GUTTER_PX}px minmax(0, 1fr)`
        : `${railWidth}px minmax(0, 1fr) ${GUTTER_PX}px minmax(0, 1fr)`
      : `${railWidth}px minmax(0, 1fr)`,
  }

  return (
    // `grid-rows-[minmax(0,1fr)]` is load-bearing, not decoration: with no explicit row the
    // implicit row is content-sized, so the waterfall section would size to its own content and
    // overflow this box - and because the canvas is absolutely positioned with `size-full`, its
    // `height` attribute becomes the content height, which the ResizeObserver then re-measures.
    // That ratchets the plot to whatever it was first measured at and never shrinks it back.
    <main
      ref={setContainer}
      style={style}
      className="grid min-h-0 w-full min-w-0 flex-1 grid-rows-[minmax(0,1fr)]"
    >
      {rail}
      {main}
      {panel && (
        <>
          <div
            ref={setGutter}
            role="separator"
            aria-orientation="vertical"
            aria-label={`Resize ${panelLabel}`}
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            tabIndex={0}
            title="Drag, or use the arrow keys, to resize"
            className="group relative w-1.5 shrink-0 cursor-col-resize bg-border focus-visible:outline-2 focus-visible:outline-ring"
          >
            {/* Widens the grab target well past its 6px without changing the layout. */}
            <span className="absolute inset-y-0 -left-1 -right-1" aria-hidden />
            <span
              className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-primary opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
              aria-hidden
            />
          </div>
          {panel}
        </>
      )}
    </main>
  )
}
