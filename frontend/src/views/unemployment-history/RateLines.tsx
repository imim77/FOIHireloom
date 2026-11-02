// The counties' monthly unemployment rates as lines on one axis. A month DZS has no rate for is a gap in its line,
// never a 0; a lone known month between gaps is a dot. Provisional months (2026) lie on a hatched band and their
// segments are dashed. Each line ends in a ringed dot and, in a wide frame, its county's name and last rate. Hover or
// the arrow keys move a crosshair over the months with every county's rate in a tooltip. Animated with anime.js: the
// lines draw in from the left, then the end labels fade in.

import { type KeyboardEvent, type PointerEvent, useId, useRef, useState } from 'react'
import { fadeIn, useChartEntrance } from '../../shared/chart-motion'
import { formatMonth, formatRate, formatShortMonth } from '../../shared/format'
import { useChartWidth } from '../../shared/use-chart-size'
import type { CountyHistory } from './types'

const HEIGHT = 248
const TOP = 28 // room for the band's label
const BOTTOM = 28 // the month labels
const LEFT = 44 // the rate labels
const RIGHT_LABELS = 128 // the end labels in a wide frame
const RIGHT = 14
// Below this width the lines end without labels; the legend names them.
const LABELS_FROM = 560
const LABEL_GAP = 15 // between end labels, so they never overlap
const MIN_TICK = 58 // between month labels
const DRAW = 1500

const STEPS = [0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10]
const EVERY = [1, 2, 3, 4, 6, 12]

/** The rate axis: a few round ticks around the known rates. */
function rateAxis(rates: number[]) {
  let low = Math.min(...rates)
  let high = Math.max(...rates)
  if (low === high) {
    low -= 0.5
    high += 0.5
  }
  const step = STEPS.find((candidate) => (high - low) / candidate <= 5) ?? 10
  low = Math.max(0, Math.floor(low / step) * step)
  high = Math.ceil(high / step) * step
  const ticks: number[] = []
  for (let tick = low; tick <= high + step / 2; tick += step) ticks.push(Math.round(tick * 100) / 100)
  return { low, high, ticks }
}

interface Run {
  dashed: boolean
  points: [number, number][]
}

/** A series as runs of segments between known months, each run solid or dashed; lone known months as dots. */
function runs(county: CountyHistory, x: (i: number) => number, y: (rate: number) => number) {
  const lines: Run[] = []
  const dots: [number, number][] = []
  const series = county.series
  series.forEach((point, i) => {
    const next = series[i + 1]
    const before = series[i - 1]
    if (point.rate === null) return
    if ((!before || before.rate === null) && (!next || next.rate === null)) dots.push([x(i), y(point.rate)])
    if (!next || next.rate === null) return
    const dashed = Boolean(point.is_provisional || next.is_provisional)
    const last = lines[lines.length - 1]
    const end = last?.points[last.points.length - 1]
    if (last && last.dashed === dashed && end && end[0] === x(i)) last.points.push([x(i + 1), y(next.rate)])
    else lines.push({ dashed, points: [[x(i), y(point.rate)], [x(i + 1), y(next.rate)]] })
  })
  return { lines, dots }
}

const path = (points: [number, number][]) => points.map(([px, py], i) => `${i ? 'L' : 'M'}${px},${py}`).join('')

/** The months to label: every few months, counted back from the last, so the latest month always has one. */
function monthTicks(count: number, plotWidth: number) {
  const every = EVERY.find((n) => (plotWidth / Math.max(1, count - 1)) * n >= MIN_TICK) ?? 12
  return Array.from({ length: count }, (_, i) => i).filter((i) => (count - 1 - i) % every === 0)
}

