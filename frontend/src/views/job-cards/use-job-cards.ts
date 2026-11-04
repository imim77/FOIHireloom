import type { App } from '@modelcontextprotocol/ext-apps'
import { useState } from 'react'
import { canSendMessage, openLink } from '../../shared/mcp'
import { sentenceCase } from '../../shared/text'
import type { ActiveFilter } from '../../shared/types'
import { useServerTool } from '../../shared/use-server-tool'
import type { JobCard, JobCardsData } from './types'

// A comparison takes 2 or 3 jobs, as show_job_comparison does.
export const MIN_COMPARED = 2
export const MAX_COMPARED = 3

/** The user's message that asks for the comparison: Usporedi oglase „Kuhar” (id 1) i „Konobar” (id 2). */
function compareMessage(jobs: JobCard[]): string {
  const names = jobs.map((job) => `„${sentenceCase(job.display_title)}” (id ${job.id})`)
  return `Usporedi oglase ${names.slice(0, -1).join(', ')} i ${names[names.length - 1]}.`
}

/** What the comparison bar says about the picked cards. */
export function pickedHint(count: number): string {
  if (count < MIN_COMPARED) return 'Odaberite još jedan ili dva oglasa za usporedbu.'
  if (count < MAX_COMPARED) return 'Možete odabrati još jedan oglas.'
  return 'Odabrana su 3 oglasa, najviše koliko se može usporediti.'
}

/** useJobCards owns pagination, filtering and comparison picks for one host result. */
export function useJobCards(app: App | null, initial: JobCardsData) {
  const [data, setData] = useState(initial)
  // Cards loaded with "Prikaži još": order is a card's place in its own batch, which delays its entrance.
  const [more, setMore] = useState<{ job: JobCard; order: number }[]>([])
  const [cursor, setCursor] = useState(initial.next_cursor)
  // The cards picked for a comparison, in the order picked; a new result starts over.
  const [chosen, setChosen] = useState<JobCard[]>([])
  const { call, loading, error, setError } = useServerTool<JobCardsData>(app, 'show_jobs', 'Oglasi se nisu mogli učitati.')
  const cards = [...data.jobs.map((job, order) => ({ job, order })), ...more]
  const tools = Boolean(app?.getHostCapabilities()?.serverTools)
  // Picking cards to compare sends the user's message, so it needs a host that takes one.
  const messages = canSendMessage(app)

  async function sendMessage(text: string): Promise<boolean> {
    if (!canSendMessage(app)) return false
    setError(null)
    try {
      const result = await app.sendMessage({ role: 'user', content: [{ type: 'text', text }] })
      if (result.isError) throw new Error('Poruka nije poslana.')
      return true
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
      return false
    }
  }

  const actions = {
    open: (job: JobCard) => openLink(app, job.canonical_url),
    ask: messages ? (job: JobCard) => {
      const employer = job.employer_name ? ` (${job.employer_name})` : ''
      void sendMessage(`Reci mi više o oglasu „${sentenceCase(job.display_title)}”${employer}, id ${job.id}.`)
    } : null,
  }

  async function loadMore() {
    if (!cursor) return
    const next = await call({ ...data.filters, cursor })
    if (!next) return
    const shown = new Set(cards.map(({ job }) => job.id))
    const added = next.jobs.filter((job) => !shown.has(job.id)).map((job, order) => ({ job, order }))
    setMore([...more, ...added])
    setCursor(next.next_cursor)
  }

  async function removeFilter(filter: ActiveFilter) {
    // The show_jobs arguments without one filter: unset, or false for include_expired.
    const next = await call({ ...data.filters,
      [filter.argument]: filter.argument === 'include_expired' ? false : null, cursor: null })
    if (!next) return
    // Cards loaded with "Prikaži još" continue the result shown now, so they go with it.
    setData(next)
    setMore([])
    setCursor(next.next_cursor)
    setChosen([])
  }

  function togglePicked(job: JobCard) {
    setChosen((jobs) => jobs.some((other) => other.id === job.id)
      ? jobs.filter((other) => other.id !== job.id)
      : jobs.length < MAX_COMPARED ? [...jobs, job] : jobs)
  }

  async function compare() {
    if (chosen.length < MIN_COMPARED) return
    if (await sendMessage(compareMessage(chosen))) setChosen([])
  }

  return { data, cards, cursor, chosen, loading, error, tools, messages, actions,
    loadMore, removeFilter, togglePicked, clearPicked: () => setChosen([]), compare }
}
