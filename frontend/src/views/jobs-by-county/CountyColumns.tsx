// A 3D column per county, after the "Investment App User Age Chart" design: the active county is orange, the
// others grey; hovering previews a county, clicking or the arrow keys select one. Layout is declarative; the
// animations write styles straight to the nodes, as anime.js did. Mount it anew (key) for each result.

import { type KeyboardEvent, useLayoutEffect, useRef, useState } from 'react'
import { formatAds, formatInteger, formatShare, formatWorkers } from '../../shared/format'
import { fadeIn, pop, reducedMotion, type Tween, tween } from '../../shared/motion'
import { BAR_VIEW, BarLook } from './Bar3d'
import type { County, CountyMetric } from './types'

const PLOT_HEIGHT = 208.921
const COLUMN_GAP = 8
const BAR_WIDTH = 48
const BAR_RATIO = 48 / 64
const VALUE_GAP = 4
const MAX_BAR = PLOT_HEIGHT - 16 - VALUE_GAP
const BARS_AT = 250
const BAR_STAGGER = 70
const GROW = 1100
// The narrowest column; the plot scrolls sideways below it.
const MIN_COLUMN = 84

const round = (n: number) => Math.round(n * 1000) / 1000

export function CountyColumns({ counties, metric }: { counties: County[]; metric: CountyMetric }) {
  const [selected, setSelected] = useState(0)
  const [hovered, setHovered] = useState<number | null>(null)
  const [plotWidth, setPlotWidth] = useState(0)
  const active = hovered ?? selected

  const plot = useRef<HTMLDivElement>(null)
  const pill = useRef<HTMLSpanElement>(null)
  const selection = useRef<HTMLDivElement>(null)
  const selectedName = useRef<HTMLParagraphElement>(null)
  const selectedWorkers = useRef<HTMLParagraphElement>(null)
  const axis = useRef<HTMLDivElement>(null)
  const workersShown = useRef(0)
  const workersTween = useRef<Tween | null>(null)
  const pillTween = useRef<Tween | null>(null)
  const tweens = useRef<Tween[]>([])
  const previous = useRef(active)

  const n = counties.length
  const gaps = COLUMN_GAP * (n - 1)
  const max = Math.max(0, ...counties.map((county) => county[metric]))
  const heights = counties.map((county) => (max > 0 ? round((county[metric] / max) * MAX_BAR) : 0))
  // Bar widths follow the plot's width: a 48px bar in a 64px column, narrower columns narrow it in proportion.
  const columnWidth = (plotWidth - gaps) / n
  const barWidth = round(Math.max(2, Math.min(BAR_WIDTH, columnWidth * BAR_RATIO)))
  const county = counties[active]

  const nodes = (selector: string) => [...plot.current!.querySelectorAll<HTMLElement>(selector)]
  const track = (...started: Tween[]) => tweens.current.push(...started)

  function showWorkers(value: number) {
    workersShown.current = value
    selectedWorkers.current!.textContent = formatWorkers(value)
  }

  useLayoutEffect(() => {
    const node = plot.current!
    const observer = new ResizeObserver(() => setPlotWidth(node.clientWidth))
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  // Entrance: the selection comes in, the columns rise one after another while their counts count up,
  // the workers sought count up and the pill pops in under the selected county.
  useLayoutEffect(() => {
    const workers = counties[selected].workers_needed
    if (reducedMotion) {
      showWorkers(workers)
      return
    }
    const bars = nodes('.bar')
    const values = nodes('.value')
    const numbers = nodes('.value span')
    const growth = heights.map(() => 0)
    const grow = () => heights.forEach((height, i) => {
      bars[i].style.height = `${round(height * growth[i])}px`
      values[i].style.bottom = `${round(height * growth[i] + VALUE_GAP)}px`
      numbers[i].textContent = formatInteger(counties[i][metric] * growth[i])
    })
    grow()
    track(...fadeIn(selection.current!.children as HTMLCollectionOf<HTMLElement>, { at: 100, stagger: 80, rise: 6 }))
    showWorkers(0)
    workersTween.current = tween({ duration: 1400, delay: 150, update: (p) => showWorkers(workers * p) })
    track(workersTween.current)
    track(...fadeIn(values, { at: BARS_AT, duration: 400, stagger: BAR_STAGGER }))
    track(...fadeIn(axis.current!.querySelectorAll<HTMLElement>('.axis-label > span'), { at: 350, stagger: 50, rise: 4 }))
    heights.forEach((_, i) => track(tween({
      duration: GROW, delay: BARS_AT + i * BAR_STAGGER,
      update: (p) => {
        growth[i] = p
        grow()
      },
    })))
    pill.current!.style.opacity = '0'
    track(pop(pill.current!, { at: BARS_AT + selected * BAR_STAGGER + GROW * 0.45 }))
    const started = tweens.current
    return () => started.forEach((running) => running.cancel())
    // Runs once: each result mounts the component anew.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // A new active county: the pill slides over from the previous one, its count pops and the workers count to it.
  useLayoutEffect(() => {
    const before = previous.current
    previous.current = active
    if (before === active) return
    const workers = counties[active].workers_needed
    if (reducedMotion) {
      showWorkers(workers)
      return
    }
    const offset = (before - active) * (columnWidth + COLUMN_GAP)
    pillTween.current?.cancel()
    pillTween.current = tween({
      duration: 550,
      update: (p) => { pill.current!.style.transform = `translateX(${offset * (1 - p)}px)` },
      done: () => { pill.current!.style.transform = '' },
    })
    track(pillTween.current, pop(nodes('.value span')[active], { from: 0.86, overshoot: 2, fade: false }),
      ...fadeIn([selectedName.current!], { duration: 300, from: 0.4 }))
    workersTween.current?.cancel()
    const from = workersShown.current
    workersTween.current = tween({ duration: 600, update: (p) => showWorkers(from + (workers - from) * p) })
    track(workersTween.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active])

  function select(index: number) {
    setSelected(Math.min(Math.max(index, 0), n - 1))
  }

  function onKeyDown(event: KeyboardEvent) {
    const next = ({ ArrowRight: selected + 1, ArrowDown: selected + 1, ArrowLeft: selected - 1,
      ArrowUp: selected - 1, Home: 0, End: n - 1 } as Record<string, number>)[event.key]
    if (next === undefined) return
    event.preventDefault()
    setHovered(null)
    const index = Math.min(Math.max(next, 0), n - 1)
    select(index)
    nodes('.column')[index].focus()
  }

  const fraction = `((100% - ${gaps}px) / ${n})`
  return (
    <>
      <div className="selection" ref={selection}>
        <p className="soft" ref={selectedName}>{county.name} · {formatAds(county.jobs)}</p>
        <p className="big" ref={selectedWorkers} />
      </div>
      <div className="scroller">
        <div className="chart" style={{ minWidth: `${n * MIN_COLUMN + gaps}px` }}>
          <div className="plot" role="group" aria-label="Broj oglasa po županijama" ref={plot}
            onPointerLeave={() => setHovered(null)}>
            {counties.map((county, i) => (
              <button key={county.name} type="button" className={`column${i === active ? ' active' : ''}`}
                aria-label={`${county.name}: ${formatAds(county.jobs)}, ${formatWorkers(county.workers_needed)}, `
                  + formatShare(county.share)}
                aria-pressed={i === selected} tabIndex={i === selected ? 0 : -1}
                onPointerEnter={() => setHovered(i)} onClick={() => select(i)} onKeyDown={onKeyDown}>
                <svg className="bar" viewBox={BAR_VIEW} preserveAspectRatio="none" aria-hidden="true"
                  style={{ width: `${barWidth}px`, left: `calc(50% - ${barWidth / 2}px)`, height: `${heights[i]}px` }}>
                  <BarLook lit={false} opacity={i === active ? 0 : 0.32} />
                  <BarLook lit opacity={i === active ? 1 : 0} />
                </svg>
                <span className="value" aria-hidden="true" style={{ bottom: `${round(heights[i] + VALUE_GAP)}px` }}>
                  <span>{formatInteger(county[metric])}</span>
                </span>
                <span className="focus-ring" aria-hidden="true" />
              </button>
            ))}
          </div>
          <div className="axis" aria-hidden="true" ref={axis}>
            <span className="pill" ref={pill}
              style={{ width: `calc${fraction}`, left: `calc(${active} * (${fraction} + ${COLUMN_GAP}px))` }} />
            {counties.map((county, i) => (
              <span key={county.name} className={`axis-label${i === active ? ' active' : ''}`} title={county.name}>
                {/* A break after each hyphen: "Splitsko-" over "dalmatinska" instead of a cut word. */}
                <span>{county.short_name.replaceAll('-', '-​')}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
