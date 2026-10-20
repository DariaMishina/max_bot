# WebApp и Android API через xTunnel gateway

## Решение

Используем уже оплаченный постоянный xTunnel и один локальный nginx-gateway.
Основной публичный адрес — постоянный xTunnel. Cloudflare Quick Tunnel нельзя
использовать как адрес клиента: его URL меняется при перезапуске. Служба
Cloudflare пока сохранена как резервная и не входит в основной маршрут.

```text
GitHub Pages / Android
          |
          v
https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com
          |
          v
      xTunnel 4.0.0
          |
          v
 nginx 127.0.0.1:8084
      |              |
      |              +-- /api/webapp/* --> max-bot 127.0.0.1:8081
      |
      +-- /v1/*, /static/* --> app-api 127.0.0.1:8083
```

Почему выбран gateway:

- одна лицензия xTunnel обслуживает только один активный локальный порт;
- Android API и бот остаются независимыми процессами со своими портами;
- nginx выполняет только статическую маршрутизацию и работает под systemd;
- порт gateway слушает только loopback и не открывается в firewall;
- постоянный URL xTunnel не меняется после перезапуска VM или сервиса.

Не переносим обработчики WebApp в `app_api_server.py`: WebApp использует БД и
контекст бота, а Android API имеет отдельную авторизацию и жизненный цикл.
Не запускаем второй xTunnel с той же лицензией: опция `--force` заменит уже
активный туннель (`last launch wins`) и отключит Android API.

## Текущий статус (проверено 20 октября 2026)

- nginx установлен и включён в автозапуск на VM;
- gateway слушает только `127.0.0.1:8084`;
- xTunnel переключён с `127.0.0.1:8083` на gateway `127.0.0.1:8084`;
- публичные `/v1/docs`, `/api/webapp/pending-question` и CORS preflight работают;
- неизвестные публичные пути возвращают `404`;
- `webapp/index.html` использует постоянный xTunnel URL;
- WebApp публикуется отдельным GitHub Pages workflow;
- `cloudflared-tunnel.service` остаётся активным как legacy/fallback, но клиент
  на его временный URL не настроен;
- Render остаётся endpoint ЮKassa и fallback WebApp, его нельзя отключать вместе
  с Cloudflare или xTunnel.

## Порты и ответственность

| Компонент | Адрес | Назначение |
|---|---|---|
| `max-bot.service` | `127.0.0.1:8081` | `/api/webapp/*`, webhook ЮKassa |
| `app-api.service` | `127.0.0.1:8083` | `/v1/*`, `/static/*` |
| nginx gateway | `127.0.0.1:8084` | маршрутизация двух API |
| `xtunnel-app.service` | постоянный HTTPS URL | туннель до `127.0.0.1:8084` |

Webhook ЮKassa не переносим автоматически. Его действующий URL и настройку в
ЮKassa меняют только отдельной задачей после проверки платежей.

## Исторический порядок внедрения

1. Установить nginx, не меняя работающий xTunnel.
2. Установить `deploy/nginx-tarot-api-gateway.conf` и запустить gateway на 8084.
3. Проверить локально все маршруты через `http://127.0.0.1:8084`.
4. Изменить цель `xtunnel-app.service` с 8083 на 8084 и перезапустить только
   `xtunnel-app`.
5. Проверить Android API через постоянный публичный URL.
6. Проверить WebApp API через тот же URL, не создавая гадание.
7. В `webapp/index.html` заменить временный Cloudflare URL на постоянный xTunnel.
8. Опубликовать WebApp через GitHub Pages.
9. Отключать `cloudflared-tunnel.service` только отдельной задачей после проверки,
   что ни один клиент не использует его текущий URL.

Эти шаги уже выполнены до публикации WebApp. Раздел оставлен как схема повторного
развёртывания и отката, а не как список незавершённых работ.

## Проверки

Локально на VM:

```bash
curl -fsS http://127.0.0.1:8081/health
curl -fsS http://127.0.0.1:8083/v1/docs
curl -fsS http://127.0.0.1:8084/gateway-health
curl -fsS http://127.0.0.1:8084/v1/docs
curl -sS -i 'http://127.0.0.1:8084/api/webapp/pending-question?user_id=0'
```

Через xTunnel после переключения:

```bash
PUBLIC_URL='https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com'
curl -fsS "$PUBLIC_URL/v1/docs"
curl -sS -i "$PUBLIC_URL/api/webapp/pending-question?user_id=0"
```

Ожидается:

- `/v1/docs` возвращает JSON Android API;
- `/api/webapp/pending-question` возвращает JSON, а не `404`/HTML;
- CORS-заголовок WebApp API содержит `Access-Control-Allow-Origin: *`;
- `app-api`, `max-bot`, nginx и `xtunnel-app` имеют статус `active`.

## Откат

Если после переключения публичные проверки не проходят:

1. вернуть `xtunnel-app.service` на `127.0.0.1:8083`;
2. выполнить `systemctl daemon-reload` и перезапустить `xtunnel-app`;
3. убедиться, что публичный `/v1/docs` снова работает;
4. не менять URL опубликованного WebApp;
5. nginx оставить для диагностики или остановить отдельно.

Откат не требует изменений БД и не затрагивает процессы `max-bot` и `app-api`.

## Безопасность WebApp API

Текущие `/api/webapp/*` принимают `user_id`, а подпись `init_data` пока не
проверяют. Переход на постоянный URL не должен расширять набор маршрутов: nginx
пропускает только `/api/webapp/*`, `/v1/*` и `/static/*`. Проверку подписи MAX
нужно реализовать отдельным изменением до дальнейшего расширения WebApp API.

## Эксплуатация

```bash
systemctl is-active max-bot app-api nginx xtunnel-app
sudo nginx -t
sudo journalctl -u nginx -u xtunnel-app --since '15 minutes ago' --no-pager
```

Срок и состояние лицензии xTunnel нужно контролировать вместе с внешним health
endpoint. Ключ остаётся только в
`/home/dariamishina/.local/share/xtunnel/license.env` и не добавляется в
репозиторий.
