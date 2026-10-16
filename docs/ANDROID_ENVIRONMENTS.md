# Staging и production Android-приложения

## Принцип разделения

У всех Android-сборок остаётся один package name — `ru.tarotsphere.app`. Это уже
зарегистрированное приложение VK ID и RuStore; новый package в VK ID добавлять не
нужно. Контуры разделяются адресом API, серверной БД, секретами и режимом RuStore,
а не `applicationId`.

| Компонент | Staging | Production |
|---|---|---|
| API environment | `APP_ENVIRONMENT=staging` | `APP_ENVIRONMENT=production` |
| База | текущая `app_bot_db` | новая `app_bot_prod_db` |
| PostgreSQL role | текущая `app_bot_user` | новая `app_bot_prod_user` |
| API service | пока текущий `app-api.service`, позднее можно `app-api@staging` | `app-api@production` |
| Локальный порт | `8083` | `8093` |
| Android package | `ru.tarotsphere.app` | `ru.tarotsphere.app` |
| API URL | текущий xTunnel | отдельный явный production URL |
| RuStore | sandbox, следующая альфа `0.8.2 (8)` с парольным входом | реальные платежи, `APP_RUSTORE_SANDBOX=false` |

Production-конфигурация проверяется при запуске. API откажется стартовать, если
там включены гостевой вход, бесплатный тестовый контакт или sandbox RuStore;
используется staging-БД/роль, HTTP URL либо отсутствуют обязательные секреты.

## Что уже существует

Текущие `app_bot_db`, `app_bot_user`, `.env`, `app-api.service`, порт `8083` и
xTunnel остаются staging без переименования и без переноса данных. Альфа
`0.8.0 (6)` отклонена модерацией; следующая staging-сборка — `0.8.2 (8)`.
Для парольного входа до установки нового APK нужны миграция 007 и новый API;
см. [PASSWORD_AUTH_RUNBOOK.md](PASSWORD_AUTH_RUNBOOK.md).

Локальный debug APK использует тот же package и staging API. RuStore Pay нужно
проверять не в локально установленном debug APK, а в сборке, установленной через
тестовый канал RuStore.

## Файлы конфигурации

При создании production на сервере понадобятся root-only файлы, не добавляемые в
Git:

```text
/etc/tarot-sphere/app-api-staging.env
/etc/tarot-sphere/app-api-production.env
```

Staging-шаблон описывает перенос уже существующих значений из текущего `.env`, а
не создание новой staging-БД. Production получает другие БД, роль, URL, JWT,
пароли и платёжные ключи. Права файлов: `root:root`, режим `0600`; каталог —
`0700`.

Проверка без печати секретов:

```bash
venv/bin/python scripts/check_app_environment.py \
  --env-file /etc/tarot-sphere/app-api-staging.env --expected staging
venv/bin/python scripts/check_app_environment.py \
  --env-file /etc/tarot-sphere/app-api-production.env --expected production \
  --compare-with /etc/tarot-sphere/app-api-staging.env
```

Вторая команда отклонит совпадающие имена БД/роли, порт, URL, JWT, пароли и
ключи между контурами, не выводя значения секретов.

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

Шаблон `deploy/app-api@.service` позволяет позднее запустить два процесса из
одного кода с разными env-файлами и портами. До отдельного согласованного
переключения существующий `app-api.service` остаётся staging и не удаляется.

Для production нужен второй HTTPS origin, например:

```text
текущий xTunnel               -> 127.0.0.1:8083 (staging)
https://api.example/          -> 127.0.0.1:8093 (production)
```

Тестовые callback RuStore остаются на staging. Перед реальными продажами
production callback должен указывать на production API. Конкретный production
адрес и способ переключения ещё не выбраны.

## Android-сборки

Debug для локальной разработки:

```bash
cd android
./gradlew :app:assembleDebug \
  -PAPP_STAGING_API_BASE_URL=https://staging-api.example/
```

Package остаётся `ru.tarotsphere.app`; менять настройки приложения VK ID не
нужно.

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
HTTPS URL. После следующей альфы `0.8.2 (8)` основная версия должна иметь
`versionCode` не меньше `9`; это новая сборка и новая модерация, а не повторная
загрузка alpha AAB.

## Что ещё не выполнено

- production-БД и роль не созданы;
- production-секреты не сгенерированы;
- второй HTTPS origin не выбран;
- production systemd service не включён;
- workflow пока развёртывает только прежний `app-api.service`;
- production-БД ещё не добавлена в backup и не проверена восстановлением;
- production AAB с `versionCode >= 7` ещё не собирался.

Это отдельные инфраструктурные действия. В рамках текущих правок сервер и уже
отправленная альфа не изменяются.
