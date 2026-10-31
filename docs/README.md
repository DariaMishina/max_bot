# Карта проекта «Сфера Таро»

Срез репозитория: 24 октября 2026. Разделы WebApp обновлены 31 октября 2026. Начинать знакомство с этого файла.
Основа: Python, Kotlin, WebApp, SQL, shell-скрипты, конфигурации развёртывания и существующие документы.
Состояние серверов и RuStore приведено по датированным записям, без новой проверки VM/магазина.
Все пути в тексте — от корня репозитория; ссылки открывают соответствующие файлы.

## 1. Что здесь находится

Это один репозиторий с двумя продуктами и отдельной системой резервного копирования.

| Часть | Что делает | Код / запуск | Данные и деньги |
|---|---|---|---|
| MAX-бот | Таро, Ицзин, карта дня, уточнения, консультации, рассылки | `bot.py`, `handlers/`, `main/`, `keyboards/` | `max_bot_db`, ЮKassa |
| WebApp бота | Мини-приложение в MAX: расклады, история, карта дня, баланс | `webapp/`, `main/webapp_*.py`, `webhook_server.py` | Те же пользователи и баланс бота, `max_bot_db` |
| Android | Самостоятельное приложение «Сфера Таро» из RuStore | `android/` + `app_api_server.py` + `app/` | Своя БД, аккаунты, баланс; RuStore Pay |
| Backup | Архивирует БД с VM во внешнее хранилище | `scripts/backup_databases.sh`, systemd timer | VK Cloud S3, шифрование age |

Покупка и аккаунт бота не переносятся в Android. Связка аккаунтов отложена.
WebApp — часть бота, а не Android-приложение и не его веб-версия.
`psy_max` и `girl_max` — другие проекты вне этого репозитория; здесь только backup их БД.

## 2. MAX-бот: как проходит запрос

`MAX → bot.py → handlers → main/database.py → max_bot_db`.
Толкование запрашивается у DeepSeek; `API_KEY` относится к DeepSeek, несмотря на старые подписи OpenAI/ChatGPT.

| Файл / группа | Ответственность |
|---|---|
| `bot.py` | Long polling через aiomax, регистрация обработчиков, фоновые задания APScheduler |
| `main/botdef.py` | Экземпляр бота, адаптация aiomax к MAX, сохранение контекста для ответов |
| `handlers/message_router.py`, `main/message_routing.py` | Единый маршрут текста, защита от повторной обработки |
| `handlers/common.py` | Старт, меню, баланс, подписка на канал |
| `handlers/divination.py`, `hexagrams.py` | Сценарии Таро/Ицзин, вопрос, результат, уточнения |
| `handlers/tarot_card_parser.py`, `tarot_cards.py` | Разбор названий карт, каталог и картинки |
| `handlers/pay.py`, `keyboards/pay.py` | Пакеты, консультации, email для чека, создание/проверка платежа |
| `handlers/daily_card.py`, `feedback.py` | Карта дня, подписка на рассылку, обратная связь |
| `keyboards/` | Кнопки меню и сценариев |
| `main/database.py` | Таблицы `max_*`, баланс, платежи, история, сегменты рассылок, контекст ответов |
| `main/*reminders.py`, `inactivity_nudges.py`, `broadcast_*.py` | Отбор получателей, расписание, тексты, отправка напоминаний |
| `main/outbound_messages.py`, `reply_updates.py`, `send_errors.py` | Ответы на сообщения, журнал доставки, обработка ограничений MAX |
| `main/conversions.py`, `metrika_mp.py` | Воронка, рекламная атрибуция и отправка конверсий в Метрику |
| `send_message.py` | Общая отправка и ручные кампании; запуск может отправить сообщения пользователям |

Карта дня запланирована на 09:25 MSK; её отключает `ENABLE_DAILY_TIP`.
Есть сверка незавершённых платежей, напоминания об оплате, неактивности и окончании доступа.
Подробные сегменты и интервалы: [BROADCASTS.md](BROADCASTS.md).
`PERSONALIZED_BROADCASTS` управляет LLM-персонализацией, а не выключает все рассылки.

