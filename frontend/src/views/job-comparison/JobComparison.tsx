// show_job_comparison: 2 or 3 jobs side by side in a table, a column per job and a row per aspect. Each cell shows
// HZZ's own words (or why the value is unknown) and, for a condition the user stated, a verdict chip; the user's
// condition is named once, in the row's heading. Rows whose values differ are marked, the others are quieter. In a
// narrow frame the table scrolls sideways under its sticky aspect column. Animated like the job cards: the columns'
// headings rise in one after another, then the rows.

import type { CSSProperties } from 'react'
import { Card, ExpandButton, Notes } from '../../shared/Card'
import { useComparisonEntrance } from '../../shared/use-comparison-entrance'
import { capitalise, FEED_CATEGORY, sentenceCase, titleCase } from '../../shared/text'
import type { ComparedJob, ComparisonCell, ComparisonRow, JobComparisonData } from './types'

const ROW_STAGGER = 60
const VERDICT_COLORS = {
  match: 'bg-green-tint text-green-on-tint',
  no_match: 'bg-warning-bg text-warning-fg',
  unknown: 'bg-surface-subdued text-fg-soft',
}

const OPEN_ICON = ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5']

/** "Rovinj-Rovigno · Istarska županija": the town of work and the county, each when known. */
function where(job: ComparedJob): string | null {
  const known = !/mjesto rada nije navedeno/i.test(job.display_location)
  const first = known ? job.display_location.split(',')[0].trim() : ''
  const town = first === first.toUpperCase() ? titleCase(first) : first
  const parts = [town, job.county_name].filter((part): part is string => Boolean(part))
  return parts.length ? [...new Set(parts)].join(' · ') : null
}

