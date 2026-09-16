import { Minus, Plus } from 'lucide-react'
import type { SessionExercise, Side } from '@/api/sessions'
import { Button } from '@/components/ui/button'
import { formatKg } from '@/lib/format'

const SIDE_LABELS: Record<Side, string> = {
  both: '',
  left: 'левая сторона',
  right: 'правая сторона',
}

type SetEditorProps = {
  exercise: SessionExercise
  side: Side
  reps: number
  weightKg: string | null
  onReps: (reps: number) => void
  onWeight: (weight: string) => void
  onConfirm: () => void
}

/**
 * The one thing the screen is for: confirm a set.
 *
 * Both numbers arrive filled in, so the usual case is a single tap on a target the size of
 * a thumb; tapping a number opens the keypad for the times it wasn't right.
 */
export function SetEditor({
  exercise,
  side,
  reps,
  weightKg,
  onReps,
  onWeight,
  onConfirm,
}: SetEditorProps) {
  const unit = exercise.timed ? 'секунд' : 'повторов'

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-center gap-5 sm:gap-8">
        {weightKg !== null && (
          <BigNumber
            label="кг"
            value={formatKg(weightKg)}
            inputLabel="Вес в килограммах"
            onChange={(raw) => onWeight(raw.replace(',', '.'))}
          />
        )}
        {weightKg !== null && <span className="pb-8 text-3xl text-muted-foreground">×</span>}
        <BigNumber
          label={unit}
          value={String(reps)}
          inputLabel={exercise.timed ? 'Секунд работы' : 'Сделано повторов'}
          onChange={(raw) => onReps(Math.max(0, Math.round(Number(raw) || 0)))}
          step={{
            onDown: () => onReps(Math.max(0, reps - 1)),
            onUp: () => onReps(reps + 1),
          }}
        />
      </div>

      <Button size="lg" className="h-14 w-full text-lg" onClick={onConfirm}>
        Подход выполнен
        {side !== 'both' && <span className="font-normal">· {SIDE_LABELS[side]}</span>}
      </Button>
    </div>
  )
}

type BigNumberProps = {
  label: string
  value: string
  inputLabel: string
  onChange: (raw: string) => void
  step?: { onDown: () => void; onUp: () => void }
}

function BigNumber({ label, value, inputLabel, onChange, step }: BigNumberProps) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex items-center gap-1">
        {step && (
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-11"
            aria-label="Меньше"
            onClick={step.onDown}
          >
            <Minus />
          </Button>
        )}
        <input
          type="text"
          inputMode="decimal"
          aria-label={inputLabel}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onFocus={(event) => event.target.select()}
          className="w-[3.5ch] rounded-lg bg-transparent text-center text-5xl font-semibold tabular-nums outline-none focus-visible:ring-3 focus-visible:ring-ring/50 sm:text-6xl"
        />
        {step && (
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-11"
            aria-label="Больше"
            onClick={step.onUp}
          >
            <Plus />
          </Button>
        )}
      </div>
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  )
}
