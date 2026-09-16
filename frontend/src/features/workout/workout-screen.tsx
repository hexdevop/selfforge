import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import type { ExerciseSummary } from '@/api/catalog'
import { locationsQuery } from '@/api/locations'
import type { GuidanceLevel } from '@/api/profile'
import {
  abortWorkout,
  finishWorkout,
  type SetLogIn,
  type Side,
  type SubstitutionReason,
  substituteExercise,
  trimWorkout,
  type WorkoutSession,
} from '@/api/sessions'
import { swapLocation } from '@/api/weather'
import { Button } from '@/components/ui/button'
import { WeatherNotice } from '@/features/weather/weather-notice'
import { formatKg } from '@/lib/format'
import { cn } from '@/lib/utils'
import { primeChime } from './chime'
import { ReasonPicker, TimePicker } from './pickers'
import {
  completedSets,
  currentIndex,
  doneSets,
  isSetComplete,
  nextSet,
  suggestedReps,
  workExercises,
  workoutIsDone,
} from './progress'
import { isStale, useQueue } from './queue'
import { RestTimer } from './rest-timer'
import { useScreenAwake } from './screen-awake'
import { SetEditor } from './set-editor'
import { Technique } from './technique'

type WorkoutScreenProps = {
  session: WorkoutSession
  titles: Map<string, ExerciseSummary>
  guidance: GuidanceLevel
}

type Panel = 'none' | 'technique' | 'substitute' | 'time'

