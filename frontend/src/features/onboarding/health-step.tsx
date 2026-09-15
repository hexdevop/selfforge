import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api } from '@/api/client'
import { applyApiError } from '@/api/errors'
import { profileQuery } from '@/api/profile'
import { ChoiceGroup } from '@/components/choice-group'
import { FormError, FormField } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { HEALTH_CHOICES } from './choices'

const currentYear = new Date().getFullYear()
// Same threshold as the backend's CLEARANCE_AGE: past it we recommend a doctor's check.
const CLEARANCE_AGE = 60

const schema = z.object({
  birth_year: z.coerce
    .number<string>({ error: 'Укажи год рождения' })
    .int('Укажи год целиком')
    .min(1920, 'Проверь год')
    .max(currentYear - 14, 'Проверь год'),
  heart_condition: z.boolean(),
  pregnancy: z.boolean(),
  recent_injury: z.boolean(),
  health_flags: z.array(z.enum(['knees', 'shoulders', 'lower_back', 'wrists', 'neck', 'elbows'])),
  accepted: z.literal(true, { error: 'Поставь галочку, чтобы продолжить' }),
})

type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

const RED_FLAGS = [
  { name: 'heart_condition', label: 'Проблемы с сердцем или давлением' },
  { name: 'pregnancy', label: 'Беременность' },
  { name: 'recent_injury', label: 'Травма, которая ещё не зажила' },
] as const

export function HealthStep({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const form = useForm<Input, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: {
      birth_year: '',
      heart_condition: false,
      pregnancy: false,
      recent_injury: false,
      health_flags: [],
    },
  })
  const { errors, isSubmitting } = form.formState
  const values = form.watch()
  const age = currentYear - Number(values.birth_year)
  const recommendDoctor =
    values.heart_condition ||
    values.pregnancy ||
    values.recent_injury ||
    (Number(values.birth_year) > 1900 && age >= CLEARANCE_AGE)

  const onSubmit = form.handleSubmit(async (body) => {
    try {
      const { data, error } = await api.POST('/api/v1/profile/disclaimer', { body })
      if (!data) return applyApiError(error, form.setError)
      queryClient.setQueryData(profileQuery.queryKey, data)
      onDone()
    } catch {
      applyApiError(undefined, form.setError)
    }
  })

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-7">
      <FormField
        label="Год рождения"
        inputMode="numeric"
        autoComplete="bday-year"
        className="max-w-40"
        error={errors.birth_year?.message}
        {...form.register('birth_year')}
      />

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 text-base font-medium">Есть что-то из этого?</legend>
        {RED_FLAGS.map(({ name, label }) => (
          <label key={name} className="flex min-h-11 items-center gap-3">
            <input type="checkbox" className="size-5 accent-primary" {...form.register(name)} />
            {label}
          </label>
        ))}
      </fieldset>

      <ChoiceGroup
        type="checkbox"
        legend="Что-то беспокоит?"
        hint="Упражнения, которые нагружают эти места, не попадут в программу."
        choices={HEALTH_CHOICES}
        {...form.register('health_flags')}
      />

      {recommendDoctor && (
        <p role="status" className="rounded-lg border border-border bg-card p-4">
          Перед началом тренировок лучше посоветоваться с врачом. Приложение даёт общие рекомендации
          и не знает твоего состояния. Продолжить можно в любом случае.
        </p>
      )}

      <div className="flex flex-col gap-2">
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-0.5 size-5 shrink-0 accent-primary"
            aria-invalid={Boolean(errors.accepted)}
            {...form.register('accepted')}
          />
          <span>
            Понимаю, что Self Forge даёт общие рекомендации по тренировкам и не заменяет
            консультацию врача.
          </span>
        </label>
        {errors.accepted && <p className="text-sm text-destructive">{errors.accepted.message}</p>}
      </div>

      <FormError message={errors.root?.message} />
      <Button type="submit" size="lg" disabled={isSubmitting}>
        Дальше
      </Button>
    </form>
  )
}