### WebApp и оплата бота

Мини-приложение и его API открываются с одного адреса xTunnel. Интерфейс: `webapp/index.html`, `app.js`, `style.css`, `card-data.js`. Серверная логика: `main/webapp_api.py`, `main/webapp_service.py`.
Три сценария: ответ целиком в чате, выбор карт в приложении с ответом в чате, вопрос и ответ только в приложении. В чат сначала уходит картинка карт, затем текст.
Как запустить локально и что уже работает в боте: [README-WEBAPP.md](../README-WEBAPP.md).
`webhook_server.py` отдаёт страницу, `/api/webapp/*` и `/webhook/yookassa`. Тот же процесс на Render принимает только внешний callback ЮKassa.
По [чек-листу ЮKassa](YOOKASSA_CHECKLIST.md) этот callback остаётся на Render. Открытая страница оплаты баланс не меняет.
`SERVICE_URL` — адрес возврата после оплаты, не адрес мини-приложения и не адрес Android API.
Картинки чата и гексаграммы лежат в `static/`. Каталог карт интерфейса — в `webapp/card-data.js`.

## 3. Android: клиент и собственный сервер

Пакет `ru.tarotsphere.app`, Kotlin + Jetpack Compose; Android 8+ (`minSdk 26`, `targetSdk 35`).
Исходники: `0.8.3`, `versionCode 9`. По плану в закрытой альфе проверена `0.8.2 (8)`.
Приложение устанавливается из RuStore; production-контур по последнему статусу ещё не создан.

| Слой | Где искать |
|---|---|
| Экраны и состояние | `android/app/src/main/java/ru/tarotsphere/app/ui/`: session/auth, onboarding, spread, reading, history, shop, profile |
| Навигация и оформление | `ui/navigation/`, `ui/main/`, `ui/components/`, `ui/theme/` |
| Модели и интерфейсы | `android/domain/`: баланс, расклад, аккаунт, репозитории, проверка вопроса |
| Работа с сервером | `android/data/`: Retrofit/OkHttp, DTO, refresh токенов, реализации репозиториев |
| Данные на телефоне | `SecurePrefs.kt`: зашифрованные токены; `HistoryDatabase.kt`: Room-кэш истории/результатов |
| HTTP API | `app_api_server.py`: `/v1/*`, `/health`, изображения `/static/images/*` |
| Вход и сессии | `app/account_auth.py`, `password_auth.py`, `password_recovery.py`, `auth_tokens.py` |
| Расклады | `app/divination_service.py`: сохранение результата и списание одной транзакцией, повторы по `request_id` |
| Платежи | `app/billing.py`: RuStore Public API, verify, callback, пакеты, подписка, возвраты |
| Защита расходов | `app/trial_grants.py`, `rate_limits.py`, `llm_budget.py` |
| PostgreSQL | `app/database.py`, `init_app_db.sql`, `app/migrations/` |

Вход: логин/пароль, VK ID или код на email. Восстановление пароля — через подтверждённую почту.
Пробный пакет — 3 расклада при выполнении серверных условий; `ANDROID_ID` служит антифрод-сигналом.
Три способа выбора: случайно, 3 из 9, выбор названий собственных карт; распознавания фото пока нет.
Уточнения: 2 к бесплатному раскладу, 5 к платному/безлимитному; история хранится на сервере.
Покупки проверяет сервер; UI не может сам начислить баланс. Незавершённая проверка покупки сохраняется на телефоне.
Обратная связь сохраняется в `app_feedback`; автоматическая пересылка в MAX/почту не реализована.
Продажа консультаций и ЮKassa для Android не завершены; тестовый контакт управляется отдельным флагом.
Push и полноценная продуктовая аналитика отложены; есть диагностика запуска приложения.

### Насколько части независимы

