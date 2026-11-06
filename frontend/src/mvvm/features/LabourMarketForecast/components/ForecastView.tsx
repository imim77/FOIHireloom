import { Slider } from '@/components/ui/slider'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Button } from '@/components/ui/button'
import { ChevronDownIcon } from 'lucide-react'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { animate, type JSAnimation, stagger } from 'animejs'
import { type MouseEvent, type PointerEvent, type ReactNode, useId, useLayoutEffect, useRef } from 'react'
import { fadeIn, finish, MOTION, releaseStyles, useChartEntrance, useReducedMotion } from '../../../hooks/chart-motion'
import { useChartWidth } from '../../../hooks/use-chart-size'
import { forecastChart, formatChange, formatPeriod, formatValue } from '../utils/forecast-chart'
import type { useForecast } from '../hooks/use-forecast'
import type { CountyForecast, ForecastData, ObservedPoint } from '../types'

function Flags({ point }: { point: ObservedPoint }) {
  return <>{point.is_estimated && <Badge variant="provisional" className="provisional">procijenjeno</Badge>}
    {point.is_provisional && <Badge variant="provisional" className="provisional">privremeno</Badge>}</>
}

/**
 * Readout shows the inspected period's median over the chart, as the county chart shows its county's workers: the
 * eyebrow and lines rise in and the median counts up from 0; a newly inspected period rolls its name in and the
 * median counts to its value.
 */
