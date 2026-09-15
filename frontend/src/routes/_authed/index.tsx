import { createFileRoute } from '@tanstack/react-router'
import { useMe } from '@/api/auth'

export const Route = createFileRoute('/_authed/')({
  component: Cabinet,
})

function Cabinet() {
  const user = useMe()
  if (!user) return null

  return (
    <section className="max-w-prose">
      <h1 className="mb-3 text-2xl font-semibold">Привет, {user.full_name || user.username}!</h1>
      <p className="text-muted-foreground">
        Здесь появится твоя программа. Скоро расскажешь, какое у тебя железо и сколько дней в неделю
        готов тренироваться, — и мы соберём план под тебя.
      </p>
    </section>
  )
}
