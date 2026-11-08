import { Fragment } from 'react'
import { cn } from 'cn'

const STAGGER = 20
const LETTER = 'inline-block whitespace-pre motion-safe:[transition:translate_250ms_ease-in]'
const OUTGOING = 'motion-safe:[:is(button,a):hover_&]:-translate-y-full'
const INCOMING = 'translate-y-full motion-safe:[:is(button,a):hover_&]:translate-y-0'

export function RollLabel({ children, className }: { children: string; className?: string }) {
  const words = children.split(' ')
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
  return (
    <span className="relative inline-grid overflow-clip">
      {copy(false)}
      {copy(true)}
    </span>
  )
}
