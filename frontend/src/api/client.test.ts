import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, setAccessToken } from './client'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('authFetch', () => {
  let fetchMock: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>

  beforeEach(() => {
    setAccessToken(null)
    fetchMock = vi.fn(async (request: Request) => {
      const path = new URL(request.url).pathname
      if (path === '/api/v1/auth/refresh') return json(200, { access_token: 'fresh' })
      if (request.headers.get('Authorization') === 'Bearer fresh') return json(200, { ok: true })
      return json(401, { detail: { code: 'invalid_token', message: 'x' } })
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => vi.unstubAllGlobals())

  const calls = (path: string) =>
    fetchMock.mock.calls.filter(([request]) => new URL(request.url).pathname === path)

  it('refreshes through the cookie on 401 and replays the request', async () => {
    const { response } = await api.GET('/api/v1/auth/me')

    expect(response.status).toBe(200)
    expect(calls('/api/v1/auth/refresh')).toHaveLength(1)
    expect(calls('/api/v1/auth/me')).toHaveLength(2)
  })

  it('shares one refresh between parallel 401s', async () => {
    await Promise.all([api.GET('/api/v1/auth/me'), api.GET('/api/v1/auth/me')])

    expect(calls('/api/v1/auth/refresh')).toHaveLength(1)
  })

  it('does not try to refresh after a failed login', async () => {
    const { response } = await api.POST('/api/v1/auth/login', {
      body: { login: 'alice', password: 'wrong' },
    })

    expect(response.status).toBe(401)
    expect(calls('/api/v1/auth/refresh')).toHaveLength(0)
  })
})
