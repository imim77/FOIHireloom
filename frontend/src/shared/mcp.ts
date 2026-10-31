import { App, type McpUiHostContext } from '@modelcontextprotocol/ext-apps'
import { useEffect, useState } from 'react'

// Outside a host, e.g. on the Vite dev server, a view shows its sample data instead.
export const embedded = window.parent !== window

export interface McpApp<T> {
  app: App | null
  // The tool's structuredContent; null until the host sends it.
  data: T | null
  // Counts the results received, so a view can key its animations to each new one.
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
    const app = new App({ name, version: '1.0.0' }, { availableDisplayModes: ['inline', 'fullscreen'] },
      { autoResize: true })
    app.ontoolresult = ({ structuredContent }) => {
      if (structuredContent) {
        setResult((previous) => ({ data: structuredContent as T, revision: previous.revision + 1 }))
      }
    }
    app.onhostcontextchanged = (context) => setHostContext((previous) => ({ ...previous, ...context }))
    void app.connect().then(() => {
      setHostContext(app.getHostContext() ?? {})
      setApp(app)
    })
  }, [name])

  useEffect(() => {
    if (hostContext.theme) document.documentElement.dataset.theme = hostContext.theme
  }, [hostContext.theme])

  return { app, ...result, hostContext }
}

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
