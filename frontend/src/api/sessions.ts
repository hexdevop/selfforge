import { queryOptions } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'

export type WorkoutSession = components['schemas']['WorkoutSessionRead']
export type SessionBlock = components['schemas']['SessionBlockRead']
export type SessionExercise = components['schemas']['SessionExerciseRead']
export type Drill = components['schemas']['DrillRead']
export type SetLogIn = components['schemas']['SetLogIn']
export type SetLog = components['schemas']['SetLogRead']
export type PersonalRecord = components['schemas']['PersonalRecordRead']
export type Readiness = components['schemas']['Readiness-Input']
export type Feeling = components['schemas']['Feeling']
export type Side = components['schemas']['Side']
export type SubstitutionReason = components['schemas']['SubstitutionReason']
export type SetsAccepted = components['schemas']['SetsAccepted']

function unwrap<T>(data: T | undefined, message: string): T {
  if (data === undefined) throw new Error(message)
  return data
}

export const nextSessionQuery = queryOptions({
  queryKey: ['programs', 'next-session'],
  queryFn: async () => {
    const { data, response } = await api.GET('/api/v1/programs/active/next-session')
    if (response.status === 404 || response.status === 422) return null
    return unwrap(data, 'Не удалось понять, что тренируем сегодня')
  },
})

export const workoutQuery = (id: string) =>
  queryOptions({
    queryKey: ['sessions', id],
    queryFn: async () =>
      unwrap(
        (await api.GET('/api/v1/sessions/{session_id}', { params: { path: { session_id: id } } }))
          .data,
        'Не удалось загрузить тренировку',
      ),
    // The screen is the source of truth while it runs; refetching would fight the buffer.
    staleTime: Number.POSITIVE_INFINITY,
  })

/** A workout left open — on this device or another — to pick up instead of starting over. */
export const inProgressQuery = queryOptions({
  queryKey: ['sessions', 'in-progress'],
  queryFn: async () => {
    const { data } = await api.GET('/api/v1/sessions', {
      params: { query: { status: 'in_progress', size: 1 } },
    })
    return unwrap(data, 'Не удалось проверить начатые тренировки').items[0] ?? null
  },
  staleTime: 0,
})

export async function startWorkout(body: {
  planned_session_id?: string | null
  unplanned?: boolean
  location_id?: string | null
  readiness?: Readiness
}): Promise<WorkoutSession> {
  const { data, error } = await api.POST('/api/v1/sessions', { body })
  if (!data) throw new Error(error?.detail.message ?? 'Не удалось начать тренировку')
  return data
}

export async function sendSets(sessionId: string, sets: SetLogIn[]): Promise<SetsAccepted> {
  const { data, error } = await api.POST('/api/v1/sessions/{session_id}/sets', {
    params: { path: { session_id: sessionId } },
    body: { sets },
  })
  if (!data) throw new Error(error?.detail.message ?? 'Подходы не ушли на сервер')
  return data
}

export async function substituteExercise(
  sessionId: string,
  body: { exercise_slug: string; reason: SubstitutionReason },
): Promise<WorkoutSession> {
  const { data, error } = await api.POST('/api/v1/sessions/{session_id}/substitute', {
    params: { path: { session_id: sessionId } },
    body,
  })
  if (!data) throw new Error(error?.detail.message ?? 'Не нашлось замены')
  return data
}

export async function trimWorkout(sessionId: string, minutesLeft: number) {
  const { data, error } = await api.POST('/api/v1/sessions/{session_id}/trim', {
    params: { path: { session_id: sessionId } },
    body: { minutes_left: minutesLeft },
  })
  if (!data) throw new Error(error?.detail.message ?? 'Не удалось пересобрать тренировку')
  return data
}

export async function finishWorkout(sessionId: string, note?: string) {
  const { data, error } = await api.POST('/api/v1/sessions/{session_id}/finish', {
    params: { path: { session_id: sessionId } },
    body: { note: note ?? null },
  })
  if (!data) throw new Error(error?.detail.message ?? 'Не удалось завершить тренировку')
  return data
}

export async function abortWorkout(sessionId: string) {
  const { data, error } = await api.POST('/api/v1/sessions/{session_id}/abort', {
    params: { path: { session_id: sessionId } },
  })
  if (!data) throw new Error(error?.detail.message ?? 'Не удалось остановить тренировку')
  return data
}
