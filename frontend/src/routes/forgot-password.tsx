import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { AuthShell } from '@/features/auth/auth-shell'
import { ForgotPasswordForm } from '@/features/auth/password-reset-forms'

export const Route = createFileRoute('/forgot-password')({
  component: ForgotPasswordPage,
})

function ForgotPasswordPage() {
  const [sent, setSent] = useState(false)

  return (
    <AuthShell title="Сброс пароля">
      {sent ? (
        <p role="status">
          Если такой адрес зарегистрирован, письмо со ссылкой уже в пути. Проверь почту, в том числе
          папку «Спам».
        </p>
      ) : (
        <>
          <p className="mb-6 text-muted-foreground">
            Укажи email, с которым регистрировался, — пришлём ссылку для нового пароля.
          </p>
          <ForgotPasswordForm onSent={() => setSent(true)} />
        </>
      )}
      <Link to="/login" className="mt-6 inline-block underline underline-offset-4">
        Вернуться ко входу
      </Link>
    </AuthShell>
  )
}
