import { openLink, useExpanded, useMcpApp } from '../../shared/mcp'
import { JobComparison } from './JobComparison'
import { sample } from './sample'
import type { JobComparisonData } from './types'

export function JobComparisonApp() {
  const mcp = useMcpApp<JobComparisonData>('FOIHireloom job comparison', sample)
  const expansion = useExpanded(mcp)
  return <JobComparison key={mcp.revision} data={mcp.data} {...expansion} onOpenLink={(url) => openLink(mcp.app, url)} />
}
