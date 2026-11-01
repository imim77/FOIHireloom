// HZZ writes most values in capitals and with every option it allows; these turn them into the card's short labels.

import { formatWorkers, plural } from '../../shared/format'
import type { Contract, JobCard, JobConditions } from './types'

/** "PRODAVAČ/PRODAVAČICA" → "Prodavač/prodavačica"; text that is not all capitals stays. */
export function sentenceCase(text: string): string {
  if (text !== text.toUpperCase()) return text
  const lower = text.toLocaleLowerCase('hr-HR')
  return lower.charAt(0).toLocaleUpperCase('hr-HR') + lower.slice(1)
}

/** "županija istarska" → "Županija istarska": only the first letter changes. */
export const capitalise = (text: string) => text.charAt(0).toLocaleUpperCase('hr-HR') + text.slice(1)

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

/** How long ago the job was published, for the card's first label: "Danas", "Jučer", "Prije 5 dana". */
export function age(job: JobCard, today: string): string | null {
  if (!job.published_on) return null
  const days = daysBetween(job.published_on, today)
  if (days <= 0) return 'Danas'
  if (days === 1) return 'Jučer'
  return `Prije ${days} ${plural(days, 'dan', 'dana', 'dana')}`
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

// What a detail is about, which picks its icon.
export type DetailKind = 'place' | 'hours' | 'deadline' | 'contract' | 'education' | 'experience' | 'workers'
  | 'accommodation'

export interface Detail {
  kind: DetailKind
  text: string
}

const CONTRACTS: Record<Contract, string> = {
  permanent: 'Na neodređeno', fixed_term: 'Na određeno', other: 'Drugi oblici rada',
}
const ACCOMMODATION: Record<Exclude<NonNullable<JobConditions['accommodation']>, 'none'>, string> = {
  shared: 'Zajednički smještaj', single: 'Samački smještaj', family: 'Obiteljski stan',
}

/** "Bez iskustva", "Za pripravnike", "Iskustvo 18 mj." or, in whole years, "Iskustvo 2 godine". */
function experience(job: JobCard): string | null {
  const { experience_months: months, trainee } = job.conditions ?? {}
  if (trainee) return 'Za pripravnike'
  if (months === 0) return 'Bez iskustva'
  if (months && months % 12) return `Iskustvo ${months} mj.`
  if (months) return `Iskustvo ${months / 12} ${plural(months / 12, 'godina', 'godine', 'godina')}`
  if (job.experience === 'Nije važno') return 'Bez traženog iskustva'
  return job.experience ? `Iskustvo ${job.experience}` : null
}

/** "Puno radno vrijeme" or "Nepuno, 20 h tjedno"; the page's own words when they were not recognised. */
function workingTime(job: JobCard): string | null {
  const { full_time: full, weekly_hours: hours } = job.conditions ?? {}
  if (full == null) return job.working_hours
  if (hours) return `${full ? 'Puno' : 'Nepuno'}, ${hours} h tjedno`
  return full ? 'Puno radno vrijeme' : 'Nepuno radno vrijeme'
}

/**
 * The card's details, in the reference's three columns: where and when first, then what the job asks and offers.
 * Each uses the normalised conditions where known and the page's text otherwise, whose first part is the lowest
 * education level or the contract.
 */
export function details(job: JobCard): Detail[] {
  const first = (value: string | null) => value?.split(';')[0].trim() || null
  const conditions = job.conditions
  const contract = conditions?.contract ? CONTRACTS[conditions.contract] : first(job.employment_type)
  // No accommodation is the usual case and is not shown.
  const accommodation = conditions?.accommodation
    ? conditions.accommodation === 'none' ? null : ACCOMMODATION[conditions.accommodation]
    : job.accommodation && job.accommodation !== 'Nema smještaja' ? job.accommodation : null
  const all: [DetailKind, string | null][] = [
    ['place', town(job)],
    ['hours', workingTime(job)],
    ['deadline', deadline(job)],
    ['contract', contract],
    ['education', first(job.education)],
    ['experience', experience(job)],
    ['workers', job.workers_needed && job.workers_needed > 1 ? formatWorkers(job.workers_needed) : null],
    ['accommodation', accommodation],
  ]
  return all.filter((detail): detail is [DetailKind, string] => Boolean(detail[1])).map(([kind, text]) => ({ kind, text }))
}
