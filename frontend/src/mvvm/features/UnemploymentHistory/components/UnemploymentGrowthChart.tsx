import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { type ChartConfig, ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent }
  from '@/components/ui/chart'
import { EmptyState } from '@/components/Card'
import { cn } from 'cn'
import { type KeyboardEvent, type PointerEvent, useId, useLayoutEffect, useRef } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, XAxis, YAxis } from 'recharts'
import { clearEntrance, EASE, enter, MOTION, roll, s, useChartEntrance, useCountUp, useReducedMotion }
  from '../../../hooks/chart-motion'
import { formatMonth, formatRate, formatShortMonth } from '../../../utils/format'
import { useChartWidth } from '../../../hooks/use-chart-size'
import { growthRows, provisionalBands, type GrowthRow } from '../utils/chart-data'
import { monthTicks, rateAxis } from '../utils/chart-geometry'
import type { useHistoryChart } from '../hooks/use-history-chart'

const HEIGHT = 360
const Y_AXIS = 52
const EDGE = 8

const config = {
  focus: { label: 'Odabrana županija', color: 'var(--accent-500)' },
  county: { label: 'Ostale županije', color: 'var(--surface-disable)' },
  provisional: { label: 'privremeni podaci', icon: () => <svg className="key h-3 w-7" viewBox="0 0 28 12" aria-hidden="true">
    <rect x="0" y="0" width="28" height="12" rx="3" className="key-band fill-surface-subdued" />
    <line x1="2" y1="6" x2="26" y2="6" className="key-dashed stroke-fg-soft [stroke-width:2] [stroke-linecap:round] [stroke-dasharray:4_3]" />
  </svg> },
  gap: { label: 'prekid: nema podatka', icon: () => <svg className="key h-3 w-7" viewBox="0 0 28 12" aria-hidden="true">
    <line x1="1" y1="6" x2="9" y2="6" className="key-solid stroke-fg-soft [stroke-width:2] [stroke-linecap:round]" />
    <line x1="19" y1="6" x2="27" y2="6" className="key-solid stroke-fg-soft [stroke-width:2] [stroke-linecap:round]" />
  </svg> },
} satisfies ChartConfig

function RateValue({ rate }: { rate: number }) {
  const ref = useRef<HTMLParagraphElement>(null)
  useCountUp(ref, rate, formatRate)
  return <p ref={ref} className="growth-value m-0 mono-headline whitespace-nowrap text-fg-loud"
    data-slot="growth-readout-value" data-value={rate}>{formatRate(rate)}</p>
}

function growthNode({ id, key, rows, active, dense, lit, layer }: { id: string; key: string; rows: GrowthRow[];
  active: number; dense: boolean; lit: boolean; layer: string }) {
  return function GrowthNode({ cx, cy, index }: { cx?: number; cy?: number; index?: number }) {
    const row = index == null ? undefined : rows[index]
    const rate = row?.[key]
    if (cx == null || cy == null || index == null || !row || typeof rate !== 'number') return <g key={index} />
    const isolated = typeof rows[index - 1]?.[key] !== 'number' && typeof rows[index + 1]?.[key] !== 'number'
    if (dense && index !== active && index !== 0 && index !== rows.length - 1 && !isolated) return <g key={index} />
    return <g key={index} data-slot={lit ? 'growth-focus-node' : 'growth-node'} data-series={id} data-index={index}
      data-period={row.period} data-rate={rate} className={cn('growth-node fill-current', layer, lit ? 'text-accent-500' : 'text-surface-disable', index === active && 'is-active')}>
      <circle cx={cx} cy={cy} r={index === active ? 6 : 4.5} className="growth-node-shell fill-card" />
      <circle cx={cx} cy={cy} r={index === active ? 4.5 : 3} />
    </g>
  }
}

