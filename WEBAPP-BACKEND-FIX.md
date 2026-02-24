# Как сделать, чтобы после выбора карт приходило сообщение в чат

**Проблема:** веб-приложение шлёт запросы на Render, а не на вашу VM. Render может не отвечать или падать — сообщение в чат не приходит.

**Решение:** направить веб-приложение на вашу VM по HTTPS (браузер не пускает запросы с HTTPS-страницы на голый HTTP). Проще всего — туннель.

---

## Шаг 1. Туннель на VM через systemd (HTTPS к порту 8081)

На сервере (по SSH):

```bash
# 1) Установка cloudflared (один раз)
# Ubuntu/Debian:
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# 2) Копировать unit из репозитория и включить сервис
cd ~/max_bot
sudo cp deploy/cloudflared-tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cloudflared-tunnel.service
sudo systemctl start cloudflared-tunnel.service

# 3) Узнать URL туннеля (появится в логе при старте)
sudo journalctl -u cloudflared-tunnel.service -f --no-pager | head -20
```

В логе будет строка вида: `https://xxxx-xx-xx-xx-xx.trycloudflare.com` — это ваш HTTPS-URL до бэкенда. Скопируйте его для шага 2.

**Поведение:** сервис поднимается при загрузке сервера и перезапускается при сбое. При каждом перезапуске сервиса URL quick tunnel **меняется** — тогда снова смотрите лог и обновляйте `WEBAPP_API_URL` в веб-приложении. Для постоянного URL настройте [именованный туннель Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/) с фиксированным доменом.

---

## Шаг 2. Подставить этот URL в веб-приложение

**Вариант А — через index.html (постоянно):**

В `webapp/index.html` раскомментируйте строку и вставьте ваш HTTPS-URL:

```html
<script>window.WEBAPP_API_URL = 'https://xxxx-xx-xx-xx-xx.trycloudflare.com';</script>
```

Сохраните, закоммитьте и запушьте — после деплоя на GitHub Pages запросы пойдут на вашу VM.

**Вариант Б — через ссылку с параметром (для проверки):**

Откройте веб-приложение с параметром:
`https://dariamishina.github.io/max_bot/?api=https://ВАШ_ТУННЕЛЬ_URL`  
Тогда бэкендом будет указанный URL (без правки кода).

---

## Полезные команды (systemd)

```bash
sudo systemctl status cloudflared-tunnel.service   # статус
sudo journalctl -u cloudflared-tunnel.service -f   # лог (и URL при старте)
sudo systemctl restart cloudflared-tunnel.service # перезапуск (URL сменится!)
```

После настройки: выбор карт в веб-приложении → запрос на туннель → VM:8081 → в логах VM появятся `WebApp card selection` и сообщение уйдёт в чат.
