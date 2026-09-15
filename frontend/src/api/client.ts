import createClient from 'openapi-fetch'
import type { paths } from './schema'

// The access token lives only in memory; the refresh token is an httpOnly cookie
// the browser attaches to /api/v1/auth/* by itself. On reload the first request gets
// a 401, we refresh through the cookie and replay it.
let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null

const NO_REFRESH_PATHS = ['/api/v1/auth/login', '/api/v1/auth/refresh', '/api/v1/auth/logout']

// Explicit origin: Node's Request (tests) doesn't resolve relative URLs like browsers do.
const baseUrl = globalThis.location.origin

// Resolve fetch at call time (not at client creation) so it can be stubbed in tests.
const bare = createClient<paths>({ baseUrl, fetch: (request) => fetch(request) })

export function setAccessToken(token: string | null): void {
  accessToken = token
}

function refreshAccessToken(): Promise<boolean> {
  // Single flight: parallel 401s share one refresh, since each refresh rotates the cookie.
  refreshing ??= bare
    .POST('/api/v1/auth/refresh')
    .then(({ data }) => {
      accessToken = data?.access_token ?? null
      return accessToken !== null
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

export async function authFetch(request: Request): Promise<Response> {
  const send = () => {
    const attempt = request.clone()
    if (accessToken) attempt.headers.set('Authorization', `Bearer ${accessToken}`)
    return fetch(attempt)
  }

  const response = await send()
  const path = new URL(request.url).pathname
  if (response.status !== 401 || NO_REFRESH_PATHS.includes(path)) return response
  return (await refreshAccessToken()) ? send() : response
}

export const api = createClient<paths>({ baseUrl, fetch: authFetch })
