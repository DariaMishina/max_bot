"""MAX initData validation: https://dev.max.ru/docs/webapps/validation."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def validate_init_data(raw, token, *, now=None, max_age=86400):
    if not isinstance(raw, str) or not raw or len(raw) > 16384:
        raise ValueError('Откройте приложение через MAX.')
    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    if len({k for k, _ in pairs}) != len(pairs):
        raise ValueError('Повторяющиеся параметры входа.')
    data = dict(pairs)
    received = data.pop('hash', '')
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, '\n'.join(f'{k}={v}' for k, v in sorted(data.items())).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, received):
        raise ValueError('Не удалось подтвердить вход через MAX.')
    now = time.time() if now is None else now
    date = int(data.get('auth_date', 0))
    if date > now + 30 or now - date > max_age:
        raise ValueError('Сессия истекла. Откройте приложение заново через MAX.')
    user = json.loads(data.get('user', '{}'))
    if not isinstance(user, dict) or type(user.get('id')) is not int or user['id'] <= 0:
        raise ValueError('В данных MAX отсутствует пользователь.')
    return user
