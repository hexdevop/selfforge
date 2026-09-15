# Self Forge — фронтенд

React 19 + TypeScript (strict), Vite, TanStack Router/Query, Tailwind CSS v4, shadcn/ui,
React Hook Form + Zod, Biome, Vitest. Спецификация — `../docs/05-frontend.md`.

```bash
corepack pnpm install
corepack pnpm dev        # http://localhost:5173, /api проксируется на бэкенд :8000
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
corepack pnpm gen:api    # типы из OpenAPI запущенного бэкенда → src/api/schema.d.ts
```

`src/api/schema.d.ts` и `src/routeTree.gen.ts` генерируются и коммитятся — руками не
правятся. Сменилась схема на бэкенде → сначала `gen:api`, потом код.

Авторизация: access-токен живёт только в памяти (`src/api/client.ts`), refresh — в
httpOnly-cookie. На 401 клиент один раз обновляет токен и повторяет запрос.
