// Geometry from the supplied PortfolioAllocationChart: spiral-like stepped bands, tucked ends and share labels.
export const SIZE = 400
export const CENTER = SIZE / 2
export const INNER = 116.82
export const START_ANGLE = -30.188
export const TUCK = 6
const OUTER = 200
const STEP = 10
const MIN_BAND = 40
const POP = 6
const PILL = 48
const PILL_INSET = 13.15

export interface SliceGeometry {
  start: number
  span: number
  outer: number
  band: number
  tuckStart: number
  tuckEnd: number
}

const fixed = (n: number) => Math.round(n * 1000) / 1000
const rad = (degrees: number) => degrees * Math.PI / 180
export const mod = (n: number, m: number) => ((n % m) + m) % m
const polar = (radius: number, angle: number) => [CENTER + radius * Math.sin(angle), CENTER - radius * Math.cos(angle)]

export function layoutRing(values: number[], active: number | null = null, startAngle = START_ANGLE): SliceGeometry[] {
  const shown = values.flatMap((value, index) => value > 0 ? [index] : [])
  const total = shown.reduce((sum, index) => sum + values[index], 0)
  const m = shown.length
  const step = m > 1 ? Math.min(STEP, (OUTER - INNER - MIN_BAND) / (m - 1)) : 0
  const thinnest = OUTER - step * Math.max(0, m - 1)
  let edge = startAngle
  return values.map((value, index) => {
    const at = shown.indexOf(index)
    if (at < 0) return { start: shown.length && index > shown[0] ? edge : startAngle,
      span: 0, outer: thinnest, band: thinnest, tuckStart: 0, tuckEnd: 0 }
    const span = value / total * 360
    const rank = at === 0 ? 0 : m - at
    const band = OUTER - step * rank
    const outer = band + (index === active ? POP : 0)
    if (at === 0) return { start: startAngle, span, outer, band, tuckStart: 0, tuckEnd: 0 }
    edge -= span
    return { start: edge, span, outer, band, tuckStart: TUCK, tuckEnd: rank === m - 1 ? TUCK : 0 }
  })
}

function annulusPath(outer: number, inner: number) {
  const circle = (r: number, sweep: number) =>
    `M ${fixed(CENTER - r)} ${CENTER} A ${fixed(r)} ${fixed(r)} 0 1 ${sweep} ${fixed(CENTER + r)} ${CENTER} A ${fixed(r)} ${fixed(r)} 0 1 ${sweep} ${fixed(CENTER - r)} ${CENTER} Z`
  return `${circle(outer, 1)} ${circle(inner, 0)}`
}

export function slicePath(g: SliceGeometry, clip?: { from: number; upTo: number } | null, spread = 0) {
  if (!(g.span > 0.001)) return ''
  let a0 = g.start - g.tuckStart
  let a1 = g.start + g.span + g.tuckEnd
  if (clip) {
    const u0 = mod(a0 - clip.from, 360)
    const u1 = Math.min(u0 + a1 - a0, clip.upTo)
    if (!(u1 > u0)) return ''
    a0 = clip.from + u0
    a1 = clip.from + u1
  }
  const outer = g.outer + spread
  const inner = INNER * outer / g.outer
  if (a1 - a0 >= 359.999) return annulusPath(outer, inner)
  const ends = spread < 0 ? (-spread / ((inner + outer) / 2)) * 180 / Math.PI : 0
  if (a1 - a0 <= 2 * ends) return ''
  const [x0, y0] = polar(outer, rad(a0 + ends))
  const [x1, y1] = polar(outer, rad(a1 - ends))
  const [x2, y2] = polar(inner, rad(a1 - ends))
  const [x3, y3] = polar(inner, rad(a0 + ends))
  const large = a1 - a0 - ends * 2 > 180 ? 1 : 0
  return `M ${fixed(x0)} ${fixed(y0)} A ${fixed(outer)} ${fixed(outer)} 0 ${large} 1 ${fixed(x1)} ${fixed(y1)} L ${fixed(x2)} ${fixed(y2)} A ${fixed(inner)} ${fixed(inner)} 0 ${large} 0 ${fixed(x3)} ${fixed(y3)} Z`
}

export function pillPlace(g: SliceGeometry) {
  const radius = (INNER + g.band) / 2 + 0.6
  const angle = g.start + g.span - Math.min(PILL_INSET, g.span / 2)
  const [x, y] = polar(radius, rad(angle))
  return { left: Math.round(x - PILL / 2), top: Math.round(y - PILL / 2), fits: rad(g.span) * radius >= PILL + 6 }
}

export function interpolateGeometry(a: SliceGeometry, b: SliceGeometry, t: number): SliceGeometry {
  const from = a.start + 360 * Math.round((b.start - a.start) / 360)
  const lerp = (a: number, b: number) => a + (b - a) * t
  return { start: lerp(from, b.start), span: lerp(a.span, b.span), outer: lerp(a.outer, b.outer),
    band: lerp(a.band, b.band), tuckStart: lerp(a.tuckStart, b.tuckStart), tuckEnd: lerp(a.tuckEnd, b.tuckEnd) }
}

/** A slice without its tucked ends: its own angular range, which no neighbour overlaps, for pointer and focus. */
export function untucked(g: SliceGeometry): SliceGeometry {
  return { ...g, tuckStart: 0, tuckEnd: 0 }
}
