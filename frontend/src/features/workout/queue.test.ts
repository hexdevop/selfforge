import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SetLogIn } from '@/api/sessions'
import { backoffMs, FLUSH_DELAY_MS, isStale, STALE_AFTER_MS, useQueue } from './queue'

const set = (id: string, reps = 10): SetLogIn => ({
  client_uuid: id,
  exercise_slug: 'goblet-squat',
  set_index: 0,
  reps,
  performed_at: '2026-09-16T10:00:00Z',
})

const state = () => useQueue.getState()

beforeEach(() => {
  vi.useFakeTimers()
  state().close()
})

afterEach(() => {
  state().close()
  vi.useRealTimers()
})

describe('the set buffer', () => {
  it('shows a set immediately and sends it a moment later', async () => {
    const send = vi.fn().mockResolvedValue({ records: [] })
    state().open('s1')
    useQueue.setState({ send })

    state().enqueue(set('a'))

    expect(state().logged).toHaveLength(1)
    expect(state().pending).toEqual(['a'])
    expect(send).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(FLUSH_DELAY_MS)

    expect(send).toHaveBeenCalledWith('s1', [set('a')])
    expect(state().pending).toEqual([])
  })

  it('sends everything buffered in one batch', async () => {
    const send = vi.fn().mockResolvedValue({ records: [] })
    state().open('s1')
    useQueue.setState({ send })

    state().enqueue(set('a'))
    state().enqueue(set('b'))
    await vi.advanceTimersByTimeAsync(FLUSH_DELAY_MS)

    expect(send).toHaveBeenCalledTimes(1)
    expect(send.mock.calls[0]?.[1]).toHaveLength(2)
  })

  it('keeps the sets on screen and retries when the network drops', async () => {
    const send = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue({ records: [] })
    state().open('s1')
    useQueue.setState({ send })

    state().enqueue(set('a'))
    await vi.advanceTimersByTimeAsync(FLUSH_DELAY_MS)

    expect(state().logged).toHaveLength(1)
    expect(state().pending).toEqual(['a'])
    expect(state().failingSince).not.toBeNull()

    await vi.advanceTimersByTimeAsync(backoffMs(1))
    await vi.advanceTimersByTimeAsync(backoffMs(2))

    expect(send).toHaveBeenCalledTimes(3)
    expect(state().pending).toEqual([])
    expect(state().failingSince).toBeNull()
  })

  it('sends sets confirmed while offline once the connection is back', async () => {
    const send = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({
      records: [],
    })
    state().open('s1')
    useQueue.setState({ send })

    state().enqueue(set('a'))
    await vi.advanceTimersByTimeAsync(FLUSH_DELAY_MS)
    state().enqueue(set('b'))
    await vi.advanceTimersByTimeAsync(backoffMs(1) + FLUSH_DELAY_MS)

    expect(send.mock.calls.at(-1)?.[1].map((s: SetLogIn) => s.client_uuid)).toEqual(['a', 'b'])
    expect(state().pending).toEqual([])
  })

  it('never logs the same set twice', () => {
    state().open('s1')
    state().enqueue(set('a'))
    state().enqueue(set('a', 99))

    expect(state().logged).toHaveLength(1)
    expect(state().logged[0]?.reps).toBe(10)
  })

  it('backs off further after each failure but not forever', () => {
    expect(backoffMs(1)).toBe(1_000)
    expect(backoffMs(2)).toBe(2_000)
    expect(backoffMs(3)).toBe(4_000)
    expect(backoffMs(20)).toBe(30_000)
  })

  it('stays quiet about a hiccup and speaks up only after half a minute', () => {
    expect(isStale(null, 1_000)).toBe(false)
    expect(isStale(1_000, 1_000 + STALE_AFTER_MS - 1)).toBe(false)
    expect(isStale(1_000, 1_000 + STALE_AFTER_MS)).toBe(true)
  })
})
