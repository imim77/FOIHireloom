// show_unemployment_history: the counties' monthly registered unemployment rate (DZS) as lines, a legend that also
// explains the provisional band and the gaps, and per county the latest rate against the same month a year earlier.
// The tiles fade in one after another once the lines have drawn in.

import type { App } from '@modelcontextprotocol/ext-apps'
import { stagger } from 'animejs'
import { useRef } from 'react'
import { Card, Notes, Warning } from '../../shared/Card'
import { fadeIn, useChartEntrance } from '../../shared/chart-motion'
import { formatDay, formatMonth, formatPoints, formatRate, plural } from '../../shared/format'
import { useMcpApp } from '../../shared/mcp'
import { Sources } from '../../shared/Sources'
import { UnemploymentGrowthChart } from './UnemploymentGrowthChart'
import { sample } from './sample'
import type { CountyHistory, UnemploymentHistoryData } from './types'
import './unemployment-history.css'

const TILES_AT = 700
const TILE_STAGGER = 80

export function UnemploymentHistory() {
  const mcp = useMcpApp<UnemploymentHistoryData>('FOIHireloom unemployment history', sample)
  const data = mcp.data
  if (!data) return <Card title="Stopa registrirane nezaposlenosti" description="Učitavanje…" />
  const charted = data.counties.some((county) => county.series.length)
  return (
    <Card title={data.title} description={data.description}>
      {charted ? <History data={data} app={mcp.app} /> : (
        <>
          <Warning text={data.unavailable_label ?? 'Podaci o nezaposlenosti nisu dostupni.'} />
          <Footer data={data} app={mcp.app} />
        </>
      )}
    </Card>
  )
}

/** Mounted once the data is there, so its entrance plays with the data. */
function History({ data, app }: { data: UnemploymentHistoryData; app: App | null }) {
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
    <div className="history" ref={root}>
      <UnemploymentGrowthChart counties={data.counties} />
      <div className="tiles">
        {data.counties.map((county, index) => <Tile key={county.code} county={county} index={index} />)}
      </div>
      <Footer data={data} app={app} />
    </div>
  )
}

function Tile({ county, index }: { county: CountyHistory; index: number }) {
  const { latest, same_month_previous_year: before, change_pp: change } = county
  const missing = county.series.filter((point) => point.rate === null).length
  const direction = change === null ? null : change < 0 ? 'down' : change > 0 ? 'up' : 'same'
  return (
    <section className="tile" data-slot="tile" aria-label={county.name}>
      <p className="tile-name"><span className={`swatch s${index + 1}`} />{county.name}</p>
      {latest && (
        <div className="tile-latest">
          <p className="soft">
            {formatMonth(latest.period)}
            {latest.is_provisional && <span className="provisional">privremeno</span>}
          </p>
          <p className={latest.rate === null ? 'tile-missing' : 'big'}>
            {latest.rate === null ? 'nema podatka' : formatRate(latest.rate)}
          </p>
        </div>
      )}
      {before && (
        <p className="tile-before">
          {formatMonth(before.period)}: {before.rate === null ? 'nema podatka' : formatRate(before.rate)}
        </p>
      )}
      {change !== null ? (
        <p className="tile-change">
          <span className={`change ${direction}`}>
            {direction !== 'same' && (
              <svg viewBox="0 0 12 12" aria-hidden="true">
                <path d={direction === 'down' ? 'M6 2v8M2.5 6.5 6 10l3.5-3.5' : 'M6 10V2M2.5 5.5 6 2l3.5 3.5'} />
              </svg>
            )}
            {formatPoints(change)}
          </span>
          <span className="soft">prema istom mjesecu prošle godine</span>
        </p>
      ) : (
        <p className="tile-change unavailable">
          <span className="change none">promjena nije dostupna</span>
          {county.change_unavailable_label && <span className="soft">{county.change_unavailable_label}</span>}
        </p>
      )}
      {missing > 0 && (
        <p className="soft">Nema podatka za {missing} {plural(missing, 'mjesec', 'mjeseca', 'mjeseci')} u nizu.</p>
      )}
    </section>
  )
}

function Footer({ data, app }: { data: UnemploymentHistoryData; app: App | null }) {
  return (
    <>
      <Sources app={app} links={data.source_links}>
        {data.dzs && <span>DZS podaci uvezeni {formatDay(data.dzs.finished_at)}</span>}
      </Sources>
      <Notes warning={null} note={data.view_notes} />
    </>
  )
}
