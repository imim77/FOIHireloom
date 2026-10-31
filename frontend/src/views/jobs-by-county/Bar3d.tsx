// One 3D column drawn once (48 × 188.921) and stretched to each bar's height: two faces, a lid and white edges.
// The grey look shows for other counties, the lit (orange) one for the active county.

export const BAR_VIEW = '0 0 48 188.921'
const RIGHT = 'M23.9683 15.685L47.0527 8.2763V181.04L23.9683 188.449Z'
const LID = 'M23.9672 0.0161L47.7527 8.05164L23.9672 15.6854L0.181641 8.05164Z'
const LEFT = 'M0.881216 8.2758L23.9672 15.6849V188.449L0.881216 180.6494Z'
const EDGES = [
  'M23.6187 15.6855h0.699575v172.764h-0.699575Z',
  'M23.9683 16.4893L23.9684 15.6856L47.7527 8.05167L47.7527 8.8553Z',
  'M24.1562 16.4884L24.1561 15.6847L0.181752 8.05066L0.181702 8.85444Z',
  'M23.9683 0.0161L23.9684 0.81981L47.7527 8.4537L47.7527 7.65007Z',
  'M24.1562 0.016L24.1561 0.81974L0.181752 8.45374L0.181702 7.64996Z',
  'M24.1994 188.618C23.8191 188.744 23.4483 188.47 23.4484 188.063L47.7536 180.011L47.7536 180.815Z',
  'M23.5824 188.628C23.966 188.749 24.3359 188.472 24.3359 188.063L0.180678 180.413L0.18066 181.217Z',
].join('')

export function BarLook({ lit, opacity }: { lit: boolean; opacity: number }) {
  const look = lit ? 'lit' : 'grey'
  return (
    <g className="look" style={{ opacity }}>
      <path d={RIGHT} fill={`url(#${look}-right)`} />
      <path d={LID} style={{ fill: `var(${lit ? '--orange-100' : '--surface-subdued'})` }} />
      <path d={LEFT} fill={`url(#${look}-left)`} />
      <path d={EDGES} style={{ fill: 'var(--card)' }} />
    </g>
  )
}

function Gradient({ id, x1, y1, x2, y2, from, to }: Record<'id' | 'x1' | 'y1' | 'x2' | 'y2' | 'from' | 'to', string>) {
  return (
    <linearGradient id={id} gradientUnits="userSpaceOnUse" x1={x1} y1={y1} x2={x2} y2={y2}>
      <stop style={{ stopColor: `var(${from})` }} />
      <stop offset="1" style={{ stopColor: `var(${to})` }} />
    </linearGradient>
  )
}

/** The face gradients every BarLook refers to; render once per page. */
export function BarGradients() {
  return (
    <svg aria-hidden="true" width="0" height="0" style={{ position: 'absolute' }}>
      <defs>
        <Gradient id="grey-right" x1="35.8613" y1="8.0502" x2="35.8613" y2="188.448" from="--surface-disable" to="--surface-subdued" />
        <Gradient id="grey-left" x1="23.9673" y1="0" x2="0.181152" y2="0" from="--surface-disable" to="--surface-subdued" />
        <Gradient id="lit-right" x1="23.9683" y1="0" x2="47.7538" y2="0" from="--orange-100" to="--orange-300" />
        <Gradient id="lit-left" x1="23.9672" y1="0" x2="0.181641" y2="0" from="--orange-100" to="--orange-300" />
      </defs>
    </svg>
  )
}
