// show_county_comparison: 2 to 6 counties side by side in a table, a column per county and three groups of rows: the
// HZZ ads matching the filters, the DZS values with their reference months, and the two indicators, which describe
// each county as a whole and sit apart on a grey band. An unavailable value says why, never 0 or ∞. Over the table the
// filters (removable when the host lets the view call tools) and the two moments the data refers to; under it the
// coverage warning, the sources and the notes. In a narrow frame the table scrolls sideways under its sticky row names.
// Animated like the job comparison: the counties' headings rise in one after another, then the rows.

import type { App } from '@modelcontextprotocol/ext-apps'
import { stagger } from 'animejs'
import { type CSSProperties, useRef, useState } from 'react'
import { Card, ExpandButton, Notes, Warning } from '../../shared/Card'
import { fadeIn, useChartEntrance } from '../../shared/chart-motion'
import { formatAds, formatDay, formatDecimal, formatInteger, formatMoment, formatMonth, formatRate, formatShare, plural }
  from '../../shared/format'
import { useExpanded, useMcpApp } from '../../shared/mcp'
import { Sources } from '../../shared/Sources'
import { capitalise } from '../../shared/text'
import type { ActiveFilter } from '../../shared/types'
import { sample } from './sample'
import type { ComparedCounty, CountyComparisonData, CountyFilters, DzsIndicator, DzsValue, Indicator } from './types'
import './county-comparison.css'

const HEAD_STAGGER = 70
const ROWS_AT = 250
const ROW_STAGGER = 45

const DZS_NAMES: Record<DzsIndicator, string> = {
  unemployed: 'nezaposleni',
  active_population: 'aktivno stanovništvo',
  unemployment_rate: 'stopa',
  employed: 'zaposleni',
}

// What a cell shows: its value, or why there is none, with a quieter note under it.
interface CellView {
  text: string
  note?: string | null
  unavailable?: boolean
  provisional?: boolean
  // For the highest and lowest of a row; null when unavailable.
  value?: number | null
}

interface RowView {
  key: string
  name: string
  cell: (county: ComparedCounty, data: CountyComparisonData) => CellView
  // Mark the highest and the lowest value of the row.
  extremes?: boolean
}

interface Section {
  key: 'hzz' | 'dzs' | 'indicators'
  name: string
  hint: string
  rows: RowView[]
}

// A county none of whose HZZ feeds was ever loaded: its 0 ads are not known to be 0.
const noHzz = (county: ComparedCounty) => county.hzz_last_success_at === null
const NO_HZZ: CellView = { text: 'nije poznato', note: 'HZZ oglasi za županiju nisu učitani', unavailable: true }

/** "u 9 od 10 oglasa (90,0 %)" */
function coverage(part: number, whole: number, percent: number | null): string {
  return `${formatInteger(part)} od ${formatAds(whole)}${percent === null ? '' : ` (${formatShare(percent)})`}`
}

function dzsCell(value: DzsValue, format: (value: number) => string): CellView {
  if (value.value === null) {
    return { text: 'podatak nije dostupan', note: value.unavailable_label, unavailable: true, value: null }
  }
  return { text: format(value.value), note: value.period ? formatMonth(value.period) : null,
    provisional: Boolean(value.is_provisional), value: value.value }
}

function indicatorCell(indicator: Indicator, note: string): CellView {
  if (indicator.value === null) {
    return { text: 'pokazatelj nije dostupan', note: indicator.unavailable_label, unavailable: true, value: null }
  }
  const month = indicator.dzs_period ? ` · ${formatMonth(indicator.dzs_period)}` : ''
  return { text: formatDecimal(indicator.value), note: note + month, provisional: Boolean(indicator.is_provisional),
    value: indicator.value }
}

