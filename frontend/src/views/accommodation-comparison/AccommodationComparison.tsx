import { Card, Notes } from '../../shared/Card'
import { formatInteger, formatMoment } from '../../shared/format'
import { useMcpApp } from '../../shared/mcp'
import { Sources } from '../../shared/Sources'
import { PortfolioAllocationChart } from './PortfolioAllocationChart'
import { sample } from './sample'
import type { AccommodationComparisonData } from './types'
import './accommodation-comparison.css'

export function AccommodationComparison() {
  const { app, data } = useMcpApp<AccommodationComparisonData>('FOIHireloom accommodation comparison', sample)
  if (!data) return <Card title="Smještaj u oglasima za posao" description="Učitavanje…" />
  return (
    <Card title={data.title} description={data.description}>
      <div className="accommodation-comparison">
        <Notes warning={data.coverage_note} note={data.unknown_note} />
        {data.total_jobs > 0 ? <>
          <PortfolioAllocationChart key={JSON.stringify([data.description, data.groups])} groups={data.groups} total={data.total_jobs} />
          <p className="soft accommodation-known">Podatak o smještaju poznat je za {formatInteger(data.known_jobs)} od {formatInteger(data.total_jobs)} oglasa.</p>
        </> : <p className="empty">Nema oglasa za zadane filtre.</p>}
        <Sources app={app} links={[{ label: 'HZZ, Burza rada', url: 'https://burzarada.hzz.hr/' }]}>
          {data.coverage.data_as_of && <span>Oglasi provjereni {formatMoment(data.coverage.data_as_of)}</span>}
        </Sources>
        <Notes warning={null} note={data.view_notes} />
      </div>
    </Card>
  )
}
