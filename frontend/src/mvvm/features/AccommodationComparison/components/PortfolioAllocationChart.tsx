import { cn } from 'cn'
import { Button } from '@/components/ui/button'
import { RollLabel } from '@/components/RollLabel'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
// Domain adaptation of the supplied PortfolioAllocationChart, drawn as a shadcn chart donut over Recharts: one
// ramp (offered red, not offered grey, unknown light grey), share discs on the segments, a readout over the ring
// with the active segment's name, share and ad count, and the other segments dimmed. Drawn flat, as Dalco draws:
// no shadow, glow, bevel or glass. Each segment is a button: hover previews, click or the arrow keys select. The
// readout fades in and counts up while the ring sweeps in; another active segment rolls its name in and
// counts to its number.
import { type KeyboardEvent, useId, useLayoutEffect, useRef } from 'react'
import { Pie, PieChart, Sector } from 'recharts'
import { clearEntrance, countTo, EASE, enter, MOTION, roll, s, useChartEntrance, useReducedMotion }
  from '../../../hooks/chart-motion'
import { formatAds, formatInteger, formatShare } from '../../../utils/format'
import type { useAllocation } from '../hooks/use-allocation'

const percent = (value: number) => `${formatInteger(value)} %`

/** Slice is one visible group as the ring draws it; index is the group's position in groups. */
interface Slice { index: number; key: string; value: number }
const config = {
  offered: { label: 'Nudi smještaj', color: 'var(--accent-500)' },
  not_offered: { label: 'Ne nudi smještaj', color: 'var(--surface-disable)' },
  unknown: { label: 'Podatak nije poznat', color: 'var(--surface-subdued)' },
} satisfies ChartConfig

