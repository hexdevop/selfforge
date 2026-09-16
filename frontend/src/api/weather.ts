import { queryOptions } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'

export type Forecast = components['schemas']['ForecastRead']
export type Verdict = components['schemas']['VerdictRead']

export type ForecastState =
  | { state: 'ready'; forecast: Forecast }
  | { state: 'no-pin'; message: string }
  | { state: 'unavailable'; message: string }

export const forecastQuery = (locationId: string) =>
  queryOptions({
    queryKey: ['weather', locationId],
    queryFn: async (): Promise<ForecastState> => {
      const { data, error, response } = await api.GET('/api/v1/weather/forecast', {
        params: { query: { location_id: locationId } },
      })
      if (data) return { state: 'ready', forecast: data }
      const message = error?.detail.message ?? 'Прогноз сейчас недоступен'
      // 422: the place has no coordinates yet — something the person can fix right away.
      return response.status === 422
        ? { state: 'no-pin', message }
        : { state: 'unavailable', message }
    },
    // The server caches for 30 minutes; there's no point asking more often.
    staleTime: 10 * 60 * 1000,
    retry: false,
  })

export async function swapLocation(sessionId: string, locationId: string) {
  const { data, error } = await api.POST('/api/v1/sessions/{session_id}/swap-location', {
    params: { path: { session_id: sessionId } },
    body: { location_id: locationId },
  })
  if (!data) throw new Error(error?.detail.message ?? 'Не удалось перенести тренировку')
  return data
}

export async function pinLocation(locationId: string, lat: number | null, lon: number | null) {
  const { data, error } = await api.PATCH('/api/v1/locations/{location_id}', {
    params: { path: { location_id: locationId } },
    body: { geo_lat: lat, geo_lon: lon },
  })
  if (!data) throw new Error(error?.detail.message ?? 'Не удалось сохранить, где площадка')
  return data
}
