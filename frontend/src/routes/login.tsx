import { createFileRoute, Link, redirect, useNavigate } from '@tanstack/react-router'
import { meQueryOptions } from '@/api/auth'
import { AuthShell } from '@/features/auth/auth-shell'
import { LoginForm } from '@/features/auth/login-form'

// Only same-app paths: never bounce to another origin after login.
const safeRedirect = (target?: string) =>
  target?.startsWith('/') && !target.startsWith('//') ? target : '/'

export const Route = createFileRoute('/login')({
  validateSearch: (search): { redirect?: string } =>
    typeof search.redirect === 'string' ? { redirect: search.redirect } : {},
  beforeLoad: async ({ context }) => {
    if (await context.queryClient.ensureQueryData(meQueryOptions)) throw redirect({ to: '/' })
  },
  component: LoginPage,
})

function LoginPage() {
  const { redirect: target } = Route.useSearch()
  const navigate = useNavigate()

  return (
    <AuthShell title="Вход">
      <LoginForm onSuccess={() => navigate({ href: safeRedirect(target) })} />
      <div className="mt-6 flex flex-col gap-3 text-base">
        <Link to="/forgot-password" className="underline underline-offset-4">
          Забыл пароль
        </Link>
        <p className="text-muted-foreground">
          Нет аккаунта?{' '}
          <Link to="/register" className="font-medium text-foreground underline underline-offset-4">
            Зарегистрироваться
          </Link>
        </p>
      </div>
    </AuthShell>
  )
}
