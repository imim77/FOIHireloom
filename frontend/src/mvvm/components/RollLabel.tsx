import { Fragment } from 'react'
import { cn } from 'cn'

const STAGGER = 20 // ms between letters
const LETTER = 'inline-block whitespace-pre motion-safe:[transition:translate_250ms_ease-in]'
// Spelled out for Tailwind's scanner. The enclosing button or link is the hover target, so the whole pill rolls it.
const OUTGOING = 'motion-safe:[:is(button,a):hover_&]:-translate-y-full'
const INCOMING = 'translate-y-full motion-safe:[:is(button,a):hover_&]:translate-y-0'

/**
 * RollLabel rolls its text up when the enclosing button or link is hovered while an identical copy slides in from
 * below, as on Dalco's nav and buttons; with reduced motion only the colour changes. Both rolling copies are
 * aria-hidden and a visually hidden copy carries the text, so screen readers read the label once and as words rather
 * than letter by letter. Each word rolls in its own clipped box, so a long label (a source's name in the footer)
 * wraps between words when its parent allows wrapping.
 */
export function RollLabel({ children, className }: { children: string; className?: string }) {
  const words = children.split(' ')
  // Where each word starts in the label, so the letters' stagger runs on across words.
  const starts = words.map((_, w) => words.slice(0, w).reduce((sum, word) => sum + word.length + 1, 0))
  return (
    <span className={cn('roll relative', className)}>
      <span className="sr-only">{children}</span>
      {words.map((word, w) => (
        <Fragment key={w}>
          {w > 0 && <span aria-hidden="true"> </span>}
          <RollWord word={word} start={starts[w]} />
        </Fragment>
      ))}
    </span>
  )
}

function RollWord({ word, start }: { word: string; start: number }) {
  const letters = [...word]
  const copy = (incoming: boolean) => (
    <span aria-hidden="true" className="col-start-1 row-start-1">
      {letters.map((letter, i) => (
        <span key={i} style={{ transitionDelay: `${(start + i) * STAGGER}ms` }}
          className={cn(LETTER, incoming ? INCOMING : OUTGOING)}>{letter}</span>
      ))}
    </span>
  )
  // overflow: clip, not hidden, keeps the text baseline, so the word still lines up with the text around it.
  return (
    <span className="relative inline-grid overflow-clip">
      {copy(false)}
      {copy(true)}
    </span>
  )
}
