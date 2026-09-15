import type { Location } from '@/api/locations'
import type { Program } from '@/api/programs'

/** Start from the running program's places if they still fit, otherwise every day at the
 *  default place (the API lists it first). */
export function initialPlaces(active: Program | null, locations: Location[], days: number) {
  const known = new Set(locations.map((l) => l.id))
  const current = active?.weeks[0]?.sessions.map((s) => s.location_id) ?? []
  if (current.length === days && current.every((id) => id !== null && known.has(id))) {
    return current as string[]
  }
  const fallback = locations[0]?.id
  return fallback ? Array<string>(days).fill(fallback) : []
}
