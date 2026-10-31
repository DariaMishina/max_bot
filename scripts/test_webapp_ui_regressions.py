import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / '.local-webapp/screenshots'
SHOTS.mkdir(parents=True, exist_ok=True)
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width':390,'height':844})
        await page.route('https://review.local/**', lambda route: route.fulfill(content_type='text/html',body='<div class="app-shell"><main id="screen"></main></div><button id="balance" hidden></button><button id="close-dialog" hidden></button>'))
        await page.goto('https://review.local/')
        await page.add_style_tag(content=(ROOT/'webapp/style.css').read_text())
        await page.add_script_tag(content=(ROOT/'webapp/card-data.js').read_text())
        await page.add_script_tag(content=(ROOT/'webapp/app.js').read_text().rsplit('init();',1)[0])
        await page.evaluate('''() => {
          catalog = {cards:Object.fromEntries(Object.keys(CARD_DATA).slice(0,9).map(id=>[id,{name:id}])),themes:{timeline:['Прошлое','Настоящее','Будущее']},consultation:{name:'Тест'}};
          profile = {access:'free',balance:{free_divinations_remaining:3,paid_divinations_remaining:0}};
          draft = defaultDraft(); cards();
        }''')
        for width in [320,390,768]:
            await page.set_viewport_size({'width':width,'height':844})
            before = await page.locator('.card').first.bounding_box()
            assert before['width'] >= 70, before
            await page.locator('.card').first.click()
            after = await page.locator('.card').first.bounding_box()
            assert abs(before['width']-after['width']) < 1
            assert abs(before['height']-after['height']) < 1
            await page.locator('#reset').click()
        await page.set_viewport_size({'width':390,'height':844})
        await page.screenshot(path=str(SHOTS / 'webapp-cards-fixed.png'),full_page=True)
        await page.evaluate('''() => {
          catalog.themes.choice=['Ситуация','Возможность','Совет'];
          catalog.themes.relationships=['Ваши чувства','Динамика отношений','Совет'];
          draft.question='Что важно сейчас?'; spread();
        }''')
        await page.locator('[data-theme="relationships"]').click()
        assert await page.evaluate('draft.theme') == 'relationships'
        assert await page.locator('[data-theme][aria-pressed="true"]').count() == 1
        assert await page.evaluate('JSON.parse(localStorage.getItem(userKey+"draft")).theme') == 'relationships'
        for width in [320,390,768]:
            await page.set_viewport_size({'width':width,'height':844})
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            box = await page.locator('[data-theme]').first.bounding_box()
            assert box['height'] >= 100
        await page.set_viewport_size({'width':390,'height':844})
        await page.screenshot(path=str(SHOTS / 'webapp-theme-fixed.png'),full_page=True)
        await page.locator('[data-kind="iching"]').click()
        assert await page.locator('[data-theme]').count() == 0
        await page.locator('[data-kind="tarot"]').click()
        assert await page.locator('[data-theme="relationships"]').get_attribute('aria-pressed') == 'true'
        await page.locator('[data-suggest="1"]').click()
        assert await page.locator('#question').input_value() == 'Что поможет мне развиваться в работе?'
        assert await page.evaluate('draft.theme') == 'relationships'
        await page.locator('#clear-question').click()
        assert await page.locator('#question').input_value() == ''
        await page.evaluate('''async () => {
          api = async () => ({});
          go = () => {};
          draft.question = 'На что обратить внимание в работе?';
          await home(routeVersion);
        }''')
        assert await page.locator('.topic-tile').count() == 6
        await page.screenshot(path=str(SHOTS / 'webapp-home-inspired.png'),full_page=True)
        await page.locator('[data-suggest="0"]').click()
        assert await page.evaluate('draft.theme') == 'relationships'
        await page.locator('#custom-question').click()
        assert await page.evaluate('draft.question') == ''
        assert await page.evaluate('JSON.parse(localStorage.getItem(userKey+"draft")).source') == 'custom'
        await page.evaluate('''() => { screen.innerHTML = '<article class="reading-body">'+readingMarkup('Прошлое — Туз Жезлов\\nПервый абзац.\\n\\nСовет\\nВторой абзац.\\n\\n- Первый шаг\\n- Второй шаг\\n\\n<img src=x onerror=alert(1)>')+'</article>'; }''')
        assert await page.locator('.reading-body h3').count() == 2
        assert await page.locator('.reading-body li').count() == 2
        assert await page.locator('.reading-body img').count() == 0
        await page.screenshot(path=str(SHOTS / 'webapp-text-fixed.png'),full_page=True)
        await page.evaluate('''async () => {
          profile.active_operation='fixture-operation';
          api = async () => ({status:'queued',created_at:new Date(Date.now()-14000).toISOString(),payload:{question:'Что поможет мне развиваться в работе?'}});
          await waiting(routeVersion); clearTimeout(operationTimer);
        }''')
        assert int(await page.locator('#waiting-seconds').inner_text()) >= 14
        assert await page.locator('.waiting-note').inner_text() == 'Вопрос принят. Можно перейти на главную: расклад продолжит готовиться и появится в истории.'
        await page.screenshot(path=str(SHOTS / 'webapp-waiting-inspired.png'),full_page=True)
        await page.evaluate('''async () => {
          api=async()=>({items:[{id:1,question:'Мой вопрос',divination_type:'Таро',selected_cards:[],created_at:new Date().toISOString(),preview:'Начало сохранённого ответа'}],next:null});
          await historyShell();
        }''')
        assert await page.locator('.history-preview').inner_text() == 'Начало сохранённого ответа'
        assert await page.locator('.pending-history').count() == 1
        for width in [320,390,768]:
            await page.set_viewport_size({'width':width,'height':844})
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.evaluate('''() => {
          const sections = Object.values(catalog.themes).flat();
          screen.innerHTML='<article class="reading-body">'+readingMarkup([...new Set(sections)].map(title => title+': Карта\\nКраткое толкование.').join('\\n\\n')+'\\n\\nОбщее толкование:\\nВывод.')+'</article>';
        }''')
        assert await page.locator('.reading-body h3').count() == 9
        for theme in ['timeline', 'choice', 'relationships']:
            for variant in ['normal', 'placeholder', 'inline']:
                await page.evaluate('''async ({theme, variant}) => {
                  const ids=Object.keys(catalog.cards).slice(0,3);
                  ['Девятка Пентаклей','Дурак','Двойка Жезлов'].forEach((name,i)=>catalog.cards[ids[i]].name=name);
                  const positions=catalog.themes[theme];
                  const interpretation=positions.map((position,i)=>{
                    const title=(variant==='placeholder'?'Позиция':position)+': '+catalog.cards[ids[i]].name;
                    return title+(variant==='inline'?'. ':'\\n\\n')+'**Обычный текст толкования. Второе предложение без выделения.**';
                  }).join('\\n\\n')+'\\n\\nОбщее толкование:\\n\\nКраткий итог и конкретный совет.';
                  const value={id:1,divination_type:'Таро',created_at:new Date().toISOString(),question:'Что поможет мне сейчас?',positions,selected_cards:ids,interpretation,followups:[],remaining:2,note:'',favorite:false};
                  api=async()=>value;
                  await reading(1,routeVersion);
                }''', {'theme':theme,'variant':variant})
                assert await page.locator('.reading-body h3').count() == 4, (theme,variant)
                assert await page.locator('.reading-body b, .reading-body strong').count() == 0
                assert await page.locator('.reading-body p').evaluate_all('(items)=>items.every(el=>getComputedStyle(el).fontWeight==="400")')
                assert await page.locator('.reading-body h3').evaluate_all('(items)=>items.every(el=>getComputedStyle(el).fontWeight==="600")')
                assert await page.locator('.reading-body .reading-card-name').count() == 3
                assert 'Позиция:' not in await page.locator('.reading-body').inner_text()
            await page.screenshot(path=str(SHOTS / ('webapp-format-'+theme+'.png')),full_page=True)
        await page.evaluate('''() => {
          catalog.consultation={name:'Диана',hours:'10:00–22:00'};
          catalog.packages=[{id:'consult_detailed',name:'Подробный разбор',type:'consultation',amount_rub:1500},{id:'consult_basic',name:'Базовый разбор',type:'consultation',amount_rub:500}];
          shop(true);
        }''')
        assert await page.locator('.consultation-card').count() == 2
        assert await page.get_by_text('Скрытые моменты ситуации',exact=True).count() == 1
        await page.locator('[data-package="consult_detailed"]').click()
        assert await page.locator('#checkout h2').inner_text() == 'Подробный разбор'
        await page.evaluate('''async () => { api=async()=>({}); await home(routeVersion); }''')
        assert await page.locator('.consultation-overview .consultation-shortcut').count() == 2
        overview=await page.locator('.consultation-overview').bounding_box()
        daily=await page.locator('.daily-panel').bounding_box()
        assert overview['y'] < daily['y']
        colors=await page.locator('.topic-tile > span:last-child').evaluate_all('(items)=>items.map(el=>getComputedStyle(el).color)')
        assert len(set(colors)) == 1
        background=await page.locator('.topic-tile').first.evaluate('(el)=>getComputedStyle(el).backgroundImage')
        await page.locator('.topic-tile').first.hover()
        assert background == await page.locator('.topic-tile').first.evaluate('(el)=>getComputedStyle(el).backgroundImage')
        await page.set_viewport_size({'width':390,'height':844})
        await page.screenshot(path=str(SHOTS / 'webapp-consultations-entry.png'),full_page=True)
        await page.evaluate('''async () => {
          activeRequest=null;
          profile.active_operation=null;
          profile.chat_selection={question:'Исходный вопрос из чата',version:'2026-10-30T12:00:00'};
          profile.pending_question='Исходный вопрос из чата';
          draft={...defaultDraft(),question:'Самостоятельный вопрос'};
          api=async()=>({});
          await home(routeVersion);
        }''')
        assert await page.locator('#pending').count() == 1
        await page.locator('#pending').click()
        assert await page.evaluate('draft.question') == 'Самостоятельный вопрос'
        assert await page.evaluate('chatSelection.question') == 'Исходный вопрос из чата'
        await page.evaluate('cards(true)')
        assert await page.locator('.reading-question').inner_text() == 'Исходный вопрос из чата'
        assert await page.locator('#confirm').inner_text() == 'Получить ответ в чате'
        for i in range(3):
            await page.locator('#card-list [data-card]').nth(i).click()
        await page.locator('#confirm').click()
        assert await page.evaluate('activeRequest.channel') == 'chat-picker'
        await page.evaluate('''async () => {
          window.hybridCalls=[];
          const me={...profile,active_operation:null,chat_selection:null};
          api=async(path)=>{
            hybridCalls.push(path);
            if(path==='me') return me;
            if(path==='chat-card-readings') return {id:'hybrid-fixture'};
            if(path.startsWith('operations/')) return {status:'completed',result_id:77,payload:{delivery:'chat'}};
            return {};
          };
          await waiting(routeVersion);
        }''')
        assert await page.locator('#return-chat').count() == 1
        assert await page.locator('.reading-body').count() == 0
        assert 'chat-card-readings' in await page.evaluate('hybridCalls')
        assert await page.evaluate('draft.question') == 'Самостоятельный вопрос'
        await page.evaluate('''async () => {
          selected=[];
          await startReading();
          const me={...profile,active_operation:null};
          window.webappCalls=[];
          api=async(path)=>{
            webappCalls.push(path);
            if(path==='me') return me;
            if(path==='readings') return {id:'webapp-fixture'};
            if(path.startsWith('operations/')) return {status:'completed',result_id:78,payload:{}};
            return {};
          };
          await waiting(routeVersion);
        }''')
        assert 'readings' in await page.evaluate('webappCalls')
        assert 'chat-card-readings' not in await page.evaluate('webappCalls')
        await browser.close()
        print('PASS: cards, theme selection, topics, question reset, formatting, elapsed waiting, history preview, mobile widths')

asyncio.run(main())
