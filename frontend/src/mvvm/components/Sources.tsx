import { Button } from './ui/button'
import { RollLabel } from './RollLabel'
import type { ReactNode } from 'react'
import type { SourceLink } from '../types'

export function Sources({ onOpenLink, links, children }: {
  onOpenLink: (url: string) => void
  links: SourceLink[]
  children?: ReactNode
}) {
  if (!links.length && !children) return null
  return (
    <p className="sources flex flex-wrap [gap:4px_12px] m-0 [padding:0_12px] mono-label uppercase text-fg-soft">
      {links.length > 0 && (
        <span>
          {links.length > 1 ? 'Izvori: ' : 'Izvor: '}
          {links.map((link, i) => (
            <span key={link.label}>
              {i > 0 && ', '}
              {link.url ? (
                <Button type="button" variant="link" size="xs" className="link h-auto p-0 whitespace-normal text-left font-normal normal-case text-fg-loud" title={link.url} onClick={() => onOpenLink(link.url!)}>
                  <RollLabel>{link.label}</RollLabel>
                </Button>
              ) : <span className="normal-case">{link.label}</span>}
            </span>
          ))}
        </span>
      )}
      {children}
    </p>
  )
}
