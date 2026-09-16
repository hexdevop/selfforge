import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
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
  /** When the current rest began; a moment in time, never a count of ticks. */
  restStartedAt: number | null
  attempt: number
  failingSince: number | null
  records: PersonalRecord[]
  send: Sender
  /** Pick up a workout: what the server has, plus whatever this device still owes it. */
  open: (sessionId: string, fromServer?: SetLogIn[]) => void
  /** Forget the workout — only once it is finished or stopped on the server. */
  close: () => void
  enqueue: (set: SetLogIn) => void
  flush: () => Promise<void>
  startRest: () => void
  skipRest: () => void
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

const byTime = (a: SetLogIn, b: SetLogIn) => Date.parse(a.performed_at) - Date.parse(b.performed_at)

const empty = {
  sessionId: null,
  logged: [],
  pending: [],
  restStartedAt: null,
  attempt: 0,
  failingSince: null,
  records: [],
}

/** localStorage can be missing or throw (private mode, blocked storage): run on memory then. */
const storage = createJSONStorage(() => {
  try {
    return globalThis.localStorage
  } catch {
    return undefined as unknown as Storage
  }
})

export const useQueue = create<QueueState>()(
  // Persisted: iOS unloads a backgrounded tab, and sets still waiting for the network
  // must be there when the person comes back.
  persist(
    (set, get) => ({
      ...empty,
      send: sendSets,

      open: (sessionId, fromServer = []) => {
        cancelFlush()
        const current = get()
        if (current.sessionId !== sessionId) {
          set({ ...empty, sessionId, logged: [...fromServer].sort(byTime) })
          return
        }
        const known = new Set(fromServer.map((s) => s.client_uuid))
        const local = current.logged.filter((s) => !known.has(s.client_uuid))
        const pending = current.pending.filter((id) => !known.has(id))
        set({
          logged: [...fromServer, ...local].sort(byTime),
          pending,
          attempt: 0,
          failingSince: null,
        })
        if (pending.length > 0) scheduleFlush(0, get().flush)
      },

      close: () => {
        cancelFlush()
        set(empty)
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

      startRest: () => set({ restStartedAt: Date.now() }),
      skipRest: () => set({ restStartedAt: null }),
    }),
    {
      name: 'selfforge:workout-buffer',
      storage,
      partialize: ({ sessionId, logged, pending, restStartedAt }) => ({
        sessionId,
        logged,
        pending,
        restStartedAt,
      }),
    },
  ),
)

/** True once the queue has been failing long enough to be worth a word on screen. */
export function isStale(failingSince: number | null, now: number): boolean {
  return failingSince !== null && now - failingSince >= STALE_AFTER_MS
}