Базы, пользователи и процессы разделены, но код ещё связан:
Android API импортирует каталог `handlers/tarot_cards.py`, проверку вопроса `main/question_validation.py`
и DeepSeek-клиент `main/llm_divination.py`, который загружает общий `main/config_reader.py`.
Поэтому API пока требует также `API_KEY`, `BOT_TOKEN` и `DB_*` из общего окружения/корневого `.env`.
Это зависимость конфигурации при импорте; она не объединяет базы или балансы продуктов.
У бота отдельный DeepSeek-вызов в `handlers/divination.py`: изменения общего LLM-модуля не заменяют его автоматически.

## 4. Серверы, порты и базы

Текущая схема из конфигураций и записи о внедрении 20 октября:

```text
Мини-приложение и staging Android
  → https://01a0ba9c-….tunnel4.com → nginx 127.0.0.1:8084
      ├─ / , /assets/ , /static/geks/ , /api/webapp/ → бот :8081 → max_bot_db
      └─ /v1/ , остальной /static/                 → App API :8083 → app_bot_db
Production Android
  → https://01a16ef9-….tunnel4.com → nginx 127.0.0.1:8094 → API :8093
ЮKassa → Render /webhook/yookassa → max_bot_db
MAX → polling bot.py → max_bot_db
```

Подробности: [WEBAPP-BACKEND-FIX.md](WEBAPP-BACKEND-FIX.md), [nginx](../deploy/nginx-tarot-api-gateway.conf).
Cloudflare Quick Tunnel нужен только для телефона при локальной проверке тестового бота. Рабочее мини-приложение открывается с xTunnel.
Python-серверы в коде слушают `0.0.0.0`, nginx — только loopback; сетевые ограничения на VM надо проверять отдельно.
Наличие `127.0.0.1` в схеме upstream само по себе не закрывает порты Python-процессов снаружи.

| Контур | БД | Сервис | Конфигурация |
|---|---|---|---|
| Бот | `max_bot_db` | `max-bot.service` | Серверный `.env`; сам unit бота в репозитории отсутствует |
| Android staging | `app_bot_db` | `app-api.service`, порт 8083 | Пока общий `.env` |
| Android production, план | `app_bot_prod_db` | `app-api@production`, порт 8093 | `/etc/tarot-sphere/app-api-production.env` |
| Резервные копии | Все перечисленные + БД соседних ботов | `postgres-backup.service` / `.timer` | `/etc/max-bot-backup/backup.env` |

Схема бота: `init_db.sql`, затем `migrations/`; часть служебных таблиц/полей создаёт `main/database.py`.
Миграция `20261024_add_max_reply_context.sql` добавляет контекст ответов и журнал доставки.
Схема Android: `init_app_db.sql` и миграции 004–012; один init-файл не заменяет все миграции.
По плану на staging подтверждены 004–011. Применение `012_app_llm_budget.sql` надо подтвердить отдельно.
`admin_sql.sql` — ручные административные запросы, а не автоматическая миграция.

## 5. Backup — самостоятельная эксплуатационная система

Дамп каждой БД → проверка `pg_restore --list` → manifest с SHA-256 → шифрование age → VK Cloud S3.
Скрипт проверяет размер загруженных объектов; manifest загружается последним как отметка полного комплекта.
По умолчанию сохраняются 3 последних успешных комплекта; timer — ежедневно в 03:00 MSK с задержкой до 10 минут.
Обязательные БД: `max_bot_db`, `app_bot_db`, `psy_bot_db`, `girl_bot_db`.
`app_bot_prod_db` добавляется только через `BACKUP_APP_PRODUCTION_ENV_FILE`, не заменяя staging.
Это копии БД, не всей VM: env, ключ подписи Android, конфиги и приватный age-ключ требуют отдельного хранения.
Скрипты на VM устанавливаются в `/usr/local/sbin`; обновление Git само по себе эти копии не обновляет.
Восстановление: `scripts/restore_database_backup.sh`; требует явного подтверждения целевой БД.
По [runbook на 18 октября](DATABASE_BACKUP_PLAN.md) backup включён, четыре базы восстановлены тестово.
Остаются регулярный restore test и внешний heartbeat, если ещё не подключён; сегодняшний запуск здесь не проверялся.

## 6. Где лежат настройки и почему файлов несколько

