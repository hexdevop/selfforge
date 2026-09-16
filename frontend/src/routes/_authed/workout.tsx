import { useMutation, useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, redirect } from '@tanstack/react-router'
import { useMemo } from 'react'
import { exercisesQuery } from '@/api/catalog'
import { locationsQuery } from '@/api/locations'
import { profileQuery } from '@/api/profile'
import { inProgressQuery, nextSessionQuery, startWorkout, workoutQuery } from '@/api/sessions'
import { Button } from '@/components/ui/button'
import { ReadinessForm, type StartChoice } from '@/features/workout/readiness-form'
import { WorkoutScreen } from '@/features/workout/workout-screen'

export const Route = createFileRoute('/_authed/workout')({
  validateSearch: (search): { session?: string; place?: string } => ({
    session: typeof search.session === 'string' ? search.session : undefined,
    place: typeof search.place === 'string' ? search.place : undefined,
  }),
  beforeLoad: async ({ context: { queryClient }, search }) => {
    const profile = await queryClient.ensureQueryData(profileQuery)
    if (!profile.onboarding_completed_at) throw redirect({ to: '/onboarding' })
    if (search.session) return
    // Coming back to a workout left open resumes it; starting over would close it unfinished.
    const running = await queryClient.fetchQuery(inProgressQuery)
    if (running) throw redirect({ to: '/workout', search: { session: running.id }, replace: true })
  },
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(exercisesQuery),
      queryClient.ensureQueryData(locationsQuery),
      queryClient.ensureQueryData(nextSessionQuery),
    ]),
  component: WorkoutPage,
})

function WorkoutPage() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data: profile } = useSuspenseQuery(profileQuery)
  const { data: planned } = useSuspenseQuery(nextSessionQuery)
  const { data: locations } = useSuspenseQuery(locationsQuery)
  const { data: catalog } = useSuspenseQuery(exercisesQuery)
  const titles = useMemo(() => new Map(catalog.map((e) => [e.slug, e])), [catalog])

  const running = useQuery({ ...workoutQuery(search.session ?? ''), enabled: !!search.session })

  const start = useMutation({
    mutationFn: ({ readiness, unplanned, locationId }: StartChoice) =>
      startWorkout({
        readiness,
        unplanned,
        planned_session_id: unplanned ? null : (planned?.id ?? null),
        location_id: locationId,
      }),
    onSuccess: (session) => navigate({ search: { session: session.id }, replace: true }),
  })

  if (search.session) {
    if (running.isError) {
      return (
        <section className="flex max-w-prose flex-col items-start gap-4">
          <h1 className="text-2xl font-semibold">Тренировку не удалось открыть</h1>
          <p className="text-muted-foreground">
            Проверь связь и попробуй ещё раз. Отмеченные подходы сохранены на этом устройстве.
          </p>
          <Button onClick={() => running.refetch()}>Попробовать снова</Button>
        </section>
      )
    }
    if (!running.data) return <p className="text-muted-foreground">Загружаем тренировку…</p>
    if (running.data.status !== 'in_progress') {
      return (
        <section className="flex max-w-prose flex-col items-start gap-4">
          <h1 className="text-2xl font-semibold">Эта тренировка уже закрыта</h1>
          <p className="text-muted-foreground">
            {running.data.status === 'completed'
              ? 'Всё записано. Следующий день ждёт в программе.'
              : 'Она была остановлена. Можно начать новую.'}
          </p>
          <Button asChild>
            <Link to="/workout">Новая тренировка</Link>
          </Button>
        </section>
      )
    }
    return (
      <WorkoutScreen session={running.data} titles={titles} guidance={profile.guidance_level} />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <ReadinessForm
        planned={
          planned
            ? {
                id: planned.id ?? '',
                title: `День ${planned.day_index + 1} · ${planned.title_ru}`,
                minutes: planned.estimated_minutes,
                locationId: planned.location_id,
              }
            : null
        }
        locations={locations}
        pending={start.isPending}
        onStart={(choice) => start.mutate(choice)}
        initialPlace={search.place}
      />
      {start.isError && <p className="text-destructive">{start.error.message}</p>}
    </div>
  )
}
