import { queryOptions } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'

export type BodyMetrics = components['schemas']['BodyMetrics']
export type BodyMetric = components['schemas']['BodyMetricRead']
export type BodyMetricIn = components['schemas']['BodyMetricIn']
export type Photo = components['schemas']['PhotoRead']
export type PhotoAngle = components['schemas']['PhotoAngle']

export const bodyMetricsQuery = queryOptions({
  queryKey: ['body', 'metrics'],
  queryFn: async () => {
    const { data } = await api.GET('/api/v1/body/metrics')
    if (!data) throw new Error('Не удалось загрузить замеры')
    return data
  },
})

export const photosQuery = queryOptions({
  queryKey: ['body', 'photos'],
  queryFn: async () => {
    const { data } = await api.GET('/api/v1/body/photos')
    if (!data) throw new Error('Не удалось загрузить фото')
    return data
  },
  // Links expire in 15 minutes; refresh well before that.
  staleTime: 5 * 60 * 1000,
  refetchInterval: 10 * 60 * 1000,
})

export async function addMetric(body: BodyMetricIn): Promise<BodyMetric> {
  const { data, error } = await api.POST('/api/v1/body/metrics', { body })
  if (!data) throw new Error(error?.detail.message ?? 'Не удалось сохранить замер')
  return data
}

export async function deleteMetric(id: string): Promise<void> {
  const { response } = await api.DELETE('/api/v1/body/metrics/{metric_id}', {
    params: { path: { metric_id: id } },
  })
  if (!response.ok) throw new Error('Не удалось удалить замер')
}

/**
 * The file goes straight to storage with a presigned form; the API only hands out the form.
 * If the upload itself fails, the empty photo entry is removed again.
 */
export async function uploadPhoto(file: File, angle: PhotoAngle): Promise<void> {
  const { data, error } = await api.POST('/api/v1/body/photos/upload-url', {
    body: { angle, content_type: file.type },
  })
  if (!data) throw new Error(error?.detail.message ?? 'Такой файл загрузить нельзя')

  const form = new FormData()
  for (const [key, value] of Object.entries(data.upload.fields)) form.append(key, String(value))
  form.append('file', file)
  const stored = await fetch(data.upload.url, { method: 'POST', body: form }).catch(() => null)
  if (!stored?.ok) {
    await deletePhoto(data.photo.id).catch(() => {})
    throw new Error(
      stored?.status === 400
        ? 'Файл слишком большой — до 15 МБ'
        : 'Фото не загрузилось. Проверь связь и попробуй ещё раз',
    )
  }
}

export async function deletePhoto(id: string): Promise<void> {
  const { response } = await api.DELETE('/api/v1/body/photos/{photo_id}', {
    params: { path: { photo_id: id } },
  })
  if (!response.ok) throw new Error('Не удалось удалить фото')
}
