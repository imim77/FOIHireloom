import { Button } from './ui/button'
import type { ReactNode } from 'react'
import type { SourceLink } from '../types'

/** "Izvori: HZZ …, DZS …" with each source opened through the host, then any other facts, e.g. when DZS was read. */
export function Sources({ onOpenLink, links, children }: {
  onOpenLink: (url: string) => void
  links: SourceLink[]
  children?: ReactNode
}) {
  if (!links.length && !children) return null
  return (
    <p className="sources flex flex-wrap [gap:4px_12px] m-0 [padding:0_12px] text-[12px] font-medium leading-[1.25] text-fg-soft">
      {links.length > 0 && (
        <span>
          {links.length > 1 ? 'Izvori: ' : 'Izvor: '}
          {links.map((link, i) => (
            <span key={link.label}>
              {i > 0 && ', '}
              {link.url ? (
                <Button type="button" variant="link" size="xs" className="link h-auto p-0" title={link.url} onClick={() => onOpenLink(link.url!)}>
                  {link.label}
                </Button>
              ) : link.label}
            </span>
          ))}
        </span>
      )}
      {children}
    </p>
  )
}
