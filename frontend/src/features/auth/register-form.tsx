import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { signIn } from '@/api/auth'
import { api } from '@/api/client'
import { applyApiError } from '@/api/errors'
import { FormError, FormField } from '@/components/form-field'
import { Button } from '@/components/ui/button'

// Mirrors UserCreate on the backend; the server still has the final say.
export const registerSchema = z.object({
  email: z.email('Похоже, в адресе опечатка'),
  username: z.string().trim().min(3, 'Не короче 3 символов').max(50, 'Не длиннее 50 символов'),
  full_name: z.string().trim().max(255, 'Слишком длинно'),
  password: z.string().min(8, 'Не короче 8 символов').max(128, 'Не длиннее 128 символов'),
})

type Values = z.infer<typeof registerSchema>

export function RegisterForm({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const form = useForm<Values>({ resolver: zodResolver(registerSchema) })
  const { errors, isSubmitting } = form.formState

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const { error } = await api.POST('/api/v1/auth/register', {
        body: { ...values, full_name: values.full_name || null },
      })
      if (error) return applyApiError(error, form.setError)

      const loginError = await signIn(queryClient, values.email, values.password)
      if (loginError) return applyApiError(loginError, form.setError)
      onSuccess()
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
      <FormField
        label="Имя пользователя"
        autoComplete="username"
        hint="Для входа, вместо email"
        error={errors.username?.message}
        {...form.register('username')}
      />
      <FormField
        label="Как тебя зовут"
        autoComplete="given-name"
        hint="Необязательно"
        error={errors.full_name?.message}
        {...form.register('full_name')}
      />
      <FormField
        label="Пароль"
        type="password"
        autoComplete="new-password"
        hint="Не короче 8 символов"
        error={errors.password?.message}
        {...form.register('password')}
      />
      <FormError message={errors.root?.message} />
      <Button type="submit" size="lg" disabled={isSubmitting}>
        Создать аккаунт
      </Button>
    </form>
  )
}
