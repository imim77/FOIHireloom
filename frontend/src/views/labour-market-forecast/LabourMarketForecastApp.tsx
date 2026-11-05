import { openLink, useMcpApp } from '../../shared/mcp'
import { ForecastView, LabourMarketForecast } from './LabourMarketForecast'
import { sample } from './sample'
import type { CountyForecast, ForecastData } from './types'
import { useForecast } from './use-forecast'

function Session({ data, county }: { data: ForecastData; county: CountyForecast }) {
  const model = useForecast(data, county)
  return <ForecastView {...model} />
}

export function LabourMarketForecastApp() {
  const mcp = useMcpApp<ForecastData>('FOIHireloom labour market forecast', sample)
  const data = mcp.data
  const county = data?.counties[0]
  return <LabourMarketForecast data={data} onOpenLink={(url) => openLink(mcp.app, url)}>
    {data && county && <Session key={mcp.revision} data={data} county={county} />}
  </LabourMarketForecast>
}
