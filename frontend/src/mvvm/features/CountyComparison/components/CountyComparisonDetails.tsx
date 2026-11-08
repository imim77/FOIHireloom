import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import type { CSSProperties } from 'react'
import { useComparisonEntrance } from '../../../hooks/use-comparison-entrance'
import { formatMoment, formatMonth } from '../../../utils/format'
import { Sources } from '../../../components/Sources'
import { FIRST_ROWS, SECTIONS } from '../utils/county-rows'
import type { CountyComparisonData } from '../types'

const ROW_STAGGER = 45

/** When the HZZ ads were checked and which month the DZS values are for, in one muted line: they are different moments. */
export function Moments({ data }: { data: CountyComparisonData }) {
  const months = [...new Set(data.dzs_periods.flatMap((reference) => reference.period ?? []))]
  const provisional = data.counties.some((county) => [county.unemployed, county.active_population,
    county.unemployment_rate].some((value) => value.is_provisional))
  const parts = [
    data.hzz_coverage.data_as_of && `Oglasi: ${formatMoment(data.hzz_coverage.data_as_of)}`,
    months.length && `Nezaposlenost: ${months.map(formatMonth).join(', ')}${provisional ? ' (privremeno)' : ''}`,
  ].filter(Boolean)
  return parts.length ? <p data-enter className="moments m-0 text-[12px] text-fg-soft">{parts.join(' · ')}</p> : null
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
        [&_.section_>_th]:[padding:20px_0_8px] [&_thead_th]:[border-bottom:2px_solid_var(--fg-loud)]" style={{ '--counties': data.counties.length } as CSSProperties}>
        <TableHeader>
          <TableRow>
            <TableCell sticky className="corner w-(--aspect) bg-surface-sunken" />
            {data.counties.map((county) => (
              <TableHead key={county.code} scope="col" className="county-head">
                <div className="county-head-inner min-w-0" data-slot="county">
                  <span className="county-name text-[16px] font-semibold leading-[1.3]">{county.short_name}</span>
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
                  <div className="section-inner sticky left-0 [width:max-content] [padding:0_12px]" data-row={sectionRow}>
                    <span className="section-name mono-label font-medium uppercase text-fg-loud">{section.name}</span>
                  </div>
                </TableHead>
              </TableRow>
              {section.rows.map((row, r) => {
                const rowIndex = sectionRow + 1 + r
                const cells = data.counties.map((county) => row.cell(county))
                const known = cells.flatMap((cell) => cell.value ?? [])
                const high = Math.max(...known)
                const low = Math.min(...known)
                const marked = row.extremes && known.length > 1 && high !== low
                return (
                  <TableRow key={row.key}>
                    <TableHead scope="row" sticky="column" className="aspect w-(--aspect) bg-surface-sunken text-fg-soft">
                      <div className="aspect-inner font-medium leading-[1.4] min-w-0" data-row={rowIndex}>{row.name(data)}</div>
                    </TableHead>
                    {cells.map((cell, j) => (
                      <TableCell key={data.counties[j].code} title={cell.reason ?? undefined}
                        className={`cell ${cell.unavailable ? ' unavailable text-fg-soft' : ''}`}>
                        <div className="cell-inner min-w-0" data-row={rowIndex}>
                          <span className="cell-text flex flex-wrap items-center [gap:4px_8px] font-mono text-[15px] font-medium">
                            {cell.text}{cell.provisional && <span aria-label="privremeno" className="text-fg-soft">*</span>}
                            {marked && cell.value === high && <Extreme>najviše</Extreme>}
                            {marked && cell.value === low && <Extreme>najmanje</Extreme>}
                          </span>
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
    <Sources onOpenLink={onOpenLink} links={data.source_links} />
  )
}
