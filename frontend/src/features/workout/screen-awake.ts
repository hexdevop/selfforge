import { useEffect } from 'react'

type WakeLockSentinel = { release: () => Promise<void> }
type WakeLockNavigator = { wakeLock?: { request: (type: 'screen') => Promise<WakeLockSentinel> } }

/**
 * Keeps the screen on for the length of the workout.
 *
 * The lock is dropped by the browser whenever the tab goes to the background, so it is
 * taken again on every return — otherwise the screen starts dimming mid-session.
 */
export function useScreenAwake(active: boolean): void {
  useEffect(() => {
    if (!active) return
    const wakeLock = (navigator as WakeLockNavigator).wakeLock
    if (!wakeLock) return

    let sentinel: WakeLockSentinel | null = null
    let dropped = false

    const acquire = async () => {
      if (dropped || document.visibilityState !== 'visible') return
      try {
        sentinel = await wakeLock.request('screen')
      } catch {
        // Denied (low battery, no permission). The workout works fine without it.
      }
    }

    void acquire()
    document.addEventListener('visibilitychange', acquire)
    return () => {
      dropped = true
      document.removeEventListener('visibilitychange', acquire)
      void sentinel?.release().catch(() => {})
    }
  }, [active])
}
