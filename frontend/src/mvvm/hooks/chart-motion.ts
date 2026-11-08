
import { gsap } from 'gsap'
import { type RefObject, useLayoutEffect, useRef, useSyncExternalStore } from 'react'

const REDUCE = '(prefers-reduced-motion: reduce)'

export const MOTION = {
  readout: { at: 100, duration: 500, stagger: 60, rise: 6 },
  headline: { at: 150, duration: 1200 },
  marks: { at: 250, duration: 900, stagger: 50 },
  labels: { at: 350, duration: 400, stagger: 20, rise: 4 },
  pill: { duration: 450, progress: 0.45 },
  slide: 450,
  pop: 400,
  roll: 250,
  count: 600,
  morph: 600,
  frame: 1150,
} as const

export const EASE = { arrive: 'expo.out', exit: 'power1.in', pop: 'back.out(2)' } as const

export const s = (ms: number) => ms / 1000

export function useReducedMotion(): boolean {
  return useSyncExternalStore((onChange) => {
    const query = matchMedia(REDUCE)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, () => matchMedia(REDUCE).matches)
}

export function finish<T extends gsap.core.Animation>(animation: T): T {
  const timer = setTimeout(() => {
    if (animation.progress() < 1) animation.progress(1)
  }, (animation.delay() + animation.totalDuration()) * 1000 + 100)
  const clear = () => clearTimeout(timer)
  animation.eventCallback('onInterrupt', clear)
  void animation.then(clear)
  return animation
}

export function fadeIn(targets: Element[], rise = 0): gsap.TweenVars {
  gsap.set(targets, { opacity: 0, y: rise })
  return { opacity: 1, y: 0, ease: EASE.arrive, clearProps: 'opacity,transform' }
}

export function enter(timeline: gsap.core.Timeline, targets: Element[], at: number,
  { rise = MOTION.labels.rise, duration = MOTION.labels.duration, stagger = MOTION.labels.stagger }:
    { rise?: number; duration?: number; stagger?: number } = {}) {
  if (!targets.length) return
  timeline.to(targets, { ...fadeIn(targets, rise), duration: s(duration), stagger: s(stagger) }, s(at))
}

export function useChartEntrance(root: RefObject<HTMLElement | null>,
  build: (timeline: gsap.core.Timeline) => (() => void) | void, ready = true) {
  const reduced = useReducedMotion()
  const played = useRef(false)
  useLayoutEffect(() => {
    if (!root.current || reduced || !ready || played.current) return
    played.current = true
    const timeline = gsap.timeline()
    const cleanup = build(timeline)
    finish(timeline)
    return () => {
      timeline.kill()
      cleanup?.()
    }
  }, [ready])
}

export function clearEntrance(targets: (Element | null | undefined)[]) {
  gsap.set(targets.filter(Boolean) as Element[], { clearProps: 'opacity,transform' })
}

export function useAppear<T extends HTMLElement>() {
  const reduced = useReducedMotion()
  const element = useRef<T>(null)
  const shown = useRef<T | null>(null)
  useLayoutEffect(() => {
    const node = element.current
    if (node === shown.current) return
    shown.current = node
    if (!node || reduced) return
    finish(gsap.fromTo(node, { opacity: 0, y: MOTION.labels.rise }, { opacity: 1, y: 0, duration: s(MOTION.labels.duration),
      ease: EASE.arrive, clearProps: 'opacity,transform' }))
  })
  return element
}

export function pop(target: Element, from = 0.86) {
  return finish(gsap.fromTo(target, { scale: from }, { scale: 1, duration: s(MOTION.pop), ease: EASE.pop,
    clearProps: 'transform' }))
}

export function roll(target: Element) {
  return finish(gsap.fromTo(target, { yPercent: 100 }, { yPercent: 0, duration: s(MOTION.roll), ease: EASE.arrive,
    clearProps: 'transform' }))
}

export function countTo(state: { value: number }, value: number, show: (value: number) => void,
  duration: number = MOTION.count) {
  return finish(gsap.to(state, { value, duration: s(duration), ease: EASE.arrive, onUpdate: () => show(state.value),
    onComplete: () => show(value) }))
}

export function useCountUp(ref: RefObject<HTMLElement | null>, value: number, format: (value: number) => string,
  { duration = MOTION.count }: { duration?: number } = {}) {
  const reduced = useReducedMotion()
  const shown = useRef({ value })
  const tween = useRef<gsap.core.Tween | null>(null)
  useLayoutEffect(() => {
    const node = ref.current
    const state = shown.current
    if (!node || state.value === value) return
    tween.current?.kill()
    if (reduced) {
      state.value = value
      node.textContent = format(value)
      return
    }
    tween.current = countTo(state, value, (v) => { node.textContent = format(v) }, duration)
  }, [ref, value, format, duration, reduced])
  useLayoutEffect(() => () => { tween.current?.kill() }, [])
}
