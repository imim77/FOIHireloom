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
      <div className="header">
        <div className="titles">
          <p className="title truncate">{title}</p>
          <p className="soft truncate">{description}</p>
        </div>
        {actions}
      </div>
      <ErrorBoundary>
        <div className="body">{children}</div>
      </ErrorBoundary>
    </>
  )
  return (
    <div className={`card${sunken ? ' sunken' : ''}`} role="group" aria-label={title}>
      {sunken ? <div className="panel">{content}</div> : content}
    </div>
  )
}

export function Warning({ text }: { text: string | null | undefined }) {
  return text ? <p className="warning">{text}</p> : null
}

/** How current the data is, as a warning, and under it a quieter note; nothing when both are empty. */
export function Notes({ warning, note }: { warning: string | null | undefined; note: string | null | undefined }) {
  if (!warning && !note) return null
  return (
    <div className="notes">
      <Warning text={warning} />
      {note && <p className="note">{note}</p>}
    </div>
  )
}

const EXPAND = ['M15 3h6v6', 'M9 21H3v-6', 'M21 3l-7 7', 'M3 21l7-7']
const COLLAPSE = ['M4 14h6v6', 'M20 10h-6V4', 'M14 10l7-7', 'M3 21l7-7']

export function ExpandButton({ expanded, label, onClick }: { expanded: boolean; label: string; onClick: () => void }) {
  return (
    <button className="icon-button" type="button" title={label} aria-label={label} onClick={onClick}>
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
    if (error) return <p className="warning">Graf se nije mogao prikazati: {error.message}</p>
    return this.props.children
  }
}
