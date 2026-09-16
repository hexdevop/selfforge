import type { SessionExercise, SetLogIn, Side, WorkoutSession } from '@/api/sessions'

const WORK_BLOCKS = new Set(['main', 'accessory', 'finisher'])

/** Everything that gets logged, in the order it is done. Warm-up and cool-down are drills. */
export function workExercises(session: WorkoutSession): SessionExercise[] {
  return session.blocks.filter((b) => WORK_BLOCKS.has(b.kind)).flatMap((b) => b.exercises)
}

export type DoneSet = {
  index: number
  /** What the set counts as: for one-sided work, the weaker side (docs/03-engine.md §6). */
  reps: number
  weightKg: string | null
  sides: Partial<Record<Side, number>>
}

export function doneSets(logged: SetLogIn[], slug: string): DoneSet[] {
  const byIndex = new Map<number, DoneSet>()
  for (const log of logged) {
    if (log.exercise_slug !== slug || log.is_warmup) continue
    const set = byIndex.get(log.set_index) ?? {
      index: log.set_index,
      reps: log.reps,
      weightKg: log.weight_kg == null ? null : String(log.weight_kg),
      sides: {},
    }
    set.sides[log.side ?? 'both'] = log.reps
    const reps = Object.values(set.sides)
    set.reps = Math.min(...reps)
    byIndex.set(log.set_index, set)
  }
  return [...byIndex.values()].sort((a, b) => a.index - b.index)
}

/** A one-sided set is only done once both sides are logged. */
export function isSetComplete(set: DoneSet | undefined, unilateral: boolean): boolean {
  if (!set) return false
  return unilateral ? set.sides.left !== undefined && set.sides.right !== undefined : true
}

/** Which set is being worked on, and which side of it is still owed. */
export function nextSet(
  logged: SetLogIn[],
  exercise: SessionExercise,
): { index: number; side: Side } {
  const sets = doneSets(logged, exercise.exercise_slug)
  const open = sets.find((s) => !isSetComplete(s, exercise.unilateral))
  if (open) return { index: open.index, side: open.sides.left === undefined ? 'left' : 'right' }
  return {
    index: sets.length === 0 ? 0 : Math.max(...sets.map((s) => s.index)) + 1,
    side: exercise.unilateral ? 'left' : 'both',
  }
}

export function completedSets(logged: SetLogIn[], exercise: SessionExercise): number {
  return doneSets(logged, exercise.exercise_slug).filter((s) =>
    isSetComplete(s, exercise.unilateral),
  ).length
}

export function isExerciseDone(logged: SetLogIn[], exercise: SessionExercise): boolean {
  return completedSets(logged, exercise) >= exercise.sets
}

/** The exercise to show: the first one with sets still owed, else the last. */
export function currentIndex(session: WorkoutSession, logged: SetLogIn[]): number {
  const exercises = workExercises(session)
  const index = exercises.findIndex((e) => !isExerciseDone(logged, e))
  return index === -1 ? Math.max(0, exercises.length - 1) : index
}

/**
 * Reps to offer for a set.
 *
 * The symmetry rule: the second side matches what the first side actually did, so the
 * strong side never runs ahead of the weak one.
 */
export function suggestedReps(
  exercise: SessionExercise,
  logged: SetLogIn[],
  at: { index: number; side: Side },
): number {
  if (at.side === 'right') {
    const set = doneSets(logged, exercise.exercise_slug).find((s) => s.index === at.index)
    if (set?.sides.left !== undefined) return set.sides.left
  }
  const previous = doneSets(logged, exercise.exercise_slug).at(-1)
  return previous?.reps ?? exercise.target_max
}

export function workoutIsDone(session: WorkoutSession, logged: SetLogIn[]): boolean {
  return workExercises(session).every((e) => isExerciseDone(logged, e))
}

export function totalTonnage(logged: SetLogIn[]): number {
  return logged.reduce(
    (sum, log) => (log.is_warmup ? sum : sum + Number(log.weight_kg ?? 0) * log.reps),
    0,
  )
}
