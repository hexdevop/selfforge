import { useSuspenseQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { equipmentQuery } from '@/api/catalog'

export function useEquipmentMap() {
  const { data } = useSuspenseQuery(equipmentQuery)
  return useMemo(() => new Map(data.map((item) => [item.code, item])), [data])
}
