import type { App as McpApp } from '@modelcontextprotocol/ext-apps'
import { Card } from '../../shared/Card'
import { openLink, useExpanded, useMcpApp } from '../../shared/mcp'
import { CountyComparison } from './CountyComparison'
import { sample } from './sample'
import type { CountyComparisonData } from './types'
import { useCountyComparison } from './use-county-comparison'

function Session({ app, initial, ...expansion }: {
  app: McpApp | null
  initial: CountyComparisonData
  expanded: boolean
  toggle: () => void
}) {
  const model = useCountyComparison(app, initial)
  return <CountyComparison {...model} {...expansion} onOpenLink={(url) => openLink(app, url)} />
}

export function CountyComparisonApp() {
  const mcp = useMcpApp<CountyComparisonData>('FOIHireloom county comparison', sample)
  const expansion = useExpanded(mcp)
  if (!mcp.data) return <Card sunken title="Usporedba županija" description="Učitavanje…" />
  // A new result from the host replaces the one the view asked for.
  return <Session key={mcp.revision} initial={mcp.data} app={mcp.app} {...expansion} />
}
