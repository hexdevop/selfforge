import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, redirect } from '@tanstack/react-router'
import { useMemo } from 'react'
import { exercisesQuery } from '@/api/catalog'
import { locationsQuery } from '@/api/locations'
import { activeProgramQuery } from '@/api/programs'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/features/program/calendar'
import { DayCard } from '@/features/program/day-card'
import { STRUCTURE_LABELS, weeksText, weekTitle } from '@/features/program/format'
import { Rationale } from '@/features/program/rationale'

const dayMonth = new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'long' })
const index = (value: unknown) =>
  Number.isInteger(value) && Number(value) >= 0 ? Number(value) : 0

export const Route = createFileRoute('/_authed/program/')({
  validateSearch: (search): { week?: number; day?: number } => ({
    week: search.week === undefined ? undefined : index(search.week),
    day: search.day === undefined ? undefined : index(search.day),
  }),
  beforeLoad: async ({ context: { queryClient } }) => {
    if (!(await queryClient.ensureQueryData(activeProgramQuery))) {
      throw redirect({ to: '/program/new' })
    }
  },
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(locationsQuery),
      queryClient.ensureQueryData(exercisesQuery),
    ]),
  component: ProgramPage,
})

function ProgramPage() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data: program } = useSuspenseQuery(activeProgramQuery)
  const { data: locations } = useSuspenseQuery(locationsQuery)
  const { data: catalog } = useSuspenseQuery(exercisesQuery)
  const exercises = useMemo(() => new Map(catalog.map((e) => [e.slug, e])), [catalog])
  const week = program?.weeks[search.week ?? 0] ?? program?.weeks[0]
  const session = week?.sessions.find((s) => s.day_index === search.day) ?? week?.sessions[0]
  if (!program || !week || !session) return null

  const placeOf = (id: string | null) =>
    locations.find((l) => l.id === id)?.title ?? 'Место удалено'

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Программа</h1>
        <p className="text-muted-foreground">
          {STRUCTURE_LABELS[program.structure]} · {weeksText(program.weeks_total)} · с{' '}
          {dayMonth.format(new Date(program.started_at))}
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{weekTitle(week.index, week.kind)}</h2>
        <DayCard session={session} exercises={exercises} place={placeOf(session.location_id)} />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Весь цикл</h2>
        <Calendar
          weeks={program.weeks}
          placeOf={placeOf}
          selected={{ week: week.index, day: session.day_index }}
          onSelect={(w, d) => navigate({ search: { week: w, day: d }, replace: true })}
        />
      </section>

      <details className="group flex flex-col gap-3">
        <summary className="flex min-h-11 cursor-pointer items-center text-lg font-semibold">
          Почему программа такая
        </summary>
        <Rationale text={program.rationale_ru} />
      </details>

      <Button asChild variant="outline" className="self-start">
        <Link to="/program/new">Собрать заново</Link>
      </Button>
    </div>
  )
}
