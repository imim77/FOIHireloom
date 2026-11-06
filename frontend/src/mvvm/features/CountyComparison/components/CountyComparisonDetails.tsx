import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import type { CSSProperties, ReactNode } from 'react'
import { useComparisonEntrance } from '../../../hooks/use-comparison-entrance'
import { formatDay, formatInteger, formatMoment, formatMonth } from '../../../utils/format'
import { Sources } from '../../../components/Sources'
import { FIRST_ROWS, noHzz, SECTIONS } from '../utils/county-rows'
import type { CountyComparisonData, DzsIndicator } from '../types'

const ROW_STAGGER = 45

const DZS_NAMES: Record<DzsIndicator, string> = {
  unemployed: 'nezaposleni',
  active_population: 'aktivno stanovništvo',
  unemployment_rate: 'stopa',
  employed: 'zaposleni',
}

/** When the HZZ ads were checked and which month the DZS values are for, side by side: they are different moments. */
export function Moments({ data }: { data: CountyComparisonData }) {
  const periods = data.dzs_periods.filter((reference) => reference.period !== null)
  const months = [...new Set(periods.map((reference) => reference.period!))]
  const provisional = data.counties.some((county) => [county.unemployed, county.active_population,
    county.unemployment_rate].some((value) => value.is_provisional))
  return (
    <dl className="moments grid [grid-template-columns:repeat(auto-fit,_minmax(180px,_1fr))] gap-2 m-0">
      <Moment label="HZZ oglasi provjereni" note="posljednja uspješna provjera svih uspoređenih županija">
        {data.hzz_coverage.data_as_of ? formatMoment(data.hzz_coverage.data_as_of) : 'nije poznato'}
      </Moment>
      <Moment label="DZS referentni mjesec"
        note={data.requested_period ? 'zadani mjesec' : 'posljednji mjesec s podatkom za sve uspoređene županije'}>
        {!months.length ? 'nije dostupan' : months.length === 1 ? formatMonth(months[0])
          : periods.map((reference) => `${DZS_NAMES[reference.indicator]}: ${formatMonth(reference.period!)}`)
            .join(' · ')}
        {provisional && <Provisional />}
      </Moment>
    </dl>
  )
}

// Moment is a dense fact on a sunken tile, like Dalco's spec panels: mono label and value, a sans note under them.
function Moment({ label, note, children }: { label: string; note: string; children: ReactNode }) {
  return (
    <div className="moment flex flex-col gap-1.5 min-w-0 p-3 rounded-[10px] bg-surface-sunken">
      <dt className="mono-label uppercase text-fg-soft">{label}</dt>
      <dd className="moment-value m-0 flex flex-wrap items-center gap-1.5 font-mono text-[14px] font-medium leading-[1.3]">
        {children}
      </dd>
      <dd className="soft m-0 text-[12px] leading-[1.35] text-fg-soft">{note}</dd>
    </div>
  )
}

// Provisional marks a value DZS may still revise, in mono like the other short labels.
function Provisional() {
  return <Badge variant="provisional" className="provisional font-mono font-normal uppercase tracking-[0.04em]">
    privremeno
  </Badge>
}

// Extreme marks a row's highest or lowest value. Grey, not red: two marks share a row, and DESIGN.md allows one red
// datum per view.
function Extreme({ children }: { children: string }) {
  return <span className="extreme inline-flex items-center gap-1.5 mono-label uppercase not-italic text-fg-soft
    whitespace-nowrap [&::before]:[content:''] [&::before]:flex-none [&::before]:size-1.5 [&::before]:rounded-full
    [&::before]:bg-fg-soft">{children}</span>
}

