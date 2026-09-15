import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api } from '@/api/client'
import { applyApiError } from '@/api/errors'
import { FormError, FormField } from '@/components/form-field'
import { Button } from '@/components/ui/button'

const requestSchema = z.object({ email: z.email('Похоже, в адресе опечатка') })

export function ForgotPasswordForm({ onSent }: { onSent: () => void }) {
  const form = useForm<z.infer<typeof requestSchema>>({ resolver: zodResolver(requestSchema) })
  const { errors, isSubmitting } = form.formState

  const onSubmit = form.handleSubmit(async (body) => {
    try {
      const { error } = await api.POST('/api/v1/auth/password-reset/request', { body })
      if (error) return applyApiError(error, form.setError)
      onSent()
    } catch {
      applyApiError(undefined, form.setError)
    }
  })

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <FormField
        label="Email"
        type="email"
        autoComplete="email"
        error={errors.email?.message}
        {...form.register('email')}
      />
      <FormError message={errors.root?.message} />
      <Button type="submit" size="lg" disabled={isSubmitting}>
        Отправить ссылку
      </Button>
    </form>
  )
}

const confirmSchema = z.object({
  password: z.string().min(8, 'Не короче 8 символов').max(128, 'Не длиннее 128 символов'),
})

export function ResetPasswordForm({ token, onDone }: { token: string; onDone: () => void }) {
  const form = useForm<z.infer<typeof confirmSchema>>({ resolver: zodResolver(confirmSchema) })
  const { errors, isSubmitting } = form.formState

  const onSubmit = form.handleSubmit(async ({ password }) => {
    try {
      const { error } = await api.POST('/api/v1/auth/password-reset/confirm', {
        body: { token, password },
      })
      if (error) return applyApiError(error, form.setError)
      onDone()
    } catch {
      applyApiError(undefined, form.setError)
    }
  })

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <FormField
        label="Новый пароль"
        type="password"
        autoComplete="new-password"
        hint="Не короче 8 символов"
        error={errors.password?.message}
        {...form.register('password')}
      />
      <FormError message={errors.root?.message} />
      <Button type="submit" size="lg" disabled={isSubmitting}>
        Сохранить пароль
      </Button>
    </form>
  )
}
