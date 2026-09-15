import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Outlet, redirect, useNavigate } from '@tanstack/react-router'
import { meQueryOptions, signOut, type User, useMe } from '@/api/auth'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'

export const Route = createFileRoute('/_authed')({
  beforeLoad: async ({ context, location }) => {
    const user = await context.queryClient.ensureQueryData(meQueryOptions)
    if (!user) throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: AuthedLayout,
})

function AuthedLayout() {
  const user = useMe()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const logout = async () => {
    await signOut(queryClient)
    await navigate({ to: '/login' })
  }

  if (!user) return null

  return (
    <div className="min-h-dvh">
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-2">
          <span className="text-lg font-bold tracking-tight">Self Forge</span>
          <Button variant="ghost" onClick={logout}>
            Выйти
          </Button>
        </div>
      </header>
      {!user.is_verified && <VerifyEmailNotice user={user} />}
      <main className="mx-auto max-w-3xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}

function VerifyEmailNotice({ user }: { user: User }) {
  const resend = useMutation({
    mutationFn: async () => {
      const { response } = await api.POST('/api/v1/auth/verify-email/resend')
      if (!response.ok) throw new Error(String(response.status))
    },
  })

  return (
    <div className="border-b bg-secondary/60">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <p className="grow">
          {resend.isSuccess
            ? `Отправили ещё одно письмо на ${user.email}.`
            : `Подтверди почту: ссылка в письме на ${user.email}.`}
          {resend.isError && ' Не получилось отправить, попробуй чуть позже.'}
        </p>
        {!resend.isSuccess && (
          <Button variant="outline" onClick={() => resend.mutate()} disabled={resend.isPending}>
            Отправить письмо ещё раз
          </Button>
        )}
      </div>
    </div>
  )
}
