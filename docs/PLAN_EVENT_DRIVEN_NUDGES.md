# Переход к событийной модели рассылок: от Пн/Чт слотов к персональным триггерам

> **Источник:** рефакторинг в psy_max (коммиты `758a4b0` + `c88d97f`).
> Адаптация для проекта **max_bot** (бот «Сфера Таро»).

---

## 1. Что изменилось в psy_max

### 1.1. Суть рефакторинга

**Было:** сегментированная рассылка по фиксированным дням (Вт/Пт) — все eligible-пользователи получают сообщение в один из двух дней недели.

**Стало:** событийная (event-driven) модель — каждый пользователь получает nudge, когда наступает его персональный триггер (N дней/часов молчания, момент истечения подписки и т.д.).

### 1.2. Ключевые изменения

| Что | Было | Стало |
|-----|------|-------|
| Когда шлём | Вт и Пт (фикс. дни) | Когда наступает событие (ежедневная/2-минутная проверка) |
| Платникам | 1 gentle nudge 2 раза в неделю | Прогрессивная серия: 1d → 3d → 5d → 10d молчания |
| Бесплатным | Один nudge/paywall в Вт или Пт | 4 подкатегории (C1–C4) с таймерами от якорного события |
| Expired sub | catch-up в Вт/Пт рассылке | Отдельный поток day0–day3 от момента истечения |
| Слот | Только `last_active_at` | `anchor_at` — можно привязать к любому событию |
| Защита от спама | `is_same_msk_day` | Catch-up guard: макс. 1 этап на категорию за тик |
| Welcome-активация | Отдельный ежедневный job | Заменена категорией C2 (онбординг пройден, не написал) |
| Free-return nudge | Одноразовый, 3–6ч молчания | Заменён категорией C3 (прогрессивные этапы) |

### 1.3. Исправленные баги

1. **day1 expired reminder пропускался** — слот привязан к `last_active_at`, а подписка истекала позже → день навсегда пропускался. Фикс: слот привязан к `unlimited_until`.
2. **Рассылка Вт/Пт дублировала expired_sub_reminders** — удалена, каждый триггер работает автономно.
3. **Платники получали один и тот же gentle nudge** 2×/неделю без учёта длительности молчания.

---

## 2. Текущее состояние max_bot

### 2.1. Что есть сейчас

| Рассылка | Расписание | Триггер | Проблемы |
|----------|------------|---------|----------|
| Карта дня | 09:25 ежедневно | Подписка на карту дня | OK, не трогаем |
| Welcome-активация | :00/:30 10–20 ежедневно | ≥24ч, 0 divinations | Одноразовый, нет follow-up |
| Пн/Чт сегментированная | :00/:30 10–20 Пн/Чт | Сегмент пользователя | Грубая — 1 nudge 2×/неделю всем одинаково |
| Payment reminders | Каждые 2 мин | 10м/1ч/3ч | OK |
| Reconcile payments | Каждые 10 мин | — | OK |

### 2.2. Проблемы текущей модели (аналогичные psy_max)

1. **Платник с unlimited получает один и тот же gentle nudge** каждый Пн и Чт — может раздражать
2. **Нет прогрессии** — 1 день молчания и 10 дней молчания обрабатываются одинаково
3. **Нет учёта контекста бесплатных** — пользователь бросил на 1-м расклекаде и тот, кто упёрся в paywall, получают nudge с одинаковой частотой
4. **Welcome-активация одноразовая** — если проигнорировал, follow-up нет
5. **Expired sub** не выделен в отдельную серию — catch-up через Пн/Чт рассылку ненадёжен (тот же баг слотов)
6. **`last_active_at` обновляется на `/start`**, а не на реальной активности (гадании) — слоты нестабильны

---

## 3. Предлагаемая архитектура

### 3.1. Концепция

Заменить Пн/Чт рассылку + welcome-активацию на **3 автономных триггера** с прогрессивными этапами:

