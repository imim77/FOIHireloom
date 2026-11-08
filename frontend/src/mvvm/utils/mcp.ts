import type { App } from '@modelcontextprotocol/ext-apps'

export const embedded = window.parent !== window

export function openLink(app: App | null, url: string) {
  if (app) void app.openLink({ url }).catch(() => window.open(url, '_blank', 'noopener'))
  else window.open(url, '_blank', 'noopener')
}

export const canSendMessage = (app: App | null): app is App => Boolean(app?.getHostCapabilities()?.message)
