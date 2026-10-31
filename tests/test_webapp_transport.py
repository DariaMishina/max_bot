from pathlib import Path
import tempfile
import unittest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from main.webapp_transport import switch_to_polling


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.entries = []
        self.deleted = []
        self.refuse = False
        self.bad_response = False
        app = web.Application()
        async def get(request):
            return web.json_response({} if self.bad_response else {'subscriptions':self.entries})
        async def delete(request):
            url = request.query['url']
            self.deleted.append(url)
            if not self.refuse:
                self.entries = [item for item in self.entries if item['url'] != url]
            return web.json_response({'success':not self.refuse})
        app.router.add_get('/subscriptions', get)
        app.router.add_delete('/subscriptions', delete)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.temp = tempfile.TemporaryDirectory()
        self.backup = Path(self.temp.name) / 'subscriptions.json'

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    async def test_no_webhook_needs_no_changes(self):
        self.assertEqual(await switch_to_polling(self.client,self.backup), 0)
        self.assertFalse(self.backup.exists())
        self.assertEqual(self.deleted, [])

    async def test_old_webhook_is_backed_up_and_removed(self):
        self.entries = [{'url':'https://old-tunnel.example/webhook/max','update_types':['message_created']}]
        self.assertEqual(await switch_to_polling(self.client,self.backup), 1)
        self.assertIn('old-tunnel.example', self.backup.read_text())
        self.assertEqual(self.entries, [])

    async def test_refused_switch_stops_startup(self):
        self.entries = [{'url':'https://old-tunnel.example/webhook/max'}]
        self.refuse = True
        with self.assertRaises(RuntimeError):
            await switch_to_polling(self.client,self.backup)
        self.assertEqual(len(self.entries), 1)

    async def test_unknown_response_is_not_treated_as_polling_ready(self):
        self.bad_response = True
        with self.assertRaises(RuntimeError):
            await switch_to_polling(self.client,self.backup)
        self.assertEqual(self.deleted, [])
