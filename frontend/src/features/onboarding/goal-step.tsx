import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api } from '@/api/client'
import { applyApiError } from '@/api/errors'
import { type Profile, profileQuery } from '@/api/profile'
import { ChoiceGroup } from '@/components/choice-group'
import { FormError } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { DAYS_CHOICES, GOAL_CHOICES, MINUTES_CHOICES } from './choices'

const goals = [
  'hypertrophy',
  'strength',
  'endurance',
  'fat_loss',
  'skill',
  'health',
  'maintenance',
] as const

const schema = z
  .object({
    goal_primary: z.enum(goals, { error: 'Выбери основную цель' }),
    goal_secondary: z.union([z.enum(goals), z.literal('')]).transform((v) => (v === '' ? null : v)),
    days_per_week: z.coerce.number<string>({ error: 'Выбери число дней' }).int().min(2).max(6),
    session_minutes: z.coerce.number<string>({ error: 'Выбери длительность' }).int(),
  })
  .refine((v) => v.goal_secondary !== v.goal_primary, {
    path: ['goal_secondary'],
    message: 'Выбери цель, отличную от основной',
  })

type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

export function GoalStep({ profile, onDone }: { profile: Profile; onDone: () => void }) {
  const queryClient = useQueryClient()
  const form = useForm<Input, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: {
      goal_primary: profile.goal_primary ?? undefined,
      goal_secondary: profile.goal_secondary ?? '',
      days_per_week: profile.days_per_week?.toString(),
      session_minutes: profile.session_minutes?.toString(),
    },
  })
  const { errors, isSubmitting } = form.formState
  const primary = form.watch('goal_primary')

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const { data, error } = await api.PATCH('/api/v1/profile', {
        body: { ...values, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
      })
      if (!data) return applyApiError(error, form.setError)
      queryClient.setQueryData(profileQuery.queryKey, data)
      onDone()
    } catch {
      applyApiError(undefined, form.setError)
    }
  })

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-7">
      <ChoiceGroup
        legend="Чего хочешь добиться?"
        hint="Цель задаёт повторы, отдых и подбор упражнений."
        stacked
        choices={GOAL_CHOICES}
        error={errors.goal_primary?.message}
        {...form.register('goal_primary')}
      />

      <div className="flex flex-col gap-2">
        <label htmlFor="goal-secondary" className="text-base font-medium">
          Второстепенная цель
        </label>
        <select
          id="goal-secondary"
          className="h-11 rounded-md border border-input bg-card px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          aria-invalid={Boolean(errors.goal_secondary)}
          {...form.register('goal_secondary')}
        >
          <option value="">Без второстепенной</option>
          {GOAL_CHOICES.filter((g) => g.value !== primary).map((g) => (
            <option key={g.value} value={g.value}>
              {g.label}
            </option>
          ))}
        </select>
        {errors.goal_secondary && (
          <p className="text-sm text-destructive">{errors.goal_secondary.message}</p>
        )}
      </div>

      <ChoiceGroup
        legend="Сколько дней в неделю есть на тренировки?"
        choices={DAYS_CHOICES}
        error={errors.days_per_week?.message}
        {...form.register('days_per_week')}
      />
      <ChoiceGroup
        legend="Сколько времени на одну тренировку?"
        choices={MINUTES_CHOICES}
        error={errors.session_minutes?.message}
        {...form.register('session_minutes')}
      />

      <FormError message={errors.root?.message} />
      <Button type="submit" size="lg" disabled={isSubmitting}>
        Дальше
      </Button>
    </form>
  )
}
