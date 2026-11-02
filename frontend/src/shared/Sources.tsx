import type { App } from '@modelcontextprotocol/ext-apps'
import type { ReactNode } from 'react'
import { openLink } from './mcp'
import type { SourceLink } from './types'

/** "Izvori: HZZ …, DZS …" with each source opened through the host, then any other facts, e.g. when DZS was read. */
export function Sources({ app, links, children }: { app: App | null; links: SourceLink[]; children?: ReactNode }) {
  if (!links.length && !children) return null
  return (
    <p className="sources">
      {links.length > 0 && (
        <span>
          {links.length > 1 ? 'Izvori: ' : 'Izvor: '}
          {links.map((link, i) => (
            <span key={link.label}>
              {i > 0 && ', '}
              {link.url ? (
                <button type="button" className="link" title={link.url} onClick={() => openLink(app, link.url!)}>
                  {link.label}
                </button>
              ) : link.label}
            </span>
          ))}
        </span>
      )}
      {children}
    </p>
  )
}
