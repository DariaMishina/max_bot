"""Local-only launcher. Never reads production configuration."""
import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def _present(value):
    text = (value or '').strip()
    return text or None


def configure(demo=False):
    from dotenv import dotenv_values
    shared = dotenv_values(ROOT / '.env')
    own = dotenv_values(ROOT / '.env.webapp')
    # The test token lives in .env.webapp. Production BOT_TOKEN is never a fallback.
    token = (
        _present(own.get('BOT_TOKEN_TEST'))
        or _present(own.get('MAX_TEST_BOT_TOKEN'))
        or _present(shared.get('BOT_TOKEN_TEST'))
        or _present(shared.get('MAX_TEST_BOT_TOKEN'))
    )
    production_token = _present(shared.get('BOT_TOKEN'))
    if token and production_token and token == production_token:
        raise SystemExit('Test launcher refused the production BOT_TOKEN.')
    if not demo and not token:
        raise SystemExit('Set BOT_TOKEN_TEST in .env.webapp (never BOT_TOKEN).')
    values = {
        'TEST_MODE': 'true', 'DB_TABLE_SUFFIX': '', 'BOT_TOKEN': '',
        'BOT_TOKEN_TEST': token or 'local-demo-only',
        'API_KEY': own.get('API_KEY') or 'demo', 'DB_HOST': '127.0.0.1',
        'DB_PORT': '55439', 'DB_NAME': 'max_webapp_test', 'DB_USER': 'webapp_local',
        'DB_PASSWORD': '', 'PORT': '8091', 'HOST': '127.0.0.1',
        'ENABLE_DAILY_TIP': 'false', 'ENABLE_BACKGROUND_JOBS': 'false',
        'PERSONALIZED_BROADCASTS': 'false', 'METRIKA_MP_TOKEN': '',
        'METRIKA_MP_COUNTER_ID': '', 'CHANNEL_CHAT_ID': '', 'CHANNEL_URL': '',
        'ADMIN_CHAT_ID': '', 'YOOKASSA_SHOP_ID': '', 'YOOKASSA_SECRET_KEY': '',
        'SERVICE_URL': own.get('PUBLIC_BASE_URL') or 'http://127.0.0.1:8091',
        'WEBAPP_DEMO': str(demo).lower(), 'WEBAPP_ALLOWED_IDS': own.get('WEBAPP_ALLOWED_IDS', ''),
        'TAROLOGIST_PROFILE_URL': own.get('TAROLOGIST_PROFILE_URL', ''),
        'WEBAPP_LOCAL': 'true',
    }
    if not demo:
        for key in ('YOOKASSA_SHOP_ID', 'YOOKASSA_SECRET_KEY'):
            values[key] = own.get(key) or ''
        key = values['YOOKASSA_SECRET_KEY']
        if key and not key.startswith('test_'):
            raise SystemExit('Only YooKassa test_ keys are accepted in this test branch.')
        if not values['WEBAPP_ALLOWED_IDS']:
            raise SystemExit('Set WEBAPP_ALLOWED_IDS in .env.webapp to your MAX user ID(s).')
        if values['API_KEY'] == 'demo':
            raise SystemExit('Set API_KEY (DeepSeek) in .env.webapp for connected mode.')
    os.environ.update(values)


def db(action):
    if action != 'stop':
        probe = subprocess.run(
            ['psql', '-h', '127.0.0.1', '-p', '55439', '-U', 'webapp_local', '-d', 'max_webapp_test', '-Atc', 'SELECT 1'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            print('Local database already running: 127.0.0.1:55439/max_webapp_test')
            return
    data = ROOT / '.local-webapp/postgres'
    data.parent.mkdir(exist_ok=True)
    ctl = ['pg_ctl', '-D', str(data)]
    if action == 'stop':
        subprocess.run(ctl + ['stop', '-m', 'fast'], check=True)
        return
    if not (data / 'PG_VERSION').exists():
        subprocess.run(['initdb', '-D', str(data), '-U', 'webapp_local', '-A', 'trust', '--encoding=UTF8', '--locale=C'], check=True, stdout=subprocess.DEVNULL)
    if subprocess.run(ctl + ['status'], stdout=subprocess.DEVNULL).returncode:
        subprocess.run(ctl + ['-l', str(data.parent / 'postgres.log'), '-o', '-h 127.0.0.1 -p 55439 -k ' + str(data.parent), 'start'], check=True)
    args = ['psql', '-h', '127.0.0.1', '-p', '55439', '-U', 'webapp_local', '-d', 'postgres', '-Atc']
    exists = subprocess.check_output(args + ["SELECT 1 FROM pg_database WHERE datname='max_webapp_test'"], text=True).strip()
    if not exists:
        subprocess.run(args + ['CREATE DATABASE max_webapp_test'], check=True)
    subprocess.run(['psql', '-h', '127.0.0.1', '-p', '55439', '-U', 'webapp_local', '-d', 'max_webapp_test', '-v', 'ON_ERROR_STOP=1', '-f', 'init_db.sql'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    print('Local database: 127.0.0.1:55439/max_webapp_test')


async def serve(demo):
    from webhook_server import start_webhook_server
    from main.database import Database
    runner = await start_webhook_server(8091)
    print('WebApp: http://127.0.0.1:8091 — ' + ('DEMO' if demo else 'MAX'), flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await Database.close_pool()


async def run_max():
    import ssl
    import aiohttp
    import aiomax
    from main.webapp_transport import switch_to_polling
    if os.environ.get('WEBAPP_LOCAL') != 'true' or os.environ.get('TEST_MODE') != 'true' or os.environ.get('BOT_TOKEN'):
        raise RuntimeError('Transport switching is allowed only for the isolated test launcher.')
    tls = ssl.create_default_context()
    tls.load_verify_locations(cafile=str(Path(aiomax.__file__).parent / 'russian_trusted_root_ca.cer'))
    async with aiohttp.ClientSession(base_url='https://platform-api2.max.ru', headers={'Authorization': os.environ['BOT_TOKEN_TEST']}, connector=aiohttp.TCPConnector(ssl=tls), timeout=aiohttp.ClientTimeout(total=30)) as session:
        removed = await switch_to_polling(session, ROOT / '.local-webapp/max-subscriptions-before-polling.json')
    print(f'MAX test bot: polling; removed webhook subscriptions: {removed}', flush=True)
    from bot import main
    await main()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['db', 'stop-db', 'demo', 'max', 'api'])
    args = parser.parse_args()
    if args.mode in ('db', 'stop-db'):
        db('stop' if args.mode == 'stop-db' else 'start')
    else:
        configure(demo=args.mode == 'demo')
        if args.mode == 'max':
            asyncio.run(run_max())
        else:
            asyncio.run(serve(args.mode == 'demo'))
