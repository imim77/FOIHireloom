import { Card, ExpandButton, Warning } from '../../shared/Card'
import { formatAds, formatWorkers } from '../../shared/format'
import { useExpanded, useMcpApp } from '../../shared/mcp'
import { CountyColumns } from './CountyColumns'
import { sample } from './sample'
import type { JobsByCountyData } from './types'
import './jobs-by-county.css'

/** show_jobs_by_county: the top counties as 3D columns, every county once expanded. */
export function JobsByCounty() {
  const mcp = useMcpApp<JobsByCountyData>('FOIHireloom jobs by county', sample)
  const { expanded, toggle } = useExpanded(mcp)
  const data = mcp.data
  if (!data) return <Card title="Broj oglasa po županijama" description="Učitavanje…" />

  const all = data.counties ?? []
  const counties = expanded ? all : all.slice(0, data.top)
  // The columns and the numbers over them show this value; the server has ranked the counties by it.
  const metric = data.metric === 'workers_needed' ? 'workers_needed' : 'jobs'
  const shown = counties.length < all.length
    ? `Prikazano ${counties.length} od ${all.length} županija s oglasima`
    : `Sve županije s oglasima (${all.length})`
  const label = expanded ? 'Prikaži manje županija' : `Prikaži svih ${all.length} županija`

  return (
    <Card title={data.title} description={data.description}
      actions={(expanded || all.length > data.top) && <ExpandButton expanded={expanded} label={label} onClick={toggle} />}>
      <Warning text={data.coverage?.warning} />
      {counties.length ? (
        <>
          <CountyColumns counties={counties} metric={metric} />
          <p className="soft footer">
            {shown} · ukupno {formatAds(data.total_jobs)}, {formatWorkers(data.total_workers_needed)}
          </p>
        </>
      ) : (
        <p className="empty">Nema aktivnih oglasa za zadane filtre.</p>
      )}
    </Card>
  )
}
