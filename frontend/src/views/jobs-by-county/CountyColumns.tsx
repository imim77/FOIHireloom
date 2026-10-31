// The counties as 3D columns, after the "Investment App User Age Chart" from the Keitoto library: the active county
// is orange with its count in orange and its name in a dark pill, the others grey; the selected county's workers sought
// stand over the chart. Hover previews a county, click or the arrow keys select one. Animated with anime.js: the
// workers count up, the columns rise one after another while their counts count up and the pill pops in; a new county
// cross-fades the columns, pops its count, slides the pill over and counts the workers to the new number; new data
// (another result, or every county once expanded) regrows the columns from the heights on screen.

import { animate, type JSAnimation, stagger, utils } from 'animejs'
import { type KeyboardEvent, useId, useLayoutEffect, useRef, useState } from 'react'
import { finish, releaseStyles, useChartEntrance, useCountUp, useReducedMotion } from '../../shared/chart-motion'
import { formatAds, formatInteger, formatShare, formatWorkers } from '../../shared/format'
import { useChartWidth } from '../../shared/use-chart-size'
import { BAR_VIEW, BarGradients, BarLook } from './Bar3d'
import type { County, CountyMetric } from './types'

// Figma geometry ("Investment App User Age Chart" 1473:77228)
const PLOT_HEIGHT = 208.921 // the tallest column: its 16px value, a 4px gap and its bar
const COLUMN_GAP = 8
const BAR_WIDTH = 48 // centred in a 64px column; narrower columns narrow it in proportion
const BAR_RATIO = 48 / 64
const VALUE_HEIGHT = 16
const VALUE_GAP = 4 // between a bar's top and its value
const MAX_BAR = PLOT_HEIGHT - VALUE_HEIGHT - VALUE_GAP
const BARS_AT = 250
const BAR_STAGGER = 70
const GROW = 1100
const MORPH = 700
// The narrowest column; the plot scrolls sideways below it.
const MIN_COLUMN = 84

const round = (n: number) => Math.round(n * 1000) / 1000

