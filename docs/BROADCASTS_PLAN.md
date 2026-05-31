# План: персонализация рассылок в Сфере Таро

Документ описывает, что сделано в коммите `d12c07ae` проекта **psy_max** («personofication»), и как адаптировать это для **max_bot** без написания кода на данном этапе.

---

## 1. Что изменил коммит в psy_max

Коммит превращает «один шаблон всем в одну минуту» в систему из двух автоматических потоков с **сегментацией** и **персональными слотами отправки**.

### 1.1. Новые возможности

| Компонент | Суть |
|-----------|------|
| `main/broadcast_schedule.py` | Окно 10:00–20:00 MSK, тик 30 мин, слот на пользователя по `last_active_at` или `user_id % 600` |
| Welcome-активация | Ежедневно: пользователи ≥24ч после регистрации, **ни разу не писали в чат** |
| Вт/Пт рассылка | Сегментированные сценарии вместо одного paywall-шаблона |
| Поля БД | `activation_sent_at`, `last_sub_reminder_broadcast_at` |
| `database.py` | SQL-сегментация + `mark_activation_sent` / `mark_sub_reminder_broadcast_sent` |
| `send_message.py` | Tick-функции с счётчиками `skipped_time`, `by_segment` и т.д. |
| `bot.py` | Cron `:00/:30` 10–20 вместо одного фиксированного времени |
| `docs/BROADCASTS.md` | Живая документация по всем рассылкам |

### 1.2. Сегменты psy_max (Вт/Пт)

| Сегмент | Условие | Действие |
|---------|---------|----------|
| `skip_pending` | Открытая оплata (pending/canceled без succeeded) | Пропуск |
| `skip_no_chat` | Нет сессий в `max_sessions` | Пропуск (активация отдельно) |
| `active_subscriber` | Подписка / unlimited / платные сообщения | Мягкий nudge, **без** paywall |
| `expired_sub` | Была подписка/оплата, сейчас нет доступа | Напоминание + paywall |
| `paywall` | Исчерпаны 6 бесплатных сообщений, не платил | Paywall |
| `free_return` | Есть бесплатные сообщения, уже общался | Мягкий nudge, **без** paywall |

### 1.3. Ключевая проблема, которую решает коммит

**До:** рассылка бьёт одним paywall-сообщением по всей базе в фиксированное время → спам платникам, холодным пользователям и тем, у кого ещё есть бесплатный лимит.

**После:** каждый получает релевантный сценарий в «своё» время внутри дневного окна.

---

## 2. Текущее состояние max_bot

### 2.1. Автоматические рассылки сейчас

| Рассылка | Расписание | Файл | Проблема |
|----------|------------|------|----------|
| Карта дня | Ежедневно 09:25 MSK | `handlers/daily_card.py` | OK, не трогаем |
| `--no-divinations` | **Пн, Чт 16:30 MSK** | `send_message.py` → `send_no_divinations_broadcast()` | **Всем** незаблокированным, один paywall-шаблон |
| Напоминания об оплате | Каждые 2 мин (10м/1ч/3ч) | `main/payment_reminders.py` | Уже как в psy_max |
| Сверка pending | Каждые 10 мин | `bot.py` | OK |

### 2.2. Что уже есть в инфраструктуре

- `last_active_at` в `max_users` — есть
- `max_divinations` — аналог `max_sessions` (факт использования бота)
- `max_user_balances`: `free_divinations_remaining` (старт 3), `paid_divinations_remaining`, `unlimited_until`, `total_divinations_used`
- `max_subscriptions`, `max_payments` — та же модель монетизации
- `send_no_divinations_reminder()` — готовый paywall-сценарий с конверсиями
- Ручные CLI-флаги в `send_message.py` (промо, таролог, feedback и т.д.)

### 2.3. Чего нет (нужно добавить по аналогии)

