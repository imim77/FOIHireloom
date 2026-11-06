import { openLink } from '../../../../utils/mcp'
import { useExpanded } from '../../../../hooks/use-expanded'
import { useMcpApp } from '../../../../hooks/use-mcp-app'
import { JobComparison } from './JobComparison'
import { sample } from '../../utils/sample'
import type { JobComparisonData } from '../../types'

export function JobComparisonApp() {
  const mcp = useMcpApp<JobComparisonData>('FOIHireloom job comparison', sample)
  const expansion = useExpanded(mcp)
  return <JobComparison key={mcp.revision} data={mcp.data} {...expansion} onOpenLink={(url) => openLink(mcp.app, url)} />
}
