import { useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { equipmentQuery, exercisesQuery } from '@/api/catalog'
import { api } from '@/api/client'
import { locationsQuery } from '@/api/locations'
import { patternLevelsQuery, profileQuery } from '@/api/profile'
import { FormError } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { LocationsManager } from '@/features/inventory/locations-manager'
import { GoalStep } from '@/features/onboarding/goal-step'
import { HealthStep } from '@/features/onboarding/health-step'
import { LevelStep } from '@/features/onboarding/level-step'
import { firstUnfinished, STEPS, type Step } from '@/features/onboarding/steps'

const TITLES: Record<Step, string> = {
  health: 'Сначала о здоровье',
  level: 'Что получается сейчас',
  goal: 'Цель и расписание',
  places: 'Где тренируешься',
}

export const Route = createFileRoute('/_authed/onboarding')({
  validateSearch: (search): { step?: Step } =>
    STEPS.includes(search.step as Step) ? { step: search.step as Step } : {},
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(profileQuery),
      queryClient.ensureQueryData(patternLevelsQuery),
      queryClient.ensureQueryData(locationsQuery),
      queryClient.ensureQueryData(equipmentQuery),
      queryClient.ensureQueryData(exercisesQuery),
    ]),
  component: OnboardingPage,
})

function OnboardingPage() {
  const search = Route.useSearch()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: profile } = useSuspenseQuery(profileQuery)
  const { data: levels } = useSuspenseQuery(patternLevelsQuery)
  const { data: locations } = useSuspenseQuery(locationsQuery)
  const [error, setError] = useState<string>()

  const step = search.step ?? firstUnfinished(profile, levels.length > 0)
  const index = STEPS.indexOf(step)
  const next = () => navigate({ to: '/onboarding', search: { step: STEPS[index + 1] } })

  const finish = async () => {
    setError(undefined)
    const { data, error } = await api.POST('/api/v1/profile/onboarding/complete')
    if (!data) return setError(error?.detail.message)
    queryClient.setQueryData(profileQuery.queryKey, data)
    await navigate({ to: '/program/new' })
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <p className="text-muted-foreground tabular-nums">
          Шаг {index + 1} из {STEPS.length}
        </p>
        <h1 className="text-2xl font-semibold">{TITLES[step]}</h1>
      </header>

      {step === 'health' && <HealthStep onDone={next} />}
      {step === 'level' && <LevelStep onDone={next} />}
      {step === 'goal' && <GoalStep profile={profile} onDone={next} />}
      {step === 'places' && (
        <>
          <LocationsManager />
          <FormError message={error} />
          <Button size="lg" disabled={locations.length === 0} onClick={finish}>
            Готово
          </Button>
        </>
      )}

      {index > 0 && (
        <Button
          variant="ghost"
          className="self-start"
          onClick={() => navigate({ to: '/onboarding', search: { step: STEPS[index - 1] } })}
        >
          Назад
        </Button>
      )}
    </div>
  )
}
