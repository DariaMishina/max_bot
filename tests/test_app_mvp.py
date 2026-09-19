"""MVP API regression tests. No real database, LLM, messages or payments.
Run: venv/bin/python -m unittest discover -s tests -v
"""
import json
import os
import unittest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Every required credential is synthetic, even when a developer has a real .env.
for key, value in {
    "APP_DB_USER": "test", "APP_DB_PASSWORD": "test", "APP_JWT_SECRET": "test-only",
    "API_KEY": "test", "BOT_TOKEN": "test", "DB_HOST": "localhost", "DB_PORT": "5432",
    "DB_NAME": "unused_test", "DB_USER": "test", "DB_PASSWORD": "test",
}.items():
    os.environ[key] = value

import app_api_server as api
from app import divination_service as service

USER = uuid.uuid4()
CARDS = ["00-TheFool", "16-TheTower", "Cups01"]


def request(body=None, path="/v1/divinations/tarot", method="POST"):
    req = MagicMock()
    req.body_exists = True
    req.json = AsyncMock(return_value=body)
    req.__getitem__.side_effect = lambda key: USER if key == "app_user_id" else None
    req.get.side_effect = lambda key: USER if key == "app_user_id" else None
    req.match_info = {"id": "12"}
    req.query = {}
    req.path = path
    req.method = method
    req.scheme = "https"
    req.host = "example.test"
    req.headers = {}
    return req


