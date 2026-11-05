import { openLink, useMcpApp } from '../../shared/mcp'
import { AccommodationComparison } from './AccommodationComparison'
import { sample } from './sample'
import type { AccommodationComparisonData } from './types'

export function AccommodationComparisonApp() {
  const mcp = useMcpApp<AccommodationComparisonData>('FOIHireloom accommodation comparison', sample)
  return <AccommodationComparison key={mcp.revision} data={mcp.data} onOpenLink={(url) => openLink(mcp.app, url)} />
}
