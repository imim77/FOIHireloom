import { animate } from 'animejs'
import { useLayoutEffect, useRef, useState } from 'react'
import { Card, ExpandButton, Notes, Warning } from '../../shared/Card'
import { finish, releaseStyles, useReducedMotion } from '../../shared/chart-motion'
import { formatAds } from '../../shared/format'
import { canSendMessage, openLink, useExpanded, useMcpApp } from '../../shared/mcp'
import type { ActiveFilter } from '../../shared/types'
import { type CardActions, JobCardView } from './JobCardView'
import { capitalise, sentenceCase } from './job-format'
import { sample } from './sample'
import type { JobCard, JobCardsData, JobCardsFilters } from './types'
import './job-cards.css'

// Expanding or collapsing moves every tile; each slides over from where it was, as the charts' bars morph.
const MOVE = 650
const MOVE_STAGGER = 30

// Cards loaded with "Prikaži još": order is a card's place in its own batch, which delays its entrance.
interface More {
  // The result these cards continue; a new result starts over.
  base: JobCardsData
  jobs: { job: JobCard; order: number }[]
  cursor: string | null
}

// The cards picked for a comparison, in the order picked; a new result starts over.
interface Picked {
  base: JobCardsData
  jobs: JobCard[]
}

// A comparison takes 2 or 3 jobs, as show_job_comparison does.
const MIN_COMPARED = 2
const MAX_COMPARED = 3

/** The user's message that asks for the comparison: Usporedi oglase „Kuhar” (id 1) i „Konobar” (id 2). */
function compareMessage(jobs: JobCard[]): string {
  const names = jobs.map((job) => `„${sentenceCase(job.display_title)}” (id ${job.id})`)
  return `Usporedi oglase ${names.slice(0, -1).join(', ')} i ${names[names.length - 1]}.`
}

/** What the comparison bar says about the picked cards. */
function pickedHint(count: number): string {
  if (count < MIN_COMPARED) return 'Odaberite još jedan ili dva oglasa za usporedbu.'
  if (count < MAX_COMPARED) return 'Možete odabrati još jedan oglas.'
  return 'Odabrana su 3 oglasa, najviše koliko se može usporediti.'
}

// A result the view asked for itself, without a removed filter; base is the host's result it replaced.
interface Refiltered {
  base: JobCardsData
  data: JobCardsData
}

/** The show_jobs arguments without one filter: unset, or false for include_expired. */
function without(filters: JobCardsFilters, argument: string): JobCardsFilters {
  return { ...filters, [argument]: argument === 'include_expired' ? false : null, cursor: null }
}