Файлы `*.example` — образцы без рабочих секретов; сами по себе процессы их не читают.
В локальной рабочей копии найдены один `.env`, четыре env-образца и Android properties.
Серверные пути ниже взяты из unit-файлов/runbook; это не локальные дубликаты.

| Файл | Кто читает / назначение |
|---|---|
| `.env` (не в Git) | Сейчас смешаны бот, Android staging, пароли release-подписи и вспомогательный MaxStat |
| [`.env.example`](../.env.example) | Образец общего окружения разработки/staging |
| [deploy/app-api-staging.env.example](../deploy/app-api-staging.env.example) | Шаблон будущего отдельного env staging |
| [deploy/app-api-production.env.example](../deploy/app-api-production.env.example) | Шаблон отдельного env production, новые БД/роль/секреты/URL |
| [deploy/backup.env.example](../deploy/backup.env.example) | Шаблон `/etc/max-bot-backup/backup.env`: S3, шифрование, хранение |
| `android/local.properties` (не в Git) | Путь SDK и VK ID; образец — `android/local.properties.example` |
| `android/keystore.properties` (не в Git) | Путь ключа подписи и alias; ключи — `android/signing/` |
| `android/gradle.properties` | Общие параметры Gradle/Android, не серверные секреты |
| `…/.local/share/xtunnel/license.env` на VM | Только `XTUNNEL_LICENSE`; отдельная конфигурация туннеля |
| GitHub Secrets / окружение Render | Настройки CI и удалённого webhook; не синхронизируются с локальным `.env` автоматически |

`main/config_reader.py` читает `.env` относительно рабочей директории; переменные процесса приоритетнее файла.
`app/config.py` читает `APP_CONFIG_FILE`, иначе `.env`; этот переключатель действует только на AppSettings.
`TEST_MODE` и `DB_TABLE_SUFFIX` в коде сначала читаются из окружения процесса: для тестового бота задавать их явно там.
`PORT` также читается через `os.environ`: запись только в `.env` не равна экспорту для этого потребителя.
Shell-скрипты не имеют единого загрузчика env: backup/billing читают указанный файл, `internal_reports.sh` ждёт окружение/аргументы.
Файлы оставлены на своих путях: перенос потребует согласованно менять загрузчики, systemd, backup и Gradle.

## 7. Справочник переменных по назначению

`*` ниже обозначает группу имён, а не отдельную переменную. Значения секретов здесь не приводятся.

