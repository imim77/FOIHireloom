import { Button } from './ui/button'
import { RollLabel } from './RollLabel'
import type { ReactNode } from 'react'
import type { SourceLink } from '../types'

/** "Izvori: HZZ …, DZS …" with each source opened through the host, then any other facts, e.g. when DZS was read. */
export function Sources({ onOpenLink, links, children }: {
  onOpenLink: (url: string) => void
  links: SourceLink[]
  children?: ReactNode
}) {
  if (!links.length && !children) return null
  // DESIGN.md's footer line: uppercase mono, which the links inherit.
  return (
    <p className="sources flex flex-wrap [gap:4px_12px] m-0 [padding:0_12px] mono-label uppercase text-fg-soft">
      {links.length > 0 && (
        <span>
          {links.length > 1 ? 'Izvori: ' : 'Izvor: '}
          {links.map((link, i) => (
            <span key={link.label}>
              {i > 0 && ', '}
              {link.url ? (
                <Button type="button" variant="link" size="xs" className="link h-auto p-0 whitespace-normal text-left font-normal uppercase text-fg-loud" title={link.url} onClick={() => onOpenLink(link.url!)}>
                  <RollLabel>{link.label}</RollLabel>
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
