"""Integration tests against the isolated local PostgreSQL, never production."""
import asyncio
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.webapp_local import configure
configure(demo=True)
if os.getenv("WEBAPP_UNITTEST_DB") != "max_webapp_unittest":
    raise RuntimeError("Use scripts/test_webapp.py for the isolated test database")
os.environ["DB_NAME"] = "max_webapp_unittest"
from main import webapp_service as service
from main.database import Database, get_user_balance


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.uid = 920000000 + uuid.uuid4().int % 10000000
        await service.initialize()
        await service.ensure_user({'id':self.uid,'first_name':'Integration test'})
        self.payload={'question':'Что поможет в работе?', 'mode':'random'}

    async def asyncTearDown(self):
        # All rows are created by this test user in an isolated database.
        await Database.execute_query('DELETE FROM max_webapp_operations WHERE user_id=$1', self.uid)
        await Database.execute_query('DELETE FROM max_webapp_daily WHERE user_id=$1', self.uid)
        await Database.execute_query('DELETE FROM max_webapp_follow_up_context WHERE user_id=$1', self.uid)
        await Database.execute_query('DELETE FROM max_pending_questions WHERE user_id=$1', self.uid)
        await Database.execute_query('DELETE FROM max_users WHERE user_id=$1', self.uid)
        await Database.close_pool()

    async def complete(self, payload=None, source='webapp'):
        op = await service.submit(self.uid, uuid.uuid4(), payload or self.payload, source=source)
        await service.perform(op['id'])
        op = await service.operation(self.uid,op['id'])
        self.assertEqual(op['status'],'completed',op['error'])
        return await service.reading(self.uid,op['result_id'])

    async def test_reading_and_followup_delivered_to_chat(self):
        from main.botdef import bot
        with patch.dict(os.environ, WEBAPP_DEMO='false'), \
             patch.object(service, 'generate', AsyncMock(return_value='Совет\n\nСделайте первый шаг.')), \
             patch.object(bot, 'send_message', AsyncMock()) as send, \
             patch('handlers.tarot_cards.send_card_images', AsyncMock()) as images:
            order = []
            images.side_effect = lambda *args, **kwargs: order.append('cards')
            send.side_effect = lambda *args, **kwargs: order.append('text')
            reading = await self.complete(source='chat')
            self.assertEqual(order, ['cards', 'text'])
            images.assert_awaited_once()
            self.assertTrue(images.call_args.kwargs['as_media_group'])
            self.assertIn('Ваш расклад', send.call_args.args[0])
            self.assertEqual(send.call_args.kwargs['user_id'], self.uid)
            send.reset_mock()
            await self.complete({'kind':'followup', 'reading_id':reading['id'], 'question':'Какой первый шаг сделать?'}, source='chat')
            send.assert_awaited_once()
            self.assertIn('Уточнение', send.call_args.args[0])

    async def test_webapp_reading_and_followup_do_not_send_to_chat(self):
        from main.botdef import bot
        with patch.dict(os.environ, WEBAPP_DEMO='false'), \
             patch.object(service, 'generate', AsyncMock(return_value='Общее толкование\n\nСделайте первый шаг.')), \
             patch.object(bot, 'send_message', AsyncMock()) as send, \
             patch('handlers.tarot_cards.send_card_images', AsyncMock()) as images:
            reading = await self.complete({**self.payload, 'delivery':'chat', 'source':'chat'})
            result = await self.complete({'kind':'followup', 'reading_id':reading['id'], 'question':'Какой первый шаг сделать?'})
            self.assertEqual(len(result['followups']), 1)
            send.assert_not_awaited()
            images.assert_not_awaited()

    async def test_chat_adapter_followup_stays_on_chat_reading_after_webapp(self):
        from main.botdef import bot
        from handlers.divination import _finish_tarot_reading, _process_follow_up_message
        cursor = MagicMock()
        with patch.dict(os.environ, WEBAPP_DEMO='false'), \
             patch.object(service, 'generate', AsyncMock(return_value='Общее толкование\n\nКраткий ответ.')), \
             patch.object(bot, 'send_message', AsyncMock()) as send, \
             patch('handlers.tarot_cards.send_card_images', AsyncMock()) as images:
            completed = await _finish_tarot_reading(bot=bot, chat_id=self.uid, user_id=self.uid, question=self.payload['question'], card_ids=['01-TheMagician','00-TheFool','02-TheHighPriestess'], cursor=cursor, data={}, method='random')
            self.assertTrue(completed)
            cursor.change_state.assert_called_with('chatting')
            chat_id = (await Database.fetch_one('SELECT id FROM max_divinations WHERE user_id=$1',self.uid))['id']
            webapp = await self.complete()
            self.assertEqual(send.await_count, 1)
            cursor.get_data.return_value = {'divination_id':chat_id}
            message = SimpleNamespace(sender=SimpleNamespace(user_id=self.uid),content='Какой первый шаг сделать?',id='followup-fixture',reply=AsyncMock())
            await _process_follow_up_message(message,cursor)
            self.assertEqual(send.await_count, 2)
            images.assert_awaited_once()
            self.assertEqual(len((await service.reading(self.uid,chat_id))['followups']),1)
            self.assertEqual(len((await service.reading(self.uid,webapp['id']))['followups']),0)

    async def test_callback_allowlist_checks_person_not_bot_message_sender(self):
        from main import botdef
        update = {'update_type':'message_callback', 'message':{'sender':{'user_id':494864527}}, 'callback':{'user':{'user_id':self.uid}, 'payload':'back_to_menu'}}
        with patch.dict(os.environ, WEBAPP_LOCAL='true', WEBAPP_ALLOWED_IDS=str(self.uid)), \
             patch.object(botdef,'_aiomax_handle_update',AsyncMock()) as dispatch, \
             patch('main.reply_updates.capture_reply_update',AsyncMock()):
            await botdef._handle_update_with_reply_context(botdef.bot,update)
            dispatch.assert_awaited_once_with(update)
            dispatch.reset_mock()
            update['message']['sender']['user_id'] = self.uid
            update['callback']['user']['user_id'] = self.uid + 1
            await botdef._handle_update_with_reply_context(botdef.bot,update)
            dispatch.assert_not_awaited()

    async def test_back_to_menu_after_reading_resets_context_and_sends_keyboard(self):
        from main.botdef import bot
        from handlers.common import handle_back_to_menu
        reading = await self.complete(source='chat')
        cursor = MagicMock()
        callback = SimpleNamespace(user=SimpleNamespace(user_id=self.uid),send=AsyncMock())
        await handle_back_to_menu(callback,cursor)
        cursor.clear.assert_called_once()
        callback.send.assert_awaited_once()
        self.assertIn('Выбери действие', callback.send.call_args.args[0])
        self.assertIsNotNone(callback.send.call_args.kwargs['keyboard'])
        self.assertIsNone(await Database.fetch_one('SELECT divination_id FROM max_webapp_follow_up_context WHERE user_id=$1',self.uid))

    async def test_opening_app_does_not_clear_chat_state(self):
        from handlers.common import open_webapp_button
        from main.botdef import bot
        cursor = MagicMock()
        message = SimpleNamespace(reply=AsyncMock())
        with patch.object(bot,'get_me',AsyncMock(return_value=SimpleNamespace(username='test_bot',user_id=123))):
            await open_webapp_button(message,cursor)
        cursor.clear.assert_not_called()
        message.reply.assert_awaited_once()

    async def test_webapp_keeps_chat_context_and_pending_question(self):
        from main.database import save_pending_question, get_pending_question
        chat = await self.complete(source='chat')
        await save_pending_question(self.uid, self.payload['question'])
        await self.complete()
        context = await Database.fetch_one('SELECT divination_id FROM max_webapp_follow_up_context WHERE user_id=$1', self.uid)
        self.assertEqual(context['divination_id'], chat['id'])
        self.assertEqual(await get_pending_question(self.uid), self.payload['question'])

    async def picker_payload(self):
        from main.database import save_pending_question
        await save_pending_question(self.uid, self.payload['question'])
        row = await Database.fetch_one('SELECT created_at FROM max_pending_questions WHERE user_id=$1', self.uid)
        return {**self.payload, 'mode':'manual', 'cards':['01-TheMagician','00-TheFool','02-TheHighPriestess'], 'pending_version':row['created_at'].isoformat()}

    async def test_hybrid_selection_one_debit_and_chat_context(self):
        payload = await self.picker_payload()
        key = uuid.uuid4()
        op = await service.submit(self.uid, key, payload, source='chat-picker')
        await service.perform(op['id'])
        repeated = await service.submit(self.uid, key, payload, source='chat-picker')
        self.assertEqual(repeated['status'], 'completed')
        self.assertEqual((await get_user_balance(self.uid))['free_divinations_remaining'], 2)
        context = await Database.fetch_one('SELECT divination_id FROM max_webapp_follow_up_context WHERE user_id=$1', self.uid)
        self.assertEqual(context['divination_id'], repeated['result_id'])
        self.assertEqual(service.decode(repeated['payload'])['delivery'], 'chat')

    async def test_stale_hybrid_selection_is_rejected(self):
        from main.database import save_pending_question
        payload = await self.picker_payload()
        await save_pending_question(self.uid, payload['question'])
        with self.assertRaises(service.ServiceError):
            await service.submit(self.uid, uuid.uuid4(), payload, source='chat-picker')

    async def test_changed_chat_question_cancels_queued_picker_without_debit(self):
        from main.database import save_pending_question
        payload = await self.picker_payload()
        op = await service.submit(self.uid, uuid.uuid4(), payload, source='chat-picker')
        await save_pending_question(self.uid, 'Новый вопрос из другого телефона')
        await service.perform(op['id'])
        self.assertEqual((await service.operation(self.uid,op['id']))['status'], 'failed')
        self.assertEqual((await get_user_balance(self.uid))['free_divinations_remaining'], 3)

    async def test_concurrent_repeat_one_debit(self):
        key=uuid.uuid4()
        a,b=await asyncio.gather(service.submit(self.uid,key,self.payload),service.submit(self.uid,key,self.payload))
        self.assertEqual(a['id'],b['id'])
        await asyncio.gather(service.perform(a['id']),service.perform(b['id']))
        self.assertEqual((await get_user_balance(self.uid))['free_divinations_remaining'],2)
        again=await service.submit(self.uid,key,self.payload)
        self.assertEqual(again['status'],'completed')

    async def test_conflicting_idempotency_key(self):
        key=uuid.uuid4();await service.submit(self.uid,key,self.payload)
        with self.assertRaises(service.ServiceError):
            await service.submit(self.uid,key,{'question':'Другой вопрос'})

    async def test_parallel_distinct_request_blocked(self):
        await service.submit(self.uid,uuid.uuid4(),self.payload)
        with self.assertRaises(service.ServiceError):
            await service.submit(self.uid,uuid.uuid4(),self.payload)

    async def test_llm_failure_no_debit_or_history(self):
        op=await service.submit(self.uid,uuid.uuid4(),self.payload)
        with patch.object(service,'generate',AsyncMock(side_effect=RuntimeError('provider unavailable'))):
            await service.perform(op['id'])
        self.assertEqual((await service.operation(self.uid,op['id']))['status'],'failed')
        self.assertEqual((await get_user_balance(self.uid))['free_divinations_remaining'],3)
        self.assertFalse(await Database.fetch_all('SELECT id FROM max_divinations WHERE user_id=$1',self.uid))

    async def test_cancelled_operation_resumes(self):
        op=await service.submit(self.uid,uuid.uuid4(),self.payload)
        with patch.object(service,'generate',AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):await service.perform(op['id'])
        self.assertEqual((await service.operation(self.uid,op['id']))['status'],'queued')
        self.assertEqual((await get_user_balance(self.uid))['free_divinations_remaining'],3)
        await service.perform(op['id'])
        self.assertEqual((await service.operation(self.uid,op['id']))['status'],'completed')

    async def test_insufficient_balance(self):
        await Database.execute_query('UPDATE max_user_balances SET free_divinations_remaining=0 WHERE user_id=$1',self.uid)
        op=await service.submit(self.uid,uuid.uuid4(),self.payload)
        await service.perform(op['id'])
        self.assertEqual((await service.operation(self.uid,op['id']))['status'],'failed')

    async def test_unlimited_does_not_consume_free(self):
        await Database.execute_query('UPDATE max_user_balances SET unlimited_until=$2 WHERE user_id=$1',self.uid,datetime.now()+timedelta(days=1))
        result=await self.complete()
        self.assertFalse(result['is_free'])
        self.assertEqual(result['remaining'],5)
        self.assertEqual((await get_user_balance(self.uid))['free_divinations_remaining'],3)

    async def test_followups_accumulate_and_limit(self):
        result=await self.complete()
        for text in ('Что делать дальше?', 'На что обратить внимание?'):
            value=await self.complete({'kind':'followup','reading_id':result['id'],'question':text})
        self.assertEqual(len(value['followups']),2)
        self.assertEqual(value['remaining'],0)
        op=await service.submit(self.uid,uuid.uuid4(),{'kind':'followup','reading_id':result['id'],'question':'Ещё один вопрос?'})
        await service.perform(op['id'])
        self.assertEqual((await service.operation(self.uid,op['id']))['status'],'failed')
        self.assertEqual((await get_user_balance(self.uid))['free_divinations_remaining'],2)

    async def test_other_user_reading_not_visible(self):
        result=await self.complete()
        with self.assertRaises(service.ServiceError):await service.reading(self.uid+1,result['id'])

    async def test_daily_shared_chat_and_webapp(self):
        chosen=await service.daily(self.uid,0)
        same=await service.daily(self.uid,card_id='00-TheFool')
        self.assertEqual(chosen['card_id'],same['card_id'])
        self.assertEqual((await get_user_balance(self.uid))['free_divinations_remaining'],3)

    async def test_iching(self):
        from handlers.hexagrams import get_all_available_hexagrams
        result=await self.complete({'question':'Как поступить в этой ситуации?', 'kind':'iching'})
        self.assertEqual(result['divination_type'],'Ицзин')
        self.assertEqual(len(result['selected_cards']),1)
        self.assertIn(result['selected_cards'][0], get_all_available_hexagrams())

    async def test_duplicate_or_unknown_cards(self):
        for cards in (['00-TheFool']*3, ['missing','00-TheFool','01-TheMagician']):
            with self.assertRaises(service.ServiceError):await service.submit(self.uid,uuid.uuid4(),{'question':'Что делать?', 'mode':'own','cards':cards})

    async def test_generation_uses_actual_headings_for_all_schemas(self):
        from handlers.tarot_cards import get_card_info
        ids=['01-TheMagician','00-TheFool','02-TheHighPriestess']
        for theme, positions in service.THEMES.items():
            with patch.dict(os.environ, WEBAPP_DEMO='false'), patch('main.llm_divination.call_deepseek', AsyncMock(return_value='Ответ')) as llm:
                await service.generate({'kind':'tarot','question':'Что поможет мне сейчас?','theme':theme}, ids)
                system=llm.call_args.args[1]
                for position, cid in zip(positions, ids):
                    self.assertIn(f"{position}: {get_card_info(cid)['name']}", system)
                self.assertNotIn('Позиция: Название карты', system)

    async def test_schema_and_selected_order(self):
        ids=['01-TheMagician','00-TheFool','02-TheHighPriestess']
        result=await self.complete({'question':'Как мне сделать выбор?', 'mode':'own','cards':ids,'theme':'choice'})
        self.assertEqual(result['selected_cards'],ids)
        self.assertEqual(result['positions'],service.THEMES['choice'])
