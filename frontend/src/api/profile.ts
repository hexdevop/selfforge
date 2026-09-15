import { queryOptions } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'

export type Profile = components['schemas']['ProfileRead']
export type Goal = components['schemas']['Goal']
export type Assessment = components['schemas']['AssessmentRead']
export type AssessmentAnswers = components['schemas']['AssessmentRequest']
export type PatternLevel = components['schemas']['PatternLevelRead']

export const profileQuery = queryOptions({
  queryKey: ['profile'],
  queryFn: async () => {
    const { data } = await api.GET('/api/v1/profile')
    if (!data) throw new Error('Не удалось загрузить профиль')
    return data
  },
})

export const patternLevelsQuery = queryOptions({
  queryKey: ['profile', 'pattern-levels'],
  queryFn: async () => {
    const { data } = await api.GET('/api/v1/profile/pattern-levels')
    if (!data) throw new Error('Не удалось загрузить уровни')
    return data
  },
})