```
APScheduler (Europe/Moscow)
│
├── 09:25 daily              → daily_card (без изменений)
├── :00/:30 10–20 daily      → inactivity_nudges (платники — триггер B)
├── every 2 min              → free_user_nudges (бесплатные — триггер C)
├── :00/:30 10–20 daily      → expired_access_reminders (триггер A)
├── every 10 min             → reconcile_pending_payments (без изменений)
└── every 2 min              → payment_reminders (без изменений)
```

**Удаляется:**
- `activation_broadcast` (заменяется C1/C2)
- `divination_reminder_broadcast` Пн/Чт (заменяется триггерами A/B/C)

---

## 4. Триггер A — Доступ истёк (expired access)

**Заменяет:** сегмент `expired_sub` из Пн/Чт рассылки.

### Условие

Пользователь имел платный доступ (`unlimited_until` / `paid_divinations_remaining > 0`), сейчас всё исчерпано.

### Серия

| Этап | Время от истечения | Описание |
|------|-------------------|----------|
| day0 | День истечения | «Расклады закончились, но вопросы — нет» |
| day1 | +1 день | Follow-up |
| day2 | +2 дня | Второе напоминание |
| day3 | +3 дня | Последнее напоминание |

### Механика

- Расписание: ежедневно 10:00–20:00, тик 30 мин
- Слот привязан к `unlimited_until` (anchor_at), **не** к `last_active_at`
- Для day0: grace period — если слот прошёл, отправить в ближайший тик
- Стоп: если пользователь купил новый доступ (`unlimited_until > NOW()` или `paid > 0`)
- Каждый этап требует `previous_sent_at IS NOT NULL` (кроме day0)
- Paywall: да (кнопка оплаты)

### Тексты (черновики)

| Этап | Текст |
|------|-------|
| day0 | «Привет! 💫 Твои расклады закончились, но карты всё ещё помнят тебя. Если снова нужна ясность — я здесь ✨» |
| day1 | «Карты заметили, что ты давно не задавал(а) вопросов 🔮 Может, пора?» |
| day2 | «Иногда один расклад помогает увидеть то, что не замечаешь. Я рядом, когда будешь готов(а) 💫» |
| day3 | «Последнее: если захочешь вернуться — нажми кнопку ниже. Без спешки ✨» |

---

## 5. Триггер B — Платник давно не делал расклад

**Заменяет:** сегмент `active_subscriber` из Пн/Чт рассылки.

### Условие

- Активный доступ: `unlimited_until > NOW()` или `paid_divinations_remaining > 0`
- Есть хотя бы 1 гадание в `max_divinations`
- Нет открытого платежа (skip_pending)

### Серия (прогрессивная)

| Этап | Молчание | Тон |
|------|----------|-----|
| 1d | 1 день | Мягкое «карты здесь» |
| 3d | 3 дня | «Давно не раскладывали» |
| 5d | 5 дней | «Доступ активен, я на связи» |
| 10d | 10 дней | Последний nudge |

### Механика

- Расписание: ежедневно 10:00–20:00, тик 30 мин
- Слот по `last_active_at`
- Поля: `paid_inactivity_1d_sent_at`, `paid_inactivity_3d_sent_at`, `paid_inactivity_5d_sent_at`, `paid_inactivity_10d_sent_at`
- Сброс всех `*_sent_at` при новом гадании
- Catch-up guard: макс. 1 этап за тик на пользователя
- Paywall: нет

### Тексты (черновики)

| Этап | Текст |
|------|-------|
| 1d | «Привет 🔮 Просто напомню — карты здесь, если захочется новый расклад. Можно спросить о чём угодно ✨» |
| 3d | «Давно не раскладывали 🔮 Если что-то крутится в голове — можешь спросить у карт. Я рядом 💫» |
| 5d | «Привет! Доступ к раскладам активен — можешь вернуться когда удобно. Иногда один вопрос стоит целого разговора 🔮» |
| 10d | «Просто заглянула 🔮 Если захочешь снова спросить у карт — я здесь. Без спешки ✨» |

