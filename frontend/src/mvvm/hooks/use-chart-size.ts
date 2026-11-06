import { type RefObject, useLayoutEffect, useRef, useState } from 'react'

/**
 * An element's width, for charts that lay out by it; 0 before the first measure. Pass what changes the element's
 * own layout (e.g. the number of columns) as layout to measure again when it changes.
 */
export function useChartWidth<T extends HTMLElement>(layout?: unknown): [RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  // Measure now too: ResizeObserver reports only with the next rendering update, which a hidden frame skips.
  useLayoutEffect(() => {
    setWidth(ref.current!.clientWidth)
  }, [layout])
  useLayoutEffect(() => {
    const node = ref.current!
    const measure = () => setWidth(node.clientWidth)
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}
