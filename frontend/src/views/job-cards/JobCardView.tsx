// One job, after the reference card: the employer's name and line, the title, the job's labels and, under a rule,
// when it was published and until when to apply, with its actions, on a tile of the Performance chart. Animated with
// anime.js like that chart's tiles: the card rises in after the ones before it, then the labels come in one after
// another and the footer last.

import { animate, stagger } from 'animejs'
import { useRef } from 'react'
import { fadeIn, finish, releaseStyles, useChartEntrance } from '../../shared/chart-motion'
import { chips, deadline, published, sentenceCase, subtitle } from './job-format'
import type { JobCard } from './types'

// The Performance chart's tile entrance: each tile rises 10px over 800ms after the one before it (70ms).
const CARD_STAGGER = 70
const CHIPS_AT = 300
const FOOT_AT = 450

export interface CardActions {
  // Open the advertisement on the HZZ site.
  open: (job: JobCard) => void
  // Ask about the job in the conversation; null outside a host.
  ask: ((job: JobCard) => void) | null
}

const OPEN_ICON = ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5']
const ASK_ICON = ['M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z', 'M8.5 12h.01', 'M12 12h.01', 'M15.5 12h.01']

/** A footer action: its icon pops when pressed. */
function Action({ label, icon, onClick }: { label: string; icon: string[]; onClick: () => void }) {
  return (
    <button className="icon-button" type="button" title={label} aria-label={label} onClick={(event) => {
      finish(animate(event.currentTarget.firstElementChild!, { scale: [0.7, 1], duration: 500, ease: 'outBack(2.4)',
        onComplete: releaseStyles('transform') }))
      onClick()
    }}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
        strokeLinejoin="round" aria-hidden="true">
        {icon.map((d) => <path key={d} d={d} />)}
      </svg>
    </button>
  )
}

/** order is the card's place among the cards that came in together, which delays its entrance. */
export function JobCardView({ job, today, order, actions }: {
  job: JobCard
  today: string
  order: number
  actions: CardActions
}) {
  const labels = chips(job)
  const employer = job.employer_name ?? 'Poslodavac nije naveden'
  const root = useRef<HTMLElement>(null)

  useChartEntrance(root, (timeline) => {
    const card = root.current!
    const all = (selector: string) => [...card.querySelectorAll<HTMLElement>(selector)]
    const at = order * CARD_STAGGER
    timeline.add(card, { ...fadeIn([card], 10), duration: 800, ease: 'outExpo' }, at)
    const labels = all('[data-slot="chip"]')
    if (labels.length) timeline.add(labels, { ...fadeIn(labels, 4), duration: 500, delay: stagger(40) }, at + CHIPS_AT)
    const foot = all('[data-slot="foot"]')
    timeline.add(foot, { ...fadeIn(foot), duration: 500 }, at + FOOT_AT)
    return () => {
      for (const el of [card, ...labels, ...foot]) {
        el.style.removeProperty('opacity')
        el?.style.removeProperty('transform')
      }
    }
  })

  return (
    <article className="job" ref={root} data-slot="job" aria-label={`${sentenceCase(job.display_title)}, ${employer}`}>
      <div className="titles">
        <p className="employer truncate" title={employer}>{employer}</p>
        <p className="soft truncate">{subtitle(job)}</p>
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
        <Action label="Otvori oglas na HZZ-u" icon={OPEN_ICON} onClick={() => actions.open(job)} />
        {actions.ask && <Action label="Pitaj o ovom oglasu" icon={ASK_ICON} onClick={() => actions.ask?.(job)} />}
      </div>
    </article>
  )
}
