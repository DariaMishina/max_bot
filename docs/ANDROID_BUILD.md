# Сфера Таро — Android

Приложение для RuStore. Пакет `ru.tarotsphere.app`, текущая версия исходников
`0.8.3` (`versionCode 9`). Загруженная ранее alpha `0.8.2 (8)` остаётся
исторической сборкой. Вход по логину/паролю и восстановление через подтверждённую
почту развёрнуты на staging.

Клиент — Kotlin + Jetpack Compose, модули `app` / `data` / `domain`. API — `app_api_server.py` в корне `max_bot`, порт 8083, отдельная PostgreSQL приложения.

## Возможности

- Обязательный вход по логину/паролю, через VK ID или одноразовый email-код; токены хранятся зашифрованно.
- Вопрос → случайные карты, интуитивный выбор 3 из 9 или ввод трёх карт из своего расклада → толкование.
- Уточнения с серверным лимитом 2/5 и защитой от повторной отправки.
- История с подгрузкой страниц, полный результат, кэш Room для чтения без сети.
- Баланс, обратная связь, удаление гостевых данных.
- Каталог пакетов и консультаций; покупки через RuStore Pay проверены в sandbox по статусу основного плана от 22 октября. ЮKassa отложена.

## Запуск

Открыть **папку `android/`** в Android Studio. Нужны Android SDK 35 и совместимая с Gradle 8.11.1 Java (17–23). Java 25 из текущей Studio не подходит; на этом Mac проверена Temurin 22.

Для VK ID добавьте `VKIDClientID`, `VKIDClientSecret`, `VKIDRedirectHost` и `VKIDRedirectScheme` в игнорируемый `local.properties` по образцу `local.properties.example`. Защищённый ключ не коммитить.

На staging VM применены миграции `004_mvp.sql`–`011_password_credentials_policy.sql`.

Из корня `max_bot`:

```bash
bash scripts/check_android.sh
```

Debug использует staging-адрес xTunnel `https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com/` и отдельный package `ru.tarotsphere.app.test`.
Название на телефоне — «Сфера Таро — тест», версия — `0.8.3-test`.
Приложение устанавливается рядом с production. Другой staging-адрес задаётся через
`-PAPP_STAGING_API_BASE_URL=https://staging.example/`; `APP_API_BASE_URL` не меняет
debug API. VK ID и покупки в локальном debug отключены: используйте вход по
логину/паролю или email и отдельный staging-аккаунт. Интеграции проверяются через
зарегистрированную магазинную сборку, а не через этот APK.

Release нельзя собрать без явного канала и адреса. Для alpha используется staging:

```bash
cd android
./gradlew :app:bundleRelease \
  -PAPP_RELEASE_CHANNEL=alpha \
  -PAPP_API_BASE_URL=https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com/
```

Для production задаются `-PAPP_RELEASE_CHANNEL=production` и отдельный HTTPS URL, отличный от staging. URL не должен содержать `/v1`. Схема контуров описана в [руководстве staging/production](ANDROID_ENVIRONMENTS.md).

APK: `app/build/outputs/apk/debug/app-debug.apk`. Установить через Run в Android Studio на подключённый телефон.

Актуальные статусы и сценарии приёмки находятся в [основном плане](PLAN_ANDROID_APP.md);
платёжная эксплуатация — в [RuStore runbook](RUSTORE_BILLING_RUNBOOK.md),
логика пробного доступа — в [описании антифрода](TRIAL_ANTIFRAUD.md).

Локальные тесты не заменяют проверку живого API и установку на устройство. Отдельная приёмка на 5–10 людях исключена из первой версии; оставшиеся проверки production candidate перечислены в основном плане.
