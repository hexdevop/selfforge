import type { EquipmentCategory } from '@/api/catalog'

const kg = new Intl.NumberFormat('ru', { maximumFractionDigits: 2 })

/** API weights are strings like "17.50" → "17,5" for display. */
export const formatKg = (value: string | number) => kg.format(Number(value))

const pluralRules = new Intl.PluralRules('ru')

/** plural(5, ['упражнение', 'упражнения', 'упражнений']) → 'упражнений' */
export function plural(n: number, [one, few, many]: [string, string, string]): string {
  const form = pluralRules.select(n)
  return form === 'one' ? one : form === 'few' ? few : many
}

export const exercisesCount = (n: number) =>
  `${n} ${plural(n, ['упражнение', 'упражнения', 'упражнений'])}`

export const CATEGORY_LABELS: Record<EquipmentCategory, string> = {
  weights: 'Отягощения',
  bars: 'Турники и брусья',
  bands: 'Резинки и петли',
  bench: 'Скамьи и опоры',
  support: 'Подручное',
  bodyweight: 'Аксессуары',
}
