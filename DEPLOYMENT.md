# Инструкция по настройке CI/CD для деплоя бота на сервер

## 📋 Предварительные требования

1. Репозиторий на GitHub: https://github.com/DariaMishina/max_bot
2. Сервер VM (`dariamishina@46.16.36.243`): max_bot :8081, psy_max :8080, PostgreSQL `max_bot_db`
3. Systemd на сервере (обычно уже установлен)

## 🔧 Шаг 1: Настройка сервера

### 1.1. Подключитесь к серверу

```bash
ssh -i ~/.ssh/id_ed25519_deploy dariamishina@46.16.36.243
```

### 1.2. Клонируйте репозиторий (если еще не клонирован)

**Вариант 1: Через HTTPS (рекомендуется, самый простой)**

```bash
cd ~
git clone https://github.com/DariaMishina/max_bot.git
cd max_bot
```

**Если репозиторий приватный, при запросе введите:**
- **Username**: ваш GitHub username (например, `DariaMishina`)
- **Password**: Personal Access Token (см. инструкцию ниже)

**Как создать Personal Access Token:**

1. Перейдите в GitHub: https://github.com/settings/tokens
2. Нажмите **"Generate new token"** → **"Generate new token (classic)"**
3. Заполните форму:
   - **Note**: `max_bot deployment` (любое описание)
   - **Expiration**: выберите срок действия (например, 90 days или No expiration)
   - **Select scopes**: отметьте `repo` (полный доступ к репозиториям)
4. Нажмите **"Generate token"** внизу страницы
5. **⚠️ ВАЖНО:** Скопируйте токен сразу! Он показывается только один раз
6. Сохраните токен в безопасном месте (например, в менеджере паролей)

**Использование токена:**
- При клонировании/пуше через HTTPS используйте токен вместо пароля
- Настройте Git для сохранения токена (важно для автоматического деплоя):
  ```bash
  git config --global credential.helper store
  # При первом использовании введите токен, он сохранится
  ```

**⚠️ Для автоматического деплоя лучше использовать SSH:**

Если репозиторий клонирован через HTTPS, переключите на SSH:

```bash
# На сервере
cd ~/max_bot
git remote set-url origin git@github.com:DariaMishina/max_bot.git

# Добавьте SSH ключ GitHub в authorized_keys на сервере
# (или используйте тот же ключ, что и для деплоя)
```

**Вариант 2: Через SSH (если настроен SSH ключ)**

Если у вас уже есть SSH ключ на сервере и он добавлен в GitHub:
```bash
cd ~
git clone git@github.com:DariaMishina/max_bot.git
cd max_bot
```

**Если SSH ключ не настроен, настройте его:**

```bash
# Проверьте, есть ли уже SSH ключи
ls -la ~/.ssh

# Если нет, создайте новый ключ
ssh-keygen -t ed25519 -C "your_email@example.com"
# Нажмите Enter для всех вопросов (или укажите путь)

# Покажите публичный ключ
cat ~/.ssh/id_ed25519.pub
# Скопируйте вывод и добавьте в GitHub: Settings → SSH and GPG keys → New SSH key

# Проверьте подключение
ssh -T git@github.com
```

### 1.3. Создайте виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Как проверить, активирован ли venv:**

1. **По приглашению командной строки:**
   - Если venv активирован, в начале строки будет `(venv)`:
     ```bash
     (venv) dariamishina@server:~/max_bot$
     ```
   - Если не активирован, будет просто:
     ```bash
     dariamishina@server:~/max_bot$
     ```

2. **Проверка через `which python`:**
   ```bash
   which python
   # Если активирован: /home/dariamishina/max_bot/venv/bin/python
   # Если не активирован: /usr/bin/python или /usr/bin/python3
   ```

3. **Проверка переменной окружения:**
   ```bash
   echo $VIRTUAL_ENV
   # Если активирован: /home/dariamishina/max_bot/venv
   # Если не активирован: (пусто)
   ```

**Как активировать venv (если не активирован):**

```bash
cd ~/max_bot
source venv/bin/activate
```

После активации вы увидите `(venv)` в начале строки.

**Как деактивировать venv (если нужно):**

```bash
deactivate
```

