import { useMemo, useState } from 'react'
import { formatShare } from '../../../utils/format'
import type { AccommodationGroup } from '../types'

const mod = (value: number, size: number) => ((value % size) + size) % size

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
  const tabStop = pick(selected) ?? shown[0] ?? null
  function showGroups(keys: string[]) {
    const visible = groups.filter((group) => group.jobs > 0 && keys.includes(group.key))
    if (!visible.length) return
    setHidden(groups.filter((group) => group.jobs > 0 && !keys.includes(group.key)).map((group) => group.key))
    if (selected !== null && !keys.includes(groups[selected].key)) setSelected(null)
  }

  function selectGroup(index: number | null) {
    setSelected(selected === index ? null : index)
  }

  function navigate(key: string, index: number): number | null {
    if (key === 'Escape') { setHovered(null); setPreviewed(null); setSelected(null); return index }
    if (key === 'Enter' || key === ' ') { selectGroup(index); return index }
    const at = shown.indexOf(index)
    const next = ({ ArrowRight: at + 1, ArrowDown: at + 1, ArrowLeft: at - 1, ArrowUp: at - 1,
      Home: 0, End: shown.length - 1 } as Record<string, number>)[key]
    if (next === undefined || !shown.length) return null
    const target = shown[mod(next, shown.length)]
    setHovered(null)
    setSelected(target)
    return target
  }

  const filtered = visibleTotal !== total
  const denominator = filtered ? 'prikazanih oglasa' : 'svih oglasa'
  const readout = active === null
    ? { name: null, share: null, detail: `Ukupno oglasa · ${filtered ? 'u prikazanim skupinama' : 'u odabranom skupu'}`,
      amount: visibleTotal }
    : { name: groups[active].label, share: formatShare(shares[active]), detail: denominator, amount: values[active] }

  return { groups, total, hidden, values, shown, visibleTotal, shares, active, selected, tabStop,
    filtered, denominator, readout, showGroups, selectGroup,
    hoverGroup: setHovered, previewGroup: setPreviewed, navigate, resetGroups: () => setHidden([]) }
}
