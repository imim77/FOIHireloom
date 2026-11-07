# Design

Every FOIHireloom view follows the look of [dalco.ch](https://www.dalco.ch)
([Awwwards nominee](https://www.awwwards.com/sites/dalco)): a quiet,
monochrome Swiss-tech surface with one signal red, a clean grotesk paired
with an uppercase mono for labels, generous white space and short, precise
motion. When a choice about colour, type, spacing, shape or motion is open,
ask what that site would do.

The data rules come from the **jobs-by-county chart** (`show_jobs_by_county`),
which already works the way Dalco looks: grey shapes, one lit item, a big
number above. It stays the reference implementation:

- `frontend/src/mvvm/features/JobsByCounty/components/CountyColumns.tsx` —
  layout, interaction, motion
- `frontend/src/mvvm/components/ui/chart.tsx` — the shadcn chart
  (`ChartContainer`, `ChartTooltip`, `ChartLegend` over Recharts) every
  chart draws with
- `frontend/src/mvvm/tailwind.css` — the tokens every rule below refers to
- `frontend/src/mvvm/components/Card.tsx` — the frame around every view

Preview it with `npm run dev` in `frontend/` and open
`http://localhost:5173/jobs-by-county.html`.

## The idea: monochrome hardware, one red signal

Dalco shows black-and-silver machines on near-white space; the only colour
is a red that marks what matters (the logo, the drive caddies, the word to
read first). Our views do the same with data.

1. **One red thing.** At most one datum per view is red at a time. All
   others stay grey (`surface-disable` → `surface-subdued`, dimmed just
   enough to sit behind the red while still reading as shapes on white).
   Small markers (a 6 px dot beside a label, such as "differs" in a
   comparison) may repeat; filled shapes and lines may not.
2. **The number leads.** The active datum's key value sits above the chart
   in a 28 px mono number; the chart explains it, not the other way round.
3. **Labels speak mono.** Context lines, axis labels and eyebrows are small
   uppercase mono in `fg-soft`, like Dalco's `• OUR PRODUCTS`. Running text
   and names stay in the grotesk.
4. **Black pill for the active label and the primary action.** The selected
   item's name, and the one primary button, sit in a fully rounded
   `surface-muted` pill with `fg-on-muted` text (inverts in dark mode).
5. **Air over ornament.** No gridlines, shadows or gradients for decoration.
   Space, hairlines and one colour carry the structure.
6. **Motion is mechanical.** Short, precise, staggered: things slide into
   place like a drive into a bay. Nothing moves without a data or focus
   change behind it.

## Colour

Use only the semantic tokens from `tailwind.css`. Never hard-code a hex value
in a component; if a view needs a colour that is not here, add a token to
both `:root` and `:root[data-theme="dark"]` first and justify it.

| Role | Token | Light | Dark |
| --- | --- | --- | --- |
| Card / page | `card` | `#ffffff` | `#191919` |
| Loud text (headline, active) | `fg-loud` | `#191919` | `#f4f4f4` |
| Soft text (labels, values, notes) | `fg-soft` | `#6e6e6e` | `#9a9a9a` |
| Hairlines | `border` | `#ededed` | `#2f2f2f` |
| Inactive datum, light end | `surface-subdued` | `#eeeeee` | `#3a3a3a` |
| Inactive datum, dark end | `surface-disable` | `#cdcdcd` | `#6e6e6e` |
| Sunken rows, hover wash, tiles | `surface-sunken` | `#f7f8fd` | `#111111` |
| Active pill, primary button | `surface-muted` | `#191919` | `#f4f4f4` |
| Text on the pill | `fg-on-muted` | `#ffffff` | `#191919` |
| Lid, light focus fills | `accent-100` | `#ffd5ce` | `#ff9d8f` |
| Focus, light end of faces | `accent-300` | `#ff7a66` | `#f0533c` |
| Focus, dark end; ring, lines, marks | `accent-500` | `#fb290e` | `#fb290e` |
| Ranges and areas (translucent) | `accent-wash` | `accent-100` at 70 % | `accent-500` at 40 % |

Dalco's red is `#fb290e`; its greys are pure neutrals (`#191919`, `#888`,
`#cdcdcd`, `#eee`) with one cool tint for panels (`#f7f8fd`). `fg-soft` is
darker than Dalco's `#888` because 12 px text needs 4.5 : 1 on white.

Status colours are the only exception to "grey plus red", and they never
encode data: `warning-bg`/`warning-fg` (coverage warnings), `green-tint`/
`green-on-tint` (success badges), `destructive` (errors). `destructive` must
stay visibly different from `accent-500`, so errors also carry an icon and
text, never colour alone.

### Encoding data

- **Single series, many items** (bars, columns, rows): items grey, the active
  one red. Hover previews, click selects.
- **Several series at once** (lines per county): the active series is
  `accent-500`, the others `surface-disable` at reduced opacity. The legend or
  stat tiles choose the active series, just as the axis does for columns.
- **Parts of a whole** (offered / not offered / unknown): the part the
  question is about is red (`accent-300` → `accent-500`), the rest are quiet
  greys (`surface-disable`, `surface-subdued`). Never `surface-muted` for a
  datum: it inverts to near-white in dark mode and out-shouts the red. Focus
  dims the other parts instead of recolouring them, keeping a
  `surface-disable` hairline edge so the lightest part never fades into the
  card, and each part keeps its label and value beside it, so colour is never
  the only cue.
- **Measured vs projected** (history vs forecast): history is grey (`fg-soft`
  line), the projection is red, its interval an `accent-wash` fill edged in
  `accent-300`. A pale tint at low opacity turns muddy on the dark card, so
  the wash token mixes the saturated red there. Provisional or projected
  segments are dashed.
- **Gaps stay gaps.** Missing values are not drawn and not interpolated.

## Shape

Every chart is a shadcn chart: a `ChartContainer` whose `ChartConfig` maps
each series to a token (`var(--accent-500)`, `var(--surface-disable)`, …), so
both themes follow `data-theme` without per-chart dark rules. Marks are flat
(no gradients, drop shadows, glows, bevels or blur): solid fills, a `4px`
radius on the top of a column, card-coloured separators between adjacent
shapes, and no axis lines, gridlines or outlines unless the reader needs them
to read a value. Tooltips are flat too: a `card` panel with a `border`
hairline and mono labels.

Radii follow Dalco: cards and tiles `10px`; buttons, pills and chips fully
rounded (`9999px`); focus ring `12px` around the focused item. Hairlines are
`1px` `border` (Dalco uses 0.5 px on retina; 1 px keeps it visible on
standard screens). Secondary buttons are outline pills: transparent, `1px`
`fg-loud` at 40 %, label plus a `›` chevron (`Detalji ›`).

## Typography

Dalco sets everything in LT Superior (a grotesk) and LT Superior Mono. Both
are commercial, so we use the free pair closest to them, self-hosted in each
built view:

- **Sans:** Geist (`font-sans`), weights 300, 400, 500.
- **Mono:** Geist Mono (`font-mono`), weights 400, 500; numbers in mono are
  tabular by construction, numbers in sans still take `tabular-nums`.

Large text tightens (`-0.02em`), small mono opens up (`+0.04em`), as on Dalco.

| Use | Face / size / weight / leading / tracking | Colour |
| --- | --- | --- |
| Headline number (active datum) | mono 28 px / 500 / 1 / -0.02em | `fg-loud` |
| Card title | sans 16 px / 500 / 1.4 / -0.01em | `fg-loud` |
| Body, table cells, names | sans 14 px / 400 / 1.5 | `fg-loud` |
| Eyebrow, context line, axis labels, values, footer | mono 12 px / 400 / 1.25 / +0.04em, uppercase | `fg-soft` |
| Active axis label | mono 12 px / 500, uppercase | `fg-on-muted` on the pill |

These four sizes (28, 16, 14, 12) are the scale; anything else migrates to
the nearest step. Short labels that sit with the data (axis names, values,
the readout line, footers) are mono; prose, titles, descriptions and names
inside running text are sans. Uppercase is for mono labels that are not
names (eyebrows, units, footers); place and person names keep their own case
even in mono, because uppercase Croatian names lose their shape, so the
readout reads `Grad Zagreb · 1.325 OGLASA`. Unit symbols and
abbreviations keep their own case even inside an uppercase label (`2,7 %`,
`+0,2 p. b.`, `20 h`); counted nouns follow the label (`1.325 OGLASA`).
Values that are phrases (job conditions such as `Srednja škola 3 godine`)
are not labels and keep their own case. Long labels clamp to two lines and break
after hyphens (`Splitsko-` / `dalmatinska`) rather than mid-word; the full
name goes in `title` and the `aria-label`.

The **eyebrow** is Dalco's section marker: a 6 px `accent-500` dot, 8 px gap,
then the mono label (`● PROGNOZA`). Use it once per card, above the title,
for the kind of view, not for data.

## Layout

Every view is a `Card` (`components/Card.tsx`) and reads top to bottom:

```text
Eyebrow          ● BROJ OGLASA                    12px mono
Card header      title · description            [expand]
Notes            coverage warning, then quiet notes
Readout          Grad Zagreb · 1.234 OGLASA       12px mono soft
                 4.567 radnika                    28px mono loud
Chart            plot (columns + values over them)
                 axis (labels, pill under the active one)
Footer           PRIKAZANO 8 OD 21 ŽUPANIJA …     12px mono soft
```

- Sections in the card body are `gap-6`; the readout's two lines `gap-2.5`;
  columns and axis labels `gap-2` (8 px); a value sits 4 px over its bar.
- Separate groups with space first and a `border` hairline second, never a
  filled band; Dalco's lists are rows divided by hairlines.
- The footer pulls up 8 px (`-mt-2`) so it belongs to the chart above it.
- The plot keeps a fixed height (≈ 209 px) and scrolls sideways when columns
  would narrow below 96 px (the width a mono `Koprivničko-` needs) — it never
  squeezes labels into illegibility.
- The view shows the top N items; an `ExpandButton` in the header reveals
  all of them. Counts of hidden items go in the footer.
- Dense facts (stat tiles, job conditions) sit on `surface-sunken` tiles
  with a `10px` radius and no border, like Dalco's spec panels.

## Interaction

- **Hover previews, click commits.** Pointer hover makes an item active and
  updates the readout; leaving the plot falls back to the selection.
- **Text links and pills roll.** On hover a label slides up and an identical
  copy slides in from below (Dalco's nav and buttons); colour changes take
  300 ms. Reduced motion swaps the colour only.
- **Keyboard:** items are buttons in a roving tab order (`tabIndex` 0 only on
  the selected one), `←`/`→`/`↑`/`↓`/`Home`/`End` move the selection, and
  `aria-pressed` marks it. The focus ring is `shadow-focus` (`accent-500` at
  40 %) on a 12 px radius, inset 4 px around the item.
- **Accessible names carry the data:** each item's `aria-label` states the
  name and every value the readout shows; decorative SVG is `aria-hidden`.
  Uppercase is CSS (`text-transform`), never typed, so screen readers read
  words, not letters.
- Controls are shadcn primitives restyled as pills: `ghost` for chart items,
  outline pill for card actions, `default` (black `surface-muted` pill) for
  the one primary action.

## Motion

Recharts draws the marks in (`animationBegin`/`animationDuration` from the
`marks` row below) and morphs them to new data; GSAP, through the helpers
in `hooks/chart-motion.ts`, moves everything else: the card frame, readout,
labels and counting numbers. Every view is animated: `Card` plays the frame's
entrance (header, notes, sources, footers and parts a view marks with
`data-enter`), and each view animates its own content. Dalco moves fast and
in sequence, so durations are short and staggers tight; easing is `outExpo`
for arrivals, `inQuad` for exits, `outBack` only for the pill pop.

| Moment | What moves | Timing |
| --- | --- | --- |
| Entrance | card header (eyebrow, title, description, actions) rises in, staggered 60 ms | 500 ms at 0 ms |
| | readout, filters and warnings above the content fade in, rising 6 px, staggered 60 ms | 500 ms at 100 ms |
| | headline number counts up from 0 | 1200 ms at 150 ms |
| | Recharts draws the marks in: columns grow from their feet, lines and the ring sweep in | 900 ms from 250 ms |
| | axis and legend labels fade in, rising 4 px, staggered 20 ms per label | 400 ms at 350 ms |
| | sources, footers and notes under the content rise in, staggered 60 ms | 500 ms at 1150 ms |
| New focus | the pill moves to the new item by cross-fading | 300 ms CSS |
| | readout label rolls to the new name; number counts to the new value | 250 ms / 600 ms |
| | lit and grey looks cross-fade | 300 ms CSS |
| Hover | link or pill label rolls up, letters staggered 20 ms | 250 ms `ease-in` |
| New data | Recharts morphs every shape from the size on screen | 900 ms |

Rules: animate from what is on screen, never jump back to zero on an update;
wrap every GSAP animation in `finish()` so hidden host frames still reach
the end state (Recharts plays its marks once the frame shows); `prefers-reduced-motion` skips straight to the final state; release
inline styles when an animation ends so the stylesheet applies again.

## Moving from the orange style

| Area | Today | Target |
| --- | --- | --- |
| Tokens | `orange-100/300/500`, `orange-wash`; zinc greys | rename to `accent-*` and `accent-wash` with the red values above; neutral greys from the colour table |
| Fonts | Inter only | Geist + Geist Mono, self-hosted and inlined by the build |
| Labels | 12 px sans `fg-soft` | 12 px uppercase mono with `+0.04em` tracking; headline number in mono |
| Cards | no eyebrow | one `●` eyebrow per card naming the view |
| Buttons | shadcn defaults (`rounded-md`) | fully rounded pills; outline pill with `›` for secondary actions |
| Hover | colour change | roll-up label plus colour change on links and pills |
| Motion | 600–1400 ms, 70–80 ms staggers | shorter durations and tighter staggers from the motion table |

## Checklist for a new or changed view

- [ ] Only tokens from `tailwind.css`; no hex values in components.
- [ ] At most one red datum at a time; everything else grey.
- [ ] One eyebrow, then a readout (mono context line + 28 px mono number)
      above the chart that follows focus.
- [ ] Text sizes are 28, 16, 14 or 12 px; mono for data labels and numbers,
      sans for prose and titles; uppercase only on mono labels that are not
      names.
- [ ] Buttons and pills are fully rounded; cards and tiles 10 px.
- [ ] Hover previews, click/keys select, focus ring visible, `aria-label`
      carries the values.
- [ ] Entrance and updates animate from what is on screen; reduced motion
      shows the end state.
- [ ] Checked in light and dark (`data-theme="dark"`) and at narrow width.