**⚠️ ВАЖНО:**
- При каждом новом подключении к серверу venv нужно активировать заново
- В systemd service venv активируется автоматически через полный путь к Python

### 1.4. Создайте файл `.env` с переменными окружения

```bash
cp .env.example .env
nano .env
```

Заполните все необходимые переменные:
```
# --- Обязательные ---
BOT_TOKEN=ваш_токен_max_бота
API_KEY=sk-proj-xxx
DB_HOST=localhost
DB_PORT=5432
DB_NAME=max_bot_db
DB_USER=max_bot_user
DB_PASSWORD=пароль

# --- Опциональные ---
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=live_xxxxx
ADMIN_CHAT_ID=ваш_user_id
METRIKA_MP_COUNTER_ID=
METRIKA_MP_TOKEN=
```

### 1.5. Создайте БД

```bash
psql -U max_bot_user -d max_bot_db -h localhost -f init_db.sql
```

### 1.6. Установите systemd service

Создайте файл `/etc/systemd/system/max-bot.service`:

```bash
sudo nano /etc/systemd/system/max-bot.service
```

Вставьте содержимое:

```ini
[Unit]
Description=Max Bot (Gadanie AI)
After=network.target postgresql.service

[Service]
Type=simple
User=dariamishina
WorkingDirectory=/home/dariamishina/max_bot
ExecStart=/home/dariamishina/max_bot/venv/bin/python bot.py
Restart=always
RestartSec=10
EnvironmentFile=/home/dariamishina/max_bot/.env

[Install]
WantedBy=multi-user.target
```

**⚠️ ВАЖНО:** Отредактируйте файл и укажите правильные пути:
- `User` — ваш пользователь на сервере (сейчас: `dariamishina`)
- `WorkingDirectory` — путь к проекту (сейчас: `/home/dariamishina/max_bot`)
- `ExecStart` — путь к Python и bot.py
- `EnvironmentFile` — путь к `.env`

### 1.7. Перезагрузите systemd и запустите сервис

```bash
sudo systemctl daemon-reload
sudo systemctl enable max-bot.service
sudo systemctl start max-bot.service
```

### 1.8. Проверьте статус

```bash
sudo systemctl status max-bot.service
```

Посмотрите логи:
```bash
tail -f ~/max_bot/bot.log
```

---

## 🔐 Шаг 2: Настройка GitHub Secrets

### 2.1. Перейдите в настройки репозитория

GitHub → https://github.com/DariaMishina/max_bot → Settings → Secrets and variables → Actions

### 2.2. Создайте SSH ключ без пароля для деплоя

**⚠️ ВАЖНО:** GitHub Actions не может использовать SSH ключи с паролем. Нужно создать специальный ключ без пароля для деплоя.

**На локальной машине выполните:**

```bash
# 1. Создайте новый SSH ключ БЕЗ пароля (нажмите Enter при запросе пароля)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_deploy -N ""

# 2. Скопируйте публичный ключ на сервер
ssh-copy-id -i ~/.ssh/id_ed25519_deploy.pub dariamishina@46.16.36.243

# Или вручную:
cat ~/.ssh/id_ed25519_deploy.pub
# Скопируйте вывод и на сервере выполните:
# mkdir -p ~/.ssh
# echo "ВАШ_ПУБЛИЧНЫЙ_КЛЮЧ" >> ~/.ssh/authorized_keys
# chmod 600 ~/.ssh/authorized_keys
```

**Проверьте подключение:**

```bash
ssh -i ~/.ssh/id_ed25519_deploy dariamishina@46.16.36.243
# Должно подключиться без запроса пароля
```

### 2.3. Добавьте следующие секреты:

1. **SSH_HOST**: `46.16.36.243`
2. **SSH_USER**: `dariamishina`
3. **SSH_PRIVATE_KEY**: содержимое приватного ключа БЕЗ пароля

Чтобы получить приватный ключ:
```bash
cat ~/.ssh/id_ed25519_deploy
```

**⚠️ ВАЖНО:**
- Используйте ключ БЕЗ пароля (созданный с `-N ""`)
- Не коммитьте приватный ключ в репозиторий!
- Этот ключ используется только для деплоя, не для личного доступа

