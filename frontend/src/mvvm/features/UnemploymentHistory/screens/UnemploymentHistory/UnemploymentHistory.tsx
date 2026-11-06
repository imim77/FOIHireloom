import { cn } from 'cn'
import { Badge } from '@/components/ui/badge'
// show_unemployment_history: the counties' monthly registered unemployment rate (DZS) as lines, a legend that picks
// the county to light up and explains the provisional band and the gaps, and per county the latest rate against the
// same month a year earlier; the focused county's tile is marked like its curve. The tiles fade in one after another
// once the lines have drawn in.

import { stagger } from 'animejs'
import { useRef } from 'react'
import { Card, Notes, Warning } from '../../../../components/Card'
import { fadeIn, MOTION, useChartEntrance } from '../../../../hooks/chart-motion'
import { formatDay, formatMonth, formatPoints, formatRate, plural } from '../../../../utils/format'
import { Sources } from '../../../../components/Sources'
import { UnemploymentGrowthChart } from '../../components/UnemploymentGrowthChart'
import type { CountyHistory, UnemploymentHistoryData } from '../../types'
import type { useHistoryChart } from '../../hooks/use-history-chart'

const EYEBROW = 'Nezaposlenost'
// The tiles come in once the curves are half drawn.
const TILES_AT = MOTION.marks.at + MOTION.marks.duration / 2

export function UnemploymentHistory({ data, chart, onOpenLink }: {
  data: UnemploymentHistoryData | null
  chart: ReturnType<typeof useHistoryChart>
  onOpenLink: (url: string) => void
}) {
  if (!data) return <Card eyebrow={EYEBROW} title="Stopa registrirane nezaposlenosti" description="Učitavanje…" loading />
  const charted = data.counties.some((county) => county.series.length)
  return (
    <Card eyebrow={EYEBROW} title={data.title} description={data.description}>
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
    const tiles = [...root.current!.querySelectorAll<HTMLElement>('[data-slot="tile"]')]
    timeline.add(tiles, { ...fadeIn(tiles, MOTION.readout.rise), duration: MOTION.readout.duration,
      delay: stagger(MOTION.marks.stagger) }, TILES_AT)
    return () => {
      for (const el of tiles) {
        el.style.removeProperty('opacity')
        el.style.removeProperty('transform')
      }
    }
  })

  return (
    <div className="history flex flex-col gap-6 min-w-0" ref={root}>
      <UnemploymentGrowthChart {...chart} />
      <div className="tiles grid [grid-template-columns:repeat(auto-fill,_minmax(190px,_1fr))] gap-2">
        {data.counties.map((county) => <Tile key={county.code} county={county}
          lit={chart.series[chart.activeSeries]?.id === county.code} />)}
      </div>
      <Footer data={data} onOpenLink={onOpenLink} />
    </div>
  )
}

function Tile({ county, lit }: { county: CountyHistory; lit: boolean }) {
  const { latest, same_month_previous_year: before, change_pp: change } = county
  const missing = county.series.filter((point) => point.rate === null).length
  const direction = change === null ? null : change < 0 ? 'down' : change > 0 ? 'up' : 'same'
  return (
    <section className="tile flex flex-col gap-2 min-w-0 p-3 rounded-[10px] bg-surface-sunken [&_p]:m-0 [&_>_.soft]:font-normal
      [&_>_.soft]:leading-[1.35]" data-slot="tile" data-lit={lit} aria-label={county.name}>
      <p className="tile-name flex items-center gap-2 text-[14px] font-medium">
        <span className={cn('swatch h-[3px] w-3 flex-none rounded-[2px] transition-colors duration-300 motion-reduce:transition-none',
          lit ? 'bg-accent-500' : 'bg-surface-disable')} aria-hidden="true" />{county.name}</p>
      {latest && (
        <div className="tile-latest flex flex-col gap-1.5 [&_.soft]:flex [&_.soft]:items-center [&_.soft]:gap-1.5">
          {/* The badge keeps its own case, as in the readout; the month never breaks. */}
          <p className="soft m-0 flex-wrap mono-label text-fg-soft">
            <span className="whitespace-nowrap uppercase">{formatMonth(latest.period)}</span>
            {latest.is_provisional && <Badge variant="provisional" className="provisional">privremeno</Badge>}
          </p>
          <p className={latest.rate === null ? "tile-missing text-[14px] italic text-fg-soft" : "big m-0 font-mono text-[16px] font-medium leading-[1.25] whitespace-nowrap"}>
            {latest.rate === null ? 'nema podatka' : formatRate(latest.rate)}
          </p>
        </div>
      )}
      {before && (
        <p className="tile-before mono-label uppercase text-fg-soft">
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
