import type { ProgramWeek } from '@/api/programs'
import { cn } from '@/lib/utils'
import { weekTitle } from './format'

type CalendarProps = {
  weeks: ProgramWeek[]
  placeOf: (locationId: string | null) => string
  selected: { week: number; day: number }
  onSelect: (week: number, day: number) => void
}

/** The whole mesocycle at a glance; picking a day shows its card. */
export function Calendar({ weeks, placeOf, selected, onSelect }: CalendarProps) {
  return (
    <div className="flex flex-col gap-4">
      {weeks.map((week) => (
        <section key={week.index} className="flex flex-col gap-2">
          <h3 className="text-sm text-muted-foreground">{weekTitle(week.index, week.kind)}</h3>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(9.5rem,1fr))] gap-2">
            {week.sessions.map((session) => {
              const active = selected.week === week.index && selected.day === session.day_index
              return (
                <button
                  key={session.day_index}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onSelect(week.index, session.day_index)}
                  className={cn(
                    'flex min-h-11 flex-col rounded-lg border bg-card px-3 py-2 text-left',
                    'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                    active
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'hover:bg-secondary',
                  )}
                >
                  <span className="font-medium">
                    День {session.day_index + 1} · {session.title_ru}
                  </span>
                  <span className="text-sm tabular-nums opacity-80">
                    {placeOf(session.location_id)} · {session.estimated_minutes} мин
                  </span>
                </button>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
