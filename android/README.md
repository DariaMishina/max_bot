# tarot sphere — Android (этап 3)

Приложение для RuStore. Пакет: `ru.tarotsphere.app`.

Бэкенд живёт в репозитории `max_bot` (порт 8083 / xTunnel). Этот каталог — клиент: Kotlin, Jetpack Compose, модули `app` / `data` / `domain`.

## Как открыть

1. Установить [Android Studio](https://developer.android.com/studio) (SDK 35, JDK 17).
2. File → Open → папка `android/` (не корень `max_bot`).
3. Дождаться Gradle Sync.
4. Run на телефоне (USB, режим разработчика) или эмуляторе.

Базовый URL API задан в `data/build.gradle.kts` как `BuildConfig.API_BASE_URL` (тестовый xTunnel). Если туннель сменился — обновить строку и пересобрать.

## Что уже есть

- Онбординг без экрана входа
- Гостевой токен: `POST /v1/auth/guest`, хранение в EncryptedSharedPreferences
- Retrofit + заголовок `Authorization: Bearer …` и обновление через `/v1/auth/refresh`
- Нижние вкладки: Расклад | История | Магазин | Профиль
- Профиль, история и магазин читают живое API

Полный расклад Таро — этап 4.
