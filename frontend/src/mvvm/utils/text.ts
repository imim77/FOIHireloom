
export function sentenceCase(text: string): string {
  if (text !== text.toUpperCase()) return text
  const lower = text.toLocaleLowerCase('hr-HR')
  return lower.charAt(0).toLocaleUpperCase('hr-HR') + lower.slice(1)
}

export const capitalise = (text: string) => text.charAt(0).toLocaleUpperCase('hr-HR') + text.slice(1)

export function titleCase(text: string): string {
  return text.toLocaleLowerCase('hr-HR').replace(/(^|[\s\-/(])(\p{L})/gu,
    (_, before: string, letter: string) => before + letter.toLocaleUpperCase('hr-HR'))
}

export const FEED_CATEGORY = 'Skupina zanimanja dopunjena iz HZZ-ova feeda po zanimanju'
