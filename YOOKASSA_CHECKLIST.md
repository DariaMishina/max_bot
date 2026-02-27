# Чеклист ЮKassa для max_bot

По гайду из tg_bot ([YOOKASSA_COMPLETE_GUIDE.md](../tg_bot/YOOKASSA_COMPLETE_GUIDE.md)). Что уже сделано в коде и что нужно сделать вручную.

---

## ✅ Уже сделано в проекте

- **Переменные в `.env`**: `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `SERVICE_URL=https://max-bot-awtw.onrender.com`
- **Конфиг**: `main/config_reader.py` читает `yookassa_shop_id`, `yookassa_secret_key`
- **Создание платежа**: `handlers/pay.py` — `create_yookassa_payment()` с metadata `user_id`, `package_id`, `email`
- **Проверка статуса**: `check_payment_status()` по API ЮKassa
- **Webhook**: `webhook_server.py` — `POST /webhook/yookassa`, обработка `payment.succeeded`, защита от дублей, обновление БД, уведомление пользователю
- **Запуск**: `bot.py` поднимает webhook-сервер на `PORT` (8081), если ключи заданы
- **Return URL**: после оплаты редирект на `SERVICE_URL` (max-bot-awtw.onrender.com)

---

## 📋 Что нужно сделать вручную

### 1. Личный кабинет ЮKassa

- [ ] Войти: [yookassa.ru/my/](https://yookassa.ru/my/)
- [ ] **Настройки** → **HTTP-уведомления**
- [ ] Включить уведомления
- [ ] **URL для уведомлений**: `https://max-bot-awtw.onrender.com/webhook/yookassa`
  - Обязательно **HTTPS**
  - Обязательно путь **/webhook/yookassa** в конце
- [ ] События:
  - ✅ **payment.succeeded** — обязательно
  - ✅ **payment.canceled** — рекомендуется
- [ ] Нажать **«Изменить настройки»**

### 2. Render (если webhook на Render)

- [ ] **Start Command**: `python webhook_server.py` (не `bot.py`)
- [ ] В **Environment** заданы: `BOT_TOKEN`, `API_KEY`, `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, переменные БД (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`)
- [ ] При желании: `SERVICE_URL=https://max-bot-awtw.onrender.com` (на Render часто задаётся свой URL)

### 3. Проверка

- [ ] Health: открыть в браузере [https://max-bot-awtw.onrender.com/health](https://max-bot-awtw.onrender.com/health) → должно быть **OK**
- [ ] Тестовый платёж: создать платёж в боте, оплатить (тестовая карта в тестовом магазине или реальная мелкая сумма в продакшене)
- [ ] В логах: `=== YOOKASSA WEBHOOK RECEIVED ===`, `Payment notification sent to user ...`

### 4. Продакшен (если переходите с теста)

- [ ] В ЮKassa: продакшен **Shop ID** и секретный ключ (**live_**)
- [ ] В `.env` и на Render: `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY` от продакшен-магазина
- [ ] В ЮKassa в **продакшен** магазине указан webhook URL (не в тестовом)
- [ ] В тестовом магазине URL уведомлений очищен или отключён, чтобы тестовые платежи не шли в прод

---

## 🔗 Полезные ссылки

- [Личный кабинет ЮKassa](https://yookassa.ru/my/)
- [Документация API](https://yookassa.ru/developers/api)
- [Webhooks](https://yookassa.ru/developers/using-api/webhooks)
- Полный гайд (tg_bot): [tg_bot/YOOKASSA_COMPLETE_GUIDE.md](../tg_bot/YOOKASSA_COMPLETE_GUIDE.md)
