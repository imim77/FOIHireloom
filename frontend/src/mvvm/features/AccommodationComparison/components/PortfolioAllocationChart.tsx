import { cn } from 'cn'
import { Button } from '@/components/ui/button'
import { RollLabel } from '@/components/RollLabel'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
// Domain adaptation of the supplied PortfolioAllocationChart. Geometry, stepped bands, sweep, morphing,
// share labels and interactive legend follow the reference; values count ads instead of currency. Drawn flat, as
// Dalco draws: no shadow, glow, bevel or glass, only faces, card-coloured separators and the dim veil.
// Styled after the jobs-by-county chart: one ramp (offered red, not offered grey, unknown light grey), a readout
// over the ring with the active segment's name, share and ad count, and the other segments dimmed. Each segment is
// a button: hover previews, click or the arrow keys select. The eyebrow and readout fade in and count up with the
// sweep; another active segment rolls its name in and counts to its number.
import { animate, type JSAnimation, stagger } from 'animejs'
import { type KeyboardEvent, useCallback, useId, useLayoutEffect, useMemo, useRef } from 'react'
import { fadeIn, finish, MOTION, releaseStyles, useChartEntrance, useCountUp, useReducedMotion } from '../../../hooks/chart-motion'
import { formatAds, formatInteger, formatShare } from '../../../utils/format'
import { SIZE, START_ANGLE, TUCK, interpolateGeometry, layoutRing, mod, pillPlace, slicePath, untucked,
  type SliceGeometry } from '../utils/ring-geometry'
import type { useAllocation } from '../hooks/use-allocation'

const LAYERS = [{ name: 'shape', spread: 0 }, { name: 'veil', spread: 0 }]
const inOutCubic = (t: number) => t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
const percent = (value: number) => `${formatInteger(value)} %`

