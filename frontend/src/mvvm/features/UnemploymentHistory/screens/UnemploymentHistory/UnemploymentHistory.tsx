import { cn } from 'cn'
import { Badge } from '@/components/ui/badge'
// show_unemployment_history: the counties' monthly registered unemployment rate (DZS) as lines, a legend that also
// explains the provisional band and the gaps, and per county the latest rate against the same month a year earlier.
// The tiles fade in one after another once the lines have drawn in.

import { stagger } from 'animejs'
import { useRef } from 'react'
import { Card, Notes, Warning } from '../../../../components/Card'
import { fadeIn, useChartEntrance } from '../../../../hooks/chart-motion'
import { formatDay, formatMonth, formatPoints, formatRate, plural } from '../../../../utils/format'
import { Sources } from '../../../../components/Sources'
import { UnemploymentGrowthChart } from '../../components/UnemploymentGrowthChart'
import type { CountyHistory, UnemploymentHistoryData } from '../../types'
import type { useHistoryChart } from '../../hooks/use-history-chart'

const TILES_AT = 700
const TILE_STAGGER = 80

export function UnemploymentHistory({ data, chart, onOpenLink }: {
  data: UnemploymentHistoryData | null
  chart: ReturnType<typeof useHistoryChart>
  onOpenLink: (url: string) => void
}) {
  if (!data) return <Card title="Stopa registrirane nezaposlenosti" description="Učitavanje…" loading />
  const charted = data.counties.some((county) => county.series.length)
  return (
    <Card title={data.title} description={data.description}>
      {charted ? <History chart={chart} data={data} onOpenLink={onOpenLink} /> : (
        <>
          <Warning text={data.unavailable_label ?? 'Podaci o nezaposlenosti nisu dostupni.'} />
          <Footer data={data} onOpenLink={onOpenLink} />
        </>
      )}
    </Card>
  )
}

/** Mounted once the data is there, so its entrance plays with the data. */
function History({ data, chart, onOpenLink }: {
  data: UnemploymentHistoryData
  chart: ReturnType<typeof useHistoryChart>
  onOpenLink: (url: string) => void
}) {
  const root = useRef<HTMLDivElement>(null)

  useChartEntrance(root, (timeline) => {
    const items = [...root.current!.querySelectorAll<HTMLElement>('[data-slot="legend"] > li')]
    const tiles = [...root.current!.querySelectorAll<HTMLElement>('[data-slot="tile"]')]
    timeline.add(items, { ...fadeIn(items, 4), duration: 500, delay: stagger(50) }, 0)
    timeline.add(tiles, { ...fadeIn(tiles, 10), duration: 700, ease: 'outExpo', delay: stagger(TILE_STAGGER) }, TILES_AT)
    return () => {
      for (const el of [...items, ...tiles]) {
        el.style.removeProperty('opacity')
        el.style.removeProperty('transform')
      }
    }
  })

  return (
    <div className="history [--series-1:#8979ff] [--series-2:#f58233] [--series-3:#3a6ee8] [--series-4:#19965a]
      [--series-5:#c85594] [--series-6:#a38500] dark:[--series-1:#a99dff] dark:[--series-2:#ff9d5c]
      dark:[--series-3:#79a2ff] dark:[--series-4:#5ed799] dark:[--series-5:#f58fc9] dark:[--series-6:#ddc45a]
      [&_.s1]:[--series:var(--series-1)] [&_.s2]:[--series:var(--series-2)] [&_.s3]:[--series:var(--series-3)]
      [&_.s4]:[--series:var(--series-4)] [&_.s5]:[--series:var(--series-5)] [&_.s6]:[--series:var(--series-6)]
      flex flex-col gap-5 min-w-0" ref={root}>
      <UnemploymentGrowthChart {...chart} />
      <div className="tiles grid [grid-template-columns:repeat(auto-fill,_minmax(190px,_1fr))] gap-2">
        {data.counties.map((county, index) => <Tile key={county.code} county={county} index={index} />)}
      </div>
      <Footer data={data} onOpenLink={onOpenLink} />
    </div>
  )
}

function Tile({ county, index }: { county: CountyHistory; index: number }) {
  const { latest, same_month_previous_year: before, change_pp: change } = county
  const missing = county.series.filter((point) => point.rate === null).length
  const direction = change === null ? null : change < 0 ? 'down' : change > 0 ? 'up' : 'same'
  return (
    <section className="tile flex flex-col gap-2 min-w-0 p-3 rounded-[14px] bg-surface-sunken [&_p]:m-0 [&_>_.soft]:font-normal
      [&_>_.soft]:leading-[1.35]" data-slot="tile" aria-label={county.name}>
      <p className="tile-name flex items-center gap-2 text-[13px] font-semibold"><span className={`swatch flex-none w-3 [height:3px] rounded-[2px] [background:var(--series)] s${index + 1}`} />{county.name}</p>
      {latest && (
        <div className="tile-latest flex flex-col gap-1.5 [&_.soft]:flex [&_.soft]:items-center [&_.soft]:gap-1.5">
          <p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">
            {formatMonth(latest.period)}
            {latest.is_provisional && <Badge variant="provisional" className="provisional">privremeno</Badge>}
          </p>
          <p className={latest.rate === null ? "tile-missing text-[13px] italic text-fg-soft" : "big m-0 text-[28px] font-semibold leading-[1] whitespace-nowrap tabular-nums"}>
            {latest.rate === null ? 'nema podatka' : formatRate(latest.rate)}
          </p>
        </div>
      )}
      {before && (
        <p className="tile-before text-[13px] text-fg-soft tabular-nums">
          {formatMonth(before.period)}: {before.rate === null ? 'nema podatka' : formatRate(before.rate)}
        </p>
      )}
      {change !== null ? (
        <p className="tile-change flex flex-col items-start gap-1 [&_.soft]:font-normal [&_.soft]:leading-[1.35]">
          <Badge className={cn('change', direction)} variant={direction === 'down' ? 'success' : direction === 'up' ? 'warning' : 'secondary'}>
            {direction !== 'same' && (
              <svg viewBox="0 0 12 12" aria-hidden="true">
                <path d={direction === 'down' ? 'M6 2v8M2.5 6.5 6 10l3.5-3.5' : 'M6 10V2M2.5 5.5 6 2l3.5 3.5'} />
              </svg>
            )}
            {formatPoints(change)}
          </Badge>
          <span className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">prema istom mjesecu prošle godine</span>
        </p>
      ) : (
        <p className="tile-change unavailable flex flex-col items-start gap-1 [&_.soft]:font-normal [&_.soft]:leading-[1.35]">
          <Badge className="change none" variant="secondary">promjena nije dostupna</Badge>
          {county.change_unavailable_label && <span className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">{county.change_unavailable_label}</span>}
        </p>
      )}
      {missing > 0 && (
        <p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">Nema podatka za {missing} {plural(missing, 'mjesec', 'mjeseca', 'mjeseci')} u nizu.</p>
      )}
    </section>
  )
}

function Footer({ data, onOpenLink }: { data: UnemploymentHistoryData; onOpenLink: (url: string) => void }) {
  return (
    <>
      <Sources onOpenLink={onOpenLink} links={data.source_links}>
        {data.dzs && <span>DZS podaci uvezeni {formatDay(data.dzs.finished_at)}</span>}
      </Sources>
      <Notes warning={null} note={data.view_notes} />
    </>
  )
}
