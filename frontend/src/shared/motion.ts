// Easings and a requestAnimationFrame tween, standing in for anime.js.

export const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches

type Easing = (t: number) => number

export const ease = {
  outExpo: ((t) => (t >= 1 ? 1 : 1 - 2 ** (-10 * t))) as Easing,
  outQuad: ((t) => 1 - (1 - t) * (1 - t)) as Easing,
  outBack: (s: number): Easing => (t) => 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2,
}

export interface Tween {
  cancel(): void
}

interface TweenOptions {
  duration: number
  delay?: number
  easing?: Easing
  update: (progress: number) => void
  done?: () => void
}

export function tween({ duration, delay = 0, easing = ease.outExpo, update, done }: TweenOptions): Tween {
  let finished = false
  const start = performance.now() + delay
  const finish = () => {
    if (finished) return
    finished = true
    clearTimeout(timer)
    update(1)
    done?.()
  }
  const frame = (now: number) => {
    if (finished) return
    const t = Math.min(1, Math.max(0, (now - start) / duration))
    if (t >= 1) return finish()
    update(easing(t))
    requestAnimationFrame(frame)
  }
  requestAnimationFrame(frame)
  // Browsers pause animation frames in hidden frames; the end state must still arrive.
  const timer = setTimeout(finish, delay + duration + 100)
  return {
    cancel() {
      finished = true
      clearTimeout(timer)
    },
  }
}

interface FadeOptions {
  at?: number
  duration?: number
  stagger?: number
  rise?: number
  from?: number
}

export function fadeIn(nodes: Iterable<HTMLElement>, { at = 0, duration = 600, stagger = 0, rise = 0, from = 0 }: FadeOptions = {}): Tween[] {
  return [...nodes].map((node, i) => {
    node.style.opacity = String(from)
    if (rise) node.style.transform = `translateY(${rise}px)`
    return tween({
      duration, delay: at + i * stagger, easing: ease.outQuad,
      update: (p) => {
        node.style.opacity = String(from + (1 - from) * p)
        if (rise) node.style.transform = `translateY(${rise * (1 - p)}px)`
      },
      done: () => {
        node.style.opacity = ''
        node.style.transform = ''
      },
    })
  })
}

interface PopOptions {
  at?: number
  duration?: number
  from?: number
  overshoot?: number
  fade?: boolean
}

export function pop(node: HTMLElement, { at = 0, duration = 500, from = 0.7, overshoot = 1.7, fade = true }: PopOptions = {}): Tween {
  return tween({
    duration, delay: at, easing: ease.outBack(overshoot),
    update: (p) => {
      node.style.transform = `scale(${from + (1 - from) * p})`
      if (fade) node.style.opacity = String(Math.min(1, Math.max(0, p)))
    },
    done: () => {
      node.style.transform = ''
      node.style.opacity = ''
    },
  })
}