---

## 6. Триггер C — Бесплатные пользователи

**Заменяет:** welcome-активацию + сегменты `free_return` и `paywall` из Пн/Чт + free_return_nudge.

### Подкатегории

#### C1 — Зарегистрировался, не сделал ни одного расклада

**Якорь:** `created_at`

| Этап | Интервал | Описание |
|------|----------|----------|
| 1h | +1 час | «Карты ждут — задай первый вопрос» |
| 3h | +3 часа | «Можно начать с простого вопроса» |
| 24h | +24 часа | «Я рядом, когда будешь готов(а)» |

#### C2 — Сделал 1 расклад, остались бесплатные

**Якорь:** `last_active_at` (время последнего расклада)

| Этап | Интервал | Описание |
|------|----------|----------|
| 3h | +3 часа | «Мы не закончили — можешь продолжить» |
| 24h | +24 часа | «У тебя ещё есть бесплатные расклады» |
| 48h | +48 часов | Последнее напоминание |

#### C3 — Исчерпал бесплатные расклады (paywall)

**Якорь:** `paywall_reached_at` (момент упора в лимит)

| Этап | Интервал | Описание |
|------|----------|----------|
| 1h | +1 час | Напоминание об оплате |
| 3h | +3 часа | Второе напоминание |
| 24h | +24 часа | Третье напоминание |
| 48h | +48 часов | Последнее |

#### C4 — Сделал расклад, молчит давно (3+ дня), есть бесплатные

**Якорь:** `last_active_at`

| Этап | Интервал | Описание |
|------|----------|----------|
| 3d | +3 дня | «Карты заметили — давно не спрашивал(а)» |
| 7d | +7 дней | Последнее напоминание |

### Механика (общая для C)

- Расписание: каждые 2 мин (без привязки к окну 10–20, чтобы 1h/3h были точными)
- Catch-up guard: макс. 1 этап за тик на пользователя внутри категории
- Поля: `free_nudge_{category}_{stage}_sent_at`
- Сброс при новом гадании
- Paywall: да для C3, нет для C1/C2/C4
- C1 отправляет кнопку «Выбрать расклад» (меню)
- C3 отправляет `make_payment_kb()`

### Тексты C1 (черновики)

| Этап | Текст |
|------|-------|
| 1h | «Привет 🔮 Ты заходил(а), но мы ещё не погадали вместе. Задай первый вопрос — карты уже ждут ✨» |
| 3h | «Можно начать с простого: «Что мне важно знать сегодня?» 🔮 Я рядом.» |
| 24h | «Если захочешь попробовать — просто нажми «Новый расклад» в меню. Я здесь, когда будешь готов(а) 💫» |

### Тексты C2 (черновики)

| Этап | Текст |
|------|-------|
| 3h | «Мы не договорили 🔮 Хочешь задать ещё один вопрос картам? У тебя остались бесплатные расклады ✨» |
| 24h | «У тебя ещё есть бесплатные расклады — можешь использовать, когда будет удобно 💫» |
| 48h | «Просто напоминаю: бесплатные расклады ещё доступны. Загляни, если нужна ясность 🔮» |

### Тексты C3 (черновики)

| Этап | Текст |
|------|-------|
| 1h | «Бесплатные расклады закончились — но вопросы к картам никуда не делись 🔮 Выбери пакет и продолжай ✨» |
| 3h | «Если сейчас нужна ясность — доступ можно открыть за пару минут 💫» |
| 24h | «Карты ждут твоего вопроса 🔮 Нажми «Оплатить» и продолжай раскладывать ✨» |
| 48h | «Последнее: если захочешь вернуться — кнопка ниже. Без спешки 💫» |

### Тексты C4 (черновики)

| Этап | Текст |
|------|-------|
| 3d | «Привет 🔮 Давно не раскладывали. Если что-то крутится в голове — можешь спросить у карт ✨» |
| 7d | «Карты здесь, если понадобится ясность. Возвращайся, когда будет удобно 💫» |

