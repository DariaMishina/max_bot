import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from main import database
from main import inactivity_nudges


class FreeNudgeSkipAheadTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 20, 21, 30, tzinfo=timezone.utc)

    def test_picks_highest_overdue_stage(self):
        stage = database.pick_highest_due_free_nudge_stage(
            'c2',
            self.now - timedelta(hours=49),
            {'3h': self.now, '12h': None, '24h': None, '48h': None},
            now=self.now,
        )

        self.assertEqual(stage, '48h')

    def test_does_not_catch_up_junior_after_senior_was_sent(self):
        stage = database.pick_highest_due_free_nudge_stage(
            'c2',
            self.now - timedelta(hours=49),
            {'3h': None, '12h': None, '24h': None, '48h': self.now},
            now=self.now,
        )

        self.assertIsNone(stage)

    def test_returns_next_real_stage_when_it_becomes_due(self):
        stage = database.pick_highest_due_free_nudge_stage(
            'c2',
            self.now - timedelta(hours=13),
            {'3h': self.now - timedelta(hours=10), '12h': None, '24h': None, '48h': None},
            now=self.now,
        )

        self.assertEqual(stage, '12h')

    def test_stages_up_to_selected_stage(self):
        self.assertEqual(
            database.free_nudge_stages_up_to('c2', '24h'),
            ('3h', '12h', '24h'),
        )


class FreeNudgePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_marking_stage_atomically_marks_all_junior_stages(self):
        with patch.object(database, 'ensure_users_nudge_columns', AsyncMock()), patch.object(
            database.Database, 'execute_query', AsyncMock()
        ) as execute:
            result = await database.mark_free_nudge_sent(42, 'c2', '24h')

        self.assertTrue(result)
        query = execute.await_args.args[0]
        self.assertIn('free_nudge_c2_3h_sent_at = COALESCE', query)
        self.assertIn('free_nudge_c2_12h_sent_at = COALESCE', query)
        self.assertIn('free_nudge_c2_24h_sent_at = COALESCE', query)
        self.assertNotIn('free_nudge_c2_48h_sent_at', query)
        self.assertEqual(execute.await_args.args[1], 42)

    async def test_due_query_has_payment_priority_and_cooldowns(self):
        with patch.object(database, 'ensure_users_nudge_columns', AsyncMock()), patch.object(
            database, 'ensure_payments_reminder_columns', AsyncMock()
        ), patch.object(database.Database, 'fetch_all', AsyncMock(return_value=[])) as fetch:
            result = await database.get_users_due_for_free_nudges('c2')

        self.assertEqual(result, [])
        query = fetch.await_args.args[0]
        self.assertIn('p.reminder_48h_sent_at IS NULL', query)
        self.assertIn("INTERVAL '12 hours'", query)
        self.assertIn("INTERVAL '1 hours'", query)


class FreeNudgeJobTests(unittest.IsolatedAsyncioTestCase):
    async def test_job_sends_only_selected_skip_ahead_stage(self):
        async def due_for_category(category):
            if category == 'c2':
                return [{'user_id': 42, 'category': 'c2', 'stage': '48h'}]
            return []

        with patch.object(inactivity_nudges, 'is_in_broadcast_window', return_value=False), patch.object(
            inactivity_nudges,
            'get_users_due_for_free_nudges',
            AsyncMock(side_effect=due_for_category),
        ), patch.object(
            inactivity_nudges,
            'send_free_user_nudge',
            AsyncMock(return_value=(True, False)),
        ) as send, patch.object(
            inactivity_nudges,
            'mark_free_nudge_sent',
            AsyncMock(return_value=True),
        ) as mark, patch.object(inactivity_nudges.asyncio, 'sleep', AsyncMock()):
            result = await inactivity_nudges.process_inactivity_nudges()

        send.assert_awaited_once_with(42, category='c2', stage='48h')
        mark.assert_awaited_once_with(42, 'c2', '48h')
        self.assertEqual(result['sent'], 1)
        self.assertEqual(result['by_type']['c2_48h']['sent'], 1)
        self.assertEqual(result['by_type']['c2_12h']['sent'], 0)
        self.assertEqual(result['by_type']['c2_24h']['sent'], 0)


if __name__ == '__main__':
    unittest.main()
