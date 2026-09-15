import { X } from 'lucide-react'
import { useId, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatKg } from '@/lib/format'
import { PLATE_SIZES } from './labels'

type Kg = string | number

const parseKg = (text: string) => {
  const value = Number(text.replace(',', '.'))
  return Number.isFinite(value) && value > 0 && value <= 500 ? String(value) : null
}

/** A list of weights, one entry per piece (two 16 kg kettlebells → 16, 16). */
export function WeightsInput({
  label,
  hint,
  value,
  onChange,
}: {
  label: string
  hint?: string
  value: Kg[]
  onChange: (next: string[]) => void
}) {
  const id = useId()
  const [text, setText] = useState('')
  const [invalid, setInvalid] = useState(false)

  const add = () => {
    const kg = parseKg(text)
    if (!kg) return setInvalid(true)
    onChange([...value.map(String), kg].sort((a, b) => Number(a) - Number(b)))
    setText('')
    setInvalid(false)
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-base">
        {label}
      </label>
      {hint && <p className="text-sm text-muted-foreground">{hint}</p>}
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {value.map((kg, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: duplicates are meaningful (a pair)
            <li key={`${kg}-${i}`}>
              <button
                type="button"
                onClick={() => onChange(value.filter((_, j) => j !== i).map(String))}
                aria-label={`Убрать ${formatKg(kg)} кг`}
                className="flex h-11 items-center gap-1.5 rounded-lg border bg-card px-3 tabular-nums hover:bg-secondary"
              >
                {formatKg(kg)} кг
                <X aria-hidden className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <Input
          id={id}
          inputMode="decimal"
          placeholder="Вес, кг"
          className="max-w-32"
          value={text}
          aria-invalid={invalid}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              add()
            }
          }}
        />
        <Button type="button" variant="outline" onClick={add}>
          Добавить
        </Button>
      </div>
      {invalid && <p className="text-sm text-destructive">Вес — число больше нуля, до 500 кг</p>}
    </div>
  )
}

export function BarInput({
  value,
  onChange,
}: {
  value: Kg | null | undefined
  onChange: (next: string | null) => void
}) {
  const id = useId()
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-base">
        Вес грифа, кг
      </label>
      <Input
        id={id}
        inputMode="decimal"
        className="max-w-32"
        defaultValue={value == null ? '' : formatKg(value)}
        onChange={(e) => onChange(parseKg(e.target.value))}
      />
    </div>
  )
}

type PlateSet = { kg: Kg; count: number }

export function PlatesInput({
  value,
  onChange,
}: {
  value: PlateSet[]
  onChange: (next: PlateSet[]) => void
}) {
  const update = (i: number, patch: Partial<PlateSet>) =>
    onChange(value.map((plate, j) => (j === i ? { ...plate, ...patch } : plate)))

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-base">Блины — сколько штук каждого веса всего</legend>
      {value.map((plate, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: rows have no identity besides position
        <div key={i} className="flex items-center gap-2">
          <select
            aria-label="Вес блина"
            value={String(Number(plate.kg))}
            onChange={(e) => update(i, { kg: e.target.value })}
            className="h-11 rounded-md border border-input bg-card px-3 text-base tabular-nums"
          >
            {PLATE_SIZES.map((kg) => (
              <option key={kg} value={kg}>
                {formatKg(kg)} кг
              </option>
            ))}
          </select>
          <span aria-hidden>×</span>
          <Input
            aria-label="Количество"
            type="number"
            min={1}
            max={50}
            className="w-20"
            value={plate.count}
            onChange={(e) => update(i, { count: Math.max(1, Number(e.target.value) || 1) })}
          />
          <Button
            type="button"
            variant="ghost"
            aria-label="Убрать блины"
            onClick={() => onChange(value.filter((_, j) => j !== i))}
          >
            <X aria-hidden />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        className="self-start"
        onClick={() => onChange([...value, { kg: '2.5', count: 2 }])}
      >
        Добавить блины
      </Button>
    </fieldset>
  )
}
