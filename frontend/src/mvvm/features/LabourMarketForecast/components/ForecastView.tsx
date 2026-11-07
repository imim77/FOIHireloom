import { Slider } from '@/components/ui/slider'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { type ReactNode, useId, useLayoutEffect, useRef } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ReferenceLine, XAxis, YAxis } from 'recharts'
import { type ChartConfig, ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { clearEntrance, enter, MOTION, roll, useChartEntrance, useReducedMotion }
  from '../../../hooks/chart-motion'
import { type ForecastRow, forecastRows, formatChange, formatPeriod, formatPeriodGenitive, formatValue, valueTicks }
  from '../utils/forecast-chart'
import { useReadoutCount } from '../../../hooks/use-readout-count'
import type { useForecast } from '../hooks/use-forecast'
import type { CountyForecast, ForecastData, ObservedPoint } from '../types'

function Flags({ point }: { point: ObservedPoint }) {
  return <>{point.is_estimated && <Badge variant="provisional" className="provisional">procijenjeno</Badge>}
    {point.is_provisional && <Badge variant="provisional" className="provisional">privremeno</Badge>}</>
}

/**
 * Readout shows the inspected period's median over the chart, as the county chart shows its county's workers: the
 * lines rise in and the median counts up from 0; a newly inspected period rolls its name in and the
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
  const count = useReadoutCount(numberRef, median, format)

  useChartEntrance(root, (timeline) => {
    const lines = [...root.current!.children] as HTMLElement[]
    enter(timeline, lines, MOTION.readout.at, MOTION.readout)
    const finishCount = count(timeline)
    return () => {
      finishCount()
      clearEntrance(lines)
    }
  })

  const lastContext = useRef(context)
  useLayoutEffect(() => {
    if (lastContext.current === context) return
    lastContext.current = context
    if (reduced || !contextRef.current) return
    roll(contextRef.current)
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

/**
 * ForecastView puts one message first: the inspected period's median, then one sentence with its interval and how
 * far it is from the last observed value. The chart is the focus; the slider under it is the keyboard route to a
 * period. Every exact value is in ForecastTables, which the screen keeps behind its details control.
 */
export function ForecastView(model: ReturnType<typeof useForecast>) {
  const { data, county, active, selected, selectPeriod, hoverPeriod, point, selectedPoint, last, value, period,
    interval } = model
  const sliderId = useId()
  const sliderLabel = `${sliderId}-label`
  const change = point && last?.value != null ? formatChange(point.median - last.value, data.unit) : null
  return <div className="forecast-content min-w-0 flex flex-col gap-6">
    {point && <Readout context={`${period(point.period)} · medijan prognoze`} median={point.median} format={value}>
      {/* One plain sentence instead of more mono label rows: the range, then the change against the last value. */}
      <p className="forecast-summary m-0 text-[14px] leading-[1.4] text-fg-soft" data-slot="forecast-summary">
        <span data-slot="forecast-interval">{value(point.low)} – {value(point.high)} ({interval})</span>
        {change && last && <>{' · '}<span className="font-medium text-fg-loud">{change}</span>
          {` u odnosu na ${period(last.period)}${last.is_provisional ? ' (privremeno)' : last.is_estimated ? ' (procijenjeno)' : ''}`}</>}
      </p>
    </Readout>}
    {county.history.some((p) => p.value !== null) || point ? <div className="flex flex-col gap-3">
      <ForecastChart data={data} county={county} active={active} onSelect={selectPeriod} onHover={hoverPeriod} />
      {selectedPoint && <FieldGroup className="forecast-control">
        <Field>
          {/* Named for screen readers; on screen the chart above says what the slider moves. */}
          <FieldLabel id={sliderLabel} className="sr-only">
            {data.frequency === 'month' ? 'Mjesec prognoze' : 'Tjedan prognoze'}</FieldLabel>
          <Slider min={0} max={county.forecast.length - 1} step={1} value={[selected]}
            onValueChange={(values) => selectPeriod(Array.isArray(values) ? values[0] : values)}
            thumbProps={{ 'aria-labelledby': sliderLabel,
              'aria-valuetext': `${period(selectedPoint.period)}: ${value(selectedPoint.median)}, ${interval} `
                + `${value(selectedPoint.low)} – ${value(selectedPoint.high)}` }} />
        </Field>
      </FieldGroup>}
    </div> : null}
  </div>
}

const TABLE = `forecast-table w-full border-collapse text-right tabular-nums [&_caption]:text-left [&_caption]:p-3
  [&_caption]:text-fg-soft [&_th]:[padding:9px_12px] [&_th]:[border-top:1px_solid_var(--border)]
  [&_th]:whitespace-nowrap [&_td]:[padding:9px_12px] [&_td]:[border-top:1px_solid_var(--border)]
  [&_td]:whitespace-nowrap [&_th]:font-medium [&_th:first-child]:text-left [&_thead_th]:sticky
  [&_thead_th]:top-0 [&_thead_th]:text-fg-soft [&_.provisional]:m-0.5 [@media(max-width:_420px)]:[&_th]:p-2
  [@media(max-width:_420px)]:[&_td]:p-2`
const SCROLL = `forecast-table-scroll focus-visible:outline-none focus-visible:shadow-focus overflow-auto
  [max-height:290px] border border-border rounded-[10px]`

/** ForecastTables lists every forecast and history value exactly, with the change to the horizon. */
export function ForecastTables({ data, county }: { data: ForecastData; county: CountyForecast }) {
  const value = (n: number) => formatValue(n, data.unit)
  const period = (iso: string) => formatPeriod(iso, data.frequency)
  const end = county.forecast.at(-1)
  return <div className="forecast-tables flex flex-col gap-4">
    {end && county.change_to_horizon !== null && <p className="forecast-change m-0 text-[14px] text-fg-soft">
      <span className="font-medium text-fg-loud">{formatChange(county.change_to_horizon, data.unit)}</span>
      {` do ${formatPeriodGenitive(end.period, data.frequency)}, u odnosu na posljednji podatak`}
    </p>}
    {county.forecast.length > 0 && <div className={SCROLL} tabIndex={0} role="region" aria-label="Prognozirane vrijednosti">
      <Table variant="numeric" containerClassName="contents" className={TABLE}>
        <TableCaption>Sve prognozirane vrijednosti · {data.unit === 'percent' ? '%' : data.unit === 'persons' ? 'osobe' : 'oglasi'}</TableCaption>
        <TableHeader><TableRow><TableHead scope="col" sticky="header">{data.frequency === 'month' ? 'Mjesec' : 'Tjedan od'}</TableHead>
          <TableHead scope="col" sticky="header">Medijan</TableHead><TableHead scope="col" sticky="header">Donja granica</TableHead><TableHead scope="col" sticky="header">Gornja granica</TableHead></TableRow></TableHeader>
        <TableBody>{county.forecast.map((p) => <TableRow key={p.period} data-period={p.period} data-slot="forecast-row">
          <TableHead scope="row">{period(p.period).replace('tjedan od ', '')}</TableHead><TableCell>{value(p.median)}</TableCell>
          <TableCell>{value(p.low)}</TableCell><TableCell>{value(p.high)}</TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </div>}
    {county.history.length > 0 && <div className={SCROLL} tabIndex={0} role="region" aria-label="Povijesne vrijednosti">
      <Table variant="numeric" containerClassName="contents" className={TABLE}>
        <TableCaption>Povijesni podaci ({county.history.length})</TableCaption>
        <TableHeader><TableRow><TableHead scope="col" sticky="header">Razdoblje</TableHead><TableHead scope="col" sticky="header">Vrijednost</TableHead><TableHead scope="col" sticky="header">Status</TableHead></TableRow></TableHeader>
        <TableBody>{county.history.map((p) => <TableRow key={p.period}><TableHead scope="row">{period(p.period)}</TableHead>
          <TableCell>{p.value === null ? 'nema podatka' : value(p.value)}</TableCell>
          <TableCell>{p.value === null ? 'nedostaje' : p.is_estimated || p.is_provisional ? <Flags point={p} /> : 'objavljeno'}</TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </div>}
  </div>
}

// The interval is the red wash, edged in accent-300 so it still reads as red on the dark card.
const WASH_KEY = 'bg-accent-wash border border-accent-300/60'
const HEIGHT = 240

/** legendKey draws a legend entry's line or swatch; spans, since ChartLegendContent sizes svg icons to a square. */
const legendKey = (className: string) => () => <span aria-hidden="true" className={`forecast-key w-4 ${className}`} />

// HistoryDot marks one known history value, isolated ones included, with its period and value.
function HistoryDot({ cx, cy, payload }: { cx?: number; cy?: number; payload?: ForecastRow }) {
  if (cx == null || cy == null || payload?.value == null) return null
  return <circle cx={cx} cy={cy} r={2.5} className="forecast-observed-node fill-fg-soft" data-slot="history-node"
    data-value={payload.value} data-period={payload.period} />
}

function ForecastChart({ data, county, active, onSelect, onHover }: {
  data: ForecastData; county: CountyForecast; active: number
  onSelect: (index: number) => void; onHover: (index: number | null) => void
}) {
  const reduced = useReducedMotion()
  const { rows, runs } = forecastRows(county)
  const ticks = valueTicks(county, data.unit)
  const total = rows.length
  const start = county.history.length // the first forecast row
  const cursor = county.forecast[active]
  const flags = runs.some((run) => run.flagged)
  const interval = `${Math.round(data.interval * 100)}% interval`
  const config = {
    history: { label: 'Povijest', color: 'var(--fg-soft)', icon: legendKey('h-0 border-t-2 border-fg-soft') },
    // The median and its interval read as one thing, the forecast: one key, a dashed line over the wash.
    median: { label: `Prognoza · ${interval}`, color: 'var(--accent-500)', icon: () => <span aria-hidden="true"
      className={`forecast-key relative w-4 h-2.5 ${WASH_KEY} after:absolute after:inset-x-0 after:top-1/2
        after:border-t-2 after:border-dashed after:border-accent-500 after:-translate-y-1/2`} /> },
    range: { label: interval, color: 'var(--accent-wash)' },
    flagged: { label: 'privremeno', color: 'var(--fg-soft)',
      icon: legendKey('h-0 border-t-2 border-dashed border-fg-soft') },
  } satisfies ChartConfig
  const legend = (['history', ...(county.forecast.length ? ['median'] : []), ...(flags ? ['flagged'] : [])])
    .map((key) => ({ value: key, dataKey: key, type: 'line' as const, color: config[key as keyof typeof config].color }))
  const motion = { isAnimationActive: !reduced, animationBegin: MOTION.marks.at, animationDuration: MOTION.marks.duration }
  // The forecast row under the pointer; null over the history.
  const forecastIndex = (index: unknown) => {
    const row = Number(index)
    return index == null || Number.isNaN(row) || row < start ? null : row - start
  }
  const format = (value: number) => formatValue(value, data.unit)
  return <div className="forecast-chart" data-slot="forecast-chart">
    {/* Hover previews a forecast period and click selects it, as on the county chart; the slider is the
        keyboard route. */}
    <ChartContainer config={config} className={`forecast-plot aspect-auto w-full mono-label
      [&_.recharts-cartesian-axis-tick_text]:fill-fg-soft${county.forecast.length ? ' cursor-pointer' : ''}`}
      style={{ height: HEIGHT + 56 }} role="img"
      aria-label="Povijesne vrijednosti i Chronos prognoza; točne vrijednosti navedene su u tablicama.">
      <ComposedChart data={rows} margin={{ top: 12, right: 6, bottom: 0, left: 0 }} accessibilityLayer={false} throttledEvents={[]}
        onMouseMove={(state) => onHover(forecastIndex(state.activeTooltipIndex))}
        onMouseLeave={() => onHover(null)}
        onClick={(state) => {
          const index = forecastIndex(state.activeTooltipIndex)
          if (index !== null) onSelect(index)
        }}>
        <ChartLegend verticalAlign="top" align="left"
          content={() => <ChartLegendContent payload={legend} verticalAlign="top"
            className="forecast-legend flex-wrap justify-start [gap:8px_16px] pb-4 uppercase text-fg-soft" />} />
        <CartesianGrid vertical={false} strokeDasharray="3 4" className="forecast-grid [&_line]:stroke-border" />
        <XAxis dataKey="index" type="number" domain={[0, Math.max(1, total - 1)]} ticks={total > 1 ? [0, total - 1] : [0]}
          tickLine={false} axisLine={false} tickMargin={10} interval={0}
          tick={({ x, y, payload }) => <text x={x} y={y} dy={8} className="uppercase fill-fg-soft stroke-none"
            textAnchor={payload.value === 0 && total > 1 ? 'start' : 'end'}>
            {formatPeriod(rows[payload.value]?.period ?? '', data.frequency)}</text>} />
        <YAxis domain={[0, ticks.at(-1)!]} ticks={ticks} tickFormatter={format} tickLine={false} axisLine={false}
          width={64} />
        <ChartTooltip cursor={{ className: 'stroke-border' }} content={({ active, payload, label }) => {
          const row = payload?.[0]?.payload as ForecastRow | undefined
          if (!active || !row) return null
          const forecast = forecastIndex(label)
          const point = forecast === null ? undefined : county.forecast[forecast]
          const items = point
            ? [{ name: 'Medijan', value: format(point.median) }, { name: interval,
              value: `${format(point.low)} – ${format(point.high)}` }]
            : [{ name: 'Povijest', value: row.value === null ? 'nema podatka' : format(row.value) }]
          return <ChartTooltipContent active hideIndicator label={formatPeriod(row.period, data.frequency)}
            labelClassName="uppercase text-fg-loud"
            payload={items.map((item) => ({ ...item, dataKey: item.name, graphicalItemId: item.name }))}
            formatter={(value, name) => <span className="flex w-full justify-between gap-4">
              <span>{name}</span><span className="text-fg-loud">{String(value)}</span></span>} />
        }} />
        {county.forecast.length > 0 && <ReferenceLine x={start - 1 < 0 ? 0 : start - 1} strokeDasharray="2 5"
          className="forecast-boundary [&_line]:stroke-fg-soft [&_line]:[opacity:.5]" />}
        {county.forecast.length > 0 && <Area dataKey="range" type="linear" connectNulls={false} {...motion}
          className="forecast-band" fill="var(--color-range)" fillOpacity={1}
          stroke="var(--accent-300)" strokeOpacity={0.6} strokeWidth={1} activeDot={false} legendType="none" />}
        {runs.map((run) => <Line key={run.key} dataKey={run.key} type="linear" connectNulls={false} dot={false}
          activeDot={false} legendType="none" stroke="var(--color-history)" strokeWidth={2} {...motion}
          strokeDasharray={run.flagged ? '4 4' : undefined} className="forecast-observed"
          data-slot="history-run" data-from={run.from} data-to={run.to} data-flagged={run.flagged} />)}
        {/* The history's dots, isolated values included; the line itself is drawn per run above. */}
        <Line dataKey="value" stroke="none" connectNulls={false} dot={<HistoryDot />} activeDot={false}
          legendType="none" isAnimationActive={false} />
        {/* Projected values are dashed, like provisional history; red because the forecast is the focus. */}
        {county.forecast.length > 0 && <Line dataKey="median" type="linear" connectNulls={false}
          stroke="var(--color-median)" strokeWidth={2.5} strokeDasharray="6 4" className="forecast-predicted"
          dot={({ cx, cy, index }) => index < start ? <g key={index} /> :
            <circle key={index} cx={cx} cy={cy} r={2.5} className="forecast-predicted-node fill-accent-500" />}
          activeDot={false} legendType="none" {...motion} />}
        {cursor && <ReferenceLine segment={[{ x: start + active, y: cursor.low }, { x: start + active, y: cursor.high }]}
          className="forecast-range-line [&_line]:stroke-accent-500 [&_line]:[stroke-width:1.5]" />}
        {cursor && <ReferenceDot x={start + active} y={cursor.median} shape={({ cx, cy }: { cx?: number; cy?: number }) =>
          <g data-slot="forecast-cursor" data-period={cursor.period}>
            <circle cx={cx} cy={cy} r={5} className="forecast-active-node fill-accent-500 stroke-card [stroke-width:2]" />
          </g>} />}
      </ComposedChart>
    </ChartContainer>
  </div>
}
