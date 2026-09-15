import { keepPreviousData, useQuery, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, redirect, useNavigate } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { exercisesQuery } from '@/api/catalog'
import { api } from '@/api/client'
import { locationsQuery } from '@/api/locations'
import { profileQuery } from '@/api/profile'
import { activeProgramQuery, programPreviewQuery } from '@/api/programs'
import { FormError } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { DayCard } from '@/features/program/day-card'
import { DayPlaces } from '@/features/program/day-places'
import { STRUCTURE_LABELS, weeksText } from '@/features/program/format'
import { initialPlaces } from '@/features/program/places'
import { Rationale } from '@/features/program/rationale'

export const Route = createFileRoute('/_authed/program/new')({
  beforeLoad: async ({ context: { queryClient } }) => {
    const profile = await queryClient.ensureQueryData(profileQuery)
    if (!profile.onboarding_completed_at) throw redirect({ to: '/onboarding' })
  },
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(locationsQuery),
      queryClient.ensureQueryData(activeProgramQuery),
      queryClient.ensureQueryData(exercisesQuery),
    ]),
  component: NewProgramPage,
})

function NewProgramPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: profile } = useSuspenseQuery(profileQuery)
  const { data: locations } = useSuspenseQuery(locationsQuery)
  const { data: active } = useSuspenseQuery(activeProgramQuery)
  const { data: catalog } = useSuspenseQuery(exercisesQuery)
  const exercises = useMemo(() => new Map(catalog.map((e) => [e.slug, e])), [catalog])

  const [places, setPlaces] = useState(() =>
    initialPlaces(active, locations, profile.days_per_week ?? 0),
  )
  const preview = useQuery({ ...programPreviewQuery(places), placeholderData: keepPreviousData })
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string>()

  const placeOf = (id: string | null) =>
    locations.find((l) => l.id === id)?.title ?? 'Место удалено'

  const start = async () => {
    setError(undefined)
    setStarting(true)
    try {
      const { data, error } = await api.POST('/api/v1/programs', {
        body: { day_locations: places },
      })
      if (!data) return setError(error?.detail.message)
      queryClient.setQueryData(activeProgramQuery.queryKey, data)
      await navigate({ to: '/program' })
    } catch {
      setError('Нет связи с сервером. Проверь интернет и попробуй ещё раз')
    } finally {
      setStarting(false)
    }
  }

  const draft = preview.data
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Твоя программа</h1>
        <p className="max-w-[70ch] text-muted-foreground">
          Посмотри, что получилось, и начни, когда всё устраивает. Цель, число дней и длительность
          меняются в шаге{' '}
          <Link
            to="/onboarding"
            search={{ step: 'goal' }}
            className="text-foreground underline underline-offset-4"
          >
            «Цель и расписание»
          </Link>
          , снаряды — в разделе{' '}
          <Link to="/locations" className="text-foreground underline underline-offset-4">
            «Места»
          </Link>
          .
        </p>
      </header>

      {locations.length > 1 && (
        <DayPlaces value={places} locations={locations} onChange={setPlaces} />
      )}

      {preview.isError && <FormError message={preview.error.message} />}
      {!draft && preview.isPending && <p aria-live="polite">Собираем программу…</p>}

      {draft && (
        <div
          className="flex flex-col gap-8 transition-opacity aria-busy:opacity-60"
          aria-busy={preview.isFetching}
        >
          <section className="flex flex-col gap-3">
            <p className="text-muted-foreground">
              {STRUCTURE_LABELS[draft.structure]} · {weeksText(draft.weeks_total)}
            </p>
            <h2 className="text-lg font-semibold">Почему она такая</h2>
            <Rationale text={draft.rationale_ru} />
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold">Первая неделя</h2>
            <div className="grid gap-4 lg:grid-cols-2">
              {draft.weeks[0]?.sessions.map((session) => (
                <DayCard
                  key={session.day_index}
                  session={session}
                  exercises={exercises}
                  place={placeOf(session.location_id)}
                />
              ))}
            </div>
          </section>

          <div className="flex flex-col items-start gap-3">
            {active && (
              <p className="text-muted-foreground">
                Текущая программа закончится, и с сегодняшнего дня пойдёт эта.
              </p>
            )}
            <FormError message={error} />
            <Button size="lg" onClick={start} disabled={starting || preview.isFetching}>
              Начать программу
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
