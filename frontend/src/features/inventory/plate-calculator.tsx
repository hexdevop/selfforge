import { useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { api } from '@/api/client'
import { type Location, type PlatesResult, weightGridQuery } from '@/api/locations'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatKg } from '@/lib/format'
import { PLATE_COLORS } from './labels'

type Adjustable = 'barbell' | 'dumbbell'

const TITLES: Record<Adjustable, string> = { barbell: 'Штанга', dumbbell: 'Гантель' }

export function PlateCalculator({ location }: { location: Location }) {
  const id = useId()
  const adjustable = location.equipment
    .filter((item) => item.details.bar_kg != null)
    .map((item) => item.equipment_code as Adjustable)
  const [code, setCode] = useState<Adjustable>(adjustable[0] ?? 'barbell')
  const [target, setTarget] = useState('')
  const [result, setResult] = useState<PlatesResult | null>(null)
  const [error, setError] = useState<string>()
  const { data: grids } = useQuery(weightGridQuery(location.id))
  const grid = grids?.find((g) => g.equipment_code === code)

  const calculate = async () => {
    setError(undefined)
    const target_kg = target.replace(',', '.')
    if (!(Number(target_kg) > 0)) return setError('Введи вес больше нуля')
    try {
      const { data, error } = await api.POST('/api/v1/locations/{location_id}/plates', {
        params: { path: { location_id: location.id } },
        body: { equipment_code: code, target_kg },
      })
      if (!data) return setError(error?.detail.message)
      setResult(data)
    } catch {
      setError('Нет связи с сервером. Проверь интернет и попробуй ещё раз')
    }
  }

  return (
    <section aria-labelledby={id} className="flex flex-col gap-4 rounded-xl border bg-card p-4">
      <h3 id={id} className="font-semibold">
        Калькулятор блинов
      </h3>
      {adjustable.length > 1 && (
        <div className="flex gap-2">
          {adjustable.map((c) => (
            <Button
              key={c}
              variant={c === code ? 'default' : 'outline'}
              aria-pressed={c === code}
              onClick={() => {
                setCode(c)
                setResult(null)
              }}
            >
              {TITLES[c]}
            </Button>
          ))}
        </div>
      )}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          calculate()
        }}
      >
        <Input
          aria-label="Нужный вес, кг"
          placeholder="Нужный вес, кг"
          inputMode="decimal"
          className="max-w-40"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <Button type="submit" variant="outline">
          Посчитать
        </Button>
      </form>
      {error && <p className="text-sm text-destructive">{error}</p>}

      {result && (
        <div aria-live="polite">
          {result.achievable ? (
            <>
              <p className="mb-3">
                Чтобы собрать {formatKg(result.target_kg)} кг, повесь на каждую сторону
                {code === 'dumbbell' ? ' каждой гантели' : ''}:
              </p>
              {result.per_side.length === 0 ? (
                <p className="font-medium">ничего — это вес самого грифа</p>
              ) : (
                <ul className="flex flex-wrap items-center gap-2">
                  {result.per_side.flatMap((plate) =>
                    Array.from({ length: plate.count }, (_, i) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: identical plates, position is identity
                      <li key={`${plate.kg}-${i}`}>
                        <PlateChip kg={plate.kg} />
                      </li>
                    )),
                  )}
                </ul>
              )}
            </>
          ) : (
            <p>
              Ровно {formatKg(result.target_kg)} кг из этих блинов не собрать.
              {result.nearest_kg.length > 0 &&
                ` Ближайшие: ${result.nearest_kg.map((kg) => `${formatKg(kg)} кг`).join(' и ')}.`}
            </p>
          )}
        </div>
      )}

      {grid && (
        <p className="text-sm text-muted-foreground">
          Можно собрать: {grid.weights_kg.map((kg) => formatKg(kg)).join(' · ')} кг
          {grid.min_step_kg && `. Минимальный шаг — ${formatKg(grid.min_step_kg)} кг`}
        </p>
      )}
    </section>
  )
}

function PlateChip({ kg }: { kg: string }) {
  const key = String(Number(kg))
  const color = PLATE_COLORS[key]
  const light = key === '5' || key === '15' || !color
  return (
    <span
      className="flex h-11 min-w-11 items-center justify-center rounded-lg border px-2 font-bold tabular-nums"
      style={{
        backgroundColor: color ?? 'var(--steel-200)',
        color: light ? 'var(--ink)' : '#fff',
      }}
    >
      {formatKg(kg)}
    </span>
  )
}
