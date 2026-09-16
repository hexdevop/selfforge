import type { SubstitutionReason } from '@/api/sessions'
import { Button } from '@/components/ui/button'

const REASONS: { value: SubstitutionReason; label: string }[] = [
  { value: 'equipment_busy', label: 'Снаряд занят' },
  { value: 'pain', label: 'Больно делать' },
  { value: 'too_hard', label: 'Слишком тяжело' },
  { value: 'too_easy', label: 'Слишком легко' },
  { value: 'disliked', label: 'Не нравится это движение' },
]

export function ReasonPicker({
  pending,
  onPick,
}: {
  pending: boolean
  onPick: (reason: SubstitutionReason) => void
}) {
  return (
    <fieldset className="flex flex-col gap-2 rounded-lg border bg-card p-4">
      <legend className="px-1 text-sm text-muted-foreground">Почему меняем</legend>
      {REASONS.map((reason) => (
        <Button
          key={reason.value}
          variant="outline"
          className="h-12 justify-start"
          disabled={pending}
          onClick={() => onPick(reason.value)}
        >
          {reason.label}
        </Button>
      ))}
    </fieldset>
  )
}

const WINDOWS = [10, 15, 20, 30]

export function TimePicker({
  pending,
  onPick,
}: {
  pending: boolean
  onPick: (minutes: number) => void
}) {
  return (
    <fieldset className="flex flex-col gap-2 rounded-lg border bg-card p-4">
      <legend className="px-1 text-sm text-muted-foreground">Сколько времени осталось</legend>
      <div className="flex flex-wrap gap-2">
        {WINDOWS.map((minutes) => (
          <Button
            key={minutes}
            variant="outline"
            className="h-12 min-w-24 tabular-nums"
            disabled={pending}
            onClick={() => onPick(minutes)}
          >
            {minutes} мин
          </Button>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        Пересоберём остаток: основные движения останутся, вспомогательные уйдут.
      </p>
    </fieldset>
  )
}