- `main/broadcast_schedule.py`
- Поля `activation_sent_at`, `last_*_broadcast_at`
- SQL-сегментация пользователей
- Шаблоны: activation, gentle nudge, free return, expired sub
- Tick-логика вместо «все сразу в 16:30»

---

## 3. Маппинг psy_max → max_bot

| psy_max | max_bot | Примечание |
|---------|---------|------------|
| `max_sessions` | `max_divinations` | «Никогда не пользовался» = нет записей в divinations |
| `FREE_MESSAGES_LIMIT = 6` | `free_divinations_remaining = 0` + `total_divinations_used > 0` | Стартовый лимит 3 бесплатных расклада |
| Вт/Пт subscription reminder | **Пн/Чт** divination reminder | Сохраняем текущие дни бизнес-логики |
| `last_sub_reminder_broadcast_at` | `last_div_reminder_broadcast_at` | Переименовать для ясности домена |
| Совет дня 09:30 | Карта дня 09:25 | Не менять |
| `daily_tip_subscribed` фильтр | `daily_card_subscribed` | В текущей рассылке `include_unsubscribed_daily_card=True` — **оставить** (рассылка шире карты дня) |

---

## 4. Целевая архитектура max_bot

```
APScheduler (Europe/Moscow)
│
├── 09:25 daily              → daily_card (без изменений)
├── :00/:30 10–20 daily      → activation_broadcast (NEW)
├── :00/:30 10–20 Mon/Thu    → divination_reminder_broadcast (REFACTOR no_divinations)
├── every 10 min             → reconcile_pending_payments
└── every 2 min              → payment_reminders (optional)
```

### 4.1. Персональный слот (копируется из psy_max)

Модуль `main/broadcast_schedule.py` — **переносить почти без изменений**:

- окно 10:00–20:00 MSK;
- тик 30 мин;
- `compute_user_send_minute(user_id, last_active_at)`;
- `is_user_due_in_tick()`;
- `is_same_msk_day()` — защита от повторной отправки в тот же день.

---

## 5. Поток 1: Welcome-активация

### Цель

Вернуть пользователей, которые нажали `/start`, но **ни разу не сделали расклад**.

### Условия отбора (SQL)

- `is_blocked = FALSE`
- `activation_sent_at IS NULL`
- `created_at <= NOW() - INTERVAL '24 hours'`
- `NOT EXISTS (SELECT 1 FROM max_divinations WHERE user_id = u.user_id)`
- нет открытой оплаты (та же логика `has_open_payment`, что в psy_max / payment_reminders)

### Отправка

- Один раз, в персональный слот 10:00–20:00 MSK
- После успеха: `activation_sent_at = NOW()`
- **Без paywall** — только приглашение сделать первый расклад

### Черновик текста (адаптировать под тон Сферы Таро)

> Привет 🔮  
>  
> Ты заходил(а), но мы ещё не успели погадать вместе.  
>  
> Задай свой первый вопрос — карты уже ждут. Можно начать с чего-то простого: «Что мне важно знать сегодня?»  
>  
> Нажми /start или выбери расклад в меню ✨

### Anti-spam backfill при деплое (обязательно)

Без этого шага при первом включении activation-рассылки **вся «холодная» база** (кто когда-то нажал `/start`, но ни разу не гадал) получит welcome-сообщение — возможен массовый спам.

**Решение:** в миграции сразу после добавления колонки проставить `activation_sent_at = NOW()` всем, кто уже «простыл» — старше 7 дней и без единого гадания. Такие пользователи считаются уже «обработанными», новая рассылка пойдёт только свежим регистрациям (≥24ч, 0 divinations).

Адаптация из psy_max (`max_sessions` → `max_divinations`):

```sql
-- Не слать активацию «задним числом» пользователям старше 7 дней без гаданий
UPDATE max_users u
SET activation_sent_at = NOW()
WHERE activation_sent_at IS NULL
  AND created_at < NOW() - INTERVAL '7 days'
  AND NOT EXISTS (
      SELECT 1 FROM max_divinations d WHERE d.user_id = u.user_id
  );
```

