import { useMutation, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useMemo } from 'react'
import { exercisesQuery } from '@/api/catalog'
import { markSkill, type SkillProgress, type SkillTarget, skillsQuery } from '@/api/progress'
import { Button } from '@/components/ui/button'
import { localDay, shortDate } from '@/features/progress/format'
import { plural } from '@/lib/format'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/_authed/progress/skills')({
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(skillsQuery),
      queryClient.ensureQueryData(exercisesQuery),
    ]),
  component: SkillsPage,
})

const GROUPS: { status: SkillProgress['status']; title: string; hint: string }[] = [
  { status: 'in_progress', title: 'В работе', hint: 'Предусловия выполнены — можно идти к цели' },
  { status: 'achieved', title: 'Освоено', hint: '' },
  {
    status: 'locked',
    title: 'Дальше',
    hint: 'Откроются, когда будут выполнены предусловия',
  },
]

function SkillsPage() {
  const { data: skills } = useSuspenseQuery(skillsQuery)
  const { data: catalog } = useSuspenseQuery(exercisesQuery)
  const titles = useMemo(() => new Map(catalog.map((e) => [e.slug, e.title_ru])), [catalog])
  const titleOf = (slug: string) => titles.get(slug) ?? slug

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <Link to="/progress" className="self-start underline underline-offset-4">
          Прогресс
        </Link>
        <h1 className="text-2xl font-semibold">Навыки</h1>
        <p className="text-muted-foreground">
          Засчитываются по твоим тренировкам: лучший подход, одинаковый на обе стороны.
        </p>
      </header>

      {GROUPS.map((group) => {
        const list = skills.filter((s) => s.status === group.status)
        if (list.length === 0) return null
        return (
          <section key={group.status} className="flex flex-col gap-3">
            <div>
              <h2 className="text-lg font-semibold">{group.title}</h2>
              {group.hint && <p className="text-sm text-muted-foreground">{group.hint}</p>}
            </div>
            <ul className="flex flex-col gap-3">
              {list.map((skill) => (
                <li key={skill.skill_slug}>
                  <SkillCard skill={skill} titleOf={titleOf} />
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

function targetText(target: SkillTarget, titleOf: (slug: string) => string): string {
  const need = target.reps ?? target.hold_seconds ?? 0
  const unit = target.hold_seconds ? 'с' : plural(need, ['повтор', 'повтора', 'повторов'])
  return `${titleOf(target.exercise_slug)} — ${need} ${unit}`
}

function Progress({ target }: { target: SkillTarget }) {
  const need = target.reps ?? target.hold_seconds ?? 1
  const best = target.best ?? 0
  const share = Math.min(1, best / need)
  return (
    <div className="flex items-center gap-3">
      <div
        className="h-2 grow overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={need}
        aria-valuenow={Math.min(best, need)}
      >
        <div className="h-full rounded-full bg-foreground" style={{ width: `${share * 100}%` }} />
      </div>
      <span className="w-20 text-right text-sm tabular-nums">
        {target.met ? 'выполнено' : `${best} / ${need}`}
      </span>
    </div>
  )
}

function SkillCard({
  skill,
  titleOf,
}: {
  skill: SkillProgress
  titleOf: (slug: string) => string
}) {
  const queryClient = useQueryClient()
  const mark = useMutation({
    mutationFn: (achieved: boolean) => markSkill(skill.skill_slug, achieved),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['progress', 'skills'] }),
  })
  const achieved = skill.status === 'achieved'

  return (
    <article className="flex flex-col gap-3 rounded-xl border bg-card p-4">
      <header className="flex flex-col gap-1">
        <h3 className="text-lg font-semibold">{skill.title_ru}</h3>
        {achieved && skill.achieved_at && (
          <p className="text-sm">
            <span className="font-medium text-heat">Освоено</span> ·{' '}
            {shortDate(localDay(skill.achieved_at))}
          </p>
        )}
        <p className="text-muted-foreground">{skill.description_ru}</p>
      </header>

      {skill.goal && (
        <div className="flex flex-col gap-1">
          <p className="text-sm">Цель: {targetText(skill.goal, titleOf)}</p>
          <Progress target={skill.goal} />
        </div>
      )}

      {skill.prerequisites.length > 0 && !achieved && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">Чтобы начать</p>
          {skill.prerequisites.map((p) => (
            <div key={p.exercise_slug} className="flex flex-col gap-1">
              <p className="text-sm">{targetText(p, titleOf)}</p>
              <Progress target={p} />
            </div>
          ))}
        </div>
      )}

      {!achieved && (
        <p className="text-sm">
          Подводящие упражнения:{' '}
          {skill.lead_up_exercise_slugs.map((slug, i) => (
            <span key={slug}>
              {i > 0 && ', '}
              <Link
                to="/exercises/$slug"
                params={{ slug }}
                className={cn(
                  'underline underline-offset-4',
                  slug === skill.current_lead_up_slug && 'font-medium',
                )}
              >
                {titleOf(slug)}
              </Link>
            </span>
          ))}
        </p>
      )}

      {skill.goal === null && (
        <div className="flex flex-col items-start gap-1">
          <p className="text-sm text-muted-foreground">
            Этот навык по подходам не проверить — отметь сам, когда получится.
          </p>
          <Button
            variant={achieved ? 'ghost' : 'outline'}
            disabled={mark.isPending}
            onClick={() => mark.mutate(!achieved)}
          >
            {achieved ? 'Снять отметку' : 'Получилось'}
          </Button>
        </div>
      )}
      {mark.isError && <p className="text-sm text-destructive">{mark.error.message}</p>}
    </article>
  )
}
