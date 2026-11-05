import type { App } from '@modelcontextprotocol/ext-apps'
import { useState } from 'react'
import type { ActiveFilter } from '../../../types'
import { useServerTool } from '../../../hooks/use-server-tool'
import type { CountyComparisonData, CountyFilters } from '../types'

/** The compare_counties arguments of a result without one filter: unset, or false for include_expired. */
function argumentsWithout(data: CountyComparisonData, argument: string) {
  const filters: CountyFilters = { ...data.filters, [argument]: argument === 'include_expired' ? false : null }
  return {
    counties: data.counties.map((county) => county.code),
    ...filters,
    ...(data.requested_period ? { period: data.requested_period.slice(0, 7) } : {}),
  }
}

/** useCountyComparison owns filter requests for one host result. */
export function useCountyComparison(app: App | null, initial: CountyComparisonData) {
  const [data, setData] = useState(initial)
  const { call, loading, error } = useServerTool<CountyComparisonData>(app, 'show_county_comparison',
    'Usporedba se nije mogla učitati.')
  const tools = Boolean(app?.getHostCapabilities()?.serverTools)

  async function removeFilter(filter: ActiveFilter) {
    const next = await call(argumentsWithout(data, filter.argument))
    if (next) setData(next)
  }

  return { data, loading, error, removeFilter: tools ? removeFilter : undefined }
}
