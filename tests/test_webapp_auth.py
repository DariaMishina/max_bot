import hashlib
import hmac
import json
import unittest
from urllib.parse import urlencode
from main.webapp_auth import validate_init_data

TOKEN = 'test-token'
NOW = 1800000000


def signed(**overrides):
    params = {'user': json.dumps({'id': 42, 'first_name': 'Анна + & ='}), 'auth_date': str(NOW)}
    params.update(overrides)
    key = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    params['hash'] = hmac.new(key, '\n'.join(f'{k}={v}' for k,v in sorted(params.items())).encode(), hashlib.sha256).hexdigest()
    return urlencode(params)


class AuthTests(unittest.TestCase):
    def test_valid_unicode(self):
        self.assertEqual(validate_init_data(signed(), TOKEN, now=NOW)['first_name'], 'Анна + & =')

    def test_tampering(self):
        with self.assertRaises(ValueError):
            validate_init_data(signed().replace('42', '43'), TOKEN, now=NOW)

    def test_wrong_bot(self):
        with self.assertRaises(ValueError):
            validate_init_data(signed(), 'another-token', now=NOW)

    def test_duplicate_hash(self):
        with self.assertRaises(ValueError):
            validate_init_data(signed() + '&hash=x', TOKEN, now=NOW)

    def test_duplicate_user(self):
        with self.assertRaises(ValueError):
            validate_init_data(signed() + '&user=%7B%7D', TOKEN, now=NOW)

    def test_expired(self):
        with self.assertRaises(ValueError):
            validate_init_data(signed(auth_date=str(NOW-86401)), TOKEN, now=NOW)

    def test_future(self):
        with self.assertRaises(ValueError):
            validate_init_data(signed(auth_date=str(NOW+60)), TOKEN, now=NOW)

    def test_missing_user(self):
        with self.assertRaises(ValueError):
            validate_init_data(signed(user='{}'), TOKEN, now=NOW)

    def test_invalid_user_id(self):
        with self.assertRaises(ValueError):
            validate_init_data(signed(user='{"id":true}'), TOKEN, now=NOW)