---

## 7. Изменения по файлам

### 7.1. Что удалить

| Файл | Что убрать |
|------|------------|
| `send_message.py` | `send_activation_broadcast()`, `send_divination_reminder_broadcast()`, `_send_div_reminder_for_segment()`, `DIV_REMINDER_SENDERS`, `_init_broadcast_results()` |
| `bot.py` | Jobs `activation_broadcast` и `divination_reminder_broadcast` (Пн/Чт) |
| `main/database.py` | `get_users_for_div_reminder_broadcast()`, `get_users_for_activation_broadcast()`, `mark_activation_sent()`, `mark_div_reminder_broadcast_sent()`, сегментные константы `DIV_REMINDER_*` |

### 7.2. Что создать

| Файл | Содержание |
|------|------------|
| `main/inactivity_nudges.py` | Модуль с `process_inactivity_nudges()` — обработка триггеров B и C |
| `main/expired_access_reminders.py` | Модуль с `process_expired_access_reminders()` — триггер A (серия day0–day3) |

### 7.3. Что переработать

| Файл | Изменения |
|------|-----------|
| `main/broadcast_schedule.py` | Добавить параметр `anchor_at`, `is_in_broadcast_window()` |
| `send_message.py` | Новые функции: `send_paid_inactivity_nudge(user_id, stage)`, `send_free_user_nudge(user_id, category, stage)`, серия `send_expired_access_reminder(user_id, stage)` |
| `main/database.py` | Новые запросы: `get_users_due_for_paid_inactivity_nudge(stage)`, `get_users_due_for_free_nudge(category, stage)`, `get_users_due_for_expired_access_reminder(stage)`, соответствующие `mark_*_sent()` |
| `bot.py` | Новые jobs: `inactivity_nudges_job` (30 мин), `free_user_nudges_job` (2 мин), `expired_access_reminders_job` (30 мин) |
| `handlers/divination.py` | Сброс `*_inactivity_*_sent_at` при новом гадании |

### 7.4. Миграция БД

```sql
-- Триггер A: expired access reminders
ALTER TABLE max_user_balances ADD COLUMN IF NOT EXISTS expired_access_reminder_for_until TIMESTAMP NULL;
ALTER TABLE max_user_balances ADD COLUMN IF NOT EXISTS expired_access_day0_sent_at TIMESTAMP NULL;
ALTER TABLE max_user_balances ADD COLUMN IF NOT EXISTS expired_access_day1_sent_at TIMESTAMP NULL;
ALTER TABLE max_user_balances ADD COLUMN IF NOT EXISTS expired_access_day2_sent_at TIMESTAMP NULL;
ALTER TABLE max_user_balances ADD COLUMN IF NOT EXISTS expired_access_day3_sent_at TIMESTAMP NULL;

-- Триггер B: paid inactivity nudges
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS paid_inactivity_1d_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS paid_inactivity_3d_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS paid_inactivity_5d_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS paid_inactivity_10d_sent_at TIMESTAMP NULL;

-- Триггер C: free user nudges
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c1_1h_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c1_3h_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c1_24h_sent_at TIMESTAMP NULL;

ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c2_3h_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c2_24h_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c2_48h_sent_at TIMESTAMP NULL;

ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c3_1h_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c3_3h_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c3_24h_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c3_48h_sent_at TIMESTAMP NULL;

ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c4_3d_sent_at TIMESTAMP NULL;
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS free_nudge_c4_7d_sent_at TIMESTAMP NULL;

-- Якорь для C3
ALTER TABLE max_users ADD COLUMN IF NOT EXISTS paywall_reached_at TIMESTAMP NULL;

-- Удаление устаревших полей (после полного перехода)
-- ALTER TABLE max_users DROP COLUMN IF EXISTS last_div_reminder_broadcast_at;
-- ALTER TABLE max_users DROP COLUMN IF EXISTS activation_sent_at;
```

