import { describe, expect, it } from 'vitest'
import type { SessionExercise, SetLogIn, Side } from '@/api/sessions'
import {
  completedSets,
  currentIndex,
  doneSets,
  isExerciseDone,
  nextSet,
  suggestedReps,
  totalTonnage,
  workExercises,
  workoutIsDone,
} from './progress'
import { clock, secondsLeft } from './timer'

const exercise = (over: Partial<SessionExercise> = {}): SessionExercise => ({
  exercise_slug: 'goblet-squat',
  pattern_code: 'squat',
  sets: 3,
  target_min: 8,
  target_max: 12,
  timed: false,
  rest_seconds: 90,
  rir: 2,
  unilateral: false,
  weight_kg: '16.00',
  tempo: null,
  hint_ru: '',
  planned_slug: 'goblet-squat',
  ...over,
})

const log = (index: number, reps: number, over: Partial<SetLogIn> = {}): SetLogIn => ({
  client_uuid: `${index}-${over.side ?? 'both'}`,
  exercise_slug: 'goblet-squat',
  set_index: index,
  reps,
  performed_at: '2026-09-16T10:00:00Z',
  weight_kg: '16.00',
  ...over,
})

const session = (...exercises: SessionExercise[]) =>
  ({
    blocks: [
      { kind: 'warmup' as const, minutes: 5, exercises: [], drills: [] },
      { kind: 'main' as const, minutes: 20, exercises, drills: [] },
      { kind: 'cooldown' as const, minutes: 3, exercises: [], drills: [] },
    ],
  }) as never

describe('what is left of the workout', () => {
  it('counts only the blocks that get logged', () => {
    expect(workExercises(session(exercise())).map((e) => e.exercise_slug)).toEqual(['goblet-squat'])
  })

  it('moves to the next exercise once this one is finished', () => {
    const squat = exercise()
    const row = exercise({ exercise_slug: 'row', planned_slug: 'row', sets: 2 })
    const logged = [0, 1, 2].map((i) => log(i, 10))

    expect(currentIndex(session(squat, row), [])).toBe(0)
    expect(currentIndex(session(squat, row), logged)).toBe(1)
    expect(isExerciseDone(logged, squat)).toBe(true)
    expect(workoutIsDone(session(squat, row), logged)).toBe(false)
  })

  it('offers the next set number after the ones already done', () => {
    expect(nextSet([], exercise())).toEqual({ index: 0, side: 'both' })
    expect(nextSet([log(0, 10)], exercise())).toEqual({ index: 1, side: 'both' })
  })

  it('leaves warm-up sets out of the count and out of the tonnage', () => {
    const logged = [log(0, 10, { is_warmup: true }), log(1, 10)]
    expect(completedSets(logged, exercise())).toBe(1)
    expect(totalTonnage(logged)).toBe(160)
  })
})

describe('one-sided work', () => {
  const single = exercise({ exercise_slug: 'split-squat', unilateral: true, sets: 2 })
  const side = (index: number, reps: number, which: Side) =>
    log(index, reps, { exercise_slug: 'split-squat', side: which })

  it('asks for the left side, then the right one of the same set', () => {
    expect(nextSet([], single)).toEqual({ index: 0, side: 'left' })
    expect(nextSet([side(0, 8, 'left')], single)).toEqual({ index: 0, side: 'right' })
    expect(nextSet([side(0, 8, 'left'), side(0, 8, 'right')], single)).toEqual({
      index: 1,
      side: 'left',
    })
  })

  it('does not count a set until both sides are done', () => {
    expect(completedSets([side(0, 8, 'left')], single)).toBe(0)
    expect(completedSets([side(0, 8, 'left'), side(0, 8, 'right')], single)).toBe(1)
  })

  it('offers the strong side exactly what the weak one did', () => {
    const logged = [side(0, 6, 'left')]
    expect(suggestedReps(single, logged, { index: 0, side: 'right' })).toBe(6)
  })

  it('counts the set as the weaker side', () => {
    const logged = [side(0, 6, 'left'), side(0, 9, 'right')]
    const [set] = doneSets(logged, 'split-squat')
    expect(set?.reps).toBe(6)
    expect(set?.sides).toEqual({ left: 6, right: 9 })
  })
})

describe('the rest timer', () => {
  it('reads the clock instead of counting ticks', () => {
    const started = 1_000_000
    expect(secondsLeft(started, 90, started)).toBe(90)
    expect(secondsLeft(started, 90, started + 2_000)).toBe(88)
    // Backgrounded for two minutes: it comes back finished, not frozen.
    expect(secondsLeft(started, 90, started + 120_000)).toBe(0)
  })

  it('shows minutes and seconds', () => {
    expect(clock(88)).toBe('1:28')
    expect(clock(5)).toBe('0:05')
    expect(clock(0)).toBe('0:00')
  })
})
