import type { Profile } from '@/api/profile'

export const STEPS = ['health', 'level', 'goal', 'places'] as const
export type Step = (typeof STEPS)[number]

/** Resume where the person left off: the first step the server doesn't have yet. */
export function firstUnfinished(profile: Profile, hasLevels: boolean): Step {
  if (!profile.medical_disclaimer_accepted_at) return 'health'
  if (!hasLevels) return 'level'
  if (!profile.goal_primary || !profile.days_per_week || !profile.session_minutes) return 'goal'
  return 'places'
}
