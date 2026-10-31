// The days left to apply in a pill-shaped ring, in place of the reference's match score: the ring is the part of the
// application window still open, green with time to spare, orange in the last week and red in the last two days.

import { plural } from '../../shared/format'

const WIDTH = 76
const HEIGHT = 40
const STROKE = 3
const INSET = STROKE / 2
const RADIUS = HEIGHT / 2 - INSET
// From the top middle, clockwise, so the ring fills like a clock.
const RING_PATH = `M ${WIDTH / 2} ${INSET} H ${WIDTH - INSET - RADIUS} A ${RADIUS} ${RADIUS} 0 0 1 ${WIDTH - INSET - RADIUS} `
  + `${HEIGHT - INSET} H ${INSET + RADIUS} A ${RADIUS} ${RADIUS} 0 0 1 ${INSET + RADIUS} ${INSET} Z`

export interface Deadline {
  daysLeft: number
  // The part of the application window still open, 0 to 1.
  open: number
}

const deadlineTone = (days: number) => (days <= 2 ? 'urgent' : days <= 7 ? 'soon' : 'open')

export function DeadlineRing({ deadline }: { deadline: Deadline }) {
  const { daysLeft, open } = deadline
  const label = daysLeft === 0 ? 'Prijave još danas' : `Još ${daysLeft} ${plural(daysLeft, 'dan', 'dana', 'dana')} za prijavu`
  return (
    <div className={`ring ${deadlineTone(daysLeft)}`} role="img" aria-label={label} title={label} data-slot="ring">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width={WIDTH} height={HEIGHT} aria-hidden="true">
        <path className="ring-track" d={RING_PATH} pathLength={100} />
        <path className="ring-fill" d={RING_PATH} pathLength={100} data-slot="ring-fill"
          strokeDasharray={`${open * 100} 100`} />
      </svg>
      <span className="ring-text" aria-hidden="true">
        {daysLeft === 0 ? <b>Danas</b> : (
          <>
            <b data-slot="ring-days">{daysLeft}</b>
            <small>{plural(daysLeft, 'dan', 'dana', 'dana')}</small>
          </>
        )}
      </span>
    </div>
  )
}
