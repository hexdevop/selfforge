import { Share, SquarePlus, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { dismiss, isInstalled, isIosSafari, wasDismissed } from './install'

type InstallPrompt = Event & { prompt: () => Promise<void> }

/**
 * iOS never suggests installing a site, so the app says how (docs/05-frontend.md, PWA).
 * Android and desktop Chrome hand over their own prompt, which gets a button instead.
 */
export function InstallHint() {
  const [hidden, setHidden] = useState(() => isInstalled() || wasDismissed())
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null)
  const ios = isIosSafari(navigator.userAgent, navigator.maxTouchPoints)

  useEffect(() => {
    const capture = (event: Event) => {
      event.preventDefault()
      setPrompt(event as InstallPrompt)
    }
    window.addEventListener('beforeinstallprompt', capture)
    return () => window.removeEventListener('beforeinstallprompt', capture)
  }, [])

  if (hidden || (!ios && !prompt)) return null
  const close = () => {
    dismiss()
    setHidden(true)
  }

  return (
    <aside
      aria-label="Установка приложения"
      className="relative flex w-full flex-col gap-2 rounded-xl border bg-card p-4 pr-12"
    >
      <p className="font-medium">Удобнее как приложение</p>
      {ios ? (
        <p>
          В Safari нажми{' '}
          <Share className="inline size-4 align-text-bottom" aria-label="Поделиться" />{' '}
          «Поделиться», затем <SquarePlus className="inline size-4 align-text-bottom" aria-hidden />{' '}
          «На экран „Домой“». Откроется на весь экран и не потеряется среди вкладок.
        </p>
      ) : (
        <>
          <p>Установи на телефон — откроется на весь экран и не потеряется среди вкладок.</p>
          <Button
            className="self-start"
            onClick={async () => {
              await prompt?.prompt()
              close()
            }}
          >
            Установить приложение
          </Button>
        </>
      )}
      <Button
        variant="ghost"
        size="icon-lg"
        className="absolute top-2 right-2 size-11"
        aria-label="Скрыть подсказку"
        onClick={close}
      >
        <X />
      </Button>
    </aside>
  )
}
