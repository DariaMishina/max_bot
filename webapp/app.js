const API_URL = 'https://max-bot-awtw.onrender.com';
const IMG_BASE = '/static/images';
const IMG_VER = 'v=2';
const REQUIRED_CARDS = 3;
const DISPLAYED_CARDS = 9;

const TAROT_CARDS = {
    "00-TheFool": "Дурак",
    "01-TheMagician": "Маг",
    "02-TheHighPriestess": "Верховная Жрица",
    "03-TheEmpress": "Императрица",
    "04-TheEmperor": "Император",
    "05-TheHierophant": "Иерофант",
    "06-TheLovers": "Влюбленные",
    "07-TheChariot": "Колесница",
    "08-Strength": "Сила",
    "09-TheHermit": "Отшельник",
    "10-WheelOfFortune": "Колесо Фортуны",
    "11-Justice": "Справедливость",
    "12-TheHangedMan": "Повешенный",
    "13-Death": "Смерть",
    "14-Temperance": "Умеренность",
    "15-TheDevil": "Дьявол",
    "16-TheTower": "Башня",
    "17-TheStar": "Звезда",
    "18-TheMoon": "Луна",
    "19-TheSun": "Солнце",
    "20-Judgement": "Суд",
    "21-TheWorld": "Мир",
    "Cups01": "Туз Кубков", "Cups02": "Двойка Кубков", "Cups03": "Тройка Кубков",
    "Cups04": "Четверка Кубков", "Cups05": "Пятерка Кубков", "Cups06": "Шестерка Кубков",
    "Cups07": "Семерка Кубков", "Cups08": "Восьмерка Кубков", "Cups09": "Девятка Кубков",
    "Cups10": "Десятка Кубков", "Cups11": "Паж Кубков", "Cups12": "Рыцарь Кубков",
    "Cups13": "Королева Кубков", "Cups14": "Король Кубков",
    "Pentacles01": "Туз Пентаклей", "Pentacles02": "Двойка Пентаклей",
    "Pentacles03": "Тройка Пентаклей", "Pentacles04": "Четверка Пентаклей",
    "Pentacles05": "Пятерка Пентаклей", "Pentacles06": "Шестерка Пентаклей",
    "Pentacles07": "Семерка Пентаклей", "Pentacles08": "Восьмерка Пентаклей",
    "Pentacles09": "Девятка Пентаклей", "Pentacles10": "Десятка Пентаклей",
    "Pentacles11": "Паж Пентаклей", "Pentacles12": "Рыцарь Пентаклей",
    "Pentacles13": "Королева Пентаклей", "Pentacles14": "Король Пентаклей",
    "Swords01": "Туз Мечей", "Swords02": "Двойка Мечей", "Swords03": "Тройка Мечей",
    "Swords04": "Четверка Мечей", "Swords05": "Пятерка Мечей", "Swords06": "Шестерка Мечей",
    "Swords07": "Семерка Мечей", "Swords08": "Восьмерка Мечей", "Swords09": "Девятка Мечей",
    "Swords10": "Десятка Мечей", "Swords11": "Паж Мечей", "Swords12": "Рыцарь Мечей",
    "Swords13": "Королева Мечей", "Swords14": "Король Мечей",
    "Wands01": "Туз Жезлов", "Wands02": "Двойка Жезлов", "Wands03": "Тройка Жезлов",
    "Wands04": "Четверка Жезлов", "Wands05": "Пятерка Жезлов", "Wands06": "Шестерка Жезлов",
    "Wands07": "Семерка Жезлов", "Wands08": "Восьмерка Жезлов", "Wands09": "Девятка Жезлов",
    "Wands10": "Десятка Жезлов", "Wands11": "Паж Жезлов", "Wands12": "Рыцарь Жезлов",
    "Wands13": "Королева Жезлов", "Wands14": "Король Жезлов"
};

let selectedCards = [];
let availableCards = [];
let userId = null;
let initData = null;

function shuffleArray(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
}

function pickRandomCards(count) {
    const allIds = Object.keys(TAROT_CARDS);
    return shuffleArray(allIds).slice(0, count);
}

function _decodeWebAppData(raw) {
    try {
        let decoded = decodeURIComponent(raw);
        const params = new URLSearchParams(decoded);

        let userStr = params.get('user');
        if (userStr) {
            try { userStr = decodeURIComponent(userStr); } catch (_) {}
            const user = JSON.parse(userStr);
            if (user && user.id) return { userId: user.id, initData: decoded };
        }

        let chatStr = params.get('chat');
        if (chatStr) {
            try { chatStr = decodeURIComponent(chatStr); } catch (_) {}
            const chat = JSON.parse(chatStr);
            if (chat && chat.type === 'DIALOG' && chat.id) {
                return { userId: chat.id, initData: decoded };
            }
        }
    } catch (_) {}
    return null;
}

