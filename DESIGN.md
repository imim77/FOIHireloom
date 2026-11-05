# Design

Every FOIHireloom view follows the look of the **jobs-by-county chart**
(`show_jobs_by_county`). When a choice about colour, type, spacing, shape or
motion is open, copy what that chart does. This document names its rules so
the other views can follow them without reverse-engineering the code.

Reference implementation:

- `frontend/src/mvvm/features/JobsByCounty/components/CountyColumns.tsx` —
  layout, interaction, motion
- `frontend/src/mvvm/features/JobsByCounty/components/Bar3d.tsx` — the 3D
  column and its gradients
- `frontend/src/mvvm/tailwind.css` — the tokens every rule below refers to
- `frontend/src/mvvm/components/Card.tsx` — the frame around every view

Preview it with `npm run dev` in `frontend/` and open
`http://localhost:5173/jobs-by-county.html`.

## The idea: grey world, one orange focus

The chart is monochrome. Every datum is a quiet grey shape; the one the user
is looking at lights up orange, and a single large number above the chart
says what that datum means. Colour marks **focus**, not category.

1. **One lit thing.** At most one datum per view is orange at a time. All
   others stay grey (`surface-disable` → `surface-subdued`, 32 % opacity).
2. **The number leads.** The active datum's key value sits above the chart
   in 28 px semibold; the chart explains it, not the other way round.
3. **Quiet text.** Labels, values and notes are 12 px `fg-soft`. Only the
   headline number and the active label use loud ink.
4. **Dark pill for the active label.** The selected item's name sits in a
   `surface-muted` pill with `fg-on-muted` text, which inverts in dark mode.
5. **Motion explains change.** Things grow from zero, numbers count, the pill
   slides. Nothing moves without a data or focus change behind it.

## Colour

Use only the semantic tokens from `tailwind.css`. Never hard-code a hex value
in a component; if a view needs a colour that is not here, add a token to
both `:root` and `:root[data-theme="dark"]` first and justify it.

| Role | Token | Light | Dark |
| --- | --- | --- | --- |
| Card / page | `card` | `#ffffff` | `#18181b` |
| Loud text (headline, active) | `fg-loud` | `#18181b` | `#fafafa` |
| Soft text (labels, values, notes) | `fg-soft` | `#71717a` | `#a1a1aa` |
| Hairlines | `border` | `#ececef` | `#2e2e33` |
| Inactive datum, light end | `surface-subdued` | `#eceef2` | `#3f3f46` |
| Inactive datum, dark end | `surface-disable` | `#c4c8d0` | `#71717a` |
| Sunken rows, hover wash | `surface-sunken` | `#f1f2f4` | `#0f0f11` |
| Active pill, primary button | `surface-muted` | `#27272a` | `#f4f4f5` |
| Text on the pill | `fg-on-muted` | `#ffffff` | `#18181b` |
| Focus, light end / lid | `orange-100` | `#ffd9c2` | `#ffb98f` |
| Focus, dark end | `orange-300` | `#ff9a5c` | `#e8742f` |
| Focus ring, lines, small marks | `orange-500` | `#f26419` | `#f26419` |

Status colours are the only exception to "grey plus orange", and they never
encode data: `warning-bg`/`warning-fg` (coverage warnings), `green-tint`/
`green-on-tint` (success badges), `destructive` (errors).

### Encoding data

- **Single series, many items** (bars, columns, rows): items grey, the active
  one orange. Hover previews, click selects.
- **Several series at once** (lines per county): the active series is
  `orange-500`, the others `surface-disable` at reduced opacity. The legend or
  stat tiles choose the active series, just as the axis does for columns.
- **Parts of a whole** (offered / not offered / unknown): the part the
  question is about is orange (`orange-100` → `orange-300`), the rest are
  quiet greys (`surface-disable`, `surface-subdued`). Never `surface-muted`
  for a datum: it inverts to near-white in dark mode and out-shouts the
  orange. Focus dims the other parts instead of recolouring them, and each
  part keeps its label and value beside it, so colour is never the only cue.
- **Measured vs projected** (history vs forecast): history is grey
  (`fg-soft` line), the projection is orange, its interval an `orange-100`
  wash. Provisional or projected segments are dashed.
- **Gaps stay gaps.** Missing values are not drawn and not interpolated.

## Shape

The column from `Bar3d.tsx` is the signature shape:

- two faces with a vertical gradient (`*-100` → `*-300` when lit,
  `surface-disable` → `surface-subdued` when grey);
- a flat lid one step lighter (`orange-100` / `surface-subdued`);
- hairline edges in `card` colour, so the faces read as separate planes in
  both themes;
- a bottom fade (`mask-image`: opaque to 72 %, transparent at 100 %), so the
  column rises out of the card instead of standing on a baseline.

Other marks borrow the same vocabulary: soft vertical gradients, a lighter
top surface, card-coloured separators between adjacent shapes, and no axis
lines, gridlines or outlines unless the reader needs them to read a value.

Radii: card `rounded-xl` (shadcn), label pill `8px`, focus ring `12px`
around the focused item, badges fully rounded.

## Typography

Inter (`font-sans`), numbers always `tabular-nums`.

