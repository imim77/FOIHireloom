// One job on a tile of the Performance chart, laid out after the reference job row (without the company logo): labels
// for how long ago it was published and its category, the title, the employer in capitals over a slash and its
// county, then under a rule the details in three columns, each with its icon. Animated with anime.js like the
// Performance chart: the tile rises in after the ones before it, its labels come in, its rule draws across like the
// chart's grid lines and the details come in one after another.

import { animate, stagger, utils } from 'animejs'
import { useId, useRef } from 'react'
import { ExternalLinkIcon, MessageCircleIcon, type LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card as SurfaceCard, CardContent, CardHeader } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldLabel } from '@/components/ui/field'
import { Separator } from '@/components/ui/separator'
import { fadeIn, finish, releaseStyles, useChartEntrance } from '../../../hooks/chart-motion'
import { FEED_CATEGORY, sentenceCase } from '../../../utils/text'
import { age, type DetailKind, details } from '../utils/job-format'
import type { JobCard } from '../types'

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

// Picking the card for a comparison; null when the host takes no messages from the view.
export interface CardCompare {
  checked: boolean
  // Already as many cards picked as a comparison takes.
  disabled: boolean
  onChange: () => void
}

// 24px outline icons, one per kind of detail.
const DETAIL_ICONS: Record<DetailKind, string[]> = {
  place: ['M12 21s-7-6.1-7-11.5a7 7 0 0 1 14 0C19 14.9 12 21 12 21Z', 'M12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z'],
  hours: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z', 'M12 7v5l3 2'],
  deadline: ['M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z', 'M4 10h16', 'M8 3v4', 'M16 3v4'],
  contract: ['M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z', 'M14 3v5h5', 'M9 13h6', 'M9 17h4'],
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
function Action({ label, icon: IconComponent, onClick }: { label: string; icon: LucideIcon; onClick: () => void }) {
  return (
    <Button className="icon-button" variant="outline" size="icon" type="button" title={label} aria-label={label} onClick={(event) => {
      finish(animate(event.currentTarget.firstElementChild!, { scale: [0.7, 1], duration: 500, ease: 'outBack(2.4)',
        onComplete: releaseStyles('transform') }))
      onClick()
    }}>
      <IconComponent data-icon="inline-start" aria-hidden="true" />
    </Button>
  )
}

/** order is the card's place among the cards that came in together, which delays its entrance. */
export function JobCardView({ job, today, order, actions, compare }: {
  job: JobCard
  today: string
  order: number
  actions: CardActions
  compare: CardCompare | null
}) {
  const published = age(job, today)
  const items = details(job)
  // Employers are written in capitals, as HZZ writes most of them; the placeholder is not a name and stays as it is.
  const employer = job.employer_name?.toLocaleUpperCase('hr-HR') ?? 'Poslodavac nije naveden'
  const title = sentenceCase(job.display_title)
  const root = useRef<HTMLDivElement>(null)
  const compareId = useId()

  useChartEntrance(root, (timeline) => {
    const card = root.current!
    const at = order * CARD_STAGGER
    timeline.add(card, { ...fadeIn([card], 10), duration: 800, ease: 'outExpo' }, at)
    const all = (selector: string) => [...card.querySelectorAll<HTMLElement>(selector)]
    const labels = all('[data-slot="label"]')
    if (labels.length) timeline.add(labels, { ...fadeIn(labels, 4), duration: 500, delay: stagger(60) }, at + LABELS_AT)
    const rules = all('[data-slot="rule"]')
    utils.set(rules, { scaleX: 0 })
    timeline.add(rules, { scaleX: [0, 1], duration: 900, ease: 'outQuad', onComplete: releaseStyles('transform') },
      at + RULES_AT)
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
    <SurfaceCard className="job @container min-w-0" role="article" ref={root} data-slot="job" data-id={job.id} aria-label={`${title}, ${employer}`}>
      <CardHeader className="job-top flex min-w-0 flex-row flex-wrap items-center gap-2">
        <ul className="labels flex basis-full flex-1 flex-wrap gap-1.5 min-w-0 m-0 p-0 [list-style:none]" aria-label="Oznake">
          {published && <li data-slot="label" className="min-w-0 max-w-full"><Badge className="label age" variant="success">{published}</Badge></li>}
          {job.category && (
            <li data-slot="label" className="min-w-0 max-w-full"><Badge variant={job.category_source === 'feed' ? 'provisional' : 'secondary'} className="label max-w-full" title={job.category_source === 'feed' ? FEED_CATEGORY : undefined}>
              <span className="truncate">{sentenceCase(job.category)}</span>
            </Badge></li>
          )}
        </ul>
        {compare && (
          <Field orientation="horizontal" className="compare-toggle w-auto shrink-0" data-disabled={compare.disabled}
            title={compare.disabled ? 'Usporediti se mogu najviše 3 oglasa' : undefined}>
            <Checkbox id={compareId} checked={compare.checked} disabled={compare.disabled}
              onCheckedChange={compare.onChange} aria-label={`Usporedi oglas ${title}`} />
            <FieldLabel htmlFor={compareId} aria-hidden="true">Usporedi</FieldLabel>
          </Field>
        )}
        <Action label="Otvori oglas na HZZ-u" icon={ExternalLinkIcon} onClick={() => actions.open(job)} />
        {actions.ask && <Action label="Pitaj o ovom oglasu" icon={MessageCircleIcon} onClick={() => actions.ask?.(job)} />}
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-3">
        <div className="job-heading flex flex-col gap-1 min-w-0">
          <h2 className="job-title m-0 text-[18px] font-bold leading-[1.25] [overflow-wrap:anywhere]">{title}</h2>
          <p className="employer-line m-0 text-[13px] font-medium leading-[1.35] text-fg-loud [overflow-wrap:anywhere] [&_.where]:text-fg-soft">
            <span className="employer" title={employer}>{employer}</span>
            {job.county_name && <> / <span className="where">{job.county_name}</span></>}
          </p>
        </div>
        {items.length > 0 && <Separator className="rule origin-left" aria-hidden="true" data-slot="rule" />}
        {items.length > 0 && (
          <ul className="details grid [grid-template-columns:repeat(3,_minmax(0,_1fr))] [gap:8px_16px] m-0 p-0 [list-style:none]
            [@container(max-width:_520px)]:[grid-template-columns:repeat(2,_minmax(0,_1fr))]" aria-label="Uvjeti">
            {items.map((item) => (
              <li key={item.kind} className={`detail flex items-center gap-2 min-w-0 text-[13px] leading-[1.3] text-fg-loud [&_svg]:flex-none
                [&_svg]:w-4 [&_svg]:h-4 [&_svg]:text-fg-soft [&_span]:min-w-0 [&_span]:overflow-hidden
                [&_span]:whitespace-nowrap [&_span]:text-ellipsis ${item.kind}`} data-slot="detail">
                <Icon paths={DETAIL_ICONS[item.kind]} />
                <span>{item.text}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </SurfaceCard>
  )
}