export function RateLines({ counties }: { counties: CountyHistory[] }) {
  const [plot, width] = useChartWidth<HTMLDivElement>(counties.length)
  const [hovered, setHovered] = useState<number | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const clip = useRef<SVGRectElement>(null)
  const ids = useId().replace(/[^\w-]/g, '')

  const months = counties[0]?.series.map((point) => point.period) ?? []
  const n = months.length
  const labelled = width >= LABELS_FROM
  const right = labelled ? RIGHT_LABELS : RIGHT
  const plotWidth = Math.max(0, width - LEFT - right)
  const step = n > 1 ? plotWidth / (n - 1) : 0
  const x = (i: number) => LEFT + i * step
  const known = counties.flatMap((county) => county.series.flatMap((point) => point.rate ?? []))
  const axis = rateAxis(known.length ? known : [0, 1])
  const plotHeight = HEIGHT - TOP - BOTTOM
  const y = (rate: number) => TOP + (1 - (rate - axis.low) / (axis.high - axis.low)) * plotHeight

  // Provisional months from the first one any county has to the end, half a month either side.
  const firstProvisional = months.findIndex((_, i) => counties.some((county) => county.series[i]?.is_provisional))
  const bandFrom = firstProvisional < 0 ? null : Math.max(LEFT, x(firstProvisional) - step / 2)
  const bandTo = x(n - 1) + Math.min(step / 2, right - 4)

  // Each line's last known month, for its end dot and label; labels are pushed apart so none overlaps another.
  const ends = counties.map((county, index) => {
    const i = county.series.findLastIndex((point) => point.rate !== null)
    return i < 0 ? null : { index, i, rate: county.series[i].rate!, y: y(county.series[i].rate!) }
  })
  const placed = new Map<number, number>()
  const order = ends.filter((end) => end !== null).sort((a, b) => a.y - b.y)
  order.forEach((end, k) => {
    const previous = k ? placed.get(order[k - 1].index)! : -Infinity
    placed.set(end.index, Math.max(end.y, previous + LABEL_GAP))
  })
  // Labels pushed below the plot move up again, together.
  const overflow = Math.max(0, ...[...placed.values()].map((value) => value - (TOP + plotHeight)))
  for (const [index, value] of placed) placed.set(index, value - overflow)

  useChartEntrance(root, (timeline) => {
    const state = { t: 0 }
    const reveal = () => clip.current?.setAttribute('width', `${state.t * 100}%`)
    reveal()
    timeline.add(state, { t: [0, 1], duration: DRAW, ease: 'inOutQuad', onUpdate: reveal }, 100)
    const labels = [...root.current!.querySelectorAll<HTMLElement>('[data-slot="end"]')]
    timeline.add(labels, { ...fadeIn(labels, 4), duration: 500 }, DRAW - 300)
    return () => {
      state.t = 1
      reveal()
      for (const el of labels) {
        el.style.removeProperty('opacity')
        el.style.removeProperty('transform')
      }
    }
  })

  function hover(event: PointerEvent<SVGRectElement>) {
    if (!step) return
    const box = event.currentTarget.ownerSVGElement!.getBoundingClientRect()
    const i = Math.round((event.clientX - box.left - LEFT) / step)
    setHovered(Math.min(Math.max(i, 0), n - 1))
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const at = hovered ?? n - 1
    const next = ({ ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: n - 1 } as Record<string, number>)[event.key]
    if (next === undefined) return
    event.preventDefault()
    setHovered(Math.min(Math.max(next, 0), n - 1))
  }

  const ticks = monthTicks(n, plotWidth)
  const tooltipLeft = hovered === null ? 0 : x(hovered)
  const flip = tooltipLeft > width / 2

  return (
    <div className="rate-lines" ref={root}>
      <div className="plot-box" ref={plot} tabIndex={0} role="group" onKeyDown={onKeyDown}
        onBlur={() => setHovered(null)}
        aria-label="Stopa registrirane nezaposlenosti po mjesecima; strelicama lijevo i desno birate mjesec">
        <svg width={width} height={HEIGHT} viewBox={`0 0 ${width} ${HEIGHT}`} aria-hidden="true">
          <defs>
            <pattern id={`${ids}-hatch`} width="6" height="6" patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="6" className="hatch-line" />
            </pattern>
            <clipPath id={`${ids}-draw`}>
              <rect ref={clip} x="0" y="0" width="100%" height={HEIGHT} />
            </clipPath>
          </defs>
          {bandFrom !== null && width > 0 && (
            <g className="band">
              <rect x={bandFrom} y={TOP - 6} width={Math.max(0, bandTo - bandFrom)} height={plotHeight + 6}
                fill={`url(#${ids}-hatch)`} />
              <text x={bandFrom + 4} y={TOP - 12} className="band-label">privremeni podaci</text>
            </g>
          )}
          {axis.ticks.map((tick) => (
            <g key={tick} className="grid">
              <line x1={LEFT} x2={LEFT + plotWidth} y1={y(tick)} y2={y(tick)} />
              <text x={LEFT - 8} y={y(tick)} dy="0.32em" textAnchor="end">{formatRate(tick)}</text>
            </g>
          ))}
          {ticks.map((i, k) => {
            // The first label and each one in a new year name the year.
            const withYear = k === 0 || months[i].slice(0, 4) !== months[ticks[k - 1]].slice(0, 4)
            return (
              <text key={i} x={x(i)} y={HEIGHT - 8} className="month" textAnchor={i === 0 ? 'start' : 'middle'}>
                {formatShortMonth(months[i], withYear)}
              </text>
            )
          })}
          <g clipPath={`url(#${ids}-draw)`}>
            {counties.map((county, index) => {
              const { lines, dots } = runs(county, x, y)
              return (
                <g key={county.code} className={`series s${index + 1}`}>
                  {lines.map((run, k) => (
                    <path key={k} d={path(run.points)} className={run.dashed ? 'line dashed' : 'line'} />
                  ))}
                  {dots.map(([px, py]) => <circle key={px} cx={px} cy={py} r="3" className="dot" />)}
                </g>
              )
            })}
          </g>
          {hovered !== null && (
            <g className="crosshair">
              <line x1={x(hovered)} x2={x(hovered)} y1={TOP - 6} y2={TOP + plotHeight} />
              {counties.map((county, index) => {
                const rate = county.series[hovered]?.rate
                return rate == null ? null : (
                  <circle key={county.code} cx={x(hovered)} cy={y(rate)} r="4.5" className={`ring s${index + 1}`} />
                )
              })}
            </g>
          )}
          {ends.map((end) => end && (
            <g key={end.index} data-slot="end" className={`end s${end.index + 1}`}>
              <circle cx={x(end.i)} cy={end.y} r="4" className="ring" />
              {labelled && (
                <text x={x(n - 1) + 12} y={placed.get(end.index)} dy="0.32em">
                  <tspan className="end-name">{counties[end.index].short_name}</tspan>
                  <tspan dx="6">{formatRate(end.rate)}</tspan>
                </text>
              )}
            </g>
          ))}
          <rect x={LEFT} y={0} width={Math.max(0, plotWidth)} height={HEIGHT} className="hit"
            onPointerMove={hover} onPointerLeave={() => setHovered(null)} />
        </svg>
        {hovered !== null && (
          <div className="tooltip" role="status"
            style={flip ? { right: `${width - tooltipLeft + 12}px` } : { left: `${tooltipLeft + 12}px` }}>
            <p className="tooltip-month">
              {formatMonth(months[hovered])}
              {counties.some((county) => county.series[hovered]?.is_provisional) && (
                <span className="provisional">privremeno</span>
              )}
            </p>
            {counties.map((county, index) => {
              const rate = county.series[hovered]?.rate
              return (
                <p key={county.code} className="tooltip-row">
                  <span className={`swatch s${index + 1}`} />
                  <span className="tooltip-name">{county.short_name}</span>
                  <span className={rate == null ? 'tooltip-missing' : 'tooltip-value'}>
                    {rate == null ? 'nema podatka' : formatRate(rate)}
                  </span>
                </p>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
