# WebApp и Android API через xTunnel

Мини-приложение бота и staging API Android открываются с одного постоянного адреса. Production API Android идёт через другой туннель. Webhook ЮKassa остаётся на Render.

```text
https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com
        |
        v
   xTunnel -> nginx 127.0.0.1:8084
        |
        +-- / , /assets/ , /static/geks/ , /api/webapp/
        |       -> max-bot 127.0.0.1:8081 -> max_bot_db
        |
        +-- /v1/ , остальной /static/
                -> app-api 127.0.0.1:8083 -> app_bot_db

https://01a16ef9-d30d-71a7-ace3-0c86e758ccd0.tunnel4.com
        |
        v
   xTunnel -> nginx 127.0.0.1:8094
        |
        +-- /v1/ , /static/
                -> production API 127.0.0.1:8093 -> app_bot_prod_db

ЮKassa -> https://max-bot-awtw.onrender.com/webhook/yookassa -> max_bot_db
```

Конфиг staging-шлюза: `deploy/nginx-tarot-api-gateway.conf`. Production Android: `deploy/nginx-tarot-api-production.conf`. Порты nginx слушают только loopback.

Один процесс xTunnel с одной лицензией занимает один локальный порт, поэтому бот и staging API сходятся на nginx, а не на двух туннелях с одним ключом. Обработчики WebApp не переносятся в `app_api_server.py`: у приложения другие пользователи, база и оплата.

## Кто что обслуживает

| Компонент | Адрес | Назначение |
|---|---|---|
| `max-bot.service` | `127.0.0.1:8081` | страница WebApp, `/api/webapp/*`, локальная копия webhook ЮKassa |
| `app-api` staging | `127.0.0.1:8083` | `/v1/*`, картинки приложения |
| nginx | `127.0.0.1:8084` | общий вход бота и staging API |
| nginx production | `127.0.0.1:8094` | только production API Android |
| Render | `max-bot-awtw.onrender.com` | внешний webhook ЮKassa |

Внешний callback ЮKassa на xTunnel не переносят. `SERVICE_URL` в `.env` бота остаётся адресом Render: это адрес возврата после оплаты. Страница мини-приложения им не задаётся.

GitHub Pages публикует копию `webapp/`, но кабинет MAX указывает на адрес `01a0ba9c-…`. Интерфейс запрашивает API на том же хосте.

Cloudflare Quick Tunnel используется только чтобы открыть локальный порт `8091` с телефона при проверке тестового бота. Рабочий адрес мини-приложения он не заменяет.

## Проверки

На VM:

```bash
curl -fsS http://127.0.0.1:8081/health
curl -fsS http://127.0.0.1:8083/v1/docs
curl -fsS http://127.0.0.1:8084/gateway-health
curl -fsS http://127.0.0.1:8084/v1/docs
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8084/
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8084/api/webapp/catalog
```

Ожидается: `/` отдаёт HTML мини-приложения, `/api/webapp/catalog` без заголовка `X-Max-Init-Data` отвечает `401`, `/v1/docs` — JSON Android API.

Снаружи:

```bash
PUBLIC_URL='https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com'
curl -fsS -o /dev/null -w '%{http_code}\n' "$PUBLIC_URL/"
curl -fsS "$PUBLIC_URL/v1/docs"
curl -fsS https://max-bot-awtw.onrender.com/health
```

Последняя команда проверяет webhook ЮKassa, а не мини-приложение. Ответ — `OK`.

Новые методы `/api/webapp/*` требуют подпись initData. Старые `/api/webapp/cards` и `/api/webapp/pending-question` подпись не проверяют и текущим интерфейсом не вызываются. Меняющие данные запросы дополнительно сверяют заголовок `Origin` с тем же хостом.

## Откат шлюза

Если после смены цели туннеля staging API перестал открываться:

1. Вернуть `xtunnel-app.service` на прежний локальный адрес.
2. Выполнить `systemctl daemon-reload` и перезапустить только эту службу.
3. Проверить публичный `/v1/docs`.
4. Адрес в кабинете MAX и webhook ЮKassa этой операцией не менять.

Откат не трогает базы и процессы `max-bot` и `app-api`.
