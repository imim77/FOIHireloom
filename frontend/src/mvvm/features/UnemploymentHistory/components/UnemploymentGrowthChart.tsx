import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/Card'
import { cn } from 'cn'
// Local adaptation of the supplied Keitoto RevenueGrowthChart in the jobs-by-county look: every county is a grey
// curve and the focused one is lit orange over them, with its rate for the inspected month read out above the chart.
// The legend picks the county (hover previews, click or the arrow keys select); the plot's scrubber picks the month.
// Rates retain the original DZS gaps and provenance; provisional runs are dashed.
import { animate, stagger } from 'animejs'
import { type KeyboardEvent, type PointerEvent, useId, useLayoutEffect, useRef } from 'react'
import { fadeIn, finish, releaseStyles, useChartEntrance, useCountUp, useReducedMotion } from '../../../hooks/chart-motion'
import { formatMonth, formatRate, formatShortMonth } from '../../../utils/format'
import { useChartWidth } from '../../../hooks/use-chart-size'
import { provisionalBands, seriesRuns, type GrowthPoint, type GrowthSeries } from '../utils/chart-data'
import { areaPath, curvePath, monthTicks, rateAxis } from '../utils/chart-geometry'
import type { useHistoryChart } from '../hooks/use-history-chart'

const HEIGHT = 360
const TOP = 14
const BOTTOM = HEIGHT - 14
const EDGE = 8
const DRAW_AT = 250
const DRAW_DURATION = 1400

/** The focused county's rate, counting from the number on screen when the county or month changes. */
function RateValue({ rate }: { rate: number }) {
  const ref = useRef<HTMLParagraphElement>(null)
  useCountUp(ref, rate, formatRate)
  return <p ref={ref} className="growth-value m-0 text-[28px] font-semibold leading-[1] whitespace-nowrap tabular-nums"
    data-slot="growth-readout-value" data-value={rate}>{formatRate(rate)}</p>
}

/** SeriesShape draws one county's runs and month nodes, grey for the backdrop or lit for the copy laid over it. */
function SeriesShape({ series, points, active, x, y, step, lit, fill }: {
  series: GrowthSeries
  points: GrowthPoint[]
  active: number
  x: (index: number) => number
  y: (rate: number) => number
  step: number
  lit: boolean
  fill: string
}) {
  const runs = seriesRuns(points, series.id)
  return <>
    {runs.filter((run) => run.indices.length > 1).map((run) => {
      const coords = run.indices.map((index) => ({ x: x(index), y: y(points[index].values[series.id].rate!) }))
      return <g key={run.indices[0]}>
        {lit && <path data-slot="growth-area" d={areaPath(coords, BOTTOM)} fill={fill} />}
        <path data-slot={lit ? 'growth-focus-line' : 'growth-line'} data-from={points[run.indices[0]].period}
          data-to={points[run.indices.at(-1)!].period} data-provisional={run.provisional} d={curvePath(coords)}
          className="growth-line fill-none stroke-current [stroke-width:2] [stroke-linecap:round] [stroke-linejoin:round]"
          strokeDasharray={run.provisional ? '5 4' : undefined} />
      </g>
    })}
    {points.map((p, index) => {
      const value = p.values[series.id]
      if (value.rate === null) return null
      const isolated = (points[index - 1]?.values[series.id].rate ?? null) === null &&
        (points[index + 1]?.values[series.id].rate ?? null) === null
      if (step < 20 && index !== active && index !== 0 && index !== points.length - 1 && !isolated) return null
      return <g key={p.period} data-slot={lit ? 'growth-focus-node' : 'growth-node'} data-index={index}
        data-period={p.period} data-rate={value.rate}
        className={`growth-node fill-current [transform-box:fill-box] [transform-origin:center]${index === active ? ' is-active' : ''}`}>
        <circle cx={x(index)} cy={y(value.rate)} r={index === active ? 6 : 4.5} className="growth-node-shell fill-card" />
        <circle cx={x(index)} cy={y(value.rate)} r={index === active ? 4.5 : 3} />
      </g>
    })}
  </>
}

