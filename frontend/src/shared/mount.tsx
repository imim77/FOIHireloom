import type { ComponentType } from 'react'
import { createRoot } from 'react-dom/client'
import './theme.css'

/** Render a view into the page's #root. */
export function mount(View: ComponentType) {
  createRoot(document.getElementById('root')!).render(<View />)
}
