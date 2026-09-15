import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, redirect } from '@tanstack/react-router'
import { useMe } from '@/api/auth'
import { locationsQuery } from '@/api/locations'
import { profileQuery } from '@/api/profile'
import { activeProgramQuery } from '@/api/programs'
import { Button } from '@/components/ui/button'
import { exercisesCount } from '@/lib/format'

export const Route = createFileRoute('/_authed/')({
  beforeLoad: async ({ context: { queryClient } }) => {
    const profile = await queryClient.ensureQueryData(profileQuery)
    if (!profile.onboarding_completed_at) throw redirect({ to: '/onboarding' })
  },
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(locationsQuery),
      queryClient.ensureQueryData(activeProgramQuery),
    ]),
  component: Cabinet,
})

function Cabinet() {
  const user = useMe()
  const { data: locations } = useSuspenseQuery(locationsQuery)
  const { data: program } = useSuspenseQuery(activeProgramQuery)
  if (!user) return null

  return (
    <section className="flex max-w-prose flex-col items-start gap-6">
      <h1 className="text-2xl font-semibold">Привет, {user.full_name || user.username}!</h1>
      {program ? (
        <p>Программа собрана: открой её, чтобы посмотреть день и весь цикл.</p>
      ) : (
        <p>
          Всё готово, чтобы собрать программу под твою цель и твоё железо. Сначала покажем, что
          получилось и почему, — начнёшь, когда устроит.
        </p>
      )}
      <Button asChild size="lg">
        <Link to={program ? '/program' : '/program/new'}>
          {program ? 'Открыть программу' : 'Собрать программу'}
        </Link>
      </Button>

      <h2 className="mt-4 text-lg font-semibold">Места</h2>
      <ul className="flex w-full flex-col">
        {locations.map((location) => (
          <li key={location.id} className="flex justify-between gap-4 border-t py-3">
            <span className="font-medium">{location.title}</span>
            <span className="text-muted-foreground">
              доступно {exercisesCount(location.available_exercise_count)}
            </span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-3">
        <Button asChild variant="outline">
          <Link to="/locations">Места и инвентарь</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/exercises">Упражнения</Link>
        </Button>
      </div>
    </section>
  )
}