| Use | Size / weight / leading | Colour |
| --- | --- | --- |
| Headline number (active datum) | 28 px / 600 / 1 | `fg-loud` |
| Card title | shadcn `CardTitle` (16 px / 500) | `fg-loud` |
| Body, table cells | 14 px / 400 | `fg-loud` |
| Context line, values, axis labels, footer | 12 px / 500 / 1.25 | `fg-soft` |
| Active axis label | 12 px / 600 | `fg-on-muted` on the pill |

These four sizes (28, 16, 14, 12) are the scale. Sizes outside it (9, 10,
11, 13, 15, 18, 22, 24, 32, 36 px and `clamp()` headlines) are to be
migrated to the nearest step. Long labels clamp to two lines and break after
hyphens (`Splitsko-` / `dalmatinska`) rather than mid-word; the full name goes
in `title` and the `aria-label`.

## Layout

Every view is a `Card` (`components/Card.tsx`) and reads top to bottom:

```text
Card header      title · description            [expand]
Notes            coverage warning, then quiet notes
Readout          "Grad Zagreb · 1.234 oglasa"     12px soft
                 4.567 radnika                    28px loud
Chart            plot (columns + values over them)
                 axis (labels, pill under the active one)
Footer           "Prikazano 8 od 21 županija …"   12px soft
```

- Sections in the card body are `gap-6`; the readout's two lines `gap-2.5`;
  columns and axis labels `gap-2` (8 px); a value sits 4 px over its bar.
- The footer pulls up 8 px (`-mt-2`) so it belongs to the chart above it.
- The plot keeps a fixed height (≈ 209 px) and scrolls sideways when columns
  would narrow below 84 px — it never squeezes labels into illegibility.
- The view shows the top N items; an `ExpandButton` in the header reveals
  all of them. Counts of hidden items go in the footer.

## Interaction

- **Hover previews, click commits.** Pointer hover makes an item active and
  updates the readout; leaving the plot falls back to the selection.
- **Keyboard:** items are buttons in a roving tab order (`tabIndex` 0 only on
  the selected one), `←`/`→`/`↑`/`↓`/`Home`/`End` move the selection, and
  `aria-pressed` marks it. The focus ring is `shadow-focus` (orange-500 at
  40 %) on a 12 px radius, inset 4 px around the item.
- **Accessible names carry the data:** each item's `aria-label` states the
  name and every value the readout shows; decorative SVG is `aria-hidden`.
- Controls are shadcn primitives: `ghost` buttons for chart items, `outline`
  icon buttons for card actions, `default` (dark `surface-muted`) for the
  one primary action.

## Motion

anime.js through the helpers in `hooks/chart-motion.ts`; all easing is
`outExpo` unless a pop is wanted (`outBack`).

| Moment | What moves | Timing |
| --- | --- | --- |
| Entrance | readout fades in, rising 6 px, staggered 80 ms | 600 ms at 100 ms |
| | headline number counts up from 0 | 1400 ms at 150 ms |
| | columns grow from their feet, staggered 70 ms; their values count with them | 1100 ms from 250 ms |
| | axis labels fade in, rising 4 px, staggered 50 ms | 600 ms at 350 ms |
| | pill pops in (scale 0.7 → 1, `outBack(1.7)`) as the active column passes 45 % | 500 ms |
| New focus | pill slides to the new item (cross-fades where items wrap, e.g. a legend) | 550 ms |
| | active value pops (scale 0.86 → 1, `outBack(2)`) | 500 ms |
| | readout name fades 0.4 → 1; number counts to the new value | 300 ms / 600 ms |
| | lit and grey looks cross-fade | 300 ms CSS |
| New data | every shape morphs from the size on screen | 700 ms |

Rules: animate from what is on screen, never jump back to zero on an update;
wrap every animation in `finish()` so hidden host frames still reach the end
state; `prefers-reduced-motion` skips straight to the final state; release
inline styles when an animation ends so the stylesheet applies again.

## Bringing the other views in line

| View | Today | Target |
| --- | --- | --- |
| Unemployment history | six hard-coded hues (`--series-1…6`); redeclares the dark tokens inside `UnemploymentGrowthChart` | active county orange, others grey; legend selects; delete the local token copies |
| Accommodation comparison | blue / light-blue / orange palette and `#18233b`-style inks | orange / `surface-disable` / `surface-subdued` ramp; readout above the ring like the county chart |
| Labour market forecast | teal line, slate history, teal wash; `clamp()` headline | grey history, orange forecast, `orange-100` wash; 28 px headline |
| County / job comparison | already grey with `orange-500` marks | align type to the 28 / 16 / 14 / 12 scale |
| Job cards | neutral | 18 px titles → 16 px; keep orange for the selected/compared state only |

## Checklist for a new or changed view

- [ ] Only tokens from `tailwind.css`; no hex values in components.
- [ ] At most one orange datum at a time; everything else grey.
- [ ] A readout (context line + 28 px number) above the chart follows focus.
- [ ] Text sizes are 28, 16, 14 or 12 px; numbers are `tabular-nums`.
- [ ] Hover previews, click/keys select, focus ring visible, `aria-label`
      carries the values.
- [ ] Entrance and updates animate from what is on screen; reduced motion
      shows the end state.
- [ ] Checked in light and dark (`data-theme="dark"`) and at narrow width.
