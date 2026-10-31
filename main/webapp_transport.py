"""Switch the explicitly configured local test bot from webhook to polling."""
import json


async def switch_to_polling(session, backup_path):
    async def subscriptions():
        async with session.get('/subscriptions') as response:
            response.raise_for_status()
            data = await response.json()
        if not isinstance(data.get('subscriptions'), list):
            raise RuntimeError('MAX did not return a subscription list; polling was not started.')
        return data['subscriptions']

    current = await subscriptions()
    if not current:
        return 0
    if any(not isinstance(item, dict) or not isinstance(item.get('url'), str) or not item['url'] for item in current):
        raise RuntimeError('Invalid MAX subscription; polling was not started.')
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(json.dumps(current, ensure_ascii=False, indent=2))
    for item in current:
        async with session.delete('/subscriptions', params={'url': item['url']}) as response:
            response.raise_for_status()
            data = await response.json()
        if data.get('success') is not True:
            raise RuntimeError('MAX refused to remove a test webhook; polling was not started.')
    if await subscriptions():
        raise RuntimeError('Test webhook subscriptions remain; polling was not started.')
    return len(current)
