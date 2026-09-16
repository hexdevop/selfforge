import { create } from 'zustand'
import { type PersonalRecord, type SetLogIn, sendSets } from '@/api/sessions'

/** Confirming a set must feel instant, so the buffer is flushed on a timer, not per tap. */
export const FLUSH_DELAY_MS = 2_000
/** Only after this long without reaching the server is the person told anything. */
export const STALE_AFTER_MS = 30_000
const MAX_BACKOFF_MS = 30_000
const BATCH_LIMIT = 200

export type Sender = (sessionId: string, sets: SetLogIn[]) => Promise<{ records: PersonalRecord[] }>

export function backoffMs(attempt: number): number {
  return Math.min(MAX_BACKOFF_MS, 1_000 * 2 ** Math.max(0, attempt - 1))
}

type QueueState = {
  sessionId: string | null
  /** Everything confirmed on this device, in the order it was done. */
  logged: SetLogIn[]
  /** `client_uuid` of sets the server hasn't acknowledged yet. */
  pending: string[]
  attempt: number
  failingSince: number | null
  records: PersonalRecord[]
  send: Sender
  open: (sessionId: string, logged?: SetLogIn[]) => void
  close: () => void
  enqueue: (set: SetLogIn) => void
  flush: () => Promise<void>
}

let timer: ReturnType<typeof setTimeout> | null = null

function cancelFlush(): void {
  if (timer !== null) clearTimeout(timer)
  timer = null
}

function scheduleFlush(delay: number, flush: () => Promise<void>): void {
  cancelFlush()
  timer = setTimeout(() => {
    timer = null
    void flush()
  }, delay)
}

export const useQueue = create<QueueState>((set, get) => ({
  sessionId: null,
  logged: [],
  pending: [],
  attempt: 0,
  failingSince: null,
  records: [],
  send: sendSets,

  open: (sessionId, logged = []) => {
    cancelFlush()
    set({ sessionId, logged, pending: [], attempt: 0, failingSince: null, records: [] })
  },

  close: () => {
    cancelFlush()
    set({ sessionId: null, logged: [], pending: [], attempt: 0, failingSince: null, records: [] })
  },

  enqueue: (entry) => {
    const { logged, pending, flush } = get()
    if (logged.some((s) => s.client_uuid === entry.client_uuid)) return
    set({ logged: [...logged, entry], pending: [...pending, entry.client_uuid] })
    scheduleFlush(FLUSH_DELAY_MS, flush)
  },

  flush: async () => {
    const { sessionId, logged, pending, attempt, send, flush } = get()
    if (!sessionId || pending.length === 0) return
    cancelFlush()

    const batch = logged.filter((s) => pending.includes(s.client_uuid)).slice(0, BATCH_LIMIT)
    try {
      const { records } = await send(sessionId, batch)
      const sent = new Set(batch.map((s) => s.client_uuid))
      const left = get().pending.filter((id) => !sent.has(id))
      set({
        pending: left,
        attempt: 0,
        failingSince: null,
        records: [...get().records, ...records],
      })
      if (left.length > 0) scheduleFlush(0, flush)
    } catch {
      // The sets stay in `logged` and keep showing; only the trip to the server failed.
      const next = attempt + 1
      set({ attempt: next, failingSince: get().failingSince ?? Date.now() })
      scheduleFlush(backoffMs(next), flush)
    }
  },
}))

/** True once the queue has been failing long enough to be worth a word on screen. */
export function isStale(failingSince: number | null, now: number): boolean {
  return failingSince !== null && now - failingSince >= STALE_AFTER_MS
}
