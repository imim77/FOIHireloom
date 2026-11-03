// Local adaptation of the supplied Keitoto RevenueGrowthChart: stat tiles, glowing curves and area fills,
// dashed grid, nodes and a scrubber with triangle caps. Rates retain the original DZS gaps and provenance.
import { animate, stagger } from 'animejs'
import { type KeyboardEvent, type PointerEvent, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { fadeIn, finish, releaseStyles, useChartEntrance, useCountUp, useReducedMotion } from '../../shared/chart-motion'
import { formatMonth, formatRate, formatShortMonth } from '../../shared/format'
import { useChartWidth } from '../../shared/use-chart-size'
import { provisionalBands, seriesRuns, toGrowthData, type GrowthData, type GrowthSeries } from './chart-data'
import { areaPath, curvePath, monthTicks, rateAxis } from './chart-geometry'
import type { CountyHistory, UnemploymentPoint } from './types'
import './unemployment-growth-chart.css'

const HEIGHT = 360
const TOP = 14
const BOTTOM = HEIGHT - 14
const EDGE = 8
const DRAW_AT = 250
const DRAW_DURATION = 1400

export function UnemploymentGrowthChart({ counties }: { counties: CountyHistory[] }) {
  const data = useMemo(() => toGrowthData(counties), [counties])
  // A new tool result opens on its last month and cancels every animation from the old result.
  return <GrowthChart key={JSON.stringify(counties)} data={data} />
}

function RateValue({ rate }: { rate: number }) {
  const ref = useRef<HTMLParagraphElement>(null)
  useCountUp(ref, rate, formatRate)
  return <p ref={ref} className="growth-value" data-slot="growth-stat-value" data-value={rate}>{formatRate(rate)}</p>
}

function Stat({ series, value, period, onEmphasis }: {
  series: GrowthSeries
  value: UnemploymentPoint | undefined
  period: string | undefined
  onEmphasis: (id: string | null) => void
}) {
  return (
    <section className={`growth-stat s${series.color}`} aria-label={`${series.label}, odabrani mjesec`}
      onPointerEnter={() => onEmphasis(series.id)} onPointerLeave={() => onEmphasis(null)}>
      <p className="growth-stat-name" title={series.label}>
        <span className="growth-legend-dot" aria-hidden="true" />{series.shortLabel}
      </p>
      <div className="growth-stat-reading">
        {value?.rate != null ? <RateValue rate={value.rate} /> : <p className="growth-missing">nema podatka</p>}
        {period && <p className="growth-stat-month">{formatMonth(period)}</p>}
      </div>
      {value?.is_provisional && <span className="provisional">privremeno</span>}
    </section>
  )
}

function GrowthChart({ data }: { data: GrowthData }) {
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
    <div className="growth-chart" ref={root} data-slot="unemployment-growth-chart">
      <div className="growth-stats">
        {series.map((s) => <Stat key={s.id} series={s} value={point?.values[s.id]} period={point?.period} onEmphasis={setEmphasis} />)}
      </div>
      <ul className="legend growth-legend" data-slot="legend" aria-label="Legenda">
        {series.map((s) => <li key={s.id} className={`s${s.color}`}><span className="growth-legend-dot" />{s.shortLabel}</li>)}
        {bands.length > 0 && <li><svg className="key" viewBox="0 0 28 12" aria-hidden="true">
          <rect x="0" y="0" width="28" height="12" rx="3" className="key-band" />
          <line x1="2" y1="6" x2="26" y2="6" className="key-dashed" />
        </svg>privremeni podaci</li>}
        {gaps && <li><svg className="key" viewBox="0 0 28 12" aria-hidden="true">
          <line x1="1" y1="6" x2="9" y2="6" className="key-solid" />
          <line x1="19" y1="6" x2="27" y2="6" className="key-solid" />
        </svg>prekid: nema podatka</li>}
      </ul>
      {known.length === 0 ? <div ref={plot}><p className="empty">Za odabrano razdoblje nema poznatih stopa nezaposlenosti.</p></div> : <>
        <div className="growth-plot-heading"><p>Stopa registrirane nezaposlenosti (%)</p>
          <p>{point && formatMonth(point.period)}</p></div>
        <div className="growth-axes">
          <div className="growth-y-axis" aria-hidden="true" style={{ height: HEIGHT }}>
            {axis.ticks.map((tick) => <span key={tick} style={{ top: y(tick) }}>{formatRate(tick)}</span>)}
          </div>
          <div className="growth-plot-column">
            <div className="growth-plot" ref={plot} style={{ height: HEIGHT }}>
              <svg aria-hidden="true" viewBox={`0 0 ${width} ${HEIGHT}`} width={width} height={HEIGHT}>
                <defs>
                  <clipPath id={`${id}-wipe`}><rect ref={wipe} x="0" y="0" width="100%" height={HEIGHT} /></clipPath>
                  <pattern id={`${id}-hatch`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <line x1="0" y1="0" x2="0" y2="6" className="growth-hatch" />
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
                <g ref={cursor} className="growth-cursor" data-slot="growth-cursor">
                  <line x1={cursorX} x2={cursorX} y1={TOP + 9} y2={BOTTOM - 9} strokeDasharray="4 4" />
                  <polygon points={`${cursorX - 5},${TOP} ${cursorX + 5},${TOP} ${cursorX},${TOP + 9}`} />
                  <polygon points={`${cursorX - 5},${BOTTOM} ${cursorX + 5},${BOTTOM} ${cursorX},${BOTTOM - 9}`} />
                </g>
                <line x1="0.5" x2="0.5" y1={TOP} y2={BOTTOM} className="growth-axis" />
                {axis.ticks.map((tick, index) => <line key={tick} data-slot="growth-grid" x1="0" x2={width} y1={y(tick)} y2={y(tick)}
                  className={index === 0 ? 'growth-axis' : 'growth-grid'} strokeDasharray={index === 0 ? undefined : '5 5'} />)}
                <g clipPath={`url(#${id}-wipe)`}>
                  {series.map((s) => {
                    const runs = seriesRuns(points, s.id)
                    return <g key={s.id} data-series={s.id} className={`growth-series s${s.color}${emphasis && emphasis !== s.id ? ' is-muted' : ''}`}>
                      {runs.filter((run) => run.indices.length > 1).map((run) => {
                        const coords = run.indices.map((index) => ({ x: x(index), y: y(points[index].values[s.id].rate!) }))
                        return <g key={run.indices[0]}>
                          <path data-slot="growth-area" d={areaPath(coords, BOTTOM)} fill={`url(#${id}-fade-${s.id})`} />
                          <path data-slot="growth-line" data-from={points[run.indices[0]].period} data-to={points[run.indices.at(-1)!].period}
                            data-provisional={run.provisional} d={curvePath(coords)} className="growth-line"
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
                          className={`growth-node${index === active ? ' is-active' : ''}`}>
                          <circle cx={x(index)} cy={y(value.rate)} r={index === active ? 6 : 4.5} className="growth-node-shell" />
                          <circle cx={x(index)} cy={y(value.rate)} r={index === active ? 4.5 : 3} />
                        </g>
                      })}
                    </g>
                  })}
                </g>
              </svg>
              <div role="slider" tabIndex={0} className="growth-scrubber" aria-label="Odabrani mjesec"
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
            <div className="growth-x-axis" aria-hidden="true">
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
        <p id={`${id}-hint`} className="growth-hint">Po mjesecima · pomaknite pokazivač ili birajte mjesec strelicama.</p>
      </>}
    </div>
  )
}
