import { useMemo, useState } from 'react'
import { mod } from '../utils/ring-geometry'
import type { AccommodationGroup } from '../types'

/** useAllocation owns visible groups, the denominator, and segment selection. */
export function useAllocation(groups: AccommodationGroup[], total: number) {
  const [hidden, setHidden] = useState<string[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const [previewed, setPreviewed] = useState<number | null>(null)
  const values = useMemo(() => groups.map((group) => hidden.includes(group.key) ? 0 : group.jobs), [groups, hidden])
  const shown = values.flatMap((value, index) => value > 0 ? [index] : [])
  const visibleTotal = values.reduce((sum, value) => sum + value, 0)
  const shares = values.map((value) => visibleTotal ? value / visibleTotal * 100 : 0)
  const pick = (index: number | null) => index !== null && values[index] > 0 ? index : null
  const active = pick(hovered) ?? pick(previewed) ?? pick(selected)
  function showGroups(keys: string[]) {
    const visible = groups.filter((group) => group.jobs > 0 && keys.includes(group.key))
    if (!visible.length) return
    setHidden(groups.filter((group) => group.jobs > 0 && !keys.includes(group.key)).map((group) => group.key))
    if (selected !== null && !keys.includes(groups[selected].key)) setSelected(null)
  }
  function navigate(key: string) {
    if (key === 'Escape') { setHovered(null); setPreviewed(null); setSelected(null); return true }
    if ((key === 'Enter' || key === ' ') && active !== null) {
      setSelected(selected === active ? null : active); return true
    }
    const at = active === null ? -1 : shown.indexOf(active)
    const next = ({ ArrowRight: at + 1, ArrowDown: at + 1, ArrowLeft: at - 1, ArrowUp: at - 1,
      Home: 0, End: shown.length - 1 } as Record<string, number>)[key]
    if (next === undefined || !shown.length) return false
    setHovered(shown[mod(next, shown.length)])
    return true
  }
  const sliderAt = active === null ? 0 : shown.indexOf(active)
  const sliderSlice = shown[sliderAt]
  const filtered = visibleTotal !== total
  const denominator = filtered ? 'prikazanih oglasa' : 'svih oglasa'

  function selectGroup(index: number | null) {
    setSelected(selected === index ? null : index)
  }

  return { groups, total, hidden, values, shown, visibleTotal, shares, active,
    sliderAt, sliderSlice, filtered, denominator, showGroups, selectGroup,
    hoverGroup: setHovered, previewGroup: setPreviewed, navigate, resetGroups: () => setHidden([]) }
}
