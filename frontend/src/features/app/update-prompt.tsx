import { useRegisterSW } from 'virtual:pwa-register/react'
import { Button } from '@/components/ui/button'

/** A new version waits for a tap rather than reloading the page on its own mid-workout. */
export function UpdatePrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW()
  if (!needRefresh) return null

  return (
    <div
      role="status"
      className="fixed inset-x-4 bottom-4 z-50 mx-auto flex max-w-md flex-wrap items-center gap-3 rounded-xl border bg-card p-4 shadow-lg"
    >
      <p className="grow">Есть новая версия приложения.</p>
      <div className="flex gap-2">
        <Button variant="ghost" onClick={() => setNeedRefresh(false)}>
          Позже
        </Button>
        <Button onClick={() => updateServiceWorker(true)}>Обновить</Button>
      </div>
    </div>
  )
}
