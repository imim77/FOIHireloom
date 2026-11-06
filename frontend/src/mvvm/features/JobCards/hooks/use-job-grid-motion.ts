import { animate } from 'animejs'
import { useLayoutEffect, useRef } from 'react'
import { finish, MOTION, releaseStyles, useReducedMotion } from '../../../hooks/chart-motion'

// Expanding or collapsing moves every tile; each slides over from where it was, as the charts' bars morph.
const MOVE_STAGGER = 30

/** useJobGridMotion animates tiles between their collapsed and expanded positions. */
export function useJobGridMotion(expanded: boolean) {
  const list = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  // Where each tile was after the last render, by job id, and whether the view was expanded then.
  const placed = useRef<{ expanded: boolean; rects: Map<string, DOMRect> }>({ expanded, rects: new Map() })
  useLayoutEffect(() => {
    const tiles = [...list.current?.querySelectorAll<HTMLElement>('[data-slot="job"]') ?? []]
    const rects = new Map(tiles.map((tile) => [tile.dataset.id!, tile.getBoundingClientRect()]))
    const before = placed.current
    placed.current = { expanded, rects }
    if (before.expanded === expanded || reduced) return
    tiles.forEach((tile, i) => {
      const from = before.rects.get(tile.dataset.id!)
      const to = rects.get(tile.dataset.id!)
      if (!from || !to) return
      finish(animate(tile, {
        translateX: [from.left - to.left, 0], translateY: [from.top - to.top, 0], duration: MOTION.morph, ease: 'outExpo',
        delay: i * MOVE_STAGGER, onComplete: releaseStyles('transform'),
      }))
    })
  })
  return list
}
