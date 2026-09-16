import { useQuery } from '@tanstack/react-query'
import { exerciseQuery } from '@/api/catalog'

/** Technique opens right here: leaving the screen mid-set loses the timer and the place. */
export function Technique({ slug, open }: { slug: string; open: boolean }) {
  const { data: exercise } = useQuery({ ...exerciseQuery(slug), enabled: open })
  if (!open) return null
  if (!exercise) return <p className="text-muted-foreground">Загружаем технику…</p>

  const gif = exercise.media.gif ?? exercise.media.image
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-muted/40 p-4">
      {gif && (
        <img
          src={gif}
          alt={`Техника: ${exercise.title_ru}`}
          loading="lazy"
          className="rounded-lg"
        />
      )}
      <p>{exercise.technique_ru}</p>
      {exercise.common_mistakes_ru.length > 0 && (
        <div className="flex flex-col gap-1">
          <h4 className="text-sm font-medium text-muted-foreground">На что смотреть</h4>
          <ul className="flex list-disc flex-col gap-1 pl-5">
            {exercise.common_mistakes_ru.map((mistake) => (
              <li key={mistake}>{mistake}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
