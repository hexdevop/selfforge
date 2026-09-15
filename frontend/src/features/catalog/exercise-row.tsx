import { Link } from '@tanstack/react-router'
import type { Equipment, ExerciseSummary } from '@/api/catalog'
import { equipmentText } from './labels'

export function ExerciseRow({
  exercise,
  equipment,
  showLevel = true,
}: {
  exercise: ExerciseSummary
  equipment: Map<string, Equipment>
  showLevel?: boolean
}) {
  return (
    <li>
      <Link
        to="/exercises/$slug"
        params={{ slug: exercise.slug }}
        className="flex min-h-11 flex-col gap-0.5 rounded-md px-2 py-3 hover:bg-card focus-visible:bg-card"
      >
        <span className="text-lg font-semibold leading-snug">{exercise.title_ru}</span>
        <span className="text-sm text-muted-foreground">
          {showLevel && `Ступень ${exercise.difficulty_level} · `}
          {equipmentText(exercise.required_equipment, equipment)}
          {exercise.is_unilateral && ' · по одной стороне'}
        </span>
      </Link>
    </li>
  )
}
