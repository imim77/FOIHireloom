// show_county_comparison: 2 to 6 counties side by side in a table, a column per county and three groups of rows: the
// HZZ ads matching the filters, the DZS values with their reference months, and the two indicators, which describe
// each county as a whole and sit apart on a grey band. An unavailable value says why, never 0 or ∞. Over the table the
// filters (removable when the host lets the view call tools) and the two moments the data refers to; under it the
// coverage warning, the sources and the notes. In a narrow frame the table scrolls sideways under its sticky row names.
// Animated like the job comparison: the counties' headings rise in one after another, then the rows.

import type { App } from '@modelcontextprotocol/ext-apps'
import { type CSSProperties, useState } from 'react'
import { Card, ExpandButton, Notes, Warning } from '../../shared/Card'
import { useComparisonEntrance } from '../../shared/use-comparison-entrance'
import { formatDay, formatInteger, formatMoment, formatMonth } from '../../shared/format'
import { useExpanded, useMcpApp } from '../../shared/mcp'
import { Sources } from '../../shared/Sources'
import type { ActiveFilter } from '../../shared/types'
import { FilterChips } from '../../shared/FilterChips'
import { useServerTool } from '../../shared/use-server-tool'
import { FIRST_ROWS, noHzz, SECTIONS } from './county-rows'
import { sample } from './sample'
import type { CountyComparisonData, CountyFilters, DzsIndicator } from './types'

const ROW_STAGGER = 45

const DZS_NAMES: Record<DzsIndicator, string> = {
  unemployed: 'nezaposleni',
  active_population: 'aktivno stanovništvo',
  unemployment_rate: 'stopa',
  employed: 'zaposleni',
}

/** The compare_counties arguments of a result without one filter: unset, or false for include_expired. */
function argumentsWithout(data: CountyComparisonData, argument: string) {
  const filters: CountyFilters = { ...data.filters, [argument]: argument === 'include_expired' ? false : null }
  return {
    counties: data.counties.map((county) => county.code),
    ...filters,
    ...(data.requested_period ? { period: data.requested_period.slice(0, 7) } : {}),
  }
}

export function CountyComparison() {
  const mcp = useMcpApp<CountyComparisonData>('FOIHireloom county comparison', sample)
  const { expanded, toggle } = useExpanded(mcp)
  if (!mcp.data) return <Card sunken title="Usporedba županija" description="Učitavanje…" />
  // A new result from the host replaces the one the view asked for.
  return <CountyComparisonContent key={mcp.revision} initial={mcp.data} app={mcp.app}
    expanded={expanded} toggle={toggle} />
}

