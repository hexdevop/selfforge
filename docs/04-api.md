# API

Префикс `/api/v1`. Всё, кроме `auth/*` и справочника, требует access-токена.

## Соглашения

- Ответы только через Pydantic-схемы, ORM наружу не отдаётся.
- Ошибки в едином формате: `{"detail": {"code": "...", "message": "...", "fields": {...}}}`.
  `code` — машинный, `message` — на русском, для показа пользователю.
- Даты — ISO 8601 с таймзоной. Веса — числа в килограммах, сериализуются как строки для
  сохранения точности (`"17.50"`).
- Пагинация — из шаблона: `PageParams(page, size)`, ответ `Page[T]`.
- Все изменяющие эндпоинты, которые может вызвать клиент повторно, идемпотентны по
  `client_uuid`.

## Аутентификация

Из шаблона: `POST auth/register | login | refresh | logout`, `GET auth/me`.
Добавляется: подтверждение email, сброс пароля, rate limiting на `login` и `register`
через Redis.

## Справочник

```
GET  /exercises                  фильтры: pattern, equipment (`none` — без оборудования),
                                 difficulty_min, difficulty_max, location_id (с Этапа 2);
                                 весь список без пагинации — справочник маленький
GET  /exercises/{slug}
GET  /patterns
GET  /patterns/{code}/ladder     полная лестница сложности
GET  /equipment                  каталог возможного оборудования
GET  /skills
```

Справочник меняется редко — агрессивное кеширование в Redis и `ETag` на клиент.
Клиент подтягивает его один раз и держит в кеше TanStack Query надолго.

## Профиль и онбординг

```
GET   /profile
PATCH /profile
POST  /profile/assessment        ответы на поведенческие вопросы → pattern_levels
GET   /profile/pattern-levels
PATCH /profile/pattern-levels    ручная корректировка
POST  /profile/disclaimer        фиксация принятия медицинского дисклеймера
```

## Локации и инвентарь

```
GET    /locations
POST   /locations
PATCH  /locations/{id}
DELETE /locations/{id}
PUT    /locations/{id}/equipment   полная замена инвентаря локации
GET    /locations/{id}/weight-grid доступные веса и минимальный шаг
POST   /locations/{id}/plates      разбивка целевого веса на блины
```

## Программа

```
POST /programs/preview    сгенерировать без сохранения (для экрана «вот что получилось»)
POST /programs            создать и сделать активной
GET  /programs/active
GET  /programs/{id}
POST /programs/{id}/regenerate
POST /programs/{id}/abandon
GET  /programs/active/next-session   что тренируем сегодня
```

`preview` важен: человек должен увидеть программу и объяснение до того, как согласится.

## Тренировка

```
POST  /sessions                        старт (planned_session_id + readiness)
GET   /sessions/{id}
POST  /sessions/{id}/sets              батч подходов, идемпотентно по client_uuid
POST  /sessions/{id}/substitute        замена упражнения, с указанием причины
POST  /sessions/{id}/trim              пересборка под оставшееся время
POST  /sessions/{id}/finish
POST  /sessions/{id}/abort
GET   /sessions                        история, пагинация
```

**Про `POST /sessions/{id}/sets`.** Это главный эндпоинт по частоте вызовов. Клиент копит
подходы локально и отправляет пачкой каждые несколько секунд или по завершении упражнения.
Тело — массив подходов, каждый с `client_uuid`. Сервер возвращает список принятых uuid.
Повторная отправка того же uuid — не ошибка, а no-op. Ответ включает свежие личные рекорды,
если они были побиты.

## Прогресс

```
GET /progress/summary                  сводка: серия, объём за неделю, ближайшие рекорды
GET /progress/patterns/{code}          график по паттерну
GET /progress/exercises/{slug}
GET /progress/tonnage?period=week
GET /progress/records
GET /progress/balance                  дисбаланс сторон по односторонним упражнениям
GET /progress/skills
```

## Тело

```
GET  /body/metrics?from=&to=
POST /body/metrics
GET  /body/photos
POST /body/photos/upload-url    presigned URL, файл идёт в хранилище мимо бэкенда
```

## Погода

```
GET  /weather/forecast?location_id=    прогноз для уличной локации
POST /sessions/{id}/swap-location      перенос сессии в другую локацию
```

Бэкенд проксирует внешний погодный API и кеширует в Redis по округлённым координатам и
дате. Ключ внешнего API на клиент не попадает.

## Экспорт

```
GET /export/all        полный дамп данных пользователя в JSON
```

## Генерация типов для фронта

FastAPI отдаёт OpenAPI-схему на `/api/v1/openapi.json`. Фронтенд генерирует из неё
TypeScript-типы командой `pnpm gen:api`. Руками типы ответов API не пишутся. Если схема
изменилась — сначала перегенерировать, потом править код.
