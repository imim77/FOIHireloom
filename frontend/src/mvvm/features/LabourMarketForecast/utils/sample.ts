import type { ForecastData } from '../types'

export function sample(): ForecastData {
  const history = [3.2, 3.3, 3.1, 2.9, 2.7, 2.5, 2.4, 2.4, 2.3, 2.5, 2.7, 2.8,
    2.9, 3, 2.8, 2.6, 2.4, 2.2, 2.1, 2, 2.1, 2.3, 2.4, 2.5].map((value, index) => ({
    period: `${2024 + Math.floor((9 + index) / 12)}-${String((9 + index) % 12 + 1).padStart(2, '0')}-01`,
    value, is_provisional: index >= 15, is_estimated: false,
  }))
  const forecast = [2.6, 2.8, 2.9, 3, 2.9, 2.7].map((median, index) => ({
    period: `${2026 + Math.floor((9 + index) / 12)}-${String((9 + index) % 12 + 1).padStart(2, '0')}-01`,
    median, low: Math.round((median - 0.3 - index * 0.1) * 10) / 10,
    high: Math.round((median + 0.3 + index * 0.1) * 10) / 10,
  }))
  return {
    title: 'Prognoza stope nezaposlenosti', description: 'Varaždinska županija · po mjesecima',
    target: 'unemployment_rate', frequency: 'month', unit: 'percent', sex: 'total', horizon: 6,
    interval: 0.8, model: 'amazon/chronos-2', last_observed_period: '2026-09-01', unavailable_reason: null,
    counties: [{ code: 'varazdinska', name: 'Varaždinska županija', iso_code: 'HR-05', history, forecast,
      last_observed: history.at(-1)!, change_to_horizon: 0.2, unavailable_reason: null }],
    unavailable_label: null, sources: [], notes: [],
    source_links: [{ label: 'DZS, pregled po županijama', url: 'https://podaci.dzs.hr/' },
      { label: 'Amazon Chronos (amazon/chronos-2)', url: 'https://huggingface.co/amazon/chronos-2' }],
    view_notes: ['Ogledni podaci za pregled izgleda; ove vrijednosti nisu stvarna Chronos prognoza.',
      'Medijan je središnja prognoza; osjenčani raspon prikazuje 80% interval.',
      'Prognoza počinje nakon zadnjeg dostupnog mjeseca. Povijesni podaci mogu biti privremeni.'],
  }
}
