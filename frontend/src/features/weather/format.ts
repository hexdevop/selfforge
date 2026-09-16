import type { LocationKind } from '@/api/locations'

export const isOutdoor = (kind: LocationKind) => kind === 'outdoor_gym' || kind === 'outdoor_bare'

/**
 * Two decimals is about a kilometre. The phone knows the spot to a few metres; the server
 * never needs to — the precise position doesn't leave the device.
 */
export const coarse = (degrees: number) => Math.round(degrees * 100) / 100

const signed = (value: number) => {
  const rounded = Math.round(value)
  return `${rounded > 0 ? '+' : rounded < 0 ? '−' : ''}${Math.abs(rounded)}`
}

export const degrees = (value: number) => `${signed(value)}°`

const hourFormat = new Intl.DateTimeFormat('ru', { hour: '2-digit', minute: '2-digit' })
export const hourOf = (iso: string) => hourFormat.format(new Date(iso))
