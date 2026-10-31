# Staging и production Android-приложения

## Принцип разделения

С 28 октября локальный debug APK имеет отдельный package `ru.tarotsphere.app.test`
и название «Сфера Таро — тест». Он устанавливается рядом с production и имеет
собственное локальное хранилище. Debug всегда использует `APP_STAGING_API_BASE_URL`,
даже если одновременно передан `APP_API_BASE_URL` для release.

Магазинные release-сборки пока сохраняют package `ru.tarotsphere.app`, уже
зарегистрированный в VK ID и RuStore. Их alpha и production нельзя установить
рядом: для alpha нужен отдельный тестовый телефон/профиль. Серверные контуры
разделяются адресом API, БД, секретами и режимом RuStore.

| Компонент | Staging | Production |
|---|---|---|
| API environment | `APP_ENVIRONMENT=staging` | `APP_ENVIRONMENT=production` |
| База | текущая `app_bot_db` | новая `app_bot_prod_db` |
| PostgreSQL role | текущая `app_bot_user` | новая `app_bot_prod_user` |
| API service | `app-api@staging` | `app-api@production` |
| Локальный порт | `8083` | `8093` |
| Android package | локально `ru.tarotsphere.app.test`; alpha RuStore `ru.tarotsphere.app` | `ru.tarotsphere.app` |
| API URL | `https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com` | `https://01a16ef9-d30d-71a7-ace3-0c86e758ccd0.tunnel4.com` |
| RuStore | sandbox, альфа `0.8.2 (8)` с парольным входом загружена в черновик | реальные платежи, `APP_RUSTORE_SANDBOX=false` |

Production-конфигурация проверяется при запуске. API откажется стартовать, если
там включены гостевой вход, бесплатный тестовый контакт или sandbox RuStore;
используется staging-БД/роль, HTTP URL либо отсутствуют обязательные секреты.

## Что уже существует

Staging использует прежние `app_bot_db`, `app_bot_user`, порт `8083` и первый
xTunnel без переноса данных, но его API-конфигурация уже вынесена из общей
`.env` в root-only файл и запущена как `app-api@staging`. Production поднят
отдельно на чистой `app_bot_prod_db`, портах `8093`/`8094` и втором xTunnel.
Оба API и оба туннеля включены в systemd. Миграции 004–012 применены к обеим
базам. Production callback RuStore 25 октября принял новый тестовый запрос с
HTTP 200; реальные уведомления пока выключены.

Локальный debug APK использует отдельный package и staging API. VK ID и оплата
отключены; вход доступен по логину/паролю и email. Callback-activity VK удалена из
debug manifest, платёжная схема зависит от applicationId, автозапуск Pay SDK
отключён. Тестовая версия не перехватывает callback основной версии.

RuStore Pay и VK ID проверяются отдельно в зарегистрированной магазинной сборке.
Для полного параллельного staging, включая эти интеграции, нужно зарегистрировать
тестовый package и его сертификат в соответствующих кабинетах и использовать
отдельные параметры интеграций. Это не требуется для проверки дизайна.

## Файлы конфигурации

При создании production на сервере понадобятся root-only файлы, не добавляемые в
Git:

```text
/etc/tarot-sphere/app-api-staging.env
/etc/tarot-sphere/app-api-production.env
```

Staging-шаблон описывает перенос уже существующих значений из текущего `.env`, а
не создание новой staging-БД. Production получает другие БД, роль, URL, JWT,
пароль БД и платёжные ключи. SMTP-ящик может быть общим для двух контуров, если
это осознанное операционное решение; его пароль всё равно хранится только в
root-only env-файлах. Права файлов: `root:root`, режим `0600`; каталог — `0700`.

Проверка без печати секретов:

```bash
venv/bin/python scripts/check_app_environment.py \
  --env-file /etc/tarot-sphere/app-api-staging.env --expected staging
venv/bin/python scripts/check_app_environment.py \
  --env-file /etc/tarot-sphere/app-api-production.env --expected production \
  --compare-with /etc/tarot-sphere/app-api-staging.env
```

Вторая команда отклонит совпадающие имена БД/роли, порт, URL, JWT, пароль БД и
ключи RuStore между контурами, не выводя значения секретов. Совпадение SMTP
учётных данных допускается.

