import { useMutation } from '@tanstack/react-query'
import { authFetch } from '@/api/client'
import { Button } from '@/components/ui/button'

async function download(): Promise<void> {
  const response = await authFetch(new Request(`${location.origin}/api/v1/export/all`))
  if (!response.ok) throw new Error('Не получилось собрать файл. Попробуй ещё раз чуть позже')
  const name =
    /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')?.[1] ??
    'selfforge.json'
  const url = URL.createObjectURL(await response.blob())
  const link = Object.assign(document.createElement('a'), { href: url, download: name })
  link.click()
  URL.revokeObjectURL(url)
}

/** Principle 6: the data belongs to the person — all of it, in one file, any time. */
export function ExportData() {
  const run = useMutation({ mutationFn: download })
  return (
    <div className="flex flex-col items-start gap-2">
      <p className="text-muted-foreground">
        Все тренировки, подходы, программы, замеры и места — одним файлом JSON. Фото в файле
        представлены ссылками, которые действуют 15 минут.
      </p>
      <Button variant="outline" disabled={run.isPending} onClick={() => run.mutate()}>
        {run.isPending ? 'Собираем файл…' : 'Скачать мои данные'}
      </Button>
      {run.isError && (
        <p className="text-sm text-destructive" role="alert">
          {run.error.message}
        </p>
      )}
    </div>
  )
}
