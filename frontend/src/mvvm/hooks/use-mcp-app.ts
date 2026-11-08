import { App, type McpUiHostContext } from '@modelcontextprotocol/ext-apps'
import { useEffect, useState } from 'react'
import { embedded } from '../utils/mcp'

export interface McpApp<T> {
  app: App | null
  data: T | null
  revision: number
  hostContext: McpUiHostContext
}

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
