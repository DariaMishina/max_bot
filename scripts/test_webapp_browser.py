"""Headless UI regression tests against the local demo; screenshots are local."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, expect
import subprocess


async def main():
    subprocess.run(['psql','-h','127.0.0.1','-p','55439','-U','webapp_local','-d','max_webapp_test','-c', 'UPDATE max_user_balances SET free_divinations_remaining=3 WHERE user_id=900000001'],check=True,stdout=subprocess.DEVNULL)
    target = Path('.local-webapp/screenshots')
    target.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        page=await browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        # SDK is irrelevant in demo; don't depend on external network for UI tests.
        await page.route('https://max.ru/js/max-web-app.js',lambda route:route.fulfill(status=200,body=''))
        await page.goto('http://127.0.0.1:8091')
        await page.get_by_role('heading',name='У каждого вопроса').wait_for()
        await page.screenshot(path=str(target/'home.png'),full_page=True)
        await page.get_by_role('link',name='Сделать расклад').click()
        await page.locator('#question').fill('Как выбрать новое направление в работе?')
        await page.locator('#next').click()
        for i in range(3):await page.locator('#card-list [data-card]').nth(i).click()
        await page.screenshot(path=str(target/'cards.png'),full_page=True)
        await page.locator('#confirm').click()
        await page.get_by_role('heading',name='Ваше толкование').wait_for(timeout=20000)
        await page.screenshot(path=str(target/'reading.png'),full_page=True)
        await page.locator('#followup').fill('Какой первый шаг мне сделать?')
        await page.locator('#ask').click()
        await page.get_by_role('heading',name='Ваше толкование').wait_for(timeout=20000)
        await expect(page.locator('.followup')).to_have_count(1,timeout=20000)
        await page.locator('#favorite').check()
        await page.locator('#note').fill('Проверочная заметка')
        await page.locator('#save-note').click()
        await page.get_by_role('link',name='В историю',exact=True).click()
        await page.locator('.history-row').first.wait_for()
        await page.locator('#favorites').check()
        await page.locator('.history-row').first.click()
        await page.locator('#note').wait_for()
        assert await page.locator('#note').input_value()=='Проверочная заметка'
        await page.goto('http://127.0.0.1:8091/#daily')
        await page.locator('h1').filter(has_text='Ваша карта дня').wait_for()
        if await page.locator('[data-daily]').count():await page.locator('[data-daily]').first.click()
        await page.locator('[data-zoom]').wait_for()
        await page.locator('[data-zoom]').click()
        assert await page.locator('dialog').is_visible()
        await page.locator('#close-dialog').click()
        await page.goto('http://127.0.0.1:8091/#profile')
        await page.locator('#feedback').wait_for()
        await page.locator('#feedback').fill('Локальная проверка формы обратной связи')
        await page.locator('#send-feedback').click()
        await page.goto('http://127.0.0.1:8091/#shop')
        await page.locator('[data-package]').first.wait_for()
        await page.locator('[data-package]').first.click()
        assert await page.locator('#pay').is_disabled()
        # Narrow viewport + large font across core pages.
        for width in (320,412):
            await page.set_viewport_size({'width':width,'height':844})
            for route in ('home','spread','history','profile','consultation'):
                await page.goto('http://127.0.0.1:8091/#'+route)
                await page.locator('h1').wait_for()
                await page.add_style_tag(content=':root {font-size:20px}')
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width,route)
        assert not errors,errors
        print('Browser checks passed: manual reading, follow-up, history, notes, daily card, profile, disabled payments, 320/390/412px')
        await browser.close()

asyncio.run(main())
