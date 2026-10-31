// HZZ writes most values in capitals and with every option it allows; these turn them into the card's short labels.

import { formatWorkers, plural } from '../../shared/format'
import type { JobCard } from './types'

/** "PRODAVAČ/PRODAVAČICA" → "Prodavač/prodavačica"; text that is not all capitals stays. */
export function sentenceCase(text: string): string {
  if (text !== text.toUpperCase()) return text
  const lower = text.toLocaleLowerCase('hr-HR')
  return lower.charAt(0).toLocaleUpperCase('hr-HR') + lower.slice(1)
}

/** "PULA-POLA" → "Pula-Pola": a place name keeps a capital on each word. */
export function titleCase(text: string): string {
  return text.toLocaleLowerCase('hr-HR').replace(/(^|[\s\-/(])(\p{L})/gu,
    (_, before: string, letter: string) => before + letter.toLocaleUpperCase('hr-HR'))
}

const day = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10))
/** Whole days from one ISO date to another. */
export const daysBetween = (from: string, to: string) => Math.round((day(to) - day(from)) / 86_400_000)

/** "15. 11." */
export const shortDate = (iso: string) => `${+iso.slice(8, 10)}. ${+iso.slice(5, 7)}.`

export function published(job: JobCard, today: string): string {
  if (!job.published_on) return 'Datum objave nije naveden'
  const days = daysBetween(job.published_on, today)
  if (days <= 0) return 'Objavljeno danas'
  if (days === 1) return 'Objavljeno jučer'
  return `Objavljeno prije ${days} ${plural(days, 'dan', 'dana', 'dana')}`
}

export function deadline(job: JobCard): string {
  if (!job.deadline_on) return 'Rok prijave nije naveden'
  return job.deadline_passed ? `Rok prijave istekao ${shortDate(job.deadline_on)}` : `Prijave do ${shortDate(job.deadline_on)}`
}

/** The town of work: "ČAZMA, BJELOVARSKO-BILOGORSKA ŽUPANIJA" → "Čazma"; null when HZZ named only the county. */
export function town(job: JobCard): string | null {
  if (!job.work_place && /mjesto rada nije navedeno/i.test(job.display_location)) return null
  const place = (job.work_place ?? job.display_location).split(',')[0].trim()
  return place === place.toUpperCase() ? titleCase(place) : place
}

/** The line under the employer: category and county, as they are known. */
export function subtitle(job: JobCard): string {
  return [job.category && sentenceCase(job.category), job.county_name].filter(Boolean).join(' · ')
    || 'Hrvatski zavod za zapošljavanje'
}

export type ChipTone = 'plain' | 'workers' | 'perk'

export interface Chip {
  text: string
  tone: ChipTone
}

/** The card's labels, most telling first; the highlighted ones say how many are sought and what comes with the job. */
export function chips(job: JobCard): Chip[] {
  const first = (value: string | null) => value?.split(';')[0].trim() || null
  const experience = job.experience === 'Nije važno' ? 'Bez traženog iskustva'
    : job.experience ? `Iskustvo ${job.experience}` : null
  const accommodation = job.accommodation && job.accommodation !== 'Nema smještaja' ? job.accommodation : null
  return [
    { text: town(job), tone: 'plain' as const },
    { text: first(job.employment_type), tone: 'plain' as const },
    { text: job.working_hours, tone: 'plain' as const },
    { text: first(job.education), tone: 'plain' as const },
    { text: experience, tone: 'plain' as const },
    { text: job.workers_needed && job.workers_needed > 1 ? formatWorkers(job.workers_needed) : null, tone: 'workers' as const },
    { text: accommodation, tone: 'perk' as const },
  ].filter((chip): chip is Chip => Boolean(chip.text))
}
