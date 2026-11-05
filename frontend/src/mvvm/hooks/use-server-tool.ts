import type { App } from '@modelcontextprotocol/ext-apps'
import { useEffect, useRef, useState } from 'react'

/** useServerTool runs one request at a time and discards replies after unmount. */
export function useServerTool<T>(app: App | null, name: string, failureMessage: string) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pending = useRef(false)
  const active = useRef(false)

  useEffect(() => {
    active.current = true
    return () => { active.current = false }
  }, [])

  async function call(arguments_: Record<string, unknown>): Promise<T | null> {
    if (!app || pending.current || !active.current) return null
    pending.current = true
    setLoading(true)
    setError(null)
    try {
      const result = await app.callServerTool({ name, arguments: arguments_ })
      if (result.isError || !result.structuredContent) throw new Error(failureMessage)
      return active.current ? result.structuredContent as T : null
    } catch (failure) {
      if (active.current) setError(failure instanceof Error ? failure.message : String(failure))
      return null
    } finally {
      pending.current = false
      if (active.current) setLoading(false)
    }
  }

  return { call, loading, error, setError }
}
