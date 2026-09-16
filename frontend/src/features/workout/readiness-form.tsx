import { useState } from 'react'
import type { Feeling, Readiness } from '@/api/sessions'
import { ChoiceGroup } from '@/components/choice-group'
import { Button } from '@/components/ui/button'

type Tap = 'sleep' | 'stress' | 'soreness'
type Taps = Record<Tap, Feeling>

const TAPS: { key: Tap; legend: string; labels: Record<Feeling, string> }[] = [
  {
    key: 'sleep',
    legend: 'Как спалось?',
    labels: { bad: 'Плохо', ok: 'Обычно', good: 'Выспался' },
  },
  {
    key: 'stress',
    legend: 'Как с напряжением?',
    labels: { bad: 'Тяжёлый день', ok: 'Обычно', good: 'Спокойно' },
  },
  {
    key: 'soreness',
    legend: 'Мышцы после прошлой тренировки',
    labels: { bad: 'Болят', ok: 'Немного тянут', good: 'Не болят' },
  },
]
const VALUES: Feeling[] = ['bad', 'ok', 'good']

type ReadinessFormProps = {
  title: string
  subtitle: string
  pending: boolean
  onStart: (readiness: Readiness) => void
}

/** Three taps before the start; they scale today's volume, nothing else. */
export function ReadinessForm({ title, subtitle, pending, onStart }: ReadinessFormProps) {
  const [readiness, setReadiness] = useState<Taps>({
    sleep: 'ok',
    stress: 'ok',
    soreness: 'ok',
  })

  return (
    <section className="flex max-w-prose flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-muted-foreground">{subtitle}</p>
      </header>

      {TAPS.map(({ key, legend, labels }) => (
        <ChoiceGroup
          key={key}
          legend={legend}
          name={key}
          choices={VALUES.map((value) => ({ value, label: labels[value] }))}
          selected={[readiness[key]]}
          onSelect={(value) => setReadiness((r) => ({ ...r, [key]: value as Feeling }))}
        />
      ))}

      <p className="text-sm text-muted-foreground">
        Это нужно только чтобы подобрать объём на сегодня. Ответы ни на что больше не влияют.
      </p>

      <Button size="lg" disabled={pending} onClick={() => onStart(readiness)}>
        {pending ? 'Собираем тренировку…' : 'Начать тренировку'}
      </Button>
    </section>
  )
}
