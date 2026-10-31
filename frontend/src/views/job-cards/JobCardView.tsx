// One job, after the reference job row (without the company logo): labels for how long ago it was published and its
// category, the title, the employer in capitals over a slash and its county, then under a rule the details in three
// columns, each with its icon, and a rule under the job. Animated with anime.js like the Performance chart: the job
// rises in after the ones before it like its tiles, its labels come in, its rules draw across like its grid lines and
// the details come in one after another.

import { animate, stagger, utils } from 'animejs'
import { useRef } from 'react'
import { fadeIn, finish, releaseStyles, useChartEntrance } from '../../shared/chart-motion'
import { age, type DetailKind, details, sentenceCase } from './job-format'
import type { JobCard } from './types'

// The Performance chart's tile entrance: each tile rises 10px over 800ms after the one before it (70ms).
const CARD_STAGGER = 70
const LABELS_AT = 150
const RULES_AT = 200
const DETAILS_AT = 350

export interface CardActions {
  // Open the advertisement on the HZZ site.
  open: (job: JobCard) => void
  // Ask about the job in the conversation; null outside a host.
  ask: ((job: JobCard) => void) | null
}

const OPEN_ICON = ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5']
const ASK_ICON = ['M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z', 'M8.5 12h.01', 'M12 12h.01', 'M15.5 12h.01']

// 24px outline icons, one per kind of detail.
const DETAIL_ICONS: Record<DetailKind, string[]> = {
  place: ['M12 21s-7-6.1-7-11.5a7 7 0 0 1 14 0C19 14.9 12 21 12 21Z', 'M12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z'],
  hours: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z', 'M12 7v5l3 2'],
  deadline: ['M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z', 'M4 10h16', 'M8 3v4', 'M16 3v4'],
  type: ['M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z', 'M8 7V5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2',
    'M3 13h18'],
  education: ['M2 9l10-5 10 5-10 5Z', 'M6 11v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5', 'M22 9v6'],
  experience: ['M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9Z'],
  workers: ['M16 19v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1', 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z',
    'M22 19v-1a4 4 0 0 0-3-3.9', 'M16 4.1a3.5 3.5 0 0 1 0 6.8'],
  accommodation: ['M3 10.5 12 3l9 7.5', 'M5 9v11h14V9', 'M10 20v-6h4v6'],
}

function Icon({ paths }: { paths: string[] }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true">
      {paths.map((d) => <path key={d} d={d} />)}
    </svg>
  )
}

/** An action at the end of the label row: its icon pops when pressed. */
function Action({ label, icon, onClick }: { label: string; icon: string[]; onClick: () => void }) {
  return (
    <button className="icon-button" type="button" title={label} aria-label={label} onClick={(event) => {
      finish(animate(event.currentTarget.firstElementChild!, { scale: [0.7, 1], duration: 500, ease: 'outBack(2.4)',
        onComplete: releaseStyles('transform') }))
      onClick()
    }}>
      <Icon paths={icon} />
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
  const published = age(job, today)
  const items = details(job)
  // Employers are written in capitals, as HZZ writes most of them; the placeholder is not a name and stays as it is.
  const employer = job.employer_name?.toLocaleUpperCase('hr-HR') ?? 'Poslodavac nije naveden'
  const title = sentenceCase(job.display_title)
  const root = useRef<HTMLElement>(null)

  useChartEntrance(root, (timeline) => {
    const card = root.current!
    const at = order * CARD_STAGGER
    timeline.add(card, { ...fadeIn([card], 10), duration: 800, ease: 'outExpo' }, at)
    const all = (selector: string) => [...card.querySelectorAll<HTMLElement>(selector)]
    const labels = all('[data-slot="label"]')
    if (labels.length) timeline.add(labels, { ...fadeIn(labels, 4), duration: 500, delay: stagger(60) }, at + LABELS_AT)
    const rules = all('[data-slot="rule"]')
    utils.set(rules, { scaleX: 0 })
    timeline.add(rules, { scaleX: [0, 1], duration: 900, ease: 'outQuad', delay: stagger(120),
      onComplete: releaseStyles('transform') }, at + RULES_AT)
    const items = all('[data-slot="detail"]')
    if (items.length) timeline.add(items, { ...fadeIn(items, 4), duration: 500, delay: stagger(40) }, at + DETAILS_AT)
    return () => {
      for (const el of [card, ...labels, ...rules, ...items]) {
        el.style.removeProperty('opacity')
        el.style.removeProperty('transform')
      }
    }
  })

  return (
    <article className="job" ref={root} data-slot="job" aria-label={`${title}, ${employer}`}>
      <div className="job-top">
        <ul className="labels" aria-label="Oznake">
          {published && <li className="label age" data-slot="label">{published}</li>}
          {job.category && <li className="label" data-slot="label">{sentenceCase(job.category)}</li>}
        </ul>
        <Action label="Otvori oglas na HZZ-u" icon={OPEN_ICON} onClick={() => actions.open(job)} />
        {actions.ask && <Action label="Pitaj o ovom oglasu" icon={ASK_ICON} onClick={() => actions.ask?.(job)} />}
      </div>
      <div className="job-heading">
        <h2 className="job-title">{title}</h2>
        <p className="employer-line">
          <span className="employer" title={employer}>{employer}</span>
          {job.county_name && <> / <span className="where">{job.county_name}</span></>}
        </p>
      </div>
      {items.length > 0 && <span className="rule" aria-hidden="true" data-slot="rule" />}
      {items.length > 0 && (
        <ul className="details" aria-label="Uvjeti">
          {items.map((item) => (
            <li key={item.kind} className={`detail ${item.kind}`} data-slot="detail">
              <Icon paths={DETAIL_ICONS[item.kind]} />
              <span>{item.text}</span>
            </li>
          ))}
        </ul>
      )}
      <span className="rule" aria-hidden="true" data-slot="rule" />
    </article>
  )
}
