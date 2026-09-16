import { useQuery, useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { exercisesQuery, type PatternCode, patternsQuery } from '@/api/catalog'
import {
  balanceQuery,
  type PersonalRecord,
  patternProgressQuery,
  recordsQuery,
  summaryQuery,
  weeklyTonnageQuery,
  workoutDaysQuery,
} from '@/api/progress'
import { ChoiceGroup } from '@/components/choice-group'
import { Button } from '@/components/ui/button'
import {
  ChartFrame,
  DataTable,
  LevelChart,
  ResultChart,
  WeeklyBars,
} from '@/features/progress/charts'
import {
  fillWeeks,
  levelSeries,
  localDay,
  monthGrid,
  RESULT_LABELS,
  resultSeries,
  resultText,
  shortDate,
  streakText,
} from '@/features/progress/format'
import { formatKg, plural } from '@/lib/format'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/_authed/progress/')({
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(summaryQuery),
      queryClient.ensureQueryData(exercisesQuery),
      queryClient.ensureQueryData(patternsQuery),
    ]),
  component: ProgressPage,
})

const WORKOUTS: [string, string, string] = ['тренировка', 'тренировки', 'тренировок']

function ProgressPage() {
  const { data: summary } = useSuspenseQuery(summaryQuery)
  const { data: catalog } = useSuspenseQuery(exercisesQuery)
  const titles = useMemo(() => new Map(catalog.map((e) => [e.slug, e])), [catalog])
  const titleOf = (slug: string) => titles.get(slug)?.title_ru ?? slug

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Прогресс</h1>
        <nav className="flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <Link to="/progress/skills">Навыки</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/body">Тело и замеры</Link>
          </Button>
        </nav>
      </header>

      <section className="flex flex-col gap-3" aria-labelledby="week">
        <h2 id="week" className="sr-only">
          Эта неделя
        </h2>
        <p className="text-lg font-medium">{streakText(summary.week_streak)}</p>
        <dl className="grid grid-cols-2 gap-4">
          <Stat
            term="На этой неделе"
            value={String(summary.this_week.workouts)}
            unit={plural(summary.this_week.workouts, WORKOUTS)}
          />
          <Stat
            term="Поднято за неделю"
            value={formatKg(Math.round(Number(summary.this_week.tonnage_kg)))}
            unit="кг"
          />
        </dl>
        {summary.near_records.length > 0 && (
          <ul className="flex flex-col gap-1">
            {summary.near_records.map((n) => (
              <li key={n.exercise_slug} className="flex gap-2">
                <span aria-hidden className="text-heat">
                  ●
                </span>
                {n.text_ru}
              </li>
            ))}
          </ul>
        )}
      </section>

      <Balance titleOf={titleOf} />
      <PatternCharts titleOf={titleOf} />
      <Tonnage />
      <WorkoutCalendar />
      <Records titleOf={titleOf} timedOf={(slug) => titles.get(slug)?.timed ?? false} />
    </div>
  )
}

function Stat({ term, value, unit }: { term: string; value: string; unit: string }) {
  return (
    <div className="flex min-w-0 flex-col rounded-xl border bg-card p-4">
      <dt className="text-sm text-muted-foreground">{term}</dt>
      <dd className="flex flex-col">
        <span className="text-4xl font-bold tabular-nums">{value}</span>
        <span className="text-sm text-muted-foreground">{unit}</span>
      </dd>
    </div>
  )
}

function Balance({ titleOf }: { titleOf: (slug: string) => string }) {
  const { data } = useQuery(balanceQuery)
  if (!data?.length) return null
  return (
    <section className="flex flex-col gap-3 rounded-xl border bg-card p-4">
      <h2 className="text-lg font-semibold">Баланс сторон</h2>
      {data.map((gap) => (
        <div key={gap.exercise_slug} className="flex flex-col gap-1">
          <p className="font-medium">{titleOf(gap.exercise_slug)}</p>
          <p className="tabular-nums text-muted-foreground">
            левая {formatKg(gap.left_avg)} · правая {formatKg(gap.right_avg)} повторов в среднем
          </p>
          <p>{gap.advice_ru}</p>
        </div>
      ))}
    </section>
  )
}

function PatternCharts({ titleOf }: { titleOf: (slug: string) => string }) {
  const { data: patterns } = useSuspenseQuery(patternsQuery)
  const [code, setCode] = useState<PatternCode>('squat')
  const { data } = useQuery(patternProgressQuery(code))
  const points = data?.points ?? []
  const levels = levelSeries(points)
  const results = resultSeries(points)
  const format = (value: number) =>
    results.kind ? resultText({ kind: results.kind, value: String(value) }) : String(value)

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">По движениям</h2>
      <ChoiceGroup
        legend={<span className="sr-only">Движение</span>}
        name="pattern"
        choices={patterns.map((p) => ({ value: p.code, label: p.title_ru }))}
        selected={[code]}
        onSelect={(value) => setCode(value as PatternCode)}
      />
      {!data ? (
        <p className="text-muted-foreground">Загружаем…</p>
      ) : points.length === 0 ? (
        <p className="text-muted-foreground">
          Этого движения ещё не было в тренировках. Как только появится — здесь будет видно, как оно
          растёт.
        </p>
      ) : (
        <>
          <ChartFrame
            title="Ступень лестницы"
            hint="Самый сложный вариант, сделанный на тренировке"
            table={
              <DataTable
                head={['Дата', 'Упражнение', 'Ступень']}
                rows={levels.map((p) => [shortDate(p.day), titleOf(p.exercise), p.level])}
              />
            }
          >
            <LevelChart data={levels} titleOf={titleOf} />
          </ChartFrame>
          {results.kind && (
            <ChartFrame
              title={RESULT_LABELS[results.kind]}
              hint={`На текущей ступени: ${titleOf(results.exercise ?? '')}`}
              table={
                <DataTable
                  head={['Дата', 'Упражнение', 'Результат']}
                  rows={results.data.map((p) => [
                    shortDate(p.day),
                    titleOf(p.exercise),
                    format(p.value),
                  ])}
                />
              }
            >
              <ResultChart data={results.data} format={format} titleOf={titleOf} />
            </ChartFrame>
          )}
        </>
      )}
    </section>
  )
}