function Readout({ context, median, format, children }: {
  context: string
  median: number
  format: (value: number) => string
  children: ReactNode
}) {
  const reduced = useReducedMotion()
  const root = useRef<HTMLDivElement>(null)
  const contextRef = useRef<HTMLParagraphElement>(null)
  const numberRef = useRef<HTMLParagraphElement>(null)
  const latest = useRef(median)
  useLayoutEffect(() => {
    latest.current = median
  })
  // The median on screen; while the entrance counts it up, a new period leaves the counting to the entrance.
  const count = useRef<{ tween: JSAnimation | null; value: number; entering: boolean }>(
    { tween: null, value: median, entering: false })
  const show = (value: number) => {
    count.current.value = value
    if (numberRef.current) numberRef.current.textContent = format(value)
  }

  useChartEntrance(root, (timeline) => {
    // The card's eyebrow comes in with the readout, ahead of it.
    const eyebrow = root.current!.closest('[data-slot="card"]')?.querySelector<HTMLElement>('[data-slot="eyebrow"]')
    const lines = [...(eyebrow ? [eyebrow] : []), ...root.current!.children] as HTMLElement[]
    const up = { t: 0 }
    const countUp = () => show(latest.current * up.t)
    count.current.entering = true
    countUp()
    const { readout, headline } = MOTION
    timeline
      .add(lines, { ...fadeIn(lines, readout.rise), duration: readout.duration, delay: stagger(readout.stagger) },
        readout.at)
      .add(up, { t: [0, 1], duration: headline.duration, ease: 'outExpo', onUpdate: countUp,
        onComplete: () => { count.current.entering = false } }, headline.at)
    return () => {
      count.current.entering = false
      show(latest.current)
      for (const el of lines) {
        el.style.removeProperty('opacity')
        el.style.removeProperty('transform')
      }
    }
  })

  useLayoutEffect(() => {
    const state = count.current
    if (state.entering || state.value === median) return
    state.tween?.cancel()
    state.tween = null
    if (reduced) {
      show(median)
      return
    }
    const from = { value: state.value }
    state.tween = finish(animate(from, {
      value: median, duration: MOTION.count, ease: 'outExpo',
      onUpdate: () => show(from.value),
      onComplete: () => {
        state.tween = null
        show(median)
      },
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [median, reduced])
  useLayoutEffect(() => () => { count.current.tween?.cancel() }, [])

  const lastContext = useRef(context)
  useLayoutEffect(() => {
    if (lastContext.current === context) return
    lastContext.current = context
    if (reduced || !contextRef.current) return
    finish(animate(contextRef.current, { translateY: ['100%', '0%'], duration: MOTION.roll, ease: 'outExpo',
      onComplete: releaseStyles('transform') }))
  }, [context, reduced])

  return <div className="forecast-readout flex flex-col items-start gap-2.5" ref={root} data-slot="readout">
    {/* Clips the period as it rolls in from below on a new one. */}
    <div className="overflow-clip">
      <p className="soft m-0 mono-label uppercase text-fg-soft" ref={contextRef} data-slot="forecast-period">{context}</p>
    </div>
    <p className="forecast-number m-0 mono-headline whitespace-nowrap text-fg-loud" ref={numberRef}
      data-slot="forecast-median">{format(median)}</p>
    {children}
  </div>
}

export function ForecastView(model: ReturnType<typeof useForecast>) {
  const { data, county, active, selected, selectPeriod, hoverPeriod, point, selectedPoint, last, end, value, period,
    interval } = model
  const sliderId = useId()
  const sliderLabel = `${sliderId}-label`
  return <div className="forecast-content min-w-0 flex flex-col gap-6">
    {point && <Readout context={`${period(point.period)} · medijan prognoze`} median={point.median} format={value}>
      <p className="forecast-interval m-0 mono-label uppercase text-fg-soft" data-slot="forecast-interval">{value(point.low)} – {value(point.high)} · {interval}</p>
      {/* The badges keep their own case, as in the other views' readouts. */}
      <div className="forecast-last flex flex-wrap items-center [gap:4px_8px] mono-label text-fg-soft"
        data-slot="forecast-last">
        <span className="uppercase">Posljednji podatak: {last?.value == null ? 'nema podatka' : value(last.value)}
          {last && ` · ${period(last.period)}`}</span>
        {last && <Flags point={last} />}
      </div>
    </Readout>}
    {county.history.some((p) => p.value !== null) || point ?
      <ForecastChart data={data} county={county} active={active} onSelect={selectPeriod} onHover={hoverPeriod} />
      : null}
    {selectedPoint && <FieldGroup className="forecast-control">
      <Field>
        <FieldLabel id={sliderLabel}>{data.frequency === 'month' ? 'Mjesec prognoze' : 'Tjedan prognoze'}</FieldLabel>
        <Slider min={0} max={county.forecast.length - 1} step={1} value={[selected]}
          onValueChange={(values) => selectPeriod(Array.isArray(values) ? values[0] : values)}
          thumbProps={{ 'aria-labelledby': sliderLabel,
            'aria-valuetext': `${period(selectedPoint.period)}: ${value(selectedPoint.median)}, ${interval} `
              + `${value(selectedPoint.low)} – ${value(selectedPoint.high)}` }} />
      </Field>
    </FieldGroup>}
    {end && county.change_to_horizon !== null && <p className="forecast-change flex flex-wrap items-baseline [gap:6px_12px] m-0 mono-label uppercase text-fg-soft
      [&_strong]:text-fg-loud [&_strong]:text-[14px] [&_strong]:font-medium">
      <strong>{formatChange(county.change_to_horizon, data.unit)}</strong>
      <span>do {period(end.period)}, u odnosu na posljednji podatak</span>
    </p>}
    {county.forecast.length > 0 && <div className="forecast-table-scroll focus-visible:outline-none focus-visible:shadow-focus overflow-auto [max-height:290px]
      border border-border rounded-[10px]" tabIndex={0} role="region" aria-label="Prognozirane vrijednosti">
      <Table variant="numeric" containerClassName="contents" className="forecast-table w-full border-collapse text-right tabular-nums [&_caption]:text-left [&_caption]:p-3
        [&_caption]:text-fg-soft [&_th]:[padding:9px_12px] [&_th]:[border-top:1px_solid_var(--border)]
        [&_th]:whitespace-nowrap [&_td]:[padding:9px_12px] [&_td]:[border-top:1px_solid_var(--border)]
        [&_td]:whitespace-nowrap [&_th]:font-medium [&_th:first-child]:text-left [&_thead_th]:sticky
        [&_thead_th]:top-0 [&_thead_th]:text-fg-soft [&_.provisional]:m-0.5 [@media(max-width:_420px)]:[&_th]:p-2
        [@media(max-width:_420px)]:[&_td]:p-2">
        <TableCaption>Sve prognozirane vrijednosti · {data.unit === 'percent' ? '%' : data.unit === 'persons' ? 'osobe' : 'oglasi'}</TableCaption>
        <TableHeader><TableRow><TableHead scope="col" sticky="header">{data.frequency === 'month' ? 'Mjesec' : 'Tjedan od'}</TableHead>
          <TableHead scope="col" sticky="header">Medijan</TableHead><TableHead scope="col" sticky="header">Donja granica</TableHead><TableHead scope="col" sticky="header">Gornja granica</TableHead></TableRow></TableHeader>
        <TableBody>{county.forecast.map((p) => <TableRow key={p.period} data-period={p.period} data-slot="forecast-row"
          data-state={point?.period === p.period ? 'selected' : undefined}>
          <TableHead scope="row">{period(p.period).replace('tjedan od ', '')}</TableHead><TableCell>{value(p.median)}</TableCell>
          <TableCell>{value(p.low)}</TableCell><TableCell>{value(p.high)}</TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </div>}
    {county.history.length > 0 && <Collapsible className="forecast-history">
      <CollapsibleTrigger render={<Button variant="ghost" />}>
        Povijesni podaci ({county.history.length})<ChevronDownIcon data-icon="inline-end" aria-hidden="true" />
      </CollapsibleTrigger>
      <CollapsibleContent>
      <div className="forecast-table-scroll focus-visible:outline-none focus-visible:shadow-focus overflow-auto [max-height:290px]
        border border-border rounded-[10px]" tabIndex={0} role="region" aria-label="Povijesne vrijednosti">
        <Table variant="numeric" containerClassName="contents" className="forecast-table w-full border-collapse text-right tabular-nums [&_caption]:text-left [&_caption]:p-3
        [&_caption]:text-fg-soft [&_th]:[padding:9px_12px] [&_th]:[border-top:1px_solid_var(--border)]
        [&_th]:whitespace-nowrap [&_td]:[padding:9px_12px] [&_td]:[border-top:1px_solid_var(--border)]
        [&_td]:whitespace-nowrap [&_th]:font-medium [&_th:first-child]:text-left [&_thead_th]:sticky
        [&_thead_th]:top-0 [&_thead_th]:text-fg-soft [&_.provisional]:m-0.5 [@media(max-width:_420px)]:[&_th]:p-2
        [@media(max-width:_420px)]:[&_td]:p-2"><TableCaption>Povijesne vrijednosti korištene u prikazu</TableCaption>
          <TableHeader><TableRow><TableHead scope="col" sticky="header">Razdoblje</TableHead><TableHead scope="col" sticky="header">Vrijednost</TableHead><TableHead scope="col" sticky="header">Status</TableHead></TableRow></TableHeader>
          <TableBody>{county.history.map((p) => <TableRow key={p.period}><TableHead scope="row">{period(p.period)}</TableHead>
            <TableCell>{p.value === null ? 'nema podatka' : value(p.value)}</TableCell>
            <TableCell>{p.value === null ? 'nedostaje' : p.is_estimated || p.is_provisional ? <Flags point={p} /> : 'objavljeno'}</TableCell>
          </TableRow>)}</TableBody>
        </Table>
      </div>
      </CollapsibleContent>
    </Collapsible>}
  </div>
}

// The interval is the red wash, edged in accent-300 so it still reads as red on the dark card.
const WASH = '[fill:var(--accent-wash)] [stroke:var(--accent-300)] [stroke-opacity:.6] [stroke-width:1]'
const WASH_KEY = 'bg-accent-wash border border-accent-300/60'

function ForecastChart({ data, county, active, onSelect, onHover }: {
  data: ForecastData; county: CountyForecast; active: number
  onSelect: (index: number) => void; onHover: (index: number | null) => void
}) {
  const [ref, measured] = useChartWidth<HTMLDivElement>()
  const width = Math.max(80, measured || 560)
  const chart = forecastChart(county, width, data.unit)
  const cursor = chart.forecast[active]
  const periods = [...county.history, ...county.forecast]
  const flags = county.history.some((p) => p.is_estimated || p.is_provisional)
  // The forecast period nearest the pointer; null over the history.
  const nearest = (event: PointerEvent<HTMLDivElement> | MouseEvent<HTMLDivElement>) => {
    if (!chart.forecast.length) return null
    const rect = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - rect.left) / rect.width * width
    if (x < chart.forecast[0].x) return null
    return chart.forecast.reduce((best, p, index) =>
      Math.abs(p.x - x) < Math.abs(chart.forecast[best].x - x) ? index : best, 0)
  }
  return <div className="forecast-chart" data-slot="forecast-chart">
    <ul className="forecast-legend flex flex-wrap [gap:8px_16px] p-0 [margin:0_0_16px] [list-style:none] text-fg-soft
      mono-label uppercase [&_li]:inline-flex [&_li]:items-center [&_li]:gap-2" aria-label="Legenda">
      <li><span className="forecast-key history w-4 h-0 border-t-2 border-fg-soft" />Povijest</li>
      <li><span className="forecast-key median w-4 h-0 border-t-2 border-dashed border-accent-500" />Prognoza (medijan)</li>
      <li><span className={`forecast-key interval w-4 h-2.5 ${WASH_KEY}`} />
        {Math.round(data.interval * 100)}% interval</li>
      {flags && <li><span className="forecast-key estimated w-4 h-0 border-t-2 border-dashed border-fg-soft" />
        Procijenjeno / privremeno</li>}
    </ul>
    <div className="forecast-axes flex gap-2 min-w-0">
      <div className="forecast-y-axis relative flex-none w-16 mono-label text-fg-soft
        [&_span]:absolute [&_span]:right-0 [&_span]:[transform:translateY(-50%)] [&_span]:whitespace-nowrap
        [@media(max-width:_420px)]:w-14" aria-hidden="true" style={{ height: chart.height }}>
        {chart.ticks.map((tick) => <span key={tick} style={{ top: chart.y(tick) }}>{formatValue(tick, data.unit)}</span>)}
      </div>
      <div className="forecast-plot-column flex-1 min-w-0">
        {/* Hover previews a forecast period and click selects it, as on the county chart; the slider is the
            keyboard route. A touch drag scrolls the page instead of previewing. */}
        <div ref={ref} className={`forecast-plot [&_svg]:block [&_svg]:overflow-visible${
          chart.forecast.length ? ' cursor-pointer' : ''}`}
          onPointerMove={(event) => { if (event.buttons === 0) onHover(nearest(event)) }}
          onPointerLeave={() => onHover(null)}
          onClick={(event) => {
            const index = nearest(event)
            if (index !== null) onSelect(index)
          }}>
          <svg width="100%" height={chart.height} viewBox={`0 0 ${width} ${chart.height}`} role="img"
            aria-label="Povijesne vrijednosti i Chronos prognoza; točne vrijednosti navedene su u tablicama.">
            {chart.ticks.map((tick) => <line key={tick} x1={0} x2={width} y1={chart.y(tick)} y2={chart.y(tick)} className="forecast-grid [stroke:var(--border)] [stroke-dasharray:3_4]" />)}
            {chart.forecast.length > 0 && <line x1={chart.boundary} x2={chart.boundary} y1={chart.top} y2={chart.bottom}
              className="forecast-boundary [stroke:var(--fg-soft)] [stroke-dasharray:2_5] [opacity:.5]" />}
            {chart.band && <path d={chart.band} className={`forecast-band ${WASH}`} data-slot="forecast-band" />}
            {chart.history.map((p, index) => {
              const next = chart.history[index + 1]
              return p.y !== null && next?.y != null ? <line key={p.period} x1={p.x} y1={p.y} x2={next.x} y2={next.y}
                className="forecast-observed [fill:none] [stroke:var(--fg-soft)] [stroke-width:2]" data-slot="history-segment" data-from={p.period} data-to={next.period}
                strokeDasharray={p.is_estimated || p.is_provisional || next.is_estimated || next.is_provisional ? '4 4' : undefined} /> : null
            })}
            {chart.history.map((p) => p.y !== null && <circle key={p.period} cx={p.x} cy={p.y} r={2.5}
              className="forecast-observed-node [fill:var(--fg-soft)]" data-slot="history-node" data-value={p.value} data-period={p.period} />)}
            {/* Projected values are dashed, like provisional history; red because the forecast is the focus. */}
            {chart.forecast.length > 0 && <path d={chart.median} strokeDasharray="6 4"
              className="forecast-predicted [fill:none] [stroke:var(--accent-500)] [stroke-width:2.5]" />}
            {chart.forecast.map((p) => <circle key={p.period} cx={p.x} cy={p.y} r={2.5} className="forecast-predicted-node [fill:var(--accent-500)]" />)}
            {cursor && <g data-slot="forecast-cursor" data-period={cursor.period}>
              <line x1={cursor.x} x2={cursor.x} y1={cursor.highY} y2={cursor.lowY} className="forecast-range-line [stroke:var(--accent-500)] [stroke-width:1.5]" />
              <circle cx={cursor.x} cy={cursor.y} r={5} className="forecast-active-node [fill:var(--accent-500)] [stroke:var(--card)] [stroke-width:2]" />
            </g>}
          </svg>
        </div>
        <div className="forecast-x-axis flex justify-between gap-3 mt-2.5 mono-label uppercase text-fg-soft [&_span:last-child]:text-right"><span>{formatPeriod(periods[0].period, data.frequency)}</span>
          {periods.length > 1 && <span>{formatPeriod(periods.at(-1)!.period, data.frequency)}</span>}</div>
      </div>
    </div>
  </div>
}