function initWebApp() {
    try {
        const wa = window.WebApp;
        if (wa) {
            wa.ready();
            initData = wa.initData || '';
            if (wa.initDataUnsafe && wa.initDataUnsafe.user && wa.initDataUnsafe.user.id) {
                userId = wa.initDataUnsafe.user.id;
            }
            if (!userId && initData) {
                const r = _decodeWebAppData(initData);
                if (r) userId = r.userId;
            }
            if (wa.HapticFeedback) window._haptic = wa.HapticFeedback;
        }
    } catch (e) {
        console.warn('MAX Bridge init error:', e);
    }

    if (!userId) {
        try {
            const hash = window.location.hash.substring(1);
            if (hash) {
                const hp = new URLSearchParams(hash);
                const webAppData = hp.get('WebAppData') || hp.get('tgWebAppData');
                if (webAppData) {
                    const r = _decodeWebAppData(webAppData);
                    if (r) { userId = r.userId; if (!initData) initData = r.initData; }
                }
                if (!userId) {
                    const r = _decodeWebAppData(hash);
                    if (r) { userId = r.userId; if (!initData) initData = r.initData; }
                }
            }
        } catch (_) {}
    }

    if (!userId) {
        try {
            const sp = new URLSearchParams(window.location.search);
            const uid = sp.get('user_id') || sp.get('userId');
            if (uid) userId = parseInt(uid, 10);
        } catch (_) {}
    }

    console.log('[MAX WebApp] userId:', userId);
    _showDebug();
}

function _showDebug() {
    var d = document.createElement('div');
    d.id = 'debug-panel';
    d.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:rgba(0,0,0,0.92);color:#0f0;font:10px/1.3 monospace;padding:6px;max-height:40vh;overflow:auto;z-index:9999;word-break:break-all;';
    document.body.appendChild(d);
    _dbg('uid:' + userId + ' | WA:' + !!window.WebApp + ' | loc:' + location.hostname);

    var testUrl = IMG_BASE + '/CardBacks.png?' + IMG_VER;
    var t0 = Date.now();

    _dbg('T1-fetch start');
    fetch(testUrl).then(function(r) {
        _dbg('T1-fetch status:' + r.status + ' ' + (Date.now()-t0) + 'ms');
        return r.blob();
    }).then(function(blob) {
        _dbg('T1-fetch OK blob:' + blob.size + 'B ' + (Date.now()-t0) + 'ms');
    }).catch(function(e) {
        _dbg('T1-fetch FAIL: ' + e.message);
    });

    var xhr = new XMLHttpRequest();
    xhr.open('GET', testUrl, true);
    xhr.responseType = 'blob';
    xhr.onload = function() { _dbg('T2-xhr OK status:' + xhr.status + ' size:' + xhr.response.size + ' ' + (Date.now()-t0) + 'ms'); };
    xhr.onerror = function() { _dbg('T2-xhr FAIL ' + (Date.now()-t0) + 'ms'); };
    xhr.ontimeout = function() { _dbg('T2-xhr TIMEOUT'); };
    xhr.send();
    _dbg('T2-xhr start');

    var di = new Image();
    di.onload = function() { _dbg('T3-datauri OK'); };
    di.onerror = function() { _dbg('T3-datauri FAIL'); };
    di.src = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/58BHgAI/AL+hc2rNAAAAABJRU5ErkJggg==';
    _dbg('T3-datauri start');
}

function _dbg(msg) {
    var d = document.getElementById('debug-panel');
    if (!d) return;
    var line = document.createElement('div');
    var ts = new Date();
    line.textContent = ts.getMinutes() + ':' + String(ts.getSeconds()).padStart(2,'0') + '.' + String(ts.getMilliseconds()).padStart(3,'0') + ' ' + msg;
    d.appendChild(line);
    d.scrollTop = d.scrollHeight;
}

function cardDataUri(cardId) {
    return (typeof CARD_DATA !== 'undefined' && CARD_DATA[cardId]) ? CARD_DATA[cardId] : '';
}

function renderCards() {
    var grid = document.getElementById('cards-grid');
    grid.innerHTML = '';
    var hasData = typeof CARD_DATA !== 'undefined';
    _dbg('renderCards: ' + availableCards.length + ' cards, CARD_DATA:' + hasData);

    var backUri = hasData ? CARD_DATA['CardBacks'] : '';

    availableCards.forEach(function(cardId, idx) {
        var slot = document.createElement('div');
        slot.className = 'card-slot';
        slot.dataset.cardId = cardId;
        slot.dataset.index = idx;

        var back = document.createElement('div');
        back.className = 'card-face card-back';
        if (backUri) back.style.backgroundImage = "url('" + backUri + "')";

        var front = document.createElement('div');
        front.className = 'card-face card-front';
        var frontUri = cardDataUri(cardId);
        if (frontUri) front.style.backgroundImage = "url('" + frontUri + "')";

        var check = document.createElement('div');
        check.className = 'card-check';
        check.textContent = '✓';

        slot.appendChild(front);
        slot.appendChild(back);
        slot.appendChild(check);
        slot.addEventListener('click', function() { onCardClick(slot, cardId); });
        grid.appendChild(slot);
    });

    _dbg('DOM built, cards rendered');
}