function Pill({ index, groupKey, share, geometry, dimmed }:
  { index: number; groupKey: string; share: number; geometry: SliceGeometry; dimmed: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  useCountUp(ref, share, percent)
  const place = pillPlace(geometry)
  return <span aria-hidden="true" data-slot="allocation-pill" data-index={index}
    className={`allocation-pill allocation-${groupKey} absolute pointer-events-none [width:12%] [aspect-ratio:1]
      [transition:opacity_300ms] [&.is-hidden]:[opacity:0] [&.is-dimmed]:[opacity:0.4]
      motion-reduce:[transition:none] ${!place.fits ? ' is-hidden' : ''}${dimmed ? ' is-dimmed' : ''}`}
    style={{ left: `${place.left / SIZE * 100}%`, top: `${place.top / SIZE * 100}%` }}>
    {/* A flat card-coloured disc edged by a hairline, so the share reads on any slice in either theme. */}
    <span className="allocation-disc flex items-center justify-center w-full h-full rounded-full bg-card
      border border-border mono-label text-fg-soft" data-slot="allocation-disc">
      <span ref={ref} data-slot="allocation-share" data-share={share}>{percent(share)}</span>
    </span>
  </span>
}

export function PortfolioAllocationChart(model: ReturnType<typeof useAllocation>) {
  const root = useRef<HTMLDivElement>(null)
  const { groups, total, hidden, values, shown, visibleTotal, shares, active, selected, tabStop,
    filtered, denominator, readout, showGroups, selectGroup,
    hoverGroup, previewGroup, navigate, resetGroups } = model
  const geometry = useMemo(() => layoutRing(values, active), [values, active])
  const order = groups.map((_, index) => index).sort((a, b) => geometry[a].band - geometry[b].band)
  const latest = useRef(geometry)
  const drawn = useRef(geometry)
  const sweep = useRef<{ t: number } | null>(null)
  const previousGeometry = useRef(geometry)
  const reduced = useReducedMotion()
  const id = useId().replace(/[^\w-]/g, '')
  const contextRef = useRef<HTMLParagraphElement>(null)
  const amountRef = useRef<HTMLParagraphElement>(null)
  const all = (selector: string) => [...root.current?.querySelectorAll<HTMLElement>(selector) ?? []]

  const draw = useCallback((frame: SliceGeometry[], clip?: { from: number; upTo: number }) => {
    drawn.current = frame
    for (const layer of LAYERS) {
      for (const element of root.current?.querySelectorAll<SVGPathElement>(`[data-layer="${layer.name}"]`) ?? []) {
        element.setAttribute('d', slicePath(frame[Number(element.dataset.index)], clip, layer.spread))
      }
    }
    // Segment buttons cover their own angle only, so neighbours never overlap under the pointer or focus ring.
    for (const element of root.current?.querySelectorAll<SVGPathElement>('[data-slot="allocation-slice-button"]') ?? []) {
      element.setAttribute('d', slicePath(untucked(frame[Number(element.dataset.index)]), clip))
    }
    for (const pill of root.current?.querySelectorAll<HTMLElement>('[data-slot="allocation-pill"]') ?? []) {
      const place = pillPlace(frame[Number(pill.dataset.index)])
      pill.style.left = `${place.left / SIZE * 100}%`
      pill.style.top = `${place.top / SIZE * 100}%`
    }
  }, [])
  useLayoutEffect(() => { latest.current = geometry }, [geometry])

  // The readout's ad count on screen; the entrance counts it up from zero, later changes count from here.
  const latestAmount = useRef(readout.amount)
  useLayoutEffect(() => { latestAmount.current = readout.amount })
  const countingAmount = useRef(false)
  const amountCount = useRef<{ tween: JSAnimation | null; value: number }>({ tween: null, value: readout.amount })
  const showAmount = (value: number) => {
    amountCount.current.value = value
    if (amountRef.current) amountRef.current.textContent = formatAds(value)
  }

  useChartEntrance(root, (timeline) => {
    const { readout, headline, marks, labels } = MOTION
    // The card's eyebrow comes in with the readout, ahead of it.
    const eyebrow = root.current?.closest('[data-slot="card"]')?.querySelector<HTMLElement>('[data-slot="eyebrow"]')
    const lines = [...(eyebrow ? [eyebrow] : []), ...all('[data-slot="allocation-readout"] > *')]
    timeline.add(lines, { ...fadeIn(lines, readout.rise), duration: readout.duration, delay: stagger(readout.stagger) },
      readout.at)
    const up = { t: 0 }
    const countUp = () => showAmount(latestAmount.current * up.t)
    countingAmount.current = true
    countUp()
    timeline.add(up, { t: [0, 1], duration: headline.duration, ease: 'outExpo', onUpdate: countUp,
      onComplete: () => { countingAmount.current = false } }, headline.at)
    const state = { t: 0 }
    sweep.current = state
    const paint = () => draw(latest.current, { from: START_ANGLE, upTo: inOutCubic(state.t) * (360 + TUCK) })
    paint()
    timeline.add(state, { t: [0, 1], duration: marks.duration, ease: 'linear', onUpdate: paint,
      onComplete: () => { sweep.current = null; draw(latest.current) } }, marks.at)
    const buttons = all('.allocation-legend-item')
    timeline.add(buttons, { ...fadeIn(buttons, labels.rise), duration: labels.duration, delay: stagger(labels.stagger) },
      labels.at)
    for (const pill of all('[data-slot="allocation-pill"]')) {
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
      const disc = pill.querySelector<HTMLElement>('[data-slot="allocation-disc"]')!
      // Pops in as the sweep reaches it, like the pill under the lit column.
      timeline.add(disc, { opacity: { from: 0 }, scale: { from: 0.7 }, duration: MOTION.pill.duration,
        ease: 'outBack(1.7)', onComplete: releaseStyles('opacity', 'transform') }, marks.at + lo * marks.duration - 60)
      const value = pill.querySelector<HTMLElement>('[data-slot="allocation-share"]')!
      const counter = { t: 0 }
      const count = () => { value.textContent = percent(Number(value.dataset.share) * counter.t) }
      count()
      timeline.add(counter, { t: [0, 1], duration: marks.duration, ease: 'outExpo', onUpdate: count },
        marks.at + lo * marks.duration)
    }
    return () => {
      sweep.current = null
      countingAmount.current = false
      draw(latest.current)
      showAmount(latestAmount.current)
      for (const node of [...lines, ...all('.allocation-legend-item, .allocation-disc')]) {
        node.style.removeProperty('opacity'); node.style.removeProperty('transform')
      }
      for (const value of all('[data-slot="allocation-share"]')) {
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
    // Same spans: only the active slice popped out, as fast as a value pops; else new shares morph the ring.
    const animation = finish(animate(state, { t: 1, duration: sameSpans ? MOTION.pop : MOTION.morph, ease: 'outExpo', onUpdate: paint,
      onComplete: () => draw(latest.current) }))
    return () => { animation.cancel() }
  }, [geometry, reduced, draw])

  // Another active segment rolls its name in from below.
  const lastActive = useRef(active)
  useLayoutEffect(() => {
    const before = lastActive.current
    lastActive.current = active
    if (reduced || before === active || !contextRef.current) return
    finish(animate(contextRef.current, { translateY: ['100%', '0%'], duration: MOTION.roll, ease: 'outExpo',
      onComplete: releaseStyles('transform') }))
  }, [active, reduced])

  // The ad count counts from the number on screen to the new one; during the entrance its count-up carries on to it.
  useLayoutEffect(() => {
    const count = amountCount.current
    if (countingAmount.current || count.value === readout.amount) return
    count.tween?.cancel()
    count.tween = null
    if (reduced) { showAmount(readout.amount); return }
    const state = { value: count.value }
    const target = readout.amount
    count.tween = finish(animate(state, { value: target, duration: MOTION.count, ease: 'outExpo',
      onUpdate: () => showAmount(state.value),
      onComplete: () => { count.tween = null; showAmount(target) } }))
  }, [readout.amount, reduced])
  useLayoutEffect(() => () => { amountCount.current.tween?.cancel() }, [])

  function onSliceKeyDown(event: KeyboardEvent<SVGPathElement>, index: number) {
    const next = navigate(event.key, index)
    if (next === null) return
    event.preventDefault()
    root.current?.querySelector<SVGPathElement>(`[data-slot="allocation-slice-button"][data-index="${next}"]`)?.focus()
  }

  // One ramp for the parts of the whole: offered lights up red from accent-300 to accent-500, as the lit column's
  // faces do, so it reads as signal red rather than pink; not offered is the darker grey and unknown the lighter
  // one, so only the red stands out. The greys stay flat: a disable-to-subdued face would end not offered in
  // unknown's colour. Card-coloured strokes part neighbouring slices; the veil leaves inactive slices at the 32 % of the county chart's grey columns, and its
  // surface-disable edge keeps the lightest slice's shape, which the veil alone would fade into the card.
  return <div className="portfolio-allocation
    [&_.allocation-offered]:[--allocation-color:var(--accent-500)] [&_.allocation-offered]:[--allocation-top:var(--accent-300)]
    [&_.allocation-not\_offered]:[--allocation-color:var(--surface-disable)] [&_.allocation-not\_offered]:[--allocation-top:var(--surface-disable)]
    [&_.allocation-unknown]:[--allocation-color:var(--surface-subdued)] [&_.allocation-unknown]:[--allocation-top:var(--surface-subdued)]
    flex flex-col items-center gap-6 min-w-0 w-full
    [&_.allocation-shape]:[stroke:var(--card)] [&_.allocation-shape]:[stroke-width:1]
    [&_.allocation-veil]:fill-card [&_.allocation-veil]:[stroke:var(--surface-disable)] [&_.allocation-veil]:[stroke-width:1]
    [&_.allocation-veil]:[opacity:0] [&_.allocation-veil]:[transition:opacity_300ms]
    [&_.allocation-veil.is-visible]:[opacity:0.68] motion-reduce:[&_.allocation-veil]:[transition:none]" ref={root} data-slot="accommodation-chart">
    <div className="allocation-readout flex flex-col items-start gap-2.5 self-stretch" data-slot="allocation-readout">
      {/* Clips the name as it rolls in from below on a new segment. Only what is not a name is uppercase. */}
      <div className="overflow-clip">
        <p className="allocation-context m-0 mono-label text-fg-soft" ref={contextRef}>
          {readout.name && <>{readout.name} · </>}<span className="uppercase">{readout.detail}</span>
        </p>
      </div>
      <p className="allocation-amount m-0 mono-headline whitespace-nowrap text-fg-loud" ref={amountRef}>{formatAds(readout.amount)}</p>
    </div>
    <div className="allocation-ring relative [width:min(100%,_400px)] [aspect-ratio:1] m-2 [&_>_svg]:absolute [&_>_svg]:inset-0
      [&_>_svg]:w-full [&_>_svg]:h-full [&_>_svg]:overflow-visible [&_>_svg]:pointer-events-none
      [@media(max-width:_400px)]:[margin:8px_0]"
      onClick={(event) => { if (event.target === event.currentTarget) selectGroup(null) }}>
      <svg aria-hidden="true" viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <defs>
          {groups.map((group) => <linearGradient key={group.key} id={`${id}-fill-${group.key}`} x1="0" y1="0" x2="0" y2="1"
            className={`allocation-${group.key}`}>
            <stop stopColor="var(--allocation-top)" /><stop offset="1" stopColor="var(--allocation-color)" />
          </linearGradient>)}
        </defs>
        {order.map((index) => <g key={groups[index].key} className={`allocation-slice allocation-${groups[index].key}`} data-key={groups[index].key}>
          {LAYERS.map((layer) => <path key={layer.name} data-layer={layer.name} data-index={index}
            d={slicePath(geometry[index], null, layer.spread)} className={`allocation-${layer.name}${layer.name === 'veil' && active !== null && active !== index ? ' is-visible' : ''}`}
            fill={layer.name === 'shape' ? `url(#${id}-fill-${groups[index].key})` : undefined} />)}
        </g>)}
      </svg>
      {groups.map((group, index) => <Pill key={group.key} index={index} groupKey={group.key} share={shares[index]}
        geometry={geometry[index]} dimmed={active !== null && active !== index} />)}
      {/* The segments as buttons, over the pills so the pointer reaches them; transparent but for the focus ring. */}
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="group" aria-label="Udjeli skupina smještaja" aria-describedby={`${id}-hint`}
        onPointerLeave={() => hoverGroup(null)}>
        {shown.map((index) => <path key={groups[index].key} role="button" data-slot="allocation-slice-button" data-index={index}
          d={slicePath(untucked(geometry[index]))} tabIndex={index === tabStop ? 0 : -1} aria-pressed={index === selected}
          aria-label={`${groups[index].label}: ${formatAds(values[index])}, ${formatShare(shares[index])} ${denominator}`}
          className="allocation-slice-button pointer-events-auto cursor-pointer [fill:transparent] outline-none
            [-webkit-tap-highlight-color:transparent] [stroke-linejoin:round]
            focus-visible:[stroke:color-mix(in_srgb,_var(--accent-500)_40%,_transparent)] focus-visible:[stroke-width:4]"
          onPointerEnter={(event) => { if (event.pointerType === 'mouse') hoverGroup(index) }}
          onClick={() => selectGroup(index)} onKeyDown={(event) => onSliceKeyDown(event, index)} />)}
      </svg>
    </div>
    <ToggleGroup multiple value={groups.filter((group) => group.jobs > 0 && !hidden.includes(group.key)).map((group) => group.key)}
      onValueChange={showGroups} className="allocation-legend flex w-full flex-wrap gap-3"
      aria-label="Skupine smještaja">
      {groups.map((group, index) => {
        const off = hidden.includes(group.key) || group.jobs === 0
        return <ToggleGroupItem key={group.key} value={group.key}
          className={cn('allocation-legend-item h-auto min-w-0 justify-start gap-2 whitespace-normal px-3 py-2 text-left',
            'mono-label text-fg-soft [transition:color_300ms] motion-reduce:[transition:none]',
            `allocation-${group.key}`, off && 'is-off', index === active && 'is-active text-fg-loud')}
          disabled={group.jobs === 0} aria-disabled={!off && shown.length <= 1 ? true : undefined}
          aria-label={`${group.label}: ${formatAds(group.jobs)}, ${formatShare(group.share)} svih oglasa`}
          onPointerEnter={(event) => { if (event.pointerType === 'mouse') previewGroup(index) }}
          onPointerLeave={() => previewGroup(null)} onFocus={() => previewGroup(index)} onBlur={() => previewGroup(null)}>
          <span className="allocation-dot flex-none w-2.5 h-2.5 rounded-full
            [background:linear-gradient(var(--allocation-top),_var(--allocation-color))]
            [box-shadow:0_0_0_2px_var(--card),_0_0_0_3px_color-mix(in_srgb,_var(--allocation-color)_40%,_transparent)]" /><span className="allocation-legend-label flex-1">{group.label}</span>
          <span className="allocation-legend-count font-medium">{formatInteger(group.jobs)}</span>
        </ToggleGroupItem>
      })}
    </ToggleGroup>
    {filtered && <div className="allocation-filter-note flex flex-wrap items-center justify-center [gap:8px_16px] w-full text-[12px]
      leading-[1.25] text-fg-soft" role="status">
      <span>Prikazano {formatInteger(visibleTotal)} od {formatInteger(total)} oglasa. Udjeli su među prikazanim oglasima.</span>
      <Button type="button" variant="link" size="sm" className="link text-[12px]" onClick={resetGroups}><RollLabel>Prikaži sve skupine</RollLabel></Button>
    </div>}
    <p id={`${id}-hint`} className="soft allocation-hint m-0 text-[12px] font-medium leading-[1.25] text-fg-soft w-full">Odaberite segment za broj i udio oglasa. Klikom na legendu sakrivate ili vraćate skupinu; strelicama birate segment.</p>
  </div>
}