**Проверка после миграции** (опционально):

```sql
SELECT COUNT(*) AS backfilled_cold_users
FROM max_users
WHERE activation_sent_at IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM max_divinations d WHERE d.user_id = max_users.user_id);
```

Этот же `UPDATE` — в `migrations/20260531_broadcasts.sql` и дублируется в `init_db.sql` (для новых инсталляций harmlessly no-op после первого прогона).

---

## 6. Поток 2: Пн/Чт сегментированная рассылка

Заменяет текущий `send_no_divinations_broadcast()` (все → paywall в 16:30).

### Расписание

- Дни: **понедельник, четверг** (как сейчас)
- Окно: 10:00–20:00 MSK, тик 30 мин
- Не чаще 1 раза в день: `last_div_reminder_broadcast_at`

### Сегменты (адаптация)

| Сегмент | Условие (max_bot) | Функция отправки | Paywall |
|---------|-------------------|------------------|---------|
| `skip_pending` | Открытая оплata | — | — |
| `skip_no_divinations` | Нет записей в `max_divinations` | — | — |
| `active_subscriber` | `unlimited_until > NOW()` OR `paid_divinations_remaining > 0` OR активная подписка | `send_gentle_nudge` | Нет |
| `expired_sub` | Был unlimited/подписка/succeeded-платёж, сейчас нет доступа | `send_expired_sub_reminder` | Да |
| `paywall` | `free_divinations_remaining = 0`, нет paid/unlimited, **никогда не платил** (или исчерпал только бесплатные) | `send_no_divinations_reminder` *(существует)* | Да |
| `free_return` | `free_divinations_remaining > 0`, есть хотя бы 1 гадание | `send_free_return_nudge` | Нет |

### Порядок CASE в SQL (важен!)

1. `skip_pending`
2. `skip_no_divinations`
3. `active_subscriber`
4. `expired_sub`
5. `paywall`
6. `free_return` (ELSE)

### Новые шаблоны сообщений (нужно написать)

| Функция | Назначение |
|---------|------------|
| `send_activation_nudge` | Welcome-активация |
| `send_gentle_nudge` | Платники / безлимит — «карты ждут», без меню оплаты |
| `send_free_return_nudge` | Есть бесплатные расклады — мягкое напоминание |
| `send_expired_sub_reminder` | Подписка/пакет закончились — эмпатия + `make_payment_kb()` |
| `send_no_divinations_reminder` | **Уже есть** — paywall для исчерпавших бесплатные |

### Конверсии / Метрика

Для paywall-сценариев (`expired_sub`, `paywall`) — сохранить текущий паттерн:

- `save_paywall_conversion(..., metadata={'segment': ..., 'sent_via': 'broadcast'})`
- `send_conversion_event(user_id, 'paywall')`

Для nudge без paywall — **не** писать paywall-конверсию.

---

## 7. Изменения по файлам

### 7.1. База данных

**Новая миграция** `migrations/20260531_broadcasts.sql`:

```sql
-- Миграция: welcome-активация + отметка Пн/Чт рассылки
-- activation_sent_at                 — когда отправлена welcome-активация (1 раз после регистрации)
-- last_div_reminder_broadcast_at     — когда отправлена последняя Пн/Чт рассылка

ALTER TABLE max_users ADD COLUMN IF NOT EXISTS activation_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS last_div_reminder_broadcast_at TIMESTAMP NULL;

CREATE INDEX IF NOT EXISTS idx_max_users_activation_sent_at
    ON max_users(activation_sent_at)
    WHERE activation_sent_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_max_users_last_div_reminder_broadcast_at
    ON max_users(last_div_reminder_broadcast_at);

-- ⚠️ ОБЯЗАТЕЛЬНО: anti-spam backfill (см. §5)
-- Не слать активацию «задним числом» пользователям старше 7 дней без гаданий
UPDATE max_users u
SET activation_sent_at = NOW()
WHERE activation_sent_at IS NULL
  AND created_at < NOW() - INTERVAL '7 days'
  AND NOT EXISTS (
      SELECT 1 FROM max_divinations d WHERE d.user_id = u.user_id
  );
```