export function JobComparison({ data, expanded, toggle, onOpenLink }: {
  data: JobComparisonData | null
  expanded: boolean
  toggle: () => void
  onOpenLink: (url: string) => void
}) {
  if (!data) return <Card sunken title="Usporedba oglasa" description="Učitavanje…" />
  return (
    <Card sunken title={data.title} description={data.description} actions={(
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži usporedbu preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      <ComparisonTable data={data} onOpenLink={onOpenLink} expanded={expanded} />
      <Notes warning={null} note={[data.unknown_note, data.disclaimer]} />
    </Card>
  )
}

/** Mounted once the data is there, so its entrance plays with the data. */
function ComparisonTable({ data, onOpenLink, expanded }: { data: JobComparisonData; onOpenLink: (url: string) => void; expanded: boolean }) {
  const root = useComparisonEntrance('job', ROW_STAGGER)

  return (
    <div className={`compare-scroll [--aspect:132px] [--column:168px] @container overflow-x-auto [overscroll-behavior-x:contain]
      max-w-full rounded-[12px]
      [background:linear-gradient(to_left,_var(--card)_40%,_transparent)_right_/_32px_100%_no-repeat_local,_radial-gradient(farthest-side_at_100%_50%,_rgb(0_0_0_/_0.14),_transparent)_right_/_14px_100%_no-repeat_scroll]
      [&:focus-visible]:[outline:none] [&:focus-visible]:shadow-focus [&.expanded]:[--aspect:168px]
      [&.expanded]:[--column:240px] ${expanded ? ' expanded' : ''}`} ref={root} role="region" tabIndex={0}
      aria-label="Usporedba oglasa po uvjetima">
      <table className="compare [@container(max-width:_520px)]:[--aspect:100px] [@container(max-width:_520px)]:[--column:128px]
        hyphens-auto [overflow-wrap:break-word] w-full
        [min-width:calc(var(--aspect)_+_var(--jobs)_*_var(--column))] table-fixed border-separate
        border-spacing-0 text-[13px] leading-[1.35] text-fg-loud [&_th]:p-3 [&_th]:text-left [&_th]:align-top
        [&_th]:[font-weight:inherit] [&_td]:p-3 [&_td]:text-left [&_td]:align-top [&_td]:[font-weight:inherit]
        [&_.corner]:[width:var(--aspect)] [&_.aspect]:[width:var(--aspect)] [&_.corner]:sticky [&_.corner]:left-0
        [&_.corner]:[z-index:1] [&_.corner]:bg-card [&_.corner]:[box-shadow:inset_-1px_0_0_var(--border)]
        [&_.aspect]:sticky [&_.aspect]:left-0 [&_.aspect]:[z-index:1] [&_.aspect]:bg-card
        [&_.aspect]:[box-shadow:inset_-1px_0_0_var(--border)] [&_tbody_th]:[border-top:1px_solid_var(--border)]
        [&_tbody_td]:[border-top:1px_solid_var(--border)] [&_tr.same_.cell-text]:text-fg-soft" style={{ '--jobs': data.jobs.length } as CSSProperties}>
        <thead>
          <tr>
            <td className="corner" />
            {data.jobs.map((job) => <JobHead key={job.id} job={job} onOpenLink={onOpenLink} />)}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={row.aspect} className={row.differs ? 'differs' : 'same'}>
              <RowHead row={row} index={i} />
              {row.cells.map((cell, j) => (
                <Cell key={cell.job_id} row={row} cell={cell} job={data.jobs[j]} index={i} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function JobHead({ job, onOpenLink }: { job: ComparedJob; onOpenLink: (url: string) => void }) {
  const title = sentenceCase(job.display_title)
  // Employers in capitals, as on the cards; the placeholder is not a name and stays as it is.
  const employer = job.employer_name?.toLocaleUpperCase('hr-HR') ?? 'Poslodavac nije naveden'
  const place = where(job)
  return (
    <th scope="col" className="job-head [&_.label]:min-w-0 [&_.label]:[padding:3px_7px] [&_.label]:rounded-[6px] [&_.label]:text-[11px]
      [&_.label]:font-medium [&_.label]:leading-[1.25] [&_.label]:bg-surface-subdued [&_.label]:text-fg-loud
      [&_.label.feed]:bg-card [&_.label.feed]:[outline:1px_dashed_var(--fg-soft)]
      [&_.label.feed]:[outline-offset:-1px] [&_.label.feed]:cursor-help">
      <div className="job-head-inner flex flex-col gap-1 min-w-0" data-slot="job">
        <div className="job-head-top flex items-start justify-between gap-1.5 [min-height:28px] mb-1 [&_.icon-button]:w-7
          [&_.icon-button]:h-7 [&_.icon-button]:rounded-[8px] [&_.icon-button_svg]:w-3.5
          [&_.icon-button_svg]:h-3.5">
          {job.category ? (
            <span className={`label ${job.category_source === 'feed' ? ' feed' : ''}`}
              title={job.category_source === 'feed' ? FEED_CATEGORY : undefined}>
              {sentenceCase(job.category)}
            </span>
          ) : <span />}
          <button className="icon-button grid place-items-center flex-none w-9 h-9 p-0 rounded-[10px] border border-border bg-card
            text-fg-loud cursor-pointer [&:hover]:bg-surface-subdued [&:focus-visible]:[outline:none]
            [&:focus-visible]:shadow-focus [&_svg]:w-4.5 [&_svg]:h-4.5" type="button" title="Otvori oglas na HZZ-u"
            aria-label={`Otvori oglas ${title} na HZZ-u`} onClick={() => onOpenLink(job.canonical_url)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
              strokeLinejoin="round" aria-hidden="true">
              {OPEN_ICON.map((d) => <path key={d} d={d} />)}
            </svg>
          </button>
        </div>
        {/* "Kuhar/kuharica" may break after the slash in a narrow column. */}
        <span className="job-name text-[15px] font-bold leading-[1.25]">{title.replaceAll('/', '/​')}</span>
        <span className="job-employer text-[12px] font-medium">{employer}</span>
        {place && <span className="job-where text-[12px] text-fg-soft">{place}</span>}
      </div>
    </th>
  )
}

function RowHead({ row, index }: { row: ComparisonRow; index: number }) {
  return (
    <th scope="row" className="aspect">
      <div className="aspect-inner flex flex-col gap-1 min-w-0" data-row={index}>
        <span className="aspect-name font-semibold">{row.name}</span>
        {row.condition_label && <span className="aspect-you text-[12px] text-fg-soft">vi: {row.condition_label}</span>}
        {row.differs && <span className="aspect-differs inline-flex items-center [gap:5px] text-[11px] font-medium text-fg-soft
          whitespace-nowrap [&::before]:[content:''] [&::before]:flex-none [&::before]:w-1.5 [&::before]:h-1.5
          [&::before]:rounded-full [&::before]:bg-orange-500">razlikuje se</span>}
      </div>
    </th>
  )
}

function Cell({ row, cell, job, index }: { row: ComparisonRow; cell: ComparisonCell; job: ComparedJob; index: number }) {
  const expired = row.aspect === 'deadline' && job.deadline_passed
  return (
    <td className={`cell [&.unknown_.cell-text]:text-fg-soft [&.unknown_.cell-text]:italic
      [&.expired_.cell-text]:text-warning-fg [&.expired_.cell-text]:font-medium ${expired ? ' expired' : ''}${cell.unknown_reason && !cell.note ? ' unknown' : ''}`}>
      <div className="cell-inner flex flex-col items-start gap-1.5 min-w-0" data-row={index}>
        {cell.verdict && <span className={`verdict [padding:2px_8px] rounded-full text-[11px] font-semibold
          leading-[1.4] whitespace-nowrap ${cell.verdict} ${VERDICT_COLORS[cell.verdict]}`}>{cell.verdict_label}</span>}
        <span className="cell-text">{capitalise(cell.text)}</span>
        {cell.note && <span className="cell-note text-[12px] text-fg-soft">{capitalise(cell.note)}</span>}
      </div>
    </td>
  )
}
