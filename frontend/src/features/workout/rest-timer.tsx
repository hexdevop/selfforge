import { useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { chime } from './chime'
import { clock, useCountdown } from './timer'

type RestTimerProps = {
  startedAt: number | null
  seconds: number
  onSkip: () => void
}

/** Runs off the moment the rest began, so backgrounding the app can't freeze it. */
export function RestTimer({ startedAt, seconds, onSkip }: RestTimerProps) {
  const left = useCountdown(startedAt, seconds)
  const rang = useRef<number | null>(null)

  useEffect(() => {
    if (startedAt === null || left === null || left > 0) return
    if (rang.current === startedAt) return
    rang.current = startedAt
    chime()
  }, [startedAt, left])

  if (startedAt === null || left === null) {
    return (
      <p className="min-h-11 text-muted-foreground" aria-live="off">
        Отдых начнётся сам, как только подтвердишь подход
      </p>
    )
  }

  const done = left === 0
  return (
    <div className="flex items-center justify-between gap-4">
      <p className="text-lg tabular-nums" aria-hidden>
        {done ? (
          <span className="font-medium">Отдых закончился</span>
        ) : (
          <>
            Отдых <span className="font-medium">{clock(left)}</span>
          </>
        )}
      </p>
      {/* A screen reader shouldn't hear every second — only the state that matters. */}
      <span role="status" className="sr-only">
        {done ? 'Отдых закончился' : 'Идёт отдых'}
      </span>
      {!done && (
        <Button variant="ghost" onClick={onSkip}>
          Пропустить отдых
        </Button>
      )}
    </div>
  )
}
