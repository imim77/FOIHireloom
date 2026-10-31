// One job, after the reference card: the employer's tile, name and line, the days left to apply, the title, the
// job's labels and, under a rule, when it was published and until when to apply, with its actions. Animated with
// anime.js like the county chart: the card rises in after the ones before it, the tile pops, the ring fills while its
// days count up, then the labels come in one after another and the footer last.

import { stagger, utils } from 'animejs'
import { useRef } from 'react'
import { fadeIn, releaseStyles, useChartEntrance } from '../../shared/chart-motion'
import { type Deadline, DeadlineRing } from './DeadlineRing'
import { chips, daysBetween, deadline, initials, published, sentenceCase, subtitle } from './job-format'
import type { JobCard } from './types'

const CARD_STAGGER = 90
const TILE_AT = 150
const RING_AT = 250
const CHIPS_AT = 300
const FOOT_AT = 450
const FILL = 1100

function deadlineOf(job: JobCard, today: string): Deadline | null {
  if (!job.deadline_on || job.deadline_passed) return null
  const daysLeft = Math.max(0, daysBetween(today, job.deadline_on))
  const window = job.published_on ? daysBetween(job.published_on, job.deadline_on) : Math.max(daysLeft, 30)
  return { daysLeft, open: window > 0 ? Math.min(1, daysLeft / window) : 0 }
}

/** order is the card's place among the cards that came in together, which delays its entrance. */
export function JobCardView({ job, today, order }: { job: JobCard; today: string; order: number }) {
  const ring = deadlineOf(job, today)
  const labels = chips(job)
  const employer = job.employer_name ?? 'Poslodavac nije naveden'
  const root = useRef<HTMLElement>(null)

  useChartEntrance(root, (timeline) => {
    const card = root.current!
    const one = (selector: string) => card.querySelector<HTMLElement>(selector)
    const all = (selector: string) => [...card.querySelectorAll<HTMLElement>(selector)]
    const at = order * CARD_STAGGER
    timeline.add(card, { ...fadeIn([card], 12), duration: 600 }, at)
    const tile = one('[data-slot="tile"]')
    if (tile) {
      utils.set(tile, { opacity: 0, scale: 0.6 })
      timeline.add(tile, { opacity: [0, 1], scale: [0.6, 1], duration: 700, ease: 'outBack(1.8)',
        onComplete: releaseStyles('opacity', 'transform') }, at + TILE_AT)
    }
    const fill = one('[data-slot="ring-fill"]')
    const days = one('[data-slot="ring-days"]')
    const draw = (t: number) => {
      if (!ring) return
      fill?.setAttribute('stroke-dasharray', `${ring.open * 100 * t} 100`)
      if (days) days.textContent = String(Math.round(ring.daysLeft * t))
    }
    if (ring) {
      const filled = { t: 0 }
      draw(0)
      timeline.add(filled, { t: [0, 1], duration: FILL, ease: 'outExpo', onUpdate: () => draw(filled.t) }, at + RING_AT)
    }
    const labels = all('[data-slot="chip"]')
    if (labels.length) timeline.add(labels, { ...fadeIn(labels, 4), duration: 500, delay: stagger(40) }, at + CHIPS_AT)
    const foot = all('[data-slot="foot"]')
    timeline.add(foot, { ...fadeIn(foot), duration: 500 }, at + FOOT_AT)
    return () => {
      draw(1)
      for (const el of [card, tile, ...labels, ...foot]) {
        el?.style.removeProperty('opacity')
        el?.style.removeProperty('transform')
      }
    }
  })

  return (
    <article className="job" ref={root} data-slot="job" aria-label={`${sentenceCase(job.display_title)}, ${employer}`}>
      <div className="job-head">
        <span className="tile" aria-hidden="true" data-slot="tile">{initials(job.employer_name)}</span>
        <div className="titles">
          <p className="employer truncate" title={employer}>{employer}</p>
          <p className="soft-line truncate">{subtitle(job)}</p>
        </div>
        {ring && <DeadlineRing deadline={ring} />}
      </div>
      <h2 className="job-title">{sentenceCase(job.display_title)}</h2>
      {labels.length > 0 && (
        <ul className="chips" aria-label="Uvjeti">
          {labels.map((chip) => (
            <li key={chip.text} className={`chip ${chip.tone}`} data-slot="chip">{chip.text}</li>
          ))}
        </ul>
      )}
      <div className="job-foot" data-slot="foot">
        <p className="when">
          {published(job, today)} · <b>{deadline(job)}</b>
        </p>
      </div>
    </article>
  )
}
