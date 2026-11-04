import type { App } from '@modelcontextprotocol/ext-apps'
import { animate } from 'animejs'
import { Card, ExpandButton, Notes, Warning } from '../../shared/Card'
import { FilterChips } from '../../shared/FilterChips'
import { finish, releaseStyles } from '../../shared/chart-motion'
import { formatAds } from '../../shared/format'
import { useExpanded, useMcpApp } from '../../shared/mcp'
import { JobCardView } from './JobCardView'
import { sample } from './sample'
import { MAX_COMPARED, MIN_COMPARED, pickedHint, useJobCards } from './use-job-cards'
import { useJobGridMotion } from './use-job-grid-motion'
import type { JobCardsData } from './types'
import './job-cards.css'

/** show_jobs: the found jobs as cards, with more on request; expanded (full screen) they fill several columns. */
export function JobCards() {
  const mcp = useMcpApp<JobCardsData>('FOIHireloom job cards', sample)
  const { expanded, toggle } = useExpanded(mcp)
  if (!mcp.data) return <Card sunken title="Oglasi" description="Učitavanje…" />
  // New host results discard local pages, filter changes and comparison picks.
  return <JobCardsContent key={mcp.revision} initial={mcp.data} app={mcp.app} expanded={expanded} toggle={toggle} />
}

function JobCardsContent({ initial, app, expanded, toggle }: {
  initial: JobCardsData
  app: App | null
  expanded: boolean
  toggle: () => void
}) {
  const { data, cards, cursor, chosen, loading, error, tools, messages, actions,
    loadMore, removeFilter, togglePicked, clearPicked, compare } = useJobCards(app, initial)
  const list = useJobGridMotion(expanded)

  return (
    <Card sunken title={data.title} description={data.description} actions={cards.length > 1 && (
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži oglase preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      <FilterChips filters={data.active_filters} disabled={loading} onRemove={tools ? removeFilter : undefined} />
      <Notes warning={data.coverage_note} note={data.unknown_note} />
      {cards.length ? (
        <div className={`job-list${expanded ? ' expanded' : ''}`} ref={list}>
          {cards.map(({ job, order }) => (
            <JobCardView key={job.id} job={job} today={data.today} order={order} actions={actions}
              compare={messages ? {
                checked: chosen.some((other) => other.id === job.id),
                disabled: chosen.length >= MAX_COMPARED && !chosen.some((other) => other.id === job.id),
                onChange: () => togglePicked(job),
              } : null} />
          ))}
        </div>
      ) : (
        <p className="empty">Nema aktivnih oglasa za zadane filtre.</p>
      )}
      {messages && chosen.length > 0 && (
        <div className="compare-bar">
          <p className="soft" role="status">{pickedHint(chosen.length)}</p>
          <button className="more" type="button" onClick={clearPicked}>Poništi odabir</button>
          <button className="more primary" type="button" disabled={chosen.length < MIN_COMPARED}
            onClick={() => void compare()}>
            Usporedi odabrane ({chosen.length})
          </button>
        </div>
      )}
      <Warning text={error} />
      {cards.length > 0 && (
        <div className="cards-foot">
          <p className="soft">Prikazano {formatAds(cards.length)}</p>
          {cursor && tools && (
            <button className="more" type="button" disabled={loading} onClick={(event) => {
              finish(animate(event.currentTarget, { scale: [0.94, 1], duration: 400, ease: 'outBack(2)',
                onComplete: releaseStyles('transform') }))
              void loadMore()
            }}>
              {loading ? 'Učitavanje…' : 'Prikaži još oglasa'}
            </button>
          )}
        </div>
      )}
    </Card>
  )
}