export function UnemploymentGrowthChart(model: ReturnType<typeof useHistoryChart>) {
  const { series, points, active, point, valueText, selectMonth, hoverMonth, navigate,
    selectedSeries, activeSeries, selectSeries, hoverSeries, navigateSeries } = model
  const root = useRef<HTMLDivElement>(null)
  const cursor = useRef<SVGGElement>(null)
  const wipe = useRef<SVGRectElement>(null)
  const nameRef = useRef<HTMLParagraphElement>(null)
  const [plot, measuredWidth] = useChartWidth<HTMLDivElement>()
  const width = Math.max(2 * EDGE + 1, measuredWidth || 591)
  const reduced = useReducedMotion()
  const id = useId().replace(/[^\w-]/g, '')
  const known = points.flatMap((point) => series.flatMap((s) => point.values[s.id].rate ?? []))
  const axis = rateAxis(known)
  const step = points.length > 1 ? (width - 2 * EDGE) / (points.length - 1) : 0
  const x = (index: number) => points.length > 1 ? EDGE + index * step : width - EDGE
  const y = (rate: number) => BOTTOM - (rate - axis.low) / (axis.high - axis.low) * (BOTTOM - TOP)
  const cursorX = x(active)
  const bands = provisionalBands(points)
  const gaps = points.some((p) => series.some((s) => p.values[s.id].rate === null))
  const ticks = monthTicks(points.length, width - 2 * EDGE)
  const drawnX = useRef(cursorX)
  const previousWidth = useRef(width)
  const focused = series[activeSeries]
  const reading = focused && point?.values[focused.id]
  const all = <T extends Element>(selector: string) => [...root.current?.querySelectorAll<T>(selector) ?? []]

  // Entrance: the readout comes in and its rate counts up, the grid draws, the curves wipe in from the left with
  // their nodes popping as the wipe passes them, then the legend comes in.
  useChartEntrance(root, (timeline) => {
    const stats = all<HTMLElement>('[data-slot="growth-readout-value"]')
    const readout = all<HTMLElement>('[data-slot="readout"] > *')
    const legend = all<HTMLElement>('[data-slot="legend-county"], [data-slot="legend-key"]')
    const grid = all<SVGLineElement>('[data-slot="growth-grid"]')
    const nodes = all<SVGGElement>('.growth-node')
    const cursorNode = cursor.current
    const state = { progress: 0, count: 0 }
    const reveal = () => wipe.current?.setAttribute('width', `${state.progress * 100}%`)
    const count = () => stats.forEach((el) => { el.textContent = formatRate(Number(el.dataset.value) * state.count) })
    reveal()
    count()
    timeline.add(readout, { ...fadeIn(readout, 6), duration: 600, delay: stagger(80) }, 100)
    timeline.add(state, { count: [0, 1], duration: 1400, ease: 'outExpo', onUpdate: count }, 150)
    timeline.add(legend, { ...fadeIn(legend, 4), duration: 600, delay: stagger(50) }, 350)
    if (grid.length) timeline.add(grid, { scaleX: { from: 0 }, duration: 850, delay: stagger(40), ease: 'outQuad',
      onComplete: releaseStyles('transform') }, 100)
    timeline.add(state, { progress: [0, 1], duration: DRAW_DURATION, ease: 'inOutSine', onUpdate: reveal }, DRAW_AT)
    for (const node of nodes) {
      const index = Number(node.dataset.index)
      timeline.add(node, { scale: { from: 0 }, opacity: { from: 0 }, duration: 450, ease: 'outBack(2)',
        onComplete: releaseStyles('transform', 'opacity') }, DRAW_AT + (index / Math.max(1, points.length - 1)) * DRAW_DURATION)
    }
    if (cursorNode) timeline.add(cursorNode, { opacity: { from: 0 }, duration: 400 }, DRAW_AT + DRAW_DURATION - 250)
    return () => {
      wipe.current?.setAttribute('width', '100%')
      for (const el of [...readout, ...legend, ...grid, ...nodes, ...(cursorNode ? [cursorNode] : [])]) {
        el.style.removeProperty('opacity')
        el.style.removeProperty('transform')
      }
      stats.forEach((el) => { el.textContent = formatRate(Number(el.dataset.value)) })
    }
  })

  // Ride between months as in the reference; a resize redraws at the correct coordinates immediately.
  useLayoutEffect(() => {
    const node = cursor.current
    if (!node) return
    const from = drawnX.current
    const resized = previousWidth.current !== width
    previousWidth.current = width
    const settle = () => { drawnX.current = cursorX; node.style.removeProperty('transform') }
    if (reduced || resized || from === cursorX) { settle(); return }
    const state = { x: from }
    const paint = () => {
      drawnX.current = state.x
      node.style.transform = `translateX(${state.x - cursorX}px)`
    }
    paint()
    const ride = finish(animate(state, { x: cursorX, duration: 450, ease: 'outExpo', onUpdate: paint, onComplete: settle }))
    return () => { ride.cancel(); node.style.removeProperty('transform') }
  }, [cursorX, width, reduced])

  // A new county fades its name in; its rate counts over in RateValue and the curves cross-fade in CSS.
  const lastSeries = useRef(activeSeries)
  useLayoutEffect(() => {
    const before = lastSeries.current
    lastSeries.current = activeSeries
    if (!nameRef.current || reduced || before === activeSeries) return
    finish(animate(nameRef.current, { opacity: [0.4, 1], duration: 300, ease: 'outQuad', onComplete: releaseStyles('opacity') }))
  }, [activeSeries, reduced])

  function pointAt(event: PointerEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    const localX = (event.clientX - box.left) / (box.width || 1) * width
    return step ? Math.min(points.length - 1, Math.max(0, Math.round((localX - EDGE) / step))) : 0
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

  return (
    <div className="growth-chart flex flex-col gap-6 min-w-0
      [&_[data-slot='growth-grid']]:[transform-box:fill-box]
      [&_[data-slot='growth-grid']]:[transform-origin:left]" ref={root} data-slot="unemployment-growth-chart">
      {known.length === 0 ? <div ref={plot}><EmptyState>Za odabrano razdoblje nema poznatih stopa nezaposlenosti.</EmptyState></div> : <>
        {focused && point && <div className="readout flex flex-col items-start gap-2.5" data-slot="readout">
          <p className="growth-readout-name m-0 flex min-h-5 flex-wrap items-center gap-1.5 text-[12px] font-medium leading-[1.25] text-fg-soft"
            ref={nameRef}>
            {focused.label} · {formatMonth(point.period)}
            {reading?.is_provisional && <Badge variant="provisional" className="provisional">privremeno</Badge>}
          </p>
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
                className={cn('legend-county relative h-7 gap-1.5 rounded-[8px] px-2 text-[12px] font-medium leading-[1.25]',
                  'text-fg-soft tabular-nums transition-[background-color,color] duration-300 motion-reduce:transition-none',
                  'focus-visible:border-transparent focus-visible:ring-0',
                  lit && 'active bg-surface-muted font-semibold text-fg-on-muted hover:bg-surface-muted hover:text-fg-on-muted')}
                title={s.label} aria-label={`${s.label}, ${point ? formatMonth(point.period) + ': ' : ''}${rate}`
                  + (value?.is_provisional ? ', privremeno' : '')}
                aria-pressed={i === selectedSeries} tabIndex={i === selectedSeries ? 0 : -1}
                onPointerEnter={() => hoverSeries(i)} onClick={() => selectSeries(i)} onKeyDown={onCountyKeyDown}>
                <span className={cn('swatch h-[3px] w-3 flex-none rounded-[2px] transition-colors duration-300 motion-reduce:transition-none',
                  lit ? 'bg-orange-500' : 'bg-surface-disable')} aria-hidden="true" />
                {s.shortLabel}
                <span className="font-medium">{rate}</span>
                {/* keyboard focus rings the chip */}
                <span className="focus-ring pointer-events-none absolute -inset-1 rounded-[12px] opacity-0 shadow-focus
                  transition-opacity duration-150 group-focus-visible/button:opacity-100" aria-hidden="true" />
              </Button>
            })}
          </div>
          {(bands.length > 0 || gaps) && <ul className="legend-keys m-0 flex flex-wrap [gap:6px_16px] p-0 [list-style:none]
            text-[12px] font-medium leading-[1.25] text-fg-soft [&_li]:inline-flex [&_li]:items-center [&_li]:gap-1.5">
            {bands.length > 0 && <li data-slot="legend-key"><svg className="key h-3 w-7" viewBox="0 0 28 12" aria-hidden="true">
              <rect x="0" y="0" width="28" height="12" rx="3" className="key-band fill-surface-subdued" />
              <line x1="2" y1="6" x2="26" y2="6" className="key-dashed stroke-fg-soft [stroke-width:2] [stroke-linecap:round] [stroke-dasharray:4_3]" />
            </svg>privremeni podaci</li>}
            {gaps && <li data-slot="legend-key"><svg className="key h-3 w-7" viewBox="0 0 28 12" aria-hidden="true">
              <line x1="1" y1="6" x2="9" y2="6" className="key-solid stroke-fg-soft [stroke-width:2] [stroke-linecap:round]" />
              <line x1="19" y1="6" x2="27" y2="6" className="key-solid stroke-fg-soft [stroke-width:2] [stroke-linecap:round]" />
            </svg>prekid: nema podatka</li>}
          </ul>}
        </div>
        <div className="flex flex-col gap-2">
          <p className="growth-plot-heading m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">Stopa registrirane nezaposlenosti (%)</p>
          <div className="growth-axes flex gap-3 min-w-0 [@media(max-width:_400px)]:gap-2">
            <div className="growth-y-axis relative flex-none min-w-11 text-fg-soft text-[12px] tabular-nums [&_span]:absolute
              [&_span]:left-0 [&_span]:whitespace-nowrap [&_span]:[transform:translateY(-50%)]" aria-hidden="true" style={{ height: HEIGHT }}>
              {axis.ticks.map((tick) => <span key={tick} style={{ top: y(tick) }}>{formatRate(tick)}</span>)}
            </div>
            <div className="growth-plot-column flex-1 min-w-0">
              <div className="growth-plot relative [&_>_svg]:block [&_>_svg]:w-full [&_>_svg]:overflow-visible" ref={plot} style={{ height: HEIGHT }}>
                <svg aria-hidden="true" viewBox={`0 0 ${width} ${HEIGHT}`} width={width} height={HEIGHT}>
                  <defs>
                    <clipPath id={`${id}-wipe`}><rect ref={wipe} x="0" y="0" width="100%" height={HEIGHT} /></clipPath>
                    <pattern id={`${id}-hatch`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                      <line x1="0" y1="0" x2="0" y2="6" className="growth-hatch stroke-surface-disable [stroke-width:1] [opacity:0.35]" />
                    </pattern>
                    <linearGradient id={`${id}-fade`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0" className="[stop-color:var(--orange-500)]" stopOpacity="0.14" />
                      <stop offset="1" className="[stop-color:var(--orange-500)]" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  {bands.map((band) => <rect key={band.first} data-slot="growth-provisional-band"
                    x={Math.max(0, x(band.first) - step / 2)} y={TOP}
                    width={Math.min(width, x(band.last) + step / 2) - Math.max(0, x(band.first) - step / 2)}
                    height={BOTTOM - TOP} fill={`url(#${id}-hatch)`} />)}
                  <g ref={cursor} className="growth-cursor fill-fg-soft [&_line]:stroke-fg-soft [&_line]:[stroke-width:1.5]" data-slot="growth-cursor">
                    <line x1={cursorX} x2={cursorX} y1={TOP + 9} y2={BOTTOM - 9} strokeDasharray="4 4" />
                    <polygon points={`${cursorX - 5},${TOP} ${cursorX + 5},${TOP} ${cursorX},${TOP + 9}`} />
                    <polygon points={`${cursorX - 5},${BOTTOM} ${cursorX + 5},${BOTTOM} ${cursorX},${BOTTOM - 9}`} />
                  </g>
                  <line x1="0.5" x2="0.5" y1={TOP} y2={BOTTOM} className="growth-axis stroke-border [stroke-width:1]" />
                  {axis.ticks.map((tick, index) => <line key={tick} data-slot="growth-grid" x1="0" x2={width} y1={y(tick)} y2={y(tick)}
                    className={index === 0 ? 'growth-axis stroke-border [stroke-width:1]' : 'growth-grid stroke-border [stroke-width:1]'}
                    strokeDasharray={index === 0 ? undefined : '5 5'} />)}
                  <g clipPath={`url(#${id}-wipe)`}>
                    {/* The grey world: every county, in request order, never changing with focus. */}
                    {series.map((s) => <g key={s.id} data-series={s.id} className="growth-series text-surface-disable [opacity:0.5]">
                      <SeriesShape series={s} points={points} active={active} x={x} y={y} step={step} lit={false} fill="" />
                    </g>)}
                    {/* Lit copies over all grey curves, so the focus is never painted under another county; only the
                        focused one is visible and a new focus cross-fades. */}
                    {series.map((s, i) => <g key={s.id} data-focus-series={s.id} data-lit={i === activeSeries}
                      className={cn('growth-focus text-orange-500 [transition:opacity_300ms] motion-reduce:[transition:none]',
                        i === activeSeries ? 'opacity-100' : 'opacity-0')}>
                      <SeriesShape series={s} points={points} active={active} x={x} y={y} step={step} lit fill={`url(#${id}-fade)`} />
                    </g>)}
                  </g>
                </svg>
                <div role="slider" tabIndex={0} className="growth-scrubber absolute inset-0 cursor-crosshair touch-pan-y rounded-[8px] [outline:none]
                  [&:focus-visible]:shadow-focus" aria-label="Odabrani mjesec"
                  aria-describedby={`${id}-hint`} aria-orientation="horizontal" aria-valuemin={0} aria-valuemax={points.length - 1}
                  aria-valuenow={active} aria-valuetext={valueText} data-period={point?.period}
                  onKeyDown={onKeyDown} onPointerMove={(event) => {
                    const index = pointAt(event)
                    if (event.currentTarget.hasPointerCapture(event.pointerId)) selectMonth(index)
                    else if (event.pointerType === 'mouse') hoverMonth(index)
                  }} onPointerLeave={() => hoverMonth(null)} onPointerCancel={() => hoverMonth(null)}
                  onPointerDown={(event) => {
                    if (event.button !== 0) return
                    if (event.pointerType !== 'mouse') event.currentTarget.setPointerCapture(event.pointerId)
                    hoverMonth(null)
                    selectMonth(pointAt(event))
                  }} onPointerUp={(event) => {
                    if (event.button !== 0) return
                    hoverMonth(null)
                    selectMonth(pointAt(event))
                    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
                  }} />
              </div>
              <div className="growth-x-axis relative h-6 mt-1 text-fg-soft text-[12px] [&_span]:absolute
                [&_span]:whitespace-nowrap [&_span]:[transform:translateX(-50%)] [&_.is-first]:[transform:none]
                [&_.is-last]:[transform:translateX(-100%)]" aria-hidden="true">
                {ticks.map((index, position) => {
                  const withYear = position === 0 || index === points.length - 1 ||
                    points[index].period.slice(0, 4) !== points[ticks[position - 1]].period.slice(0, 4)
                  return <span key={index} style={{ left: x(index) }} className={index === points.length - 1 ? 'is-last' : index === 0 ? 'is-first' : ''}>
                    {formatShortMonth(points[index].period, withYear)}
                  </span>
                })}
              </div>
            </div>
          </div>
        </div>
        <p id={`${id}-hint`} className="growth-hint -mt-2 mb-0 text-fg-soft text-[12px] leading-[1.25]">
          Po mjesecima · pomaknite pokazivač ili birajte mjesec strelicama; županiju birajte u legendi.</p>
      </>}
    </div>
  )
}