export function WorkoutScreen({ session, titles, guidance }: WorkoutScreenProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { logged, pending, failingSince, restStartedAt, enqueue, flush, open, close } = useQueue()
  const { startRest, skipRest } = useQueue()
  const [picked, setPicked] = useState<number | null>(null)
  const [panel, setPanel] = useState<Panel>(guidance === 'verbose' ? 'technique' : 'none')
  const [reps, setReps] = useState<number | null>(null)
  const [weight, setWeight] = useState<string | null>(null)

  const exercises = useMemo(() => workExercises(session), [session])
  const index = picked ?? currentIndex(session, logged)
  const exercise = exercises[Math.min(index, exercises.length - 1)]
  const at = exercise ? nextSet(logged, exercise) : { index: 0, side: 'both' as Side }

  useScreenAwake(session.status === 'in_progress')

  // No cleanup on unmount: leaving the screen must not drop sets still on their way.
  useEffect(() => {
    open(session.id, session.sets as SetLogIn[])
  }, [session.id, session.sets, open])

  // Leaving with sets still in the buffer would lose them; the browser asks first.
  useEffect(() => {
    if (pending.length === 0) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [pending.length])

  // Coming back from the background is the best moment to retry a stuck buffer.
  useEffect(() => {
    const retry = () => {
      if (document.visibilityState === 'visible') void flush()
    }
    document.addEventListener('visibilitychange', retry)
    window.addEventListener('online', retry)
    return () => {
      document.removeEventListener('visibilitychange', retry)
      window.removeEventListener('online', retry)
    }
  }, [flush])

  const { data: locations } = useQuery(locationsQuery)
  const place = locations?.find((l) => l.id === session.location_id)
  const moveIndoors = useMutation({
    mutationFn: async (locationId: string) => {
      // Sets on their way belong to exercises that stay; send them before the plan changes.
      await flush()
      return swapLocation(session.id, locationId)
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(['sessions', session.id], updated)
      setPicked(null)
      setReps(null)
      setWeight(null)
    },
  })

  const reshape = useMutation({
    mutationFn: async (action: { substitute?: SubstitutionReason; minutes?: number }) => {
      if (!exercise) throw new Error('Нечего менять')
      return action.substitute
        ? substituteExercise(session.id, {
            exercise_slug: exercise.exercise_slug,
            reason: action.substitute,
          })
        : trimWorkout(session.id, action.minutes ?? 15)
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(['sessions', session.id], updated)
      setPanel('none')
      setPicked(null)
      setReps(null)
      setWeight(null)
    },
  })

  const closeOut = useMutation({
    mutationFn: async (how: 'finish' | 'abort') => {
      await flush()
      // A closed workout takes no more sets: closing now would lose the ones still waiting.
      if (useQueue.getState().pending.length > 0) {
        throw new Error('Подходы ещё не ушли на сервер. Как появится связь — заверши снова.')
      }
      return how === 'finish' ? finishWorkout(session.id) : abortWorkout(session.id)
    },
    onSuccess: async (updated) => {
      close()
      queryClient.setQueryData(['sessions', session.id], updated)
      await queryClient.invalidateQueries({ queryKey: ['programs'] })
      await queryClient.invalidateQueries({ queryKey: ['sessions'] })
      await navigate({ to: '/program' })
    },
  })

  if (!exercise) return null

  const done = doneSets(logged, exercise.exercise_slug)
  const currentWeight = weight ?? exercise.weight_kg
  const currentReps = reps ?? suggestedReps(exercise, logged, at)
  const title = titles.get(exercise.exercise_slug)?.title_ru ?? exercise.exercise_slug
  const slots = Array.from({ length: Math.max(exercise.sets, done.length) }, (_, i) => {
    const set = done.find((s) => s.index === i)
    return { index: i, set, complete: isSetComplete(set, exercise.unilateral) }
  })

  const confirm = () => {
    primeChime()
    enqueue({
      client_uuid: crypto.randomUUID(),
      exercise_slug: exercise.exercise_slug,
      set_index: at.index,
      side: at.side,
      reps: currentReps,
      weight_kg: currentWeight,
      tempo: exercise.tempo,
      performed_at: new Date().toISOString(),
    })
    setReps(null)
    setWeight(null)
    setPicked(null)
    // Rest only starts once the set is really over — for one-sided work, after both sides.
    if (at.side === 'left') skipRest()
    else startRest()
  }

  return (
    <div className="flex flex-col gap-6 pb-10">
      <header className="flex flex-col gap-1">
        <p className="flex flex-wrap items-baseline justify-between gap-x-4 text-muted-foreground">
          <span>
            {session.blocks.find((b) => b.exercises.includes(exercise))?.kind === 'main'
              ? 'Основное движение'
              : 'Вспомогательное'}
          </span>
          <span className="tabular-nums">
            {index + 1} из {exercises.length}
          </span>
        </p>
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-muted-foreground tabular-nums">
          подход {Math.min(at.index + 1, exercise.sets)} из {exercise.sets} · {exercise.target_min}–
          {exercise.target_max}
          {exercise.timed ? ' с' : ''}
          {exercise.tempo && ` · темп ${exercise.tempo}`}
        </p>
      </header>

      {place && (
        <WeatherNotice
          location={place}
          onlyWhenBad
          moveIndoors={{
            label: 'Перенести тренировку домой',
            onClick: (id) => moveIndoors.mutate(id),
            pending: moveIndoors.isPending,
          }}
        />
      )}
      {moveIndoors.isError && <p className="text-destructive">{moveIndoors.error.message}</p>}

      <Notes notes={session.notes_ru} />

      {exercise.hint_ru && <p className="text-muted-foreground">{exercise.hint_ru}</p>}

      <SetEditor
        exercise={exercise}
        side={at.side}
        reps={currentReps}
        weightKg={currentWeight}
        onReps={setReps}
        onWeight={setWeight}
        onConfirm={confirm}
      />

      <ol className="flex flex-wrap gap-x-5 gap-y-1 tabular-nums">
        {slots.map(({ index: slot, set, complete }) => (
          <li
            key={`${exercise.exercise_slug}-${slot}`}
            className={cn('flex gap-2', complete ? 'font-medium' : 'text-muted-foreground')}
          >
            <span aria-hidden>{complete ? '✓' : '○'}</span>
            {set ? (
              <span>
                {set.weightKg && `${formatKg(set.weightKg)} × `}
                {exercise.unilateral
                  ? `${set.sides.left ?? '—'} / ${set.sides.right ?? '—'}`
                  : set.reps}
              </span>
            ) : (
              <span>подход {slot + 1}</span>
            )}
          </li>
        ))}
      </ol>

      <RestTimer startedAt={restStartedAt} seconds={exercise.rest_seconds} onSkip={skipRest} />

      <nav className="flex flex-wrap gap-2 border-t pt-4">
        <Toggle active={panel === 'technique'} onClick={() => toggle(panel, 'technique', setPanel)}>
          Техника
        </Toggle>
        <Toggle
          active={panel === 'substitute'}
          onClick={() => toggle(panel, 'substitute', setPanel)}
        >
          Заменить
        </Toggle>
        <Toggle active={panel === 'time'} onClick={() => toggle(panel, 'time', setPanel)}>
          Осталось меньше времени
        </Toggle>
      </nav>

      <Technique slug={exercise.exercise_slug} open={panel === 'technique'} />
      {panel === 'substitute' && (
        <ReasonPicker
          pending={reshape.isPending}
          onPick={(reason) => reshape.mutate({ substitute: reason })}
        />
      )}
      {panel === 'time' && (
        <TimePicker pending={reshape.isPending} onPick={(minutes) => reshape.mutate({ minutes })} />
      )}
      {reshape.isError && <p className="text-destructive">{(reshape.error as Error).message}</p>}

      {guidance === 'quiet' && (
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">Вся тренировка</h2>
          <ul className="flex flex-col">
            {exercises.map((e, i) => (
              <li key={e.planned_slug || e.exercise_slug}>
                <button
                  type="button"
                  onClick={() => setPicked(i)}
                  className={cn(
                    'flex min-h-11 w-full items-baseline justify-between gap-4 border-t py-2 text-left',
                    i === index && 'font-medium',
                  )}
                >
                  <span>{titles.get(e.exercise_slug)?.title_ru ?? e.exercise_slug}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {completedSets(logged, e)} / {e.sets}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <SyncNote pending={pending.length} failingSince={failingSince} />

      <div className="flex flex-wrap gap-3 border-t pt-4">
        <Button size="lg" disabled={closeOut.isPending} onClick={() => closeOut.mutate('finish')}>
          Завершить тренировку
        </Button>
        <Button
          variant="ghost"
          size="lg"
          disabled={closeOut.isPending}
          onClick={() => closeOut.mutate('abort')}
        >
          Остановить
        </Button>
      </div>
      {closeOut.isError && <p className="text-destructive">{closeOut.error.message}</p>}
      {workoutIsDone(session, logged) && (
        <p className="text-muted-foreground">Все подходы отмечены — можно завершать.</p>
      )}
    </div>
  )
}

/**
 * Why the workout looks the way it does: readiness, a trim, a move indoors. The latest
 * change is spoken right away; the earlier ones stay one tap away.
 */
function Notes({ notes }: { notes: string[] }) {
  const latest = notes.at(-1)
  if (!latest) return null
  const earlier = notes.slice(0, -1)
  return (
    <div className="flex flex-col gap-1 rounded-lg border bg-card px-4 py-3">
      <p aria-live="polite">{latest}</p>
      {earlier.length > 0 && (
        <details className="text-sm text-muted-foreground">
          <summary className="flex min-h-11 cursor-pointer items-center">Что ещё менялось</summary>
          <ul className="flex flex-col gap-1">
            {earlier.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

function toggle(current: Panel, next: Panel, set: (panel: Panel) => void) {
  set(current === next ? 'none' : next)
}

function Toggle({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: string
}) {
  return (
    <Button variant={active ? 'secondary' : 'outline'} aria-pressed={active} onClick={onClick}>
      {children}
    </Button>
  )
}

/** Silent while the buffer drains; speaks only when it has really been stuck. */
function SyncNote({ pending, failingSince }: { pending: number; failingSince: number | null }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (failingSince === null) return
    const id = setInterval(() => setNow(Date.now()), 1_000)
    return () => clearInterval(id)
  }, [failingSince])

  if (pending === 0 || !isStale(failingSince, now)) return null
  return (
    <p className="rounded-lg bg-muted px-4 py-3">
      Подходы пока не ушли на сервер — связь. Они сохранены здесь и отправятся сами, как только сеть
      вернётся. Тренировку можно продолжать.
    </p>
  )
}