export function PortfolioAllocationChart(model: ReturnType<typeof useAllocation>) {
  const root = useRef<HTMLDivElement>(null)
  const { groups, total, hidden, values, shown, visibleTotal, shares, active, selected, tabStop,
    filtered, denominator, readout, showGroups, selectGroup,
    hoverGroup, previewGroup, navigate, resetGroups } = model
  const slices: Slice[] = shown.map((index) => ({ index, key: groups[index].key, value: values[index] }))
  const reduced = useReducedMotion()
  const id = useId().replace(/[^\w-]/g, '')
  const contextRef = useRef<HTMLParagraphElement>(null)
  const amountRef = useRef<HTMLParagraphElement>(null)
  const all = (selector: string) => [...root.current?.querySelectorAll<HTMLElement>(selector) ?? []]

  // The readout's ad count on screen; the entrance counts it up from zero, later changes count from here.
  const latestAmount = useRef(readout.amount)
  useLayoutEffect(() => { latestAmount.current = readout.amount })
  const countingAmount = useRef(false)
  const amountCount = useRef<{ tween: gsap.core.Tween | null; value: number }>({ tween: null, value: readout.amount })
  const showAmount = (value: number) => {
    amountCount.current.value = value
    if (amountRef.current) amountRef.current.textContent = formatAds(value)
  }

  useChartEntrance(root, (timeline) => {
    const { readout, headline, labels } = MOTION
    const lines = all('[data-slot="allocation-readout"] > *')
    enter(timeline, lines, readout.at, readout)
    const up = { t: 0 }
    const countUp = () => showAmount(latestAmount.current * up.t)
    countingAmount.current = true
    countUp()
    timeline.fromTo(up, { t: 0 }, { t: 1, duration: s(headline.duration), ease: EASE.arrive, onUpdate: countUp,
      onComplete: () => { countingAmount.current = false } }, s(headline.at))
    const buttons = all('.allocation-legend-item')
    enter(timeline, buttons, labels.at)
    return () => {
      countingAmount.current = false
      showAmount(latestAmount.current)
      clearEntrance([...lines, ...buttons])
    }
  })

  // Another active segment rolls its name in from below.
  const lastActive = useRef(active)
  useLayoutEffect(() => {
    const before = lastActive.current
    lastActive.current = active
    if (reduced || before === active || !contextRef.current) return
    roll(contextRef.current)
  }, [active, reduced])

  // The ad count counts from the number on screen to the new one; during the entrance its count-up carries on to it.
  useLayoutEffect(() => {
    const count = amountCount.current
    if (countingAmount.current || count.value === readout.amount) return
    count.tween?.kill()
    count.tween = null
    if (reduced) { showAmount(readout.amount); return }
    count.tween = countTo({ value: count.value }, readout.amount, showAmount)
  }, [readout.amount, reduced])
  useLayoutEffect(() => () => { amountCount.current.tween?.kill() }, [])

  function onSliceKeyDown(event: KeyboardEvent<SVGElement>, index: number) {
    const next = navigate(event.key, index)
    if (next === null) return
    event.preventDefault()
    // After Recharts has redrawn for the new selection: it replaces its segments' elements whenever the chart
    // renders again, one store update after React's own commit, so focus set any sooner is lost with them.
    setTimeout(() => root.current
      ?.querySelector<SVGElement>(`[data-slot="allocation-slice-button"][data-index="${next}"]`)?.focus())
  }

  // One ramp for the parts of the whole: offered is the signal red, not offered the darker grey and unknown the
  // lighter one, so only the red stands out. Card-coloured strokes part neighbouring segments; focus dims the
  // others to 32 %, as the county chart's grey columns.
  return <div className="portfolio-allocation
    [&_.allocation-offered]:[--allocation-color:var(--accent-500)]
    [&_.allocation-not\_offered]:[--allocation-color:var(--surface-disable)]
    [&_.allocation-unknown]:[--allocation-color:var(--surface-subdued)]
    flex flex-col items-center gap-6 min-w-0 w-full" ref={root} data-slot="accommodation-chart">
    <div className="allocation-readout flex flex-col items-start gap-2.5 self-stretch" data-slot="allocation-readout">
      {/* Clips the name as it rolls in from below on a new segment. Only label words are uppercase: names and
          values with their units keep their own case. */}
      <div className="overflow-clip">
        <p className="allocation-context m-0 mono-label text-fg-soft" ref={contextRef}>
          {readout.name && <>{readout.name} · </>}{readout.share && <>{readout.share} </>}<span className="uppercase">{readout.detail}</span>
        </p>
      </div>
      <p className="allocation-amount m-0 mono-headline whitespace-nowrap text-fg-loud" ref={amountRef}>{formatAds(readout.amount)}</p>
    </div>
    {/* The ring; Pie sweeps it in and morphs it to new shares. Each segment is a button: hover previews, click
        selects, the arrow keys move the selection. A click beside the segments clears it. */}
    <ChartContainer config={config} className="allocation-ring aspect-square [width:min(100%,_400px)] mono-label"
      role="group" aria-label="Udjeli skupina smještaja" aria-describedby={`${id}-hint`}
      onClick={(event) => { if (!(event.target as Element).closest('[data-slot="allocation-slice-button"]')) selectGroup(null) }}
      onPointerLeave={() => hoverGroup(null)}>
      <PieChart accessibilityLayer={false} throttledEvents={[]}>
        <ChartTooltip cursor={false} content={({ active: shown, payload }) => {
          const index = payload?.[0]?.payload?.index as number | undefined
          if (!shown || index == null) return null
          return <ChartTooltipContent active hideIndicator label={groups[index].label} labelClassName="text-fg-loud"
            payload={[formatAds(values[index]), `${formatShare(shares[index])} ${denominator}`]
              .map((value) => ({ value, dataKey: value, graphicalItemId: value, name: value }))}
            formatter={(value) => <span>{String(value)}</span>} />
        }} />
        <Pie data={slices} dataKey="value" nameKey="key" startAngle={90} endAngle={-270} innerRadius="58%"
          outerRadius="96%" isAnimationActive={!reduced}
          animationBegin={MOTION.marks.at} animationDuration={MOTION.marks.duration} labelLine={false}
          label={({ cx, cy, midAngle, innerRadius, outerRadius, payload }) => {
            const slice = payload as Slice | undefined
            // A share disc mid-ring, left out where the segment is too narrow to hold it.
            if (!slice || shares[slice.index] < 6) return null
            const radius = (Number(innerRadius) + Number(outerRadius)) / 2
            const angle = -Number(midAngle) * Math.PI / 180
            const x = Number(cx) + radius * Math.cos(angle)
            const y = Number(cy) + radius * Math.sin(angle)
            const dimmed = active !== null && active !== slice.index
            return <g data-slot="allocation-pill" data-index={slice.index} aria-hidden="true"
              className={cn('allocation-pill pointer-events-none [transition:opacity_300ms] motion-reduce:[transition:none]',
                `allocation-${slice.key}`, dimmed && 'opacity-40')}>
              <circle cx={x} cy={y} r={20} className="allocation-disc fill-card stroke-border" data-slot="allocation-disc" />
              <text x={x} y={y} dy="0.35em" textAnchor="middle" className="fill-fg-soft" data-slot="allocation-share"
                data-share={shares[slice.index]}>{percent(shares[slice.index])}</text>
            </g>
          }}
          rootTabIndex={-1} onMouseEnter={(sector) => hoverGroup((sector.payload as Slice | undefined)?.index ?? null)}
          // Each segment wrapped in a button of its own, since Recharts keeps its sectors out of the tab order. Read
          // the segment's group from its own data: while Recharts morphs to fewer groups, it still draws the old ones.
          shape={(props) => {
            const slice = props.payload as Slice
            const dimmed = active !== null && active !== slice.index
            return <g data-slot="allocation-slice-button" data-index={slice.index} data-key={slice.key}
              role="button" tabIndex={slice.index === tabStop ? 0 : -1} aria-pressed={slice.index === selected}
              aria-label={`${groups[slice.index].label}: ${formatAds(values[slice.index])}, `
                + `${formatShare(shares[slice.index])} ${denominator}`}
              className="allocation-slice-button cursor-pointer outline-none [-webkit-tap-highlight-color:transparent]
                [&:focus-visible_path]:[stroke:var(--accent-500)] [&:focus-visible_path]:[stroke-width:3]"
              onClick={() => selectGroup(slice.index)} onKeyDown={(event) => onSliceKeyDown(event, slice.index)}>
              {/* A dimmed segment keeps a surface-disable edge, so the lightest one never fades into the card. */}
              <Sector {...props} fill={`var(--color-${slice.key})`} fillOpacity={dimmed ? 0.32 : 1}
                stroke={dimmed ? 'var(--surface-disable)' : 'var(--card)'} strokeWidth={1}
                className={cn('allocation-shape [transition:fill-opacity_300ms] motion-reduce:[transition:none]',
                  `allocation-${slice.key}`)} />
            </g>
          }} />
      </PieChart>
    </ChartContainer>
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
            bg-(--allocation-color)
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
    <p id={`${id}-hint`} data-enter className="soft allocation-hint m-0 text-[12px] font-medium leading-[1.25] text-fg-soft w-full">Odaberite segment za broj i udio oglasa. Klikom na legendu sakrivate ili vraćate skupinu; strelicama birate segment.</p>
  </div>
}
