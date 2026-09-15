import { queryOptions } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'

export type Location = components['schemas']['LocationRead']
export type LocationKind = components['schemas']['LocationKind']
export type LocationConstraints = components['schemas']['Constraints-Output']
export type EquipmentInput = components['schemas']['LocationEquipmentIn']
export type EquipmentDetailsInput = components['schemas']['EquipmentDetails-Input']
export type PlatesResult = components['schemas']['PlatesRead']

export const locationsQuery = queryOptions({
  queryKey: ['locations'],
  queryFn: async () => {
    const { data } = await api.GET('/api/v1/locations')
    if (!data) throw new Error('Не удалось загрузить места')
    return data
  },
})

export const weightGridQuery = (locationId: string) =>
  queryOptions({
    queryKey: ['locations', locationId, 'weight-grid'],
    queryFn: async () => {
      const { data } = await api.GET('/api/v1/locations/{location_id}/weight-grid', {
        params: { path: { location_id: locationId } },
      })
      if (!data) throw new Error('Не удалось загрузить сетку весов')
      return data
    },
  })
