import { Button } from '@/components/ui/button'
import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { cn } from 'cn'
// The counties as flat columns drawn with shadcn chart over Recharts, after the "Investment App User Age Chart" from
// the Keitoto library: the active county is red with its name in a dark pill, the others grey; the selected county's
// workers sought stand over the chart. Hover previews a county, click or the arrow keys select one. Recharts grows
// the columns from their feet and regrows them from the heights on screen for new data; GSAP brings the
// selection in, counts the workers to the active county's number and rolls its name in.

import { type KeyboardEvent, useLayoutEffect, useRef } from 'react'
import { Bar, BarChart, Cell, LabelList, XAxis, YAxis } from 'recharts'
import { clearEntrance, enter, MOTION, roll, useChartEntrance, useReducedMotion }
  from '../../../hooks/chart-motion'
import { formatAds, formatInteger, formatShare, formatWorkers } from '../../../utils/format'
import { useReadoutCount } from '../../../hooks/use-readout-count'
import type { useJobsByCounty } from '../hooks/use-jobs-by-county'

const PLOT_HEIGHT = 209 // the tallest column with its 16px value and a 4px gap over it
const BAR_WIDTH = 48 // centred in its column; narrower columns narrow it
// The narrowest column; the plot scrolls sideways below it. Wide enough for the longest mono name part,
// "Koprivničko-" (92px), and the label's 2px sides, so no name is cut mid-word.
const MIN_COLUMN = 96
const PILL_MARGIN = 4 // between neighbouring pills, on each side

const config = {
  active: { label: 'Odabrana županija', color: 'var(--accent-500)' },
  county: { label: 'Županija', color: 'var(--surface-disable)' },
} satisfies ChartConfig