**`init_db.sql`:** добавить колонки + тот же `UPDATE` в конец ALTER-блока (идемпотентно).

> **Примечание:** backfill для `last_div_reminder_broadcast_at` не нужен — у старой рассылки не было поля «уже отправлено сегодня»; первый Пн/Чт после деплоя отработает сегментация + персональные слоты без массового дубля в одну минуту.

### 7.2. `main/broadcast_schedule.py`

- Создать файл (копия из psy_max, без доменной логики).

### 7.3. `main/database.py`

Добавить:

- константы сегментов (`DIV_REMINDER_SEGMENT_*`, `DIV_REMINDER_SKIP_SEGMENTS`);
- `get_users_for_div_reminder_broadcast()` — адаптированный SQL (divinations вместо sessions, balances вместо messages);
- `get_users_for_activation_broadcast()` — divinations вместо sessions;
- `mark_activation_sent(user_id)`;
- `mark_div_reminder_broadcast_sent(user_id)`.

**Открытая оплата:** переиспользовать тот же подзапрос, что в `get_payments_due_for_reminder` / psy_max (pending/canceled без «связанного» succeeded).

### 7.4. `send_message.py`

- Импорты из `broadcast_schedule` и новых DB-функций;
- `_init_broadcast_results()` — общий счётчик;
- `send_activation_broadcast()` — tick-цикл;
- `send_divination_reminder_broadcast()` — замена `send_no_divinations_broadcast()`;
- `DIV_REMINDER_SENDERS` — маппинг segment → sender;
- Новые функции шаблонов (см. §6);
- **CLI:** `--no-divinations` для ручной отправки оставить как есть (без сегментации/слотов);
- опционально: флаги `--gentle-nudge`, `--free-return`, `--expired-sub` для точечных ручных отправок (как в psy_max).

### 7.5. `bot.py`

Заменить блок:

```python
# Было: Mon/Thu 16:30 → send_no_divinations_broadcast()
# Станет:
BROADCAST_CRON_HOURS = '10-20'
BROADCAST_CRON_MINUTES = '0,30'

# activation_broadcast_job — daily :00/:30 10–20
# divination_reminder_broadcast_job — Mon/Thu :00/:30 10–20
```

Обновить log-сообщения при старте планировщика.

### 7.6. `docs/BROADCASTS.md`

После реализации — живая документация по образцу psy_max (этот файл остаётся **планом**, финальный doc — отдельно).

### 7.7. Вне scope первой итерации (фаза 2+)

- `internal_reports.sh` — конверсия по сегментам
- `{first_name}` в текстах
- A/B варианты Пн vs Чт
- frequency cap 7–10 дней между nudge-рассылками

---

## 8. Порядок реализации (чеклист)

### Этап 1 — инфраструктура

- [ ] Миграция БД + обновление `init_db.sql` (**включая anti-spam UPDATE из §5**)
- [ ] `main/broadcast_schedule.py`
- [ ] DB-функции сегментации и mark_* 

### Этап 2 — сообщения

- [ ] Тексты: activation, gentle, free_return, expired (expired можно взять за основу из `send_no_divinations_reminder` + эмпатичный intro)
- [ ] Tick-функции в `send_message.py`
- [ ] Маппинг `DIV_REMINDER_SENDERS`

### Этап 3 — планировщик

- [ ] Обновить `bot.py` (activation + refactor Mon/Thu)
- [ ] Удалить/заменить старый `NO_DIV_BROADCAST_HOUR/MINUTE`

### Этап 4 — проверка

