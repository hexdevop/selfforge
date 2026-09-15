# Модель данных

PostgreSQL. Первичные ключи — UUID. У всех таблиц `created_at` / `updated_at`.
Гибкие вложенные структуры хранятся в JSONB — это причина, по которой тесты идут на
настоящем Postgres, а не на SQLite.

## Справочник (seed, общий для всех)

### `movement_patterns`
`code` (PK, см. `01-domain.md`), `title_ru`, `description_ru`, `is_bilateral_default`.

### `equipment_items`
Каталог возможного оборудования.
`code`, `title_ru`, `category` (weights / bars / bands / bench / support / bodyweight),
`supports_quantity` (можно ли иметь одну штуку или пару), `supports_weight_list`
(нужен ли список весов, как у гирь), `is_outdoor`.

### `exercises`
`slug` (уникальный, стабильный — по нему идёт идемпотентный seed),
`title_ru`, `pattern_code` (FK), `difficulty_level` (int, позиция на единой шкале
паттерна; варианты на другом оборудовании стоят на уровне своей ступени),
`is_unilateral`, `requires_pair`, `is_quiet` (подходит для бесшумного режима),
`needs_floor_space` (нужно место за пределами коврика: выпады в движении, переноски),
`needs_ceiling_height` (жим над головой стоя), `lies_on_floor` (лёжа на полу — отсекается
покрытием площадки),
`required_equipment` (JSONB: «И» из групп «ИЛИ» — `[["pullup_bar", "rings"], ["backpack"]]`;
`[]` — только вес тела),
`primary_muscles` / `secondary_muscles` (массивы),
`technique_ru`, `common_mistakes_ru` (массив),
`media` (JSONB: ключи в объектном хранилище для видео, превью, SVG-схемы),
`prev_slug` / `next_slug` (ссылки по лестнице),
`progression_criteria` (JSONB: что нужно выполнить для перехода на следующую ступень —
`{"sets": 3, "reps": 12}` или `{"sets": 3, "hold_seconds": 30}` для статики и переносок),
`contraindicated_for` (массив тегов здоровья).

### `skills`
`slug`, `title_ru`, `description_ru`, `prerequisites` (JSONB), `lead_up_exercise_slugs`.

## Пользователь

### `users`
Из шаблона: email, username, хеш пароля, активность, верификация.

### `profiles`
`user_id` (FK, 1:1, он же PK), `sex`, `birth_year` (только год — нужен для возрастного
флага), `height_cm`, `goal_primary`, `goal_secondary`,
`days_per_week`, `session_minutes`, `guidance_level` (verbose / normal / quiet),
`health_flags` (массив тегов), `needs_medical_clearance` (итог стартового фильтра: сердце,
беременность, свежая травма или возраст 60+; сами ответы не хранятся),
`medical_disclaimer_accepted_at`, `units` (metric / imperial), `timezone`,
`onboarding_completed_at`.

### `pattern_levels`
Уровень пользователя по каждому паттерну — ключевая таблица.
`user_id`, `pattern_code`, `current_exercise_slug`, `estimated_level` (int),
`assessment_source` (onboarding / performance / manual), `updated_at`.
`current_exercise_slug` — ступень главной линии лестницы; конкретное упражнение под локацию
подбирает движок.
Уникальность по паре (user_id, pattern_code).

### `body_metrics`
`user_id`, `measured_at`, `weight_kg`, `waist_cm`, `chest_cm`, `hip_cm`, `arm_cm`,
`thigh_cm`, `note`. Вес показывается скользящим средним за 7 дней, сырые значения
пользователю как основной график не подаются.

### `progress_photos`
`user_id`, `taken_at`, `storage_key`, `angle` (front / side / back).
Приватны по умолчанию, загрузка через presigned URL мимо бэкенда.

## Локации и инвентарь

