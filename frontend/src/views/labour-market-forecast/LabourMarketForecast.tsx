import { useId, useState } from 'react'
import { Card, Notes, Warning } from '../../shared/Card'
import { useMcpApp } from '../../shared/mcp'
import { Sources } from '../../shared/Sources'
import { useChartWidth } from '../../shared/use-chart-size'
import { forecastChart, formatChange, formatPeriod, formatValue } from './forecast-chart'
import { sample } from './sample'
import type { CountyForecast, ForecastData, ObservedPoint } from './types'

export function LabourMarketForecast() {
  const mcp = useMcpApp<ForecastData>('FOIHireloom labour market forecast', sample)
  const data = mcp.data
  const county = data?.counties[0]
  return <div className="forecast-view [--forecast-line:#087f8c] [--forecast-history:#64748b] [--forecast-wash:#e6f4f5]
    dark:[--forecast-line:#5dd7de] dark:[--forecast-history:#b0bdcf] dark:[--forecast-wash:#163437]
    [&_.title]:whitespace-normal [&_.title]:overflow-visible [&_.titles_>_.soft]:whitespace-normal
    [&_.titles_>_.soft]:overflow-visible [&_.body]:min-w-0 [@media(max-width:_420px)]:[&_.card]:p-3.5">
    <Card title={data?.title ?? 'Chronos prognoza za županiju'} description={data?.description ?? 'Učitavanje…'}>
      {data && <>
        <Warning text={data.unavailable_label} />
        {county && <Forecast key={mcp.revision} data={data} county={county} />}
        <Sources app={mcp.app} links={data.source_links}><span>Model: {data.model}</span></Sources>
        <Notes warning={null} note={data.view_notes} />
      </>}
    </Card>
  </div>
}

function Flags({ point }: { point: ObservedPoint }) {
  return <>{point.is_estimated && <span className="provisional inline-block [padding:1px_6px] rounded-full text-[11px] font-medium leading-[1.4]
    whitespace-nowrap text-fg-soft [outline:1px_dashed_var(--fg-soft)] [outline-offset:-1px]">procijenjeno</span>}
    {point.is_provisional && <span className="provisional inline-block [padding:1px_6px] rounded-full text-[11px] font-medium leading-[1.4]
      whitespace-nowrap text-fg-soft [outline:1px_dashed_var(--fg-soft)] [outline-offset:-1px]">privremeno</span>}</>
}

function Forecast({ data, county }: { data: ForecastData; county: CountyForecast }) {
  const [selected, setSelected] = useState(Math.max(0, county.forecast.length - 1))
  const point = county.forecast[selected]
  const last = county.last_observed
  const end = county.forecast.at(-1)
  const value = (n: number) => formatValue(n, data.unit)
  const period = (iso: string) => formatPeriod(iso, data.frequency)
  const interval = `${Math.round(data.interval * 100)}% interval`
  const sliderId = useId()
  return <div className="forecast-content min-w-0 flex flex-col gap-5">
    {point && <>
      <div className="forecast-readings grid [grid-template-columns:1fr_1fr] gap-3 [@media(max-width:_420px)]:gap-2">
        <section className="forecast-reading flex flex-col items-start gap-2.5 p-4 border border-border rounded-[14px] min-w-0
          [@media(max-width:_420px)]:p-3" aria-label="Posljednji podatak">
          <p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">Posljednji podatak</p>
          <p className="forecast-number m-0 text-[clamp(22px,_4vw,_32px)] font-semibold [letter-spacing:-.04em]
            leading-[1.15] tabular-nums [overflow-wrap:anywhere]">{last?.value == null ? 'nema podatka' : value(last.value)}</p>
          {last && <><p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">{period(last.period)}</p><div className="forecast-flags flex flex-wrap gap-1"><Flags point={last} /></div></>}
        </section>
        <section className="forecast-reading forecast-selected flex flex-col items-start gap-2.5 p-4 border border-border
          rounded-[14px] min-w-0 [background:var(--forecast-wash)] [border-color:transparent]
          [&_.forecast-number]:[color:var(--forecast-line)] [@media(max-width:_420px)]:p-3" aria-label="Odabrana prognoza" aria-live="polite">
          <p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">Prognoza · medijan</p>
          <p className="forecast-number m-0 text-[clamp(22px,_4vw,_32px)] font-semibold [letter-spacing:-.04em]
            leading-[1.15] tabular-nums [overflow-wrap:anywhere]" data-slot="forecast-median">{value(point.median)}</p>
          <p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft" data-slot="forecast-period">{period(point.period)}</p>
          <p className="forecast-interval flex flex-wrap [gap:4px_12px] m-0 text-[12px] leading-[1.5] tabular-nums [&_span]:text-fg-soft" data-slot="forecast-interval">{value(point.low)} – {value(point.high)}<span>{interval}</span></p>
        </section>
      </div>
    </>}
    {county.history.some((p) => p.value !== null) || point ?
      <ForecastChart data={data} county={county} selected={selected} onSelect={setSelected} /> : null}
    {point && <div className="forecast-control grid [grid-template-columns:auto_1fr] gap-4 items-center text-[12px] [&_input]:w-full
      [&_input]:min-w-0 [&_input]:m-0 [&_input]:[accent-color:var(--forecast-line)] [&_input]:cursor-pointer
      [&_input:focus-visible]:[outline:2px_solid_var(--forecast-line)]
      [&_input:focus-visible]:[outline-offset:4px] [&_input:focus-visible]:rounded-[3px]
      [@media(max-width:_420px)]:[grid-template-columns:1fr] [@media(max-width:_420px)]:gap-2">
      <label htmlFor={sliderId}>{data.frequency === 'month' ? 'Mjesec prognoze' : 'Tjedan prognoze'}</label>
      <input id={sliderId} type="range" min={0} max={county.forecast.length - 1} step={1} value={selected}
        aria-valuetext={`${period(point.period)}: ${value(point.median)}, ${interval} ${value(point.low)} – ${value(point.high)}`}
        onChange={(event) => setSelected(Number(event.target.value))} />
    </div>}
    {end && county.change_to_horizon !== null && <p className="forecast-change flex flex-wrap items-baseline [gap:6px_12px] m-0 text-[12px] leading-[1.5] text-fg-soft
      [&_strong]:text-fg-loud [&_strong]:text-[15px] [&_strong]:font-semibold [&_strong]:tabular-nums">
      <strong>{formatChange(county.change_to_horizon, data.unit)}</strong>
      <span>do {period(end.period)}, u odnosu na posljednji podatak</span>
    </p>}
    {county.forecast.length > 0 && <div className="forecast-table-scroll [&:focus-visible]:[outline:2px_solid_var(--forecast-line)]
      [&:focus-visible]:[outline-offset:4px] [&:focus-visible]:rounded-[3px] overflow-auto [max-height:290px]
      border border-border rounded-[12px]" tabIndex={0} role="region" aria-label="Prognozirane vrijednosti">
      <table className="forecast-table w-full border-collapse text-right text-[12px] leading-[1.5] tabular-nums
        [&_caption]:text-left [&_caption]:p-3 [&_caption]:text-fg-soft [&_caption]:text-[11px]
        [&_th]:[padding:9px_12px] [&_th]:[border-top:1px_solid_var(--border)] [&_th]:whitespace-nowrap
        [&_td]:[padding:9px_12px] [&_td]:[border-top:1px_solid_var(--border)] [&_td]:whitespace-nowrap
        [&_th]:font-medium [&_th:first-child]:text-left [&_thead_th]:sticky [&_thead_th]:top-0
        [&_thead_th]:bg-card [&_thead_th]:text-[10px] [&_thead_th]:text-fg-soft
        [&_.is-selected]:[background:var(--forecast-wash)] [&_.provisional]:m-0.5
        [@media(max-width:_420px)]:[&_th]:p-2 [@media(max-width:_420px)]:[&_td]:p-2">
        <caption>Sve prognozirane vrijednosti · {data.unit === 'percent' ? '%' : data.unit === 'persons' ? 'osobe' : 'oglasi'}</caption>
        <thead><tr><th scope="col">{data.frequency === 'month' ? 'Mjesec' : 'Tjedan od'}</th>
          <th scope="col">Medijan</th><th scope="col">Donja granica</th><th scope="col">Gornja granica</th></tr></thead>
        <tbody>{county.forecast.map((p) => <tr key={p.period} data-period={p.period} data-slot="forecast-row"
          className={point?.period === p.period ? 'is-selected' : ''}>
          <th scope="row">{period(p.period).replace('tjedan od ', '')}</th><td>{value(p.median)}</td>
          <td>{value(p.low)}</td><td>{value(p.high)}</td>
        </tr>)}</tbody>
      </table>
    </div>}
    {county.history.length > 0 && <details className="forecast-history [&_summary:focus-visible]:[outline:2px_solid_var(--forecast-line)]
      [&_summary:focus-visible]:[outline-offset:4px] [&_summary:focus-visible]:rounded-[3px] text-fg-soft
      text-[12px] [&_summary]:cursor-pointer [&_summary]:[padding:4px_0] [&_.forecast-table-scroll]:mt-3
      [&_.forecast-table-scroll]:text-fg-loud">
      <summary>Povijesni podaci ({county.history.length})</summary>
      <div className="forecast-table-scroll [&:focus-visible]:[outline:2px_solid_var(--forecast-line)]
        [&:focus-visible]:[outline-offset:4px] [&:focus-visible]:rounded-[3px] overflow-auto [max-height:290px]
        border border-border rounded-[12px]" tabIndex={0} role="region" aria-label="Povijesne vrijednosti">
        <table className="forecast-table w-full border-collapse text-right text-[12px] leading-[1.5] tabular-nums
          [&_caption]:text-left [&_caption]:p-3 [&_caption]:text-fg-soft [&_caption]:text-[11px]
          [&_th]:[padding:9px_12px] [&_th]:[border-top:1px_solid_var(--border)] [&_th]:whitespace-nowrap
          [&_td]:[padding:9px_12px] [&_td]:[border-top:1px_solid_var(--border)] [&_td]:whitespace-nowrap
          [&_th]:font-medium [&_th:first-child]:text-left [&_thead_th]:sticky [&_thead_th]:top-0
          [&_thead_th]:bg-card [&_thead_th]:text-[10px] [&_thead_th]:text-fg-soft
          [&_.is-selected]:[background:var(--forecast-wash)] [&_.provisional]:m-0.5
          [@media(max-width:_420px)]:[&_th]:p-2 [@media(max-width:_420px)]:[&_td]:p-2"><caption>Povijesne vrijednosti korištene u prikazu</caption>
          <thead><tr><th scope="col">Razdoblje</th><th scope="col">Vrijednost</th><th scope="col">Status</th></tr></thead>
          <tbody>{county.history.map((p) => <tr key={p.period}><th scope="row">{period(p.period)}</th>
            <td>{p.value === null ? 'nema podatka' : value(p.value)}</td>
            <td>{p.value === null ? 'nedostaje' : p.is_estimated || p.is_provisional ? <Flags point={p} /> : 'objavljeno'}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </details>}
  </div>
}

function ForecastChart({ data, county, selected, onSelect }: {
  data: ForecastData; county: CountyForecast; selected: number; onSelect: (index: number) => void
}) {
  const [ref, measured] = useChartWidth<HTMLDivElement>()
  const width = Math.max(80, measured || 560)
  const chart = forecastChart(county, width, data.unit)
  const active = chart.forecast[selected]
  const periods = [...county.history, ...county.forecast]
  const flags = county.history.some((p) => p.is_estimated || p.is_provisional)
  return <div className="forecast-chart" data-slot="forecast-chart">
    <ul className="forecast-legend flex flex-wrap [gap:8px_16px] p-0 [margin:0_0_18px] [list-style:none] text-fg-soft
      text-[11px] [&_li]:inline-flex [&_li]:items-center [&_li]:gap-1.5" aria-label="Legenda">
      <li><span className="forecast-key history w-4 h-0 [border-top:2px_solid_var(--forecast-history)]
        [&.median]:[border-color:var(--forecast-line)] [&.interval]:h-2.5 [&.interval]:[border:0]
        [&.interval]:[background:color-mix(in_srgb,_var(--forecast-line)_18%,_transparent)]
        [&.estimated]:[border-top-style:dashed]" />Povijest</li>
      <li><span className="forecast-key median w-4 h-0 [border-top:2px_solid_var(--forecast-history)]
        [&.median]:[border-color:var(--forecast-line)] [&.interval]:h-2.5 [&.interval]:[border:0]
        [&.interval]:[background:color-mix(in_srgb,_var(--forecast-line)_18%,_transparent)]
        [&.estimated]:[border-top-style:dashed]" />Prognoza (medijan)</li>
      <li><span className="forecast-key interval w-4 h-0 [border-top:2px_solid_var(--forecast-history)]
        [&.median]:[border-color:var(--forecast-line)] [&.interval]:h-2.5 [&.interval]:[border:0]
        [&.interval]:[background:color-mix(in_srgb,_var(--forecast-line)_18%,_transparent)]
        [&.estimated]:[border-top-style:dashed]" />{Math.round(data.interval * 100)}% interval</li>
      {flags && <li><span className="forecast-key estimated w-4 h-0 [border-top:2px_solid_var(--forecast-history)]
        [&.median]:[border-color:var(--forecast-line)] [&.interval]:h-2.5 [&.interval]:[border:0]
        [&.interval]:[background:color-mix(in_srgb,_var(--forecast-line)_18%,_transparent)]
        [&.estimated]:[border-top-style:dashed]" />Procijenjeno / privremeno</li>}
    </ul>
    <div className="forecast-axes flex gap-2 min-w-0">
      <div className="forecast-y-axis relative flex-none w-16 text-[10px] tabular-nums text-fg-soft [&_span]:absolute
        [&_span]:right-0 [&_span]:[transform:translateY(-50%)] [&_span]:whitespace-nowrap
        [@media(max-width:_420px)]:w-12 [@media(max-width:_420px)]:text-[9px]" aria-hidden="true" style={{ height: chart.height }}>
        {chart.ticks.map((tick) => <span key={tick} style={{ top: chart.y(tick) }}>{formatValue(tick, data.unit)}</span>)}
      </div>
      <div className="forecast-plot-column flex-1 min-w-0">
        <div ref={ref} className="forecast-plot [&_svg]:block [&_svg]:overflow-visible" onPointerMove={(event) => {
          if (!chart.forecast.length || event.buttons !== 0) return
          const rect = event.currentTarget.getBoundingClientRect()
          const x = (event.clientX - rect.left) / rect.width * width
          if (x < chart.forecast[0].x) return
          const nearest = chart.forecast.reduce((best, p, index) =>
            Math.abs(p.x - x) < Math.abs(chart.forecast[best].x - x) ? index : best, 0)
          onSelect(nearest)
        }}>
          <svg width="100%" height={chart.height} viewBox={`0 0 ${width} ${chart.height}`} role="img"
            aria-label="Povijesne vrijednosti i Chronos prognoza; točne vrijednosti navedene su u tablicama.">
            {chart.ticks.map((tick) => <line key={tick} x1={0} x2={width} y1={chart.y(tick)} y2={chart.y(tick)} className="forecast-grid [stroke:var(--border)] [stroke-dasharray:3_4]" />)}
            {chart.forecast.length > 0 && <line x1={chart.boundary} x2={chart.boundary} y1={chart.top} y2={chart.bottom}
              className="forecast-boundary [stroke:var(--fg-soft)] [stroke-dasharray:2_5] [opacity:.5]" />}
            {chart.band && <path d={chart.band} className="forecast-band [fill:var(--forecast-line)] [fill-opacity:.16]" data-slot="forecast-band" />}
            {chart.history.map((p, index) => {
              const next = chart.history[index + 1]
              return p.y !== null && next?.y != null ? <line key={p.period} x1={p.x} y1={p.y} x2={next.x} y2={next.y}
                className="forecast-observed [fill:none] [stroke:var(--forecast-history)] [stroke-width:2]" data-slot="history-segment" data-from={p.period} data-to={next.period}
                strokeDasharray={p.is_estimated || p.is_provisional || next.is_estimated || next.is_provisional ? '4 4' : undefined} /> : null
            })}
            {chart.history.map((p) => p.y !== null && <circle key={p.period} cx={p.x} cy={p.y} r={2.5}
              className="forecast-observed-node [fill:var(--forecast-history)]" data-slot="history-node" data-value={p.value} data-period={p.period} />)}
            {chart.forecast.length > 0 && <path d={chart.median} className="forecast-predicted [fill:none] [stroke:var(--forecast-line)] [stroke-width:2.5]" />}
            {chart.forecast.map((p) => <circle key={p.period} cx={p.x} cy={p.y} r={2.5} className="forecast-predicted-node [fill:var(--forecast-line)]" />)}
            {active && <g data-slot="forecast-cursor" data-period={active.period}>
              <line x1={active.x} x2={active.x} y1={active.highY} y2={active.lowY} className="forecast-range-line [stroke:var(--forecast-line)] [stroke-width:1.5]" />
              <circle cx={active.x} cy={active.y} r={5} className="forecast-active-node [fill:var(--forecast-line)] [stroke:var(--card)] [stroke-width:2]" />
            </g>}
          </svg>
        </div>
        <div className="forecast-x-axis flex justify-between gap-3 mt-2.5 text-[10px] leading-[1.5] text-fg-soft [&_span:last-child]:text-right"><span>{formatPeriod(periods[0].period, data.frequency)}</span>
          {periods.length > 1 && <span>{formatPeriod(periods.at(-1)!.period, data.frequency)}</span>}</div>
      </div>
    </div>
  </div>
}
