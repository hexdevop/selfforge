import { describe, expect, it } from 'vitest'
import type { ExerciseSummary } from '@/api/catalog'
import { BODYWEIGHT, filterExercises } from './filter'

const exercise = (overrides: Partial<ExerciseSummary>): ExerciseSummary => ({
  slug: 'x',
  title_ru: 'Упражнение',
  pattern_code: 'squat',
  difficulty_level: 1,
  is_unilateral: false,
  requires_pair: false,
  is_quiet: true,
  timed: false,
  required_equipment: [],
  primary_muscles: ['quads'],
  ...overrides,
})

const catalog = [
  exercise({ slug: 'air_squat', title_ru: 'Приседания с весом тела' }),
  exercise({
    slug: 'goblet',
    title_ru: 'Гоблет-присед',
    required_equipment: [['kettlebell', 'dumbbell']],
  }),
  exercise({
    slug: 'weighted_pullup',
    title_ru: 'Подтягивания с рюкзаком',
    pattern_code: 'pull_v',
    required_equipment: [['pullup_bar'], ['backpack', 'weight_vest']],
  }),
  exercise({ slug: 'hollow', title_ru: 'Лодочка на спине', pattern_code: 'core' }),
]

const slugs = (filter: Parameters<typeof filterExercises>[1]) =>
  filterExercises(catalog, filter).map((e) => e.slug)

describe('filterExercises', () => {
  it('returns everything without filters', () => {
    expect(slugs({})).toHaveLength(catalog.length)
  })

  it('filters by pattern', () => {
    expect(slugs({ pattern: 'pull_v' })).toEqual(['weighted_pullup'])
  })

  it('matches equipment in any OR-group', () => {
    expect(slugs({ equipment: 'dumbbell' })).toEqual(['goblet'])
    expect(slugs({ equipment: 'backpack' })).toEqual(['weighted_pullup'])
  })

  it('treats bodyweight as "needs nothing"', () => {
    expect(slugs({ equipment: BODYWEIGHT })).toEqual(['air_squat', 'hollow'])
  })

  it('searches titles case-insensitively and ignores ё', () => {
    expect(slugs({ q: 'ПРИСЕД' })).toEqual(['air_squat', 'goblet'])
    expect(slugs({ q: 'лодочка' })).toEqual(['hollow'])
    expect(filterExercises([exercise({ title_ru: 'Ёж' })], { q: 'еж' })).toHaveLength(1)
  })

  it('combines filters', () => {
    expect(slugs({ pattern: 'squat', equipment: BODYWEIGHT, q: 'присед' })).toEqual(['air_squat'])
  })
})
