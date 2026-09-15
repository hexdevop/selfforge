import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { RegisterForm } from './register-form'

it('shows Russian validation messages and does not submit invalid data', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()

  render(
    <QueryClientProvider client={new QueryClient()}>
      <RegisterForm onSuccess={() => {}} />
    </QueryClientProvider>,
  )

  await user.type(screen.getByLabelText('Email'), 'not-an-email')
  await user.type(screen.getByLabelText('Имя пользователя'), 'al')
  await user.type(screen.getByLabelText('Пароль'), 'short')
  await user.click(screen.getByRole('button', { name: 'Создать аккаунт' }))

  expect(await screen.findByText('Похоже, в адресе опечатка')).toBeInTheDocument()
  expect(screen.getByText('Не короче 3 символов')).toBeInTheDocument()
  expect(screen.getByLabelText('Пароль')).toHaveAccessibleDescription('Не короче 8 символов')
  expect(fetchMock).not.toHaveBeenCalled()
  vi.unstubAllGlobals()
})
