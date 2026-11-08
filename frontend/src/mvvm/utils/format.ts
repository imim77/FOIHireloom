const integer = new Intl.NumberFormat('hr-HR', { maximumFractionDigits: 0 })
const percent = new Intl.NumberFormat('hr-HR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export const formatInteger = (value: number) => integer.format(Math.round(value))
export const formatShare = (value: number) => `${percent.format(value)}\u00a0%`

export function plural(count: number, one: string, few: string, many: string): string {
  const n = Math.round(count)
  if (n % 10 === 1 && n % 100 !== 11) return one
  return n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? few : many
}

export const formatAds = (value: number) => `${formatInteger(value)} ${plural(value, 'oglas', 'oglasa', 'oglasa')}`
export const formatWorkers = (value: number) => `${formatInteger(value)} traženih radnika`

export const formatDecimal = (value: number) => percent.format(value)
export const formatRate = formatShare

export function formatPoints(value: number): string {
  const rounded = Math.round(value * 10) / 10
  const sign = rounded > 0 ? '+' : rounded < 0 ? '−' : ''
  return `${sign}${percent.format(Math.abs(rounded))}\u00a0p.\u00a0b.`
}

const MONTHS = ['siječanj', 'veljača', 'ožujak', 'travanj', 'svibanj', 'lipanj', 'srpanj', 'kolovoz', 'rujan',
  'listopad', 'studeni', 'prosinac']
const MONTHS_GENITIVE = ['siječnja', 'veljače', 'ožujka', 'travnja', 'svibnja', 'lipnja', 'srpnja', 'kolovoza',
  'rujna', 'listopada', 'studenoga', 'prosinca']
const SHORT_MONTHS = ['sij', 'velj', 'ožu', 'tra', 'svi', 'lip', 'srp', 'kol', 'ruj', 'lis', 'stu', 'pro']

const monthOf = (iso: string) => ({ year: Number(iso.slice(0, 4)), month: Number(iso.slice(5, 7)) })

export function formatMonth(iso: string): string {
  const { year, month } = monthOf(iso)
  return `${MONTHS[month - 1]} ${year}.`
}

export function formatMonthGenitive(iso: string): string {
  const { year, month } = monthOf(iso)
  return `${MONTHS_GENITIVE[month - 1]} ${year}.`
}

export function formatShortMonth(iso: string, withYear = false): string {
  const { year, month } = monthOf(iso)
  return withYear ? `${SHORT_MONTHS[month - 1]} ${year}.` : SHORT_MONTHS[month - 1]
}

const ZAGREB = 'Europe/Zagreb'
const dayParts = new Intl.DateTimeFormat('hr-HR', { timeZone: ZAGREB, day: '2-digit', month: '2-digit', year: 'numeric' })
const timeParts = new Intl.DateTimeFormat('hr-HR', { timeZone: ZAGREB, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })

export function formatDay(iso: string): string {
  const parts = Object.fromEntries(dayParts.formatToParts(new Date(iso)).map((part) => [part.type, part.value]))
  return `${parts.day}. ${parts.month}. ${parts.year}.`
}

export const formatMoment = (iso: string) => `${formatDay(iso)} u ${timeParts.format(new Date(iso))}`