export function CountyColumns({ counties, values, selected, active, county, workers, selectCounty, hoverCounty, navigate }:
  ReturnType<typeof useJobsByCounty>['columns']) {
  const n = counties.length
  const reduced = useReducedMotion()
  const root = useRef<HTMLDivElement>(null)
  const nameRef = useRef<HTMLParagraphElement>(null)
  const workersRef = useRef<HTMLParagraphElement>(null)
  const workersCount = useReadoutCount(workersRef, workers, formatWorkers)
  const all = (selector: string) => [...root.current?.querySelectorAll<HTMLElement>(selector) ?? []]
  const rows = counties.map((county, index) => ({ index, name: county.name, value: values[index] }))

  // Entrance: the selection comes in and its workers count up while Recharts grows the columns, then the names come in.
  useChartEntrance(root, (timeline) => {
    const finishCount = workersCount(timeline)
    const selection = all('[data-slot="selection"] > *')
    const names = all('[data-slot="column"] > span')
    const { readout, labels } = MOTION
    enter(timeline, selection, readout.at, readout)
    enter(timeline, names, labels.at)
    return () => {
      finishCount()
      clearEntrance([...selection, ...names])
    }
  })

  // A new county rolls its name in from below.
  const lastActive = useRef(active)
  useLayoutEffect(() => {
    const before = lastActive.current
    lastActive.current = active
    if (!nameRef.current || reduced || before === active) return
    roll(nameRef.current)
  }, [active, reduced])

  function onColumnKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const index = navigate(event.key)
    if (index === null) return
    event.preventDefault()
    all('[data-slot="column"]')[index]?.focus()
  }

  const columns = { gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }
  return (
    <div className="columns flex flex-col gap-6" ref={root}>
      <div className="selection flex flex-col items-start gap-2.5" data-slot="selection">
        {/* Clips the name as it rolls in from below on a new county. */}
        <div className="overflow-clip">
          {/* Mono like every label, but only the count is uppercase: county names keep their own case. */}
          <p className="soft m-0 mono-label text-fg-soft" ref={nameRef}>
            {county.name} · <span className="uppercase">{formatAds(county.jobs)}</span>
          </p>
        </div>
        <p className="big m-0 mono-headline text-fg-loud whitespace-nowrap" ref={workersRef}>{formatWorkers(workers)}</p>
      </div>
      <div className="scroller overflow-x-auto overflow-y-hidden p-1 [margin:-4px]">
        <div className="chart flex flex-col gap-2" style={{ minWidth: `${n * (MIN_COLUMN + 2 * PILL_MARGIN)}px` }}
          onPointerLeave={() => hoverCounty(null)}>
          {/* Decorative: every value is in the columns' buttons below. */}
          <ChartContainer config={config} aria-hidden="true" className="plot aspect-auto w-full mono-label"
            style={{ height: PLOT_HEIGHT }}>
            <BarChart data={rows} margin={{ top: 20, right: 0, bottom: 0, left: 0 }} barCategoryGap={8}
              accessibilityLayer={false} throttledEvents={[]}>
              <XAxis dataKey="index" hide />
              <YAxis hide domain={[0, 'dataMax']} />
              <ChartTooltip cursor={false} content={({ active: shown, label }) => {
                const index = Number(label)
                const item = counties[index]
                if (!shown || !item) return null
                return <ChartTooltipContent active hideIndicator label={item.name} labelClassName="text-fg-loud"
                  payload={[formatAds(item.jobs), formatWorkers(item.workers_needed), formatShare(item.share)]
                    .map((value) => ({ value, dataKey: value, graphicalItemId: value, name: value }))}
                  formatter={(value) => <span>{String(value)}</span>} />
              }} />
              <Bar dataKey="value" maxBarSize={BAR_WIDTH} radius={[4, 4, 0, 0]} isAnimationActive={!reduced}
                animationBegin={MOTION.marks.at} animationDuration={MOTION.marks.duration}
                onMouseEnter={(_, index) => hoverCounty(index)} onClick={(_, index) => selectCounty(index)}
                className="cursor-pointer">
                {rows.map((row) => <Cell key={row.index} data-slot="bar" data-lit={row.index === active}
                  fill={row.index === active ? 'var(--color-active)' : 'var(--color-county)'}
                  fillOpacity={row.index === active ? 1 : 'var(--grey-look-opacity)'}
                  className="[transition:fill_300ms,fill-opacity_300ms] motion-reduce:[transition:none]" />)}
                {/* the count, 4px over the bar */}
                <LabelList dataKey="value" position="top" offset={4}
                  content={({ x, y, width, value }) => <text x={Number(x) + Number(width) / 2} y={Number(y) - 4}
                    textAnchor="middle" className="fill-fg-soft" data-slot="value-text">
                    {formatInteger(Number(value))}</text>} />
              </Bar>
            </BarChart>
          </ChartContainer>
          <div className="axis grid" role="group" aria-label="Broj oglasa po županijama" style={columns}>
            {counties.map((county, i) => (
              <Button variant="ghost" key={i} type="button" data-slot="column"
                className={cn('column axis-label relative h-auto min-w-0 rounded-full px-0.5! py-1.5 mx-1',
                  'transition-[background-color,color] duration-300 motion-reduce:transition-none',
                  'focus-visible:border-transparent focus-visible:ring-0',
                  i === active && 'active bg-surface-muted hover:bg-surface-muted')}
                title={county.name}
                aria-label={`${county.name}: ${formatAds(county.jobs)}, ${formatWorkers(county.workers_needed)}, `
                  + formatShare(county.share)}
                aria-pressed={i === selected} tabIndex={i === selected ? 0 : -1}
                onPointerEnter={() => hoverCounty(i)} onClick={() => selectCounty(i)} onKeyDown={onColumnKeyDown}>
                {/* A break after each hyphen: "Splitsko-" over "dalmatinska" instead of a cut word. */}
                <span className={cn('[display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]',
                  'overflow-hidden text-ellipsis whitespace-normal text-center mono-label text-fg-soft',
                  '[transition:color_300ms] motion-reduce:[transition:none]',
                  i === active && 'font-medium text-fg-on-muted')}>
                  {county.short_name.replaceAll('-', '-​')}</span>
                {/* keyboard focus rings the column */}
                <span className="focus-ring pointer-events-none absolute -inset-1 rounded-full opacity-0 shadow-focus
                  transition-opacity duration-150 group-focus-visible/button:opacity-100" aria-hidden="true" />
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
