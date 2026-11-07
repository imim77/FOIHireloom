// Motion helpers for every view, on GSAP: animations that still reach their end state in a hidden frame, an
// entrance timeline, counting numbers and the reduced-motion setting.

import { gsap } from 'gsap'
import { type RefObject, useLayoutEffect, useRef, useSyncExternalStore } from 'react'

const REDUCE = '(prefers-reduced-motion: reduce)'

/**
 * MOTION holds the timings (ms) of the DESIGN.md motion table: short durations and tight staggers, so things slide
 * into place in sequence. at is the start within an entrance timeline; rise is how far (px) an element comes up from.
 * GSAP counts in seconds; pass these through s().
 */
export const MOTION = {
  readout: { at: 100, duration: 500, stagger: 60, rise: 6 }, // eyebrow and readout lines
  headline: { at: 150, duration: 1200 }, // the headline number counting up from 0
  marks: { at: 250, duration: 900, stagger: 50 }, // chart marks drawing in (Recharts)
  labels: { at: 350, duration: 400, stagger: 20, rise: 4 }, // axis labels
  pill: { duration: 450, progress: 0.45 }, // pops in as the active mark passes this share of its growth
  slide: 450, // the pill moving to a new item
  pop: 400, // the active value on a new focus
  roll: 250, // the readout label rolling to a new name; also the hover roll of links and pills
  count: 600, // a number counting to a new value
  morph: 600, // shapes regrowing from their size on screen for new data
  frame: 1150, // where the card's own parts (notes, sources, footers) come in: once the marks have drawn
} as const

/** EASE names DESIGN.md's easings in GSAP terms: outExpo for arrivals, a back ease only for pops. */
export const EASE = { arrive: 'expo.out', exit: 'power1.in', pop: 'back.out(2)' } as const

/** s converts MOTION's milliseconds to GSAP's seconds. */
export const s = (ms: number) => ms / 1000

export function useReducedMotion(): boolean {
  return useSyncExternalStore((onChange) => {
    const query = matchMedia(REDUCE)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, () => matchMedia(REDUCE).matches)
}

/**
 * Browsers pause animation frames in hidden frames, and a host may keep the view's frame hidden while it plays;
 * complete the animation by its deadline anyway, so its end state still arrives. A killed animation stays killed.
 */
export function finish<T extends gsap.core.Animation>(animation: T): T {
  const timer = setTimeout(() => {
    if (animation.progress() < 1) animation.progress(1)
  }, (animation.delay() + animation.totalDuration()) * 1000 + 100)
  const clear = () => clearTimeout(timer)
  animation.eventCallback('onInterrupt', clear)
  void animation.then(clear)
  return animation
}

/**
 * For an entrance timeline: hide targets at once (not one frame later, when the timeline first renders) and return
 * the tween vars that fade them in, rising by rise pixels, and then hand the styles back to the stylesheet.
 */
export function fadeIn(targets: Element[], rise = 0): gsap.TweenVars {
  gsap.set(targets, { opacity: 0, y: rise })
  return { opacity: 1, y: 0, ease: EASE.arrive, clearProps: 'opacity,transform' }
}

/** enter adds a staggered fade-and-rise of targets to timeline at ms, if there are any. */
export function enter(timeline: gsap.core.Timeline, targets: Element[], at: number,
  { rise = MOTION.labels.rise, duration = MOTION.labels.duration, stagger = MOTION.labels.stagger }:
    { rise?: number; duration?: number; stagger?: number } = {}) {
  if (!targets.length) return
  timeline.to(targets, { ...fadeIn(targets, rise), duration: s(duration), stagger: s(stagger) }, s(at))
}

/**
 * Play an entrance timeline once, when the view mounts (or when ready first turns true). build adds to the
 * timeline and may return a cleanup that puts the view in its final state, should it unmount before the timeline
 * ends. Skipped for reduced motion.
 */
export function useChartEntrance(root: RefObject<HTMLElement | null>,
  build: (timeline: gsap.core.Timeline) => (() => void) | void, ready = true) {
  const reduced = useReducedMotion()
  const played = useRef(false)
  useLayoutEffect(() => {
    if (!root.current || reduced || !ready || played.current) return
    played.current = true
    const timeline = gsap.timeline()
    const cleanup = build(timeline)
    // After build: the deadline needs the timeline's full duration.
    finish(timeline)
    return () => {
      timeline.kill()
      cleanup?.()
    }
    // Once: later changes animate on their own.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready])
}

/** clearEntrance hands targets' opacity and transform back to the stylesheet, for an entrance's cleanup. */
export function clearEntrance(targets: (Element | null | undefined)[]) {
  gsap.set(targets.filter(Boolean) as Element[], { clearProps: 'opacity,transform' })
}

/** useAppear fades its element in, rising, whenever it mounts; for a part that shows up after the entrance. */
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

/** pop scales target up from 86 %, as a new focus pops the active value; for a pressed button. */
export function pop(target: Element, from = 0.86) {
  return finish(gsap.fromTo(target, { scale: from }, { scale: 1, duration: s(MOTION.pop), ease: EASE.pop,
    clearProps: 'transform' }))
}

/** roll brings target in from below its clipping box, as a readout label rolls to a new name. */
export function roll(target: Element) {
  return finish(gsap.fromTo(target, { yPercent: 100 }, { yPercent: 0, duration: s(MOTION.roll), ease: EASE.arrive,
    clearProps: 'transform' }))
}

/** countTo tweens state.value to value, calling show on every frame; returns the tween so callers can kill it. */
export function countTo(state: { value: number }, value: number, show: (value: number) => void,
  duration: number = MOTION.count) {
  return finish(gsap.to(state, { value, duration: s(duration), ease: EASE.arrive, onUpdate: () => show(state.value),
    onComplete: () => show(value) }))
}

/** Count an element's text from the number it shows to a new value whenever value changes. */
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
