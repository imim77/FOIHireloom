
import { Card, ExpandButton, Notes } from '../../../../components/Card'
import { ComparisonTable } from '../../components/ComparisonTable'
import type { JobComparisonData } from '../../types'

const EYEBROW = 'Usporedba oglasa'

export function JobComparison({ data, expanded, toggle, onOpenLink }: {
  data: JobComparisonData | null
  expanded: boolean
  toggle: () => void
  onOpenLink: (url: string) => void
}) {
  if (!data) return <Card eyebrow={EYEBROW} title="Usporedba oglasa" description="Učitavanje…" loading />
  return (
    <Card eyebrow={EYEBROW} title={data.title} description={data.description} actions={(
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži usporedbu preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      <ComparisonTable data={data} onOpenLink={onOpenLink} expanded={expanded} />
      <Notes warning={null} note={[data.unknown_note, data.disclaimer]} />
    </Card>
  )
}