/** A column's count over it, counting from the previous one when the data changes. */
function BarValue({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  useCountUp(ref, value, formatInteger, { duration: MORPH })
  return <span ref={ref} data-slot="value-text">{formatInteger(value)}</span>
}

export function CountyColumns({ counties, metric }: { counties: County[]; metric: CountyMetric }) {
  const n = counties.length
  const values = counties.map((county) => Math.max(0, county[metric]))
  const max = Math.max(0, ...values)
  const heights = values.map((value) => (max > 0 ? round((value / max) * MAX_BAR) : 0))
  // Content key: the data arrives as new arrays, so changes are detected by value.
  const heightsKey = heights.join(',')

  const [plot, plotWidth] = useChartWidth<HTMLDivElement>(n)
  const gaps = COLUMN_GAP * Math.max(0, n - 1)
  const columnWidth = n ? (plotWidth - gaps) / n : plotWidth
  const barWidth = round(Math.max(2, Math.min(BAR_WIDTH, columnWidth * BAR_RATIO)))

  const [selectedIndex, setSelected] = useState(0)
  const [hovered, setHovered] = useState<number | null>(null)
  const selected = Math.min(Math.max(selectedIndex, 0), n - 1)
  const active = hovered !== null && hovered < n ? hovered : selected
  const county = counties[active]
  const workers = county.workers_needed

  const reduced = useReducedMotion()
  const root = useRef<HTMLDivElement>(null)
  const pill = useRef<HTMLSpanElement>(null)
  const nameRef = useRef<HTMLParagraphElement>(null)
  const workersRef = useRef<HTMLParagraphElement>(null)
  const ids = useId().replace(/[^\w-]/g, '')
  // What the entrance's callbacks need at play time (the data may change, or another county be hovered, before it ends).
  const latest = useRef({ heights, values, workers })
  useLayoutEffect(() => {
    latest.current = { heights, values, workers }
  })
  const all = (selector: string) => [...root.current?.querySelectorAll<HTMLElement>(selector) ?? []]

  // The bars' heights on screen. A bar's count rides 4px over its top.
  const shown = useRef(heights)
  const draw = (frame: number[]) => {
    shown.current = frame
    const bars = all('[data-slot="bar"]')
    const labels = all('[data-slot="value"]')
    frame.forEach((height, i) => {
      if (bars[i]) bars[i].style.height = `${round(height)}px`
      if (labels[i]) labels[i].style.bottom = `${round(height + VALUE_GAP)}px`
    })
  }
  // How far the entrance has grown each bar (null without one), so new data before it is done keeps growing from there.
  const growing = useRef<{ t: number }[] | null>(null)
  // While the entrance counts the workers up, a new selection leaves the counting to it.
  const countingWorkers = useRef(false)
  const workersCount = useRef<{ tween: JSAnimation | null; value: number }>({ tween: null, value: workers })
  const showWorkers = (value: number) => {
    workersCount.current.value = value
    if (workersRef.current) workersRef.current.textContent = formatWorkers(value)
  }

  // Entrance: the selection comes in and its workers count up, the columns rise from their feet one after another
  // while their counts count up, then the names come in and the pill pops in under the selected column.
  useChartEntrance(root, (timeline) => {
    const growth = latest.current.heights.map(() => ({ t: 0 }))
    growing.current = growth
    const texts = all('[data-slot="value-text"]')
    const grow = () => {
      const { heights, values } = latest.current
      draw(heights.map((height, i) => height * (growth[i]?.t ?? 1)))
      texts.forEach((el, i) => (el.textContent = formatInteger((values[i] ?? 0) * (growth[i]?.t ?? 1))))
    }
    grow()
    const up = { t: 0 }
    const countUp = () => showWorkers(latest.current.workers * up.t)
    countingWorkers.current = true
    countUp()
    // Each target starts hidden at once, not one frame later when the timeline first renders.
    const fade = (targets: HTMLElement[], rise = 0) => {
      utils.set(targets, { opacity: 0, translateY: rise })
      return { opacity: [0, 1], translateY: [rise, 0], ease: 'outQuad', onComplete: releaseStyles('opacity', 'transform') }
    }
    const selection = all('[data-slot="selection"] > *')
    const counts = all('[data-slot="value"]')
    const names = all('[data-slot="axis-label"] > span')
    const pillAt = BARS_AT + Math.max(0, active) * BAR_STAGGER + GROW * 0.45
    timeline
      .add(selection, { ...fade(selection, 6), duration: 600, delay: stagger(80) }, 100)
      .add(up, {
        t: [0, 1], duration: 1400, ease: 'outExpo', onUpdate: countUp,
        onComplete: () => { countingWorkers.current = false },
      }, 150)
      .add(counts, { ...fade(counts), duration: 400, delay: stagger(BAR_STAGGER) }, BARS_AT)
      .add(names, { ...fade(names, 4), duration: 600, delay: stagger(50) }, 350)
    growth.forEach((state, i) => timeline.add(state, { t: [0, 1], duration: GROW, ease: 'outExpo', onUpdate: grow },
      BARS_AT + i * BAR_STAGGER))
    if (pill.current) {
      utils.set(pill.current, { opacity: 0 })
      timeline.add(pill.current, { scale: [0.7, 1], opacity: [0, 1], duration: 500, ease: 'outBack(1.7)',
        onComplete: releaseStyles('opacity', 'transform') }, pillAt)
    }
    return () => {
      if (growing.current === growth) growing.current = null
      countingWorkers.current = false
      const { heights, values, workers } = latest.current
      draw(heights)
      texts.forEach((el, i) => (el.textContent = formatInteger(values[i] ?? 0)))
      showWorkers(workers)
      for (const el of [...selection, ...counts, ...names, pill.current]) el?.style.removeProperty('opacity')
    }
  })

  // New data regrows every bar from the height it has on screen (new bars from their feet). While the entrance runs,
  // the bars are redrawn as far as it has grown them (it carries on with the new heights).
  const lastHeights = useRef(heightsKey)
  const morph = useRef<JSAnimation | null>(null)
  useLayoutEffect(() => {
    if (lastHeights.current === heightsKey) return
    lastHeights.current = heightsKey
    morph.current?.cancel()
    morph.current = null
    const entrance = growing.current
    if (entrance?.some((bar) => bar.t < 1)) {
      draw(heights.map((height, i) => height * (entrance[i]?.t ?? 1)))
      return
    }
    if (reduced) {
      draw(heights)
      return
    }
    const from = shown.current
    const state = { t: 0 }
    const at = () => heights.map((height, i) => (from[i] ?? 0) + (height - (from[i] ?? 0)) * state.t)
    draw(at())
    morph.current = finish(animate(state, {
      t: 1, duration: MORPH, ease: 'outExpo',
      onUpdate: () => draw(at()),
      onComplete: () => {
        morph.current = null
        draw(heights)
      },
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heightsKey, reduced])
  useLayoutEffect(() => () => { morph.current?.cancel() }, [])

  // A new county slides the pill over (from where it is, if it is still sliding), pops its count and fades its name in.
  const lastActive = useRef(active)
  useLayoutEffect(() => {
    const before = lastActive.current
    lastActive.current = active
    if (!pill.current || reduced || before === active || before < 0 || before >= n) return
    const step = columnWidth + COLUMN_GAP
    finish(animate(pill.current, {
      translateX: [(before - active) * step + (utils.get(pill.current, 'translateX', false) as number), 0],
      duration: 550, ease: 'outExpo', onComplete: releaseStyles('transform'),
    }))
    const count = all('[data-slot="value-text"]')[active]
    if (count) finish(animate(count, { scale: [0.86, 1], duration: 500, ease: 'outBack(2)', onComplete: releaseStyles('transform') }))
    if (nameRef.current) {
      finish(animate(nameRef.current, { opacity: [0.4, 1], duration: 300, ease: 'outQuad', onComplete: releaseStyles('opacity') }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, reduced])

  // The workers sought count from the number on screen to the new county's.
  useLayoutEffect(() => {
    const count = workersCount.current
    if (countingWorkers.current || count.value === workers) return
    count.tween?.cancel()
    count.tween = null
    if (reduced) {
      showWorkers(workers)
      return
    }
    const state = { value: count.value }
    count.tween = finish(animate(state, {
      value: workers, duration: 600, ease: 'outExpo',
      onUpdate: () => showWorkers(state.value),
      onComplete: () => {
        count.tween = null
        showWorkers(workers)
      },
    }))
  }, [workers, reduced])
  useLayoutEffect(() => () => { workersCount.current.tween?.cancel() }, [])

  function select(next: number) {
    setSelected(Math.min(Math.max(next, 0), n - 1))
  }

  function onColumnKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const next = ({ ArrowRight: selected + 1, ArrowDown: selected + 1, ArrowLeft: selected - 1,
      ArrowUp: selected - 1, Home: 0, End: n - 1 } as Record<string, number>)[event.key]
    if (next === undefined) return
    event.preventDefault()
    const index = Math.min(Math.max(next, 0), n - 1)
    setHovered(null)
    select(index)
    all('[data-slot="column"]')[index]?.focus()
  }

  const fraction = `((100% - ${gaps}px) / ${n})`
  return (
    <div className="columns" ref={root}>
      <div className="selection" data-slot="selection">
        <p className="soft" ref={nameRef}>{county.name} · {formatAds(county.jobs)}</p>
        <p className="big" ref={workersRef}>{formatWorkers(workers)}</p>
      </div>
      <div className="scroller">
        <div className="chart" style={{ minWidth: `${n * MIN_COLUMN + gaps}px` }}>
          <div className="plot" role="group" aria-label="Broj oglasa po županijama" ref={plot}
            onPointerLeave={() => setHovered(null)}>
            <BarGradients ids={ids} />
            {counties.map((county, i) => (
              <button key={i} type="button" data-slot="column" className={`column${i === active ? ' active' : ''}`}
                aria-label={`${county.name}: ${formatAds(county.jobs)}, ${formatWorkers(county.workers_needed)}, `
                  + formatShare(county.share)}
                aria-pressed={i === selected} tabIndex={i === selected ? 0 : -1}
                onPointerEnter={() => setHovered(i)} onClick={() => select(i)} onKeyDown={onColumnKeyDown}>
                <svg className="bar" data-slot="bar" viewBox={BAR_VIEW} preserveAspectRatio="none" aria-hidden="true"
                  style={{ width: `${barWidth}px`, left: `calc(50% - ${barWidth / 2}px)`, height: `${heights[i]}px` }}>
                  <BarLook ids={ids} lit={false} opacity={i === active ? 0 : 0.32} />
                  <BarLook ids={ids} lit opacity={i === active ? 1 : 0} />
                </svg>
                {/* the count, centred 4px over the bar */}
                <span className="value" data-slot="value" aria-hidden="true"
                  style={{ bottom: `${round(heights[i] + VALUE_GAP)}px` }}>
                  <BarValue value={values[i]} />
                </span>
                {/* keyboard focus rings the column */}
                <span className="focus-ring" aria-hidden="true" />
              </button>
            ))}
          </div>
          <div className="axis" aria-hidden="true">
            <span className="pill" ref={pill}
              style={{ width: `calc${fraction}`, left: `calc(${active} * (${fraction} + ${COLUMN_GAP}px))` }} />
            {counties.map((county, i) => (
              <span key={i} data-slot="axis-label" className={`axis-label${i === active ? ' active' : ''}`}
                title={county.name}>
                {/* A break after each hyphen: "Splitsko-" over "dalmatinska" instead of a cut word. */}
                <span>{county.short_name.replaceAll('-', '-​')}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
