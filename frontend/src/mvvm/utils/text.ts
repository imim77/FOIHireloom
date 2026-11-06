// HZZ writes most values in capitals; these turn them into the views' wording.

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

// The tooltip of a category the job's description does not state.
export const FEED_CATEGORY = 'Skupina zanimanja dopunjena iz HZZ-ova feeda po zanimanju'
