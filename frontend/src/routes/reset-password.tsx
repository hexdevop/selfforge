import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { AuthShell } from '@/features/auth/auth-shell'
import { ResetPasswordForm } from '@/features/auth/password-reset-forms'

export const Route = createFileRoute('/reset-password')({
  validateSearch: (search): { token: string } => ({
    token: typeof search.token === 'string' ? search.token : '',
  }),
  component: ResetPasswordPage,
})

function ResetPasswordPage() {
  const { token } = Route.useSearch()
  const [done, setDone] = useState(false)

  if (done) {
    return (
      <AuthShell title="Пароль изменён">
        <p role="status" className="mb-6">
          Теперь войди с новым паролем. На других устройствах тоже понадобится войти заново.
        </p>
        <Button asChild size="lg" className="w-full">
          <Link to="/login">Войти</Link>
        </Button>
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Новый пароль">
      {token ? (
        <ResetPasswordForm token={token} onDone={() => setDone(true)} />
      ) : (
        <p>
          В ссылке не хватает кода.{' '}
          <Link to="/forgot-password" className="underline underline-offset-4">
            Запроси новую ссылку
          </Link>
          .
        </p>
      )}
    </AuthShell>
  )
}
