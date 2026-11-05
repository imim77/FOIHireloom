import { animate } from 'animejs'
import { Card, ExpandButton, Notes, Warning } from '../../shared/Card'
import { FilterChips } from '../../shared/FilterChips'
import { finish, releaseStyles } from '../../shared/chart-motion'
import { formatAds } from '../../shared/format'
import { JobCardView } from './JobCardView'
import type { useJobCards } from './use-job-cards'
import { useJobGridMotion } from './use-job-grid-motion'

/** show_jobs: the found jobs as cards, with more on request; expanded (full screen) they fill several columns. */
export function JobCards({ data, cards, loading, error, actions, comparison,
  loadMore, removeFilter, expanded, toggle }:
  ReturnType<typeof useJobCards> & { expanded: boolean; toggle: () => void }) {
  const list = useJobGridMotion(expanded)

  return (
    <Card sunken title={data.title} description={data.description} actions={cards.length > 1 && (
      <ExpandButton expanded={expanded} label={expanded ? 'Smanji prikaz' : 'Prikaži oglase preko cijelog zaslona'}
        onClick={toggle} />
    )}>
      <FilterChips filters={data.active_filters} disabled={loading} onRemove={removeFilter} />
      <Notes warning={data.coverage_note} note={data.unknown_note} />
      {cards.length ? (
        <div className={`job-list grid [grid-template-columns:minmax(0,_1fr)] gap-3 items-start
          [&.expanded]:[grid-template-columns:repeat(auto-fill,_minmax(min(100%,_400px),_1fr))] ${expanded ? ' expanded' : ''}`} ref={list}>
          {cards.map(({ job, order, compare }) => (
            <JobCardView key={job.id} job={job} today={data.today} order={order} actions={actions}
              compare={compare} />
          ))}
        </div>
      ) : (
        <p className="empty m-0 text-[14px] text-fg-soft">Nema aktivnih oglasa za zadane filtre.</p>
      )}
      {comparison && (
        <div className="compare-bar flex flex-wrap items-center [gap:8px_12px] [padding:10px_12px] rounded-[12px]
          bg-surface-sunken animate-fade-in [&_.soft]:[flex:1_1_200px] [&_.more:disabled]:cursor-not-allowed
          motion-reduce:[animation:none]">
          <p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft" role="status">{comparison.hint}</p>
          <button className="more flex-none h-9 [padding:0_14px] border border-border rounded-[10px] bg-card text-fg-loud
            [font-family:inherit] text-[12px] font-semibold [font-style:inherit] leading-[inherit] cursor-pointer
            [&:hover:not(:disabled)]:bg-surface-subdued [&:focus-visible]:[outline:none]
            [&:focus-visible]:shadow-focus [&:disabled]:text-fg-soft [&:disabled]:cursor-progress
            [&.primary]:[border-color:transparent] [&.primary]:bg-surface-muted [&.primary]:text-fg-on-muted
            [&.primary:hover:not(:disabled)]:bg-surface-muted [&.primary:hover:not(:disabled)]:[opacity:0.9]
            [&.primary:disabled]:bg-surface-disable [&.primary:disabled]:text-fg-on-muted" type="button" onClick={comparison.clear}>Poništi odabir</button>
          <button className="more primary flex-none h-9 [padding:0_14px] border border-border rounded-[10px] bg-card text-fg-loud
            [font-family:inherit] text-[12px] font-semibold [font-style:inherit] leading-[inherit] cursor-pointer
            [&:hover:not(:disabled)]:bg-surface-subdued [&:focus-visible]:[outline:none]
            [&:focus-visible]:shadow-focus [&:disabled]:text-fg-soft [&:disabled]:cursor-progress
            [&.primary]:[border-color:transparent] [&.primary]:bg-surface-muted [&.primary]:text-fg-on-muted
            [&.primary:hover:not(:disabled)]:bg-surface-muted [&.primary:hover:not(:disabled)]:[opacity:0.9]
            [&.primary:disabled]:bg-surface-disable [&.primary:disabled]:text-fg-on-muted" type="button" disabled={!comparison.canCompare}
            onClick={() => void comparison.submit()}>
            Usporedi odabrane ({comparison.count})
          </button>
        </div>
      )}
      <Warning text={error} />
      {cards.length > 0 && (
        <div className="cards-foot flex items-center gap-3 [&_.soft]:flex-1">
          <p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">Prikazano {formatAds(cards.length)}</p>
          {loadMore && (
            <button className="more flex-none h-9 [padding:0_14px] border border-border rounded-[10px] bg-card text-fg-loud
              [font-family:inherit] text-[12px] font-semibold [font-style:inherit] leading-[inherit]
              cursor-pointer [&:hover:not(:disabled)]:bg-surface-subdued [&:focus-visible]:[outline:none]
              [&:focus-visible]:shadow-focus [&:disabled]:text-fg-soft [&:disabled]:cursor-progress
              [&.primary]:[border-color:transparent] [&.primary]:bg-surface-muted [&.primary]:text-fg-on-muted
              [&.primary:hover:not(:disabled)]:bg-surface-muted [&.primary:hover:not(:disabled)]:[opacity:0.9]
              [&.primary:disabled]:bg-surface-disable [&.primary:disabled]:text-fg-on-muted" type="button" disabled={loading} onClick={(event) => {
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