const SECTIONS: Section[] = [
  {
    key: 'hzz', name: 'Oglasi prema filtrima', hint: 'HZZ, oglasi koji odgovaraju filtrima',
    rows: [
      {
        key: 'jobs', name: 'Oglasi',
        cell: (county) => noHzz(county) ? NO_HZZ : { text: formatInteger(county.filtered_jobs.jobs) },
      },
      {
        key: 'workers', name: 'Traženi radnici',
        cell: (county) => {
          if (noHzz(county)) return NO_HZZ
          const { jobs, workers_needed: workers, workers_needed_coverage: known } = county.filtered_jobs
          if (!jobs) return { text: '0', note: 'nema oglasa' }
          if (!known.part) return { text: 'nije poznato', note: 'nijedan oglas ne navodi broj radnika', unavailable: true }
          return { text: formatInteger(workers), note: `navodi ${coverage(known.part, known.whole, known.percent)}` }
        },
      },
      {
        key: 'permanent', name: 'Na neodređeno',
        cell: (county) => {
          if (noHzz(county)) return NO_HZZ
          const { jobs, permanent_share: share } = county.filtered_jobs
          if (!jobs) return { text: '–', note: 'nema oglasa' }
          if (share.percent === null) return { text: 'nije poznato', note: 'nijedan oglas ne navodi ugovor', unavailable: true }
          return { text: formatShare(share.percent),
            note: `${formatInteger(share.part)} od ${formatInteger(share.whole)} s poznatim ugovorom` }
        },
      },
      {
        key: 'closing', name: 'Uskoro ističu',
        cell: (county, data) => noHzz(county) ? NO_HZZ : {
          text: formatInteger(county.filtered_jobs.closing_soon),
          note: `rok u sljedećih ${data.window_days} ${plural(data.window_days, 'dan', 'dana', 'dana')}`,
        },
      },
    ],
  },
  {
    key: 'dzs', name: 'Registrirana nezaposlenost', hint: 'DZS, za referentni mjesec',
    rows: [
      { key: 'unemployed', name: 'Registrirani nezaposleni', cell: (county) => dzsCell(county.unemployed, formatInteger) },
      { key: 'active', name: 'Aktivno stanovništvo', cell: (county) => dzsCell(county.active_population, formatInteger) },
      { key: 'rate', name: 'Stopa registrirane nezaposlenosti', cell: (county) => dzsCell(county.unemployment_rate, formatRate) },
    ],
  },
  {
    key: 'indicators', name: 'Pokazatelji za županiju u cjelini', hint: 'svi aktivni oglasi, bez filtara',
    rows: [
      {
        key: 'per-worker', name: 'Nezaposlenih na jednog traženog radnika', extremes: true,
        cell: (county) => {
          const { numerator, denominator } = county.unemployed_per_worker
          const known = county.all_active_jobs.workers_needed_coverage
          const note = numerator !== null && denominator !== null
            ? `${formatInteger(numerator)} nezaposlenih / ${formatInteger(denominator)} traženih radnika (broj navodi `
              + `${formatInteger(known.part)} od ${formatAds(known.whole)})`
            : ''
          return indicatorCell(county.unemployed_per_worker, note)
        },
      },
      {
        key: 'per-1000', name: 'Oglasa na 1.000 aktivnih stanovnika', extremes: true,
        cell: (county) => {
          const { numerator, denominator } = county.jobs_per_1000_active
          const note = numerator !== null && denominator !== null
            ? `${formatAds(numerator)} / ${formatInteger(denominator)} aktivnih` : ''
          return indicatorCell(county.jobs_per_1000_active, note)
        },
      },
    ],
  },
]

// Each section's place among the table's rows, its heading counted, for the rows' entrance delays.
const FIRST_ROWS = SECTIONS.map((_, k) => SECTIONS.slice(0, k).reduce((sum, section) => sum + section.rows.length + 1, 0))

/** The compare_counties arguments of a result without one filter: unset, or false for include_expired. */
function argumentsWithout(data: CountyComparisonData, argument: string) {
  const filters: CountyFilters = { ...data.filters, [argument]: argument === 'include_expired' ? false : null }
  return {
    counties: data.counties.map((county) => county.code),
    ...filters,
    ...(data.requested_period ? { period: data.requested_period.slice(0, 7) } : {}),
  }
}

// A result the view asked for itself, without a removed filter; base is the host's result it replaced.
interface Refiltered {
  base: CountyComparisonData
  data: CountyComparisonData
}

export function CountyComparison() {
  const mcp = useMcpApp<CountyComparisonData>('FOIHireloom county comparison', sample)
  const { app } = mcp
  const { expanded, toggle } = useExpanded(mcp)
  const [refiltered, setRefiltered] = useState<Refiltered | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // A new result from the host replaces the one the view asked for.
  const data = refiltered && refiltered.base === mcp.data ? refiltered.data : mcp.data
  if (!data) return <Card sunken title="Usporedba županija" description="Učitavanje…" />
  const tools = Boolean(app?.getHostCapabilities()?.serverTools)

  async function removeFilter(filter: ActiveFilter) {
    if (!app || !data || !mcp.data) return
    const base = mcp.data
    setLoading(true)
    setError(null)
    try {
      const result = await app.callServerTool({ name: 'show_county_comparison',
        arguments: argumentsWithout(data, filter.argument) })
      const next = result.structuredContent as CountyComparisonData | undefined
      if (result.isError || !next) throw new Error('Usporedba se nije mogla učitati.')
      setRefiltered({ base, data: next })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card sunken title={data.title} description={data.description} actions={(
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži usporedbu preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      {data.active_filters.length > 0 && (
        <ul className="filters" aria-label="Filtri oglasa">
          {data.active_filters.map((filter) => (
            <li key={filter.argument} className="filter">
              <span>{capitalise(filter.label)}</span>
              {tools && (
                <button className="filter-remove" type="button" disabled={loading}
                  title={`Ukloni filtar ${filter.label}`} aria-label={`Ukloni filtar ${filter.label}`}
                  onClick={() => void removeFilter(filter)}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                    aria-hidden="true">
                    <path d="M6 6l12 12M18 6 6 18" />
                  </svg>
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
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
  const root = useRef<HTMLDivElement>(null)

  useChartEntrance(root, (timeline) => {
    const all = (selector: string) => [...root.current!.querySelectorAll<HTMLElement>(selector)]
    const heads = all('[data-slot="county"]')
    timeline.add(heads, { ...fadeIn(heads, 10), duration: 800, ease: 'outExpo', delay: stagger(HEAD_STAGGER) }, 0)
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
