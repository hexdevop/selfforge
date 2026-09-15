import { expect, it } from 'vitest'
import type { Equipment, Exercise } from '@/api/catalog'
import { plural } from '@/lib/format'
import { criteriaText, equipmentText } from './labels'

const item = (code: string, title_ru: string): [string, Equipment] => [
  code,
  {
    code,
    title_ru,
    category: 'bars',
    supports_quantity: false,
    supports_weight_list: false,
    is_outdoor: false,
  },
]

it('picks Russian plural forms', () => {
  const forms: [string, string, string] = ['упражнение', 'упражнения', 'упражнений']
  expect([1, 3, 5, 11, 21, 22].map((n) => plural(n, forms))).toEqual([
    'упражнение',
    'упражнения',
    'упражнений',
    'упражнений',
    'упражнение',
    'упражнения',
  ])
})

it('describes equipment requirements as AND of ORs', () => {
  const byCode = new Map([
    item('pullup_bar', 'Турник'),
    item('rings', 'Кольца'),
    item('towel', 'Полотенце'),
  ])
  expect(equipmentText([], byCode)).toBe('Без оборудования')
  expect(equipmentText([['pullup_bar', 'rings'], ['towel']], byCode)).toBe(
    'Турник или кольца + полотенце',
  )
})

it('formats progression criteria for reps and holds', () => {
  const base = { is_unilateral: false, progression_criteria: null } as unknown as Exercise
  expect(criteriaText(base)).toBeNull()
  expect(
    criteriaText({ ...base, progression_criteria: { sets: 3, reps: 12, hold_seconds: null } }),
  ).toBe('3 подхода по 12 повторов')
  expect(
    criteriaText({
      ...base,
      is_unilateral: true,
      progression_criteria: { sets: 3, reps: null, hold_seconds: 30 },
    }),
  ).toBe('3 подхода по 30 с на каждую сторону')
})
