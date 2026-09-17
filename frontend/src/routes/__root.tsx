import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Link, Outlet } from '@tanstack/react-router'
import { UpdatePrompt } from '@/features/app/update-prompt'
import { AuthShell } from '@/features/auth/auth-shell'

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: () => (
    <>
      <Outlet />
      <UpdatePrompt />
    </>
  ),
  notFoundComponent: () => (
    <AuthShell title="Такой страницы нет">
      <p className="mb-6 text-muted-foreground">Возможно, ссылка устарела или в ней опечатка.</p>
      <Link to="/" className="font-medium underline underline-offset-4">
        На главную
      </Link>
    </AuthShell>
  ),
})