### 2.4. Как добавить секрет в GitHub:

1. Нажмите "New repository secret"
2. Введите имя (например, `SSH_PRIVATE_KEY`)
3. Вставьте значение
4. Нажмите "Add secret"

---

## 🚀 Шаг 3: Настройка GitHub Actions

### 3.1. Файлы workflow уже созданы

Файлы `.github/workflows/ci.yml` и `.github/workflows/deploy.yml` уже созданы и настроены.

### 3.2. Если ваша основная ветка не `main`

Отредактируйте оба файла workflow и измените:
```yaml
branches:
  - main  # Измените на вашу ветку
```

### 3.3. Проверьте путь к проекту на сервере

**На сервере выполните:**

```bash
# 1. Проверьте текущую директорию проекта
pwd
# Должно быть: /home/dariamishina/max_bot

# 2. Проверьте домашнюю директорию
echo $HOME
# Должно быть: /home/dariamishina

# 3. Проверьте полный путь
cd ~/max_bot && pwd
# Должно быть: /home/dariamishina/max_bot

# 4. Проверьте альтернативный путь
cd /home/dariamishina/max_bot && pwd
# Должно быть: /home/dariamishina/max_bot
```

**В файле `.github/workflows/deploy.yml` проверьте путь:**
```yaml
PROJECT_DIR="$HOME/max_bot"
```

Если `pwd` показывает `/home/dariamishina/max_bot`, то путь `$HOME/max_bot` правильный (так как `$HOME` = `/home/dariamishina`).

Измените на правильный путь, если проект находится в другом месте.

---

## 🔄 Шаг 4: Коммит изменений и деплой

### 4.1. Как закоммитить изменения в GitHub

**На локальной машине:**

```bash
# 1. Перейдите в директорию проекта
cd ~/Documents/my_pet_project/max_bot

# 2. Проверьте статус изменений
git status

# 3. Добавьте все изменения (или конкретные файлы)
git add .

# Или добавьте конкретные файлы:
# git add .github/workflows/deploy.yml .github/workflows/ci.yml DEPLOYMENT.md

# 4. Закоммитьте изменения
git commit -m "Добавлен CI/CD: GitHub Actions для линтинга и автодеплоя"

# 5. Запушьте в GitHub
git push origin main
```

**⚠️ ВАЖНО:**
- Не коммитьте файл `.env` с реальными паролями и токенами!
- Убедитесь, что `.env` в `.gitignore`
- Проверьте: `git status` не должен показывать `.env` в списке изменений

### 4.2. Что происходит после `git push`

**1. GitHub Actions автоматически запускается:**
- Клонирует репозиторий
- Запускает линтер Ruff (CI workflow)
- Подключается к серверу по SSH (Deploy workflow)
- Обновляет код на сервере
- Устанавливает зависимости (`pip install -r requirements.txt`)
- **Автоматически перезапускает бота** через `systemctl restart max-bot.service`

**2. Render автоматически деплоит:**
- Если настроен автоматический деплой, Render сам обновит `webhook_server.py`
- Если нет — нужно вручную нажать "Manual Deploy" в Render

### 4.3. Проверка деплоя

**Шаг 1: Проверьте GitHub Actions**

1. Перейдите в GitHub: https://github.com/DariaMishina/max_bot → вкладка **Actions**
2. Вы увидите запущенные workflows "CI" и "Deploy to Server"
3. Нажмите на каждый, чтобы увидеть детали
4. Должен быть зеленый статус ✅, если всё успешно
5. Если есть ошибки, они будут показаны в логах

**Шаг 2: Проверьте сервер**

Подключитесь к серверу:

```bash
ssh -i ~/.ssh/id_ed25519_deploy dariamishina@46.16.36.243
cd ~/max_bot

# Проверьте последний коммит
git log -1

# Проверьте статус сервиса (должен быть active)
sudo systemctl status max-bot.service

# Посмотрите логи бота (должны быть свежие записи)
tail -n 50 bot.log

# Проверьте, что процесс запущен
ps aux | grep bot.py
```

**Шаг 3: Проверьте Render (webhook сервер)**

