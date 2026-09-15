import { createFileRoute, Link } from '@tanstack/react-router'
import { useMe } from '@/api/auth'
import { Button } from '@/components/ui/button'

export const Route = createFileRoute('/_authed/')({
  component: Cabinet,
})

function Cabinet() {
  const user = useMe()
  if (!user) return null

  return (
    <section className="flex max-w-prose flex-col items-start gap-5">
      <h1 className="text-2xl font-semibold">Привет, {user.full_name || user.username}!</h1>
      <p className="text-muted-foreground">
        Здесь появится твоя программа. Скоро расскажешь, какое у тебя железо и сколько дней в неделю
        готов тренироваться, — и мы соберём план под тебя. А пока можно посмотреть, из чего он будет
        состоять.
      </p>
      <Button asChild size="lg">
        <Link to="/exercises">Посмотреть упражнения</Link>
      </Button>
    </section>
  )
}
