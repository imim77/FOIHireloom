// Motion helpers for the charts, after the original library's hooks/use-chart-motion: anime.js animations that
// still reach their end state in a hidden frame, an entrance timeline, counting numbers and the reduced-motion setting.

import { animate, createTimeline, type JSAnimation, type Timeline } from 'animejs'
import { type RefObject, useLayoutEffect, useRef, useSyncExternalStore } from 'react'

const REDUCE = '(prefers-reduced-motion: reduce)'

export function useReducedMotion(): boolean {
  return useSyncExternalStore((onChange) => {
    const query = matchMedia(REDUCE)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, () => matchMedia(REDUCE).matches)
}

/**
 * Browsers pause animation frames in hidden frames, and a host may keep the view's frame hidden while it plays;
 * complete the animation by its deadline anyway, so its end state still arrives.
 */
export function finish<T extends JSAnimation | Timeline>(animation: T): T {
  const timer = setTimeout(() => {
    if (!animation.completed && !animation.cancelled) animation.complete()
  }, animation._delay + animation.duration + 100)
  void animation.then(() => clearTimeout(timer))
  return animation
}

/** An onComplete that removes the inline styles an animation left on its targets, so the stylesheet applies again. */
export function releaseStyles(...properties: string[]) {
  return (animation: JSAnimation) => {
    for (const target of animation.targets) {
      if (target instanceof HTMLElement || target instanceof SVGElement) {
        for (const property of properties) target.style.removeProperty(property)
      }
    }
  }
}

/**
 * Play an entrance timeline once, when the chart mounts. build adds to the timeline and may return a cleanup that
 * puts the chart in its final state, should the chart unmount before the timeline ends. Skipped for reduced motion.
 */
export function useChartEntrance(root: RefObject<HTMLElement | null>, build: (timeline: Timeline) => (() => void) | void) {
  const reduced = useReducedMotion()
  useLayoutEffect(() => {
    if (!root.current || reduced) return
    const timeline = createTimeline()
    const cleanup = build(timeline)
    // After build: the deadline needs the timeline's full duration.
    finish(timeline)
    return () => {
      timeline.cancel()
      cleanup?.()
    }
    // Once: later changes animate on their own.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}

/** Count an element's text from the number it shows to a new value whenever value changes. */
export function useCountUp(ref: RefObject<HTMLElement | null>, value: number, format: (value: number) => string,
  { duration = 600 }: { duration?: number } = {}) {
  const reduced = useReducedMotion()
  const shown = useRef({ value })
  const tween = useRef<JSAnimation | null>(null)
  useLayoutEffect(() => {
    const node = ref.current
    const state = shown.current
    if (!node || state.value === value) return
    tween.current?.cancel()
    if (reduced) {
      state.value = value
      node.textContent = format(value)
      return
    }
    tween.current = finish(animate(state, {
      value, duration, ease: 'outExpo',
      onUpdate: () => { node.textContent = format(state.value) },
      onComplete: () => { node.textContent = format(value) },
    }))
  }, [ref, value, format, duration, reduced])
  useLayoutEffect(() => () => { tween.current?.cancel() }, [])
}
