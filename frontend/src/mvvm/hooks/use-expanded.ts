import { useState } from 'react'
import type { McpApp } from './use-mcp-app'

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
      }
    }
    setInline(!expanded)
  }

  return { expanded, toggle }
}
