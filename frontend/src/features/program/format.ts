import type { BlockKind, PlannedExercise, Structure } from '@/api/programs'
import { plural } from '@/lib/format'

export const BLOCK_LABELS: Record<BlockKind, string> = {
  warmup: 'Разминка',
  main: 'Основная часть',
  accessory: 'Вспомогательные',
  finisher: 'Финишер',
  cooldown: 'Заминка',
}

export const STRUCTURE_LABELS: Record<Structure, string> = {
  fullbody: 'Фулбоди',
  upper_lower: 'Верх и низ',
  ppl: 'Жим, тяга, ноги',
}

/** Content of warm-up and cool-down comes with the workout screen; until then, what they're for. */
export const BLOCK_HINTS: Partial<Record<BlockKind, string>> = {
  warmup: 'Суставная разминка и лёгкие подходы первого упражнения',
  cooldown: 'Спокойное дыхание и растяжка того, что работало',
}

/** 3 × 8–12, or 3 × 20–40 с for timed work. */
export function setsText(e: PlannedExercise): string {
  const range =
    e.target_min === e.target_max ? `${e.target_min}` : `${e.target_min}–${e.target_max}`
  return `${e.sets} × ${range}${e.timed ? ' с' : ''}`
}

/** 90 → «отдых 90 с», 180 → «отдых 3 мин». */
export function restText(seconds: number): string {
  return seconds % 60 === 0 && seconds >= 120 ? `отдых ${seconds / 60} мин` : `отдых ${seconds} с`
}

export const weeksText = (n: number) => `${n} ${plural(n, ['неделя', 'недели', 'недель'])}`

export const weekTitle = (index: number, kind: string) =>
  `Неделя ${index + 1}${kind === 'deload' ? ' · разгрузка' : ''}`
