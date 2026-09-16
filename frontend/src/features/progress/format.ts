import type { PatternPoint, ResultKind, ResultRead } from '@/api/progress'
import { formatKg, plural } from '@/lib/format'

const REPS: [string, string, string] = ['повтор', 'повтора', 'повторов']
const WEEKS: [string, string, string] = ['неделя', 'недели', 'недель']

export const RESULT_LABELS: Record<ResultKind, string> = {
  est_1rm: 'Расчётный максимум, кг',
  reps: 'Лучший подход, повторов',
  seconds: 'Лучший подход, секунд',
}

export function resultText(result: ResultRead): string {
  const value = Number(result.value)
  if (result.kind === 'est_1rm') return `≈ ${formatKg(value)} кг`
  if (result.kind === 'seconds') return `${value} с`
  return `${value} ${plural(value, REPS)}`
}

/** Never counts what was missed: an empty streak is an invitation, not a verdict. */
export function streakText(weeks: number): string {
  if (weeks === 0) return 'Тренировка на этой неделе начнёт серию'
  return `${weeks} ${plural(weeks, WEEKS)} подряд с тренировками`
}

export type ResultPoint = { day: string; value: number; exercise: string; record: boolean }

/**
 * Best results on the current step of the ladder. Reps of an easier variant aren't the same
 * thing as reps of a harder one: putting both on one line would show the step up as a drop,
 * and the move to the next step is already what the ladder chart shows.
 */
export function resultSeries(points: PatternPoint[]): {
  exercise: string | null
  kind: ResultKind | null
  data: ResultPoint[]
} {
  const latest = points.findLast((p) => p.result)
  const exercise = latest?.exercise_slug ?? null
  const kind = latest?.result?.kind ?? null
  let best = Number.NEGATIVE_INFINITY
  const data: ResultPoint[] = []
  for (const p of points) {
    if (p.exercise_slug !== exercise || !p.result || p.result.kind !== kind) continue
    const value = Number(p.result.value)
    const record = value > best
    best = Math.max(best, value)
    data.push({ day: p.day, value, exercise: p.exercise_slug, record: record && data.length > 0 })
  }
  return { exercise, kind, data }
}

export type LevelPoint = { day: string; level: number; exercise: string; stepUp: boolean }

export function levelSeries(points: PatternPoint[]): LevelPoint[] {
  return points.map((p, i) => ({
    day: p.day,
    level: p.level,
    exercise: p.exercise_slug,
    stepUp: i > 0 && p.level > (points[i - 1]?.level ?? p.level),
  }))
}

const dayMonth = new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short' })

/** "2026-09-07" → «7 сент.», read as a calendar date, not shifted by the time zone. */
export function shortDate(isoDay: string): string {
  const [y, m, d] = isoDay.split('-').map(Number)
  return dayMonth.format(new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1))
}

export type CalendarDay = { iso: string; day: number; inMonth: boolean; trained: boolean }

const iso = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`

/** Weeks of a month from Monday, padded with the neighbouring months' days. */
export function monthGrid(year: number, month: number, trained: Set<string>): CalendarDay[][] {
  const first = new Date(year, month, 1)
  const start = new Date(year, month, 1 - ((first.getDay() + 6) % 7))
  const weeks: CalendarDay[][] = []
  const cursor = new Date(start)
  do {
    const week: CalendarDay[] = []
    for (let i = 0; i < 7; i++) {
      week.push({
        iso: iso(cursor),
        day: cursor.getDate(),
        inMonth: cursor.getMonth() === month,
        trained: trained.has(iso(cursor)),
      })
      cursor.setDate(cursor.getDate() + 1)
    }
    weeks.push(week)
  } while (cursor.getMonth() === month)
  return weeks
}

export const localDay = (timestamp: string) => iso(new Date(timestamp))

/**
 * Every week between the first and the last, with 0 where nothing was lifted. Leaving the
 * week out would squeeze the time axis and quietly misstate when the work happened.
 */
export function fillWeeks(
  weeks: { day: string; value: number }[],
): { day: string; value: number }[] {
  if (weeks.length === 0) return []
  const byDay = new Map(weeks.map((w) => [w.day, w.value]))
  const [y, m, d] = (weeks[0]?.day ?? '').split('-').map(Number)
  const cursor = new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1)
  const last = weeks.at(-1)?.day ?? ''
  const filled: { day: string; value: number }[] = []
  for (;;) {
    const day = iso(cursor)
    filled.push({ day, value: byDay.get(day) ?? 0 })
    if (day >= last) return filled
    cursor.setDate(cursor.getDate() + 7)
  }
}
