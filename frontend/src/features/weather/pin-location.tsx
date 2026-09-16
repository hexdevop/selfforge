import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MapPin } from 'lucide-react'
import { useState } from 'react'
import type { Location } from '@/api/locations'
import { pinLocation } from '@/api/weather'
import { Button } from '@/components/ui/button'
import { coarse } from './format'

function currentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      reject(new Error('Этот браузер не умеет определять место'))
      return
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false,
      timeout: 15_000,
      maximumAge: 5 * 60_000,
    })
  })
}

const GEO_ERRORS: Record<number, string> = {
  1: 'Доступ к местоположению не разрешён. Его можно включить в настройках браузера для этого сайта.',
  2: 'Не получилось определить место. Попробуй на улице или чуть позже.',
  3: 'Определение места заняло слишком долго. Попробуй ещё раз.',
}

/** «I'm at this park right now» — the only moment the phone's position is asked for. */
export function PinLocation({ location }: { location: Location }) {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string>()
  const pinned = location.geo_lat != null && location.geo_lon != null

  const save = useMutation({
    mutationFn: async (clear: boolean) => {
      if (clear) return pinLocation(location.id, null, null)
      const { coords } = await currentPosition().catch(
        (error: GeolocationPositionError | Error) => {
          throw new Error('code' in error ? GEO_ERRORS[error.code] : error.message)
        },
      )
      return pinLocation(location.id, coarse(coords.latitude), coarse(coords.longitude))
    },
    onMutate: () => setMessage(undefined),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['locations'] })
      await queryClient.invalidateQueries({ queryKey: ['weather', location.id] })
    },
    onError: (error: Error) => setMessage(error.message),
  })

  return (
    <div className="flex flex-col items-start gap-2">
      <p className="text-sm text-muted-foreground">
        {pinned
          ? 'Место отмечено — перед тренировкой покажем прогноз.'
          : 'Отметь, где площадка, — перед тренировкой покажем прогноз и предложим домашний вариант в непогоду. Место сохраняется примерно, с точностью до километра.'}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={save.isPending} onClick={() => save.mutate(false)}>
          <MapPin />
          {save.isPending
            ? 'Определяем…'
            : pinned
              ? 'Отметить заново'
              : 'Я сейчас на этой площадке'}
        </Button>
        {pinned && (
          <Button variant="ghost" disabled={save.isPending} onClick={() => save.mutate(true)}>
            Убрать отметку
          </Button>
        )}
      </div>
      {message && (
        <p className="text-sm text-destructive" role="alert">
          {message}
        </p>
      )}
    </div>
  )
}