---

## 8. Расписание APScheduler (итоговое)

| Job | Расписание | Модуль | Описание |
|-----|------------|--------|----------|
| Карта дня | 09:25 ежедневно | `handlers/daily_card.py` | Без изменений |
| **Expired access reminders** | :00/:30 10–20 ежедневно | `main/expired_access_reminders.py` | Серия day0–day3 |
| **Inactivity nudges (B)** | :00/:30 10–20 ежедневно | `main/inactivity_nudges.py` | Платники: 1d/3d/5d/10d |
| **Free user nudges (C)** | каждые 2 мин | `main/inactivity_nudges.py` | C1–C4 по таймерам |
| Payment reminders | каждые 2 мин | `main/payment_reminders.py` | Без изменений |
| Reconcile payments | каждые 10 мин | `bot.py` | Без изменений |

**Удаляется:**
- ~~`activation_broadcast`~~ → заменяется C1
- ~~`divination_reminder_broadcast` (Пн/Чт)~~ → заменяется B + C4

---

## 9. Защита от catch-up (из коммита c88d97f)

При долгом простое бота (деплой, перезагрузка) пользователь может стать eligible сразу для нескольких этапов. Без защиты он получит все пропущенные nudge в одном тике.

### Решение

- За один тик каждому пользователю уходит **максимум 1 этап** на категорию
- `sent_paid_this_run: set[int]` — для триггера B
- `sent_this_category: set[int]` — для каждой из C1–C4
- Следующий этап отправится в следующем тике (через 30 мин или 2 мин)

---

## 10. Сброс состояния при возвращении

Когда пользователь делает новое гадание:

```python
# В handlers/divination.py после успешного расклада:
await reset_inactivity_nudge_state(user_id)
```

Что сбрасывается:
- Все `paid_inactivity_*_sent_at` → NULL
- Все `free_nudge_c2_*_sent_at` → NULL (начнёт с начала, если опять замолчит)
- Все `free_nudge_c4_*_sent_at` → NULL
- `free_nudge_c1_*` **не сбрасывается** (одноразовая серия после регистрации)
- `free_nudge_c3_*` **не сбрасывается** (пользователь уже в paywall)

---

## 11. Пересечения и приоритеты

| Ситуация | Что побеждает |
|----------|--------------|
| Есть open payment (pending) | Пропускаем все nudge (skip) |
| Expired access + inactivity | Только триггер A (не B, т.к. доступа уже нет) |
| C1 + C2 | Взаимоисключающие (0 гаданий vs 1+ гадание) |
| C3 + C4 | Взаимоисключающие (0 free remaining vs free > 0) |
| C2 + B | C2 = бесплатный, B = платник — взаимоисключающие |
| Карта дня + nudge в тот же день | Допускается — разные потоки |
| Payment reminder + C3 | C3 не шлётся если есть open payment |

---

## 12. Порядок реализации

### Этап 1 — Инфраструктура

- [ ] Обновить `main/broadcast_schedule.py`: добавить `anchor_at`, `is_in_broadcast_window()`
- [ ] Миграция БД (новые колонки)
- [ ] Обновить `init_db.sql`
- [ ] Добавить `paywall_reached_at` — проставлять при упоре в лимит (в `handlers/divination.py`)

### Этап 2 — Триггер A (expired access)

- [ ] `main/expired_access_reminders.py`
- [ ] DB-функции: `get_users_due_for_expired_access_reminder(stage)`, `mark_expired_access_reminder_sent()`
- [ ] Тексты в `send_message.py`
- [ ] Job в `bot.py`

### Этап 3 — Триггер B (paid inactivity)

- [ ] DB-функции: `get_users_due_for_paid_inactivity_nudge(stage)`, `mark_paid_inactivity_nudge_sent()`
- [ ] `send_paid_inactivity_nudge()` в `send_message.py`
- [ ] Интеграция в `main/inactivity_nudges.py`

