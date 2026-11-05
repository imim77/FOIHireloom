import { useExpanded, useMcpApp } from '../../shared/mcp'
import { JobsByCounty } from './JobsByCounty'
import { sample } from './sample'
import type { JobsByCountyData } from './types'

export function JobsByCountyApp() {
  const mcp = useMcpApp<JobsByCountyData>('FOIHireloom jobs by county', sample)
  const expansion = useExpanded(mcp)
  return <JobsByCounty key={mcp.revision} data={mcp.data} {...expansion} />
}
