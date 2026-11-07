import { EmptyState, Card, Notes } from '../../../../components/Card'
import { formatInteger, formatMoment } from '../../../../utils/format'
import { Sources } from '../../../../components/Sources'
import { PortfolioAllocationChart } from '../../components/PortfolioAllocationChart'
import type { AccommodationComparisonData } from '../../types'
import type { useAllocation } from '../../hooks/use-allocation'

const EYEBROW = 'Smještaj'

export function AccommodationComparison({ data, allocation, onOpenLink }: {
  data: AccommodationComparisonData | null
  allocation: ReturnType<typeof useAllocation>
  onOpenLink: (url: string) => void
}) {
  if (!data) return <Card eyebrow={EYEBROW} title="Smještaj u oglasima za posao" description="Učitavanje…" loading />
  return (
    <Card eyebrow={EYEBROW} title={data.title} description={data.description}>
      <div className="accommodation-comparison flex flex-col gap-6 min-w-0">
        <Notes warning={data.coverage_note} note={data.unknown_note} />
        {data.total_jobs > 0 ? <>
          <PortfolioAllocationChart {...allocation} />
          {/* The chart's footer: pulled up so it reads with the legend and hint above it. */}
          <p data-enter className="soft accommodation-known m-0 -mt-2 mono-label uppercase text-fg-soft">Podatak o smještaju poznat je za {formatInteger(data.known_jobs)} od {formatInteger(data.total_jobs)} oglasa.</p>
        </> : <EmptyState>Nema oglasa za zadane filtre.</EmptyState>}
        <Sources onOpenLink={onOpenLink} links={[{ label: 'HZZ, Burza rada', url: 'https://burzarada.hzz.hr/' }]}>
          {data.coverage.data_as_of && <span>Oglasi provjereni {formatMoment(data.coverage.data_as_of)}</span>}
        </Sources>
        <Notes warning={null} note={data.view_notes} />
      </div>
    </Card>
  )
}
