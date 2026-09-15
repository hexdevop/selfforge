import type { ReactNode } from 'react'

export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="flex min-h-dvh flex-col items-center px-4 py-10 sm:justify-center">
      <div className="w-full max-w-sm">
        <p className="mb-8 text-xl font-bold tracking-tight">Self Forge</p>
        <h1 className="mb-6 text-2xl font-semibold">{title}</h1>
        {children}
      </div>
    </main>
  )
}