| Группа / имена | Назначение и источник |
|---|---|
| `BOT_TOKEN`, `BOT_TOKEN_TEST`, `TEST_MODE`, `DB_TABLE_SUFFIX` | Токен MAX, тестовый режим и суффикс таблиц; `main/config_reader.py` |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL бота; также отчёты и backup |
| `API_KEY` | DeepSeek для бота и Android; не ключ авторизации Android API |
| `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` | Платежи бота |
| `PORT`, `SERVICE_URL`, `RENDER_EXTERNAL_URL` | HTTP-порт бота, платёжный return URL, внешний адрес Render |
| `CHANNEL_CHAT_ID`, `CHANNEL_URL`, `ADMIN_CHAT_ID` | Подписка на канал и адресат обратной связи |
| `TAROLOGIST_NAME`, `TAROLOGIST_PROFILE_URL`, `TAROLOGIST_WORK_HOURS` | Данные консультанта в боте |
| `METRIKA_MP_COUNTER_ID`, `METRIKA_MP_TOKEN` | Серверная отправка рекламных конверсий |
| `PERSONALIZED_BROADCASTS`, `ENABLE_DAILY_TIP` | Персонализация и массовая карта дня |
| `APP_CONFIG_FILE`, `APP_ENVIRONMENT`, `APP_API_PORT`, `APP_API_PUBLIC_URL` | Выбор контура, env-файла, порта и внешнего адреса API |
| `APP_DB_HOST/PORT/NAME/USER/PASSWORD` | Отдельная БД Android; поля `app/config.py` |
| `APP_JWT_SECRET` | Подпись токенов и HMAC антифрод-сигналов |
| `APP_ALLOW_GUEST_AUTH`, `APP_ALLOW_UNPAID_TEST_CONTACT` | Временные тестовые возможности; production требует `false` |
| `APP_TRIAL_DAILY_LIMIT` | Подарков за скользящие 24 часа; по умолчанию 1000, `0` запрещает новые подарки |
| `APP_API_IP_REQUESTS_PER_MINUTE`, `APP_AUTH_IP_REQUESTS_PER_15_MINUTES` | HTTP-лимиты по IP: по умолчанию 120/мин и 30/15 мин |
| `APP_API_USER_REQUESTS_PER_MINUTE`, `APP_DIVINATION_USER_REQUESTS_PER_HOUR` | Лимиты пользователя: 60/мин и 20/час |
| `APP_DEEPSEEK_DAILY_REQUEST_LIMIT`, `APP_DEEPSEEK_CONCURRENT_REQUESTS` | Бюджет Android: 500 вызовов/24 ч, 2 одновременно на процесс; дневной `0` останавливает LLM |
| `APP_EMAIL_SMTP_HOST/PORT/USER/PASSWORD/SSL`, `APP_EMAIL_FROM` | Доставка кодов входа и восстановления |
| `APP_VK_CLIENT_ID` | Серверная проверка VK ID; клиентские VKID-настройки отдельно в properties |
| `APP_RUSTORE_CONSOLE_APP_ID`, `APP_RUSTORE_KEY_ID` | Идентификаторы приложения и ключа RuStore Public API |
| `APP_RUSTORE_PRIVATE_KEY`, `APP_RUSTORE_CALLBACK_KEY` | Серверные платёжные секреты, не для APK |
| `APP_RUSTORE_API_BASE_URL`, `APP_RUSTORE_SANDBOX` | Адрес Public API и тестовый режим платежей |
| `APP_TAROLOGIST_PROFILE_URL` | Контакт Android; поддерживается fallback на `TAROLOGIST_PROFILE_URL` |
| `APP_RELEASE_CHANNEL`, `APP_API_BASE_URL`, `APP_STAGING_API_BASE_URL`, `RUSTORE_CONSOLE_APP_ID` | Gradle-параметры `-P…`; это не одноимённые серверные настройки |
| `ANDROID_RELEASE_STORE_PASSWORD`, `ANDROID_RELEASE_KEY_PASSWORD` | Пароли подписи: Gradle читает окружение или корневой `.env` |
| `VKIDClientID`, `VKIDClientSecret`, `VKIDRedirectHost`, `VKIDRedirectScheme`, `sdk.dir` | `android/local.properties`; секрет CI называется `VKID_CLIENT_SECRET` |
| `ANDROID_JAVA_HOME`, `JAVA_HOME`, `ANDROID_HOME` | Java/SDK для локальной сборки и CI |
| `BACKUP_S3_ENDPOINT/BUCKET/PREFIX`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` | Внешнее хранилище копий |
| `BACKUP_AGE_RECIPIENT`, `BACKUP_WORK_DIR`, `BACKUP_RETENTION_SUCCESSFUL_RUNS` | Публичный ключ шифрования, рабочий каталог, количество комплектов |
| `BACKUP_PROJECT_ROOT`, `BACKUP_MAX_ENV_FILE`, `BACKUP_PSY_ENV_FILE`, `BACKUP_GIRL_ENV_FILE` | Переопределение путей исходных настроек БД |
| `BACKUP_APP_PRODUCTION_ENV_FILE` | Подключение пятой, production-БД Android к backup |
| `BACKUP_SUCCESS_HEARTBEAT_URL`, `BACKUP_FAILURE_HEARTBEAT_URL` | Уведомления внешнему монитору, опционально |
| `BACKUP_AGE_IDENTITY_FILE`, `BACKUP_ALLOW_PRODUCTION_RESTORE`, `PGPASSWORD` | Только восстановление: приватный ключ, допуск production, пароль PostgreSQL |
| `APP_PROJECT_ROOT`, `APP_ENV_FILE`, `APP_HEALTH_URL` | Только `scripts/billing_health_report.sh`; не путать с `APP_CONFIG_FILE` |
| `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY` | GitHub Secrets для деплоя; не обязательные поля `.env` приложения |
| `OLD_HOST`, `NEW_HOST`, `OLD_DB_*`, `NEW_DB_*`, `PSY_DB_*`, `SSH_KEY`, `PROJECT_DIR`, `DUMP_FILE` | Разовый `scripts/migrate_max_db.sh`; не повседневная конфигурация |
| `MAXSTAT_API_TOKEN` | Присутствует локально; потребителя в исполняемом коде репозитория не найдено |

Мини-приложение вызывает относительный `/api/webapp/` на том же хосте. Отдельной настройки `WEBAPP_API_URL` нет.
`WEBAPP_LOCAL`, `WEBAPP_ALLOWED_IDS`, `WEBAPP_DEMO` и `PUBLIC_BASE_URL` читает только локальный запускатель. В рабочем `.env` их не задают.
Модель DeepSeek, тарифы, интервалы рассылок и часть URL заданы в коде: не вся конфигурация вынесена в env.

## 8. Что важно закрыть перед production Android

Основной план остаётся [PLAN_ANDROID_APP.md](PLAN_ANDROID_APP.md), прежде всего этап 5.5 и раздел 12.
Он актуален как рабочий план, но исторические разделы не всегда описывают текущую инфраструктуру.

1. Создать чистую production-БД/роль, отдельные секреты, HTTPS origin и RuStore callback; staging-данные не переносить.
2. Применить/проверить схему до 012 включительно; текущий LLM-бюджет и billing-report уже требуют `app_llm_requests`.
3. Устранить зависимость App API от общего конфига бота: отдельный production env сейчас не полностью самодостаточен.
4. Согласовать права env с unit: `app-api@.service` работает как `dariamishina`, но `ExecStartPre` читает root-only файл.
   `EnvironmentFile` читает systemd, однако это не даёт Python-процессу права повторно открыть файл `0600 root:root`.
5. Настроить деплой production: текущий workflow перезапускает только `app-api`, проверяет 8083 и импортирует API с общим `.env`.
6. Добавить production-БД в backup, проверить восстановление, мониторинг, лимиты и актуальный платёжный сценарий.
7. Завершить реквизиты/политику/оферту, собрать candidate с новым `versionCode` и production URL, проверить из RuStore.

Дополнительные расхождения, обнаруженные при разборе:
- §14 плана описывает старый прямой туннель на 8083; актуальный gateway идёт через 8084.
- В env-примере `API_KEY` подписан OpenAI, хотя исполняемый код обращается к DeepSeek.
- Общий env-пример не перечисляет все HTTP/LLM-лимиты; отдельные App API примеры не содержат `APP_TRIAL_DAILY_LIMIT` (используется default).
- `scripts/test_app_api.sh` — старый гостевой smoke; при `APP_ALLOW_GUEST_AUTH=false` не годится для production-приёмки.
- `scripts/test_app_stage1.py` и `test_deepseek_level0.py` — интеграционные прогоны, могут обращаться к БД/платному API.
- В backup-runbook ранняя фраза «до включения timer» устарела; датированный статус ниже фиксирует внедрение.
- Новые методы `/api/webapp/*` определяют пользователя по подписи initData. Старые `/api/webapp/cards` и `/api/webapp/pending-question` подпись не проверяют; текущий интерфейс их не вызывает. Это контур бота, не авторизация Android.
- Комментарии ссылаются на отсутствующие `MIGRATION_TO_46.16.36.243.md` и `CONVERSIONS.md`; таких документов в рабочем дереве нет.

## 9. Как проверять и обновлять

| Задача | Инструмент / ограничения |
|---|---|
| Python unit-тесты | `venv/bin/python -m unittest discover -s tests -v`; именно этот набор запускается в CI App API |
| Android debug + unit + lint | `bash scripts/check_android.sh` |
| Проверка release | `scripts/check_android_release.sh alpha\|production URL`; затем сборка по [ANDROID_BUILD.md](ANDROID_BUILD.md) |
| Проверка env | `scripts/check_app_environment.py --env-file … --expected staging\|production`; есть `--compare-with` |
| Платежи / LLM | `scripts/billing_health_report.sh`, читает БД и health выбранного контура |
| Статистика бота | `internal_reports.sh`: пользователи, воронка, оплаты, баланс, reply-доставка |
| Обновление бота | `.github/workflows/deploy.yml`: push подходящих файлов в main, restart `max-bot` |
| Обновление App API | `deploy-app-api.yml`: Python-тесты, deploy staging; новые миграции требуют ручного применения |
| Публикация WebApp | Рабочий адрес — xTunnel, деплой вместе с ботом. `pages.yml` ещё копирует `webapp/` на GitHub Pages, кабинет MAX этот адрес не использует |
| Проверка Android в CI | `android.yml`: debug APK, unit-тесты, lint; не публикация release в RuStore |

Оба серверных workflow используют один checkout на VM и общую очередь деплоя.
`scripts/migrate_max_db.sh` — исторический перенос БД с очисткой таблиц назначения; не запускать как обычное обновление схемы.
`venv/`, `__pycache__/`, Android `build/`, `.gradle/`, `release-artifacts/` — зависимости/результаты сборки, не исходники.

## 10. Навигация по документации — всё в `docs/`

| Документ | Когда открывать |
|---|---|
| [OPERATIONS.md](OPERATIONS.md) | Прежний корневой README: запуск и эксплуатация |
| [PLAN_ANDROID_APP.md](PLAN_ANDROID_APP.md) | Главный план, статус и ближайшие шаги Android; историю читать с учётом дат |
| [ANDROID_BUILD.md](ANDROID_BUILD.md) | Прежний `android/README.md`: сборка и локальная разработка |
| [ANDROID_ENVIRONMENTS.md](ANDROID_ENVIRONMENTS.md) | Разделение staging/production; старые статусы альфы сверять с главным планом |
| [RUSTORE_BILLING_RUNBOOK.md](RUSTORE_BILLING_RUNBOOK.md) | Платежи, callback, эксплуатационные проверки |
| [TRIAL_ANTIFRAUD.md](TRIAL_ANTIFRAUD.md) | Правила пробного доступа |
| [ANDROID_REDESIGN.md](ANDROID_REDESIGN.md) | Дизайн и история решений; изображения в `docs/design/` |
| [OFFER_ANDROID_DRAFT.md](OFFER_ANDROID_DRAFT.md), [PRIVACY_POLICY_ANDROID_DRAFT.md](PRIVACY_POLICY_ANDROID_DRAFT.md) | Неопубликованные юридические черновики |
| [DATABASE_BACKUP_PLAN.md](DATABASE_BACKUP_PLAN.md) | Backup/restore; актуальный зафиксированный статус — раздел от 18 октября |
| [BROADCASTS.md](BROADCASTS.md) | Рассылки MAX-бота |
| [WEBAPP-BACKEND-FIX.md](WEBAPP-BACKEND-FIX.md) | Адреса xTunnel, nginx и граница с Android |
| [README-WEBAPP.md](../README-WEBAPP.md) | Сценарии мини-приложения и локальный запуск |
| [TEST_CHAT_AND_WEBAPP.md](TEST_CHAT_AND_WEBAPP.md) | Ручная проверка чата и приложения |
| [YOOKASSA_CHECKLIST.md](YOOKASSA_CHECKLIST.md) | Платежи MAX-бота и Render |
| [LANDING_METRIKA_README.md](LANDING_METRIKA_README.md) | Скрипт для внешнего лендинга `docs/landing_metrika_script.js` |
| [PLAN_PHOTO_READING.md](PLAN_PHOTO_READING.md) | Будущая функция распознавания карт по фото, не готовая возможность |
| [maxstat_new_session_result.md](maxstat_new_session_result.md) | Исследование каналов/конкурентов, не инструкция запуска |

Обновлять статус Android в основном плане, подробные процедуры — в тематическом runbook, карту — при изменении структуры.
