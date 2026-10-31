import asyncio
import subprocess
from playwright.async_api import async_playwright, expect


async def main():
    subprocess.run(['psql','-h','127.0.0.1','-p','55439','-U','webapp_local','-d','max_webapp_test','-c','UPDATE max_user_balances SET free_divinations_remaining=4 WHERE user_id=900000001'],check=True,stdout=subprocess.DEVNULL)
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        page=await browser.new_page(viewport={'width':390,'height':844})
        await page.route('https://max.ru/js/max-web-app.js',lambda route:route.fulfill(status=200,body=''))
        await page.goto('http://127.0.0.1:8091/#spread')
        await page.locator('#question').fill('Как выбрать дело по душе?')
        await page.locator('[data-mode="own"]').click()
        await page.locator('#next').click()
        for name in ['Маг','Жрица','Императрица']:
            await page.locator('#card-search').fill(name)
            await page.locator('#card-list [data-card]').first.click()
        await page.locator('#confirm').click()
        await page.get_by_role('heading',name='Ваше толкование').wait_for(timeout=20000)
        assert await page.locator('[data-zoom]').count()==3
        await page.goto('http://127.0.0.1:8091/#spread')
        await page.locator('[data-kind="iching"]').click()
        await page.locator('#next').click()
        await page.get_by_role('heading',name='Ваше толкование').wait_for(timeout=20000)
        assert await page.locator('.hexagram-image').count()==1
        await page.goto('http://127.0.0.1:8091/#spread')
        await page.locator('[data-kind="tarot"]').click()
        await page.locator('[data-mode="random"]').click()
        # Simulate a lost HTTP response after the server accepts the operation.
        async def lose_response(route):
            await route.fetch()
            await route.abort()
        await page.route('**/api/webapp/readings',lose_response,times=1)
        await page.locator('#next').click()
        await page.locator('#retry').wait_for()
        await page.reload()
        await page.get_by_role('heading',name='Ваше толкование').wait_for(timeout=20000)
        balance=await page.evaluate("fetch('/api/webapp/me').then(r=>r.json())")
        assert balance['balance']['free_divinations_remaining']==1,balance['balance']
        await page.goto('http://127.0.0.1:8091/#spread')
        await page.locator('#question').fill('Черновик, который должен сохраниться')
        await page.reload()
        await expect(page.locator('#question')).to_have_value('Черновик, который должен сохраниться')
        print('Browser edge checks passed: own cards, I Ching, random, lost response/reload without double debit, draft restore')
        await browser.close()

asyncio.run(main())
