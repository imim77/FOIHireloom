import { type RefObject, useLayoutEffect, useRef, useState } from 'react'

export function useChartWidth<T extends HTMLElement>(layout?: unknown): [RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
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
