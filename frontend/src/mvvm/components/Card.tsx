import { Component, type ErrorInfo, type ReactNode, useRef } from 'react'
import { cn } from 'cn'
import { Maximize2Icon, Minimize2Icon, TriangleAlertIcon } from 'lucide-react'
import { Alert, AlertDescription } from './ui/alert'
import { Button } from './ui/button'
import { Card as SurfaceCard, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Empty, EmptyDescription, EmptyHeader } from './ui/empty'
import { Skeleton } from './ui/skeleton'
import { clearEntrance, enter, MOTION, useChartEntrance } from '../hooks/chart-motion'

const FRAME = '.notes, .warning, .sources, .footer, [data-enter]'

interface CardProps {
  eyebrow?: string
  title: string
  description: string
  actions?: ReactNode
  children?: ReactNode
  loading?: boolean
}

export function Card({ eyebrow, title, description, actions, children, loading = false }: CardProps) {
  const root = useRef<HTMLDivElement>(null)
  useChartEntrance(root, (timeline) => {
    const card = root.current!
    const header = [...card.querySelectorAll('[data-slot="eyebrow"], [data-slot="card-title"], '
      + '[data-slot="card-description"], [data-slot="card-action"]')]
    const parts = [...card.querySelectorAll(FRAME)].filter((el) => !el.parentElement?.closest(FRAME))
    const body = card.querySelector('[data-slot="card-content"]')
    const content = [...body?.querySelectorAll('*') ?? []].find((el) =>
      !el.closest(FRAME) && !el.querySelector(FRAME))
    const above = parts.filter((el) => !content
      || Boolean(el.compareDocumentPosition(content) & Node.DOCUMENT_POSITION_FOLLOWING))
    const below = parts.filter((el) => !above.includes(el))
    enter(timeline, header, 0, MOTION.readout)
    enter(timeline, above, MOTION.readout.at + MOTION.readout.stagger, MOTION.readout)
    enter(timeline, below, MOTION.frame, MOTION.readout)
    return () => clearEntrance([...header, ...parts])
  }, !loading)
  return (
    <SurfaceCard className="card min-w-0" role="group" aria-label={title} aria-busy={loading}
      ref={root}>
      {                                                                                              }
      <CardHeader className={cn('header flex min-w-0 gap-3', eyebrow ? 'items-start' : 'items-center')}>
        <div className="titles flex min-w-0 flex-1 flex-col gap-1.5">
          {eyebrow && <Eyebrow text={eyebrow} />}
          <CardTitle className="title">{title}</CardTitle>
          <CardDescription className="soft">{description}</CardDescription>
        </div>
        {actions && <CardAction>{actions}</CardAction>}
      </CardHeader>
      <ErrorBoundary>
        <CardContent className="body flex min-w-0 flex-col gap-6">
          {loading ? <div className="flex flex-col gap-3" aria-hidden="true">
            <Skeleton className="h-5 w-2/3 motion-reduce:animate-none" />
            <Skeleton className="h-24 w-full motion-reduce:animate-none" />
          </div> : children}
        </CardContent>
      </ErrorBoundary>
    </SurfaceCard>
  )
}

function Eyebrow({ text }: { text: string }) {
  return <p className="eyebrow m-0 mb-1 flex items-center gap-2 mono-label uppercase text-fg-soft" data-slot="eyebrow">
    <span className="size-1.5 flex-none rounded-full bg-accent-500" aria-hidden="true" />{text}
  </p>
}

export function Warning({ text }: { text: string | null | undefined }) {
  return text ? <Alert variant="warning" className="warning">
    <TriangleAlertIcon aria-hidden="true" />
    <AlertDescription>{text}</AlertDescription>
  </Alert> : null
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <Empty className="empty" role="status">
    <EmptyHeader><EmptyDescription>{children}</EmptyDescription></EmptyHeader>
  </Empty>
}

type Text = string | null | undefined

export function Notes({ warning, note }: { warning: Text; note: Text | Text[] }) {
  const notes = (Array.isArray(note) ? note : [note]).filter((text): text is string => Boolean(text))
  if (!warning && !notes.length) return null
  return <div className="notes flex flex-col gap-2">
    <Warning text={warning} />
    {notes.map((text) => <p key={text} className="note m-0 text-xs leading-relaxed text-muted-foreground">{text}</p>)}
  </div>
}

export function ExpandButton({ expanded, label, onClick }: { expanded: boolean; label: string; onClick: () => void }) {
  const Icon = expanded ? Minimize2Icon : Maximize2Icon
  return <Button className="icon-button" variant="outline" size="icon" type="button" title={label} aria-label={label} onClick={onClick}>
    <Icon data-icon="inline-start" aria-hidden="true" />
  </Button>
}

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) { return { error } }

  componentDidCatch(error: Error, info: ErrorInfo) { console.error(error, info.componentStack) }

  render() {
    const { error } = this.state
    if (error) return <Warning text={`Graf se nije mogao prikazati: ${error.message}`} />
    return this.props.children
  }
}