def payload(response):
    return json.loads(response.text)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_object_json_and_invalid_selection(self):
        response = await api.tarot_handler(request(["invalid"]))
        self.assertEqual(response.status, 400)
        response = await api.tarot_handler(request({"question": "Q", "selection": "unknown"}))
        self.assertEqual(response.status, 400)

    async def test_no_balance_has_machine_readable_paywall(self):
        with patch.object(api, "run_tarot", AsyncMock(side_effect=service.DivinationError("no_balance", "Закончились расклады"))):
            response = await api.tarot_handler(request({"question": "Q", "selection": "random"}))
        self.assertEqual(response.status, 402)
        self.assertEqual(payload(response)["error"], "no_balance")

    async def test_last_free_reading_still_returns_result(self):
        result = service.TarotResult(12, "Q", CARDS, "Текст", True, {"free_divinations_remaining": 0, "paid_divinations_remaining": 0})
        with patch.object(api, "run_tarot", AsyncMock(return_value=result)), patch.object(api, "get_divination", AsyncMock(return_value={"follow_ups": [], "created_at": datetime.now()})):
            response = await api.tarot_handler(request({"question": "Q", "selection": "random"}))
        data = payload(response)
        self.assertEqual(response.status, 200)
        self.assertTrue(data["paywall"])
        self.assertEqual(len(data["cards"]), 3)
        self.assertEqual(data["follow_ups_remaining"], 2)
        self.assertEqual(data["interpretation"], "Текст")

    async def test_detail_is_scoped_to_authenticated_guest(self):
        get = AsyncMock(return_value=None)
        with patch.object(api, "get_divination", get):
            response = await api.divination_detail_handler(request())
        get.assert_awaited_once_with(12, USER)
        self.assertEqual(response.status, 404)

    async def test_deck_contains_nine_distinct_known_cards(self):
        cards = payload(await api.tarot_deck_handler(request()))["cards"]
        self.assertEqual(len({card["id"] for card in cards}), 9)
        self.assertTrue(all(card["name"] for card in cards))

    async def test_history_pagination_and_bad_cursor(self):
        req = request()
        req.query = {"limit": "2", "before_id": "100"}
        rows = [{"id": 9}, {"id": 8}, {"id": 7}]
        with patch.object(api, "list_divinations", AsyncMock(return_value=rows)) as listing:
            data = payload(await api.me_history_handler(req))
        listing.assert_awaited_once_with(USER, limit=3, before_id=100)
        self.assertEqual(data, {"items": rows[:2], "next_before_id": 8})
        req.query = {"limit": "oops"}
        self.assertEqual((await api.me_history_handler(req)).status, 400)

    async def test_feedback_validation_and_persistence(self):
        with patch.object(api, "save_feedback", AsyncMock()) as save:
            for message in (" ", "x" * 2001, 7):
                self.assertEqual((await api.feedback_handler(request({"message": message}))).status, 400)
            save.assert_not_awaited()
            self.assertEqual((await api.feedback_handler(request({"message": "  Спасибо  "}))).status, 200)
            save.assert_awaited_once_with(USER, "Спасибо")

    async def test_delete_only_authenticated_guest_and_is_repeatable(self):
        with patch.object(api, "delete_user", AsyncMock()) as delete:
            for _ in range(2):
                self.assertEqual((await api.delete_me_handler(request())).status, 200)
            self.assertEqual(delete.await_count, 2)
            delete.assert_awaited_with(USER)

    async def test_deleted_guest_token_cannot_read_data(self):
        req = request()
        req.headers = {"Authorization": "Bearer old-token"}
        handler = AsyncMock()
        with patch.object(api, "verify_access_token", return_value=USER), patch.object(api, "get_user", AsyncMock(return_value=None)):
            response = await api.auth_middleware(req, handler)
        self.assertEqual(response.status, 401)
        handler.assert_not_awaited()

    async def test_follow_up_requires_request_id_and_maps_limit(self):
        response = await api.follow_up_handler(request({"question": "Q"}))
        self.assertEqual(response.status, 400)
        with patch.object(api, "run_follow_up", AsyncMock(side_effect=service.DivinationError("follow_up_limit", "Лимит"))):
            response = await api.follow_up_handler(request({"question": "Q", "request_id": str(uuid.uuid4())}))
        self.assertEqual(response.status, 409)
        self.assertEqual(payload(response)["error"], "follow_up_limit")


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def connection(self):
        conn = MagicMock()
        conn.fetchval = AsyncMock(return_value=USER)
        conn.fetchrow = AsyncMock()
        conn.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        conn.transaction.return_value.__aenter__ = AsyncMock()
        conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
        return conn, patch.object(service.AppDatabase, "get_pool", AsyncMock(return_value=pool))

    async def test_duplicate_cards_and_empty_question_are_rejected_before_llm(self):
        with patch.object(service, "interpret_tarot_with_llm", AsyncMock()) as llm:
            for question, cards in [(" ", CARDS), ("Q", [CARDS[0]] * 3), ("Q" * 1001, CARDS)]:
                with self.assertRaises(service.DivinationError):
                    await service.run_tarot(USER, question, card_ids=cards)
            llm.assert_not_awaited()

    async def test_retry_returns_existing_reading_without_llm_or_deduction(self):
        conn, pool = self.connection()
        balance = {"free_divinations_remaining": 0}
        previous = {"id": 12, "question": "Q", "selected_cards": json.dumps(CARDS), "interpretation": "Text", "is_free": True}
        conn.fetchrow.side_effect = [balance, previous]
        with pool, patch.object(service, "interpret_tarot_with_llm", AsyncMock()) as llm:
            result = await service.run_tarot(USER, "Q", random_cards=True, request_id=uuid.uuid4())
        self.assertEqual(result.divination_id, 12)
        conn.execute.assert_not_awaited()
        llm.assert_not_awaited()

    async def test_llm_failure_does_not_save_or_charge(self):
        conn, pool = self.connection()
        conn.fetchrow.return_value = {"unlimited_until": None, "free_divinations_remaining": 3, "paid_divinations_remaining": 0}
        with pool, patch.object(service, "interpret_tarot_with_llm", AsyncMock(side_effect=RuntimeError("LLM down"))):
            with self.assertRaises(RuntimeError):
                await service.run_tarot(USER, "Q", card_ids=CARDS)
        conn.execute.assert_not_awaited()
        self.assertEqual(conn.fetchval.await_count, 1)  # guest lock only; no INSERT
        self.assertEqual(conn.fetchrow.await_count, 1)  # balance read only; no UPDATE
        self.assertIs(conn.transaction.return_value.__aexit__.call_args.args[0], RuntimeError)

    async def test_successful_free_reading_saves_then_decrements_one(self):
        conn, pool = self.connection()
        before = {"unlimited_until": None, "free_divinations_remaining": 3, "paid_divinations_remaining": 0}
        after = {**before, "free_divinations_remaining": 2}
        conn.fetchrow.side_effect = [before, after]
        conn.fetchval.side_effect = [USER, 12]
        with pool, patch.object(service, "interpret_tarot_with_llm", AsyncMock(return_value="Text")):
            result = await service.run_tarot(USER, "Q", card_ids=CARDS)
        self.assertTrue(result.is_free)
        self.assertEqual(result.balance_after["free_divinations_remaining"], 2)
        self.assertEqual(conn.fetchrow.call_args.args[1:], (USER, 1, 0))
        self.assertIsNone(conn.transaction.return_value.__aexit__.call_args.args[0])

    async def test_failed_insert_never_deducts_balance(self):
        conn, pool = self.connection()
        conn.fetchrow.return_value = {"unlimited_until": None, "free_divinations_remaining": 3, "paid_divinations_remaining": 0}
        conn.fetchval.side_effect = [USER, RuntimeError("write failed")]
        with pool, patch.object(service, "interpret_tarot_with_llm", AsyncMock(return_value="Text")):
            with self.assertRaises(RuntimeError):
                await service.run_tarot(USER, "Q", card_ids=CARDS)
        self.assertEqual(conn.fetchrow.await_count, 1)
        conn.execute.assert_not_awaited()
        self.assertIs(conn.transaction.return_value.__aexit__.call_args.args[0], RuntimeError)

    async def test_follow_up_failure_keeps_existing_transcript(self):
        conn, pool = self.connection()
        conn.fetchrow.return_value = {"is_free": True, "follow_ups": "[]", "question": "Q", "selected_cards": CARDS, "interpretation": "Text"}
        with pool, patch.object(service, "call_deepseek", AsyncMock(side_effect=RuntimeError("LLM down"))):
            with self.assertRaises(RuntimeError):
                await service.run_follow_up(USER, 12, "Q2", uuid.uuid4())
        conn.execute.assert_not_awaited()

    async def test_follow_up_limit_and_idempotent_last_retry(self):
        conn, pool = self.connection()
        request_id = uuid.uuid4()
        history = [{"question": "Q", "answer": "A", "request_id": str(uuid.uuid4())},
                   {"question": "Q2", "answer": "A2", "request_id": str(request_id)}]
        conn.fetchrow.return_value = {"is_free": True, "follow_ups": json.dumps(history)}
        with pool, patch.object(service, "call_deepseek", AsyncMock()) as llm:
            result = await service.run_follow_up(USER, 12, "Q2", request_id)
            self.assertEqual(result["follow_ups_remaining"], 0)
            with self.assertRaises(service.DivinationError) as error:
                await service.run_follow_up(USER, 12, "Q3", uuid.uuid4())
            self.assertEqual(error.exception.code, "follow_up_limit")
        conn.execute.assert_not_awaited()
        llm.assert_not_awaited()

    async def test_follow_up_does_not_reveal_another_guests_reading(self):
        conn, pool = self.connection()
        conn.fetchrow.return_value = None
        with pool, patch.object(service, "call_deepseek", AsyncMock()) as llm:
            with self.assertRaises(service.DivinationError) as error:
                await service.run_follow_up(USER, 12, "Q", uuid.uuid4())
            self.assertEqual(error.exception.code, "not_found")
        self.assertEqual(conn.fetchrow.call_args.args[1:], (12, USER))
        llm.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
