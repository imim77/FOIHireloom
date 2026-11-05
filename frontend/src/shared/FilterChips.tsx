import { capitalise } from './text'
import type { ActiveFilter } from './types'

interface FilterChipsProps {
  filters: ActiveFilter[]
  label?: string
  disabled?: boolean
  onRemove?: (filter: ActiveFilter) => void
}

/** FilterChips shows active filters, with removal when the host allows it. */
export function FilterChips({ filters, label = 'Filtri', disabled = false, onRemove }: FilterChipsProps) {
  if (!filters.length) return null
  return (
    <ul className="filters flex flex-wrap gap-1.5 m-0 p-0 [list-style:none]" aria-label={label}>
      {filters.map((filter) => (
        <li key={filter.argument} className="filter inline-flex items-center gap-0.5 min-w-0 max-w-full [padding:4px_10px] rounded-full text-[12px]
          font-medium leading-[1.25] bg-surface-subdued text-fg-loud animate-fade-in [&_span]:min-w-0
          [&_span]:overflow-hidden [&_span]:whitespace-nowrap [&_span]:text-ellipsis
          [&:has(.filter-remove)]:pr-0.5 motion-reduce:[animation:none]">
          <span>{capitalise(filter.label)}</span>
          {onRemove && (
            <button className="filter-remove grid place-items-center flex-none w-5 h-5 p-0 [border:0] rounded-full
              [background:none] text-fg-soft cursor-pointer [&_svg]:w-3 [&_svg]:h-3
              [&:hover:not(:disabled)]:bg-card [&:hover:not(:disabled)]:text-fg-loud
              [&:focus-visible]:[outline:none] [&:focus-visible]:shadow-focus [&:disabled]:cursor-progress" type="button" disabled={disabled}
              title={`Ukloni filtar ${filter.label}`} aria-label={`Ukloni filtar ${filter.label}`}
              onClick={() => onRemove(filter)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                aria-hidden="true">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}
