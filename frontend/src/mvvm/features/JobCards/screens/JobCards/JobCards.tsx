import { Button } from '@/components/ui/button'
import { animate } from 'animejs'
import { EmptyState, Card, ExpandButton, Notes, Warning } from '../../../../components/Card'
import { FilterChips } from '../../../../components/FilterChips'
import { finish, releaseStyles } from '../../../../hooks/chart-motion'
import { formatAds } from '../../../../utils/format'
import { JobCardView } from '../../components/JobCardView'
import type { useJobCards } from '../../hooks/use-job-cards'
import { useJobGridMotion } from '../../hooks/use-job-grid-motion'

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
        <EmptyState>Nema aktivnih oglasa za zadane filtre.</EmptyState>
      )}
      {comparison && (
        <div className="compare-bar flex flex-wrap items-center [gap:8px_12px] [padding:10px_12px] rounded-[12px]
          bg-surface-sunken animate-fade-in [&_.soft]:[flex:1_1_200px] [&_.more:disabled]:cursor-not-allowed
          motion-reduce:[animation:none]">
          <p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft" role="status">{comparison.hint}</p>
          <Button variant="outline" size="lg" className="more" type="button" onClick={comparison.clear}>Poništi odabir</Button>
          <Button variant="default" size="lg" className="more primary" type="button" disabled={!comparison.canCompare}
            onClick={() => void comparison.submit()}>
            Usporedi odabrane ({comparison.count})
          </Button>
        </div>
      )}
      <Warning text={error} />
      {cards.length > 0 && (
        <div className="cards-foot flex items-center gap-3 [&_.soft]:flex-1">
          <p className="soft m-0 text-[12px] font-medium leading-[1.25] text-fg-soft">Prikazano {formatAds(cards.length)}</p>
          {loadMore && (
            <Button variant="outline" size="lg" className="more" type="button" disabled={loading} onClick={(event) => {
              finish(animate(event.currentTarget, { scale: [0.94, 1], duration: 400, ease: 'outBack(2)',
                onComplete: releaseStyles('transform') }))
              void loadMore()
            }}>
              {loading ? 'Učitavanje…' : 'Prikaži još oglasa'}
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}
