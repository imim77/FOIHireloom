import type { App as McpApp } from '@modelcontextprotocol/ext-apps'
import { Card } from '../../shared/Card'
import { useExpanded, useMcpApp } from '../../shared/mcp'
import { JobCards } from './JobCards'
import { sample } from './sample'
import type { JobCardsData } from './types'
import { useJobCards } from './use-job-cards'

function Session({ app, initial, ...expansion }: {
  app: McpApp | null
  initial: JobCardsData
  expanded: boolean
  toggle: () => void
}) {
  const model = useJobCards(app, initial)
  return <JobCards {...model} {...expansion} />
}

export function JobCardsApp() {
  const mcp = useMcpApp<JobCardsData>('FOIHireloom job cards', sample)
  const expansion = useExpanded(mcp)
  if (!mcp.data) return <Card sunken title="Oglasi" description="Učitavanje…" />
  // New host results discard local pages, filter changes and comparison picks.
  return <Session key={mcp.revision} initial={mcp.data} app={mcp.app} {...expansion} />
}
