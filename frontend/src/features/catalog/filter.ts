import type { ExerciseSummary } from '@/api/catalog'

export const BODYWEIGHT = 'none'

export type CatalogFilter = {
  pattern?: string
  /** Equipment code the exercise uses, or BODYWEIGHT for exercises needing nothing. */
  equipment?: string
  q?: string
}

const normalize = (text: string) => text.toLocaleLowerCase('ru').replaceAll('ё', 'е').trim()

export function filterExercises(
  exercises: ExerciseSummary[],
  { pattern, equipment, q }: CatalogFilter,
): ExerciseSummary[] {
  const query = q ? normalize(q) : ''
  return exercises.filter(
    (e) =>
      (!pattern || e.pattern_code === pattern) &&
      (!equipment ||
        (equipment === BODYWEIGHT
          ? e.required_equipment.length === 0
          : e.required_equipment.some((group) => group.includes(equipment)))) &&
      (!query || normalize(e.title_ru).includes(query)),
  )
}
