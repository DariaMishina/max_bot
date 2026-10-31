# Max-бот «Сфера Таро»

Бот для мессенджера MAX с раскладами Таро и Ицзин, интерпретациями через
DeepSeek, оплатой через ЮKassa и отдельным Android-приложением для RuStore.

## Компоненты

| Компонент | Точка входа | Назначение |
|---|---|---|
| MAX-бот | `bot.py` | polling, расклады, рассылки и локальный webhook-сервер |
| Webhook/API бота | `webhook_server.py` | ЮKassa и `/api/webapp/*`, порт `8081` |
| WebApp | `webapp/`, `main/webapp_*.py` | мини-приложение бота в MAX |
| Android API | `app_api_server.py` | отдельная авторизация, баланс, история и платежи, порт `8083` |
| Android-клиент | `android/` | Kotlin + Jetpack Compose, пакет `ru.tarotsphere.app` |

Данные бота и Android-приложения хранятся в разных PostgreSQL-базах. Покупки и
балансы между ними не объединяются.

## Локальный запуск бота

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
psql -U max_bot_user -d max_bot_db -f init_db.sql
python bot.py
```

Минимально нужны `BOT_TOKEN`, `API_KEY` и переменные `DB_*`. Полный перечень и
безопасные примеры находятся в [`.env.example`](../.env.example). Секреты и
локальный `.env` в Git не добавляются.

`init_db.sql` создаёт базовую схему бота. Последующие изменения схемы применяются
по порядку из `migrations/`. Схема Android API создаётся через `init_app_db.sql`
и `app/migrations/`.

## Проверки

Основной набор Python-тестов:

```bash
venv/bin/python -m pytest
```

Проверка Android-клиента и серверных контрактов:

```bash
bash scripts/check_android.sh
```

Перед коммитом также полезно выполнить:

```bash
git diff --check
```

## Рабочая инфраструктура

- `max-bot.service` запускает бота и локальный HTTP-сервер на `127.0.0.1:8081`.
- `app-api.service` запускает Android API на `127.0.0.1:8083`.
- nginx на `127.0.0.1:8084` отдаёт мини-приложение бота и staging API Android через один xTunnel.
  Production API Android идёт через nginx `127.0.0.1:8094` и второй туннель.
  Схема и проверки: [WEBAPP-BACKEND-FIX.md](WEBAPP-BACKEND-FIX.md).
- Сценарии и локальный запуск мини-приложения: [README-WEBAPP.md](../README-WEBAPP.md).
- Render принимает уведомления ЮKassa. Адресом мини-приложения он не является.
  Настройка платежей: [YOOKASSA_CHECKLIST.md](YOOKASSA_CHECKLIST.md).

Не открывайте PostgreSQL в интернет по инструкции из старых документов. Доступ
к БД должен быть ограничен фактически используемыми сервисами и сетями.

## Деплой

Деплой выполняют GitHub Actions:

- `.github/workflows/deploy.yml` — MAX-бот;
- `.github/workflows/deploy-app-api.yml` — Android API;
- `.github/workflows/pages.yml` — копия `webapp/` на GitHub Pages; кабинет MAX указывает на xTunnel;
- `.github/workflows/android.yml` — проверка Android debug build.

Ручное изменение production-сервисов, миграции БД и переключение публичных URL
выполняются отдельно и только после проверки соответствующего runbook.

## Документация

- [Рассылки и напоминания](BROADCASTS.md)
- [План и статус Android-приложения](PLAN_ANDROID_APP.md)
- [Staging и production Android](ANDROID_ENVIRONMENTS.md)
- [RuStore Billing runbook](RUSTORE_BILLING_RUNBOOK.md)
- [Антифрод пробного доступа](TRIAL_ANTIFRAUD.md)
- [Резервное копирование PostgreSQL](DATABASE_BACKUP_PLAN.md)
- [План распознавания физических карт](PLAN_PHOTO_READING.md)
- [Метрика лендинга](LANDING_METRIKA_README.md)

`docs/OFFER_ANDROID_DRAFT.md` и `docs/PRIVACY_POLICY_ANDROID_DRAFT.md` — рабочие
юридические черновики, а не опубликованные документы.
