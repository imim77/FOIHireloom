import { Component, type ErrorInfo, type ReactNode } from 'react'

interface CardProps {
  title: string
  description: string
  // Buttons at the end of the header, e.g. <ExpandButton>.
  actions?: ReactNode
  children?: ReactNode
  // The Performance chart's card: a grey card around a white panel that holds the content (tiles go in it).
  sunken?: boolean
}

export function Card({ title, description, actions, children, sunken = false }: CardProps) {
  const content = (
    <>
      <div className="header flex items-center gap-3 min-w-0">
        <div className="titles flex flex-1 flex-col gap-1.5 min-w-0">
          <p className="title truncate m-0 text-[16px] font-semibold leading-[1.25] overflow-hidden whitespace-nowrap text-ellipsis">{title}</p>
          <p className="soft truncate m-0 text-[12px] font-medium leading-[1.25] text-fg-soft overflow-hidden whitespace-nowrap text-ellipsis">{description}</p>
        </div>
        {actions}
      </div>
      <ErrorBoundary>
        <div className="body flex flex-col gap-6 [&:empty]:hidden">{children}</div>
      </ErrorBoundary>
    </>
  )
  return (
    <div className={`card flex flex-col gap-6 p-5 bg-card text-fg-loud border border-border rounded-[20px] [&.sunken]:gap-2
      [&.sunken]:p-2 [&.sunken]:rounded-[28px] [&.sunken]:bg-surface-sunken
      [&:has(.accommodation-comparison)_>_.header_.soft]:whitespace-normal
      [&:has(.accommodation-comparison)_>_.header_.soft]:overflow-visible ${sunken ? ' sunken' : ''}`} role="group" aria-label={title}>
      {sunken ? <div className="panel flex flex-col gap-5 p-3 rounded-[20px] bg-card">{content}</div> : content}
    </div>
  )
}

export function Warning({ text }: { text: string | null | undefined }) {
  return text ? <p className="warning m-0 [padding:10px_12px] rounded-[12px] text-[12px] leading-[1.4] bg-warning-bg text-warning-fg">{text}</p> : null
}

type Text = string | null | undefined

/** How current the data is, as a warning, and under it one or more quieter notes; nothing when all are empty. */
export function Notes({ warning, note }: { warning: Text; note: Text | Text[] }) {
  const notes = (Array.isArray(note) ? note : [note]).filter((text): text is string => Boolean(text))
  if (!warning && !notes.length) return null
  return (
    <div className="notes flex flex-col gap-2 animate-fade-in motion-reduce:[animation:none]">
      <Warning text={warning} />
      {notes.map((text) => <p key={text} className="note m-0 [padding:0_12px] text-[12px] leading-[1.4] text-fg-soft">{text}</p>)}
    </div>
  )
}

const EXPAND = ['M15 3h6v6', 'M9 21H3v-6', 'M21 3l-7 7', 'M3 21l7-7']
const COLLAPSE = ['M4 14h6v6', 'M20 10h-6V4', 'M14 10l7-7', 'M3 21l7-7']

export function ExpandButton({ expanded, label, onClick }: { expanded: boolean; label: string; onClick: () => void }) {
  return (
    <button className="icon-button grid place-items-center flex-none w-9 h-9 p-0 rounded-[10px] border border-border bg-card
      text-fg-loud cursor-pointer [&:hover]:bg-surface-subdued [&:focus-visible]:[outline:none]
      [&:focus-visible]:shadow-focus [&_svg]:w-4.5 [&_svg]:h-4.5" type="button" title={label} aria-label={label} onClick={onClick}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
        strokeLinejoin="round">
        {(expanded ? COLLAPSE : EXPAND).map((d) => <path key={d} d={d} />)}
      </svg>
    </button>
  )
}

// A failure shows in the card instead of leaving it empty.
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (error) return <p className="warning m-0 [padding:10px_12px] rounded-[12px] text-[12px] leading-[1.4] bg-warning-bg text-warning-fg">Graf se nije mogao prikazati: {error.message}</p>
    return this.props.children
  }
}
