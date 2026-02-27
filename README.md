# Max-бот «Гадание AI» (aiomax)

Бот для мессенджера **Max** с гаданиями Таро и Ицзин, толкованием через ChatGPT, платежами ЮKassa и аналитикой через Яндекс Метрику.

Адаптация [Telegram-бота](../tg_bot) на фреймворк [aiomax](https://github.com/dpnspn/aiomax).

---

## Содержание

1. [Структура проекта](#структура-проекта)
2. [Быстрый старт (локально)](#быстрый-старт-локально)
3. [Переменные окружения (.env)](#переменные-окружения-env)
4. [PostgreSQL — настройка БД](#postgresql--настройка-бд)
5. [ЮKassa — подключение платежей](#юkassa--подключение-платежей)
6. [Render — деплой webhook-сервера](#render--деплой-webhook-сервера)
7. [Деплой бота (сервер / VPS)](#деплой-бота-сервер--vps)
8. [Яндекс Метрика и Директ — конверсии](#яндекс-метрика-и-директ--конверсии)
9. [Статические файлы (изображения)](#статические-файлы-изображения)
10. [Архитектура и отличия от Telegram-версии](#архитектура-и-отличия-от-telegram-версии)

---

## Структура проекта

```
max_bot/
├── bot.py                  # Главный entry point (polling + scheduler + webhook)
├── webhook_server.py       # Webhook-сервер для уведомлений ЮKassa
├── init_db.sql             # SQL-миграция — создание всех таблиц
├── requirements.txt        # Python-зависимости
├── .env.example            # Шаблон переменных окружения
├── .gitignore
├── README.md               # ← Вы здесь
│
├── main/                   # Ядро (без привязки к фреймворку)
│   ├── botdef.py           # Инициализация aiomax.Bot
│   ├── config_reader.py    # Загрузка конфигурации (pydantic-settings)
│   ├── database.py         # PostgreSQL (asyncpg) — все CRUD-операции
│   ├── conversions.py      # Сохранение конверсий в БД
│   └── metrika_mp.py       # Яндекс Метрика Measurement Protocol
│
├── handlers/               # Обработчики событий бота
│   ├── common.py           # /start, /balance, /cancel, unknown
│   ├── divination.py       # Логика гаданий (Таро + Ицзин + ChatGPT)
│   ├── pay.py              # Оплата (выбор пакета → ЮKassa → проверка)
│   ├── feedback.py         # /feedback → пересылка админу
│   ├── daily_card.py       # Ежедневная карта дня + подписка
│   ├── tarot_cards.py      # Данные карт Таро + утилиты изображений
│   └── hexagrams.py        # Данные гексаграмм Ицзин + утилиты
│
├── keyboards/              # Клавиатуры (кнопки)
│   ├── main_menu.py        # Главное меню
│   ├── divination.py       # Выбор типа гадания
│   └── pay.py              # Пакеты оплаты + подтверждение email
│
└── static/                 # Изображения
    ├── images/             # 80 карт Таро (*.png)
    └── geks/               # 12 гексаграмм (*.png, *.jpg)
```

---

## Быстрый старт (локально)

### 1. Клонировать и установить зависимости

```bash
cd max_bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настроить `.env`

```bash
cp .env.example .env
# Заполните .env — как минимум BOT_TOKEN, API_KEY, DB_*
```

Подробности — в разделе [Переменные окружения](#переменные-окружения-env).

### 3. Создать таблицы в БД

```bash
psql -U max_bot_user -d max_bot_db -f init_db.sql
```

Или запустите SQL вручную — см. раздел [PostgreSQL](#postgresql--настройка-бд).

### 4. Запустить бота

```bash
python bot.py
```

Бот запустит long polling и будет отвечать на сообщения в Max.

---

## Переменные окружения (.env)

| Переменная | Обязательна | Описание |
|---|---|---|
| `BOT_TOKEN` | Да | Токен бота Max (получить у [@MasterBot](https://max.ru/masterbot)) |
| `API_KEY` | Да | OpenAI API Key для ChatGPT (толкование гаданий) |
| `DB_HOST` | Да | Хост PostgreSQL (обычно `localhost`) |
| `DB_PORT` | Да | Порт PostgreSQL (обычно `5432`) |
| `DB_NAME` | Да | Имя базы данных (например `max_bot_db`) |
| `DB_USER` | Да | Пользователь БД |
| `DB_PASSWORD` | Да | Пароль БД |
| `YOOKASSA_SHOP_ID` | Нет* | ID магазина ЮKassa |
| `YOOKASSA_SECRET_KEY` | Нет* | Секретный ключ ЮKassa |
| `ADMIN_CHAT_ID` | Нет | `user_id` админа в Max (для пересылки фидбэка) |
| `METRIKA_MP_COUNTER_ID` | Нет | ID счётчика Яндекс Метрики для Measurement Protocol |
| `METRIKA_MP_TOKEN` | Нет | Токен для Measurement Protocol |
| `TEST_MODE` | Нет | `true` — тестовый режим (суффикс `_test` для таблиц) |
| `BOT_TOKEN_TEST` | Нет | Токен тестового бота (используется при `TEST_MODE=true`) |

\* Без ЮKassa бот работает, но оплата недоступна.

---

## PostgreSQL — настройка БД

### Установка (Ubuntu/Debian)

```bash
sudo apt update && sudo apt install postgresql postgresql-contrib -y
```

### Создание пользователя и базы

```sql
sudo -u postgres psql

CREATE USER max_bot_user WITH PASSWORD 'ваш_надежный_пароль';
CREATE DATABASE max_bot_db OWNER max_bot_user;
GRANT ALL PRIVILEGES ON DATABASE max_bot_db TO max_bot_user;
\q
```

### Применение миграции

```bash
psql -U max_bot_user -d max_bot_db -h localhost -f init_db.sql
```

Скрипт `init_db.sql` создаёт 6 таблиц:

| Таблица | Назначение |
|---|---|
| `users` | Профили пользователей (user_id, имя, email, utm-метки, client_id) |
| `user_balances` | Баланс гаданий (бесплатные / платные / безлимит) |
| `payments` | История платежей ЮKassa |
| `subscriptions` | Безлимитные подписки (сроки, статус) |
| `divinations` | История гаданий (тип, вопрос, карты, интерпретация) |
| `conversions` | Аналитика конверсий (registration, service_usage, paywall, purchase) |

Все `CREATE TABLE` — с `IF NOT EXISTS`, скрипт идемпотентен.

### Удалённый доступ (для Render → БД на сервере)

Если webhook-сервер на Render должен писать в БД на вашем сервере:

1. Разрешите подключения в `pg_hba.conf`:
   ```
   host  all  all  0.0.0.0/0  md5
   ```

2. В `postgresql.conf` установите:
   ```
   listen_addresses = '*'
   ```

3. Откройте порт 5432 в firewall:
   ```bash
   sudo ufw allow 5432/tcp
   ```

4. Перезапустите PostgreSQL:
   ```bash
   sudo systemctl restart postgresql
   ```

---

## ЮKassa — подключение платежей

### 1. Создать магазин в ЮKassa

1. Зарегистрируйтесь на [yookassa.ru](https://yookassa.ru)
2. Создайте магазин и получите:
   - **Shop ID** (числовой идентификатор)
   - **Secret Key** (секретный ключ API)

### 2. Настроить webhook

В личном кабинете ЮKassa → **Настройки** → **HTTP-уведомления (webhooks)**:

| Параметр | Значение |
|---|---|
| URL | `https://max-bot-awtw.onrender.com/webhook/yookassa` |
| Событие | `payment.succeeded` (обязательно), `payment.canceled` (рекомендуется) |

### 3. Прописать в `.env`

```env
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=live_xxxxx
```

### Как работает оплата

1. Пользователь нажимает `/pay` → видит пакеты (3/10/20/30 раскладов или безлимит)
2. Бот создаёт платёж через ЮKassa API → возвращает ссылку
3. Пользователь оплачивает в браузере
4. ЮKassa отправляет webhook `payment.succeeded` → `webhook_server.py`
5. Webhook-сервер обновляет БД + отправляет пользователю подтверждение
6. Также можно проверить статус вручную кнопкой «Я оплатила»

### Пакеты оплаты

| Пакет | Цена | Кол-во раскладов |
|---|---|---|
| Безлимит на месяц | 499 ₽ | Без ограничений (30 дней) |
| 30 раскладов | 349 ₽ | 30 |
| 20 раскладов | 249 ₽ | 20 |
| 10 раскладов | 149 ₽ | 10 |
| 3 расклада | 69 ₽ | 3 |

---

## Render — деплой webhook-сервера

### Зачем нужен Render

Render нужен **только для webhook-сервера ЮKassa** — он принимает HTTP-уведомления об успешных платежах. Сам бот (polling) крутится на отдельном сервере/VPS.

> **Важно:** НЕ запускайте `bot.py` на Render. Запускайте только `webhook_server.py`.

### Настройка

1. Создайте **Web Service** на [render.com](https://render.com)
2. Подключите GitHub-репозиторий

**Settings:**
| Параметр | Значение |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python webhook_server.py` |
| Environment | Python 3 |

**Environment Variables** (обязательные):

```
BOT_TOKEN=ваш_токен_max_бота
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=live_xxxxx
API_KEY=sk-proj-xxx
DB_HOST=IP_вашего_сервера
DB_PORT=5432
DB_NAME=max_bot_db
DB_USER=max_bot_user
DB_PASSWORD=пароль
```

### Проверка

```bash
# Health check
curl https://max-bot-awtw.onrender.com/health
# Должно вернуть: OK

# Webhook endpoint для ЮKassa
# POST https://max-bot-awtw.onrender.com/webhook/yookassa
```

### URL в ЮKassa

В настройках ЮKassa (Настройки → HTTP-уведомления) укажите:

```
https://max-bot-awtw.onrender.com/webhook/yookassa
```

---

## Деплой бота (сервер / VPS)

### 1. Подготовка сервера

```bash
ssh user@your-server-ip
sudo apt update && sudo apt install python3 python3-venv python3-pip postgresql -y
```

### 2. Клонировать и настроить

```bash
cd ~
git clone https://github.com/your-repo/max_bot.git
cd max_bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # заполните все переменные
```

### 3. Создать БД

```bash
psql -U max_bot_user -d max_bot_db -h localhost -f init_db.sql
```

### 4. Systemd-сервис (автозапуск)

Создайте файл `/etc/systemd/system/max-bot.service`:

```ini
[Unit]
Description=Max Bot (Gadanie AI)
After=network.target postgresql.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/your_user/max_bot
ExecStart=/home/your_user/max_bot/venv/bin/python bot.py
Restart=always
RestartSec=10
EnvironmentFile=/home/your_user/max_bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable max-bot.service
sudo systemctl start max-bot.service

# Проверка
sudo systemctl status max-bot.service
tail -f ~/max_bot/bot.log
```

### Обновление (деплой новой версии)

```bash
cd ~/max_bot
git pull
sudo systemctl restart max-bot.service
```

---

## Яндекс Метрика и Директ — конверсии

### Обзор

Система отслеживает воронку пользователя от регистрации до покупки. Конверсии сохраняются в таблицу `conversions` и, для рекламных пользователей из Директа, дополнительно отправляются в Яндекс Метрику в реальном времени через **Measurement Protocol**.

### Два потока трекинга

#### Кампания 1: Лендинг → Бот

| | |
|---|---|
| **Путь** | Директ → лендинг (сайт) → /start бота |
| **Счётчик** | JS-счётчик на лендинге |
| **В /start приходит** | `client_id` (настоящий ClientID из JS Метрики) |
| **source в БД** | `landing` |
| **Трекинг из бота** | Не нужен — лендинг сам фиксирует конверсию |

#### Кампания 2: Директ → Бот напрямую

| | |
|---|---|
| **Путь** | Директ → /start бота напрямую |
| **Счётчик** | `METRIKA_MP_COUNTER_ID` (сайт `max.ru/gadanie_ai_bot`) |
| **В /start приходит** | `yclid` (из макроса Директа `{yclid}`) |
| **source в БД** | `direct_ad` |
| **Ссылка в объявлении** | `https://max.ru/gadanie_ai_bot?start=ydirect_{yclid}` |

### Цели конверсий

| Цель | Тип (`conversion_type`) | Когда срабатывает |
|---|---|---|
| Регистрация | `registration` | Первый `/start` нового пользователя |
| Использование | `service_usage` | Завершённое гадание (Таро / Ицзин) |
| Пейволл | `paywall_reached` | Пользователь видит предложение оплаты |
| Покупка | `purchase` | Успешная оплата через ЮKassa |

### Как работает Measurement Protocol

Модуль: `main/metrika_mp.py`

1. При `/start` директ-пользователя: генерируем `metrika_client_id`, сохраняем в БД
2. Отправляем **pageview** → создаёт «визит» в Метрике и привязывает yclid к client_id
3. При каждом событии: отправляем **event** с идентификатором цели
4. `send_conversion_event(user_id, goal)` — хелпер, который сам проверяет, является ли пользователь директ-пользователем. Для остальных — ничего не делает

Все вызовы — **fire-and-forget** через `asyncio.create_task()`, не блокируют бота.

### Настройка счётчика Метрики

1. Создайте счётчик в [Яндекс Метрике](https://metrika.yandex.ru)
2. Укажите сайт: `max.ru` (или ваш лендинг)
3. Создайте **JavaScript-цели** с идентификаторами: `registration`, `service_usage`, `paywall`, `purchase`
4. Получите **токен для Measurement Protocol** в настройках счётчика
5. Пропишите в `.env`:
   ```env
   METRIKA_MP_COUNTER_ID=106708199
   METRIKA_MP_TOKEN=ваш_токен
   ```

### Настройка Яндекс Директ

В объявлении используйте ссылку с макросом:

```
https://max.ru/gadanie_ai_bot?start=ydirect_{yclid}
```

Бот распарсит `yclid` из start-параметра и привяжет все дальнейшие конверсии.

---

## Статические файлы (изображения)

Изображения хранятся в `static/`:

```
static/
├── images/     # Карты Таро (80 файлов .png)
│   ├── 00-TheFool.png
│   ├── 01-TheMagician.png
│   ├── ...
│   ├── Cups01.png ... Cups14.png
│   ├── Pentacles01.png ... Pentacles14.png
│   ├── Swords01.png ... Swords14.png
│   ├── Wands01.png ... Wands14.png
│   ├── CardBacks.png
│   └── background.png
│
└── geks/       # Гексаграммы Ицзин (12 файлов .png/.jpg)
    ├── 1.png
    ├── 5.jpg
    ├── 10.jpg
    └── ...
```

Пути в коде: `static/images/{card_id}.png` и `static/geks/{hex_id}.{ext}`.

Изображения отправляются через `bot.upload_image(path)` → `PhotoAttachment` → `bot.send_message(attachments=...)`.

---

## Архитектура и отличия от Telegram-версии

### aiomax vs aiogram — ключевые изменения

| Компонент | aiogram (Telegram) | aiomax (Max) |
|---|---|---|
| Entry point | `Dispatcher` + `dp.start_polling(bot)` | `Bot` — сам является главным роутером, `bot.run()` |
| Роутеры | `dp.include_routers(r1, r2)` | `bot.add_router(r1)`, `bot.add_router(r2)` |
| Команды | `@router.message(Command("start"))` | `@router.on_command('start')` |
| Сообщения | `message.from_user.id` | `message.sender.user_id` |
| Старт бота | `@router.message(CommandStart())` | `@router.on_bot_start()` |
| FSM | `StatesGroup` + `FSMContext` | Строковые состояния + `fsm.FSMCursor` |
| Клавиатуры | `ReplyKeyboardBuilder`, `InlineKeyboardBuilder` | `buttons.KeyboardBuilder` + `MessageButton` / `CallbackButton` / `LinkButton` |
| Колбэки | `@router.callback_query(F.data == "x")` | `@router.on_button_callback(lambda d: d.payload == "x")` |
| Отправка файлов | `FSInputFile` → `send_photo()` | `bot.upload_image()` → `send_message(attachments=...)` |
| WebApp | Поддерживается | Не поддерживается (заменено CallbackButton) |
| Формат текста | `parse_mode="HTML"` | `format='html'` |

### Что НЕ изменилось

- **PostgreSQL-слой** (`database.py`, `conversions.py`) — полностью framework-agnostic
- **ChatGPT интеграция** — HTTP-вызовы через aiohttp, без привязки к фреймворку
- **ЮKassa API** — прямые HTTP-вызовы
- **Яндекс Метрика MP** — прямые HTTP-вызовы
- **Бизнес-логика** — карты, гексаграммы, пакеты, баланс
