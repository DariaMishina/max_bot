# Рассылки и автоматические напоминания

Все job'ы регистрируются в `bot.py` через APScheduler (timezone `Europe/Moscow`).

## Деплой / миграция БД

```bash
psql -U max_bot_user -d max_bot_db -h HOST -f migrations/20260705_event_driven_nudges.sql
```

Колонки также создаются автоматически при первом запуске job'ов через `ensure_*_columns()` в `main/database.py`.

**Важно:** миграция включает anti-spam backfill — существующая база не получит накопленные nudge «задним числом». Новые nudge пойдут только по событиям после деплоя (или после нового гадания, где предусмотрен сброс таймеров).

## Расписание

| Job | Расписание | Модуль | Описание |
|-----|------------|--------|----------|
| Карта дня | 09:25 ежедневно | `handlers/daily_card.py` | Карта дня подписчикам |
| Event-driven nudges | каждые 2 мин | `main/inactivity_nudges.py` | Платники (B) + бесплатные (C1–C4) |
| Expired access reminders | :00/:30 10–20 ежедневно | `main/expired_access_reminders.py` | day0–day3 после истечения доступа |
| Payment reminders | каждые 2 мин | `main/payment_reminders.py` | 10м / 1ч / 3ч / 24ч после pending-платежа |
| Reconcile payments | каждые 10 мин | `bot.py` | Сверка pending с ЮKassa |

## Event-driven nudges

### Триггер A — истёк платный доступ

Серия day0–day3 после истечения unlimited или исчерпания paid-пакета.

- **day0** — сразу после истечения (без слота, grace period)
- **day1–day3** — слот по моменту истечения (`expiry_at`)

### Триггер B — платник давно не гадал

Условие: активный доступ, есть гадания, нет открытого платежа.

| Этап | Молчание |
|------|----------|
| 1d | 1 день |
| 3d | 3 дня |
| 5d | 5 дней |
| 10d | 10 дней |

Отправка в персональный слот 10:00–20:00 MSK (по `last_active_at`).

### Триггер C — бесплатные пользователи

Отправка без слота, проверка каждые 2 мин.

**C1** — не сделал ни одного расклада (якорь: `created_at`): +1ч / +3ч / +24ч

**C2** — гадал, остались бесплатные (якорь: `last_active_at`): +3ч / +24ч / +48ч

**C3** — исчерпал бесплатные, не платил (якорь: `paywall_reached_at`): +1ч / +3ч / +24ч / +48ч

**C4** — есть бесплатные, молчит давно (якорь: `last_active_at`): +3d / +7d

При новом гадании сбрасываются таймеры B, C2, C4 (`update_user_activity_on_divination`).

## Payment reminders

Этапы после `created_at` pending/canceled платежа: 10м, 1ч, 3ч, 24ч.

## Слоты (broadcast_schedule.py)

Окно 10:00–20:00 MSK, тик 30 мин. Слот = время `anchor_at` (или hash по user_id).

## Удалено

- Welcome-активация по расписанию (заменена на C1)
- Пн/Чт сегментированная рассылка (заменена на A/B/C)

## Ручная отправка

```bash
python send_message.py USER_ID --expired-sub
python send_message.py USER_ID --no-divinations
python send_message.py USER_ID --gentle-nudge
python send_message.py USER_ID --free-return
python send_message.py USER_ID --activation
python send_message.py USER_ID --payment-reminder
```
