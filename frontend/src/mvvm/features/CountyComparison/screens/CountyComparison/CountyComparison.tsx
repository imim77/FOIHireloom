
import { Card, ExpandButton, Warning } from '../../../../components/Card'
import { FilterChips } from '../../../../components/FilterChips'
import { ComparisonTable, Footer, Moments } from '../../components/CountyComparisonDetails'
import type { useCountyComparison } from '../../hooks/use-county-comparison'

export const EYEBROW = 'Usporedba županija'

export function CountyComparison({ data, loading, error, removeFilter, expanded, toggle, onOpenLink }:
  ReturnType<typeof useCountyComparison> & {
    expanded: boolean
    toggle: () => void
    onOpenLink: (url: string) => void
  }) {
  return (
    <Card eyebrow={EYEBROW} title={data.title} description={data.description} actions={(
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži usporedbu preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      <FilterChips filters={data.active_filters} label="Filtri oglasa" disabled={loading}
        onRemove={removeFilter} />
      <Warning text={error} />
      <Moments data={data} />
      <ComparisonTable data={data} expanded={expanded} />
      <Footer data={data} onOpenLink={onOpenLink} />
    </Card>
  )
}
