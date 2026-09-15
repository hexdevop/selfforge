import { queryOptions } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'

export type Program = components['schemas']['ProgramRead']
export type ProgramDraft = components['schemas']['ProgramDraft']
export type ProgramWeek = components['schemas']['ProgramWeekRead']
export type PlannedSession = components['schemas']['PlannedSessionRead']
export type PlannedExercise = components['schemas']['PlannedExerciseRead']
export type BlockKind = components['schemas']['BlockKind']
export type Structure = components['schemas']['Structure']

export const activeProgramQuery = queryOptions({
  queryKey: ['programs', 'active'],
  queryFn: async (): Promise<Program | null> => {
    const { data, response } = await api.GET('/api/v1/programs/active')
    if (response.status === 404) return null
    if (!data) throw new Error('Не удалось загрузить программу')
    return data
  },
})

/** A generated but unsaved program. Pure on the server, so it's safe to cache as a query. */
export const programPreviewQuery = (dayLocations: string[] | null) =>
  queryOptions({
    queryKey: ['programs', 'preview', dayLocations],
    queryFn: async () => {
      const { data, error } = await api.POST('/api/v1/programs/preview', {
        body: { day_locations: dayLocations },
      })
      if (!data) throw new Error(error?.detail.message ?? 'Не удалось собрать программу')
      return data
    },
    staleTime: 0,
    retry: false,
  })
