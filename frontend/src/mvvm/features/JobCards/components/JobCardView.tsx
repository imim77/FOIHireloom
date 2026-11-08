
import { cn } from 'cn'
import { useId, useRef } from 'react'
import { MessageCircleIcon, type LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card as SurfaceCard, CardContent, CardHeader } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldLabel } from '@/components/ui/field'
import { RollLabel } from '../../../components/RollLabel'
import { clearEntrance, enter, MOTION, pop, useChartEntrance } from '../../../hooks/chart-motion'
import { FEED_CATEGORY, sentenceCase } from '../../../utils/text'
import { age, type DetailKind, details } from '../utils/job-format'
import type { JobCard } from '../types'

const LABELS_AT = 150
const DETAILS_AT = 250

export interface CardActions {
  open: (job: JobCard) => void
  ask: ((job: JobCard) => void) | null
}

export interface CardCompare {
  checked: boolean
  disabled: boolean
  onChange: () => void
}

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

const MONO_LABEL = 'font-mono text-[12px] font-normal tracking-[0.04em]'

function Icon({ paths }: { paths: string[] }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true">
      {paths.map((d) => <path key={d} d={d} />)}
    </svg>
  )
}

function Action({ label, icon: IconComponent, onClick }: { label: string; icon: LucideIcon; onClick: () => void }) {
  return (
    <Button className="icon-button" variant="outline" size="icon" type="button" title={label} aria-label={label} onClick={(event) => {
      pop(event.currentTarget.firstElementChild!)
      onClick()
    }}>
      <IconComponent data-icon="inline-start" aria-hidden="true" />
    </Button>
  )
}

function OpenAd({ onClick }: { onClick: () => void }) {
  return (
    <Button className="open-ad self-start" variant="outline" type="button" title="Otvori oglas na HZZ-u"
      aria-label="Otvori oglas na HZZ-u" onClick={(event) => {
        pop(event.currentTarget)
        onClick()
      }}>
      <RollLabel>Otvori oglas</RollLabel>
      <span aria-hidden="true">›</span>
    </Button>
  )
}

export function JobCardView({ job, today, order, actions, compare }: {
  job: JobCard
  today: string
  order: number
  actions: CardActions
  compare: CardCompare | null
}) {
  const published = age(job, today)
  const items = details(job)
  const employer = job.employer_name?.toLocaleUpperCase('hr-HR') ?? 'Poslodavac nije naveden'
  const title = sentenceCase(job.display_title)
  const root = useRef<HTMLDivElement>(null)
  const compareId = useId()

  useChartEntrance(root, (timeline) => {
    const card = root.current!
    const at = order * MOTION.readout.stagger
    enter(timeline, [card], at, MOTION.readout)
    const all = (selector: string) => [...card.querySelectorAll<HTMLElement>(selector)]
    const labels = all('[data-slot="label"]')
    enter(timeline, labels, at + LABELS_AT)
    const items = all('[data-slot="detail"]')
    enter(timeline, items, at + DETAILS_AT)
    return () => clearEntrance([card, ...labels, ...items])
  })

  return (
    <SurfaceCard className={cn('job @container min-w-0 [transition:box-shadow_300ms] motion-reduce:[transition:none]',
      compare?.checked && 'compared ring-accent-500')} role="article" ref={root} data-slot="job" data-id={job.id}
      aria-label={`${title}, ${employer}`}>
      <CardHeader className="job-top flex min-w-0 flex-row flex-wrap items-center gap-2">
        <ul className="labels flex basis-full flex-1 flex-wrap gap-1.5 min-w-0 m-0 p-0 [list-style:none]" aria-label="Oznake">
          {published && <li data-slot="label" className="min-w-0 max-w-full">
            <Badge className={cn('label age', MONO_LABEL)} variant="success">{published}</Badge>
          </li>}
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
              className="data-checked:border-accent-500 data-checked:bg-accent-500 data-checked:text-card"
              onCheckedChange={compare.onChange} aria-label={`Usporedi oglas ${title}`} />
            <FieldLabel htmlFor={compareId} aria-hidden="true" className={cn('uppercase text-fg-soft', MONO_LABEL)}>
              Usporedi
            </FieldLabel>
          </Field>
        )}
        {actions.ask && <Action label="Pitaj o ovom oglasu" icon={MessageCircleIcon} onClick={() => actions.ask?.(job)} />}
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-3">
        <div className="job-heading flex flex-col gap-1 min-w-0">
          <h2 className="job-title m-0 text-[16px] font-medium leading-[1.4] tracking-[-0.01em] [overflow-wrap:anywhere]">{title}</h2>
          <p className="employer-line m-0 text-[14px] leading-[1.5] text-fg-loud [overflow-wrap:anywhere] [&_.where]:text-fg-soft">
            <span className="employer" title={employer}>{employer}</span>
            {job.county_name && <> / <span className="where">{job.county_name}</span></>}
          </p>
        </div>
        {items.length > 0 && (
          <ul className="details grid [grid-template-columns:repeat(3,_minmax(0,_1fr))] [gap:12px_16px] m-0 p-3
            rounded-[10px] bg-surface-sunken [list-style:none]
            [@container(max-width:_520px)]:[grid-template-columns:repeat(2,_minmax(0,_1fr))]" aria-label="Uvjeti">
            {items.map((item) => (
              <li key={item.kind} className={cn('detail flex items-start gap-2 min-w-0 leading-[16px] text-fg-loud',
                '[&_svg]:flex-none [&_svg]:size-4 [&_svg]:text-fg-soft [&_span]:min-w-0 [&_span]:line-clamp-2',
                MONO_LABEL, item.kind)} data-slot="detail" title={item.text}>
                <Icon paths={DETAIL_ICONS[item.kind]} />
                <span>{item.text}</span>
              </li>
            ))}
          </ul>
        )}
        {                                                                                                       }
        <OpenAd onClick={() => actions.open(job)} />
      </CardContent>
    </SurfaceCard>
  )
}
