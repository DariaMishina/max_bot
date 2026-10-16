# tarot sphere — Android (этап 4)

Приложение для RuStore. Пакет `ru.tarotsphere.app`, текущая локальная версия `0.8.2-debug` (`versionCode 8`). Обычный вход по логину/паролю требует серверной миграции `007_password_auth.sql` и нового API; см. [порядок установки](../docs/PASSWORD_AUTH_RUNBOOK.md).

Клиент — Kotlin + Jetpack Compose, модули `app` / `data` / `domain`. API — `app_api_server.py` в корне `max_bot`, порт 8083, отдельная PostgreSQL приложения.

## Возможности

- Обязательный вход через VK ID или одноразовый email-код, зашифрованное хранение токенов.
- Вопрос → случайные карты, интуитивный выбор 3 из 9 или ввод трёх карт из своего расклада → толкование.
- Уточнения с серверным лимитом 2/5 и защитой от повторной отправки.
- История с подгрузкой страниц, полный результат, кэш Room для чтения без сети.
- Баланс, обратная связь, удаление гостевых данных.
- Каталог пакетов и консультаций; реальная оплата пакетов через RuStore Pay готова к настройке консоли. ЮKassa отложена.

## Запуск

Открыть **папку `android/`** в Android Studio. Нужны Android SDK 35 и совместимая с Gradle 8.11.1 Java (17–23). Java 25 из текущей Studio не подходит; на этом Mac проверена Temurin 22.

Для VK ID добавьте `VKIDClientID`, `VKIDClientSecret`, `VKIDRedirectHost` и `VKIDRedirectScheme` в игнорируемый `local.properties` по образцу `local.properties.example`. Защищённый ключ не коммитить.

На тестовой VM должны быть применены миграции `app/migrations/004_mvp.sql` и `005_account_auth.sql`.

Из корня `max_bot`:

```bash
bash scripts/check_android.sh
```

Debug использует staging-адрес xTunnel `https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com/` и тот же package `ru.tarotsphere.app`. Другой staging-адрес задаётся через `-PAPP_STAGING_API_BASE_URL=https://staging.example/`. Настройки приложения VK ID менять не нужно. Покупки проверяются в сборке, установленной через тестовый канал RuStore, а не в локальном debug APK.

Release нельзя собрать без явного канала и адреса. Для alpha используется staging:

```bash
./gradlew :app:bundleRelease \
  -PAPP_RELEASE_CHANNEL=alpha \
  -PAPP_API_BASE_URL=https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com/
```

Для production задаются `-PAPP_RELEASE_CHANNEL=production` и отдельный HTTPS URL, отличный от staging. URL не должен содержать `/v1`. Схема контуров описана в [руководстве staging/production](../docs/ANDROID_ENVIRONMENTS.md).

APK: `app/build/outputs/apk/debug/app-debug.apk`. Установить через Run в Android Studio на подключённый телефон.

Подробные объяснения каждого шага, серверные настройки и сценарии приёмки: **[Этап 4 — руководство](../docs/ANDROID_STAGE4_GUIDE.md)**.

Локальные тесты не заменяют проверку живого API и установку на устройство. Приёмка на 5–10 людях остаётся отдельным пунктом плана.