function Tonnage() {
  const { data } = useQuery(weeklyTonnageQuery)
  if (!data?.length) return null
  const bars = fillWeeks(
    data.map((w) => ({ day: w.starts_on, value: Number(w.tonnage_kg) })),
  ).slice(-12)
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Объём</h2>
      <ChartFrame
        title="Тоннаж по неделям, кг"
        hint="Вес снаряда плюс доля веса тела в упражнениях, где двигается тело"
        table={
          <DataTable
            head={['Неделя с', 'Кг']}
            rows={bars.map((b) => [shortDate(b.day), formatKg(b.value)])}
          />
        }
      >
        <WeeklyBars data={bars} />
      </ChartFrame>
    </section>
  )
}

const monthTitle = new Intl.DateTimeFormat('ru', { month: 'long', year: 'numeric' })
const WEEKDAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']

function WorkoutCalendar() {
  const { data } = useQuery(workoutDaysQuery)
  const [month, setMonth] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const trained = useMemo(() => new Set((data ?? []).map(localDay)), [data])
  const weeks = monthGrid(month.getFullYear(), month.getMonth(), trained)
  const shift = (by: number) => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + by, 1))
  const inMonth = weeks.flat().filter((d) => d.inMonth && d.trained).length

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold first-letter:uppercase">{monthTitle.format(month)}</h2>
        <div className="flex">
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-11"
            aria-label="Предыдущий месяц"
            onClick={() => shift(-1)}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-11"
            aria-label="Следующий месяц"
            onClick={() => shift(1)}
          >
            <ChevronRight />
          </Button>
        </div>
      </div>
      <p className="text-muted-foreground">
        {inMonth === 0
          ? 'В этом месяце тренировок пока нет'
          : `${inMonth} ${plural(inMonth, ['день', 'дня', 'дней'])} с тренировкой`}
      </p>
      <table className="w-full table-fixed text-center tabular-nums">
        <thead>
          <tr className="text-sm text-muted-foreground">
            {WEEKDAYS.map((d) => (
              <th key={d} className="pb-1 font-normal">
                {d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week) => (
            <tr key={week[0]?.iso}>
              {week.map((day) => (
                <td key={day.iso} className="p-0.5">
                  <span
                    className={cn(
                      'flex h-10 items-center justify-center rounded-lg',
                      !day.inMonth && 'text-muted-foreground/60',
                      day.trained && 'bg-primary font-semibold text-primary-foreground',
                    )}
                  >
                    {day.day}
                    {day.trained && <span className="sr-only">, была тренировка</span>}
                  </span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

const RECORD_LABELS: Record<PersonalRecord['kind'], string> = {
  max_weight: 'Самый большой вес',
  max_reps: 'Лучший подход',
  est_1rm: 'Расчётный максимум',
  max_volume: 'Больше всего за подход',
}

function Records({
  titleOf,
  timedOf,
}: {
  titleOf: (slug: string) => string
  timedOf: (slug: string) => boolean
}) {
  const { data } = useQuery(recordsQuery)
  if (!data) return null

  const byExercise = new Map<string, PersonalRecord[]>()
  for (const r of data)
    byExercise.set(r.exercise_slug, [...(byExercise.get(r.exercise_slug) ?? []), r])
  const value = (r: PersonalRecord) => {
    const n = Number(r.value)
    if (r.kind === 'max_reps')
      return timedOf(r.exercise_slug)
        ? `${n} с`
        : `${n} ${plural(n, ['повтор', 'повтора', 'повторов'])}`
    return `${formatKg(n)} кг`
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Рекорды</h2>
      {data.length === 0 ? (
        <p className="text-muted-foreground">
          Первые рекорды появятся после первой тренировки — любой результат с чего-то начинается.
        </p>
      ) : (
        <ul className="flex flex-col">
          {[...byExercise].map(([slug, records]) => (
            <li key={slug} className="flex flex-col gap-1 border-t py-3">
              <span className="font-medium">{titleOf(slug)}</span>
              <dl className="grid grid-cols-[1fr_auto] gap-x-4 text-sm">
                {records.map((r) => (
                  <div key={r.kind} className="contents">
                    <dt className="text-muted-foreground">{RECORD_LABELS[r.kind]}</dt>
                    <dd className="text-right tabular-nums">
                      {value(r)} · {shortDate(localDay(r.achieved_at))}
                    </dd>
                  </div>
                ))}
              </dl>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
