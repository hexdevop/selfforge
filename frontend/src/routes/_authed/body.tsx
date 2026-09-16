import { useMutation, useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { type FormEvent, useState } from 'react'
import {
  addMetric,
  type BodyMetricIn,
  bodyMetricsQuery,
  deleteMetric,
  deletePhoto,
  type Photo,
  type PhotoAngle,
  photosQuery,
  uploadPhoto,
} from '@/api/body'
import { ChoiceGroup } from '@/components/choice-group'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ChartFrame, DataTable, TrendLine } from '@/features/progress/charts'
import { localDay, shortDate } from '@/features/progress/format'
import { formatKg } from '@/lib/format'

export const Route = createFileRoute('/_authed/body')({
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(bodyMetricsQuery),
      queryClient.ensureQueryData(photosQuery),
    ]),
  component: BodyPage,
})

function BodyPage() {
  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-2">
        <Link to="/progress" className="self-start underline underline-offset-4">
          Прогресс
        </Link>
        <h1 className="text-2xl font-semibold">Тело и замеры</h1>
        <p className="text-muted-foreground">
          Видно только тебе. Вес за день гуляет на килограмм из-за воды, поэтому на графике —
          среднее за неделю.
        </p>
      </header>
      <Metrics />
      <Photos />
    </div>
  )
}

const TAPE: { key: keyof BodyMetricIn; label: string }[] = [
  { key: 'waist_cm', label: 'Талия' },
  { key: 'chest_cm', label: 'Грудь' },
  { key: 'hip_cm', label: 'Бёдра' },
  { key: 'arm_cm', label: 'Плечо' },
  { key: 'thigh_cm', label: 'Бедро' },
]

function Metrics() {
  const queryClient = useQueryClient()
  const { data } = useSuspenseQuery(bodyMetricsQuery)
  const [values, setValues] = useState<Record<string, string>>({})
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['body', 'metrics'] })

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, string | null> = {}
      for (const [key, raw] of Object.entries(values)) {
        const value = raw.trim().replace(',', '.')
        if (value) body[key] = value
      }
      return addMetric(body as BodyMetricIn)
    },
    onSuccess: async () => {
      setValues({})
      await refresh()
      await queryClient.invalidateQueries({ queryKey: ['progress'] })
    },
  })
  const remove = useMutation({ mutationFn: deleteMetric, onSuccess: refresh })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate()
  }
  const field = (key: string, label: string, unit: string) => (
    <div className="flex flex-col gap-1">
      <Label htmlFor={key}>
        {label}, {unit}
      </Label>
      <Input
        id={key}
        inputMode="decimal"
        value={values[key] ?? ''}
        onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
      />
    </div>
  )
  const trend = data.weight_trend.map((p) => ({ day: p.day, value: Number(p.weight_kg) }))

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">Замеры</h2>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="max-w-40">{field('weight_kg', 'Вес', 'кг')}</div>
        <details>
          <summary className="flex min-h-11 cursor-pointer items-center">Обхваты</summary>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {TAPE.map((t) => field(t.key, t.label, 'см'))}
          </div>
        </details>
        <Button type="submit" className="self-start" disabled={save.isPending}>
          Сохранить замер
        </Button>
        {save.isError && <p className="text-destructive">{save.error.message}</p>}
      </form>

      {trend.length === 0 ? (
        <p className="text-muted-foreground">
          Взвешивайся утром, до еды, пару раз в неделю — через неделю появится линия.
        </p>
      ) : (
        <ChartFrame
          title="Вес, среднее за 7 дней, кг"
          table={
            <DataTable
              head={['День', 'Среднее, кг']}
              rows={trend.map((p) => [shortDate(p.day), formatKg(p.value)])}
            />
          }
        >
          <TrendLine data={trend} />
        </ChartFrame>
      )}

      {data.items.length > 0 && (
        <details>
          <summary className="flex min-h-11 cursor-pointer items-center">Все замеры</summary>
          <ul className="flex flex-col">
            {data.items.map((m) => {
              const parts = [
                m.weight_kg && `${formatKg(m.weight_kg)} кг`,
                ...TAPE.map((t) => {
                  const v = m[t.key as keyof typeof m]
                  return v ? `${t.label.toLowerCase()} ${formatKg(String(v))} см` : null
                }),
              ].filter(Boolean)
              return (
                <li
                  key={m.id}
                  className="flex items-center justify-between gap-3 border-t py-2 tabular-nums"
                >
                  <span>
                    {shortDate(localDay(m.measured_at))} · {parts.join(', ')}
                  </span>
                  <Button
                    variant="ghost"
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(m.id)}
                  >
                    Удалить
                  </Button>
                </li>
              )
            })}
          </ul>
        </details>
      )}
    </section>
  )
}

