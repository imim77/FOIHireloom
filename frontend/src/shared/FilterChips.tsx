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
    <ul className="filters" aria-label={label}>
      {filters.map((filter) => (
        <li key={filter.argument} className="filter">
          <span>{capitalise(filter.label)}</span>
          {onRemove && (
            <button className="filter-remove" type="button" disabled={disabled}
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
