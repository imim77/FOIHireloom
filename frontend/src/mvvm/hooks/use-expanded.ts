import { useState } from 'react'
import type { McpApp } from './use-mcp-app'

/**
 * Whether a view shows everything: full screen when the host offers it, otherwise inline.
 * Leaving full screen from the host's own controls collapses the view again.
 */
export function useExpanded({ app, hostContext }: Pick<McpApp<unknown>, 'app' | 'hostContext'>) {
  const [inline, setInline] = useState(false)
  const expanded = hostContext.displayMode === 'fullscreen' || inline

  async function toggle() {
    const mode = expanded ? 'inline' : 'fullscreen'
    setInline(false)
    if (app && hostContext.availableDisplayModes?.includes(mode)) {
      try {
        await app.requestDisplayMode({ mode })
        return
      } catch {
        // The host refused; fall back to showing everything inline.
      }
    }
    setInline(!expanded)
  }

  return { expanded, toggle }
}
