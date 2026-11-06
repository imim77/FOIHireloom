import type { App } from '@modelcontextprotocol/ext-apps'

// Outside a host, e.g. on the Vite dev server, a view shows its sample data instead.
export const embedded = window.parent !== window

/** Open a link through the host, which may ask the user first; in a browser, or when the host fails, a new tab. */
export function openLink(app: App | null, url: string) {
  if (app) void app.openLink({ url }).catch(() => window.open(url, '_blank', 'noopener'))
  else window.open(url, '_blank', 'noopener')
}

/** Whether the host takes messages from the view, which it sends as the user's (app.sendMessage). */
export const canSendMessage = (app: App | null): app is App => Boolean(app?.getHostCapabilities()?.message)
