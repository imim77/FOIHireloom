import { openLink, useMcpApp } from '../../shared/mcp'
import { UnemploymentHistory } from './UnemploymentHistory'
import { sample } from './sample'
import type { UnemploymentHistoryData } from './types'

export function UnemploymentHistoryApp() {
  const mcp = useMcpApp<UnemploymentHistoryData>('FOIHireloom unemployment history', sample)
  return <UnemploymentHistory key={mcp.revision} data={mcp.data} onOpenLink={(url) => openLink(mcp.app, url)} />
}
