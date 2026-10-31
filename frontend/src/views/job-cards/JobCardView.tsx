// One job, after the reference card: the employer's tile, name and line, the days left to apply, the title, the
// job's labels and, under a rule, when it was published and until when to apply, with its actions.

import { type Deadline, DeadlineRing } from './DeadlineRing'
import { chips, daysBetween, deadline, initials, published, sentenceCase, subtitle } from './job-format'
import type { JobCard } from './types'

function deadlineOf(job: JobCard, today: string): Deadline | null {
  if (!job.deadline_on || job.deadline_passed) return null
  const daysLeft = Math.max(0, daysBetween(today, job.deadline_on))
  const window = job.published_on ? daysBetween(job.published_on, job.deadline_on) : Math.max(daysLeft, 30)
  return { daysLeft, open: window > 0 ? Math.min(1, daysLeft / window) : 0 }
}

export function JobCardView({ job, today }: { job: JobCard; today: string }) {
  const ring = deadlineOf(job, today)
  const labels = chips(job)
  const employer = job.employer_name ?? 'Poslodavac nije naveden'
  return (
    <article className="job" data-slot="job" aria-label={`${sentenceCase(job.display_title)}, ${employer}`}>
      <div className="job-head">
        <span className="tile" aria-hidden="true" data-slot="tile">{initials(job.employer_name)}</span>
        <div className="titles">
          <p className="employer truncate" title={employer}>{employer}</p>
          <p className="soft-line truncate">{subtitle(job)}</p>
        </div>
        {ring && <DeadlineRing deadline={ring} />}
      </div>
      <h2 className="job-title">{sentenceCase(job.display_title)}</h2>
      {labels.length > 0 && (
        <ul className="chips" aria-label="Uvjeti">
          {labels.map((chip) => (
            <li key={chip.text} className={`chip ${chip.tone}`} data-slot="chip">{chip.text}</li>
          ))}
        </ul>
      )}
      <div className="job-foot">
        <p className="when">
          {published(job, today)} · <b>{deadline(job)}</b>
        </p>
      </div>
    </article>
  )
}
