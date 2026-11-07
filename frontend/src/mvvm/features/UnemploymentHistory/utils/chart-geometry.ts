const round = (value: number) => Math.round(value * 1000) / 1000

/** Six or so round percentage ticks, with a visible baseline and a nonzero range even for all-zero data. */
export function rateAxis(values: number[]) {
  const known = values.filter(Number.isFinite)
  const low = Math.min(0, ...known)
  const high = Math.max(0, ...known)
  const rawStep = (high > low ? high - low : 1) / 5
  const power = 10 ** Math.floor(Math.log10(rawStep))
  const step = ([1, 2, 2.5, 5, 10].find((value) => value * power >= rawStep) ?? 10) * power
  const first = Math.floor(low / step) * step
  const last = Math.ceil((high > low ? high : low + 1) / step) * step
  const ticks = Array.from({ length: Math.round((last - first) / step) + 1 }, (_, i) => round(first + i * step))
  return { low: ticks[0], high: ticks.at(-1)!, ticks }
}

/** Keep the first and last month and reserve room for year labels at both edges. */
export function monthTicks(count: number, width: number) {
  if (!count) return []
  let labels = Math.min(count, Math.max(1, Math.floor(width / 120) + 1))
  while (labels > 1) {
    const indices = Array.from({ length: labels }, (_, index) => Math.round(index * (count - 1) / (labels - 1)))
    const boxes = indices.map((index, position) => {
      const x = index * width / Math.max(1, count - 1)
      const left = position === 0 ? 0 : position === labels - 1 ? x - 72 : x - 36
      return { left, right: left + 72 }
    })
    if (boxes.every((box, index) => index === 0 || box.left >= boxes[index - 1].right + 8)) return indices
    labels--
  }
  return [count - 1]
}
