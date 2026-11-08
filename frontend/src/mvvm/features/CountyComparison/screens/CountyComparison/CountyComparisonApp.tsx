import type { App as McpApp } from '@modelcontextprotocol/ext-apps'
import { Card } from '../../../../components/Card'
import { openLink } from '../../../../utils/mcp'
import { useExpanded } from '../../../../hooks/use-expanded'
import { useMcpApp } from '../../../../hooks/use-mcp-app'
import { CountyComparison, EYEBROW } from './CountyComparison'
import { sample } from '../../utils/sample'
import type { CountyComparisonData } from '../../types'
import { useCountyComparison } from '../../hooks/use-county-comparison'

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
  if (!mcp.data) return <Card eyebrow={EYEBROW} title="Usporedba županija" description="Učitavanje…" loading />
  return <Session key={mcp.revision} initial={mcp.data} app={mcp.app} {...expansion} />
}
