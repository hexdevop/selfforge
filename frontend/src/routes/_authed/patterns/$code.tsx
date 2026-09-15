import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, notFound } from '@tanstack/react-router'
import { equipmentQuery, exercisesQuery, patternsQuery } from '@/api/catalog'
import { ExerciseRow } from '@/features/catalog/exercise-row'
import { useEquipmentMap } from '@/features/catalog/use-equipment-map'

export const Route = createFileRoute('/_authed/patterns/$code')({
  loader: async ({ context: { queryClient }, params }) => {
    const [patterns] = await Promise.all([
      queryClient.ensureQueryData(patternsQuery),
      queryClient.ensureQueryData(exercisesQuery),
      queryClient.ensureQueryData(equipmentQuery),
    ])
    if (!patterns.some((p) => p.code === params.code)) throw notFound()
  },
  component: LadderPage,
})

function LadderPage() {
  const { code } = Route.useParams()
  const { data: patterns } = useSuspenseQuery(patternsQuery)
  const { data: exercises } = useSuspenseQuery(exercisesQuery)
  const equipment = useEquipmentMap()
  const pattern = patterns.find((p) => p.code === code)
  if (!pattern) return null

  // One difficulty scale per pattern; variants on other equipment share their step.
  const steps = new Map<number, typeof exercises>()
  for (const exercise of exercises.filter((e) => e.pattern_code === code)) {
    steps.set(exercise.difficulty_level, [
      ...(steps.get(exercise.difficulty_level) ?? []),
      exercise,
    ])
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <Link
          to="/exercises"
          search={{ pattern: code }}
          className="self-start underline underline-offset-4"
        >
          Упражнения паттерна
        </Link>
        <h1 className="mt-4 text-2xl font-semibold">Лестница: {pattern.title_ru.toLowerCase()}</h1>
        <p className="max-w-[70ch] text-muted-foreground">{pattern.description_ru}</p>
      </header>

      <ol className="flex flex-col">
        {[...steps].map(([level, items]) => (
          <li key={level} className="grid grid-cols-[3rem_1fr] gap-3 border-t py-3">
            <span className="pt-2.5 text-3xl leading-none font-bold tabular-nums">
              <span className="sr-only">Ступень </span>
              {level}
            </span>
            <ul className="-mx-2">
              {items.map((exercise) => (
                <ExerciseRow
                  key={exercise.slug}
                  exercise={exercise}
                  equipment={equipment}
                  showLevel={false}
                />
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </div>
  )
}
