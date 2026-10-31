import { animate } from 'animejs'
import { useState } from 'react'
import { Warning } from '../../shared/Card'
import { finish, releaseStyles } from '../../shared/chart-motion'
import { useMcpApp } from '../../shared/mcp'
import { type CardActions, JobCardView } from './JobCardView'
import { sentenceCase } from './job-format'
import { sample } from './sample'
import type { JobCard, JobCardsData } from './types'
import './job-cards.css'

// Cards loaded with "Prikaži još": order is a card's place in its own batch, which delays its entrance.
interface More {
  // The tool result these cards continue; a new result starts over.
  base: JobCardsData
  jobs: { job: JobCard; order: number }[]
  cursor: string | null
}

/** show_jobs: the found jobs as cards, with more on request. */
export function JobCards() {
  const mcp = useMcpApp<JobCardsData>('FOIHireloom job cards', sample)
  const { app, data } = mcp
  const [more, setMore] = useState<More | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!data) {
    return (
      <section className="job-cards">
        <header className="titles"><p className="title">Oglasi</p><p className="soft">Učitavanje…</p></header>
      </section>
    )
  }

  const extra = more?.base === data ? more : null
  const cards = [...data.jobs.map((job, order) => ({ job, order })), ...(extra?.jobs ?? [])]
  const cursor = extra ? extra.cursor : data.next_cursor
  const tools = Boolean(app?.getHostCapabilities()?.serverTools)

  const actions: CardActions = {
    open: (job) => {
      if (app) void app.openLink({ url: job.canonical_url }).catch(() => window.open(job.canonical_url, '_blank'))
      else window.open(job.canonical_url, '_blank', 'noopener')
    },
    ask: app ? (job) => {
      const employer = job.employer_name ? ` (${job.employer_name})` : ''
      void app.sendMessage({ role: 'user', content: [{
        type: 'text', text: `Reci mi više o oglasu „${sentenceCase(job.display_title)}”${employer}, id ${job.id}.`,
      }] })
    } : null,
  }

  async function loadMore(button: HTMLButtonElement) {
    if (!app || !cursor || !data) return
    setLoading(true)
    setError(null)
    finish(animate(button, { scale: [0.94, 1], duration: 400, ease: 'outBack(2)', onComplete: releaseStyles('transform') }))
    try {
      const result = await app.callServerTool({ name: 'show_jobs', arguments: { ...data.filters, cursor } })
      const next = result.structuredContent as JobCardsData | undefined
      if (result.isError || !next) throw new Error('Oglasi se nisu mogli učitati.')
      const shown = new Set(cards.map(({ job }) => job.id))
      const added = next.jobs.filter((job) => !shown.has(job.id)).map((job, order) => ({ job, order }))
      setMore({ base: data, jobs: [...(extra?.jobs ?? []), ...added], cursor: next.next_cursor })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="job-cards" aria-label={data.title}>
      <header className="titles">
        <p className="title truncate">{data.title}</p>
        <p className="soft truncate">{data.description}</p>
      </header>
      <Warning text={data.coverage?.warning} />
      {cards.length ? (
        <div className="job-list">
          {cards.map(({ job, order }) => (
            <JobCardView key={job.id} job={job} today={data.today} order={order} actions={actions} />
          ))}
        </div>
      ) : (
        <p className="empty">Nema aktivnih oglasa za zadane filtre.</p>
      )}
      <Warning text={error} />
      {cursor && tools && (
        <button className="more" type="button" disabled={loading} onClick={(event) => loadMore(event.currentTarget)}>
          {loading ? 'Učitavanje…' : 'Prikaži još oglasa'}
        </button>
      )}
    </section>
  )
}
