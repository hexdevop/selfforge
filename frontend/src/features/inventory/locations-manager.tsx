import { useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import { type Location, type LocationKind, locationsQuery } from '@/api/locations'
import { FormError } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { exercisesCount } from '@/lib/format'
import { InventoryEditor } from './inventory-editor'
import { DEFAULT_EQUIPMENT, KIND_LABELS } from './labels'
import { PlateCalculator } from './plate-calculator'

const hasAdjustable = (location: Location) =>
  location.equipment.some((item) => item.details.bar_kg != null)

export function LocationsManager({ withTools = false }: { withTools?: boolean }) {
  const queryClient = useQueryClient()
  const { data: locations } = useSuspenseQuery(locationsQuery)
  const [editing, setEditing] = useState<string | null>(null)
  const [error, setError] = useState<string>()

  const refresh = () => queryClient.invalidateQueries({ queryKey: locationsQuery.queryKey })

  const add = async (kind: LocationKind) => {
    setError(undefined)
    try {
      const { data } = await api.POST('/api/v1/locations', {
        body: { kind, title: KIND_LABELS[kind] },
      })
      if (!data) return setError('Не получилось добавить место. Попробуй ещё раз')
      await api.PUT('/api/v1/locations/{location_id}/equipment', {
        params: { path: { location_id: data.id } },
        body: DEFAULT_EQUIPMENT[kind].map((equipment_code) => ({ equipment_code })),
      })
      await refresh()
      setEditing(data.id)
    } catch {
      setError('Нет связи с сервером. Проверь интернет и попробуй ещё раз')
    }
  }

  const remove = async (location: Location) => {
    if (!window.confirm(`Удалить «${location.title}» вместе с инвентарём?`)) return
    await api.DELETE('/api/v1/locations/{location_id}', {
      params: { path: { location_id: location.id } },
    })
    await refresh()
  }

  return (
    <div className="flex flex-col gap-8">
      {locations.length === 0 && (
        <p className="text-muted-foreground">
          Добавь места, где тренируешься. Оборудование привязано к месту: дома одно, на площадке
          другое.
        </p>
      )}

      {locations.map((location) => {
        const open = editing === location.id
        return (
          <section
            key={location.id}
            aria-labelledby={`location-${location.id}`}
            className="flex flex-col gap-4 border-t pt-5"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
              <div>
                <h2 id={`location-${location.id}`} className="text-lg font-semibold">
                  {location.title}
                </h2>
                <p className="text-muted-foreground" aria-live="polite">
                  Здесь тебе доступно {exercisesCount(location.available_exercise_count)}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setEditing(open ? null : location.id)}>
                  {open ? 'Свернуть' : 'Настроить инвентарь'}
                </Button>
                <Button variant="ghost" onClick={() => remove(location)}>
                  Удалить
                </Button>
              </div>
            </div>
            {open && <InventoryEditor location={location} onSaved={() => setEditing(null)} />}
            {!open && withTools && hasAdjustable(location) && (
              <PlateCalculator location={location} />
            )}
          </section>
        )
      })}

      <div className="flex flex-col gap-3 border-t pt-5">
        <p className="font-medium">Добавить место</p>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(KIND_LABELS) as LocationKind[]).map((kind) => (
            <Button key={kind} variant="outline" onClick={() => add(kind)}>
              {KIND_LABELS[kind]}
            </Button>
          ))}
        </div>
        <FormError message={error} />
      </div>
    </div>
  )
}
