import { expect, it } from 'vitest'
import type { Profile } from '@/api/profile'
import { firstUnfinished } from './steps'

const blank: Profile = {
  birth_year: null,
  goal_primary: null,
  goal_secondary: null,
  days_per_week: null,
  session_minutes: null,
  guidance_level: 'normal',
  health_flags: [],
  needs_medical_clearance: false,
  medical_disclaimer_accepted_at: null,
  units: 'metric',
  timezone: 'UTC',
  onboarding_completed_at: null,
}
const accepted = { ...blank, medical_disclaimer_accepted_at: '2026-09-15T10:00:00Z' }

it.each([
  ['nothing done', blank, false, 'health'],
  ['disclaimer accepted', accepted, false, 'level'],
  ['levels assessed', accepted, true, 'goal'],
  ['goal without schedule', { ...accepted, goal_primary: 'strength' as const }, true, 'goal'],
  [
    'goal and schedule set',
    { ...accepted, goal_primary: 'strength' as const, days_per_week: 3, session_minutes: 45 },
    true,
    'places',
  ],
])('%s → %s', (_, profile, hasLevels, step) => {
  expect(firstUnfinished(profile, hasLevels)).toBe(step)
})
