import { Card, Notes } from '../../shared/Card'
import { formatInteger, formatMoment } from '../../shared/format'
import { Sources } from '../../shared/Sources'
import { PortfolioAllocationChart } from './PortfolioAllocationChart'
import type { AccommodationComparisonData } from './types'
import type { useAllocation } from './use-allocation'

export function AccommodationComparison({ data, allocation, onOpenLink }: {
  data: AccommodationComparisonData | null
  allocation: ReturnType<typeof useAllocation>
  onOpenLink: (url: string) => void
}) {
  if (!data) return <Card title="Smještaj u oglasima za posao" description="Učitavanje…" />
  return (
    <Card title={data.title} description={data.description}>
      <div className="accommodation-comparison [--allocation-blue:#3155db] [--allocation-light:#dce8ff]
        [--allocation-orange:#f58233] flex flex-col gap-5 min-w-0 dark:[--allocation-blue:#5678f2]
        dark:[--allocation-light:#b9ccff] dark:[--allocation-orange:#ff9b56]">
        <Notes warning={data.coverage_note} note={data.unknown_note} />
        {data.total_jobs > 0 ? <>
          <PortfolioAllocationChart {...allocation} />
          <p className="soft accommodation-known m-0 text-[12px] font-medium leading-[1.5] text-fg-soft [padding:0_12px]">Podatak o smještaju poznat je za {formatInteger(data.known_jobs)} od {formatInteger(data.total_jobs)} oglasa.</p>
        </> : <p className="empty m-0 text-[14px] text-fg-soft">Nema oglasa za zadane filtre.</p>}
        <Sources onOpenLink={onOpenLink} links={[{ label: 'HZZ, Burza rada', url: 'https://burzarada.hzz.hr/' }]}>
          {data.coverage.data_as_of && <span>Oglasi provjereni {formatMoment(data.coverage.data_as_of)}</span>}
        </Sources>
        <Notes warning={null} note={data.view_notes} />
      </div>
    </Card>
  )
}
