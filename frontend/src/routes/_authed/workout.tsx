import { useMutation, useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, redirect } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { exercisesQuery } from '@/api/catalog'
import { profileQuery } from '@/api/profile'
import { activeProgramQuery } from '@/api/programs'
import { nextSessionQuery, type Readiness, startWorkout, workoutQuery } from '@/api/sessions'
import { Button } from '@/components/ui/button'
import { ReadinessForm } from '@/features/workout/readiness-form'
import { WorkoutScreen } from '@/features/workout/workout-screen'

export const Route = createFileRoute('/_authed/workout')({
  validateSearch: (search): { session?: string } => ({
    session: typeof search.session === 'string' ? search.session : undefined,
  }),
  beforeLoad: async ({ context: { queryClient } }) => {
    if (!(await queryClient.ensureQueryData(activeProgramQuery))) {
      throw redirect({ to: '/program/new' })
    }
  },
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(exercisesQuery),
      queryClient.ensureQueryData(profileQuery),
      queryClient.ensureQueryData(nextSessionQuery),
    ]),
  component: WorkoutPage,
})

function WorkoutPage() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data: profile } = useSuspenseQuery(profileQuery)
  const { data: planned } = useSuspenseQuery(nextSessionQuery)
  const { data: catalog } = useSuspenseQuery(exercisesQuery)
  const titles = useMemo(() => new Map(catalog.map((e) => [e.slug, e])), [catalog])
  const [note, setNote] = useState<string | null>(null)

  const running = useQuery({ ...workoutQuery(search.session ?? ''), enabled: !!search.session })

  const start = useMutation({
    mutationFn: (readiness: Readiness) =>
      startWorkout({ planned_session_id: planned?.id ?? null, readiness }),
    onSuccess: (session) => navigate({ search: { session: session.id }, replace: true }),
    onError: (error: Error) => setNote(error.message),
  })

  if (search.session) {
    if (!running.data) return <p className="text-muted-foreground">Загружаем тренировку…</p>
    if (running.data.status !== 'in_progress') {
      return (
        <section className="flex max-w-prose flex-col items-start gap-4">
          <h1 className="text-2xl font-semibold">Эта тренировка уже закрыта</h1>
          <p className="text-muted-foreground">
            {running.data.status === 'completed'
              ? 'Всё записано. Следующий день ждёт в программе.'
              : 'Она была остановлена. Можно начать день заново.'}
          </p>
          <Button asChild>
            <Link to="/program">К программе</Link>
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
        title={planned ? `День ${planned.day_index + 1} · ${planned.title_ru}` : 'Тренировка'}
        subtitle={
          planned
            ? `Около ${planned.estimated_minutes} минут. Три вопроса — и начинаем.`
            : 'Три вопроса — и начинаем.'
        }
        pending={start.isPending}
        onStart={(readiness) => start.mutate(readiness)}
      />
      {note && <p className="text-destructive">{note}</p>}
    </div>
  )
}
