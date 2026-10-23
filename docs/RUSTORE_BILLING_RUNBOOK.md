# Runbook RuStore Pay

## Назначение

Короткая инструкция для эксплуатации платежей Android-приложения. Все команды выполняются на VM из каталога проекта. Секреты, полные email, токены, callback payload и приватные ключи в тикеты и логи не копировать.

## Нормальная проверка

```bash
sudo systemctl is-active app-api
curl -fsS http://127.0.0.1:8083/health
bash scripts/billing_health_report.sh
```

Отчёт проверяет доступность API, наличие серверной конфигурации RuStore и выводит только безопасные агрегаты: завершённые/отозванные платежи, принятые callback, обращения приложения к LLM, ошибки и зависшие обращения. Нулевые значения допустимы, если операций не было.

Дополнительно проверить журнал без вывода секретов:

```bash
sudo journalctl -u app-api --since '1 hour ago' --no-pager | grep -E 'RuStore|ERROR|Traceback'
```

Тревога нужна при повторяющихся `rustore_unavailable`, `invalid_callback`, HTTP 5xx, расхождении покупки и баланса, отсутствии ожидаемого callback, росте `app_llm_failures_24h` или ненулевом `app_llm_incomplete_10m`. `purchase_not_confirmed` сразу после оплаты может быть кратковременным и должен исчезнуть после повтора.

## Лимиты API и DeepSeek

Приложение имеет собственные лимиты IP/аккаунта и отдельный от бота аварийный
счётчик обращений DeepSeek. Значения задаются в env: `APP_API_IP_REQUESTS_PER_MINUTE`,
`APP_AUTH_IP_REQUESTS_PER_15_MINUTES`, `APP_API_USER_REQUESTS_PER_MINUTE`,
`APP_DIVINATION_USER_REQUESTS_PER_HOUR`, `APP_DEEPSEEK_DAILY_REQUEST_LIMIT` и
`APP_DEEPSEEK_CONCURRENT_REQUESTS`. Лимит DeepSeek считается атомарно по таблице
`app_llm_requests` за скользящие 24 часа; неудачные обращения тоже учитываются.
Код бота Max эту таблицу и эти настройки не использует.

Для аварийной остановки только новых LLM-запросов приложения установить
`APP_DEEPSEEK_DAILY_REQUEST_LIMIT=0` и перезапустить соответствующий app-api.
Авторизация, история, покупки и бот продолжат работать; создание расклада и
уточнение вернут безопасный HTTP 503. После изменения проверить `/health`, журнал
и затем вернуть согласованный ненулевой бюджет.

## TLS-сертификаты RuStore Public API

Хост `public-api-m.rustore.ru` использует российскую цепочку доверия. На каждой
VM, которая проверяет покупки, должны быть установлены официальные корневой и
промежуточный сертификаты Минцифры по инструкции RuStore:

```bash
curl -fsSLo /tmp/russian_trusted_root_ca.crt \
  https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt
curl -fsSLo /tmp/russian_trusted_sub_ca.crt \
  https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt
openssl x509 -in /tmp/russian_trusted_root_ca.crt -noout -subject -issuer -dates -fingerprint -sha256
openssl x509 -in /tmp/russian_trusted_sub_ca.crt -noout -subject -issuer -dates -fingerprint -sha256
sudo install -m 0644 /tmp/russian_trusted_root_ca.crt \
  /usr/local/share/ca-certificates/russian_trusted_root_ca.crt
sudo install -m 0644 /tmp/russian_trusted_sub_ca.crt \
  /usr/local/share/ca-certificates/russian_trusted_sub_ca.crt
sudo update-ca-certificates
curl -sS -o /dev/null \
  -w 'http=%{http_code} tls_verify=%{ssl_verify_result}\n' \
  https://public-api-m.rustore.ru/public/auth/
```

У `curl` допустим HTTP-ответ об отсутствии авторизации, но не допустима ошибка
`unable to get local issuer certificate`. В `app-api` эта ошибка приводит к HTTP
500 на `/v1/billing/rustore/verify`; callback затем возвращает
`payment_not_ready`, потому что покупка ещё не зарегистрирована локально. Не
отключать проверку TLS и не использовать `curl -k`/`ssl=False` как исправление.

## Деплой API

1. Убедиться, что тесты CI прошли.
2. Если появился новый файл в `app/migrations`, сначала сделать свежий backup и вручную применить миграцию только к нужной БД приложения. Перед текущей версией обязательна `012_app_llm_budget.sql`.
3. Запустить `Deploy App API` вручную с `confirm_migrations_applied=true` только после успешной миграции.
4. Проверить service, `/health`, `billing_health_report.sh` и журнал.

Workflow специально не выполняет миграции автоматически: изменение схемы и откат приложения имеют разные риски, а неудачную миграцию нельзя безопасно отменить простым возвратом к предыдущему commit.

## Аварийное отключение новых покупок

1. Сохранить резервную копию серверного `.env` с правами `0600`.
2. Очистить `APP_RUSTORE_PRIVATE_KEY` в серверном `.env` и перезапустить `app-api`.
3. Убедиться, что авторизованный `GET /v1/catalog` возвращает `billing_enabled=false` и пустой `payment_methods`.
4. Не выключать callback в консоли: уведомления о уже совершённых покупках и возвратах должны продолжить повторяться. После исправления вернуть ключ, перезапустить API и проверить отчёт.

Отключение ключа блокирует серверное подтверждение и начисление, поэтому это аварийная мера. Если покупка могла пройти непосредственно перед отключением, после восстановления обязательно повторить verify и сверить платёж с балансом.

## Разбор покупки

Для расследования использовать `purchase_id`/`invoice_id`, не email пользователя. Проверить одну запись `app_payments`, соответствующий баланс и число уведомлений. Любые ручные изменения баланса выполняются только после backup и отдельного подтверждения владельца; сначала сохраняются исходные значения и причина.

Повторный запрос verify обязан вернуть `granted=false` и не менять баланс. Повтор callback с тем же notification ID обязан вернуть успех без второго списания.

## Возврат

1. Выполнить возврат в sandbox/консоли RuStore.
2. Убедиться, что callback принят.
3. Для расходуемого товара проверить `status='revoked'` и `revoked_amount`: снимается не больше оставшегося платного баланса.
4. Для подписки проверить `is_active=false` и пересчитанный `unlimited_until`.
5. Повторить тот же callback и убедиться, что значения не изменились.

## Backup и восстановление

`app_bot_db` уже входит в общий зашифрованный backup. Полная схема, timer и контролируемое восстановление описаны в `docs/DATABASE_BACKUP_PLAN.md`. Перед production-релизом должны быть подтверждены: активный timer, свежий внешний архив, heartbeat и тест восстановления на отдельной базе.

Release keystore проверяется локально командой `bash scripts/check_android_release.sh production https://production-api.example/`. Рабочий `.jks`, его резервная копия и пароли не должны храниться только на одном физическом устройстве; одну зашифрованную копию нужно перенести во внешнее хранилище владельца.