const ANGLES: { value: PhotoAngle; label: string }[] = [
  { value: 'front', label: 'Спереди' },
  { value: 'side', label: 'Сбоку' },
  { value: 'back', label: 'Сзади' },
]

function Photos() {
  const queryClient = useQueryClient()
  const { data: photos } = useSuspenseQuery(photosQuery)
  const [angle, setAngle] = useState<PhotoAngle>('front')
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['body', 'photos'] })

  const upload = useMutation({
    mutationFn: (file: File) => uploadPhoto(file, angle),
    onSettled: refresh,
  })
  const remove = useMutation({ mutationFn: deletePhoto, onSuccess: refresh })
  const sameAngle = photos.filter((p) => p.angle === angle)

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">Фото</h2>
      <ChoiceGroup
        legend="Ракурс"
        name="angle"
        choices={ANGLES}
        selected={[angle]}
        onSelect={(value) => setAngle(value as PhotoAngle)}
      />
      <div className="flex flex-col items-start gap-1">
        <Label htmlFor="photo" className="sr-only">
          Добавить фото
        </Label>
        <Button asChild variant="outline" disabled={upload.isPending}>
          <label htmlFor="photo" className="cursor-pointer">
            {upload.isPending ? 'Загружаем…' : 'Добавить фото'}
          </label>
        </Button>
        <input
          id="photo"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) upload.mutate(file)
            e.target.value = ''
          }}
        />
        <p className="text-sm text-muted-foreground">
          Одинаковый свет и поза каждый раз — так разница видна честнее.
        </p>
        {upload.isError && <p className="text-destructive">{upload.error.message}</p>}
      </div>

      {sameAngle.length >= 2 && <Compare photos={sameAngle} />}

      {sameAngle.length === 0 ? (
        <p className="text-muted-foreground">С этого ракурса фото пока нет.</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {sameAngle.map((photo) => (
            <li key={photo.id} className="flex flex-col gap-1">
              <img
                src={photo.url}
                alt={`Фото ${shortDate(localDay(photo.taken_at))}`}
                className="aspect-[3/4] w-full rounded-lg bg-muted object-cover"
                loading="lazy"
              />
              <div className="flex items-center justify-between">
                <span className="text-sm tabular-nums">{shortDate(localDay(photo.taken_at))}</span>
                <Button
                  variant="ghost"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(photo.id)}
                >
                  Удалить
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** Before and after stacked in one frame; the slider moves the curtain between them. */
function Compare({ photos }: { photos: Photo[] }) {
  const oldest = photos.at(-1)
  const newest = photos[0]
  const [beforeId, setBeforeId] = useState(oldest?.id ?? '')
  const [afterId, setAfterId] = useState(newest?.id ?? '')
  const [position, setPosition] = useState(50)
  const before = photos.find((p) => p.id === beforeId) ?? oldest
  const after = photos.find((p) => p.id === afterId) ?? newest
  if (!before || !after) return null

  const picker = (label: string, value: string, set: (id: string) => void) => (
    <label className="flex flex-col gap-1 text-sm">
      {label}
      <select
        value={value}
        onChange={(e) => set(e.target.value)}
        className="h-11 rounded-md border bg-card px-2"
      >
        {photos.map((p) => (
          <option key={p.id} value={p.id}>
            {shortDate(localDay(p.taken_at))}
          </option>
        ))}
      </select>
    </label>
  )

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        {picker('Было', before.id, setBeforeId)}
        {picker('Стало', after.id, setAfterId)}
      </div>
      <div className="relative mx-auto aspect-[3/4] w-full max-w-sm overflow-hidden rounded-xl bg-muted">
        <img src={after.url} alt="Стало" className="absolute inset-0 size-full object-cover" />
        <img
          src={before.url}
          alt="Было"
          className="absolute inset-0 size-full object-cover"
          style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}
        />
        <div
          aria-hidden
          className="absolute inset-y-0 w-0.5 bg-card"
          style={{ left: `${position}%` }}
        />
      </div>
      <label className="flex flex-col gap-1 text-sm">
        <span className="sr-only">Шторка: слева было, справа стало</span>
        <input
          type="range"
          min={0}
          max={100}
          value={position}
          onChange={(e) => setPosition(Number(e.target.value))}
          className="h-11 w-full accent-foreground"
        />
      </label>
    </div>
  )
}
