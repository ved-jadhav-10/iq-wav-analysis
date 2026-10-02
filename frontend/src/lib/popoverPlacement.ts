export interface Rect {
  left: number
  top: number
  right: number
  bottom: number
}

export interface Placement {
  left: number
  top: number
  placement: 'below' | 'above'
}

/** Where a fixed popover of `size` goes for an anchor: centred under it, flipped above when
 * there is no room below, and clamped so it stays inside the viewport by `margin` pixels. */
export function placePopover(
  anchor: Rect,
  size: { width: number; height: number },
  viewport: { width: number; height: number },
  gap = 6,
  margin = 8,
): Placement {
  const below = viewport.height - margin - (anchor.bottom + gap)
  const above = anchor.top - gap - margin
  const placement = below >= size.height || (above < size.height && below >= above) ? 'below' : 'above'
  const rawTop = placement === 'below' ? anchor.bottom + gap : anchor.top - gap - size.height
  const top = Math.max(margin, Math.min(rawTop, viewport.height - margin - size.height))
  const centre = (anchor.left + anchor.right) / 2
  const left = Math.max(margin, Math.min(centre - size.width / 2, viewport.width - margin - size.width))
  return { left, top, placement }
}