/** show_jobs: the found jobs as cards, with more on request; expanded (full screen) they fill several columns. */
export function JobCards() {
  const mcp = useMcpApp<JobCardsData>('FOIHireloom job cards', sample)
  const { app } = mcp
  const { expanded, toggle } = useExpanded(mcp)
  const [refiltered, setRefiltered] = useState<Refiltered | null>(null)
  const [more, setMore] = useState<More | null>(null)
  const [picked, setPicked] = useState<Picked | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const list = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  // Where each tile was after the last render, by job id, and whether the view was expanded then.
  const placed = useRef<{ expanded: boolean; rects: Map<string, DOMRect> }>({ expanded, rects: new Map() })
  useLayoutEffect(() => {
    const tiles = [...list.current?.querySelectorAll<HTMLElement>('[data-slot="job"]') ?? []]
    const rects = new Map(tiles.map((tile) => [tile.dataset.id!, tile.getBoundingClientRect()]))
    const before = placed.current
    placed.current = { expanded, rects }
    if (before.expanded === expanded || reduced) return
    tiles.forEach((tile, i) => {
      const from = before.rects.get(tile.dataset.id!)
      const to = rects.get(tile.dataset.id!)
      if (!from || !to) return
      finish(animate(tile, {
        translateX: [from.left - to.left, 0], translateY: [from.top - to.top, 0], duration: MOVE, ease: 'outExpo',
        delay: i * MOVE_STAGGER, onComplete: releaseStyles('transform'),
      }))
    })
  })
  // A new result from the host replaces the one the view asked for.
  const data = refiltered && refiltered.base === mcp.data ? refiltered.data : mcp.data
  if (!data) return <Card sunken title="Oglasi" description="Učitavanje…" />

  const extra = more?.base === data ? more : null
  const cards = [...data.jobs.map((job, order) => ({ job, order })), ...(extra?.jobs ?? [])]
  const cursor = extra ? extra.cursor : data.next_cursor
  const tools = Boolean(app?.getHostCapabilities()?.serverTools)
  // Picking cards to compare sends the user's message, so it needs a host that takes one.
  const messages = canSendMessage(app)
  const chosen = picked?.base === data ? picked.jobs : []
  // Chips under the header; with server tools each one can be removed.
  const chips = data.active_filters ?? []

  const actions: CardActions = {
    open: (job) => openLink(app, job.canonical_url),
    ask: app ? (job) => {
      const employer = job.employer_name ? ` (${job.employer_name})` : ''
      void app.sendMessage({ role: 'user', content: [{
        type: 'text', text: `Reci mi više o oglasu „${sentenceCase(job.display_title)}”${employer}, id ${job.id}.`,
      }] })
    } : null,
  }

  /** Call show_jobs and hand its result to apply; a failure shows under the cards. */
  async function showJobs(filters: JobCardsFilters, apply: (next: JobCardsData) => void) {
    if (!app) return
    setLoading(true)
    setError(null)
    try {
      const result = await app.callServerTool({ name: 'show_jobs', arguments: { ...filters } })
      const next = result.structuredContent as JobCardsData | undefined
      if (result.isError || !next) throw new Error('Oglasi se nisu mogli učitati.')
      apply(next)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    } finally {
      setLoading(false)
    }
  }

  function loadMore(button: HTMLButtonElement) {
    if (!cursor || !data) return
    finish(animate(button, { scale: [0.94, 1], duration: 400, ease: 'outBack(2)', onComplete: releaseStyles('transform') }))
    void showJobs({ ...data.filters, cursor }, (next) => {
      const shown = new Set(cards.map(({ job }) => job.id))
      const added = next.jobs.filter((job) => !shown.has(job.id)).map((job, order) => ({ job, order }))
      setMore({ base: data, jobs: [...(extra?.jobs ?? []), ...added], cursor: next.next_cursor })
    })
  }

  function togglePicked(job: JobCard) {
    if (!data) return
    const jobs = chosen.some((other) => other.id === job.id)
      ? chosen.filter((other) => other.id !== job.id)
      : chosen.length < MAX_COMPARED ? [...chosen, job] : chosen
    setPicked({ base: data, jobs })
  }

  async function compare() {
    if (!canSendMessage(app) || chosen.length < MIN_COMPARED) return
    setError(null)
    try {
      const result = await app.sendMessage({ role: 'user', content: [{ type: 'text', text: compareMessage(chosen) }] })
      if (result.isError) throw new Error('Poruka za usporedbu nije poslana.')
      setPicked(null)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure))
    }
  }

  function removeFilter(filter: ActiveFilter) {
    if (!data || !mcp.data) return
    const base = mcp.data
    // Cards loaded with "Prikaži još" continue the result shown now, so they go with it.
    void showJobs(without(data.filters, filter.argument), (next) => setRefiltered({ base, data: next }))
  }

  return (
    <Card sunken title={data.title} description={data.description} actions={cards.length > 1 && (
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži oglase preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      {chips.length > 0 && (
        <ul className="filters" aria-label="Filtri">
          {chips.map((filter) => (
            <li key={filter.argument} className="filter">
              <span>{capitalise(filter.label)}</span>
              {tools && (
                <button className="filter-remove" type="button" disabled={loading}
                  title={`Ukloni filtar ${filter.label}`} aria-label={`Ukloni filtar ${filter.label}`}
                  onClick={() => removeFilter(filter)}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                    aria-hidden="true">
                    <path d="M6 6l12 12M18 6 6 18" />
                  </svg>
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
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
          <button className="more" type="button" onClick={() => setPicked(null)}>Poništi odabir</button>
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
            <button className="more" type="button" disabled={loading} onClick={(event) => loadMore(event.currentTarget)}>
              {loading ? 'Učitavanje…' : 'Prikaži još oglasa'}
            </button>
          )}
        </div>
      )}
    </Card>
  )
}
