import { type RefObject, useCallback, useLayoutEffect, useRef } from 'react'
import { countTo, EASE, MOTION, s, useReducedMotion } from './chart-motion'

export function useReadoutCount(ref: RefObject<HTMLElement | null>, value: number, format: (value: number) => string) {
  const latest = useRef({ value, format })
  const count = useRef<{ value: number; entering: boolean; tween: gsap.core.Tween | null }>(
    { value, entering: false, tween: null })
  const reduced = useReducedMotion()
  useLayoutEffect(() => { latest.current = { value, format } })

  const show = useCallback((value: number) => {
    count.current.value = value
    if (ref.current) ref.current.textContent = latest.current.format(value)
  }, [ref])

  function enter(timeline: gsap.core.Timeline) {
    const up = { t: 0 }
    const countUp = () => show(latest.current.value * up.t)
    count.current.entering = true
    countUp()
    timeline.fromTo(up, { t: 0 }, { t: 1, duration: s(MOTION.headline.duration), ease: EASE.arrive,
      onUpdate: countUp, onComplete: () => { count.current.entering = false } }, s(MOTION.headline.at))
    return () => {
      count.current.entering = false
      show(latest.current.value)
    }
  }

  useLayoutEffect(() => {
    const state = count.current
    if (state.entering || state.value === value) return
    state.tween?.kill()
    state.tween = null
    if (reduced) show(value)
    else state.tween = countTo({ value: state.value }, value, show)
  }, [value, reduced, show])
  useLayoutEffect(() => () => { count.current.tween?.kill() }, [])

  return enter
}
