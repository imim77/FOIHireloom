import assert from 'node:assert/strict'
import { test } from 'node:test'
import { INNER, SIZE, interpolateGeometry, layoutRing, pillPlace, sliceAt, slicePath } from '../src/views/accommodation-comparison/ring-geometry.ts'

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
    })
    assert.equal(sliceAt(SIZE / 2, 30, geometry), values.findIndex((value) => value > 0))
  }
})

test('all-zero data and narrow slices remain finite; small spread layers never invert', () => {
  for (const values of [[0, 0, 0], [1, 999999, 0], [0, 1, 999999]]) {
    for (const g of layoutRing(values)) {
      for (const spread of [0, -1, -2]) assert.doesNotMatch(slicePath(g, null, spread), /NaN|Infinity/)
      assert.ok(Object.values(pillPlace(g)).every((value) => typeof value !== 'number' || Number.isFinite(value)))
    }
  }
  assert.equal(sliceAt(200, 200, layoutRing([0, 0, 0])), null)
})

test('hit testing selects each angular segment, rejecting the central hole and outside space', () => {
  const geometry = layoutRing([2, 7, 1])
  geometry.forEach((g, index) => {
    const angle = (g.start + g.span / 2) * Math.PI / 180
    const radius = (INNER + g.outer) / 2
    assert.equal(sliceAt(200 + radius * Math.sin(angle), 200 - radius * Math.cos(angle), geometry), index)
  })
  assert.equal(sliceAt(200, 200, geometry), null)
  assert.equal(sliceAt(-20, -20, geometry), null)
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
