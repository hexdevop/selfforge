import { queryOptions } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'

export type ExerciseSummary = components['schemas']['ExerciseSummary']
export type Exercise = components['schemas']['ExerciseRead']
export type Pattern = components['schemas']['PatternRead']
export type Equipment = components['schemas']['EquipmentRead']
export type Muscle = components['schemas']['Muscle']
export type HealthTag = components['schemas']['HealthTag']
export type EquipmentCategory = components['schemas']['EquipmentCategory']
export type PatternCode = components['schemas']['PatternCode']

// Reference data changes only on deploy: fetch once, keep for the session.
// The server still revalidates with ETag when it does refetch.
const catalog = { staleTime: 60 * 60 * 1000, gcTime: Number.POSITIVE_INFINITY }

function required<T>(data: T | undefined, what: string): T {
  if (data === undefined) throw new Error(`Не удалось загрузить: ${what}`)
  return data
}

export const exercisesQuery = queryOptions({
  queryKey: ['catalog', 'exercises'],
  queryFn: async () => required((await api.GET('/api/v1/exercises')).data, 'упражнения'),
  ...catalog,
})

export const exerciseQuery = (slug: string) =>
  queryOptions({
    queryKey: ['catalog', 'exercise', slug],
    queryFn: async (): Promise<Exercise | null> => {
      const { data, response } = await api.GET('/api/v1/exercises/{slug}', {
        params: { path: { slug } },
      })
      if (response.status === 404) return null
      return required(data, 'упражнение')
    },
    ...catalog,
  })

export const patternsQuery = queryOptions({
  queryKey: ['catalog', 'patterns'],
  queryFn: async () => required((await api.GET('/api/v1/patterns')).data, 'паттерны'),
  ...catalog,
})

export const equipmentQuery = queryOptions({
  queryKey: ['catalog', 'equipment'],
  queryFn: async () => required((await api.GET('/api/v1/equipment')).data, 'оборудование'),
  ...catalog,
})
