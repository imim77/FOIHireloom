import { useRef } from 'react'
import { clearEntrance, EASE, fadeIn, s, useChartEntrance } from './chart-motion'

const HEAD_STAGGER = 70
const ROWS_AT = 250

export function useComparisonEntrance(column: 'job' | 'county', rowStagger: number) {
  const root = useRef<HTMLDivElement>(null)

  useChartEntrance(root, (timeline) => {
    const all = (selector: string) => [...root.current!.querySelectorAll<HTMLElement>(selector)]
    const heads = all(`[data-slot="${column}"]`)
    if (heads.length) timeline.to(heads, { ...fadeIn(heads, 10), duration: s(800), ease: EASE.arrive, stagger: s(HEAD_STAGGER) }, 0)
    const cells = all('[data-row]')
    if (cells.length) timeline.to(cells, { ...fadeIn(cells, 4), duration: s(500),
      stagger: (_index: number, target: HTMLElement) => s(Number(target.dataset.row ?? 0) * rowStagger) }, s(ROWS_AT))
    return () => clearEntrance([...heads, ...cells])
  })

  return root
}
