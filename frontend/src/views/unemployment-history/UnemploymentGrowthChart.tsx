// Local adaptation of the supplied Keitoto RevenueGrowthChart: stat tiles, glowing curves and area fills,
// dashed grid, nodes and a scrubber with triangle caps. Rates retain the original DZS gaps and provenance.
import { animate, stagger } from 'animejs'
import { type KeyboardEvent, type PointerEvent, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { fadeIn, finish, releaseStyles, useChartEntrance, useCountUp, useReducedMotion } from '../../shared/chart-motion'
import { formatMonth, formatRate, formatShortMonth } from '../../shared/format'
import { useChartWidth } from '../../shared/use-chart-size'
import { provisionalBands, seriesRuns, toGrowthData, type GrowthSeries } from './chart-data'
import { areaPath, curvePath, monthTicks, rateAxis } from './chart-geometry'
import type { CountyHistory, UnemploymentPoint } from './types'

const HEIGHT = 360
const TOP = 14
const BOTTOM = HEIGHT - 14
const EDGE = 8
const DRAW_AT = 250
const DRAW_DURATION = 1400

function RateValue({ rate }: { rate: number }) {
  const ref = useRef<HTMLParagraphElement>(null)
  useCountUp(ref, rate, formatRate)
  return <p ref={ref} className="growth-value text-[24px] leading-[30px] font-semibold tabular-nums whitespace-nowrap
    [@media(max-width:_400px)]:text-[22px]" data-slot="growth-stat-value" data-value={rate}>{formatRate(rate)}</p>
}

function Stat({ series, value, period, onEmphasis }: {
  series: GrowthSeries
  value: UnemploymentPoint | undefined
  period: string | undefined
  onEmphasis: (id: string | null) => void
}) {
  return (
    <section className={`growth-stat flex flex-col items-start gap-3 min-w-0 p-4 rounded-[16px] bg-surface-sunken [&_p]:m-0
      [@media(max-width:_400px)]:p-3 [@media(max-width:_400px)]:gap-2 s${series.color}`} aria-label={`${series.label}, odabrani mjesec`}
      onPointerEnter={() => onEmphasis(series.id)} onPointerLeave={() => onEmphasis(null)}>
      <p className="growth-stat-name flex items-center gap-2 max-w-full text-fg-soft text-[12px] font-medium leading-[1.4]
        [@media(max-width:_400px)]:text-[11px] [@media(max-width:_400px)]:[overflow-wrap:anywhere]" title={series.label}>
        <span className="growth-legend-dot inline-block flex-none w-2.5 h-2.5 rounded-full [background:var(--series)]
          [box-shadow:0_0_0_2px_var(--card),_0_0_0_3px_color-mix(in_srgb,_var(--series)_30%,_transparent)]" aria-hidden="true" />{series.shortLabel}
      </p>
      <div className="growth-stat-reading flex flex-wrap items-baseline [gap:6px_10px]">
        {value?.rate != null ? <RateValue rate={value.rate} /> : <p className="growth-missing text-fg-soft text-[16px] leading-[30px]">nema podatka</p>}
        {period && <p className="growth-stat-month text-fg-soft text-[12px] leading-[1.4] [@media(max-width:_400px)]:text-[11px]">{formatMonth(period)}</p>}
      </div>
      {value?.is_provisional && <span className="provisional inline-block [padding:1px_6px] rounded-full text-[11px] font-medium leading-[1.4]
        whitespace-nowrap text-fg-soft [outline:1px_dashed_var(--fg-soft)] [outline-offset:-1px]">privremeno</span>}
    </section>
  )
}

export function UnemploymentGrowthChart({ counties }: { counties: CountyHistory[] }) {
  const data = useMemo(() => toGrowthData(counties), [counties])
  const { series, points } = data
  const root = useRef<HTMLDivElement>(null)
  const cursor = useRef<SVGGElement>(null)
  const wipe = useRef<SVGRectElement>(null)
  const [plot, measuredWidth] = useChartWidth<HTMLDivElement>()
  const width = Math.max(2 * EDGE + 1, measuredWidth || 591)
  const [selected, setSelected] = useState(points.length - 1)
  const [hovered, setHovered] = useState<number | null>(null)
  const [emphasis, setEmphasis] = useState<string | null>(null)
  const active = hovered ?? selected
  const point = points[active]
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

  useChartEntrance(root, (timeline) => {
    const all = <T extends Element>(selector: string) => [...root.current!.querySelectorAll<T>(selector)]
    const stats = all<HTMLElement>('[data-slot="growth-stat-value"]')
    const cards = all<HTMLElement>('.growth-stat')
    const grid = all<SVGLineElement>('[data-slot="growth-grid"]')
    const nodes = all<SVGGElement>('[data-slot="growth-node"]')
    const cursorNode = cursor.current
    const state = { progress: 0, count: 0 }
    const reveal = () => wipe.current?.setAttribute('width', `${state.progress * 100}%`)
    const count = () => stats.forEach((el) => { el.textContent = formatRate(Number(el.dataset.value) * state.count) })
    reveal()
    count()
    timeline.add(cards, { ...fadeIn(cards, 6), duration: 500, delay: stagger(70) }, 0)
    timeline.add(state, { count: [0, 1], duration: 1000, ease: 'outExpo', onUpdate: count }, 0)
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
      for (const el of [...cards, ...grid, ...nodes, ...(cursorNode ? [cursorNode] : [])]) {
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

  const select = (index: number) => setSelected(Math.min(points.length - 1, Math.max(0, index)))
  function pointAt(event: PointerEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    const localX = (event.clientX - box.left) / (box.width || 1) * width
    return step ? Math.min(points.length - 1, Math.max(0, Math.round((localX - EDGE) / step))) : 0
  }
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const next = ({ ArrowRight: active + 1, ArrowUp: active + 1, ArrowLeft: active - 1, ArrowDown: active - 1,
      Home: 0, End: points.length - 1 } as Record<string, number>)[event.key]
    if (next === undefined) return
    event.preventDefault()
    setHovered(null)
    select(next)
  }
  const valueText = point ? `${formatMonth(point.period)}: ${series.map((s) => {
    const value = point.values[s.id]
    return `${s.label}: ${value.rate === null ? 'nema podatka' : formatRate(value.rate)}${value.is_provisional ? ', privremeno' : ''}`
  }).join('; ')}` : ''

  return (
    <div className="growth-chart dark:[&_]:[--card:#18181b] dark:[&_]:[--fg-loud:#fafafa] dark:[&_]:[--fg-soft:#a1a1aa]
      dark:[&_]:[--border:#2e2e33] dark:[&_]:[--surface-subdued:#3f3f46] dark:[&_]:[--surface-sunken:#0f0f11]
      dark:[&_]:[--green-tint:#173322] dark:[&_]:[--green-on-tint:#86e0a8] dark:[&_]:[--surface-disable:#71717a]
      dark:[&_]:[--surface-muted:#f4f4f5] dark:[&_]:[--fg-on-muted:#18181b] dark:[&_]:[--orange-100:#ffb98f]
      dark:[&_]:[--orange-300:#e8742f] dark:[&_]:[--warning-bg:#3a2a14] dark:[&_]:[--warning-fg:#ffc77a]
      dark:[&_]:[color-scheme:dark] flex flex-col gap-5 min-w-0
      [&_[data-slot='growth-grid']]:[transform-box:fill-box]
      [&_[data-slot='growth-grid']]:[transform-origin:left]" ref={root} data-slot="unemployment-growth-chart">
      <div className="growth-stats grid [grid-template-columns:repeat(auto-fit,_minmax(min(100%,_190px),_1fr))] gap-4
        [@media(max-width:_400px)]:gap-2
        [@media(max-width:_400px)]:[grid-template-columns:repeat(2,_minmax(0,_1fr))]">
        {series.map((s) => <Stat key={s.id} series={s} value={point?.values[s.id]} period={point?.period} onEmphasis={setEmphasis} />)}
      </div>
      <ul className="legend growth-legend [gap:6px_16px] flex flex-wrap m-0 p-0 [list-style:none] text-[12px] font-medium
        leading-[1.25] text-fg-loud [&_li]:inline-flex [&_li]:items-center [&_li]:gap-1.5" data-slot="legend" aria-label="Legenda">
        {series.map((s) => <li key={s.id} className={`s${s.color}`}><span className="growth-legend-dot inline-block flex-none w-2.5 h-2.5 rounded-full [background:var(--series)]
          [box-shadow:0_0_0_2px_var(--card),_0_0_0_3px_color-mix(in_srgb,_var(--series)_30%,_transparent)]" />{s.shortLabel}</li>)}
        {bands.length > 0 && <li><svg className="key w-7 h-3" viewBox="0 0 28 12" aria-hidden="true">
          <rect x="0" y="0" width="28" height="12" rx="3" className="key-band [fill:var(--surface-subdued)]" />
          <line x1="2" y1="6" x2="26" y2="6" className="key-dashed [stroke:var(--fg-soft)] [stroke-width:2] [stroke-linecap:round] [stroke-dasharray:4_3]" />
        </svg>privremeni podaci</li>}
        {gaps && <li><svg className="key w-7 h-3" viewBox="0 0 28 12" aria-hidden="true">
          <line x1="1" y1="6" x2="9" y2="6" className="key-solid [stroke:var(--fg-soft)] [stroke-width:2] [stroke-linecap:round]" />
          <line x1="19" y1="6" x2="27" y2="6" className="key-solid [stroke:var(--fg-soft)] [stroke-width:2] [stroke-linecap:round]" />
        </svg>prekid: nema podatka</li>}
      </ul>
      {known.length === 0 ? <div ref={plot}><p className="empty m-0 text-[14px] text-fg-soft">Za odabrano razdoblje nema poznatih stopa nezaposlenosti.</p></div> : <>
        <div className="growth-plot-heading flex flex-wrap justify-between [gap:6px_16px] text-fg-soft text-[12px] [&_p]:m-0"><p>Stopa registrirane nezaposlenosti (%)</p>
          <p>{point && formatMonth(point.period)}</p></div>
        <div className="growth-axes flex gap-3 min-w-0 [@media(max-width:_400px)]:gap-2">
          <div className="growth-y-axis relative flex-none min-w-11 text-fg-soft text-[11px] tabular-nums [&_span]:absolute
            [&_span]:left-0 [&_span]:whitespace-nowrap [&_span]:[transform:translateY(-50%)]" aria-hidden="true" style={{ height: HEIGHT }}>
            {axis.ticks.map((tick) => <span key={tick} style={{ top: y(tick) }}>{formatRate(tick)}</span>)}
          </div>
          <div className="growth-plot-column flex-1 min-w-0">
            <div className="growth-plot relative [&_>_svg]:block [&_>_svg]:w-full [&_>_svg]:overflow-visible" ref={plot} style={{ height: HEIGHT }}>
              <svg aria-hidden="true" viewBox={`0 0 ${width} ${HEIGHT}`} width={width} height={HEIGHT}>
                <defs>
                  <clipPath id={`${id}-wipe`}><rect ref={wipe} x="0" y="0" width="100%" height={HEIGHT} /></clipPath>
                  <pattern id={`${id}-hatch`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <line x1="0" y1="0" x2="0" y2="6" className="growth-hatch [stroke:var(--surface-disable)] [stroke-width:1] [opacity:0.35]" />
                  </pattern>
                  {series.map((s) => <linearGradient key={s.id} id={`${id}-fade-${s.id}`} className={`s${s.color}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor="var(--series)" stopOpacity="0.14" /><stop offset="1" stopColor="var(--series)" stopOpacity="0" />
                  </linearGradient>)}
                  <filter id={`${id}-glow`} x="-20%" y="-40%" width="140%" height="180%">
                    <feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="currentColor" floodOpacity="0.3" />
                  </filter>
                </defs>
                {bands.map((band) => <rect key={band.first} data-slot="growth-provisional-band"
                  x={Math.max(0, x(band.first) - step / 2)} y={TOP}
                  width={Math.min(width, x(band.last) + step / 2) - Math.max(0, x(band.first) - step / 2)}
                  height={BOTTOM - TOP} fill={`url(#${id}-hatch)`} />)}
                <g ref={cursor} className="growth-cursor [fill:var(--fg-loud)] [&_line]:[stroke:var(--fg-loud)] [&_line]:[stroke-width:1.5]" data-slot="growth-cursor">
                  <line x1={cursorX} x2={cursorX} y1={TOP + 9} y2={BOTTOM - 9} strokeDasharray="4 4" />
                  <polygon points={`${cursorX - 5},${TOP} ${cursorX + 5},${TOP} ${cursorX},${TOP + 9}`} />
                  <polygon points={`${cursorX - 5},${BOTTOM} ${cursorX + 5},${BOTTOM} ${cursorX},${BOTTOM - 9}`} />
                </g>
                <line x1="0.5" x2="0.5" y1={TOP} y2={BOTTOM} className="growth-axis [stroke:var(--border)] [stroke-width:1]" />
                {axis.ticks.map((tick, index) => <line key={tick} data-slot="growth-grid" x1="0" x2={width} y1={y(tick)} y2={y(tick)}
                  className={index === 0 ? "growth-axis [stroke:var(--border)] [stroke-width:1]" : "growth-grid [stroke:var(--border)] [stroke-width:1]"} strokeDasharray={index === 0 ? undefined : '5 5'} />)}
                <g clipPath={`url(#${id}-wipe)`}>
                  {series.map((s) => {
                    const runs = seriesRuns(points, s.id)
                    return <g key={s.id} data-series={s.id} className={`growth-series [color:var(--series)] [transition:opacity_250ms] [&.is-muted]:[opacity:0.25]
                      motion-reduce:[transition:none] s${s.color}${emphasis && emphasis !== s.id ? ' is-muted' : ''}`}>
                      {runs.filter((run) => run.indices.length > 1).map((run) => {
                        const coords = run.indices.map((index) => ({ x: x(index), y: y(points[index].values[s.id].rate!) }))
                        return <g key={run.indices[0]}>
                          <path data-slot="growth-area" d={areaPath(coords, BOTTOM)} fill={`url(#${id}-fade-${s.id})`} />
                          <path data-slot="growth-line" data-from={points[run.indices[0]].period} data-to={points[run.indices.at(-1)!].period}
                            data-provisional={run.provisional} d={curvePath(coords)} className="growth-line [fill:none] [stroke:currentColor] [stroke-width:2] [stroke-linecap:round] [stroke-linejoin:round]"
                            strokeDasharray={run.provisional ? '5 4' : undefined} filter={`url(#${id}-glow)`} />
                        </g>
                      })}
                      {points.map((p, index) => {
                        const value = p.values[s.id]
                        if (value.rate === null) return null
                        const isolated = (points[index - 1]?.values[s.id].rate ?? null) === null &&
                          (points[index + 1]?.values[s.id].rate ?? null) === null
                        if (step < 20 && index !== active && index !== 0 && index !== points.length - 1 && !isolated) return null
                        return <g key={p.period} data-slot="growth-node" data-index={index} data-period={p.period} data-rate={value.rate}
                          className={`growth-node [fill:currentColor] [transform-box:fill-box] [transform-origin:center] ${index === active ? ' is-active' : ''}`}>
                          <circle cx={x(index)} cy={y(value.rate)} r={index === active ? 6 : 4.5} className="growth-node-shell fill-card" />
                          <circle cx={x(index)} cy={y(value.rate)} r={index === active ? 4.5 : 3} />
                        </g>
                      })}
                    </g>
                  })}
                </g>
              </svg>
              <div role="slider" tabIndex={0} className="growth-scrubber absolute inset-0 cursor-crosshair touch-pan-y rounded-[8px] [outline:none]
                [&:focus-visible]:shadow-focus" aria-label="Odabrani mjesec"
                aria-describedby={`${id}-hint`} aria-orientation="horizontal" aria-valuemin={0} aria-valuemax={points.length - 1}
                aria-valuenow={active} aria-valuetext={valueText} data-period={point?.period}
                onKeyDown={onKeyDown} onPointerMove={(event) => {
                  const index = pointAt(event)
                  if (event.currentTarget.hasPointerCapture(event.pointerId)) select(index)
                  else if (event.pointerType === 'mouse') setHovered(index)
                }} onPointerLeave={() => setHovered(null)} onPointerCancel={() => setHovered(null)}
                onPointerDown={(event) => {
                  if (event.button !== 0) return
                  if (event.pointerType !== 'mouse') event.currentTarget.setPointerCapture(event.pointerId)
                  setHovered(null)
                  select(pointAt(event))
                }} onPointerUp={(event) => {
                  if (event.button !== 0) return
                  setHovered(null)
                  select(pointAt(event))
                  if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
                }} />
            </div>
            <div className="growth-x-axis relative h-6 mt-1 text-fg-soft text-[11px] [&_span]:absolute
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
        <p id={`${id}-hint`} className="growth-hint m-0 text-fg-soft text-[11px] leading-[1.5]">Po mjesecima · pomaknite pokazivač ili birajte mjesec strelicama.</p>
      </>}
    </div>
  )
}
