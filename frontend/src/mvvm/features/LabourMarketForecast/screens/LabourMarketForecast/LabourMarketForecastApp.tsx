import { openLink } from '../../../../utils/mcp'
import { useMcpApp } from '../../../../hooks/use-mcp-app'
import { LabourMarketForecast } from './LabourMarketForecast'
import { ForecastTables, ForecastView } from '../../components/ForecastView'
import { sample } from '../../utils/sample'
import type { CountyForecast, ForecastData } from '../../types'
import { useForecast } from '../../hooks/use-forecast'

function Session({ data, county }: { data: ForecastData; county: CountyForecast }) {
  const model = useForecast(data, county)
  return <ForecastView {...model} />
}

export function LabourMarketForecastApp() {
  const mcp = useMcpApp<ForecastData>('FOIHireloom labour market forecast', sample)
  const data = mcp.data
  const county = data?.counties[0]
  return <LabourMarketForecast data={data} onOpenLink={(url) => openLink(mcp.app, url)}
    details={data && county && <ForecastTables data={data} county={county} />}>
    {data && county && <Session key={mcp.revision} data={data} county={county} />}
  </LabourMarketForecast>
}
