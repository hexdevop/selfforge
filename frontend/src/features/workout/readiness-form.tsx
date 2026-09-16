import { useState } from 'react'
import type { Location } from '@/api/locations'
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

type Planned = { id: string; title: string; minutes: number; locationId: string | null }

export type StartChoice = {
  readiness: Readiness
  unplanned: boolean
  locationId: string | null
}

type ReadinessFormProps = {
  /** The next day of the program; null when there is no program to follow. */
  planned: Planned | null
  locations: Location[]
  pending: boolean
  onStart: (choice: StartChoice) => void
}

const FREE = 'free'

/** What to train, where, and three taps that scale today's volume — nothing else. */
export function ReadinessForm({ planned, locations, pending, onStart }: ReadinessFormProps) {
  const [readiness, setReadiness] = useState<Taps>({
    sleep: 'ok',
    stress: 'ok',
    soreness: 'ok',
  })
  const [what, setWhat] = useState(planned ? planned.id : FREE)
  const unplanned = what === FREE
  const defaultPlace = locations.find((l) => l.is_default)?.id ?? locations[0]?.id ?? null
  const [place, setPlace] = useState<string | null>(planned?.locationId ?? defaultPlace)

  return (
    <section className="flex max-w-prose flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Тренировка</h1>
        <p className="text-muted-foreground">
          {planned && !unplanned
            ? `${planned.title} · около ${planned.minutes} минут. Пара вопросов — и начинаем.`
            : 'Соберём тренировку на всё тело под место, где ты сейчас.'}
        </p>
      </header>

      <ChoiceGroup
        legend="Что тренируем"
        name="what"
        stacked
        choices={[
          ...(planned
            ? [{ value: planned.id, label: planned.title, description: 'Следующий день программы' }]
            : []),
          {
            value: FREE,
            label: 'Свободная тренировка',
            description: 'На всё тело, вне программы — цикл при этом не сдвигается',
          },
        ]}
        selected={[what]}
        onSelect={(value) => setWhat(value)}
      />

      {locations.length > 1 && (
        <ChoiceGroup
          legend="Где"
          name="place"
          hint={
            unplanned
              ? undefined
              : 'Если сегодня не там, где по плану, упражнения подберём под это место'
          }
          choices={locations.map((l) => ({ value: l.id, label: l.title }))}
          selected={place ? [place] : []}
          onSelect={(value) => setPlace(value)}
        />
      )}

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
        Самочувствие нужно только чтобы подобрать объём на сегодня. Ни на что больше оно не влияет.
      </p>

      <Button
        size="lg"
        disabled={pending}
        onClick={() => onStart({ readiness, unplanned, locationId: place })}
      >
        {pending ? 'Собираем тренировку…' : 'Начать тренировку'}
      </Button>
    </section>
  )
}
