import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers import common, divination, feedback, message_router, pay
from main.message_routing import NAVIGATION_MESSAGES


class FakeCursor:
    def __init__(self, state=None, data=None):
        self.state = state
        self.data = data

    def get_state(self):
        return self.state

    def get_data(self):
        return self.data

    def change_state(self, state):
        self.state = state

    def change_data(self, data):
        self.data = data

    def clear(self):
        self.state = None
        self.data = None


def make_message(text, *, message_id="message-1", user_id=42):
    message = SimpleNamespace(
        content=text,
        id=message_id,
        sender=SimpleNamespace(user_id=user_id, name="Test", username="test"),
        recipient=SimpleNamespace(chat_id=100),
    )
    message.reply = AsyncMock()
    return message


class MessageRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        message_router.reset_routing_cache()

    def test_only_one_text_handler_is_registered(self):
        self.assertEqual(len(message_router.router._handlers["message_created"]), 1)
        self.assertEqual(common.router._handlers["message_created"], [])
        self.assertEqual(feedback.router._handlers["message_created"], [])
        self.assertEqual(pay.router._handlers["message_created"], [])
        self.assertEqual(divination.router._handlers["message_created"], [])

    def test_every_navigation_intent_has_exactly_one_handler(self):
        self.assertEqual(set(message_router.NAVIGATION_HANDLERS), set(NAVIGATION_MESSAGES))

    async def test_new_reading_wins_over_chatting_state(self):
        message = make_message("Новый расклад 🃏")
        cursor = FakeCursor(
            divination.STATE_CHATTING,
            {"follow_up_count": 1, "conversation_history": []},
        )
        navigation = AsyncMock()
        follow_up = AsyncMock()

        with patch.dict(
            message_router.NAVIGATION_HANDLERS,
            {"Новый расклад 🃏": navigation},
        ), patch.dict(
            message_router.STATE_HANDLERS,
            {divination.STATE_CHATTING: follow_up},
        ):
            await message_router.route_text_message(message, cursor)

        navigation.assert_awaited_once_with(message, cursor)
        follow_up.assert_not_awaited()

    async def test_duplicate_message_id_is_processed_once(self):
        handler = AsyncMock()
        cursor = FakeCursor(divination.STATE_CHATTING)
        first = make_message("Что значит карта?", message_id="same-id")
        duplicate = make_message("Что значит карта?", message_id="same-id")

        with patch.dict(
            message_router.STATE_HANDLERS,
            {divination.STATE_CHATTING: handler},
        ):
            await message_router.route_text_message(first, cursor)
            await message_router.route_text_message(duplicate, cursor)

        handler.assert_awaited_once_with(first, cursor)

    async def test_messages_for_same_user_are_processed_in_order(self):
        entered_first = asyncio.Event()
        release_first = asyncio.Event()
        calls = []
        cursor = FakeCursor("serial-test")

        async def handler(message, _cursor):
            calls.append(f"start:{message.id}")
            if message.id == "first":
                entered_first.set()
                await release_first.wait()
            calls.append(f"end:{message.id}")

        with patch.dict(message_router.STATE_HANDLERS, {"serial-test": handler}):
            first_task = asyncio.create_task(
                message_router.route_text_message(
                    make_message("первое", message_id="first"), cursor
                )
            )
            await entered_first.wait()
            second_task = asyncio.create_task(
                message_router.route_text_message(
                    make_message("второе", message_id="second"), cursor
                )
            )
            await asyncio.sleep(0)
            self.assertEqual(calls, ["start:first"])
            release_first.set()
            await asyncio.gather(first_task, second_task)

        self.assertEqual(
            calls,
            ["start:first", "end:first", "start:second", "end:second"],
        )

    async def test_new_reading_clears_webapp_context_and_waits_for_question(self):
        message = make_message("Новый расклад 🃏")
        cursor = FakeCursor(divination.STATE_CHATTING, {"follow_up_count": 1})

        with patch.object(
            common, "get_and_delete_webapp_follow_up_context", AsyncMock(return_value={})
        ) as clear_webapp, patch.object(
            common, "can_user_divinate", AsyncMock(return_value=(True, "free"))
        ):
            await common.new_divination_button(message, cursor)

        clear_webapp.assert_awaited_once_with(42)
        self.assertEqual(cursor.state, divination.STATE_WAITING_FOR_NEW_QUESTION)
        self.assertIsNone(cursor.data)
        message.reply.assert_awaited_once()

    async def test_question_after_new_reading_starts_fresh_flow(self):
        message = make_message("Что меня ждёт в работе?")
        cursor = FakeCursor(divination.STATE_WAITING_FOR_NEW_QUESTION)

        with patch(
            "handlers.common.check_channel_subscription",
            AsyncMock(return_value=True),
        ):
            await divination.handle_new_divination_question(message, cursor)

        self.assertEqual(cursor.state, divination.STATE_CHOOSING_DIVINATION)
        self.assertEqual(cursor.data, {"question": "Что меня ждёт в работе?"})
        message.reply.assert_awaited_once()

    async def test_navigation_label_never_reaches_follow_up_llm(self):
        message = make_message("Новый расклад 🃏")
        cursor = FakeCursor(
            divination.STATE_CHATTING,
            {"follow_up_count": 1, "conversation_history": []},
        )

        with patch.object(
            divination,
            "get_chatgpt_response_with_history",
            AsyncMock(),
        ) as llm:
            await divination.handle_follow_up(message, cursor)

        llm.assert_not_awaited()
        message.reply.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