Для обоих контуров также задаются лимиты из env-шаблонов. Дневной счётчик
DeepSeek хранится в каждой БД приложения отдельно и не затрагивает процесс бота
Max. Перед запуском новой версии API применить
`app/migrations/012_app_llm_budget.sql`.

## Создание production-БД

Production создаётся пустой. Аккаунты, расклады, балансы и sandbox-платежи из
`app_bot_db` не копируются. Администратор PostgreSQL выполняет только создание
новой production-роли и базы с самостоятельно сгенерированным паролем:

```sql
CREATE ROLE app_bot_prod_user LOGIN PASSWORD '<production password>';
CREATE DATABASE app_bot_prod_db OWNER app_bot_prod_user;
```

К новой базе применяются `init_app_db.sql` и миграции по порядку. Перед запуском
проверяются схема и пустые пользовательские/платёжные таблицы. В backup всегда
остаётся текущая `app_bot_db`; после создания добавляется `app_bot_prod_db`, и
для обеих отдельно проверяется восстановление.

## Сервисы и адреса

Шаблон `deploy/app-api@.service` запускает два процесса из одного кода с разными
env-файлами и портами. Старый `app-api.service` выключен; его копия сохранена на
сервере для оперативного отката staging.

Для production используется второй HTTPS origin:

```text
https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com -> 127.0.0.1:8084
    /v1/ и /static/ (кроме /static/geks/) -> 127.0.0.1:8083 (staging)
    / , /assets/ , /static/geks/ , /api/webapp/ -> бот 127.0.0.1:8081
https://01a16ef9-d30d-71a7-ace3-0c86e758ccd0.tunnel4.com -> 127.0.0.1:8094 -> 127.0.0.1:8093 (production)
```

Первый адрес одновременно является мини-приложением бота MAX. Разбор маршрутов: [WEBAPP-BACKEND-FIX.md](WEBAPP-BACKEND-FIX.md).

Тестовые callback RuStore остаются на staging. Перед реальными продажами
production callback указывает на production API. Его нельзя включать для
реальных покупок до успешных локального и внешнего smoke-тестов.

## Android-сборки

Debug для локальной разработки:

```bash
cd android
./gradlew :app:assembleDebug \
  -PAPP_STAGING_API_BASE_URL=https://staging-api.example/
```

Результат: `app/build/outputs/apk/debug/app-debug.apk`, package
`ru.tarotsphere.app.test`, версия `0.8.3-test`, имя «Сфера Таро — тест».
Проверка изоляции после сборки: `python3 scripts/check_android_test_build.py`
из корня репозитория. Production удалять не нужно. Для staging нужен отдельный
аккаунт (или уже существующий staging-аккаунт); баланс production не переносится.

Следующая alpha-сборка, если понадобится до production:

```bash
bash scripts/check_android_release.sh alpha https://staging-api.example/
cd android
./gradlew :app:bundleRelease \
  -PAPP_RELEASE_CHANNEL=alpha \
  -PAPP_API_BASE_URL=https://staging-api.example/
```

Production release:

```bash
bash scripts/check_android_release.sh production https://api.example/
cd android
./gradlew :app:bundleRelease \
  -PAPP_RELEASE_CHANNEL=production \
  -PAPP_API_BASE_URL=https://api.example/
```

Обе release-сборки подписываются постоянным ключом и имеют одинаковый package,
но разные API URL. Alpha обязана использовать staging URL, production — другой
HTTPS URL. После alpha `0.8.2 (8)` следующая версия исходников уже имеет
`versionCode 9`. Её публикация является новой сборкой и новой модерацией, а не
повторной загрузкой прежнего alpha AAB.

## Что ещё не выполнено

- обновлённый deployment workflow для двух шаблонных unit ещё не проверен живым
  запуском после push;
- контрольное восстановление последнего production-архива `app_bot_prod_db`
  выполнено 26 октября во временную БД; структура и агрегаты проверены,
  временная БД удалена;
- production AAB `0.8.3 (9)` собран и проверен; полный платёжный smoke ещё не
  выполнен;
- реальные уведомления RuStore включаются только после этого smoke.

Это отдельные инфраструктурные действия. Их не смешивать с текущей staging-альфой.
