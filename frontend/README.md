# Self Forge — фронтенд

SPA на React 19 + TypeScript (strict). Общий обзор проекта — [корневой README](../README.md),
спецификация фронта — [docs/05-frontend.md](../docs/05-frontend.md).

## Оглавление

- [Стек](#стек)
- [Быстрый старт](#быстрый-старт)
- [Команды](#команды)
- [Структура](#структура)
- [Типы API](#типы-api)
- [Авторизация](#авторизация)
- [Экран тренировки и буфер подходов](#экран-тренировки-и-буфер-подходов)
- [PWA](#pwa)
- [Прод-сборка](#прод-сборка)

## Стек

Vite, TanStack Router и Query, Zustand, Tailwind CSS v4, shadcn/ui, React Hook Form + Zod,
Recharts, lucide-react, vite-plugin-pwa, openapi-fetch + openapi-typescript, Biome, Vitest +
Testing Library.

## Быстрый старт

Нужны Node.js 24 и запущенный бэкенд (см. [backend/README.md](../backend/README.md)).

```bash
corepack pnpm install
corepack pnpm dev          # http://localhost:5173, /api проксируется на http://localhost:8000
```

pnpm нужной версии берётся из `packageManager` в `package.json` через corepack.

## Команды

| Команда | Что делает |
|---|---|
| `corepack pnpm dev` | dev-сервер |
| `corepack pnpm build` | `tsc -b` + прод-сборка в `dist/` с service worker |
| `corepack pnpm preview` | посмотреть прод-сборку локально |
| `corepack pnpm lint` | Biome: проверка |
| `corepack pnpm format` | Biome: исправление и форматирование |
| `corepack pnpm typecheck` | `tsc -b` |
| `corepack pnpm test` | Vitest |
| `corepack pnpm gen:api` | типы из OpenAPI запущенного бэкенда → `src/api/schema.d.ts` |

## Структура

```
src/
├── api/          клиент, сгенерированные типы, запросы по разделам (sessions, progress, …)
├── routes/       экраны — файловая структура TanStack Router; _authed/ — после входа
├── features/     app, auth, catalog, onboarding, inventory, program, workout, progress, weather
├── components/   ui/ (shadcn) и общие компоненты продукта
└── lib/          форматирование весов, склонения, утилиты
```

`src/api/schema.d.ts` и `src/routeTree.gen.ts` генерируются и коммитятся — руками не
правятся. Дерево маршрутов обновляет плагин роутера при `dev` и `build`.

## Типы API

Типы ответов руками не пишутся. Изменилась схема на бэкенде → сначала `gen:api`, потом код.
Без запущенного бэкенда — тем же способом, что в CI:

```bash
(cd ../backend && SECRET_KEY=ci-only uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi()))") > openapi.json
corepack pnpm exec openapi-typescript openapi.json --default-non-nullable false -o src/api/schema.d.ts
rm openapi.json
```

## Авторизация

Access-токен живёт только в памяти (`src/api/client.ts`), refresh — в httpOnly-cookie. На
401 клиент один раз обновляет токен (одним запросом на все параллельные 401) и повторяет
исходный запрос.

## Экран тренировки и буфер подходов

`features/workout/`: подход сразу рисуется и кладётся в очередь (Zustand), очередь уходит на
сервер пачками с ретраями и сохраняется в `localStorage`, чтобы пережить выгрузку вкладки.
Таймер отдыха считает от метки времени, экран не гаснет (Wake Lock), конец отдыха — звук
через Web Audio. Подробности и причины решений — в
[docs/05-frontend.md](../docs/05-frontend.md#экран-тренировки).

## PWA

Манифест и service worker генерирует `vite-plugin-pwa` (`vite.config.ts`); иконки — в
`public/`. Кешируется только оболочка приложения. Новая версия ставится по тапу
«Обновить», а не перезагружает страницу сама. В dev-режиме service worker не работает — PWA
проверяется на `build` + `preview`.

## Прод-сборка

[`Dockerfile`](Dockerfile) собирает `dist/` и отдаёт его nginx из [`nginx.conf`](nginx.conf):
хешированные бандлы кешируются навсегда, `sw.js` и манифест — без кеша, неизвестные пути
отдают приложение. TLS, `/api` и фото — на хостовом nginx, см.
[docs/07-deploy.md](../docs/07-deploy.md).
