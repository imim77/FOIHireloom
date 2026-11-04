import { App, type McpUiHostContext } from '@modelcontextprotocol/ext-apps'
import { useEffect, useState } from 'react'

// Outside a host, e.g. on the Vite dev server, a view shows its sample data instead.
export const embedded = window.parent !== window

export interface McpApp<T> {
  app: App | null
  // The tool's structuredContent; null until the host sends it.
  data: T | null
  // Each host result starts a fresh interaction session, even with equal data.
  revision: number
  hostContext: McpUiHostContext
}

/** Connect to the host once, follow its theme and hold the latest tool result. */
export function useMcpApp<T>(name: string, sample: () => T): McpApp<T> {
  const [result, setResult] = useState(() => ({ data: embedded ? null : sample(), revision: 0 }))
  const [hostContext, setHostContext] = useState<McpUiHostContext>({})
  const [app, setApp] = useState<App | null>(null)

  useEffect(() => {
    if (!embedded) return
    let active = true
    const app = new App({ name, version: '1.0.0' }, { availableDisplayModes: ['inline', 'fullscreen'] },
      { autoResize: true })
    app.ontoolresult = ({ structuredContent }) => {
      if (active && structuredContent) {
        setResult((previous) => ({ data: structuredContent as T, revision: previous.revision + 1 }))
      }
    }
    app.onhostcontextchanged = (context) => {
      if (active) setHostContext((previous) => ({ ...previous, ...context }))
    }
    void app.connect().then(() => {
      if (!active) return
      setHostContext(app.getHostContext() ?? {})
      setApp(app)
    }).catch((error: unknown) => {
      if (active) console.error('MCP host connection failed', error)
    })
    return () => {
      active = false
      void app.close()
    }
  }, [name])

  useEffect(() => {
    if (hostContext.theme) document.documentElement.dataset.theme = hostContext.theme
  }, [hostContext.theme])

  return { app, ...result, hostContext }
}

/** Open a link through the host, which may ask the user first; in a browser, or when the host fails, a new tab. */
export function openLink(app: App | null, url: string) {
  if (app) void app.openLink({ url }).catch(() => window.open(url, '_blank', 'noopener'))
  else window.open(url, '_blank', 'noopener')
}

/** Whether the host takes messages from the view, which it sends as the user's (app.sendMessage). */
export const canSendMessage = (app: App | null): app is App => Boolean(app?.getHostCapabilities()?.message)

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
