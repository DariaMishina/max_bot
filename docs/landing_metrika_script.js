/**
 * Скрипт для лендинга: Яндекс.Метрика (цели + client_id) и подстановка start-параметра
 * в ссылки на TG-бота и на бота в MAX (Директ → лендинг → бот).
 *
 * На странице должен быть подключён счётчик Метрики 107059457 (через интерфейс Тильды/платформы).
 * Этот код вставляется дополнительно (например, в «Действия» / кастомный JS).
 */
(function() {
  // ============================================
  // НАСТРОЙКИ
  // ============================================
  var YANDEX_METRIKA_COUNTER_ID = 107059457;

  // IDs целей (как в Метрике -> идентификатор цели)
  var GOAL_TG  = 'go_to_tg';
  var GOAL_MAX = 'go_to_max';
  var GOAL_ANY = 'go_to_messenger';

  // Telegram bot username (без @)
  var TG_BOT_USERNAME = 'gadanie_ai_bot';

  // MAX target URL (без start — он добавится скриптом)
  var MAX_URL = 'https://max.ru/id132608020863_bot';

  // ============================================
  // УТИЛИТЫ
  // ============================================
  function getCookie(name) {
    var matches = document.cookie.match(new RegExp(
      "(?:^|; )" + name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, '\\$1') + "=([^;]*)"
    ));
    return matches ? decodeURIComponent(matches[1]) : undefined;
  }

  function getQueryParam(name) {
    try {
      return new URL(window.location.href).searchParams.get(name) || '';
    } catch (e) {
      return '';
    }
  }

  function isMobile() {
    return /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|WPDesktop/i.test(navigator.userAgent);
  }

  function sendGoal(goalName) {
    if (typeof ym !== 'undefined') {
      ym(YANDEX_METRIKA_COUNTER_ID, 'reachGoal', goalName);
    }
  }

  function getYandexMetrikaClientId(callback) {
    if (typeof ym !== 'undefined') {
      ym(YANDEX_METRIKA_COUNTER_ID, 'getClientID', function(clientID) {
        callback(clientID || getCookie('_ym_uid') || '');
      });
    } else {
      callback(getCookie('_ym_uid') || '');
    }
  }

  // ============================================
  // START PARAM (client_id + utm_campaign)
  // ============================================
  function buildStartParam(clientId) {
    var utmCampaign = getQueryParam('utm_campaign');
    var startParam = '__client_id__' + clientId;
    if (utmCampaign) {
      startParam += '__camp_' + utmCampaign;
    }
    if (startParam.length > 64) {
      startParam = '__client_id__' + clientId;
    }
    return startParam;
  }

  // ============================================
  // 1) ОБНОВЛЯЕМ TG-ССЫЛКИ
  // ============================================
  function updateTelegramLinks(clientId) {
    if (!clientId) return;
    var startParam = buildStartParam(clientId);
    var buttons = document.querySelectorAll('a[href*="t.me"], a[href^="tg://"]');
    buttons.forEach(function(button) {
      if (button.dataset.tgUpdated) return;
      var newHref;
      if (isMobile()) {
        newHref = 'tg://resolve?domain=' + TG_BOT_USERNAME + '&start=' + encodeURIComponent(startParam);
      } else {
        newHref = 'https://t.me/' + TG_BOT_USERNAME + '?start=' + encodeURIComponent(startParam);
      }
      button.setAttribute('href', newHref);
      button.dataset.tgUpdated = 'true';
    });
  }

  // ============================================
  // 2) ОБНОВЛЯЕМ ССЫЛКИ НА MAX (добавляем start)
  // ============================================
  function updateMaxLinks(clientId) {
    if (!clientId) return;
    var startParam = buildStartParam(clientId);
    var sep = MAX_URL.indexOf('?') >= 0 ? '&' : '?';
    var newHref = MAX_URL + sep + 'start=' + encodeURIComponent(startParam);
    var maxLinks = document.querySelectorAll('a[href*="max.ru/"]');
    maxLinks.forEach(function(a) {
      if (a.dataset.maxUpdated) return;
      a.setAttribute('href', newHref);
      a.dataset.maxUpdated = 'true';
    });
  }

  // ============================================
  // 3) (Опционально) нормализуем MAX-ссылки по URL
  // ============================================
  function normalizeMaxLinks() {
    var maxLinks = document.querySelectorAll('a[href*="max.ru/"]');
    maxLinks.forEach(function(a) {
      if (a.dataset.maxNormalized) return;
      a.setAttribute('href', MAX_URL);
      a.dataset.maxNormalized = 'true';
    });
  }

  // ============================================
  // 4) ЦЕЛИ МЕТРИКИ ПО КЛИКУ (TG + MAX + общая)
  // ============================================
  function attachMessengerGoalTracking() {
    if (window.__msg_goal_handler_attached__) return;
    window.__msg_goal_handler_attached__ = true;
    document.addEventListener('click', function(e) {
      var a = e.target && e.target.closest ? e.target.closest('a') : null;
      if (!a) return;
      var href = (a.getAttribute('href') || '').toLowerCase();
      var isTG = href.includes('t.me') || href.startsWith('tg://');
      var isMAX = href.includes('max.ru/');
      if (!isTG && !isMAX) return;
      if (isTG) sendGoal(GOAL_TG);
      if (isMAX) sendGoal(GOAL_MAX);
      sendGoal(GOAL_ANY);
    }, true);
  }

  // ============================================
  // INIT
  // ============================================
  function init() {
    attachMessengerGoalTracking();
    normalizeMaxLinks();

    var attempts = 0;
    var checkMetrika = setInterval(function() {
      attempts++;
      if (typeof ym !== 'undefined') {
        clearInterval(checkMetrika);
        getYandexMetrikaClientId(function(clientId) {
          updateTelegramLinks(clientId);
          updateMaxLinks(clientId);
        });
      } else if (attempts >= 100) {
        clearInterval(checkMetrika);
        var clientId = getCookie('_ym_uid');
        if (clientId) {
          updateTelegramLinks(clientId);
          updateMaxLinks(clientId);
        }
      }
    }, 100);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
