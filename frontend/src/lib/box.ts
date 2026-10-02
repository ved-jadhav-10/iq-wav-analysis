/** A time/frequency rectangle: seconds and hertz (delta-f from capture centre), the same units
 * `View` uses. The boxes computed from a real recording's
 * detections (PLAN §5 M2, `backend`'s `Box`) share this shape. */
export interface Box {
  t0: number
  t1: number
  f0: number
  f1: number
}
