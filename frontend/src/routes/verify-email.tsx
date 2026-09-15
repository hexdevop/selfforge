import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { meQueryOptions } from '@/api/auth'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { AuthShell } from '@/features/auth/auth-shell'

export const Route = createFileRoute('/verify-email')({
  validateSearch: (search): { token: string } => ({
    token: typeof search.token === 'string' ? search.token : '',
  }),
  component: VerifyEmailPage,
})

function VerifyEmailPage() {
  const { token } = Route.useSearch()
  const queryClient = useQueryClient()

  // A query rather than a mutation: verification is idempotent, and this dedupes
  // the double mount under StrictMode.
  const verify = useQuery({
    queryKey: ['verify-email', token],
    queryFn: async () => {
      const { response } = await api.POST('/api/v1/auth/verify-email', { body: { token } })
      if (response.ok) await queryClient.invalidateQueries({ queryKey: meQueryOptions.queryKey })
      return response.ok
    },
    enabled: Boolean(token),
    retry: false,
    staleTime: Number.POSITIVE_INFINITY,
  })

  if (token && verify.isPending) {
    return (
      <AuthShell title="Подтверждаем почту">
        <p role="status">Секунду…</p>
      </AuthShell>
    )
  }

  if (verify.data) {
    return (
      <AuthShell title="Почта подтверждена">
        <p className="mb-6">Всё готово, можно продолжать.</p>
        <Button asChild size="lg" className="w-full">
          <Link to="/">Продолжить</Link>
        </Button>
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Ссылка не сработала">
      <p className="mb-6">
        {verify.isError
          ? 'Нет связи с сервером. Проверь интернет и открой ссылку ещё раз.'
          : 'Ссылка устарела или уже не действует. Войди — и в кабинете сможешь отправить новое письмо.'}
      </p>
      <Button asChild size="lg" className="w-full">
        <Link to="/">Перейти в кабинет</Link>
      </Button>
    </AuthShell>
  )
}
