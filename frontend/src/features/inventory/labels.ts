import type { Equipment } from '@/api/catalog'
import type { LocationKind } from '@/api/locations'

export const KIND_LABELS: Record<LocationKind, string> = {
  home: 'Дом',
  outdoor_gym: 'Площадка',
  outdoor_bare: 'Улица без оборудования',
  travel: 'Поездка',
}

/** What most places already have, so nobody has to tick "wall" by hand. */
export const DEFAULT_EQUIPMENT: Record<LocationKind, string[]> = {
  home: ['chair', 'sofa', 'wall', 'towel'],
  outdoor_gym: ['pullup_bar', 'low_bar', 'parallel_bars'],
  outdoor_bare: ['stairs'],
  travel: ['chair', 'wall', 'towel'],
}

/** Outdoor-only items (parallel bars, monkey bars…) are offered only for playgrounds. */
export const visibleEquipment = (kind: LocationKind, items: Equipment[]) =>
  kind === 'outdoor_gym' ? items : items.filter((item) => !item.is_outdoor)

export const SURFACE_CHOICES = [
  { value: 'rubber', label: 'Резина' },
  { value: 'sand', label: 'Песок' },
  { value: 'asphalt', label: 'Асфальт' },
]

export const RESISTANCE_CHOICES = [
  { value: 'light', label: 'Лёгкая' },
  { value: 'medium', label: 'Средняя' },
  { value: 'heavy', label: 'Тяжёлая' },
]

export const PLATE_SIZES = ['0.5', '1', '1.25', '2', '2.5', '5', '10', '15', '20', '25']

/** International plate colour coding: carries information, not decoration. */
export const PLATE_COLORS: Record<string, string> = {
  '25': 'var(--plate-25)',
  '20': 'var(--plate-20)',
  '15': 'var(--plate-15)',
  '10': 'var(--plate-10)',
  '5': 'var(--plate-5)',
  '2.5': 'var(--plate-2-5)',
}

/** Items whose weights or plates we need to know. */
export const DETAILED = new Set(['dumbbell', 'kettlebell', 'barbell', 'resistance_band'])
