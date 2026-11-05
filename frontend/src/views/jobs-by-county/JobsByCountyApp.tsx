import type { ComponentProps } from 'react'
import { useExpanded, useMcpApp } from '../../shared/mcp'
import { JobsByCounty } from './JobsByCounty'
import { sample } from './sample'
import type { JobsByCountyData } from './types'
import { useJobsByCounty } from './use-jobs-by-county'

function Session({ data, expanded, toggle }: Pick<ComponentProps<typeof JobsByCounty>, 'data' | 'expanded' | 'toggle'>) {
  const model = useJobsByCounty(data, expanded)
  return <JobsByCounty {...model} expanded={expanded} toggle={toggle} />
}

export function JobsByCountyApp() {
  const mcp = useMcpApp<JobsByCountyData>('FOIHireloom jobs by county', sample)
  const expansion = useExpanded(mcp)
  return <Session key={mcp.revision} data={mcp.data} {...expansion} />
}
