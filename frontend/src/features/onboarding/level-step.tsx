import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { exercisesQuery } from '@/api/catalog'
import { api } from '@/api/client'
import { applyApiError } from '@/api/errors'
import { type Assessment, type AssessmentAnswers, patternLevelsQuery } from '@/api/profile'
import { ChoiceGroup } from '@/components/choice-group'
import { FormError } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import {
  OVERALL_LABELS,
  PISTOL_CHOICES,
  PULLUP_CHOICES,
  PUSHUP_CHOICES,
  SQUAT_CHOICES,
  YES_NO,
} from './choices'

const pick = 'Выбери вариант'
const yesNo = z.enum(['yes', 'no'], { error: pick }).transform((v) => v === 'yes')

const schema = z.object({
  pushups: z.enum(['0', '1-5', '6-15', '16-30', '30+'], { error: pick }),
  pullups: z.enum(['0', '1-3', '4-8', '9-15', '15+'], { error: pick }),
  squats: z.enum(['<10', '10-25', '25-50', '50+'], { error: pick }),
  pistol: z.enum(['no', 'assisted', 'yes'], { error: pick }),
  experienced: yesNo,
  knows_terms: yesNo,
})

type Input = z.input<typeof schema>
type Output = z.output<typeof schema>

// The three patterns we asked about directly — shown back as "we'll start with…".
const SHOWN = [
  ['push_h', 'Отжимания'],
  ['pull_v', 'Подтягивания'],
  ['squat', 'Приседания'],
] as const

export function LevelStep({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const form = useForm<Input, unknown, Output>({ resolver: zodResolver(schema) })
  const { errors, isSubmitting } = form.formState
  const [answers, setAnswers] = useState<Output | null>(null)
  const [result, setResult] = useState<Assessment | null>(null)
  const [pending, setPending] = useState(false)

  const send = async (body: AssessmentAnswers) => {
    const { data, error } = await api.POST('/api/v1/profile/assessment', { body })
    if (!data) return applyApiError(error, form.setError)
    queryClient.setQueryData(patternLevelsQuery.queryKey, data.levels)
    setResult(data)
  }

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      setAnswers(values)
      await send(values)
    } catch {
      applyApiError(undefined, form.setError)
    }
  })

  const adjust = async (shift: -1 | 0 | 1) => {
    if (!answers) return
    setPending(true)
    try {
      await send({ ...answers, shift })
    } finally {
      setPending(false)
    }
  }

  if (result) {
    return <LevelResult result={result} pending={pending} onAdjust={adjust} onDone={onDone} />
  }

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-7">
      <p className="text-muted-foreground">
        Отвечай как есть сейчас, а не как было когда-то. Честный ответ — лучший старт.
      </p>
      <ChoiceGroup
        legend="Сколько отжиманий подряд сделаешь с нормальной техникой?"
        choices={PUSHUP_CHOICES}
        error={errors.pushups?.message}
        {...form.register('pushups')}
      />
      <ChoiceGroup
        legend="А подтягиваний?"
        hint="Ноль — нормальный ответ: для него есть свой путь к первому подтягиванию."
        choices={PULLUP_CHOICES}
        error={errors.pullups?.message}
        {...form.register('pullups')}
      />
      <ChoiceGroup
        legend="Сколько приседаний подряд?"
        choices={SQUAT_CHOICES}
        error={errors.squats?.message}
        {...form.register('squats')}
      />
      <ChoiceGroup
        legend="Получается присесть на одной ноге?"
        choices={PISTOL_CHOICES}
        error={errors.pistol?.message}
        {...form.register('pistol')}
      />
      <ChoiceGroup
        legend="Были регулярные тренировки хотя бы полгода за последний год?"
        choices={YES_NO}
        error={errors.experienced?.message}
        {...form.register('experienced')}
      />
      <ChoiceGroup
        legend="Знакомы слова «подход», «повтор», «отказ», «RIR»?"
        choices={YES_NO}
        error={errors.knows_terms?.message}
        {...form.register('knows_terms')}
      />
      <FormError message={errors.root?.message} />
      <Button type="submit" size="lg" disabled={isSubmitting}>
        Узнать уровень
      </Button>
    </form>
  )
}

function LevelResult({
  result,
  pending,
  onAdjust,
  onDone,
}: {
  result: Assessment
  pending: boolean
  onAdjust: (shift: -1 | 0 | 1) => void
  onDone: () => void
}) {
  const { data: exercises = [] } = useQuery(exercisesQuery)
  const title = (slug: string) => exercises.find((e) => e.slug === slug)?.title_ru ?? slug
  const byPattern = new Map(result.levels.map((level) => [level.pattern_code, level]))

  return (
    <section aria-live="polite" className="flex flex-col gap-6">
      <p className="text-xl font-semibold">
        Похоже, у тебя {OVERALL_LABELS[result.overall]} уровень. Верно?
      </p>
      <dl className="flex flex-col gap-3">
        {SHOWN.map(([pattern, label]) => {
          const level = byPattern.get(pattern)
          return (
            level && (
              <div key={pattern}>
                <dt className="text-sm text-muted-foreground">{label}: начнём с</dt>
                <dd className="font-medium">{title(level.current_exercise_slug)}</dd>
              </div>
            )
          )
        })}
      </dl>
      <p className="text-muted-foreground">
        Если кажется, что слишком легко или тяжело, сдвинь старт. Потом приложение само подстроится
        по твоим тренировкам.
      </p>
      <div className="grid grid-cols-2 gap-3">
        <Button variant="outline" disabled={pending} onClick={() => onAdjust(-1)}>
          Скорее ниже
        </Button>
        <Button variant="outline" disabled={pending} onClick={() => onAdjust(1)}>
          Скорее выше
        </Button>
      </div>
      <Button size="lg" disabled={pending} onClick={onDone}>
        Верно, дальше
      </Button>
    </section>
  )
}
