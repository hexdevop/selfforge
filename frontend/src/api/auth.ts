import { type QueryClient, queryOptions, useQuery } from '@tanstack/react-query'
import { api, setAccessToken } from './client'
import type { ApiError } from './errors'
import type { components } from './schema'

export type User = components['schemas']['UserRead']

export const meQueryOptions = queryOptions({
  queryKey: ['me'],
  queryFn: async (): Promise<User | null> => {
    const { data, response } = await api.GET('/api/v1/auth/me')
    if (response.status === 401) return null
    if (!data) throw new Error(`GET /auth/me failed: ${response.status}`)
    return data
  },
  staleTime: Number.POSITIVE_INFINITY,
})

/** Current user from the query cache; null when signed out. */
export function useMe(): User | null {
  return useQuery(meQueryOptions).data ?? null
}

/** Returns the API error on failure; on success the `me` query holds the user. */
export async function signIn(
  queryClient: QueryClient,
  login: string,
  password: string,
): Promise<ApiError | undefined> {
  const { data, error } = await api.POST('/api/v1/auth/login', { body: { login, password } })
  if (!data) return error
  setAccessToken(data.access_token)
  await queryClient.fetchQuery({ ...meQueryOptions, staleTime: 0 })
}

export async function signOut(queryClient: QueryClient): Promise<void> {
  await api.POST('/api/v1/auth/logout').catch(() => undefined)
  setAccessToken(null)
  queryClient.clear()
  queryClient.setQueryData(meQueryOptions.queryKey, null)
}
