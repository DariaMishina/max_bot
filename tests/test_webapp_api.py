import asyncio
import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode
import uuid
from aiohttp.test_utils import TestClient, TestServer

from scripts.webapp_local import configure
configure(demo=True)
if os.getenv('WEBAPP_UNITTEST_DB') != 'max_webapp_unittest':
    raise RuntimeError('Use scripts/test_webapp.py')
os.environ['DB_NAME']='max_webapp_unittest'
from main.database import Database
from main.config_reader import config
from pydantic import SecretStr
from webhook_server import create_webhook_app


def headers(user_id):
    params={'user':json.dumps({'id':user_id,'first_name':'API test'}),'auth_date':str(int(time.time()))}
    key=hmac.new(b'WebAppData',config.effective_bot_token.get_secret_value().encode(),hashlib.sha256).digest()
    params['hash']=hmac.new(key,'\n'.join(f'{k}={v}' for k,v in sorted(params.items())).encode(),hashlib.sha256).hexdigest()
    return {'X-Max-Init-Data':urlencode(params)}


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.uid=940000000+uuid.uuid4().int%1000000
        self.env=patch.dict(os.environ,{'WEBAPP_DEMO':'false','WEBAPP_ALLOWED_IDS':str(self.uid)})
        self.env.start()
        self.client=TestClient(TestServer(create_webhook_app()))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await Database.execute_query('DELETE FROM max_webapp_operations WHERE user_id=$1',self.uid)
        await Database.execute_query('DELETE FROM max_webapp_daily WHERE user_id=$1',self.uid)
        await Database.execute_query('DELETE FROM max_webapp_purchases WHERE user_id=$1',self.uid)
        await Database.execute_query('DELETE FROM max_users WHERE user_id=$1',self.uid)
        await Database.close_pool()
        self.env.stop()

    async def test_no_unsigned_identity(self):
        response=await self.client.get('/api/webapp/me?user_id='+str(self.uid))
        self.assertEqual(response.status,401)

    async def test_allowlist(self):
        response=await self.client.get('/api/webapp/me',headers=headers(self.uid+1))
        self.assertEqual(response.status,403)

    async def test_verified_user_wins_over_query(self):
        response=await self.client.get('/api/webapp/me?user_id=123',headers=headers(self.uid))
        self.assertEqual(response.status,200)
        self.assertEqual((await response.json())['user']['id'],self.uid)

    async def test_cross_origin_write_rejected(self):
        response=await self.client.post('/api/webapp/daily',headers={**headers(self.uid),'Origin':'https://untrusted.example'},json={'choice':0})
        self.assertEqual(response.status,403)

    async def test_bad_json_rejected(self):
        response=await self.client.post('/api/webapp/readings',headers=headers(self.uid),json=['wrong'])
        self.assertEqual(response.status,400)

    async def test_old_unsigned_cards_route_removed(self):
        response=await self.client.post('/api/webapp/cards',headers=headers(self.uid+1),json={'user_id':self.uid})
        self.assertEqual(response.status,400)

    async def test_history_preview_is_plain_and_bounded(self):
        await self.client.get('/api/webapp/me', headers=headers(self.uid))
        await Database.execute_query("INSERT INTO max_divinations(user_id,divination_type,question,selected_cards,interpretation,is_free) VALUES($1,'Таро','Тестовый вопрос','[]',$2,true)", self.uid, '<b>Совет</b> ' + 'Полезный шаг. ' * 70)
        response = await self.client.get('/api/webapp/history', headers=headers(self.uid))
        self.assertEqual(response.status, 200)
        items = (await response.json())['items']
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]['preview'].startswith('Совет '))
        self.assertNotIn('<b>', items[0]['preview'])
        self.assertLessEqual(len(items[0]['preview']), 220)

    async def test_chat_picker_requires_pending_question(self):
        response = await self.client.post('/api/webapp/chat-card-readings', headers=headers(self.uid), json={'request_id':str(uuid.uuid4()), 'question':'Что поможет мне сейчас?', 'cards':['01-TheMagician','00-TheFool','02-TheHighPriestess'], 'pending_version':'stale'})
        self.assertEqual(response.status, 409)

    async def test_me_exposes_explicit_chat_selection(self):
        from main.database import save_pending_question
        await self.client.get('/api/webapp/me', headers=headers(self.uid))
        await save_pending_question(self.uid, 'Вопрос из чата')
        response = await self.client.get('/api/webapp/me', headers=headers(self.uid))
        selection = (await response.json())['chat_selection']
        self.assertEqual(selection['question'], 'Вопрос из чата')
        self.assertTrue(selection['version'])
        await Database.execute_query('DELETE FROM max_pending_questions WHERE user_id=$1', self.uid)

    async def test_unowned_reading(self):
        response=await self.client.get('/api/webapp/readings/2147483647',headers=headers(self.uid))
        self.assertEqual(response.status,404)

    async def test_payments_fail_closed(self):
        response=await self.client.post('/api/webapp/payments',headers=headers(self.uid),json={})
        self.assertEqual(response.status,503)

    async def test_secret_files_not_served(self):
        for path in ('/.env','/assets/.env'):
            response=await self.client.get(path)
            self.assertEqual(response.status,404)

    async def test_yookassa_webhook_rejects_get(self):
        response=await self.client.get('/webhook/yookassa')
        self.assertEqual(response.status,405)

    async def test_settings_requires_boolean(self):
        response=await self.client.post('/api/webapp/settings',headers=headers(self.uid),json={'daily_subscribed':'false'})
        self.assertEqual(response.status,400)

    async def test_daily_choice_is_persistent(self):
        first=await self.client.post('/api/webapp/daily',headers=headers(self.uid),json={'choice':0})
        chosen=(await first.json())['card_id']
        second=await self.client.post('/api/webapp/daily',headers=headers(self.uid),json={'choice':1})
        self.assertEqual((await second.json())['card_id'],chosen)

    async def test_payment_create_retry_and_credit_once(self):
        payment_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        payload = {'request_id':request_id,'package':'3_spreads','email':'test@example.com'}
        provider = {'id':payment_id,'test':True,'confirmation':{'confirmation_url':'https://yookassa.ru/test'},
            'metadata':{'user_id':str(self.uid),'package_id':'3_spreads'},
            'amount':{'value':'99.00','currency':'RUB'},'status':'succeeded'}
        with patch.object(config,'yookassa_shop_id',SecretStr('test-shop')), patch.object(config,'yookassa_secret_key',SecretStr('test_secret')), patch('handlers.pay.create_yookassa_payment',AsyncMock(return_value=provider)) as create, patch('handlers.pay.check_payment_status',AsyncMock(return_value=provider)):
            for _ in range(2):
                result=await self.client.post('/api/webapp/payments',headers=headers(self.uid),json=payload)
                self.assertEqual(result.status,200,await result.text())
            self.assertEqual(create.await_count,1)
            for _ in range(2):
                result=await self.client.get('/api/webapp/payments/'+payment_id,headers=headers(self.uid))
                self.assertEqual(result.status,200,await result.text())
            result=await self.client.get('/api/webapp/me',headers=headers(self.uid))
            self.assertEqual((await result.json())['balance']['paid_divinations_remaining'],3)

    async def test_payment_wrong_amount_not_credited(self):
        from main.database import create_payment
        from main.webapp_service import ensure_user
        await ensure_user({'id':self.uid,'first_name':'test'})
        payment_id=str(uuid.uuid4())
        await create_payment(payment_id,self.uid,'3_spreads',9900,99.0,'test@example.com')
        provider={'id':payment_id,'test':True,'metadata':{'user_id':str(self.uid),'package_id':'3_spreads'},'amount':{'value':'1.00','currency':'RUB'},'status':'succeeded'}
        with patch('handlers.pay.check_payment_status',AsyncMock(return_value=provider)):
            result=await self.client.get('/api/webapp/payments/'+payment_id,headers=headers(self.uid))
            self.assertEqual(result.status,502)
        result=await self.client.get('/api/webapp/me',headers=headers(self.uid))
        self.assertEqual((await result.json())['balance']['paid_divinations_remaining'],0)
