import { Link } from '@tanstack/react-router'
import type { ExerciseSummary } from '@/api/catalog'
import type { PlannedSession } from '@/api/programs'
import { BLOCK_HINTS, BLOCK_LABELS, restText, setsText } from './format'

type DayCardProps = {
  session: PlannedSession
  exercises: Map<string, ExerciseSummary>
  place: string
}

export function DayCard({ session, exercises, place }: DayCardProps) {
  return (
    <article className="flex flex-col gap-5 rounded-xl border bg-card p-4 sm:p-5">
      <header className="flex flex-col gap-1">
        <h3 className="text-lg font-semibold">
          День {session.day_index + 1} · {session.title_ru}
        </h3>
        <p className="text-muted-foreground tabular-nums">
          {place} · около {session.estimated_minutes} мин
        </p>
      </header>

      {session.blocks.map((block) => (
        <section key={block.kind} className="flex flex-col gap-1">
          <h4 className="text-sm text-muted-foreground tabular-nums">
            {BLOCK_LABELS[block.kind]} · {block.minutes} мин
          </h4>
          {block.exercises.length === 0 ? (
            <p>{BLOCK_HINTS[block.kind]}</p>
          ) : (
            <ol className="flex flex-col divide-y">
              {block.exercises.map((e) => {
                const exercise = exercises.get(e.exercise_slug)
                return (
                  <li
                    key={e.exercise_slug}
                    className="flex flex-wrap items-baseline justify-between gap-x-4 py-2"
                  >
                    <Link
                      to="/exercises/$slug"
                      params={{ slug: e.exercise_slug }}
                      className="font-medium underline-offset-4 hover:underline"
                    >
                      {exercise?.title_ru ?? e.exercise_slug}
                    </Link>
                    <span className="text-muted-foreground tabular-nums">
                      {setsText(e)}
                      {exercise?.is_unilateral && ' на сторону'} · {restText(e.rest_seconds)}
                    </span>
                  </li>
                )
              })}
            </ol>
          )}
        </section>
      ))}
    </article>
  )
}
