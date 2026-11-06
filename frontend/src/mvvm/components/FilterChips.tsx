import { XIcon } from 'lucide-react'
import { capitalise } from '../utils/text'
import type { ActiveFilter } from '../types'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

interface FilterChipsProps {
  filters: ActiveFilter[]
  label?: string
  disabled?: boolean
  onRemove?: (filter: ActiveFilter) => void
}

/** FilterChips shows active filters, with removal when the host allows it. */
export function FilterChips({ filters, label = 'Filtri', disabled = false, onRemove }: FilterChipsProps) {
  if (!filters.length) return null
  return <ul className="filters m-0 flex list-none flex-wrap gap-1.5 p-0" aria-label={label}>
    {filters.map((filter) => <li key={filter.argument} className="min-w-0 max-w-full">
      <Badge variant="secondary" className="filter h-auto max-w-full gap-1">
        <span className="truncate">{capitalise(filter.label)}</span>
        {onRemove && <Button variant="ghost" size="icon-xs" className="filter-remove" type="button" disabled={disabled}
          title={`Ukloni filtar ${filter.label}`} aria-label={`Ukloni filtar ${filter.label}`} onClick={() => onRemove(filter)}>
          <XIcon data-icon="inline-start" aria-hidden="true" />
        </Button>}
      </Badge>
    </li>)}
  </ul>
}
