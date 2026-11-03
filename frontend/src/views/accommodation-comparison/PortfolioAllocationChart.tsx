// Domain adaptation of the supplied PortfolioAllocationChart. Geometry, stepped bands, sweep, morphing,
// glass pills and interactive legend follow the reference; values count ads instead of currency.
import { animate, stagger } from 'animejs'
import { type KeyboardEvent, type MouseEvent, type PointerEvent, useCallback, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { fadeIn, finish, releaseStyles, useChartEntrance, useCountUp, useReducedMotion } from '../../shared/chart-motion'
import { formatAds, formatInteger, formatShare } from '../../shared/format'
import { SIZE, START_ANGLE, TUCK, interpolateGeometry, layoutRing, mod, pillPlace, sliceAt, slicePath, type SliceGeometry } from './ring-geometry'
import type { AccommodationGroup } from './types'

const SWEEP_AT = 150
const SWEEP = 1400
const LAYERS = [{ name: 'drop', spread: 0 }, { name: 'rim', spread: -1 }, { name: 'glow', spread: -2 },
  { name: 'shape', spread: 0 }, { name: 'veil', spread: 0 }]
const inOutCubic = (t: number) => t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
const percent = (value: number) => `${formatInteger(value)} %`

function Amount({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  useCountUp(ref, value, formatInteger, { duration: 450 })
  return <span ref={ref} className="allocation-amount">{formatInteger(value)}</span>
}

function Pill({ index, share, geometry, dimmed }: { index: number; share: number; geometry: SliceGeometry; dimmed: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  useCountUp(ref, share, percent, { duration: 700 })
  const place = pillPlace(geometry)
  return <span aria-hidden="true" data-slot="allocation-pill" data-index={index}
    className={`allocation-pill${!place.fits ? ' is-hidden' : ''}${dimmed ? ' is-dimmed' : ''}`}
    style={{ left: `${place.left / SIZE * 100}%`, top: `${place.top / SIZE * 100}%` }}>
    <span className="allocation-glass" data-slot="allocation-glass">
      <span ref={ref} data-slot="allocation-share" data-share={share}>{percent(share)}</span>
    </span>
  </span>
}

export function PortfolioAllocationChart({ groups, total }: { groups: AccommodationGroup[]; total: number }) {
  const root = useRef<HTMLDivElement>(null)
  const [hidden, setHidden] = useState<string[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const [previewed, setPreviewed] = useState<number | null>(null)
  const values = useMemo(() => groups.map((group) => hidden.includes(group.key) ? 0 : group.jobs), [groups, hidden])
  const shown = values.flatMap((value, index) => value > 0 ? [index] : [])
  const visibleTotal = values.reduce((sum, value) => sum + value, 0)
  const shares = values.map((value) => visibleTotal ? value / visibleTotal * 100 : 0)
  const pick = (index: number | null) => index !== null && values[index] > 0 ? index : null
  const active = pick(hovered) ?? pick(previewed) ?? pick(selected)
  const geometry = useMemo(() => layoutRing(values, active), [values, active])
  const order = groups.map((_, index) => index).sort((a, b) => geometry[a].band - geometry[b].band)
  const latest = useRef(geometry)
  const drawn = useRef(geometry)
  const sweep = useRef<{ t: number } | null>(null)
  const previousGeometry = useRef(geometry)
  const reduced = useReducedMotion()
  const pointer = useRef('mouse')
  const id = useId().replace(/[^\w-]/g, '')

  const draw = useCallback((frame: SliceGeometry[], clip?: { from: number; upTo: number }) => {
    drawn.current = frame
    for (const layer of LAYERS) {
      for (const element of root.current?.querySelectorAll<SVGPathElement>(`[data-layer="${layer.name}"]`) ?? []) {
        element.setAttribute('d', slicePath(frame[Number(element.dataset.index)], clip, layer.spread))
      }
    }
    for (const pill of root.current?.querySelectorAll<HTMLElement>('[data-slot="allocation-pill"]') ?? []) {
      const place = pillPlace(frame[Number(pill.dataset.index)])
      pill.style.left = `${place.left / SIZE * 100}%`
      pill.style.top = `${place.top / SIZE * 100}%`
    }
  }, [])
  useLayoutEffect(() => { latest.current = geometry }, [geometry])

  useChartEntrance(root, (timeline) => {
    const state = { t: 0 }
    sweep.current = state
    const paint = () => draw(latest.current, { from: START_ANGLE, upTo: inOutCubic(state.t) * (360 + TUCK) })
    paint()
    timeline.add(state, { t: [0, 1], duration: SWEEP, ease: 'linear', onUpdate: paint,
      onComplete: () => { sweep.current = null; draw(latest.current) } }, SWEEP_AT)
    const buttons = [...root.current!.querySelectorAll<HTMLElement>('.allocation-legend-item')]
    timeline.add(buttons, { ...fadeIn(buttons, 8), duration: 700, ease: 'outExpo', delay: stagger(80) }, 500)
    for (const pill of root.current!.querySelectorAll<HTMLElement>('[data-slot="allocation-pill"]')) {
      const index = Number(pill.dataset.index)
      const g = latest.current[index]
      if (!(g.span > 0)) continue
      const reach = mod(g.start + g.span - Math.min(13.15, g.span / 2) - START_ANGLE, 360) / (360 + TUCK)
      let lo = 0, hi = 1
      for (let k = 0; k < 24; k++) {
        const middle = (lo + hi) / 2
        if (inOutCubic(middle) < reach) lo = middle
        else hi = middle
      }
      const glass = pill.querySelector<HTMLElement>('[data-slot="allocation-glass"]')!
      timeline.add(glass, { opacity: { from: 0 }, scale: { from: 0.4 }, duration: 650, ease: 'outBack(1.8)',
        onComplete: releaseStyles('opacity', 'transform') }, SWEEP_AT + lo * SWEEP - 60)
      const value = pill.querySelector<HTMLElement>('[data-slot="allocation-share"]')!
      const counter = { t: 0 }
      const count = () => { value.textContent = percent(Number(value.dataset.share) * counter.t) }
      count()
      timeline.add(counter, { t: [0, 1], duration: 900, ease: 'outExpo', onUpdate: count }, SWEEP_AT + lo * SWEEP)
    }
    return () => {
      sweep.current = null
      draw(latest.current)
      for (const node of root.current?.querySelectorAll<HTMLElement>('.allocation-legend-item, .allocation-glass') ?? []) {
        node.style.removeProperty('opacity'); node.style.removeProperty('transform')
      }
      for (const value of root.current?.querySelectorAll<HTMLElement>('[data-slot="allocation-share"]') ?? []) {
        value.textContent = percent(Number(value.dataset.share))
      }
    }
  })

  useLayoutEffect(() => {
    const before = previousGeometry.current
    previousGeometry.current = geometry
    if (before === geometry) return
    if (sweep.current && sweep.current.t < 1) {
      draw(geometry, { from: START_ANGLE, upTo: inOutCubic(sweep.current.t) * (360 + TUCK) })
      return
    }
    if (reduced) { draw(geometry); return }
    const from = drawn.current
    const state = { t: 0 }
    const paint = () => draw(geometry.map((g, index) => interpolateGeometry(from[index] ?? g, g, state.t)))
    paint()
    const sameSpans = before.every((g, index) => g.span === geometry[index].span)
    const animation = finish(animate(state, { t: 1, duration: sameSpans ? 380 : 800, ease: 'outExpo', onUpdate: paint,
      onComplete: () => draw(latest.current) }))
    return () => { animation.cancel() }
  }, [geometry, reduced, draw])

  function toggle(index: number) {
    const key = groups[index].key
    const off = hidden.includes(key)
    if (!groups[index].jobs || (!off && shown.length <= 1)) return
    setHidden(off ? hidden.filter((item) => item !== key) : [...hidden, key])
    if (!off && selected === index) setSelected(null)
  }
  function pointAt(event: PointerEvent<HTMLDivElement> | MouseEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    return sliceAt((event.clientX - box.left) / (box.width || 1) * SIZE,
      (event.clientY - box.top) / (box.height || 1) * SIZE, geometry)
  }
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') { setHovered(null); setPreviewed(null); setSelected(null); return }
    if ((event.key === 'Enter' || event.key === ' ') && active !== null) {
      event.preventDefault(); setSelected(selected === active ? null : active); return
    }
    const at = active === null ? -1 : shown.indexOf(active)
    const next = ({ ArrowRight: at + 1, ArrowDown: at + 1, ArrowLeft: at - 1, ArrowUp: at - 1,
      Home: 0, End: shown.length - 1 } as Record<string, number>)[event.key]
    if (next === undefined || !shown.length) return
    event.preventDefault()
    setHovered(shown[mod(next, shown.length)])
  }
  const sliderAt = active === null ? 0 : shown.indexOf(active)
  const sliderSlice = shown[sliderAt]
  const filtered = visibleTotal !== total
  const denominator = filtered ? 'prikazanih oglasa' : 'svih oglasa'

  return <div className="portfolio-allocation" ref={root} data-slot="accommodation-chart">
    <div className="allocation-ring">
      <svg aria-hidden="true" viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <defs>
          <filter id={`${id}-drop`} filterUnits="userSpaceOnUse" x="-80" y="-80" width="560" height="560">
            <feDropShadow dx="-2" dy="2" stdDeviation="2.7" floodOpacity="0.16" />
          </filter>
          {groups.map((group) => <filter key={group.key} id={`${id}-glow-${group.key}`} filterUnits="userSpaceOnUse" x="-80" y="-80" width="560" height="560" className={`allocation-${group.key}`}>
            <feOffset in="SourceAlpha" dx="4" /><feGaussianBlur stdDeviation="7.2" result="blurred" />
            <feFlood floodColor="var(--allocation-color)" floodOpacity="0.4" /><feComposite in2="blurred" operator="in" />
          </filter>)}
          <filter id={`${id}-bevel`} filterUnits="userSpaceOnUse" x="-20" y="-20" width="440" height="440">
            <feOffset in="SourceAlpha" dy="-1" /><feGaussianBlur stdDeviation="0.9" result="up" />
            <feComposite in="SourceAlpha" in2="up" operator="arithmetic" k2="1" k3="-1" result="edge" />
            <feFlood floodColor="#000" floodOpacity="0.16" /><feComposite in2="edge" operator="in" result="shade" />
            <feOffset in="SourceAlpha" dy="2" /><feGaussianBlur stdDeviation="0.9" result="down" />
            <feComposite in="SourceAlpha" in2="down" operator="arithmetic" k2="1" k3="-1" result="top" />
            <feFlood floodColor="#fff" floodOpacity="0.24" /><feComposite in2="top" operator="in" result="light" />
            <feMerge><feMergeNode in="SourceGraphic" /><feMergeNode in="shade" /><feMergeNode in="light" /></feMerge>
          </filter>
        </defs>
        {order.map((index) => <g key={groups[index].key} className={`allocation-slice allocation-${groups[index].key}`} data-key={groups[index].key}>
          {LAYERS.map((layer) => <path key={layer.name} data-layer={layer.name} data-index={index}
            d={slicePath(geometry[index], null, layer.spread)} className={`allocation-${layer.name}${layer.name === 'veil' && active !== null && active !== index ? ' is-visible' : ''}`}
            filter={layer.name === 'drop' ? `url(#${id}-drop)` : layer.name === 'glow' ? `url(#${id}-glow-${groups[index].key})` : layer.name === 'shape' ? `url(#${id}-bevel)` : undefined} />)}
        </g>)}
      </svg>
      <div role="slider" tabIndex={shown.length ? 0 : -1} className="allocation-hit" aria-label="Odaberite skupinu smještaja"
        aria-describedby={`${id}-hint`} aria-orientation="horizontal" aria-valuemin={0} aria-valuemax={Math.max(0, shown.length - 1)}
        aria-valuenow={sliderAt} aria-valuetext={sliderSlice !== undefined ? `${groups[sliderSlice].label}: ${formatAds(values[sliderSlice])}, ${formatShare(shares[sliderSlice])} ${denominator}` : undefined}
        onPointerMove={(event) => { if (event.pointerType === 'mouse') setHovered(pointAt(event)) }}
        onPointerDown={(event) => { pointer.current = event.pointerType; setHovered(pointAt(event)) }}
        onPointerLeave={() => setHovered(null)} onPointerCancel={() => setHovered(null)}
        onClick={(event) => { const index = pointAt(event); setSelected(selected === index ? null : index); if (pointer.current !== 'mouse') setHovered(null) }}
        onFocus={(event) => { if (event.currentTarget.matches(':focus-visible') && active === null && shown.length) setHovered(shown[0]) }}
        onBlur={() => setHovered(null)} onKeyDown={onKeyDown} />
      {groups.map((group, index) => <Pill key={group.key} index={index} share={shares[index]} geometry={geometry[index]}
        dimmed={active !== null && active !== index} />)}
      <div className="allocation-middle" aria-hidden="true">
        <span key={active ?? 'all'} className="allocation-middle-label">{active === null ? 'Ukupno oglasa' : groups[active].label}</span>
        <Amount value={active === null ? visibleTotal : values[active]} />
        <span className="allocation-middle-share">{active === null ? (filtered ? 'u prikazanim skupinama' : 'u odabranom skupu') : `${formatShare(shares[active])} ${denominator}`}</span>
      </div>
    </div>
    <div className="allocation-legend" role="group" aria-label="Skupine smještaja">
      {groups.map((group, index) => {
        const off = hidden.includes(group.key) || group.jobs === 0
        return <button key={group.key} type="button" className={`allocation-legend-item allocation-${group.key}${off ? ' is-off' : ''}`}
          aria-pressed={!off} disabled={group.jobs === 0} aria-disabled={!off && shown.length <= 1 ? true : undefined}
          aria-label={`${group.label}: ${formatAds(group.jobs)}, ${formatShare(group.share)} svih oglasa`}
          onClick={() => toggle(index)} onPointerEnter={(event) => { if (event.pointerType === 'mouse') setPreviewed(index) }}
          onPointerLeave={() => setPreviewed(null)} onFocus={() => setPreviewed(index)} onBlur={() => setPreviewed(null)}>
          <span className="allocation-dot" /><span className="allocation-legend-label">{group.label}</span>
          <span className="allocation-legend-count">{formatInteger(group.jobs)}</span>
        </button>
      })}
    </div>
    {filtered && <div className="allocation-filter-note" role="status">
      <span>Prikazano {formatInteger(visibleTotal)} od {formatInteger(total)} oglasa. Udjeli su među prikazanim oglasima.</span>
      <button type="button" className="link" onClick={() => setHidden([])}>Prikaži sve skupine</button>
    </div>}
    <p id={`${id}-hint`} className="soft allocation-hint">Odaberite segment za broj i udio oglasa. Klikom na legendu sakrivate ili vraćate skupinu; strelicama birate segment.</p>
  </div>
}
