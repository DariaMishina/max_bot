# Стабильный HTTPS для WebApp через xTunnel

## Решение

Используем уже оплаченный постоянный xTunnel и один локальный nginx-gateway.
Временный Cloudflare Quick Tunnel (`*.trycloudflare.com`) после переключения не
используем: его адрес меняется при перезапуске сервиса.

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

## Статус внедрения на 9 октября 2026

- nginx установлен и включён в автозапуск на VM;
- gateway слушает только `127.0.0.1:8084`;
- xTunnel переключён с `127.0.0.1:8083` на gateway `127.0.0.1:8084`;
- публичные `/v1/docs`, `/api/webapp/pending-question` и CORS preflight работают;
- неизвестные публичные пути возвращают `404`;
- локальный `webapp/index.html` переведён на постоянный xTunnel URL;
- публикация изменений в GitHub и отключение Cloudflare ещё не выполнялись.

## Порты и ответственность

| Компонент | Адрес | Назначение |
|---|---|---|
| `max-bot.service` | `127.0.0.1:8081` | `/api/webapp/*`, webhook ЮKassa |
| `app-api.service` | `127.0.0.1:8083` | `/v1/*`, `/static/*` |
| nginx gateway | `127.0.0.1:8084` | маршрутизация двух API |
| `xtunnel-app.service` | постоянный HTTPS URL | туннель до `127.0.0.1:8084` |

Webhook ЮKassa не переносим автоматически. Его действующий URL и настройку в
ЮKassa меняют только отдельной задачей после проверки платежей.

## Безопасный порядок внедрения

1. Установить nginx, не меняя работающий xTunnel.
2. Установить `deploy/nginx-tarot-api-gateway.conf` и запустить gateway на 8084.
3. Проверить локально все маршруты через `http://127.0.0.1:8084`.
4. Изменить цель `xtunnel-app.service` с 8083 на 8084 и перезапустить только
   `xtunnel-app`.
5. Проверить Android API через постоянный публичный URL.
6. Проверить WebApp API через тот же URL, не создавая гадание.
7. В `webapp/index.html` заменить временный Cloudflare URL на постоянный xTunnel.
8. После отдельного разрешения опубликовать WebApp через GitHub Pages.
9. После успешной проверки отключить `cloudflared-tunnel.service`.

До шага 4 Android продолжает работать через текущий xTunnel на 8083. До шага 8
опубликованный WebApp продолжает использовать прежний адрес, поэтому gateway
можно проверить без воздействия на пользователей.

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

Лицензию xTunnel необходимо продлевать до окончания оплаченного периода. Ключ
остаётся только в `/home/dariamishina/.local/share/xtunnel/license.env` и не
добавляется в репозиторий.
