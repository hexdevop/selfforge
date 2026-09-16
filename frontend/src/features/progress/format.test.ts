import { describe, expect, it } from 'vitest'
import type { PatternPoint } from '@/api/progress'
import {
  fillWeeks,
  levelSeries,
  monthGrid,
  resultSeries,
  resultText,
  shortDate,
  streakText,
} from './format'

const point = (
  day: string,
  level: number,
  result: PatternPoint['result'],
  exercise = 'pullup',
): PatternPoint => ({ day, session_id: day, exercise_slug: exercise, level, result })

describe('texts', () => {
  it('names a result in its own unit', () => {
    expect(resultText({ kind: 'est_1rm', value: '20.27' })).toBe('≈ 20,27 кг')
    expect(resultText({ kind: 'reps', value: '5' })).toBe('5 повторов')
    expect(resultText({ kind: 'reps', value: '2' })).toBe('2 повтора')
    expect(resultText({ kind: 'seconds', value: '45' })).toBe('45 с')
  })

  it('invites rather than counts misses when there is no streak', () => {
    expect(streakText(0)).toBe('Тренировка на этой неделе начнёт серию')
    expect(streakText(1)).toBe('1 неделя подряд с тренировками')
    expect(streakText(5)).toBe('5 недель подряд с тренировками')
  })

  it('reads a date as a calendar day', () => {
    expect(shortDate('2026-09-07')).toMatch(/^7 сент/)
  })
})

describe('series', () => {
  const points = [
    point('2026-09-01', 5, { kind: 'reps', value: '5' }, 'negative_pullup'),
    point('2026-09-08', 6, { kind: 'reps', value: '2' }),
    point('2026-09-15', 6, { kind: 'reps', value: '6' }),
    point('2026-09-22', 6, null),
  ]

  it('marks every step up the ladder', () => {
    expect(levelSeries(points).map((p) => p.stepUp)).toEqual([false, true, false, false])
  })

  it('follows the current step only: an easier variant is not the same reps', () => {
    const series = resultSeries(points)
    expect(series.exercise).toBe('pullup')
    expect(series.data.map((p) => [p.day, p.value, p.record])).toEqual([
      ['2026-09-08', 2, false],
      ['2026-09-15', 6, true],
    ])
  })

  it('keeps one unit on the line: the latest one', () => {
    const mixed = [
      point('2026-09-01', 6, { kind: 'reps', value: '12' }, 'goblet_squat'),
      point('2026-09-08', 6, { kind: 'est_1rm', value: '90.5' }, 'goblet_squat'),
    ]
    const series = resultSeries(mixed)
    expect(series.kind).toBe('est_1rm')
    expect(series.data.map((p) => p.value)).toEqual([90.5])
  })
})

describe('calendar', () => {
  it('lays a month out in weeks from Monday', () => {
    // September 2026 starts on a Tuesday and ends on a Wednesday.
    const weeks = monthGrid(2026, 8, new Set(['2026-09-07']))
    expect(weeks).toHaveLength(5)
    expect(weeks[0]?.[0]).toMatchObject({ iso: '2026-08-31', inMonth: false })
    expect(weeks[1]?.[0]).toMatchObject({ iso: '2026-09-07', trained: true })
    expect(weeks.at(-1)?.at(-1)).toMatchObject({ iso: '2026-10-04', inMonth: false })
  })
})

describe('weekly volume', () => {
  it('keeps an empty week on the time axis', () => {
    expect(
      fillWeeks([
        { day: '2026-08-31', value: 100 },
        { day: '2026-09-14', value: 50 },
      ]),
    ).toEqual([
      { day: '2026-08-31', value: 100 },
      { day: '2026-09-07', value: 0 },
      { day: '2026-09-14', value: 50 },
    ])
    expect(fillWeeks([])).toEqual([])
  })
})
