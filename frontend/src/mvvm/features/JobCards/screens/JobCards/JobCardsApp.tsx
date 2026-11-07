import type { App as McpApp } from '@modelcontextprotocol/ext-apps'
import { Card } from '../../../../components/Card'
import { useExpanded } from '../../../../hooks/use-expanded'
import { useMcpApp } from '../../../../hooks/use-mcp-app'
import { EYEBROW, JobCards } from './JobCards'
import { sample } from '../../utils/sample'
import type { JobCardsData } from '../../types'
import { useJobCards } from '../../hooks/use-job-cards'

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
  if (!mcp.data) return <Card sunken eyebrow={EYEBROW} title="Oglasi" description="Učitavanje…" loading />
  // New host results discard local pages, filter changes and comparison picks.
  return <Session key={mcp.revision} initial={mcp.data} app={mcp.app} {...expansion} />
}
