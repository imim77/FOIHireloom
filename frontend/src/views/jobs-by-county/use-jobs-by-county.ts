import { useMemo, useState } from 'react'
import type { JobsByCountyData } from './types'

/** useJobsByCounty owns the visible ranking and the inspected county. */
export function useJobsByCounty(data: JobsByCountyData | null, expanded: boolean) {
  const all = data?.counties ?? []
  const counties = useMemo(() => {
    const all = data?.counties ?? []
    return expanded ? all : all.slice(0, data?.top ?? 0)
  }, [data, expanded])
  // The columns and the numbers over them show this value; the server has ranked the counties by it.
  const metric = data?.metric === 'workers_needed' ? 'workers_needed' : 'jobs'
  const values = counties.map((county) => Math.max(0, county[metric]))
  const n = counties.length
  const [selectedIndex, setSelected] = useState(0)
  const [hovered, setHovered] = useState<number | null>(null)
  const selected = Math.min(Math.max(selectedIndex, 0), n - 1)
  const active = hovered !== null && hovered < n ? hovered : selected
  const county = counties[active]
  const workers = county?.workers_needed ?? 0

  function selectCounty(next: number) {
    setSelected(Math.min(Math.max(next, 0), n - 1))
  }

  function navigate(key: string): number | null {
    const next = ({ ArrowRight: selected + 1, ArrowDown: selected + 1, ArrowLeft: selected - 1,
      ArrowUp: selected - 1, Home: 0, End: n - 1 } as Record<string, number>)[key]
    if (next === undefined || !n) return null
    const index = Math.min(Math.max(next, 0), n - 1)
    setHovered(null)
    selectCounty(index)
    return index
  }

  const shown = counties.length < all.length
    ? `Prikazano ${counties.length} od ${all.length} županija s oglasima`
    : `Sve županije s oglasima (${all.length})`
  const label = expanded ? 'Prikaži manje županija' : `Prikaži svih ${all.length} županija`

  return { data, shown, label, canExpand: expanded || all.length > (data?.top ?? 0),
    columns: { counties, values, selected, active, county, workers, selectCounty, hoverCounty: setHovered, navigate } }
}
