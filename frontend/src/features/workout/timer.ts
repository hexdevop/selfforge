import { useEffect, useState } from 'react'

/**
 * Seconds left, always recomputed from the moment the rest started.
 *
 * Nothing counts ticks: a backgrounded tab on iOS stops firing them, and a timer that
 * counted them would come back frozen and lie about how long the rest has been.
 */
export function secondsLeft(startedAt: number, seconds: number, now: number): number {
  return Math.max(0, Math.ceil((startedAt + seconds * 1000 - now) / 1000))
}

/** 88 → «1:28» */
export function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

/** Re-renders once a second while a rest is running; the value comes from the clock, not a count. */
export function useCountdown(startedAt: number | null, seconds: number): number | null {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (startedAt === null) return
    setNow(Date.now())
    const id = setInterval(() => setNow(Date.now()), 250)
    const resync = () => setNow(Date.now())
    document.addEventListener('visibilitychange', resync)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', resync)
    }
  }, [startedAt])

  return startedAt === null ? null : secondsLeft(startedAt, seconds, now)
}
