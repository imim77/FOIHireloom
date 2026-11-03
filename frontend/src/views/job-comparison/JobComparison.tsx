// show_job_comparison: 2 or 3 jobs side by side in a table, a column per job and a row per aspect. Each cell shows
// HZZ's own words (or why the value is unknown) and, for a condition the user stated, a verdict chip; the user's
// condition is named once, in the row's heading. Rows whose values differ are marked, the others are quieter. In a
// narrow frame the table scrolls sideways under its sticky aspect column. Animated like the job cards: the columns'
// headings rise in one after another, then the rows.

import type { App } from '@modelcontextprotocol/ext-apps'
import { stagger } from 'animejs'
import { type CSSProperties, useRef } from 'react'
import { Card, ExpandButton, Notes } from '../../shared/Card'
import { fadeIn, useChartEntrance } from '../../shared/chart-motion'
import { openLink, useExpanded, useMcpApp } from '../../shared/mcp'
import { capitalise, FEED_CATEGORY, sentenceCase, titleCase } from '../../shared/text'
import { sample } from './sample'
import type { ComparedJob, ComparisonCell, ComparisonRow, JobComparisonData } from './types'
import './job-comparison.css'

const HEAD_STAGGER = 70
const ROWS_AT = 250
const ROW_STAGGER = 60

const OPEN_ICON = ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5']

/** "Rovinj-Rovigno · Istarska županija": the town of work and the county, each when known. */
function where(job: ComparedJob): string | null {
  const known = !/mjesto rada nije navedeno/i.test(job.display_location)
  const first = known ? job.display_location.split(',')[0].trim() : ''
  const town = first === first.toUpperCase() ? titleCase(first) : first
  const parts = [town, job.county_name].filter((part): part is string => Boolean(part))
  return parts.length ? [...new Set(parts)].join(' · ') : null
}

export function JobComparison() {
  const mcp = useMcpApp<JobComparisonData>('FOIHireloom job comparison', sample)
  const { expanded, toggle } = useExpanded(mcp)
  const data = mcp.data
  if (!data) return <Card sunken title="Usporedba oglasa" description="Učitavanje…" />
  return (
    <Card sunken title={data.title} description={data.description} actions={(
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži usporedbu preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      <ComparisonTable data={data} app={mcp.app} expanded={expanded} />
      <Notes warning={null} note={[data.unknown_note, data.disclaimer]} />
    </Card>
  )
}

/** Mounted once the data is there, so its entrance plays with the data. */
function ComparisonTable({ data, app, expanded }: { data: JobComparisonData; app: App | null; expanded: boolean }) {
  const root = useRef<HTMLDivElement>(null)

  useChartEntrance(root, (timeline) => {
    const all = (selector: string) => [...root.current!.querySelectorAll<HTMLElement>(selector)]
    const heads = all('[data-slot="job"]')
    timeline.add(heads, { ...fadeIn(heads, 10), duration: 800, ease: 'outExpo', delay: stagger(HEAD_STAGGER) }, 0)
    // A row's heading and cells come in together, each row after the one above.
    const cells = all('[data-row]')
    timeline.add(cells, { ...fadeIn(cells, 4), duration: 500, delay: (target?: unknown) =>
      Number((target as HTMLElement | undefined)?.dataset.row ?? 0) * ROW_STAGGER }, ROWS_AT)
    return () => {
      for (const el of [...heads, ...cells]) {
        el.style.removeProperty('opacity')
        el.style.removeProperty('transform')
      }
    }
  })

  return (
    <div className={`compare-scroll${expanded ? ' expanded' : ''}`} ref={root} role="region" tabIndex={0}
      aria-label="Usporedba oglasa po uvjetima">
      <table className="compare" style={{ '--jobs': data.jobs.length } as CSSProperties}>
        <thead>
          <tr>
            <td className="corner" />
            {data.jobs.map((job) => <JobHead key={job.id} job={job} app={app} />)}
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

function JobHead({ job, app }: { job: ComparedJob; app: App | null }) {
  const title = sentenceCase(job.display_title)
  // Employers in capitals, as on the cards; the placeholder is not a name and stays as it is.
  const employer = job.employer_name?.toLocaleUpperCase('hr-HR') ?? 'Poslodavac nije naveden'
  const place = where(job)
  return (
    <th scope="col" className="job-head">
      <div className="job-head-inner" data-slot="job">
        <div className="job-head-top">
          {job.category ? (
            <span className={`label${job.category_source === 'feed' ? ' feed' : ''}`}
              title={job.category_source === 'feed' ? FEED_CATEGORY : undefined}>
              {sentenceCase(job.category)}
            </span>
          ) : <span />}
          <button className="icon-button" type="button" title="Otvori oglas na HZZ-u"
            aria-label={`Otvori oglas ${title} na HZZ-u`} onClick={() => openLink(app, job.canonical_url)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
              strokeLinejoin="round" aria-hidden="true">
              {OPEN_ICON.map((d) => <path key={d} d={d} />)}
            </svg>
          </button>
        </div>
        {/* "Kuhar/kuharica" may break after the slash in a narrow column. */}
        <span className="job-name">{title.replaceAll('/', '/​')}</span>
        <span className="job-employer">{employer}</span>
        {place && <span className="job-where">{place}</span>}
      </div>
    </th>
  )
}

function RowHead({ row, index }: { row: ComparisonRow; index: number }) {
  return (
    <th scope="row" className="aspect">
      <div className="aspect-inner" data-row={index}>
        <span className="aspect-name">{row.name}</span>
        {row.condition_label && <span className="aspect-you">vi: {row.condition_label}</span>}
        {row.differs && <span className="aspect-differs">razlikuje se</span>}
      </div>
    </th>
  )
}

function Cell({ row, cell, job, index }: { row: ComparisonRow; cell: ComparisonCell; job: ComparedJob; index: number }) {
  const expired = row.aspect === 'deadline' && job.deadline_passed
  return (
    <td className={`cell${expired ? ' expired' : ''}${cell.unknown_reason && !cell.note ? ' unknown' : ''}`}>
      <div className="cell-inner" data-row={index}>
        {cell.verdict && <span className={`verdict ${cell.verdict}`}>{cell.verdict_label}</span>}
        <span className="cell-text">{capitalise(cell.text)}</span>
        {cell.note && <span className="cell-note">{capitalise(cell.note)}</span>}
      </div>
    </td>
  )
}
