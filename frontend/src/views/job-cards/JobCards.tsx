import { Warning } from '../../shared/Card'
import { useMcpApp } from '../../shared/mcp'
import { JobCardView } from './JobCardView'
import { sample } from './sample'
import type { JobCardsData } from './types'
import './job-cards.css'

/** show_jobs: the found jobs as cards. */
export function JobCards() {
  const mcp = useMcpApp<JobCardsData>('FOIHireloom job cards', sample)
  const data = mcp.data
  if (!data) {
    return (
      <section className="job-cards">
        <header className="titles"><p className="title">Oglasi</p><p className="soft">Učitavanje…</p></header>
      </section>
    )
  }
  return (
    <section className="job-cards" aria-label={data.title}>
      <header className="titles">
        <p className="title truncate">{data.title}</p>
        <p className="soft truncate">{data.description}</p>
      </header>
      <Warning text={data.coverage?.warning} />
      {data.jobs.length ? (
        <div className="job-list">
          {data.jobs.map((job, i) => <JobCardView key={job.id} job={job} today={data.today} order={i} />)}
        </div>
      ) : (
        <p className="empty">Nema aktivnih oglasa za zadane filtre.</p>
      )}
    </section>
  )
}