function onCardClick(slot, cardId) {
    if (slot.classList.contains('disabled')) return;

    const isFlipped = slot.classList.contains('flipped');
    const isSelected = slot.classList.contains('selected');

    if (!isFlipped) {
        slot.classList.add('flipped');
        if (selectedCards.length < REQUIRED_CARDS) {
            slot.classList.add('selected');
            selectedCards.push(cardId);
            hapticFeedback('light');
        }
    } else if (isSelected) {
        slot.classList.remove('selected');
        selectedCards = selectedCards.filter(id => id !== cardId);
        hapticFeedback('light');
    } else if (selectedCards.length < REQUIRED_CARDS) {
        slot.classList.add('selected');
        selectedCards.push(cardId);
        hapticFeedback('light');
    }

    updateUI();
}

function updateUI() {
    const countEl = document.getElementById('count');
    const counterP = countEl.parentElement;
    const confirmBtn = document.getElementById('confirm-btn');
    const resetBtn = document.getElementById('reset-btn');

    countEl.textContent = selectedCards.length;

    if (selectedCards.length === REQUIRED_CARDS) {
        counterP.classList.add('complete');
        confirmBtn.disabled = false;
        resetBtn.classList.remove('hidden');

        document.querySelectorAll('.card-slot').forEach(slot => {
            if (!slot.classList.contains('selected')) {
                slot.classList.add('disabled');
            }
        });
    } else {
        counterP.classList.remove('complete');
        confirmBtn.disabled = true;

        document.querySelectorAll('.card-slot.disabled').forEach(slot => {
            slot.classList.remove('disabled');
        });
    }
}

function resetSelection() {
    selectedCards = [];
    availableCards = pickRandomCards(DISPLAYED_CARDS);
    renderCards();
    updateUI();
    hapticFeedback('medium');
}

async function confirmSelection() {
    if (selectedCards.length !== REQUIRED_CARDS) return;

    if (!userId) {
        document.getElementById('error').classList.remove('hidden');
        document.getElementById('error-text').textContent =
            'Не удалось определить пользователя. Откройте приложение через бота в MAX.';
        hapticFeedback('error');
        return;
    }

    const confirmBtn = document.getElementById('confirm-btn');
    const resetBtn = document.getElementById('reset-btn');
    const loading = document.getElementById('loading');
    const grid = document.getElementById('cards-grid');

    confirmBtn.classList.add('hidden');
    resetBtn.classList.add('hidden');
    loading.classList.remove('hidden');

    hapticFeedback('medium');

    const loadingText = loading.querySelector('p');
    const wakeTimer = setTimeout(() => {
        if (loadingText) loadingText.textContent = 'Сервер просыпается, подождите...';
    }, 5000);

    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 60000);

        const response = await fetch(`${API_URL}/api/webapp/cards`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                selected_cards: selectedCards,
                init_data: initData
            }),
            signal: controller.signal
        });

        clearTimeout(timeout);
        clearTimeout(wakeTimer);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || `Ошибка сервера: ${response.status}`);
        }

        loading.classList.add('hidden');
        document.getElementById('success').classList.remove('hidden');
        grid.classList.add('hidden');
        document.querySelector('.subtitle').classList.add('hidden');
        document.querySelector('.counter').classList.add('hidden');

        hapticFeedback('success');

        setTimeout(() => {
            try { window.WebApp.close(); } catch (_) {}
        }, 2500);

    } catch (err) {
        clearTimeout(wakeTimer);
        console.error('Error sending cards:', err);
        loading.classList.add('hidden');

        const isTimeout = err.name === 'AbortError';
        document.getElementById('error').classList.remove('hidden');
        document.getElementById('error-text').textContent = isTimeout
            ? 'Сервер не ответил за 60 секунд. Попробуйте ещё раз.'
            : err.message;
        confirmBtn.classList.remove('hidden');
        resetBtn.classList.remove('hidden');
        hapticFeedback('error');
    }
}

function hapticFeedback(type) {
    try {
        if (!window._haptic) return;
        if (type === 'success' || type === 'error' || type === 'warning') {
            window._haptic.notificationOccurred(type);
        } else {
            window._haptic.impactOccurred(type);
        }
    } catch (_) {}
}

document.addEventListener('DOMContentLoaded', function() {
    initWebApp();
    availableCards = pickRandomCards(DISPLAYED_CARDS);
    renderCards();

    document.getElementById('confirm-btn').addEventListener('click', confirmSelection);
    document.getElementById('reset-btn').addEventListener('click', resetSelection);
});
