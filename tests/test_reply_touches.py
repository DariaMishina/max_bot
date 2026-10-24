import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from main import outbound_messages, reply_updates
import send_message as send_message_module
from main.outbound_messages import ReplyTarget
from main.send_errors import (
    is_invalid_reply_error,
    is_profile_limited_error,
    is_transient_send_error,
    is_unreachable_user_error,
)


class ReplySelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_message_has_priority_for_inactivity(self):
        context = {
            "last_user_message_id": "user-mid",
            "last_callback_message_id": "callback-mid",
            "last_bot_message_id": "bot-mid",
        }
        with patch.object(
            outbound_messages, "get_reply_context", AsyncMock(return_value=context)
        ):
            target = await outbound_messages.choose_reply_target(42, "paid_inactivity")
        self.assertEqual(target, ReplyTarget("user-mid", "user_message"))

    async def test_payment_explicit_context_has_priority(self):
        with patch.object(
            outbound_messages, "get_reply_context", AsyncMock(return_value={})
        ) as get_context:
            target = await outbound_messages.choose_reply_target(
                42, "payment_reminder", "payment-mid", "callback_message"
            )
        self.assertEqual(target, ReplyTarget("payment-mid", "callback_message"))
        get_context.assert_not_awaited()


class BackgroundSendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        outbound_messages.reset_profile_circuit()

    async def test_send_uses_reply_to_and_records_outbound_id(self):
        sent = SimpleNamespace(id="out-mid", recipient=SimpleNamespace(chat_id=777))
        with (
            patch.object(
                outbound_messages, "choose_reply_target",
                AsyncMock(return_value=ReplyTarget("in-mid", "user_message")),
            ),
            patch.object(outbound_messages.bot, "send_message", AsyncMock(return_value=sent)) as send,
            patch.object(outbound_messages, "save_bot_reply_message", AsyncMock()) as save_bot,
            patch.object(outbound_messages, "log_outbound_delivery", AsyncMock()),
        ):
            result = await outbound_messages.send_background_message(
                42, "hello", touch_type="manual"
            )
        self.assertEqual(result, (True, False))
        self.assertEqual(send.await_args.kwargs["reply_to"], "in-mid")
        save_bot.assert_awaited_once()

    async def test_invalid_reply_is_invalidated_and_retried_once(self):
        sent = SimpleNamespace(id="out-mid", recipient=SimpleNamespace(chat_id=777))
        with (
            patch.object(
                outbound_messages, "choose_reply_target",
                AsyncMock(side_effect=[
                    ReplyTarget("bad-mid", "user_message"),
                    ReplyTarget("fallback-mid", "callback_message"),
                ]),
            ),
            patch.object(
                outbound_messages.bot, "send_message",
                AsyncMock(side_effect=[RuntimeError("message not found"), sent]),
            ) as send,
            patch.object(outbound_messages, "invalidate_reply_message", AsyncMock()) as invalidate,
            patch.object(outbound_messages, "save_bot_reply_message", AsyncMock()),
            patch.object(outbound_messages, "log_outbound_delivery", AsyncMock()),
        ):
            result = await outbound_messages.send_background_message(
                42, "hello", touch_type="manual"
            )
        self.assertEqual(result, (True, False))
        self.assertEqual(send.await_count, 2)
        invalidate.assert_awaited_once_with(42, "bad-mid")
        self.assertEqual(send.await_args_list[1].kwargs["reply_to"], "fallback-mid")

    async def test_profile_limit_opens_circuit_and_does_not_block_user(self):
        with (
            patch.object(
                outbound_messages, "choose_reply_target",
                AsyncMock(return_value=ReplyTarget("mid", "user_message")),
            ),
            patch.object(
                outbound_messages.bot, "send_message",
                AsyncMock(side_effect=RuntimeError("Can't start chat. Profile is limited")),
            ) as send,
            patch.object(outbound_messages, "mark_user_unreachable", AsyncMock()) as mark_user,
            patch.object(outbound_messages, "log_outbound_delivery", AsyncMock()),
        ):
            first = await outbound_messages.send_background_message(
                42, "hello", touch_type="paid_inactivity"
            )
            second = await outbound_messages.send_background_message(
                43, "hello", touch_type="paid_inactivity"
            )
        self.assertEqual(first, (False, False))
        self.assertEqual(second, (False, False))
        self.assertEqual(send.await_count, 1)
        mark_user.assert_not_awaited()

    async def test_message_pair_pins_missing_context_for_both_messages(self):
        with (
            patch.object(
                send_message_module, "choose_reply_target",
                AsyncMock(return_value=ReplyTarget(None, "no_context")),
            ),
            patch.object(
                send_message_module, "send_message_to_user",
                AsyncMock(side_effect=[(True, False), (True, False)]),
            ) as send,
        ):
            result = await send_message_module._send_message_pair(
                42, "one", "two", touch_type="expired_access"
            )
        self.assertEqual(result, (True, False))
        self.assertEqual(send.await_count, 2)
        for call in send.await_args_list:
            self.assertTrue(call.kwargs["reply_target_resolved"])
            self.assertIsNone(call.kwargs["explicit_reply_message_id"])


class UpdateCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_callback_message_is_saved(self):
        update = {
            "update_type": "message_callback",
            "timestamp": 1_700_000_000_000,
            "callback": {
                "timestamp": 1_700_000_000_000,
                "user": {"user_id": 42},
            },
            "message": {
                "recipient": {"chat_id": 777},
                "body": {"mid": "button-mid"},
            },
        }
        with patch.object(
            reply_updates, "save_callback_reply_message", AsyncMock()
        ) as save:
            await reply_updates.capture_reply_update(update)
        save.assert_awaited_once()
        self.assertEqual(save.await_args.args[:3], (42, 777, "button-mid"))


class ErrorClassificationTests(unittest.TestCase):
    def test_profile_limit_is_not_user_unreachable(self):
        error = RuntimeError("Can't start chat. Profile is limited")
        self.assertTrue(is_profile_limited_error(error))
        self.assertFalse(is_unreachable_user_error(error))

    def test_missing_reply_is_classified(self):
        self.assertTrue(is_invalid_reply_error(RuntimeError("message not found")))

    def test_api_503_is_transient_but_timeout_is_not_immediately_retried(self):
        self.assertTrue(is_transient_send_error(RuntimeError("HTTP 503 service unavailable")))
        self.assertFalse(is_transient_send_error(TimeoutError("request timed out")))


if __name__ == "__main__":
    unittest.main()
