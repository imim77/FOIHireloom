// show_job_comparison: 2 or 3 jobs side by side in a table, a column per job and a row per aspect. Each cell shows
// HZZ's own words (or why the value is unknown) and, for a condition the user stated, a verdict chip; the user's
// condition is named once, in the row's heading. Rows whose values differ are marked, the others are quieter. In a
// narrow frame the table scrolls sideways under its sticky aspect column. Animated like the job cards: the columns'
// headings rise in one after another, then the rows.

import { Card, ExpandButton, Notes } from '../../../../components/Card'
import { ComparisonTable } from '../../components/ComparisonTable'
import type { JobComparisonData } from '../../types'

export function JobComparison({ data, expanded, toggle, onOpenLink }: {
  data: JobComparisonData | null
  expanded: boolean
  toggle: () => void
  onOpenLink: (url: string) => void
}) {
  if (!data) return <Card sunken title="Usporedba oglasa" description="Učitavanje…" />
  return (
    <Card sunken title={data.title} description={data.description} actions={(
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži usporedbu preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      <ComparisonTable data={data} onOpenLink={onOpenLink} expanded={expanded} />
      <Notes warning={null} note={[data.unknown_note, data.disclaimer]} />
    </Card>
  )
}
