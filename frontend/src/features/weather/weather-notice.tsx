import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { CloudRain, CloudSun, Snowflake, Sun, Thermometer, Wind } from 'lucide-react'
import type { Location } from '@/api/locations'
import { forecastQuery, type Verdict } from '@/api/weather'
import { Button } from '@/components/ui/button'
import { degrees, hourOf, isOutdoor } from './format'

type Action = { label: string; onClick: (indoorLocationId: string) => void; pending?: boolean }

function Icon({ verdict }: { verdict: Verdict }) {
  const first = verdict.concerns[0]
  const props = { className: 'size-6 shrink-0', 'aria-hidden': true }
  if (first === 'rain') return <CloudRain {...props} />
  if (first === 'snow') return <Snowflake {...props} />
  if (first === 'wind') return <Wind {...props} />
  if (first === 'cold' || first === 'heat') return <Thermometer {...props} />
  return verdict.hints.includes('warm') ? <Sun {...props} /> : <CloudSun {...props} />
}

/**
 * The forecast for an outdoor place, and — when it's bad — the offer to do the same workout
 * indoors. It offers, it doesn't decide: the person may well prefer the rain.
 */
export function WeatherNotice({
  location,
  moveIndoors,
  onlyWhenBad = false,
}: {
  location: Location
  /** Shown only when the forecast says so and there is an indoor place to go to. */
  moveIndoors?: Action
  /** Mid-workout the screen belongs to the set: speak up only when it's worth moving. */
  onlyWhenBad?: boolean
}) {
  const outdoor = isOutdoor(location.kind)
  const { data } = useQuery({ ...forecastQuery(location.id), enabled: outdoor })
  if (!outdoor) return null

  if (onlyWhenBad && (data?.state !== 'ready' || !data.forecast.verdict?.move_indoors)) {
    return null
  }
  if (!data) {
    return <p className="text-sm text-muted-foreground">Смотрим прогноз…</p>
  }
  if (data.state === 'no-pin') {
    return (
      <p className="text-sm text-muted-foreground">
        Прогноза нет: не отмечено, где «{location.title}».{' '}
        <Link to="/locations" className="underline underline-offset-4">
          Отметить площадку
        </Link>
      </p>
    )
  }
  if (data.state === 'unavailable') {
    return <p className="text-sm text-muted-foreground">{data.message}</p>
  }

  const { verdict, hours, indoor_location_id } = data.forecast
  if (!verdict) {
    return <p className="text-sm text-muted-foreground">Прогноза на ближайшие часы пока нет.</p>
  }

  return (
    <section
      aria-label={`Погода: ${location.title}`}
      className="flex flex-col gap-3 rounded-xl border bg-card p-4"
    >
      <div className="flex gap-3">
        <Icon verdict={verdict} />
        <p>{verdict.text_ru}</p>
      </div>
      <ol className="flex gap-4 overflow-x-auto text-center text-sm tabular-nums [scrollbar-width:none]">
        {hours.slice(0, 6).map((h) => (
          <li key={h.at} className="flex shrink-0 flex-col">
            <span className="text-muted-foreground">{hourOf(h.at)}</span>
            <span className="font-medium">{degrees(h.apparent_c)}</span>
            <span className="text-muted-foreground">
              {h.precipitation_probability > 0 ? `${h.precipitation_probability}%` : '—'}
            </span>
          </li>
        ))}
      </ol>
      <p className="sr-only">Строки: время, температура по ощущению, вероятность осадков.</p>
      {verdict.move_indoors && moveIndoors && indoor_location_id && (
        <Button
          className="self-start"
          disabled={moveIndoors.pending}
          onClick={() => moveIndoors.onClick(indoor_location_id)}
        >
          {moveIndoors.label}
        </Button>
      )}
      {verdict.move_indoors && !indoor_location_id && (
        <p className="text-sm text-muted-foreground">
          Чтобы перенести тренировку, добавь домашнее место с инвентарём.
        </p>
      )}
    </section>
  )
}
