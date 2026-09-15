import '@/index.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Button } from './components/ui/button'
import { routeTree } from './routeTree.gen'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
  defaultErrorComponent: ({ reset }) => (
    <div role="alert" className="mx-auto flex max-w-prose flex-col items-start gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Не получилось загрузить страницу</h1>
      <p>Скорее всего, пропала связь. Проверь интернет и попробуй ещё раз.</p>
      <Button variant="outline" onClick={() => router.invalidate().then(reset)}>
        Попробовать ещё раз
      </Button>
    </div>
  ),
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const root = document.getElementById('root')
if (!root) throw new Error('#root is missing in index.html')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
