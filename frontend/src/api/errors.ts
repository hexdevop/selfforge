import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'
import type { components } from './schema'

export type ApiError = components['schemas']['ErrorResponse']

const NETWORK_MESSAGE = 'Нет связи с сервером. Проверь интернет и попробуй ещё раз'

/** Put server-side field errors on their inputs and the general message on the form root. */
export function applyApiError<T extends FieldValues>(
  error: ApiError | undefined,
  setError: UseFormSetError<T>,
): void {
  const detail = error?.detail
  for (const [field, message] of Object.entries(detail?.fields ?? {})) {
    setError(field as Path<T>, { message })
  }
  setError('root', { message: detail?.message ?? NETWORK_MESSAGE })
}
