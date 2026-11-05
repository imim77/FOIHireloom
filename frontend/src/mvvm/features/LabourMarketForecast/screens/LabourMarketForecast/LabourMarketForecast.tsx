import type { ReactNode } from 'react'
import { Card, Notes, Warning } from '../../../../components/Card'
import { Sources } from '../../../../components/Sources'
import type { ForecastData } from '../../types'

export function LabourMarketForecast({ data, onOpenLink, children }: {
  data: ForecastData | null
  onOpenLink: (url: string) => void
  children: ReactNode
}) {
  return <div className="forecast-view [&_.title]:whitespace-normal [&_.title]:overflow-visible [&_.titles_>_.soft]:whitespace-normal
    [&_.titles_>_.soft]:overflow-visible [&_.body]:min-w-0 [@media(max-width:_420px)]:[&_.card]:p-3.5">
    <Card loading={!data} title={data?.title ?? 'Chronos prognoza za županiju'} description={data?.description ?? 'Učitavanje…'}>
      {data && <>
        <Warning text={data.unavailable_label} />
        {children}
        <Sources onOpenLink={onOpenLink} links={data.source_links}><span>Model: {data.model}</span></Sources>
        <Notes warning={null} note={data.view_notes} />
      </>}
    </Card>
  </div>
}