### `locations`
`user_id`, `kind` (home / outdoor_gym / outdoor_bare / travel), `title`,
`is_default`, `travel_minutes`,
`constraints` (JSONB: `quiet_mode`, `low_ceiling`, `limited_space`, `surface`),
`geo_lat` / `geo_lon` (только для уличных, нужно для погоды; опционально).

### `location_equipment`
`location_id`, `equipment_code`, `quantity` (1 или 2 — критично для одиночных снарядов),
`details` (JSONB).

Примеры `details`:
```json
{ "type": "adjustable", "bar_kg": 2.0,
  "plates": [{"kg": 1.25, "count": 4}, {"kg": 2.5, "count": 4}, {"kg": 5, "count": 2}] }

{ "type": "fixed", "weights_kg": [8, 12, 16] }        // по записи на каждый снаряд:
                                                     // две гири по 16 — [16, 16]

{ "resistances": ["light", "medium", "heavy"] }
```

Вычисляемая сетка доступных весов не хранится — считается движком на лету из `details`.

## Программа

### `programs`
`user_id`, `goal_primary`, `structure` (fullbody / upper_lower / ppl / skill),
`weeks_total`, `started_at`, `status` (active / completed / abandoned),
`generation_input` (JSONB — снимок профиля и инвентаря на момент генерации),
`rationale_ru` (текстовое объяснение «почему такая структура», показывается пользователю).

Снимок входных данных обязателен: он позволяет понять, почему программа выглядит так,
и корректно пересобрать её при изменении инвентаря.

### `program_weeks`
`program_id`, `index`, `kind` (accumulation / deload), `volume_multiplier`.

### `planned_sessions`
`program_week_id`, `day_index`, `location_id`, `title_ru`,
`focus` (массив паттернов), `estimated_minutes`,
`blocks` (JSONB — структура тренировки: разминка, основные блоки, финишер, заминка;
внутри блока список упражнений со схемой подходов, диапазоном повторов, отдыхом, темпом).

## Выполнение

### `workout_sessions`
`user_id`, `planned_session_id` (nullable — бывает внеплановая),
`location_id`, `started_at`, `finished_at`, `status` (in_progress / completed / aborted),
`readiness` (JSONB: sleep, stress, soreness — три тапа перед стартом),
`total_tonnage_kg`, `note`,
`substitutions` (JSONB: что и на что заменили, с причиной — занят турник, дождь, боль).

### `set_logs`
Главная таблица истории. Растёт быстрее всех, индексируется по (user_id, performed_at)
и по (user_id, exercise_slug).

`session_id`, `exercise_slug`, `set_index`, `side` (both / left / right),
`weight_kg` (nullable — вес тела), `added_weight_kg` (рюкзак, жилет),
`band` (nullable), `reps`, `tempo`, `rir` (nullable),
`effort_label` (nullable — словесная оценка для новичков),
`is_warmup`, `performed_at`, `client_uuid` (для идемпотентной отправки пачкой).

`client_uuid` обязателен: клиент копит подходы и шлёт их батчем с ретраями, сервер должен
уметь принять один и тот же подход дважды без дублей.

### `personal_records`
`user_id`, `exercise_slug`, `pattern_code`, `kind` (max_weight / max_reps / est_1rm /
max_volume), `value`, `achieved_at`, `set_log_id`.

### `skill_progress`
`user_id`, `skill_slug`, `status` (locked / in_progress / achieved),
`current_lead_up_slug`, `achieved_at`.

## Прочее

### `sync_batches` (опционально)
Журнал принятых батчей для диагностики проблем с отправкой.

### `weather_cache`
Кеш прогноза в Redis, не в Postgres. Ключ — округлённые координаты + дата.

## Индексы, на которые стоит обратить внимание

- `set_logs (user_id, performed_at DESC)` — лента и графики
- `set_logs (user_id, exercise_slug, performed_at DESC)` — предзаполнение прошлого подхода
- `set_logs (client_uuid)` unique — идемпотентность
- `exercises (pattern_code, difficulty_level)` — лестницы
- GIN по `exercises.required_equipment` — фильтр по инвентарю