### Этап 4 — Триггер C (free users)

- [ ] DB-функции для C1–C4
- [ ] `send_free_user_nudge()` в `send_message.py`
- [ ] Интеграция в `main/inactivity_nudges.py`
- [ ] Проставление `paywall_reached_at` при достижении лимита

### Этап 5 — Сброс и catch-up

- [ ] `reset_inactivity_nudge_state()` в database.py
- [ ] Вызов сброса при новом гадании
- [ ] Catch-up guard (sent_this_run sets)

### Этап 6 — Удаление старого

- [ ] Удалить `send_activation_broadcast()`, `send_divination_reminder_broadcast()`
- [ ] Удалить jobs `activation_broadcast`, `divination_reminder_broadcast` из `bot.py`
- [ ] Удалить сегментные константы `DIV_REMINDER_*`
- [ ] Обновить `docs/BROADCASTS.md`

### Этап 7 — Тестирование и деплой

- [ ] Прогнать миграцию на staging
- [ ] Проверить пересечение с payment_reminders (skip_pending)
- [ ] Проверить catch-up guard (остановить бота → перезапуск → только 1 nudge)
- [ ] Проверить сброс при новом гадании
- [ ] Anti-spam backfill: проставить `free_nudge_c1_*_sent_at` пользователям старше 7 дней без гаданий
- [ ] Деплой: миграция → restart

---

## 13. Оценка объёма

| Файл | Строки |
|------|--------|
| `main/inactivity_nudges.py` (новый) | ~130 |
| `main/expired_access_reminders.py` (новый) | ~80 |
| `main/broadcast_schedule.py` (обновление) | +20 |
| `main/database.py` (новые запросы) | +300 |
| `send_message.py` (новые функции, удаление старых) | +150 / −120 |
| `bot.py` (новые jobs, удаление старых) | +20 / −30 |
| миграция SQL | ~50 |
| `handlers/divination.py` (сброс + paywall_reached_at) | +15 |

**Итого:** ~750 строк нового кода, −150 удалённого. 1–2 PR.

---

## 14. Отличия от psy_max (осознанные)

| # | psy_max | max_bot | Причина |
|---|---------|---------|---------|
| 1 | Сессии чата (`max_sessions`) | Гадания (`max_divinations`) | Другой продукт |
| 2 | Онбординг Q1–Q3 | Нет формального онбординга | C1 = «не сделал ни одного расклада» (вместо «не прошёл онбординг») |
| 3 | `free_messages_remaining` | `free_divinations_remaining` | Другая модель баланса |
| 4 | Триггер C2 = «не написал после онбординга» | C2 = «сделал 1 расклад, остались бесплатные» | Адаптация под воронку таро |
| 5 | day0–day3 expired sub | day0–day3 expired access | Переименование (доступ к раскладам vs подписка на чат) |
| 6 | Нет промо/праздничных рассылок | Промо (пятница 13, полнолуние и т.д.) остаются ручными через CLI | Не автоматизируем |
| 7 | Payment reminders: 10м/1ч/3ч/24ч | Payment reminders: 10м/1ч/3ч | Пока оставляем 3 этапа, позже добавим 24ч |
| 8 | Карта дня = совет дня | Карта дня | Другой контент, та же механика |

---

## 15. Риски и митигации

| Риск | Митигация |
|------|-----------|
| Спам при включении C1 для старой базы | Anti-spam backfill: проставить sent_at старым пользователям |
| Слишком много nudge одному пользователю | Catch-up guard + skip_pending + проверка пересечений |
| Нагрузка на БД (частые запросы каждые 2 мин) | Индексы на `*_sent_at IS NULL` + `last_active_at`, запросы с LIMIT |
| Пользователь получает expired access + nudge C3 | Взаимоисключающие условия в SQL (expired = был paid, C3 = был только free) |
| Деплой без миграции | CI-check: проверка наличия колонок при старте |

---

*Документ подготовлен как план. Код будет реализован отдельным коммитом.*
