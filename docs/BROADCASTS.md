# Рассылки и автоматические напоминания

Все job'ы регистрируются в `bot.py` через APScheduler (timezone `Europe/Moscow`).

Тексты отправляются из `send_message.py`. Для B/C2/C3/C4/expired доступна
LLM-персонализация по последним вопросам из раскладов; флаг
`PERSONALIZED_BROADCASTS=false` оставляет статичные fallback-шаблоны.

## Деплой / миграция БД

```bash
psql -U max_bot_user -d max_bot_db -h HOST -f migrations/20260726_broadcast_frequency.sql
psql -U max_bot_user -d max_bot_db -h HOST -f migrations/20260726_payment_funnel_catchup_backfill.sql
```

Миграции применять **в этом порядке до рестарта бота**. Первая добавляет новые
этапы и отмечает уже прошедшие пороги. Вторая закрывает накопленные B/C этапы,
которые раньше блокировались stale `pending`/`canceled`.

Runtime `ensure_*_columns()` повторяет backfill новых колонок, только если
колонка создаётся впервые. Второй catch-up защищён marker-таблицей от повторного
выполнения. Без обоих backfill выкатывать новую due-логику нельзя.

## Расписание

| Job | Расписание | Модуль | Описание |
|-----|------------|--------|----------|
| Карта дня | 09:25 ежедневно | `handlers/daily_card.py` | Карта дня подписчикам |
| Event-driven nudges | каждые 2 мин | `main/inactivity_nudges.py` | Платники (B) + бесплатные (C1–C4) |
| Expired access reminders | :00/:30 10–20 ежедневно | `main/expired_access_reminders.py` | day0–day7 после истечения доступа |
| Tarologist reminder | ср/вс 16:30 MSK | `main/tarologist_reminders.py` | Напоминание о тарологе Диане (всем незаблокированным) |
| Payment reminders | каждые 2 мин | `main/payment_reminders.py` | 10м / 1ч / 3ч / 12ч / 24ч / 48ч |
| Reconcile payments | каждые 10 мин | `bot.py` | Сверка pending с ЮKassa |

## Event-driven nudges

### Триггер A — истёк платный доступ

Серия day0–day7 после истечения unlimited или исчерпания paid-пакета.

- **day0** — сразу после истечения (без слота, grace period)
- **day1–day7** — слот по моменту истечения (`expiry_at`)

### Триггер B — платник давно не гадал

Условие: активный доступ, есть гадания, нет открытого платежа.

| Этап | Молчание |
|------|----------|
| 12h | 12 часов |
| 1d | 1 день |
| 48h | 2 дня |
| 3d | 3 дня |
| 5d | 5 дней |
| 10d | 10 дней |

Отправка в персональный слот 10:00–20:00 MSK (по `last_active_at`).

### Триггер C — бесплатные пользователи

Отправка без слота, проверка каждые 2 мин.

**C1** — не сделал ни одного расклада (якорь: `created_at`): +1ч / +3ч / +12ч / +24ч / +48ч

**C2** — гадал, остались бесплатные (якорь: `last_active_at`): +3ч / +12ч / +24ч / +48ч

**C3** — исчерпал бесплатные, не платил (якорь: `paywall_reached_at`): +1ч / +3ч / +12ч / +24ч / +48ч

**C4** — есть бесплатные, молчит давно (якорь: `last_active_at`): +3d / +7d

При новом гадании сбрасываются таймеры B, C2, C4 (`update_user_activity_on_divination`).

Для B/C действует payment-funnel TTL 48ч:

- B блокирует только свежий `pending`; `canceled` не глушит активного платника;
- C1–C4 блокируют свежие `pending`/`canceled`, пока идут payment reminders;
- следующий этап требует отметки предыдущего;
- за один тик пользователю/платежу отправляется максимум один этап.

## Payment reminders

Этапы после `created_at` pending/canceled платежа:
10м, 1ч, 3ч, 12ч, 24ч, 48ч. При активном платном доступе не отправляются.

## Персонализация

С флагом `PERSONALIZED_BROADCASTS=true` для B/C2/C3/C4/expired DeepSeek
получает до трёх последних типов и вопросов раскладов. Тексты проходят
ограничения длины/формата; при пустом контексте, ошибке API или невалидном
ответе отправляется статичный шаблон. C1 и payment reminders не персонализируются.

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
python send_message.py --broadcast --tarologist-reminder
```
