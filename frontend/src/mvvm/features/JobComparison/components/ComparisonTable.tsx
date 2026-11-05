import { cn } from 'cn'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ExternalLinkIcon } from 'lucide-react'
import type { CSSProperties } from 'react'
import { useComparisonEntrance } from '../../../hooks/use-comparison-entrance'
import { capitalise, FEED_CATEGORY, sentenceCase, titleCase } from '../../../utils/text'
import type { ComparedJob, ComparisonCell, ComparisonRow, JobComparisonData } from '../types'

const ROW_STAGGER = 60
/** "Rovinj-Rovigno · Istarska županija": the town of work and the county, each when known. */
function where(job: ComparedJob): string | null {
  const known = !/mjesto rada nije navedeno/i.test(job.display_location)
  const first = known ? job.display_location.split(',')[0].trim() : ''
  const town = first === first.toUpperCase() ? titleCase(first) : first
  const parts = [town, job.county_name].filter((part): part is string => Boolean(part))
  return parts.length ? [...new Set(parts)].join(' · ') : null
}

/** Mounted once the data is there, so its entrance plays with the data. */
export function ComparisonTable({ data, onOpenLink, expanded }: { data: JobComparisonData; onOpenLink: (url: string) => void; expanded: boolean }) {
  const root = useComparisonEntrance('job', ROW_STAGGER)

  return (
    <div className={`compare-scroll [--aspect:132px] [--column:168px] @container overflow-x-auto [overscroll-behavior-x:contain]
      max-w-full rounded-[12px]
      [background:linear-gradient(to_left,_var(--card)_40%,_transparent)_right_/_32px_100%_no-repeat_local,_radial-gradient(farthest-side_at_100%_50%,_rgb(0_0_0_/_0.14),_transparent)_right_/_14px_100%_no-repeat_scroll]
      [&:focus-visible]:[outline:none] [&:focus-visible]:shadow-focus [&.expanded]:[--aspect:168px]
      [&.expanded]:[--column:240px] ${expanded ? ' expanded' : ''}`} ref={root} role="region" tabIndex={0}
      aria-label="Usporedba oglasa po uvjetima">
      <Table variant="comparison" containerClassName="contents" className="compare [@container(max-width:_520px)]:[--aspect:100px] [@container(max-width:_520px)]:[--column:128px]
        hyphens-auto [overflow-wrap:break-word] w-full
        [min-width:calc(var(--aspect)_+_var(--jobs)_*_var(--column))] table-fixed border-separate
        border-spacing-0 [&_th]:p-3 [&_th]:text-left [&_th]:align-top [&_td]:p-3 [&_td]:text-left
        [&_td]:align-top [&_tbody_th]:[border-top:1px_solid_var(--border)]
        [&_tbody_td]:[border-top:1px_solid_var(--border)] [&_tr.same_.cell-text]:text-fg-soft" style={{ '--jobs': data.jobs.length } as CSSProperties}>
        <TableHeader>
          <TableRow>
            <TableCell sticky className="corner w-(--aspect)" />
            {data.jobs.map((job) => <JobHead key={job.id} job={job} onOpenLink={onOpenLink} />)}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.rows.map((row, i) => (
            <TableRow key={row.aspect} className={cn(row.differs ? 'differs' : 'same')}>
              <RowHead row={row} index={i} />
              {row.cells.map((cell, j) => (
                <Cell key={cell.job_id} row={row} cell={cell} job={data.jobs[j]} index={i} />
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function JobHead({ job, onOpenLink }: { job: ComparedJob; onOpenLink: (url: string) => void }) {
  const title = sentenceCase(job.display_title)
  // Employers in capitals, as on the cards; the placeholder is not a name and stays as it is.
  const employer = job.employer_name?.toLocaleUpperCase('hr-HR') ?? 'Poslodavac nije naveden'
  const place = where(job)
  return (
    <TableHead scope="col" className="job-head">
      <div className="job-head-inner flex min-w-0 flex-col gap-1" data-slot="job">
        <div className="job-head-top mb-1 flex min-h-7 items-start justify-between gap-1.5">
          {job.category ? (
            <Badge className="label min-w-0 shrink" variant={job.category_source === 'feed' ? 'provisional' : 'secondary'}
              title={job.category_source === 'feed' ? FEED_CATEGORY : undefined}>
              <span className="truncate">{sentenceCase(job.category)}</span>
            </Badge>
          ) : <span />}
          <Button className="icon-button" variant="outline" size="icon-sm" type="button" title="Otvori oglas na HZZ-u"
            aria-label={`Otvori oglas ${title} na HZZ-u`} onClick={() => onOpenLink(job.canonical_url)}>
            <ExternalLinkIcon data-icon="inline-start" aria-hidden="true" />
          </Button>
        </div>
        {/* "Kuhar/kuharica" may break after the slash in a narrow column. */}
        <span className="job-name text-[14px] font-semibold leading-[1.25]">{title.replaceAll('/', '/​')}</span>
        <span className="job-employer text-[12px] font-medium">{employer}</span>
        {place && <span className="job-where text-[12px] text-fg-soft">{place}</span>}
      </div>
    </TableHead>
  )
}

function RowHead({ row, index }: { row: ComparisonRow; index: number }) {
  return (
    <TableHead scope="row" sticky="column" className="aspect w-(--aspect)">
      <div className="aspect-inner flex flex-col gap-1 min-w-0" data-row={index}>
        <span className="aspect-name font-semibold">{row.name}</span>
        {row.condition_label && <span className="aspect-you text-[12px] text-fg-soft">vi: {row.condition_label}</span>}
        {row.differs && <span className="aspect-differs inline-flex items-center [gap:5px] text-[12px] font-medium text-fg-soft
          whitespace-nowrap [&::before]:[content:''] [&::before]:flex-none [&::before]:w-1.5 [&::before]:h-1.5
          [&::before]:rounded-full [&::before]:bg-orange-500">razlikuje se</span>}
      </div>
    </TableHead>
  )
}

function Cell({ row, cell, job, index }: { row: ComparisonRow; cell: ComparisonCell; job: ComparedJob; index: number }) {
  const expired = row.aspect === 'deadline' && job.deadline_passed
  return (
    <TableCell className={`cell [&.unknown_.cell-text]:text-fg-soft [&.unknown_.cell-text]:italic
      [&.expired_.cell-text]:text-warning-fg [&.expired_.cell-text]:font-medium ${expired ? ' expired' : ''}${cell.unknown_reason && !cell.note ? ' unknown' : ''}`}>
      <div className="cell-inner flex flex-col items-start gap-1.5 min-w-0" data-row={index}>
        {cell.verdict && <Badge className={cn('verdict', cell.verdict)} variant={cell.verdict === 'match' ? 'success' : cell.verdict === 'no_match' ? 'warning' : 'secondary'}>{cell.verdict_label}</Badge>}
        <span className="cell-text">{capitalise(cell.text)}</span>
        {cell.note && <span className="cell-note text-[12px] text-fg-soft">{capitalise(cell.note)}</span>}
      </div>
    </TableCell>
  )
}
