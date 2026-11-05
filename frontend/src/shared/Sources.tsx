import type { App } from '@modelcontextprotocol/ext-apps'
import type { ReactNode } from 'react'
import { openLink } from './mcp'
import type { SourceLink } from './types'

/** "Izvori: HZZ …, DZS …" with each source opened through the host, then any other facts, e.g. when DZS was read. */
export function Sources({ app, links, children }: { app: App | null; links: SourceLink[]; children?: ReactNode }) {
  if (!links.length && !children) return null
  return (
    <p className="sources flex flex-wrap [gap:4px_12px] m-0 [padding:0_12px] text-[12px] leading-[1.4] text-fg-soft">
      {links.length > 0 && (
        <span>
          {links.length > 1 ? 'Izvori: ' : 'Izvor: '}
          {links.map((link, i) => (
            <span key={link.label}>
              {i > 0 && ', '}
              {link.url ? (
                <button type="button" className="link inline p-0 [border:0] [background:none] [font-family:inherit] text-[inherit]
                  [font-weight:inherit] [font-style:inherit] leading-[inherit] text-fg-loud underline
                  [text-decoration-color:var(--surface-disable)] [text-underline-offset:2px] cursor-pointer
                  text-left [&:hover]:[text-decoration-color:currentColor] [&:focus-visible]:[outline:none]
                  [&:focus-visible]:rounded-[4px] [&:focus-visible]:shadow-focus" title={link.url} onClick={() => openLink(app, link.url!)}>
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
