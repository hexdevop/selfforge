import { expect, it } from 'vitest'
import type { PlannedExercise } from '@/api/programs'
import { restText, setsText, weeksText, weekTitle } from './format'

const exercise: PlannedExercise = {
  exercise_slug: 'goblet_squat',
  pattern_code: 'squat',
  sets: 3,
  target_min: 8,
  target_max: 12,
  timed: false,
  rest_seconds: 90,
  rir: 2,
  tempo: null,
}

it.each([
  [exercise, '3 × 8–12'],
  [{ ...exercise, timed: true, target_min: 20, target_max: 40 }, '3 × 20–40 с'],
  [{ ...exercise, sets: 2, target_min: 5, target_max: 5 }, '2 × 5'],
])('sets %#', (e, text) => {
  expect(setsText(e)).toBe(text)
})

it.each([
  [45, 'отдых 45 с'],
  [60, 'отдых 60 с'],
  [90, 'отдых 90 с'],
  [180, 'отдых 3 мин'],
])('rest %i', (seconds, text) => {
  expect(restText(seconds)).toBe(text)
})

it('weeks', () => {
  expect(weeksText(4)).toBe('4 недели')
  expect(weeksText(5)).toBe('5 недель')
  expect(weekTitle(0, 'accumulation')).toBe('Неделя 1')
  expect(weekTitle(3, 'deload')).toBe('Неделя 4 · разгрузка')
})
