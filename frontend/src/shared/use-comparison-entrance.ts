import { stagger } from 'animejs'
import { useRef } from 'react'
import { fadeIn, useChartEntrance } from './chart-motion'

const HEAD_STAGGER = 70
const ROWS_AT = 250

/** useComparisonEntrance reveals column headings followed by each complete row. */
export function useComparisonEntrance(column: 'job' | 'county', rowStagger: number) {
  const root = useRef<HTMLDivElement>(null)

  useChartEntrance(root, (timeline) => {
    const all = (selector: string) => [...root.current!.querySelectorAll<HTMLElement>(selector)]
    const heads = all(`[data-slot="${column}"]`)
    timeline.add(heads, { ...fadeIn(heads, 10), duration: 800, ease: 'outExpo', delay: stagger(HEAD_STAGGER) }, 0)
    // A row's heading and cells come in together, each row after the one above.
    const cells = all('[data-row]')
    timeline.add(cells, { ...fadeIn(cells, 4), duration: 500, delay: (target?: unknown) =>
      Number((target as HTMLElement | undefined)?.dataset.row ?? 0) * rowStagger }, ROWS_AT)
    return () => {
      for (const el of [...heads, ...cells]) {
        el.style.removeProperty('opacity')
        el.style.removeProperty('transform')
      }
    }
  })

  return root
}
