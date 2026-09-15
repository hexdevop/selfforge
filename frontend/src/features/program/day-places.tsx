import type { Location } from '@/api/locations'

type DayPlacesProps = {
  value: string[]
  locations: Location[]
  onChange: (places: string[]) => void
}

/** Where each training day happens. Days are numbered, not tied to weekdays. */
export function DayPlaces({ value, locations, onChange }: DayPlacesProps) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-2">
      <legend className="mb-2 text-base font-medium">Где проходит каждый день</legend>
      <p className="-mt-1 mb-1 text-sm text-muted-foreground">
        Программа раздаст движения по местам: что лучше делать на площадке, а что дома.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {value.map((locationId, day) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: a day is its position
          <label key={day} className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">День {day + 1}</span>
            <select
              value={locationId}
              onChange={(event) => onChange(value.with(day, event.target.value))}
              className="h-11 rounded-md border bg-card px-3 text-base focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              {locations.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.title}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
