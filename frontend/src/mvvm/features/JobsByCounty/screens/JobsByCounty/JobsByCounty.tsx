import { Card, ExpandButton, Notes } from '../../../../components/Card'
import { formatAds, formatWorkers } from '../../../../utils/format'
import { CountyColumns } from '../../components/CountyColumns'
import type { useJobsByCounty } from '../../hooks/use-jobs-by-county'

/** show_jobs_by_county: the top counties as 3D columns, every county once expanded. */
export function JobsByCounty({ data, columns, shown, label, canExpand, expanded, toggle }:
  ReturnType<typeof useJobsByCounty> & { expanded: boolean; toggle: () => void }) {
  if (!data) return <Card title="Broj oglasa po županijama" description="Učitavanje…" />

  return (
    <Card title={data.title} description={data.description}
      actions={canExpand && <ExpandButton expanded={expanded} label={label} onClick={toggle} />}>
      <Notes warning={data.coverage_note} note={data.unknown_note} />
      {columns.counties.length ? (
        <>
          <CountyColumns {...columns} />
          <p className="soft footer m-0 text-[12px] font-medium leading-[1.25] text-fg-soft [margin-top:-8px]">
            {shown} · ukupno {formatAds(data.total_jobs)}, {formatWorkers(data.total_workers_needed)}
          </p>
        </>
      ) : (
        <p className="empty m-0 text-[14px] text-fg-soft">Nema aktivnih oglasa za zadane filtre.</p>
      )}
    </Card>
  )
}
