import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { signIn } from '@/api/auth'
import { applyApiError } from '@/api/errors'
import { FormError, FormField } from '@/components/form-field'
import { Button } from '@/components/ui/button'

const schema = z.object({
  login: z.string().trim().min(1, 'Введи email или имя пользователя'),
  password: z.string().min(1, 'Введи пароль'),
})

type Values = z.infer<typeof schema>

export function LoginForm({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const form = useForm<Values>({ resolver: zodResolver(schema) })
  const { errors, isSubmitting } = form.formState

  const onSubmit = form.handleSubmit(async ({ login, password }) => {
    try {
      const error = await signIn(queryClient, login, password)
      if (error) return applyApiError(error, form.setError)
      onSuccess()
    } catch {
      applyApiError(undefined, form.setError)
    }
  })

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <FormField
        label="Email или имя пользователя"
        autoComplete="username"
        error={errors.login?.message}
        {...form.register('login')}
      />
      <FormField
        label="Пароль"
        type="password"
        autoComplete="current-password"
        error={errors.password?.message}
        {...form.register('password')}
      />
      <FormError message={errors.root?.message} />
      <Button type="submit" size="lg" disabled={isSubmitting}>
        Войти
      </Button>
    </form>
  )
}
