import { createFileRoute, Link, redirect, useNavigate } from '@tanstack/react-router'
import { meQueryOptions } from '@/api/auth'
import { AuthShell } from '@/features/auth/auth-shell'
import { RegisterForm } from '@/features/auth/register-form'

export const Route = createFileRoute('/register')({
  beforeLoad: async ({ context }) => {
    if (await context.queryClient.ensureQueryData(meQueryOptions)) throw redirect({ to: '/' })
  },
  component: RegisterPage,
})

function RegisterPage() {
  const navigate = useNavigate()

  return (
    <AuthShell title="Регистрация">
      <RegisterForm onSuccess={() => navigate({ to: '/' })} />
      <p className="mt-6 text-base text-muted-foreground">
        Уже есть аккаунт?{' '}
        <Link to="/login" className="font-medium text-foreground underline underline-offset-4">
          Войти
        </Link>
      </p>
    </AuthShell>
  )
}
