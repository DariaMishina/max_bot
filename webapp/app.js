// =====================================================
// КОНФИГУРАЦИЯ
// =====================================================
// URL бэкенда Max-бота (webhook_server.py)
// TODO: заменить на реальный URL после деплоя Max-бота
const API_URL = 'https://max-bot-xxxx.onrender.com';

// URL, где лежат картинки карт (существующий Netlify-сайт)
const IMAGES_BASE = 'https://courageous-khapse-7547fa.netlify.app/static/images';

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

function initWebApp() {
    try {
        if (window.WebApp) {
            const wa = window.WebApp;
            wa.ready();

            if (wa.initDataUnsafe && wa.initDataUnsafe.user) {
                userId = wa.initDataUnsafe.user.id;
            }
            initData = wa.initData || '';

            if (wa.HapticFeedback) {
                window._haptic = wa.HapticFeedback;
            }
        }
    } catch (e) {
        console.warn('MAX Bridge not available:', e);
    }
}

function renderCards() {
    const grid = document.getElementById('cards-grid');
    grid.innerHTML = '';

    availableCards.forEach((cardId, idx) => {
        const slot = document.createElement('div');
        slot.className = 'card-slot';
        slot.dataset.cardId = cardId;
        slot.dataset.index = idx;

        slot.innerHTML = `
            <div class="card-face card-back"></div>
            <div class="card-face card-front">
                <img src="${IMAGES_BASE}/${cardId}.png" alt="${TAROT_CARDS[cardId]}" loading="lazy">
            </div>
            <div class="card-check">✓</div>
        `;

        slot.addEventListener('click', () => onCardClick(slot, cardId));
        grid.appendChild(slot);
    });
}

function onCardClick(slot, cardId) {
    if (slot.classList.contains('disabled')) return;

    const isFlipped = slot.classList.contains('flipped');
    const isSelected = slot.classList.contains('selected');

    if (!isFlipped) {
        // Flip the card
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

    document.querySelectorAll('.card-slot').forEach(slot => {
        slot.classList.remove('flipped', 'selected', 'disabled');
    });

    renderCards();
    updateUI();
    hapticFeedback('medium');
}

async function confirmSelection() {
    if (selectedCards.length !== REQUIRED_CARDS) return;

    const confirmBtn = document.getElementById('confirm-btn');
    const resetBtn = document.getElementById('reset-btn');
    const loading = document.getElementById('loading');
    const grid = document.getElementById('cards-grid');

    confirmBtn.classList.add('hidden');
    resetBtn.classList.add('hidden');
    loading.classList.remove('hidden');

    hapticFeedback('medium');

    try {
        const response = await fetch(`${API_URL}/api/webapp/cards`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                selected_cards: selectedCards,
                init_data: initData
            })
        });

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
        }, 2000);

    } catch (err) {
        console.error('Error sending cards:', err);
        loading.classList.add('hidden');
        document.getElementById('error').classList.remove('hidden');
        document.getElementById('error-text').textContent = err.message;
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

// ===== Init =====

document.addEventListener('DOMContentLoaded', () => {
    initWebApp();
    availableCards = pickRandomCards(DISPLAYED_CARDS);
    renderCards();

    document.getElementById('confirm-btn').addEventListener('click', confirmSelection);
    document.getElementById('reset-btn').addEventListener('click', resetSelection);
});
