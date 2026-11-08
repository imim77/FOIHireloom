import '../tailwind.css'
import type { ComponentType } from 'react'
import { createRoot } from 'react-dom/client'

export function mount(View: ComponentType) {
  createRoot(document.getElementById('root')!).render(<View />)
}
