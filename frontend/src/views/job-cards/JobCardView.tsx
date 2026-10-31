// One job, after the reference card: the employer's tile, name and line, the title, the job's labels and, under a
// rule, when it was published and until when to apply, with its actions, on a 3D column like the county chart's.
// Animated with anime.js like the chart: the card comes in after the ones before it as its column rises from its
// foot, the tile pops, then the labels come in one after another and the footer last.

import { animate, stagger, utils } from 'animejs'
import { useRef } from 'react'
import { fadeIn, finish, releaseStyles, useChartEntrance } from '../../shared/chart-motion'
import { chips, deadline, published, sentenceCase, subtitle } from './job-format'
import type { JobCard } from './types'

const CARD_STAGGER = 90
const TILE_AT = 150
// The column rises from its foot like the chart's bars.
const GROW = 1100
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

/** One look of the card's column: two faces and a lid, as a column of the county chart draws them. */
function ColumnLook({ lit }: { lit: boolean }) {
  return (
    <span className={`look ${lit ? 'lit' : 'grey'}`}>
      <i className="face left" />
      <i className="face right" />
      <i className="lid" />
    </span>
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
    const one = (selector: string) => card.querySelector<HTMLElement>(selector)
    const all = (selector: string) => [...card.querySelectorAll<HTMLElement>(selector)]
    const at = order * CARD_STAGGER
    timeline.add(card, { ...fadeIn([card], 12), duration: 600 }, at)
    const column = one('[data-slot="column"]')
    if (column) {
      utils.set(column, { scaleY: 0 })
      timeline.add(column, { scaleY: [0, 1], duration: GROW, ease: 'outExpo', onComplete: releaseStyles('transform') }, at)
    }
    const tile = one('[data-slot="tile"]')
    if (tile) {
      utils.set(tile, { opacity: 0, scale: 0.6 })
      timeline.add(tile, { opacity: [0, 1], scale: [0.6, 1], duration: 700, ease: 'outBack(1.8)',
        onComplete: releaseStyles('opacity', 'transform') }, at + TILE_AT)
    }
    const labels = all('[data-slot="chip"]')
    if (labels.length) timeline.add(labels, { ...fadeIn(labels, 4), duration: 500, delay: stagger(40) }, at + CHIPS_AT)
    const foot = all('[data-slot="foot"]')
    timeline.add(foot, { ...fadeIn(foot), duration: 500 }, at + FOOT_AT)
    return () => {
      for (const el of [card, column, tile, ...labels, ...foot]) {
        el?.style.removeProperty('opacity')
        el?.style.removeProperty('transform')
      }
    }
  })

  return (
    <article className="job" ref={root} data-slot="job" aria-label={`${sentenceCase(job.display_title)}, ${employer}`}>
      {/* The background: a 3D column, grey like the chart's other counties and orange like its selected one when
          the card is hovered or focused. */}
      <span className="column" aria-hidden="true" data-slot="column">
        <ColumnLook lit={false} />
        <ColumnLook lit />
      </span>
      <div className="job-head">
        <span className="tile" aria-hidden="true" data-slot="tile" />
        <div className="titles">
          <p className="employer truncate" title={employer}>{employer}</p>
          <p className="soft truncate">{subtitle(job)}</p>
        </div>
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
