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
import './county-comparison.css'

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
    <dl className="moments">
      <div className="moment">
        <dt>HZZ oglasi provjereni</dt>
        <dd className="moment-value">{data.hzz_coverage.data_as_of ? formatMoment(data.hzz_coverage.data_as_of)
          : 'nije poznato'}</dd>
        <dd className="soft">posljednja uspješna provjera svih uspoređenih županija</dd>
      </div>
      <div className="moment">
        <dt>DZS referentni mjesec</dt>
        <dd className="moment-value">
          {!months.length ? 'nije dostupan' : months.length === 1 ? formatMonth(months[0])
            : periods.map((reference) => `${DZS_NAMES[reference.indicator]}: ${formatMonth(reference.period!)}`)
              .join(' · ')}
          {provisional && <span className="provisional">privremeno</span>}
        </dd>
        <dd className="soft">
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
    <div className={`compare-scroll${expanded ? ' expanded' : ''}`} ref={root} role="region" tabIndex={0}
      aria-label="Usporedba županija po oglasima i nezaposlenosti">
      <table className="compare" style={{ '--counties': data.counties.length } as CSSProperties}>
        <thead>
          <tr>
            <td className="corner" />
            {data.counties.map((county) => (
              <th key={county.code} scope="col" className="county-head">
                <div className="county-head-inner" data-slot="county">
                  <span className="county-name">{county.short_name}</span>
                  <span className="county-total">
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
                  <div className="section-inner" data-row={sectionRow}>
                    <span className="section-name">{section.name}</span>
                    <span className="section-hint">{section.hint}</span>
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
                      <div className="aspect-inner" data-row={rowIndex}>{row.name}</div>
                    </th>
                    {cells.map((cell, j) => (
                      <td key={data.counties[j].code} className={`cell${cell.unavailable ? ' unavailable' : ''}`}>
                        <div className="cell-inner" data-row={rowIndex}>
                          <span className="cell-text">
                            {cell.text}
                            {marked && cell.value === high && <span className="extreme">najviše</span>}
                            {marked && cell.value === low && <span className="extreme">najmanje</span>}
                          </span>
                          {(cell.note || cell.provisional) && (
                            <span className="cell-note">
                              {cell.note}
                              {cell.provisional && <span className="provisional">privremeno</span>}
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
