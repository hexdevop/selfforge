import type { Equipment, Exercise, ExerciseSummary, HealthTag, Muscle } from '@/api/catalog'
import { plural } from '@/lib/format'

export const MUSCLE_LABELS: Record<Muscle, string> = {
  chest: 'грудь',
  front_delts: 'передняя дельта',
  side_delts: 'средняя дельта',
  rear_delts: 'задняя дельта',
  triceps: 'трицепс',
  biceps: 'бицепс',
  forearms: 'предплечья',
  lats: 'широчайшие',
  upper_back: 'верх спины',
  lower_back: 'поясница',
  abs: 'пресс',
  obliques: 'косые мышцы живота',
  glutes: 'ягодицы',
  quads: 'передняя поверхность бедра',
  hamstrings: 'задняя поверхность бедра',
  adductors: 'приводящие мышцы бедра',
  calves: 'икры',
  hip_flexors: 'сгибатели бедра',
}

export const HEALTH_LABELS: Record<HealthTag, string> = {
  knees: 'колени',
  shoulders: 'плечи',
  lower_back: 'поясница',
  wrists: 'запястья',
  neck: 'шея',
  elbows: 'локти',
}

export const listRu = (items: string[]) =>
  items.length < 2 ? (items[0] ?? '') : `${items.slice(0, -1).join(', ')} и ${items.at(-1)}`

/** [["pullup_bar", "rings"], ["backpack"]] → "Турник или гимнастические кольца + рюкзак с грузом" */
export function equipmentText(
  groups: ExerciseSummary['required_equipment'],
  byCode: Map<string, Equipment>,
): string {
  if (groups.length === 0) return 'Без оборудования'
  const text = groups
    .map((group) =>
      group
        .map((code) => (byCode.get(code)?.title_ru ?? code).toLocaleLowerCase('ru'))
        .join(' или '),
    )
    .join(' + ')
  return text.charAt(0).toLocaleUpperCase('ru') + text.slice(1)
}

export function criteriaText(exercise: Exercise): string | null {
  const c = exercise.progression_criteria
  if (!c) return null
  const sets = `${c.sets} ${plural(c.sets, ['подход', 'подхода', 'подходов'])}`
  const work = c.reps
    ? `по ${c.reps} ${plural(c.reps, ['повтору', 'повтора', 'повторов'])}`
    : `по ${c.hold_seconds} с`
  return `${sets} ${work}${exercise.is_unilateral ? ' на каждую сторону' : ''}`
}

export function featureNotes(exercise: Exercise): string[] {
  return [
    exercise.is_unilateral && 'Каждая сторона отдельно, повторов поровну',
    exercise.requires_pair && 'Нужна пара снарядов',
    !exercise.is_quiet && 'Шумное — не для режима тишины',
    exercise.needs_ceiling_height && 'Нужен высокий потолок',
    exercise.needs_floor_space && 'Нужно место для шагов',
    exercise.lies_on_floor && 'Выполняется лёжа на полу',
  ].filter((note): note is string => Boolean(note))
}
