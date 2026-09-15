import { useQueryClient, useSuspenseQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { type Equipment, equipmentQuery } from '@/api/catalog'
import { api } from '@/api/client'
import type { ApiError } from '@/api/errors'
import {
  type EquipmentDetailsInput,
  type EquipmentInput,
  type Location,
  type LocationConstraints,
  locationsQuery,
} from '@/api/locations'
import { ChoiceGroup } from '@/components/choice-group'
import { FormError } from '@/components/form-field'
import { Button } from '@/components/ui/button'
import { CATEGORY_LABELS } from '@/lib/format'
import { DETAILED, RESISTANCE_CHOICES, SURFACE_CHOICES, visibleEquipment } from './labels'
import { BarInput, PlatesInput, WeightsInput } from './weight-inputs'

type Draft = Record<string, EquipmentInput>
type Resistance = NonNullable<EquipmentDetailsInput['resistances']>[number]

const FLAGS: { key: 'quiet_mode' | 'low_ceiling' | 'limited_space'; label: string }[] = [
  { key: 'quiet_mode', label: 'Соседи снизу — без прыжков и бросков' },
  { key: 'low_ceiling', label: 'Низкий потолок — не поднять руки со снарядом стоя' },
  { key: 'limited_space', label: 'Мало места — всё в пределах коврика' },
]

export function InventoryEditor({
  location,
  onSaved,
}: {
  location: Location
  onSaved: () => void
}) {
  const queryClient = useQueryClient()
  const { data: catalog } = useSuspenseQuery(equipmentQuery)
  const [draft, setDraft] = useState<Draft>(() =>
    Object.fromEntries(location.equipment.map((item) => [item.equipment_code, item])),
  )
  const [constraints, setConstraints] = useState<LocationConstraints>(location.constraints)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string>()
  const [saving, setSaving] = useState(false)

  const toggle = (code: string) =>
    setDraft(({ [code]: current, ...rest }) =>
      current ? rest : { ...rest, [code]: { equipment_code: code, quantity: 1, details: {} } },
    )
  const patch = (code: string, value: Partial<EquipmentInput>) =>
    setDraft((d) => ({ ...d, [code]: { ...d[code], ...value } as EquipmentInput }))
  const patchDetails = (code: string, value: Partial<EquipmentDetailsInput>) =>
    setDraft((d) => {
      const item = d[code]
      return item ? { ...d, [code]: { ...item, details: { ...item.details, ...value } } } : d
    })

  const save = async () => {
    setSaving(true)
    setErrors({})
    setFormError(undefined)
    try {
      const path = { params: { path: { location_id: location.id } } }
      const [equipment, place] = await Promise.all([
        api.PUT('/api/v1/locations/{location_id}/equipment', {
          ...path,
          body: Object.values(draft),
        }),
        api.PATCH('/api/v1/locations/{location_id}', { ...path, body: { constraints } }),
      ])
      const error: ApiError | undefined = equipment.error ?? place.error
      if (error) {
        setErrors(error.detail.fields ?? {})
        setFormError(error.detail.message)
        return
      }
      await queryClient.invalidateQueries({ queryKey: locationsQuery.queryKey })
      onSaved()
    } catch {
      setFormError('Нет связи с сервером. Проверь интернет и попробуй ещё раз')
    } finally {
      setSaving(false)
    }
  }

  const items = visibleEquipment(location.kind, catalog)
  const groups = Object.entries(CATEGORY_LABELS)
    .map(([category, label]) => ({ label, items: items.filter((i) => i.category === category) }))
    .filter((g) => g.items.length > 0)

  return (
    <div className="flex flex-col gap-7">
      {location.kind === 'outdoor_gym' ? (
        <ChoiceGroup
          legend="Покрытие"
          hint="На песке и асфальте не предложим упражнения лёжа."
          choices={SURFACE_CHOICES}
          selected={constraints.surface ? [constraints.surface] : []}
          onSelect={(surface) =>
            setConstraints((c) => ({ ...c, surface: surface as LocationConstraints['surface'] }))
          }
        />
      ) : (
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-2 text-base font-medium">Особенности места</legend>
          {FLAGS.map(({ key, label }) => (
            <label key={key} className="flex min-h-11 items-center gap-3">
              <input
                type="checkbox"
                className="size-5 accent-primary"
                checked={Boolean(constraints[key])}
                onChange={(e) => setConstraints((c) => ({ ...c, [key]: e.target.checked }))}
              />
              {label}
            </label>
          ))}
        </fieldset>
      )}

      {groups.map((group) => (
        <fieldset key={group.label} className="flex flex-col gap-1">
          <legend className="mb-2 text-base font-medium">{group.label}</legend>
          {group.items.map((item) => (
            <EquipmentRow
              key={item.code}
              item={item}
              value={draft[item.code]}
              error={errors[item.code]}
              onToggle={() => toggle(item.code)}
              onPatch={(value) => patch(item.code, value)}
              onDetails={(value) => patchDetails(item.code, value)}
            />
          ))}
        </fieldset>
      ))}

      <FormError message={formError} />
      <Button size="lg" onClick={save} disabled={saving}>
        Сохранить
      </Button>
    </div>
  )
}

function EquipmentRow({
  item,
  value,
  error,
  onToggle,
  onPatch,
  onDetails,
}: {
  item: Equipment
  value: EquipmentInput | undefined
  error?: string
  onToggle: () => void
  onPatch: (value: Partial<EquipmentInput>) => void
  onDetails: (value: Partial<EquipmentDetailsInput>) => void
}) {
  const details = value?.details ?? {}
  return (
    <div>
      <label className="flex min-h-11 items-center gap-3">
        <input
          type="checkbox"
          className="size-5 accent-primary"
          checked={Boolean(value)}
          onChange={onToggle}
        />
        {item.title_ru}
      </label>
      {value && DETAILED.has(item.code) && (
        <div className="mb-3 ml-8 flex flex-col gap-5 border-l pl-4">
          {item.code === 'dumbbell' && (
            <>
              <ChoiceGroup
                legend="Сколько гантелей"
                choices={[
                  { value: '1', label: 'Одна' },
                  { value: '2', label: 'Пара' },
                ]}
                selected={[String(value.quantity ?? 1)]}
                onSelect={(q) => onPatch({ quantity: Number(q) })}
              />
              <ChoiceGroup
                legend="Какие"
                choices={[
                  { value: 'fixed', label: 'Фиксированные' },
                  { value: 'adjustable', label: 'Разборные' },
                ]}
                selected={details.type ? [details.type] : []}
                onSelect={(type) => onDetails({ type: type as 'fixed' | 'adjustable' })}
              />
              {details.type === 'fixed' && (
                <WeightsInput
                  label="Веса гантелей"
                  hint={value.quantity === 2 ? 'Вес одной гантели из каждой пары.' : undefined}
                  value={details.weights_kg ?? []}
                  onChange={(weights_kg) => onDetails({ weights_kg })}
                />
              )}
              {details.type === 'adjustable' && (
                <AdjustableInputs details={details} onDetails={onDetails} />
              )}
            </>
          )}
          {item.code === 'kettlebell' && (
            <WeightsInput
              label="Веса гирь"
              hint="Каждую гирю отдельно: две по 16 кг — это 16 и 16."
              value={details.weights_kg ?? []}
              onChange={(weights_kg) => onDetails({ type: 'fixed', weights_kg })}
            />
          )}
          {item.code === 'barbell' && (
            <AdjustableInputs
              details={details}
              onDetails={(d) => onDetails({ ...d, type: 'adjustable' })}
            />
          )}
          {item.code === 'resistance_band' && (
            <ChoiceGroup
              type="checkbox"
              legend="Какие резинки есть"
              choices={RESISTANCE_CHOICES}
              selected={details.resistances ?? []}
              onSelect={(value) => {
                const r = value as Resistance
                const current = details.resistances ?? []
                onDetails({
                  resistances: current.includes(r)
                    ? current.filter((x) => x !== r)
                    : [...current, r],
                })
              }}
            />
          )}
        </div>
      )}
      {error && <p className="mb-2 ml-8 text-sm text-destructive">{error}</p>}
    </div>
  )
}

function AdjustableInputs({
  details,
  onDetails,
}: {
  details: EquipmentDetailsInput
  onDetails: (value: Partial<EquipmentDetailsInput>) => void
}) {
  return (
    <>
      <BarInput value={details.bar_kg} onChange={(bar_kg) => onDetails({ bar_kg })} />
      <PlatesInput value={details.plates ?? []} onChange={(plates) => onDetails({ plates })} />
    </>
  )
}