export function UnemploymentGrowthChart(model: ReturnType<typeof useHistoryChart>) {
  const { series, points, active, point, valueText, selectMonth, hoverMonth, navigate,
    selectedSeries, activeSeries, selectSeries, hoverSeries, navigateSeries } = model
  const root = useRef<HTMLDivElement>(null)
  const nameRef = useRef<HTMLParagraphElement>(null)
  const [plot, measuredWidth] = useChartWidth<HTMLDivElement>()
  const plotWidth = Math.max(1, (measuredWidth || 591) - Y_AXIS - 2 * EDGE)
  const reduced = useReducedMotion()
  const id = useId().replace(/[^\w-]/g, '')
  const known = points.flatMap((point) => series.flatMap((s) => point.values[s.id].rate ?? []))
  const axis = rateAxis(known)
  const { rows, runs } = growthRows({ series, points })
  const bands = provisionalBands(points)
  const gaps = points.some((p) => series.some((s) => p.values[s.id].rate === null))
  const ticks = monthTicks(points.length, plotWidth)
  const dense = points.length > 1 && plotWidth / (points.length - 1) < 20
  const focused = series[activeSeries]
  const reading = focused && point?.values[focused.id]
  const last = points.length - 1
  const all = <T extends Element>(selector: string) => [...root.current?.querySelectorAll<T>(selector) ?? []]
  const legend = [...(bands.length ? ['provisional'] : []), ...(gaps ? ['gap'] : [])]
    .map((key) => ({ value: key, dataKey: key, type: 'line' as const, color: 'var(--fg-soft)' }))
  const motion = { isAnimationActive: !reduced, animationBegin: MOTION.marks.at, animationDuration: MOTION.marks.duration }
  const at = (index: unknown) => index == null || Number.isNaN(Number(index)) ? null : Number(index)

  useChartEntrance(root, (timeline) => {
    const stats = all<HTMLElement>('[data-slot="growth-readout-value"]')
    const readout = all<HTMLElement>('[data-slot="readout"] > *')
    const legendItems = all<HTMLElement>('[data-slot="legend-county"]')
    const state = { count: 0 }
    const count = () => stats.forEach((el) => { el.textContent = formatRate(Number(el.dataset.value) * state.count) })
    count()
    const { headline, labels } = MOTION
    enter(timeline, readout, MOTION.readout.at, MOTION.readout)
    timeline.fromTo(state, { count: 0 }, { count: 1, duration: s(headline.duration), ease: EASE.arrive, onUpdate: count },
      s(headline.at))
    enter(timeline, legendItems, labels.at)
    return () => {
      clearEntrance([...readout, ...legendItems])
      stats.forEach((el) => { el.textContent = formatRate(Number(el.dataset.value)) })
    }
  })

  const lastSeries = useRef(activeSeries)
  useLayoutEffect(() => {
    const before = lastSeries.current
    lastSeries.current = activeSeries
    if (!nameRef.current || reduced || before === activeSeries) return
    roll(nameRef.current)
  }, [activeSeries, reduced])

  function touchedMonth(event: PointerEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - box.left - Y_AXIS - EDGE) / Math.max(1, box.width - Y_AXIS - 2 * EDGE)
    return Math.min(last, Math.max(0, Math.round(x * last)))
  }
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (navigate(event.key)) event.preventDefault()
  }
  function onCountyKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const index = navigateSeries(event.key)
    if (index === null) return
    event.preventDefault()
    all<HTMLButtonElement>('[data-slot="legend-county"]')[index]?.focus()
  }
  const layer = (lit: boolean, i: number) => lit
    ? cn('growth-focus [transition:opacity_300ms] motion-reduce:[transition:none]',
      i === activeSeries ? 'opacity-100' : 'opacity-0')
    : 'growth-series [opacity:0.5]'

  return (
    <div className="growth-chart flex flex-col gap-6 min-w-0" ref={root} data-slot="unemployment-growth-chart">
      {known.length === 0 ? <div ref={plot}><EmptyState>Za odabrano razdoblje nema poznatih stopa nezaposlenosti.</EmptyState></div> : <>
        {focused && point && <div className="readout flex flex-col items-start gap-2.5" data-slot="readout">
          {
                                                                }
          <div className="overflow-clip">
            <p className="growth-readout-name m-0 flex min-h-5 flex-wrap items-center gap-1.5 mono-label text-fg-soft"
              ref={nameRef}>
              <span>{focused.label} · <span className="uppercase">{formatMonth(point.period)}</span></span>
              {reading?.is_provisional && <Badge variant="provisional" className="provisional">privremeno</Badge>}
            </p>
          </div>
          {reading?.rate != null ? <RateValue rate={reading.rate} />
            : <p className="growth-missing m-0 text-[16px] leading-[28px] text-fg-soft">nema podatka</p>}
        </div>}
        <div className="legend growth-legend flex flex-col gap-2" data-slot="legend">
          <div className="legend-counties flex flex-wrap gap-1" role="group" aria-label="Županije"
            onPointerLeave={() => hoverSeries(null)}>
            {series.map((s, i) => {
              const value = point?.values[s.id]
              const rate = value?.rate == null ? 'nema podatka' : formatRate(value.rate)
              const lit = i === activeSeries
              return <Button variant="ghost" key={s.id} type="button" data-slot="legend-county"
                className={cn('legend-county relative h-7 gap-2 rounded-full px-3 mono-label',
                  'text-fg-soft transition-[background-color,color] duration-300 motion-reduce:transition-none',
                  'focus-visible:border-transparent focus-visible:ring-0',
                  lit && 'active bg-surface-muted font-medium text-fg-on-muted hover:bg-surface-muted hover:text-fg-on-muted')}
                title={s.label} aria-label={`${s.label}, ${point ? formatMonth(point.period) + ': ' : ''}${rate}`
                  + (value?.is_provisional ? ', privremeno' : '')}
                aria-pressed={i === selectedSeries} tabIndex={i === selectedSeries ? 0 : -1}
                onPointerEnter={() => hoverSeries(i)} onClick={() => selectSeries(i)} onKeyDown={onCountyKeyDown}>
                <span className={cn('swatch h-[3px] w-3 flex-none rounded-[2px] transition-colors duration-300 motion-reduce:transition-none',
                  lit ? 'bg-accent-500' : 'bg-surface-disable')} aria-hidden="true" />
                {s.shortLabel}
                <span>{rate}</span>
                {                                   }
                <span className="focus-ring pointer-events-none absolute -inset-1 rounded-full opacity-0 shadow-focus
                  transition-opacity duration-150 group-focus-visible/button:opacity-100" aria-hidden="true" />
              </Button>
            })}
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <p className="growth-plot-heading m-0 mono-label uppercase text-fg-soft">Stopa registrirane nezaposlenosti (%)</p>
          {
                                                                                            }
          <div ref={plot} role="slider" tabIndex={0} className="growth-scrubber relative min-w-0 cursor-crosshair
            touch-pan-y rounded-[8px] [outline:none] [&:focus-visible]:shadow-focus" aria-label="Odabrani mjesec"
            aria-describedby={`${id}-hint`} aria-orientation="horizontal" aria-valuemin={0} aria-valuemax={last}
            aria-valuenow={active} aria-valuetext={valueText} data-period={point?.period} onKeyDown={onKeyDown}
            onPointerDown={(event) => {
              if (event.pointerType === 'mouse' || event.button !== 0) return
              event.currentTarget.setPointerCapture(event.pointerId)
              selectMonth(touchedMonth(event))
            }}
            onPointerMove={(event) => {
              if (event.currentTarget.hasPointerCapture(event.pointerId)) selectMonth(touchedMonth(event))
            }}>
            <ChartContainer config={config} aria-hidden="true" className="growth-plot aspect-auto w-full mono-label
              [&_.recharts-cartesian-axis-tick_text]:fill-fg-soft" style={{ height: HEIGHT + (legend.length ? 40 : 0) }}>
              <ComposedChart data={rows} margin={{ top: 14, right: EDGE, bottom: 0, left: 0 }} accessibilityLayer={false} throttledEvents={[]}
                onMouseMove={(state) => hoverMonth(at(state.activeTooltipIndex))}
                onMouseLeave={() => hoverMonth(null)}
                onClick={(state) => { const index = at(state.activeTooltipIndex); hoverMonth(null); if (index !== null) selectMonth(index) }}>
                <defs>
                  <pattern id={`${id}-hatch`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <line x1="0" y1="0" x2="0" y2="6" className="growth-hatch stroke-surface-disable [stroke-width:1] [opacity:0.35]" />
                  </pattern>
                  <linearGradient id={`${id}-fade`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor="var(--color-focus)" stopOpacity="0.14" />
                    <stop offset="1" stopColor="var(--color-focus)" stopOpacity="0" />
                  </linearGradient>
                </defs>
                {legend.length > 0 && <ChartLegend verticalAlign="top" align="left"
                  content={() => <ChartLegendContent payload={legend} verticalAlign="top" className="legend-keys
                    flex-wrap justify-start [gap:6px_16px] pb-4 uppercase text-fg-soft [&>div]:gap-2" />} />}
                <CartesianGrid vertical={false} strokeDasharray="5 5" className="growth-grid [&_line]:stroke-border" />
                <XAxis dataKey="index" type="number" domain={[0, Math.max(1, last)]} ticks={ticks} interval={0}
                  padding={{ left: EDGE, right: 0 }} tickLine={false} axisLine={{ className: 'stroke-border' }} tickMargin={8}
                  tick={({ x, y, payload }) => {
                    const index = payload.value as number
                    const position = ticks.indexOf(index)
                    const withYear = position === 0 || index === last ||
                      points[index].period.slice(0, 4) !== points[ticks[position - 1]].period.slice(0, 4)
                    return <text x={x} y={y} dy={8} className="growth-x-label uppercase fill-fg-soft stroke-none" data-index={index}
                      textAnchor={index === last && last > 0 ? 'end' : index === 0 ? 'start' : 'middle'}>
                      {formatShortMonth(points[index].period, withYear)}</text>
                  }} />
                <YAxis domain={[axis.low, axis.high]} ticks={axis.ticks} tickFormatter={formatRate} width={Y_AXIS}
                  tickLine={false} axisLine={{ className: 'stroke-border' }} orientation="left" />
                {bands.map((band) => <ReferenceArea key={band.first} x1={Math.max(0, band.first - 0.5)}
                  x2={Math.min(last, band.last + 0.5)} fill={`url(#${id}-hatch)`} fillOpacity={1}
                  className="growth-provisional-band" />)}
                <ReferenceLine x={active} strokeDasharray="4 4" className="growth-cursor [&_line]:stroke-fg-soft
                  [&_line]:[stroke-width:1.5]" />
                <ChartTooltip cursor={false} content={({ active: shown, label }) => {
                  const index = at(label)
                  if (!shown || index === null || !points[index]) return null
                  return <ChartTooltipContent active hideIndicator label={formatMonth(points[index].period)}
                    labelClassName="uppercase text-fg-loud"
                    payload={series.map((s) => {
                      const value = points[index].values[s.id]
                      return { name: s.shortLabel, dataKey: s.id, graphicalItemId: s.id,
                        value: value.rate === null ? 'nema podatka' : formatRate(value.rate) + (value.is_provisional ? ' *' : '') }
                    })}
                    formatter={(value, name) => <span className="flex w-full justify-between gap-4">
                      <span>{name}</span><span className="text-fg-loud">{String(value)}</span></span>} />
                }} />
                {[false, true].flatMap((lit) => series.flatMap((s, i) => [
                  ...(lit ? runs[i].map((run) => <Area key={`a${run.key}`} dataKey={run.key} type="monotone"
                    connectNulls={false} fill={`url(#${id}-fade)`} fillOpacity={1} stroke="none" activeDot={false}
                    legendType="none" className={layer(true, i)} {...motion} />) : []),
                  ...runs[i].map((run) => <Line key={`${lit ? 'l' : 'g'}${run.key}`} dataKey={run.key} type="monotone"
                    connectNulls={false} dot={false} activeDot={false} legendType="none" {...motion}
                    stroke={lit ? 'var(--color-focus)' : 'var(--color-county)'} strokeWidth={2} strokeLinecap="round"
                    strokeDasharray={run.provisional ? '5 4' : undefined} className={layer(lit, i)}
                    data-slot={lit ? 'growth-focus-line' : 'growth-line'} data-series={s.id} data-lit={lit && i === activeSeries}
                    data-from={run.from} data-to={run.to} data-provisional={run.provisional} />),
                  <Line key={`${lit ? 'l' : 'g'}n${i}`} dataKey={`s${i}`} stroke="none" legendType="none"
                    isAnimationActive={false} activeDot={false} className={layer(lit, i)}
                    dot={growthNode({ id: s.id, key: `s${i}`, rows, active, dense, lit, layer: layer(lit, i) })} />,
                ]))}
              </ComposedChart>
            </ChartContainer>
          </div>
        </div>
        <p id={`${id}-hint`} className="growth-hint -mt-2 mb-0 text-fg-soft text-[12px] leading-[1.25]">
          Po mjesecima · pomaknite pokazivač ili birajte mjesec strelicama; županiju birajte u legendi.</p>
      </>}
    </div>
  )
}
