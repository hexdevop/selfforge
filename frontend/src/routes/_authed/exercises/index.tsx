import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { equipmentQuery, exercisesQuery, patternsQuery } from '@/api/catalog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ExerciseRow } from '@/features/catalog/exercise-row'
import { BODYWEIGHT, type CatalogFilter, filterExercises } from '@/features/catalog/filter'
import { useEquipmentMap } from '@/features/catalog/use-equipment-map'
import { CATEGORY_LABELS, exercisesCount } from '@/lib/format'
import { cn } from '@/lib/utils'

const text = (value: unknown) => (typeof value === 'string' && value ? value : undefined)

export const Route = createFileRoute('/_authed/exercises/')({
  validateSearch: (search): CatalogFilter => ({
    pattern: text(search.pattern),
    equipment: text(search.equipment),
    q: text(search.q),
  }),
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(exercisesQuery),
      queryClient.ensureQueryData(patternsQuery),
      queryClient.ensureQueryData(equipmentQuery),
    ]),
  component: CatalogPage,
})

function CatalogPage() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data: exercises } = useSuspenseQuery(exercisesQuery)
  const { data: patterns } = useSuspenseQuery(patternsQuery)
  const { data: equipmentList } = useSuspenseQuery(equipmentQuery)
  const equipment = useEquipmentMap()

  const setFilter = (patch: CatalogFilter) =>
    navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true })

  const found = filterExercises(exercises, search)
  const groups = patterns
    .map((pattern) => ({ pattern, items: found.filter((e) => e.pattern_code === pattern.code) }))
    .filter((group) => group.items.length > 0)
  const selectedPattern = patterns.find((p) => p.code === search.pattern)
  const categories = Object.entries(CATEGORY_LABELS).map(([category, label]) => ({
    label,
    items: equipmentList.filter((item) => item.category === category),
  }))

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-2xl font-semibold">Упражнения</h1>

      <Input
        type="search"
        aria-label="Поиск по названию"
        placeholder="Найти по названию"
        value={search.q ?? ''}
        onChange={(event) => setFilter({ q: event.target.value || undefined })}
      />

      <fieldset className="-mx-4 flex min-w-0 gap-2 overflow-x-auto px-4 [scrollbar-width:none]">
        <legend className="sr-only">Паттерн движения</legend>
        {[{ code: undefined, title_ru: 'Все' }, ...patterns].map((pattern) => {
          const active = search.pattern === pattern.code
          return (
            <button
              key={pattern.code ?? 'all'}
              type="button"
              aria-pressed={active}
              onClick={() => setFilter({ pattern: pattern.code })}
              className={cn(
                'h-11 shrink-0 rounded-lg border px-3 text-base whitespace-nowrap outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
                active
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-card hover:bg-secondary',
              )}
            >
              {pattern.title_ru}
            </button>
          )
        })}
      </fieldset>

      <select
        aria-label="Оборудование"
        value={search.equipment ?? ''}
        onChange={(event) => setFilter({ equipment: event.target.value || undefined })}
        className="h-11 w-full rounded-md border border-input bg-card px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <option value="">Любое оборудование</option>
        <option value={BODYWEIGHT}>Без оборудования</option>
        {categories.map(({ label, items }) => (
          <optgroup key={label} label={label}>
            {items.map((item) => (
              <option key={item.code} value={item.code}>
                {item.title_ru}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-muted-foreground" aria-live="polite">
          {exercisesCount(found.length)}
        </p>
        {selectedPattern && (
          <Link
            to="/patterns/$code"
            params={{ code: selectedPattern.code }}
            className="font-medium underline underline-offset-4"
          >
            Лестница сложности
          </Link>
        )}
      </div>

      {groups.length === 0 ? (
        <div className="flex flex-col items-start gap-4 py-6">
          <p>Ничего не нашлось. Попробуй убрать фильтр или изменить запрос.</p>
          <Button variant="outline" onClick={() => navigate({ search: {}, replace: true })}>
            Сбросить фильтры
          </Button>
        </div>
      ) : (
        groups.map(({ pattern, items }) => (
          <section key={pattern.code} aria-labelledby={`pattern-${pattern.code}`}>
            <h2
              id={`pattern-${pattern.code}`}
              className="mb-1 border-b pb-2 text-sm font-medium text-muted-foreground"
            >
              {pattern.title_ru}
            </h2>
            <ul className="-mx-2">
              {items.map((exercise) => (
                <ExerciseRow key={exercise.slug} exercise={exercise} equipment={equipment} />
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}
