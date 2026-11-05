import type { ComponentProps } from 'react'
import { openLink } from '../../../../utils/mcp'
import { useMcpApp } from '../../../../hooks/use-mcp-app'
import { AccommodationComparison } from './AccommodationComparison'
import { sample } from '../../utils/sample'
import type { AccommodationComparisonData } from '../../types'
import { useAllocation } from '../../hooks/use-allocation'

function Session(props: Omit<ComponentProps<typeof AccommodationComparison>, 'allocation'>) {
  const allocation = useAllocation(props.data?.groups ?? [], props.data?.total_jobs ?? 0)
  return <AccommodationComparison {...props} allocation={allocation} />
}

export function AccommodationComparisonApp() {
  const mcp = useMcpApp<AccommodationComparisonData>('FOIHireloom accommodation comparison', sample)
  return <Session key={mcp.revision} data={mcp.data} onOpenLink={(url) => openLink(mcp.app, url)} />
}
