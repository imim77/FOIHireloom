import type { ComponentProps } from 'react'
import { openLink, useMcpApp } from '../../shared/mcp'
import { UnemploymentHistory } from './UnemploymentHistory'
import { sample } from './sample'
import type { UnemploymentHistoryData } from './types'
import { useHistoryChart } from './use-history-chart'

function Session(props: Omit<ComponentProps<typeof UnemploymentHistory>, 'chart'>) {
  const chart = useHistoryChart(props.data?.counties ?? [])
  return <UnemploymentHistory {...props} chart={chart} />
}

export function UnemploymentHistoryApp() {
  const mcp = useMcpApp<UnemploymentHistoryData>('FOIHireloom unemployment history', sample)
  return <Session key={mcp.revision} data={mcp.data} onOpenLink={(url) => openLink(mcp.app, url)} />
}
