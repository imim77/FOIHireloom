const integer = new Intl.NumberFormat('hr-HR', { maximumFractionDigits: 0 })
const percent = new Intl.NumberFormat('hr-HR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export const formatInteger = (value: number) => integer.format(Math.round(value))
export const formatShare = (value: number) => `${percent.format(value)} %`

// Croatian plurals: 1, 21 … take one; 2–4, 22–24 … few; the rest, 11–14 included, many.
export function plural(count: number, one: string, few: string, many: string): string {
  const n = Math.round(count)
  if (n % 10 === 1 && n % 100 !== 11) return one
  return n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? few : many
}

export const formatAds = (value: number) => `${formatInteger(value)} ${plural(value, 'oglas', 'oglasa', 'oglasa')}`
// Always "traženih radnika", whatever the number.
export const formatWorkers = (value: number) => `${formatInteger(value)} traženih radnika`
