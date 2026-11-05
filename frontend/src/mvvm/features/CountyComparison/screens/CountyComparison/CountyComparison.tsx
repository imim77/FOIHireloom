// show_county_comparison: 2 to 6 counties side by side in a table, a column per county and three groups of rows: the
// HZZ ads matching the filters, the DZS values with their reference months, and the two indicators, which describe
// each county as a whole and sit apart on a grey band. An unavailable value says why, never 0 or ∞. Over the table the
// filters (removable when the host lets the view call tools) and the two moments the data refers to; under it the
// coverage warning, the sources and the notes. In a narrow frame the table scrolls sideways under its sticky row names.
// Animated like the job comparison: the counties' headings rise in one after another, then the rows.

import { Card, ExpandButton, Notes, Warning } from '../../../../components/Card'
import { FilterChips } from '../../../../components/FilterChips'
import { ComparisonTable, Footer, Moments } from '../../components/CountyComparisonDetails'
import type { useCountyComparison } from '../../hooks/use-county-comparison'

export function CountyComparison({ data, loading, error, removeFilter, expanded, toggle, onOpenLink }:
  ReturnType<typeof useCountyComparison> & {
    expanded: boolean
    toggle: () => void
    onOpenLink: (url: string) => void
  }) {
  return (
    <Card sunken title={data.title} description={data.description} actions={(
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži usporedbu preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      <FilterChips filters={data.active_filters} label="Filtri oglasa" disabled={loading}
        onRemove={removeFilter} />
      <Warning text={error} />
      <Moments data={data} />
      <ComparisonTable data={data} expanded={expanded} />
      <Notes warning={data.coverage_note} note={[data.disclaimer, ...data.view_notes]} />
      <Footer data={data} onOpenLink={onOpenLink} />
    </Card>
  )
}