/** Mounted once the data is there, so its entrance plays with the data. */
export function ComparisonTable({ data, expanded }: { data: CountyComparisonData; expanded: boolean }) {
  const root = useComparisonEntrance('county', ROW_STAGGER)

  return (
    <div className={`compare-scroll [--aspect:160px] [--column:144px] @container overflow-x-auto [overscroll-behavior-x:contain]
      max-w-full rounded-[10px]
      [background:linear-gradient(to_left,_var(--card)_40%,_transparent)_right_/_32px_100%_no-repeat_local,_radial-gradient(farthest-side_at_100%_50%,_rgb(0_0_0_/_0.14),_transparent)_right_/_14px_100%_no-repeat_scroll]
      [&:focus-visible]:[outline:none] [&:focus-visible]:shadow-focus [&.expanded]:[--aspect:200px]
      [&.expanded]:[--column:200px] ${expanded ? ' expanded' : ''}`} ref={root} role="region" tabIndex={0}
      aria-label="Usporedba županija po oglasima i nezaposlenosti">
      {/* Groups are set apart by space over a hairline, as Dalco divides its lists; no filled bands. */}
      <Table variant="comparison" containerClassName="contents" className="compare [@container(max-width:_520px)]:[--aspect:108px] [@container(max-width:_520px)]:[--column:120px]
        hyphens-auto [overflow-wrap:break-word] w-full
        [min-width:calc(var(--aspect)_+_var(--counties)_*_var(--column))] table-fixed border-separate
        border-spacing-0 [&_th]:[padding:10px_12px] [&_th]:text-left [&_th]:align-top [&_td]:[padding:10px_12px]
        [&_td]:text-left [&_td]:align-top [&_tbody_tr:not(.section)_>_*]:[border-top:1px_solid_var(--border)]
        [&_.section_>_th]:[padding:24px_0_8px]" style={{ '--counties': data.counties.length } as CSSProperties}>
        <TableHeader>
          <TableRow>
            <TableCell sticky className="corner w-(--aspect)" />
            {data.counties.map((county) => (
              <TableHead key={county.code} scope="col" className="county-head">
                <div className="county-head-inner flex flex-col gap-1 min-w-0" data-slot="county">
                  <span className="county-name text-[14px] font-medium leading-[1.4]">{county.short_name}</span>
                  <span className="county-total mono-label uppercase text-fg-soft hyphens-manual">
                    {noHzz(county) ? 'HZZ oglasi nisu učitani'
                      : `svih aktivnih oglasa: ${formatInteger(county.all_active_jobs.jobs)}`}
                  </span>
                </div>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        {SECTIONS.map((section, k) => {
          const sectionRow = FIRST_ROWS[k]
          return (
            <TableBody key={section.key} className={section.key}>
              <TableRow className="section">
                <TableHead scope="colgroup" colSpan={data.counties.length + 1}>
                  <div className="section-inner sticky left-0 flex flex-wrap items-baseline [gap:2px_8px] [width:max-content]
                    [max-width:min(100cqw,_100%)] [padding:0_12px]" data-row={sectionRow}>
                    <span className="section-name mono-label font-medium uppercase text-fg-loud">{section.name}</span>
                    <span className="section-hint text-[12px] font-normal text-fg-soft">{section.hint}</span>
                  </div>
                </TableHead>
              </TableRow>
              {section.rows.map((row, r) => {
                const rowIndex = sectionRow + 1 + r
                const cells = data.counties.map((county) => row.cell(county, data))
                const known = cells.flatMap((cell) => cell.value ?? [])
                const high = Math.max(...known)
                const low = Math.min(...known)
                const marked = row.extremes && known.length > 1 && high !== low
                return (
                  <TableRow key={row.key}>
                    <TableHead scope="row" sticky="column" className="aspect w-(--aspect)">
                      <div className="aspect-inner font-medium leading-[1.4] min-w-0" data-row={rowIndex}>{row.name}</div>
                    </TableHead>
                    {cells.map((cell, j) => (
                      <TableCell key={data.counties[j].code} className={`cell [&.unavailable_.cell-text]:font-sans
                        [&.unavailable_.cell-text]:text-[12px] [&.unavailable_.cell-text]:font-normal
                        [&.unavailable_.cell-text]:italic [&.unavailable_.cell-text]:text-fg-soft
                        [&.unavailable_.cell-note]:text-warning-fg ${cell.unavailable ? ' unavailable' : ''}`}>
                        <div className="cell-inner flex flex-col items-start gap-1 min-w-0" data-row={rowIndex}>
                          <span className="cell-text flex flex-wrap items-center [gap:4px_8px] font-mono text-[14px] font-medium">
                            {cell.text}
                            {marked && cell.value === high && <Extreme>najviše</Extreme>}
                            {marked && cell.value === low && <Extreme>najmanje</Extreme>}
                          </span>
                          {(cell.note || cell.provisional) && (
                            <span className="cell-note flex flex-wrap items-center [gap:4px_6px] text-[12px] text-fg-soft tabular-nums hyphens-manual">
                              {cell.note}
                              {cell.provisional && <Provisional />}
                            </span>
                          )}
                        </div>
                      </TableCell>
                    ))}
                  </TableRow>
                )
              })}
            </TableBody>
          )
        })}
      </Table>
    </div>
  )
}

export function Footer({ data, onOpenLink }: { data: CountyComparisonData; onOpenLink: (url: string) => void }) {
  return (
    <Sources onOpenLink={onOpenLink} links={data.source_links}>
      {data.dzs && <span>DZS podaci uvezeni {formatDay(data.dzs.finished_at)}</span>}
    </Sources>
  )
}
