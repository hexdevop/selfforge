import { queryOptions } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'

export type Summary = components['schemas']['Summary']
export type PatternProgress = components['schemas']['PatternProgress']
export type PatternPoint = components['schemas']['PatternPoint']
export type ResultRead = components['schemas']['ResultRead']
export type ResultKind = components['schemas']['ResultKind']
export type TonnagePoint = components['schemas']['TonnagePoint']
export type Imbalance = components['schemas']['ImbalanceRead']
export type SkillProgress = components['schemas']['SkillProgressRead']
export type SkillTarget = components['schemas']['TargetRead']
export type PersonalRecord = components['schemas']['PersonalRecordRead']

function unwrap<T>(data: T | undefined, what: string): T {
  if (data === undefined) throw new Error(`Не удалось загрузить: ${what}`)
  return data
}

export const summaryQuery = queryOptions({
  queryKey: ['progress', 'summary'],
  queryFn: async () => unwrap((await api.GET('/api/v1/progress/summary')).data, 'сводку'),
})

export const patternProgressQuery = (code: components['schemas']['PatternCode']) =>
  queryOptions({
    queryKey: ['progress', 'pattern', code],
    queryFn: async () =>
      unwrap(
        (await api.GET('/api/v1/progress/patterns/{code}', { params: { path: { code } } })).data,
        'прогресс по движению',
      ),
  })

export const weeklyTonnageQuery = queryOptions({
  queryKey: ['progress', 'tonnage', 'week'],
  queryFn: async () =>
    unwrap(
      (await api.GET('/api/v1/progress/tonnage', { params: { query: { period: 'week' } } })).data,
      'тоннаж',
    ),
})

export const recordsQuery = queryOptions({
  queryKey: ['progress', 'records'],
  queryFn: async () => unwrap((await api.GET('/api/v1/progress/records')).data, 'рекорды'),
})

export const balanceQuery = queryOptions({
  queryKey: ['progress', 'balance'],
  queryFn: async () => unwrap((await api.GET('/api/v1/progress/balance')).data, 'баланс сторон'),
})

export const skillsQuery = queryOptions({
  queryKey: ['progress', 'skills'],
  queryFn: async () => unwrap((await api.GET('/api/v1/progress/skills')).data, 'навыки'),
})

/** Days with a workout, for the calendar: the latest 100 are plenty for a few months back. */
export const workoutDaysQuery = queryOptions({
  queryKey: ['sessions', 'history', 'days'],
  queryFn: async () => {
    const { data } = await api.GET('/api/v1/sessions', { params: { query: { size: 100 } } })
    // Dated by the first working set, the same rule the streak on the server uses.
    return unwrap(data, 'историю тренировок').items.flatMap((session) => {
      const working = session.sets.filter((set) => !set.is_warmup)
      const first = working.map((set) => set.performed_at).sort()[0]
      return first ? [first] : []
    })
  },
})

export async function markSkill(slug: string, achieved: boolean): Promise<SkillProgress> {
  const { data, error } = await api.PUT('/api/v1/progress/skills/{slug}', {
    params: { path: { slug } },
    body: { achieved },
  })
  if (!data) throw new Error(error?.detail.message ?? 'Не удалось сохранить отметку')
  return data
}