function CountyComparisonContent({ initial, app, expanded, toggle }: {
  initial: CountyComparisonData
  app: App | null
  expanded: boolean
  toggle: () => void
}) {
  const [data, setData] = useState(initial)
  const { call, loading, error } = useServerTool<CountyComparisonData>(app, 'show_county_comparison',
    'Usporedba se nije mogla učitati.')
  const tools = Boolean(app?.getHostCapabilities()?.serverTools)

  async function removeFilter(filter: ActiveFilter) {
    const next = await call(argumentsWithout(data, filter.argument))
    if (next) setData(next)
  }

  return (
    <Card sunken title={data.title} description={data.description} actions={(
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži usporedbu preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      <FilterChips filters={data.active_filters} label="Filtri oglasa" disabled={loading}
        onRemove={tools ? removeFilter : undefined} />
      <Warning text={error} />
      <Moments data={data} />
      <ComparisonTable data={data} expanded={expanded} />
      <Notes warning={data.coverage_note} note={[data.disclaimer, ...data.view_notes]} />
      <Footer data={data} app={app} />
    </Card>
  )
}

/** When the HZZ ads were checked and which month the DZS values are for, side by side: they are different moments. */
function Moments({ data }: { data: CountyComparisonData }) {
  const periods = data.dzs_periods.filter((reference) => reference.period !== null)
  const months = [...new Set(periods.map((reference) => reference.period!))]
  const provisional = data.counties.some((county) => [county.unemployed, county.active_population,
    county.unemployment_rate].some((value) => value.is_provisional))
  return (
    <dl className="moments grid [grid-template-columns:repeat(auto-fit,_minmax(180px,_1fr))] gap-2 m-0">
      <div className="moment flex flex-col gap-1 min-w-0 [padding:10px_12px] rounded-[12px] bg-surface-sunken
        [&_dt]:text-[12px] [&_dt]:font-medium [&_dt]:text-fg-soft [&_dd]:m-0 [&_.soft]:font-normal
        [&_.soft]:leading-[1.35]">
        <dt>HZZ oglasi provjereni</dt>
        <dd className="moment-value flex flex-wrap items-center gap-1.5 text-[14px] font-semibold leading-[1.3] tabular-nums">{data.hzz_coverage.data_as_of ? formatMoment(data.hzz_coverage.data_as_of)
          : 'nije poznato'}</dd>
        <dd className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">posljednja uspješna provjera svih uspoređenih županija</dd>
      </div>
      <div className="moment flex flex-col gap-1 min-w-0 [padding:10px_12px] rounded-[12px] bg-surface-sunken
        [&_dt]:text-[12px] [&_dt]:font-medium [&_dt]:text-fg-soft [&_dd]:m-0 [&_.soft]:font-normal
        [&_.soft]:leading-[1.35]">
        <dt>DZS referentni mjesec</dt>
        <dd className="moment-value flex flex-wrap items-center gap-1.5 text-[14px] font-semibold leading-[1.3] tabular-nums">
          {!months.length ? 'nije dostupan' : months.length === 1 ? formatMonth(months[0])
            : periods.map((reference) => `${DZS_NAMES[reference.indicator]}: ${formatMonth(reference.period!)}`)
              .join(' · ')}
          {provisional && <span className="provisional inline-block [padding:1px_6px] rounded-full text-[11px] font-medium leading-[1.4]
            whitespace-nowrap text-fg-soft [outline:1px_dashed_var(--fg-soft)] [outline-offset:-1px]">privremeno</span>}
        </dd>
        <dd className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">
          {data.requested_period ? 'zadani mjesec' : 'posljednji mjesec s podatkom za sve uspoređene županije'}
        </dd>
      </div>
    </dl>
  )
}

/** Mounted once the data is there, so its entrance plays with the data. */
function ComparisonTable({ data, expanded }: { data: CountyComparisonData; expanded: boolean }) {
  const root = useComparisonEntrance('county', ROW_STAGGER)

  return (
    <div className={`compare-scroll [--aspect:160px] [--column:144px] @container overflow-x-auto [overscroll-behavior-x:contain]
      max-w-full rounded-[12px]
      [background:linear-gradient(to_left,_var(--card)_40%,_transparent)_right_/_32px_100%_no-repeat_local,_radial-gradient(farthest-side_at_100%_50%,_rgb(0_0_0_/_0.14),_transparent)_right_/_14px_100%_no-repeat_scroll]
      [&:focus-visible]:[outline:none] [&:focus-visible]:shadow-focus [&.expanded]:[--aspect:200px]
      [&.expanded]:[--column:200px] ${expanded ? ' expanded' : ''}`} ref={root} role="region" tabIndex={0}
      aria-label="Usporedba županija po oglasima i nezaposlenosti">
      <table className="compare [@container(max-width:_520px)]:[--aspect:108px] [@container(max-width:_520px)]:[--column:120px]
        hyphens-auto [overflow-wrap:break-word] w-full
        [min-width:calc(var(--aspect)_+_var(--counties)_*_var(--column))] table-fixed border-separate
        border-spacing-0 text-[13px] leading-[1.35] text-fg-loud [&_th]:[padding:10px_12px] [&_th]:text-left
        [&_th]:align-top [&_th]:[font-weight:inherit] [&_td]:[padding:10px_12px] [&_td]:text-left
        [&_td]:align-top [&_td]:[font-weight:inherit] [&_.corner]:[width:var(--aspect)]
        [&_.aspect]:[width:var(--aspect)] [&_.corner]:sticky [&_.corner]:left-0 [&_.corner]:[z-index:1]
        [&_.corner]:bg-card [&_.corner]:[box-shadow:inset_-1px_0_0_var(--border)] [&_.aspect]:sticky
        [&_.aspect]:left-0 [&_.aspect]:[z-index:1] [&_.aspect]:bg-card
        [&_.aspect]:[box-shadow:inset_-1px_0_0_var(--border)]
        [&_tbody_tr:not(.section)_>_*]:[border-top:1px_solid_var(--border)]
        [&_.section_>_th]:[padding:18px_0_8px] [&_tbody.indicators_tr:not(.section)_>_*]:bg-surface-sunken
        [&_tbody.indicators_tr:not(.section)_>_*]:[border-top-color:var(--card)]
        [&_tbody.indicators_.section-name]:text-orange-500" style={{ '--counties': data.counties.length } as CSSProperties}>
        <thead>
          <tr>
            <td className="corner" />
            {data.counties.map((county) => (
              <th key={county.code} scope="col" className="county-head">
                <div className="county-head-inner flex flex-col gap-0.5 min-w-0" data-slot="county">
                  <span className="county-name text-[15px] font-bold leading-[1.25]">{county.short_name}</span>
                  <span className="county-total text-[12px] text-fg-soft">
                    {noHzz(county) ? 'HZZ oglasi nisu učitani'
                      : `svih aktivnih oglasa: ${formatInteger(county.all_active_jobs.jobs)}`}
                  </span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        {SECTIONS.map((section, k) => {
          const sectionRow = FIRST_ROWS[k]
          return (
            <tbody key={section.key} className={section.key}>
              <tr className="section">
                <th scope="colgroup" colSpan={data.counties.length + 1}>
                  <div className="section-inner sticky left-0 flex flex-wrap items-baseline [gap:2px_8px] [width:max-content]
                    [max-width:min(100cqw,_100%)] [padding:0_12px]" data-row={sectionRow}>
                    <span className="section-name text-[12px] font-bold [letter-spacing:0.02em] uppercase">{section.name}</span>
                    <span className="section-hint text-[12px] text-fg-soft">{section.hint}</span>
                  </div>
                </th>
              </tr>
              {section.rows.map((row, r) => {
                const rowIndex = sectionRow + 1 + r
                const cells = data.counties.map((county) => row.cell(county, data))
                const known = cells.flatMap((cell) => cell.value ?? [])
                const high = Math.max(...known)
                const low = Math.min(...known)
                const marked = row.extremes && known.length > 1 && high !== low
                return (
                  <tr key={row.key}>
                    <th scope="row" className="aspect">
                      <div className="aspect-inner font-semibold min-w-0" data-row={rowIndex}>{row.name}</div>
                    </th>
                    {cells.map((cell, j) => (
                      <td key={data.counties[j].code} className={`cell [&.unavailable_.cell-text]:text-[13px] [&.unavailable_.cell-text]:font-medium
                        [&.unavailable_.cell-text]:italic [&.unavailable_.cell-text]:text-fg-soft
                        [&.unavailable_.cell-note]:text-warning-fg ${cell.unavailable ? ' unavailable' : ''}`}>
                        <div className="cell-inner flex flex-col items-start gap-1 min-w-0" data-row={rowIndex}>
                          <span className="cell-text flex flex-wrap items-center [gap:4px_6px] text-[14px] font-semibold tabular-nums">
                            {cell.text}
                            {marked && cell.value === high && <span className="extreme inline-flex items-center gap-1 text-[11px] font-medium not-italic
                              text-fg-soft whitespace-nowrap [&::before]:[content:''] [&::before]:flex-none
                              [&::before]:w-1.5 [&::before]:h-1.5 [&::before]:rounded-full
                              [&::before]:bg-orange-500">najviše</span>}
                            {marked && cell.value === low && <span className="extreme inline-flex items-center gap-1 text-[11px] font-medium not-italic
                              text-fg-soft whitespace-nowrap [&::before]:[content:''] [&::before]:flex-none
                              [&::before]:w-1.5 [&::before]:h-1.5 [&::before]:rounded-full
                              [&::before]:bg-orange-500">najmanje</span>}
                          </span>
                          {(cell.note || cell.provisional) && (
                            <span className="cell-note flex flex-wrap items-center [gap:4px_6px] text-[12px] text-fg-soft tabular-nums hyphens-manual">
                              {cell.note}
                              {cell.provisional && <span className="provisional inline-block [padding:1px_6px] rounded-full text-[11px] font-medium
                                leading-[1.4] whitespace-nowrap text-fg-soft [outline:1px_dashed_var(--fg-soft)]
                                [outline-offset:-1px]">privremeno</span>}
                            </span>
                          )}
                        </div>
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          )
        })}
      </table>
    </div>
  )
}

function Footer({ data, app }: { data: CountyComparisonData; app: App | null }) {
  return (
    <Sources app={app} links={data.source_links}>
      {data.dzs && <span>DZS podaci uvezeni {formatDay(data.dzs.finished_at)}</span>}
    </Sources>
  )
}