- [ ] Прогнать миграцию на staging
- [ ] Ручной тест: `python -c "..."` или временный debug-log tick results
- [ ] Проверить пересечение с payment_reminders (skip_pending)
- [ ] Проверить, что activation не дублируется с divination reminder (skip_no_divinations)

### Этап 5 — документация и деплой

- [ ] `docs/BROADCASTS.md` (финальная версия)
- [ ] Деплой: миграция → restart бота

---

## 9. Тест-план

### 9.1. Юнит-уровень (broadcast_schedule)

| Кейс | Ожидание |
|------|----------|
| `last_active_at` = 14:15, now = 14:20 | `is_user_due_in_tick` = True (тик 14:00–14:30) |
| `last_active_at` = NULL, user_id = 12345 | Стабильный слот, повторяется между неделями |
| `last_active_at` = 03:00 | Маппинг внутрь окна 10–20 |
| `last_div_reminder_broadcast_at` сегодня MSK | `skipped_already_sent` |

### 9.2. Сегментация (SQL / staging data)

Создать тестовых пользователей:

| Профиль | Ожидаемый сегмент |
|---------|-------------------|
| /start, 0 divinations, 25ч | activation (не div reminder) |
| unlimited активен | `active_subscriber` → gentle |
| 2 free left, 1 divination | `free_return` |
| 0 free, 0 paid, never paid, 3 used | `paywall` |
| succeeded раньше, сейчас 0 balance | `expired_sub` |
| pending payment | `skip_pending` |
| blocked | не попадает в выборку |

### 9.3. Интеграция

- Логи tick: `skipped_time` доминирует вне пиков — норма
- `by_segment` в Пн/Чт отражает реальное распределение базы
- Платник с unlimited **не** получает paywall в Mon/Thu tick

---

## 10. Риски и решения

| Риск | Митигация |
|------|-----------|
| Спам при первом деплое activation | **Обязательный** `UPDATE activation_sent_at = NOW()` для пользователей >7 дней без `max_divinations` (§5) |
| Дубль с payment_reminders | `skip_pending` в div reminder |
| Дубль activation + div reminder | `skip_no_divinations` в div reminder |
| Нагрузка на API Max (много тиков) | Задержка 0.1с между отправками; большинство пользователей `skipped_time` |
| Регрессия ручной `--no-divinations` | Оставить прямой вызов `send_no_divinations_reminder` без tick-логики |

---

## 11. Оценка объёма

По аналогии с psy_max (~765 строк):

| Файл | ~строк |
|------|--------|
| `broadcast_schedule.py` | 66 (новый) |
| `database.py` | +220 |
| `send_message.py` | +150 / −30 |
| `bot.py` | +25 |
| миграция + init_db | +30 |
| `docs/BROADCASTS.md` | +200 |

**Итого:** ~600–700 строк, 1 PR, без изменений handlers/divination flow.

---

## 12. Деплой (когда код будет готов)

```bash
psql -U tg_bot_user -d tg_bot_db -f migrations/20260531_broadcasts.sql
# restart max_bot service
```

Проверить в `bot.log`:

```
APScheduler: activation broadcast daily 10-20 MSK (every 0,30 min)
APScheduler: divination-reminder broadcast Mon/Thu 10-20 MSK (every 0,30 min)
```

---

## 13. Отличия от psy_max (осознанные)

1. **Дни рассылки:** Пн/Чт вместо Вт/Пт — сохраняем текущую продуктовую логику таро-бота.
2. **Имя поля:** `last_div_reminder_broadcast_at` вместо `last_sub_reminder_broadcast_at`.
3. **Критерий «новичок»:** нет divinations, а не нет chat sessions.
4. **Paywall-сегмент:** переиспользуем существующий `send_no_divinations_reminder` с конверсиями.
5. **Карта дня:** отдельный поток, не затрагивается.
6. **Нет LLM-контента** в рассылках (в отличие от совета дня в psy) — только шаблоны.

---

*Документ подготовлен как план реализации. Код не включён — следующий шаг: реализация по чеклисту §8.*
