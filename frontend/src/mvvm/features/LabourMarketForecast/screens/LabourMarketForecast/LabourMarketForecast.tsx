import type { ReactNode } from 'react'
import { ChevronDownIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Card, Notes, Warning } from '../../../../components/Card'
import { Sources } from '../../../../components/Sources'
import type { ForecastData } from '../../types'

const EYEBROW = 'Prognoza'

export function LabourMarketForecast({ data, onOpenLink, details, children }: {
  data: ForecastData | null
  onOpenLink: (url: string) => void
  details?: ReactNode
  children: ReactNode
}) {
  return <div className="forecast-view [&_.title]:whitespace-normal [&_.title]:overflow-visible [&_.titles_>_.soft]:whitespace-normal
    [&_.titles_>_.soft]:overflow-visible [&_.body]:min-w-0 [@media(max-width:_420px)]:[&_.card]:p-3.5">
    <Card eyebrow={EYEBROW} loading={!data} title={data?.title ?? 'Chronos prognoza za županiju'} description={data?.description ?? 'Učitavanje…'}>
      {data && <>
        <Warning text={data.unavailable_label} />
        {children}
        <Collapsible className="forecast-details" data-enter>
          <CollapsibleTrigger render={<Button variant="outline" className="self-start rounded-full" />}>
            Detalji, izvori i napomene<ChevronDownIcon data-icon="inline-end" aria-hidden="true"
              className="transition-transform duration-300 [[data-panel-open]_&]:rotate-180 motion-reduce:transition-none" />
          </CollapsibleTrigger>
          <CollapsibleContent className="flex flex-col gap-4 pt-4">
            {details}
            <Sources onOpenLink={onOpenLink} links={data.source_links}><span>Model: {data.model}</span></Sources>
            <Notes warning={null} note={data.view_notes} />
          </CollapsibleContent>
        </Collapsible>
      </>}
    </Card>
  </div>
}
