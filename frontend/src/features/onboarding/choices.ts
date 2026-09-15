import type { Choice } from '@/components/choice-group'

export const HEALTH_CHOICES: Choice[] = [
  { value: 'knees', label: 'Колени' },
  { value: 'shoulders', label: 'Плечи' },
  { value: 'lower_back', label: 'Поясница' },
  { value: 'wrists', label: 'Запястья' },
  { value: 'neck', label: 'Шея' },
  { value: 'elbows', label: 'Локти' },
]

export const PUSHUP_CHOICES: Choice[] = [
  { value: '0', label: '0' },
  { value: '1-5', label: '1–5' },
  { value: '6-15', label: '6–15' },
  { value: '16-30', label: '16–30' },
  { value: '30+', label: 'Больше 30' },
]

export const PULLUP_CHOICES: Choice[] = [
  { value: '0', label: '0' },
  { value: '1-3', label: '1–3' },
  { value: '4-8', label: '4–8' },
  { value: '9-15', label: '9–15' },
  { value: '15+', label: 'Больше 15' },
]

export const SQUAT_CHOICES: Choice[] = [
  { value: '<10', label: 'Меньше 10' },
  { value: '10-25', label: '10–25' },
  { value: '25-50', label: '25–50' },
  { value: '50+', label: 'Больше 50' },
]

export const PISTOL_CHOICES: Choice[] = [
  { value: 'no', label: 'Нет' },
  { value: 'assisted', label: 'С опорой рукой' },
  { value: 'yes', label: 'Да' },
]

export const YES_NO: Choice[] = [
  { value: 'yes', label: 'Да' },
  { value: 'no', label: 'Нет' },
]

export const GOAL_CHOICES: Choice[] = [
  { value: 'hypertrophy', label: 'Мышечная масса', description: 'Больше мышц: 6–15 повторов' },
  {
    value: 'strength',
    label: 'Сила',
    description: 'Тяжёлые подходы и сложные варианты движений',
  },
  { value: 'endurance', label: 'Выносливость', description: 'Много повторов, короткий отдых' },
  { value: 'fat_loss', label: 'Снижение веса', description: 'Силовые плюс короткие финишеры' },
  {
    value: 'skill',
    label: 'Навыки',
    description: 'Подтягивания, выход силой, пистолетик, стойка на руках',
  },
  { value: 'health', label: 'Здоровье', description: 'Регулярность и самочувствие' },
  { value: 'maintenance', label: 'Поддержание формы', description: 'Сохранить то, что есть' },
]

export const DAYS_CHOICES: Choice[] = ['2', '3', '4', '5', '6'].map((d) => ({
  value: d,
  label: d,
}))

export const MINUTES_CHOICES: Choice[] = ['20', '30', '45', '60', '75', '90'].map((m) => ({
  value: m,
  label: `${m} мин`,
}))

export const OVERALL_LABELS = {
  beginner: 'начальный',
  intermediate: 'средний',
  advanced: 'продвинутый',
} as const