1. Перейдите на [render.com](https://render.com)
2. Откройте ваш сервис
3. Проверьте вкладку **Logs** — должны быть свежие логи
4. Проверьте статус — должен быть "Live" (зеленый)
5. Если статус не "Live", нажмите **Manual Deploy** → **Deploy latest commit**

### 4.4. Нужно ли перезапускать бота вручную?

**❌ НЕТ, не нужно!**

GitHub Actions автоматически перезапускает бота через:
```bash
sudo systemctl restart max-bot.service
```

**⚠️ Исключения (когда нужно перезапустить вручную):**

1. **Если GitHub Actions упал с ошибкой:**
   ```bash
   ssh -i ~/.ssh/id_ed25519_deploy dariamishina@46.16.36.243
   cd ~/max_bot
   git pull origin main
   source venv/bin/activate
   pip install -r requirements.txt
   sudo systemctl restart max-bot.service
   ```

2. **Если изменили `.env` файл на сервере:**
   ```bash
   # На сервере отредактируйте .env
   nano ~/max_bot/.env
   # Затем перезапустите
   sudo systemctl restart max-bot.service
   ```

3. **Если изменили systemd service файл:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart max-bot.service
   ```

4. **Если Render не обновился автоматически:**
   - Зайдите в Render → ваш сервис → **Manual Deploy** → **Deploy latest commit**

---

## 🔄 Шаг 5: Тестирование деплоя

### 5.1. Проверка автоматического деплоя

**Шаг 1: Проверьте, что все Secrets настроены**

1. Перейдите в GitHub: https://github.com/DariaMishina/max_bot → Settings → Secrets and variables → Actions
2. Убедитесь, что есть 3 секрета:
   - `SSH_HOST`
   - `SSH_USER`
   - `SSH_PRIVATE_KEY`

**Шаг 2: Сделайте тестовый коммит и пуш**

На локальной машине:

```bash
# Перейдите в директорию проекта
cd ~/Documents/my_pet_project/max_bot

# Сделайте небольшое изменение (например, добавьте комментарий)
echo "# Test deployment" >> README.md

# Или создайте тестовый файл
echo "Deployment test $(date)" > .deployment_test

# Закоммитьте и запушьте
git add .
git commit -m "Test: проверка автоматического деплоя"
git push origin main
```

**Шаг 3: Проверьте статус деплоя в GitHub**

1. Перейдите в GitHub: https://github.com/DariaMishina/max_bot → вкладка **Actions**
2. Вы увидите запущенные workflows
3. Нажмите на них, чтобы увидеть детали
4. Должен быть зеленый статус ✅, если всё успешно
5. Если есть ошибки, они будут показаны в логах

**Шаг 4: Проверьте на сервере, что изменения применились**

Подключитесь к серверу:

```bash
ssh -i ~/.ssh/id_ed25519_deploy dariamishina@46.16.36.243
cd ~/max_bot

# Проверьте, что тестовый файл появился (если создавали)
ls -la .deployment_test

# Или проверьте последний коммит
git log -1

# Проверьте статус сервиса (должен быть active после автоматического перезапуска)
sudo systemctl status max-bot.service

# Посмотрите логи бота (должны быть свежие записи после перезапуска)
tail -n 50 bot.log
```

**Шаг 5: Проверьте Render (webhook сервер)**

1. Перейдите на [render.com](https://render.com)
2. Откройте ваш сервис
3. Проверьте вкладку **Logs** — должны быть свежие логи
4. Проверьте статус — должен быть "Live" (зеленый)
5. Если статус не "Live" или код не обновился, нажмите **Manual Deploy** → **Deploy latest commit**

**Шаг 6: Проверьте, что бот работает**

```bash
# На сервере проверьте, что процесс запущен
ps aux | grep bot.py

# Или через systemd
sudo systemctl is-active max-bot.service
# Должно показать: active
```

### 5.2. Ручной деплой (альтернатива)

Если нужно задеплоить вручную:

```bash
ssh -i ~/.ssh/id_ed25519_deploy dariamishina@46.16.36.243
cd ~/max_bot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart max-bot.service
```

### 5.3. Что делать, если деплой не работает

**Проблема: GitHub Actions не запускается**

1. Проверьте, что вы пушите в ветку `main` (или ту, что указана в workflow)
2. Проверьте, что файл `.github/workflows/deploy.yml` существует в репозитории
3. Проверьте вкладку Actions в GitHub — возможно, workflow отключен

**Проблема: Деплой падает с ошибкой SSH**

1. Проверьте, что SSH ключ правильный в Secrets
2. Проверьте, что сервер доступен: `ping 46.16.36.243`
3. Проверьте firewall настройки Google Cloud

**Проблема: Деплой проходит, но бот не перезапускается**

1. Проверьте логи GitHub Actions — там будет видно ошибку
2. Проверьте на сервере: `sudo systemctl status max-bot.service`
3. Проверьте права доступа: `ls -la ~/max_bot`

---

## 📊 Мониторинг

### Проверка статуса сервиса

```bash
ssh -i ~/.ssh/id_ed25519_deploy dariamishina@46.16.36.243
sudo systemctl status max-bot.service
```

### Просмотр логов

```bash
# В реальном времени
tail -f ~/max_bot/bot.log

# Последние 100 строк
tail -n 100 ~/max_bot/bot.log
```

### Перезапуск сервиса

```bash
sudo systemctl restart max-bot.service
```

### Остановка сервиса

```bash
sudo systemctl stop max-bot.service
```

---

## 🛠️ Устранение проблем

### Проблема: Сервис не запускается

1. Проверьте логи:
   ```bash
   sudo journalctl -u max-bot.service -n 50
   ```

2. Проверьте права доступа:
   ```bash
   ls -la ~/max_bot
   ```

3. Проверьте, что виртуальное окружение активировано в service файле (путь к Python должен быть `/home/dariamishina/max_bot/venv/bin/python`)

### Проблема: GitHub Actions не может подключиться

1. Проверьте, что SSH ключ добавлен правильно в Secrets
2. Проверьте, что сервер доступен из интернета
3. Проверьте firewall настройки Google Cloud

### Проблема: Бот не отвечает

1. Проверьте логи: `tail -f ~/max_bot/bot.log`
2. Проверьте, что `.env` файл существует и содержит все переменные
3. Проверьте статус сервиса: `sudo systemctl status max-bot.service`

---

## 📝 Дополнительные настройки

### Порты (max_bot и psy_max на одном сервере)

В **max_bot** вебхук-сервер (ЮKassa, `/api/webapp/cards`) слушает порт из переменной **`PORT`** в `.env`. По умолчанию в коде — **8081**, чтобы не конфликтовать с **psy_max**, который использует 8080.

- В `.env` задано `PORT=8081` (при необходимости можно сменить).
- На том же сервере psy_max слушает 8080, max_bot — 8081.

Проверить, кто слушает порт (ничего не останавливая):

```bash
ss -tlnp | grep 8080
ss -tlnp | grep 8081
```

### Почему «нет сообщений» после отправки карт в веб-приложении

Веб-приложение (GitHub Pages) по умолчанию шлёт запросы на **Render** (`https://max-bot-awtw.onrender.com`), а не на вашу VM. Поэтому в логах на сервере нет строк вида `WebApp card selection` или `POST /api/webapp/cards` — запросы доходят только до Render.

- Если Render «спит» (free tier) или недоступен с телефона — в консоли будут `T1-fetch FAIL`, `T2-xhr FAIL`, запрос отправки карт может не дойти или упасть по таймауту.
- Если запрос до Render дошёл и вернул 200, но толкование в чат не пришло — смотреть логи и переменные окружения на **Render** (OpenAI, БД, ошибки в `_process_webapp_divination`).

**Чтобы запросы шли на вашу VM** (где вебхук уже слушает 8081):

1. Нужен **HTTPS** до этой VM: браузер с `https://dariamishina.github.io` не разрешает запросы на `http://46.16.36.243:8081` (mixed content). Варианты:
   - домен, указывающий на VM, и nginx/caddy с Let's Encrypt;
   - туннель (ngrok, Cloudflare Tunnel) с HTTPS.
2. После появления HTTPS-URL вашей VM задать его в веб-приложении: в `index.html` перед подключением `app.js` добавить, например:
   ```html
   <script>window.WEBAPP_API_URL = 'https://ваш-домен-или-туннель';</script>
   ```
   Тогда отправка карт пойдёт на VM, в логах появятся `WebApp card selection` и сообщение в чат будет слать уже этот сервер.

### Настройка firewall для webhook

Если вебхук max_bot доступен снаружи с этого сервера (не через Render):

**На самом сервере (UFW):**
```bash
sudo ufw allow 8081/tcp
```

**Google Cloud Platform** — правило фаервола нужно создавать **не на VM**, а с локальной машины с настроенным `gcloud` (или из Cloud Console), иначе будет ошибка *insufficient authentication scopes*:

```bash
# Выполнять с локального компьютера (где вы логинились в gcloud), не по SSH на сервер
gcloud compute firewall-rules create allow-max-bot-webhook \
    --allow tcp:8081 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow webhook max_bot (YooKassa, webapp)"
```

**Либо через веб-интерфейс Google Cloud Console:**

Где открыть форму: **VPC network** → **Firewall** → **Create firewall rule** (или **Network Security** → **Firewall policies** → создать правило, в зависимости от интерфейса).

Заполнение формы по полям:

| Раздел / поле | Что указать |
|---------------|-------------|
| **Name \*** | `allow-max-bot-webhook-8081` (латиница, цифры, дефисы). |
| **Description** | `Входящий TCP 8081 для вебхука max_bot (ЮKassa, webapp)`. |
| **Logs** | Оставить **Off** (логи фаервола платные). |
| **Network \*** | Сеть, в которой запущена VM (часто `default`). |
| **Priority** | Например `1000` (чем меньше число, тем выше приоритет). |
| **Direction of traffic** | **Ingress** (входящий трафик). |
| **Action on match** | **Allow**. |
| **Targets** | **All instances in the network** — правило для всех VM в сети; либо **Specified target tags** и указать тег вашей VM (если теги настроены). |
| **Source filter** | **IPv4 ranges**. |
| **Source IPv4 ranges \*** | `0.0.0.0/0` (разрешить доступ с любого IP; для продакшена при необходимости потом сузьте диапазон). |
| **Protocols and ports** | Выбрать **Specified protocols and ports**, отметить **TCP** и в поле портов ввести `8081`. |

В конце нажать **Create** / **Создать**.

**Что дальше после создания правила фаервола:**

1. **Перезапустить max_bot на сервере**, чтобы он поднял вебхук на 8081 (если ещё не перезапускали после добавления `PORT=8081` в `.env`):
   ```bash
   sudo systemctl restart max-bot.service
   ```

2. **Проверить, что порт 8081 слушается:**
   ```bash
   ss -tlnp | grep 8081
   ```
   Должна быть строка с `python` и портом 8081.

3. **Проверить логи** — в них должно быть что-то вроде `Webhook server started successfully on 0.0.0.0:8081`:
   ```bash
   tail -50 ~/max_bot/bot.log
   ```

4. **Проверить доступ снаружи** (с любого компьютера или телефона не в VPN):
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://46.16.36.243:8081/health
   ```
   Ожидается ответ `200`. Если тестируете с самого сервера: `curl -s http://localhost:8081/health` — должно вернуть `OK`.

После этого вебхук ЮKassa и запросы с веб-приложения (если они идут на этот сервер, а не на Render) будут доходить до max_bot.

### Автоматический перезапуск при сбое

Service файл уже настроен с `Restart=always`, но можно добавить ограничения:

```ini
StartLimitInterval=200
StartLimitBurst=5
```

---

## ✅ Чеклист настройки

- [ ] Репозиторий клонирован на сервере
- [ ] Виртуальное окружение создано
- [ ] Зависимости установлены
- [ ] Файл `.env` создан и заполнен
- [ ] PostgreSQL — БД создана (`init_db.sql`)
- [ ] Systemd service установлен и настроен
- [ ] Сервис запущен и работает
- [ ] GitHub Secrets настроены (`SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`)
- [ ] GitHub Actions workflow настроен
- [ ] Тестовый деплой выполнен успешно
- [ ] Render настроен для webhook-сервера (если используется)

---

## 🎉 Готово!

После выполнения всех шагов, каждый `git push` в ветку `main` будет автоматически деплоить изменения на ваш сервер!
