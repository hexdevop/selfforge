import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, notFound } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { equipmentQuery, exerciseQuery, exercisesQuery, patternsQuery } from '@/api/catalog'
import {
  criteriaText,
  equipmentText,
  featureNotes,
  HEALTH_LABELS,
  listRu,
  MUSCLE_LABELS,
} from '@/features/catalog/labels'
import { useEquipmentMap } from '@/features/catalog/use-equipment-map'

export const Route = createFileRoute('/_authed/exercises/$slug')({
  loader: async ({ context: { queryClient }, params }) => {
    const [exercise] = await Promise.all([
      queryClient.ensureQueryData(exerciseQuery(params.slug)),
      queryClient.ensureQueryData(exercisesQuery),
      queryClient.ensureQueryData(patternsQuery),
      queryClient.ensureQueryData(equipmentQuery),
    ])
    if (!exercise) throw notFound()
  },
  component: ExercisePage,
})

function ExercisePage() {
  const { slug } = Route.useParams()
  const exercise = useSuspenseQuery(exerciseQuery(slug)).data
  const { data: all } = useSuspenseQuery(exercisesQuery)
  const { data: patterns } = useSuspenseQuery(patternsQuery)
  const equipment = useEquipmentMap()
  if (!exercise) return null

  const pattern = patterns.find((p) => p.code === exercise.pattern_code)
  const siblings = all.filter((e) => e.pattern_code === exercise.pattern_code)
  const maxLevel = Math.max(...siblings.map((e) => e.difficulty_level))
  const bySlug = (s: string | null) => all.find((e) => e.slug === s)
  const prev = bySlug(exercise.prev_slug)
  const next = bySlug(exercise.next_slug)
  const criteria = criteriaText(exercise)
  const notes = featureNotes(exercise)
  const muscles = (list: typeof exercise.primary_muscles) =>
    listRu(list.map((m) => MUSCLE_LABELS[m]))

  return (
    <article className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <Link to="/exercises" className="self-start text-base underline underline-offset-4">
          Все упражнения
        </Link>
        <p className="mt-4 text-muted-foreground">
          <Link
            to="/patterns/$code"
            params={{ code: exercise.pattern_code }}
            className="underline underline-offset-4"
          >
            {pattern?.title_ru}
          </Link>
          {' · '}
          <span className="tabular-nums">
            ступень {exercise.difficulty_level} из {maxLevel}
          </span>
        </p>
        <h1 className="text-2xl font-semibold">{exercise.title_ru}</h1>
      </header>

      <dl className="grid gap-x-6 sm:grid-cols-[max-content_1fr] sm:gap-y-3">
        <Fact term="Оборудование">{equipmentText(exercise.required_equipment, equipment)}</Fact>
        <Fact term="Основные мышцы">{muscles(exercise.primary_muscles)}</Fact>
        {exercise.secondary_muscles.length > 0 && (
          <Fact term="Помогают">{muscles(exercise.secondary_muscles)}</Fact>
        )}
        {notes.length > 0 && (
          <Fact term="Особенности">
            <ul>
              {notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </Fact>
        )}
        {exercise.contraindicated_for.length > 0 && (
          <Fact term="Не подходит при ограничениях">
            {listRu(exercise.contraindicated_for.map((tag) => HEALTH_LABELS[tag]))}
          </Fact>
        )}
      </dl>

      <Section title="Техника">
        <p className="max-w-[70ch]">{exercise.technique_ru}</p>
      </Section>

      <Section title="Типичные ошибки">
        <ul className="flex max-w-[70ch] list-disc flex-col gap-1 pl-5">
          {exercise.common_mistakes_ru.map((mistake) => (
            <li key={mistake}>{mistake}</li>
          ))}
        </ul>
      </Section>

      {(prev || next) && (
        <Section title="Лестница">
          {criteria && next && (
            <p className="mb-4 max-w-[70ch]">
              Чтобы перейти дальше, выполни {criteria} с хорошей техникой.
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {prev && <StepLink label="Проще" slug={prev.slug} title={prev.title_ru} />}
            {next && <StepLink label="Сложнее" slug={next.slug} title={next.title_ru} />}
          </div>
        </Section>
      )}
    </article>
  )
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-sm text-muted-foreground sm:text-base">{term}</dt>
      <dd className="mb-4 sm:mb-0">{children}</dd>
    </>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function StepLink({ label, slug, title }: { label: string; slug: string; title: string }) {
  return (
    <Link
      to="/exercises/$slug"
      params={{ slug }}
      className="flex min-h-11 flex-col rounded-lg border bg-card px-4 py-3 hover:bg-secondary"
    >
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="font-semibold">{title}</span>
    </Link>
  )
}
