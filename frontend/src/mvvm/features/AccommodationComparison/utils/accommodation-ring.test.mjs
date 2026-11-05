import assert from 'node:assert/strict'
import { test } from 'node:test'
import { INNER, START_ANGLE, interpolateGeometry, layoutRing, mod, pillPlace, slicePath, untucked } from './ring-geometry.ts'

test('three statuses partition the ring by ad count, preserving the reference stepped bands', () => {
  const geometry = layoutRing([2, 7, 1])
  geometry.forEach((g, index) => assert.ok(Math.abs(g.span - [72, 252, 36][index]) < 1e-9))
  assert.deepEqual(geometry.map((g) => g.band), [200, 180, 190])
  assert.ok(Math.abs(geometry.reduce((sum, g) => sum + g.span, 0) - 360) < 1e-9)
})

test('one positive group is a complete annulus, with zero groups neither drawn nor selectable', () => {
  for (const values of [[10, 0, 0], [0, 10, 0], [0, 0, 10]]) {
    const geometry = layoutRing(values)
    geometry.forEach((g, index) => {
      const path = slicePath(g)
      if (values[index] > 0) { assert.equal(g.span, 360); assert.equal((path.match(/ A /g) ?? []).length, 4) }
      else assert.equal(path, '')
      // The segment button is drawn untucked; a zero group has no shape to point at or focus.
      assert.equal(slicePath(untucked(g)) === '', values[index] === 0)
    })
  }
})

test('all-zero data and narrow slices remain finite; small spread layers never invert', () => {
  for (const values of [[0, 0, 0], [1, 999999, 0], [0, 1, 999999]]) {
    for (const g of layoutRing(values)) {
      for (const spread of [0, -1, -2]) assert.doesNotMatch(slicePath(g, null, spread), /NaN|Infinity/)
      assert.ok(Object.values(pillPlace(g)).every((value) => typeof value !== 'number' || Number.isFinite(value)))
    }
  }
  assert.ok(layoutRing([0, 0, 0]).every((g) => slicePath(untucked(g)) === ''))
})

test('untucked segments tile the ring exactly, so a point on it belongs to one segment', () => {
  for (const values of [[2, 7, 1], [2, 0, 1], [1, 999999, 0]]) {
    const geometry = layoutRing(values).map(untucked).filter((g) => g.span > 0)
      .sort((a, b) => mod(a.start - START_ANGLE, 360) - mod(b.start - START_ANGLE, 360))
    geometry.forEach((g, at) => {
      const next = geometry[(at + 1) % geometry.length]
      // Where one segment ends the next begins: no gap, no overlap.
      assert.ok(Math.abs(mod(g.start + g.span - next.start + 180, 360) - 180) < 1e-9)
      assert.equal(g.tuckStart + g.tuckEnd, 0)
    })
  }
  const tucked = layoutRing([2, 7, 1])
  assert.ok(tucked.some((g) => g.tuckStart > 0), 'the drawn slices still tuck under their neighbours')
})

test('hiding a group recomputes geometry from visible values, leaving original counts untouched', () => {
  const counts = [2, 7, 1]
  const geometry = layoutRing(counts.map((count, index) => index === 1 ? 0 : count))
  assert.equal(geometry[1].span, 0)
  assert.equal(geometry[0].span, 240)
  assert.equal(geometry[2].span, 120)
  assert.deepEqual(counts, [2, 7, 1])
})

test('morphs and sweep clipping stay finite across zero, full-ring and selected layouts', () => {
  const from = layoutRing([2, 7, 1])
  const to = layoutRing([2, 0, 1], 0)
  for (let i = 0; i <= 20; i++) {
    const t = i / 20
    from.forEach((g, index) => {
      const frame = interpolateGeometry(g, to[index], t)
      assert.doesNotMatch(slicePath(frame, { from: -30.188, upTo: t * 366 }), /NaN|Infinity/)
      assert.ok(frame.outer >= INNER)
    })
  }
  assert.ok(to[0].outer > to[0].band)
})
