"use strict";
const $ = (s) => document.querySelector(s);
const escapeHTML = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const e = escapeHTML;
const questionTopics = [
  { icon: "♡", title: "Отношения", question: "Что мне важно понять об отношениях?", theme: "relationships" },
  { icon: "♧", title: "Работа и карьера", question: "Что поможет мне развиваться в работе?", theme: "choice" },
  { icon: "✦", title: "Финансы", question: "На что обратить внимание в моём отношении к деньгам?", theme: "choice" },
  { icon: "☾", title: "Перемены", question: "Как подготовиться к переменам в моей жизни?", theme: "timeline" },
  { icon: "✧", title: "Мой выбор", question: "Что поможет мне сделать выбор?", theme: "choice" },
  { icon: "❋", title: "О себе", question: "Что поможет мне лучше понять себя сейчас?", theme: "timeline" },
];
function topicButtons(compact = false) {
  return `<div class="${compact ? "question-suggestions" : "topic-grid"}">${questionTopics.map((topic, index) => `<button class="${compact ? "suggestion-chip" : "topic-tile"}" data-suggest="${index}"><span aria-hidden="true">${topic.icon}</span><span>${topic.title}</span></button>`).join("")}</div>`;
}
function chooseTopic(index) {
  const topic = questionTopics[index];
  draft.question = topic.question;
  draft.kind = "tarot";
  draft.source = "topic";
  selected = []; deck = [];
  save("draft", draft);
}
function consultationOverview() {
  const packages = (catalog.packages || []).filter(p => p.type === "consultation");
  return `<section class="consultation-overview" aria-labelledby="consultation-overview-title"><p class="eyebrow">Лично с тарологом</p><h2 id="consultation-overview-title">Нужен более глубокий разбор?</h2><p class="muted">${e(catalog.consultation.name)} ответит лично. Выберите базовую или развёрнутую консультацию.</p><div class="consultation-shortcuts">${packages.map(p => `<a href="#consultation" class="consultation-shortcut"><strong>${e(p.name)}</strong><span>${e(p.amount_rub)} ₽</span></a>`).join("")}</div><a href="#consultation" class="primary wide">Посмотреть консультации →</a></section>`;
}
function waitingMarkup(question = "", seconds = 0, accepted = false) {
  return `${heading("Ваш вопрос", "Расклад готовится")}${question ? `<div class="reading-question">${e(question)}</div>` : ""}<section class="preparing-panel"><div class="preparing-symbol" aria-hidden="true">✧</div><h2>${accepted ? "Ваш вопрос принят. Собираем ответ" : "Принимаем ваш вопрос"}</h2><p class="muted">Рассматриваем ваш вопрос и связываем значения карт в одно толкование.</p><div class="waiting-activity" role="status"><span class="orbit-spinner" aria-hidden="true"></span><span>${accepted ? "Готовим толкование" : "Отправляем запрос"}</span></div><p class="hint">Прошло <span id="waiting-seconds">${seconds}</span> сек.</p><p class="waiting-note">${accepted ? "Вопрос принят. Можно перейти на главную: расклад продолжит готовиться и появится в истории." : "Дождитесь подтверждения, что вопрос принят."}</p><a class="secondary wide" href="#home">На главную</a></section>`;
}
function readingMarkup(text, options = {}) {
  const blocks = [];
  let paragraph = [], list = [], positionIndex = 0;
  const clean = value => String(value || "").replace(/\*\*/g, "").trim();
  const normalize = value => clean(value).toLocaleLowerCase("ru").replace(/ё/g, "е");
  const positions = options.positions || [];
  const cards = (options.selected_cards || []).map(id => catalog?.cards?.[id]?.name).filter(Boolean);
  const cardNames = [...new Set([...cards, ...Object.values(catalog?.cards || {}).map(card => card.name)])].filter(Boolean).sort((a, b) => b.length - a.length);
  const labels = [...new Set(["Прошлое", "Настоящее", "Будущее", "Сейчас", "Ситуация", "Возможность", "Совет", "Общее толкование", "Итог", "Главное", "Возможное развитие", "Ваши чувства", "Динамика отношений", ...Object.values(catalog?.themes || {}).flat(), ...positions])].sort((a, b) => b.length - a.length);
  const flush = () => {
    if (paragraph.length) blocks.push(`<p>${e(paragraph.join("\n"))}</p>`);
    if (list.length) blocks.push(`<ul>${list.map(item => `<li>${e(item)}</li>`).join("")}</ul>`);
    paragraph = []; list = [];
  };
  for (const raw of String(text || "").split(/\r?\n/)) {
    const line = clean(raw);
    if (!line) { flush(); continue; }
    const title = line.replace(/^#{1,6}\s+/, "").replace(/^\d+[.)]\s*/, "");
    let label = labels.find(item => normalize(title) === normalize(item) || /^\s*[:—–-]/.test(title.slice(item.length)) && normalize(title.slice(0, item.length)) === normalize(item));
    const placeholder = /^Позиция(?:\s+\d+)?\s*[:—–-]\s*/i.exec(title);
    let suffix = label ? title.slice(label.length).replace(/^\s*[:—–-]\s*/, "") : "";
    if (placeholder) {
      suffix = title.slice(placeholder[0].length);
      const index = cards.findIndex(name => normalize(suffix).startsWith(normalize(name)));
      label = positions[index >= 0 ? index : positionIndex] || "Карта";
    }
    if (label) {
      const name = cardNames.find(name => normalize(suffix) === normalize(name) || normalize(suffix).startsWith(normalize(name) + ".") || normalize(suffix).startsWith(normalize(name) + " —") || normalize(suffix).startsWith(normalize(name) + ":"));
      const body = name ? suffix.slice(name.length).replace(/^[\s.:—–-]+/, "") : suffix;
      flush();
      blocks.push(`<h3>${e(label)}${name ? `<span class="reading-card-name"> — ${e(name)}</span>` : ""}</h3>`);
      if (body) paragraph.push(body);
      if (placeholder || positions.includes(label)) positionIndex++;
    } else if (/^[-•*]\s+/.test(line)) {
      if (paragraph.length) flush();
      list.push(line.replace(/^[-•*]\s+/, ""));
    } else {
      if (list.length) flush();
      paragraph.push(line);
    }
  }
  flush();
  return blocks.join("");
}
const screen = $("#screen");
let catalog,
  profile,
  initData = "",
  draft,
  selected = [],
  deck = [],
  currentReading,
  chatSelection,
  pickerDraft,
  nextHistory,
  historyItems = [];
let operationTimer,
  toastTimer,
  routeVersion = 0,
  userKey = "sphere:";
let activeRequest = null,
  paymentRequest = null;
const defaultDraft = () => ({
  question: "",
  mode: "manual",
  kind: "tarot",
  theme: "timeline",
});
function getSaved(key, fallback = null) {
  try {
    return JSON.parse(localStorage.getItem(userKey + key)) ?? fallback;
  } catch {
    return fallback;
  }
}
function save(key, value) {
  try {
    localStorage.setItem(userKey + key, JSON.stringify(value));
  } catch {}
}
function notify(text) {
  clearTimeout(toastTimer);
  $("#toast").textContent = text;
  $("#toast").hidden = false;
  toastTimer = setTimeout(() => ($("#toast").hidden = true), 4500);
}
function haptic() {
  try {
    window.WebApp?.HapticFeedback?.impactOccurred("light");
  } catch {}
}
async function api(path, data) {
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch("/api/webapp/" + path, {
      method: data === undefined ? "GET" : "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Max-Init-Data": initData,
      },
      body: data === undefined ? undefined : JSON.stringify(data),
      signal: controller.signal,
    });
    const value = await response.json();
    if (!response.ok) {
      if (response.status === 401) {
        try {
          sessionStorage.removeItem("sphere:max-init-data");
        } catch {}
      }
      const error = new Error(value.error || "Не удалось выполнить запрос.");
      error.status = response.status;
      throw error;
    }
    return value;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error(
        "Сервер отвечает дольше обычного. Повторите проверку — запрос сохранён.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
function track(event) {
  api("events", { event }).catch(() => {});
}
function bind(selector, fn, event = "click") {
  const element = $(selector);
  if (!element) return;
  element.addEventListener(event, async (ev) => {
    if (event === "click") ev.preventDefault();
    try {
      await fn(ev);
    } catch (error) {
      notify(error.message);
    }
  });
}
function all(selector, fn) {
  document.querySelectorAll(selector).forEach((element) =>
    element.addEventListener("click", async (ev) => {
      ev.preventDefault();
      try {
        await fn(element, ev);
      } catch (error) {
        notify(error.message);
      }
    }),
  );
}
function go(route) {
  if (location.hash === "#" + route) render();
  else location.hash = route;
}
function imageFor(id) {
  return typeof CARD_DATA !== "undefined" ? CARD_DATA[id] || "" : "";
}
function card(
  id,
  index,
  { back = false, selectedCard = false, zoom = false } = {},
) {
  return `<button class="card ${selectedCard ? "selected" : ""}" data-card="${e(id)}" ${zoom ? 'data-zoom="' + e(id) + '"' : ""} aria-label="${back ? "Выбрать карту " + (index + 1) : e(catalog.cards[id]?.name || id)}" ${zoom ? "" : 'aria-pressed="' + selectedCard + '"'}>${back ? '<span class="card-symbol" aria-hidden="true">✧</span>' : `<img src="${e(imageFor(id))}" alt="${e(catalog.cards[id]?.name || id)}">`}${selectedCard ? `<span class="badge">${index + 1}</span>` : ""}</button>`;
}
function zoomCards() {
  all("[data-zoom]", (element) => {
    const id = element.dataset.zoom;
    $("#card-dialog img").src = imageFor(id);
    $("#card-dialog img").alt = catalog.cards[id]?.name || "";
    $("#card-dialog p").textContent = catalog.cards[id]?.name || "";
    $("#card-dialog").showModal();
  });
}
function back(to = "home", text = "Назад") {
  return `<button class="back-link" id="back">← ${e(text)}</button>`;
}
function heading(kicker, title, subtitle = "") {
  return `<p class="eyebrow">${e(kicker)}</p><h1>${e(title)}</h1>${subtitle ? `<p class="muted">${e(subtitle)}</p>` : ""}`;
}
function loading(text = "Готовим ваш расклад") {
  return `<div class="loading"><span class="orbit-spinner" aria-hidden="true"></span><h1>${e(text)}</h1><p class="muted">Можно закрыть приложение.<br>Ответ сохранится в вашей истории.</p><p role="status" class="hint">Обычно это занимает до полутора минут.</p></div>`;
}
async function refresh() {
  profile = await api("me");
  $("#balance").textContent =
    profile.access === "unlimited"
      ? "∞ Безлимит"
      : `${profile.balance.free_divinations_remaining + profile.balance.paid_divinations_remaining} ✧`;
}
function accessHint() {
  return {
    free: "Будет использован 1 подарочный расклад",
    paid: "Будет использован 1 оплаченный расклад",
    unlimited: "Включено в ваш безлимит",
    none: "Расклады закончились — выберите пакет",
  }[profile.access];
}
function empty(title, text, button = "Сделать расклад") {
  return `<div class="empty"><div class="empty-symbol">✧</div><h2>${e(title)}</h2><p class="muted">${e(text)}</p><a href="#spread" class="primary">${e(button)}</a></div>`;
}

async function home(version) {
  const day = await api("daily");
  if (version !== routeVersion) return;
  screen.innerHTML = `${profile.chat_selection ? `<section class="status-box"><p class="eyebrow">Вопрос из чата</p><p>${e(profile.chat_selection.question)}</p><button class="primary wide" id="pending">Выбрать карты для чата →</button><p class="hint">Выберите карты здесь, а ответ получите в чате бота.</p></section>` : ""}<p class="eyebrow">Ваше пространство</p><section class="hero"><div class="celestial" aria-hidden="true"><span class="orbit"></span><span class="orbit two"></span><span class="moon"></span><span class="star one">✦</span><span class="star two">✧</span><span class="star three">✦</span></div><h1>У каждого вопроса<br>есть своя Сфера</h1><p>Прислушайтесь к себе. Карты помогут увидеть ситуацию с другой стороны.</p><a class="primary" href="#spread">Сделать расклад <span>↗</span></a></section>${consultationOverview()}
 ${profile.active_operation || activeRequest ? '<button class="row-button" id="resume">Ваш ответ готовится <span>→</span></button>' : profile.last_reading ? `<a class="row-button" href="#reading/${profile.last_reading.id}">Последний расклад <span>→</span></a>` : ""}
 <section class="section"><div class="section-title"><h2>Маленький ритуал дня</h2><span class="hint">${new Date().toLocaleDateString("ru-RU", { day: "numeric", month: "long", timeZone: "Europe/Moscow" })}</span></div><a href="#daily" class="daily-panel"><div><p class="eyebrow">Карта дня</p><h2>${day.card ? e(day.card.name) : "Что подскажет<br>сегодняшний день?"}</h2><p>${day.card ? "Ваше послание уже ждёт вас" : "Выберите одну карту и найдите свой ориентир."}</p><span class="text-link">${day.card ? "Открыть послание" : "Выбрать карту"} →</span></div>${day.card ? `<img src="${e(imageFor(day.card_id))}" alt="${e(day.card.name)}" width="80" style="border-radius:7px;transform:rotate(7deg)">` : '<div class="mini-back" aria-hidden="true"></div>'}</a></section>
 <section class="section"><p class="eyebrow">С чего начать</p><h2>Что вас занимает?</h2><p class="hint">Выберите тему — поможем сформулировать вопрос.</p>${topicButtons()}<button class="secondary wide section" id="custom-question">✧ Задать свой вопрос</button></section>
 `;
  all("[data-suggest]", (el) => {
    chooseTopic(Number(el.dataset.suggest));
    go("spread");
  });
  bind("#resume", () => go("waiting"));
  bind("#custom-question", () => {
    draft = { ...defaultDraft(), source: "custom" };
    selected = []; deck = [];
    save("draft", draft);
    go("spread");
  });
  bind("#pending", () => {
    if (!profile.chat_selection) return;
    chatSelection = {question: profile.chat_selection.question, pending_version: profile.chat_selection.version, kind: "tarot", mode: "manual", theme: "timeline"};
    save("chat-selection", chatSelection);
    selected = []; deck = [];
    go("chat-cards");
  });
}
function spread() {
  screen.innerHTML =
    heading(
      "Тихий момент для себя",
      "О чём спросим карты?",
      "Начните с того, что сейчас занимает ваши мысли.",
    ) +
    `<div class="reading-kinds" role="group" aria-label="Вид гадания"><button class="reading-kind ${draft.kind === "tarot" ? "active" : ""}" data-kind="tarot" aria-pressed="${draft.kind === "tarot"}"><span aria-hidden="true">✧</span><span>Таро<small>Расклад на трёх картах</small></span></button><button class="reading-kind ${draft.kind === "iching" ? "active" : ""}" data-kind="iching" aria-pressed="${draft.kind === "iching"}"><span aria-hidden="true">☯</span><span>Ицзин<small>Книга перемен</small></span></button></div>
 <div class="question-tools"><label class="field" for="question">Ваш вопрос</label><button class="clear-question" id="clear-question" aria-label="Очистить вопрос">Очистить ×</button></div>${topicButtons(true)}<textarea id="question" maxlength="1000" placeholder="Например: что поможет мне найти своё направление?">${e(draft.question)}</textarea><p class="hint question-help">Что происходит сейчас и что вы хотите понять? Пример можно изменить своими словами.</p><div class="counter"><span id="question-count">${draft.question.length}</span>/1000</div>
 ${
   draft.kind === "tarot"
     ? `<section class="section" aria-labelledby="theme-title"><h2 id="theme-title">Выберите тип расклада</h2><p class="hint">Три карты — три взгляда на ваш вопрос.</p><div class="theme-choices" role="group" aria-labelledby="theme-title">${Object.entries(
         catalog.themes,
       )
         .map(
           ([key, value]) =>
             `<button class="theme-choice ${draft.theme === key ? "active" : ""}" data-theme="${e(key)}" aria-pressed="${draft.theme === key}"><span class="theme-icon" aria-hidden="true">${({timeline:"◷",choice:"✧",relationships:"♡"})[key] || "✧"}</span><span class="theme-copy"><strong>${e(({timeline:"Линия времени",choice:"Ситуация и совет",relationships:"Отношения"})[key] || value[0])}</strong><small>${e(value.join(" → "))}</small></span><span class="theme-check" aria-hidden="true">${draft.theme === key ? "✓" : ""}</span></button>`,
         )
         .join(
           "",
         )}</div></section><section class="section"><h2>Как выберем карты?</h2><div class="choices">${[
         [
           "manual",
           "♧",
           "Выбрать самой",
           "Три карты из девяти — доверьтесь ощущению",
         ],
         [
           "random",
           "✧",
           "Карты выберутся сами",
           "Случайный расклад из всей колоды",
         ],
         [
           "own",
           "☾",
           "У меня свои карты",
           "Найдите карты вашей физической колоды",
         ],
       ]
         .map(
           ([mode, icon, title, text]) =>
             `<button class="choice ${draft.mode === mode ? "active" : ""}" data-mode="${mode}" aria-pressed="${draft.mode === mode}"><span class="choice-icon" aria-hidden="true">${icon}</span><span><strong>${title}</strong><small>${text}</small></span></button>`,
         )
         .join("")}</div></section>`
     : '<div class="status-box">Ицзин — книга перемен. Одна из 64 гексаграмм поможет посмотреть на ситуацию и возможный следующий шаг.</div>'
 }
 <p class="hint section">${accessHint()}</p><button class="primary wide" id="next">${profile.access === "none" ? "Выбрать пакет" : draft.kind === "iching" || draft.mode === "random" ? "Получить толкование" : "Перейти к картам"} →</button>`;
  bind(
    "#question",
    (ev) => {
      draft.question = ev.target.value;
      save("draft", draft);
      $("#question-count").textContent = draft.question.length;
    },
    "input",
  );
  bind("#clear-question", () => {
    draft.question = "";
    draft.source = "custom";
    save("draft", draft);
    $("#question").value = "";
    $("#question-count").textContent = "0";
    $("#question").focus();
  });
  all("[data-suggest]", (el) => {
    chooseTopic(Number(el.dataset.suggest));
    spread();
    $("#question").focus();
  });
  all("[data-theme]", (el) => {
    draft.theme = el.dataset.theme;
    save("draft", draft);
    haptic();
    document.querySelectorAll("[data-theme]").forEach((button) => {
      const active = button.dataset.theme === draft.theme;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
      button.querySelector(".theme-check").textContent = active ? "✓" : "";
    });
  });
  all("[data-kind]", (el) => {
    draft.kind = el.dataset.kind;
    save("draft", draft);
    spread();
  });
  all("[data-mode]", (el) => {
    draft.mode = el.dataset.mode;
    save("draft", draft);
    haptic();
    spread();
    track("mode");
  });
  bind("#next", async () => {
    draft.question = $("#question").value.trim();
    save("draft", draft);
    if (draft.question.length < 3)
      throw new Error("Напишите вопрос или тему словами.");
    track("question");
    if (profile.access === "none") return go("shop");
    if (draft.kind === "iching" || draft.mode === "random")
      return startReading();
    selected = [];
    deck = shuffle(Object.keys(catalog.cards)).slice(0, 9);
    go("cards");
  });
}
function shuffle(items) {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}
function cards(chat = false) {
  if (chat && !chatSelection) {
    screen.innerHTML = empty("Выбор карт для чата", "Начните вопрос в чате, затем нажмите «Выбрать карты самой».");
    return;
  }
  pickerDraft = chat ? chatSelection : draft;
  if (!deck.length) deck = shuffle(Object.keys(catalog.cards)).slice(0, 9);
  screen.innerHTML =
    back() +
    heading(
      "Ваш расклад",
      pickerDraft.mode === "own" ? "Какие карты выпали?" : "Выберите три карты",
      chat ? "Выберите карты здесь. Толкование и уточнения будут в чате бота." : "Пусть вас ведёт первое ощущение.",
    ) +
    `<div class="reading-question">${e(pickerDraft.question)}</div><div class="selection-slots">${catalog.themes[pickerDraft.theme].map((label, i) => `<div class="selection-slot ${selected[i] ? "filled" : ""}">${i + 1} · ${e(label)}</div>`).join("")}</div><p class="hint" id="selection-count" role="status">Выбрано ${selected.length} из 3</p>${pickerDraft.mode === "own" ? '<label class="field" for="card-search">Поиск по колоде</label><input id="card-search" placeholder="Название карты" type="search"><div class="card-catalog" id="card-list"></div>' : '<div id="card-list"></div>'}<div class="sticky-action"><button class="primary wide" id="confirm" ${selected.length !== 3 ? "disabled" : ""}>${chat ? "Получить ответ в чате" : "Открыть толкование"}</button></div><button class="secondary wide" id="reset">Выбрать заново</button>`;
  bind("#back", () => go(chat ? "home" : "spread"));
  bind("#reset", () => {
    selected = [];
    deck = shuffle(Object.keys(catalog.cards)).slice(0, 9);
    cards(chat);
  });
  bind("#confirm", () => startReading(chat));
  bind("#card-search", (ev) => paintCards(ev.target.value), "input");
  paintCards();
}
function paintCards(query = "") {
  const own = (pickerDraft || draft).mode === "own";
  const items = (own ? Object.keys(catalog.cards) : deck).filter(
    (id) =>
      !query ||
      catalog.cards[id].name
        .toLocaleLowerCase("ru")
        .includes(query.toLocaleLowerCase("ru")),
  );
  $("#card-list").innerHTML =
    `<div class="cards-grid">${items.map((id, i) => `<div>${card(id, selected.includes(id) ? selected.indexOf(id) : i, { back: !own && !selected.includes(id), selectedCard: selected.includes(id) })}${own ? `<div class="card-label">${e(catalog.cards[id].name)}</div>` : ""}</div>`).join("")}</div>${!items.length ? '<p class="hint">Такой карты не найдено.</p>' : ""}`;
  all("#card-list [data-card]", (el) => {
    const id = el.dataset.card;
    if (selected.includes(id)) selected = selected.filter((x) => x !== id);
    else if (selected.length < 3) selected.push(id);
    else return notify("Вы уже выбрали три карты. Можно снять выбор.");
    haptic();
    paintCards($("#card-search")?.value || "");
    $("#confirm").disabled = selected.length !== 3;
    $("#selection-count").textContent = `Выбрано ${selected.length} из 3`;
    document
      .querySelectorAll(".selection-slot")
      .forEach((slot, i) => slot.classList.toggle("filled", !!selected[i]));
  });
}
async function startReading(chat = false) {
  if (activeRequest || profile.active_operation) return go("waiting");
  activeRequest = {
    ...(chat ? chatSelection : draft),
    channel: chat ? "chat-picker" : "webapp",
    cards: [...selected],
    started_at: Date.now(),
    request_id: crypto.randomUUID(),
  };
  save("request", activeRequest);
  go("waiting");
  track("start");
}
async function waiting(version) {
  screen.innerHTML = waitingMarkup(activeRequest?.question || "");
  let accepted = false;
  try {
    let id = profile.active_operation;
    if (activeRequest) {
      const op = await api(activeRequest.channel === "chat-picker" ? "chat-card-readings" : "readings", activeRequest);
      id = op.id;
    }
    if (!id) {
      screen.innerHTML = empty(
        "Все ответы сохранены",
        "Откройте историю или задайте новый вопрос.",
      );
      return;
    }
    async function poll() {
      if (version !== routeVersion) return;
      try {
        const op = await api("operations/" + id);
        if (version !== routeVersion) return;
        if (op.status === "completed") {
          activeRequest = null;
          save("request", null);
          await refresh();
          const payload = typeof op.payload === "string" ? JSON.parse(op.payload) : op.payload;
          if (payload?.delivery === "chat") {
            chatSelection = null;
            save("chat-selection", null);
            screen.innerHTML = heading("Продолжаем в чате", "Ваш расклад готов") + '<div class="status-box">Ответ появится в чате бота. Там же можно задать уточняющий вопрос.</div><button class="primary wide" id="return-chat">Вернуться в чат</button><a class="text-link" href="#home">На главную приложения</a>';
            bind("#return-chat", () => {
              if (window.WebApp?.close) window.WebApp.close();
              else notify("Закройте окно приложения, чтобы вернуться в чат бота.");
            });
            return;
          }
          go("reading/" + op.result_id);
          return;
        }
        if (op.status === "failed") {
          activeRequest = null;
          save("request", null);
          await refresh();
          screen.innerHTML =
            heading("Попробуем ещё раз", "Ответ не получен") +
            `<div class="status-box error" role="alert">${e(op.error)}</div><a class="primary wide" href="#spread">Вернуться к вопросу</a>`;
          return;
        }
        const payload = typeof op.payload === "string" ? JSON.parse(op.payload) : op.payload;
        const started = new Date(op.created_at).getTime() || activeRequest?.started_at || Date.now();
        const seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
        if (!accepted) {
          screen.innerHTML = waitingMarkup(payload?.question || activeRequest?.question || "", seconds, true);
          accepted = true;
        } else if ($("#waiting-seconds")) $("#waiting-seconds").textContent = seconds;
        operationTimer = setTimeout(poll, 1400);
      } catch (error) {
        showRetry(error, () => waiting(version));
      }
    }
    await poll();
  } catch (error) {
    if (error.status && error.status < 500) {
      activeRequest = null;
      save("request", null);
    }
    showRetry(error, () => waiting(version));
  }
}
function showRetry(error, fn) {
  screen.innerHTML = `<div class="status-box error" role="alert">${e(error.message)}</div><button id="retry" class="primary wide">Повторить проверку</button><a class="text-link" href="#home">На главную</a>`;
  bind("#retry", fn);
}
async function reading(id, version) {
  const value = await api("readings/" + id);
  if (version !== routeVersion) return;
  currentReading = value;
  track("result");
  screen.innerHTML =
    back("history") +
    heading(
      value.divination_type +
        " · " +
        new Date(value.created_at).toLocaleDateString("ru-RU"),
      "Ваше толкование",
    ) +
    `<div class="reading-question">${e(value.question)}</div>` +
    (value.divination_type === "Таро"
      ? `<div class="cards-grid">${value.selected_cards.map((id, i) => `<div>${card(id, i, { zoom: true })}<div class="card-label">${e(value.positions[i])}<br>${e(catalog.cards[id]?.name || id)}</div></div>`).join("")}</div>`
      : `<img class="hexagram-image" src="${e(catalog.hexagrams[value.selected_cards[0]]?.image || "")}" alt="${e(catalog.hexagrams[value.selected_cards[0]]?.name || "Гексаграмма")}">`) +
    `<article class="reading-body">${readingMarkup(value.interpretation, value)}</article><div class="reading-end" aria-hidden="true">— ✧ —</div><p class="hint" style="text-align:center">Карты помогают увидеть варианты.<br>Решение всегда остаётся за вами.</p><section class="section"><h2>Уточним ваш расклад</h2>${value.followups.map((item) => `<div class="followup"><strong>${e(item.question)}</strong><div class="reading-body">${readingMarkup(item.answer, value)}</div></div>`).join("")}${value.remaining ? `<label class="field" for="followup">Что хочется понять глубже?</label><textarea id="followup" maxlength="1000" placeholder="Задайте уточняющий вопрос"></textarea><p class="hint">Осталось уточнений: ${value.remaining}</p><button id="ask" class="primary wide">Задать уточнение</button>` : '<p class="muted">Все уточнения использованы. Вы можете начать новый расклад.</p>'}</section>
 <section class="section"><h2>Сохранить для себя</h2><label class="form-check"><input type="checkbox" id="favorite" ${value.favorite ? "checked" : ""}> В избранное</label><label class="field" for="note">Личная заметка</label><textarea id="note" maxlength="4000" placeholder="Что произошло потом?">${e(value.note)}</textarea><button id="save-note" class="secondary wide">Сохранить заметку</button></section><div class="actions"><a class="primary" href="#spread">Новый расклад</a><a class="secondary" href="#history">В историю</a></div>`;
  bind("#back", () => go("history"));
  zoomCards();
  bind("#ask", () => {
    const question = $("#followup").value.trim();
    if (question.length < 3) throw new Error("Введите уточнение словами.");
    if (activeRequest || profile.active_operation) return go("waiting");
    activeRequest = {
      request_id: crypto.randomUUID(),
      kind: "followup",
      reading_id: value.id,
      question,
    };
    save("request", activeRequest);
    track("followup");
    go("waiting");
  });
  bind("#save-note", async () => {
    await api(`readings/${value.id}/annotation`, {
      favorite: $("#favorite").checked,
      note: $("#note").value,
    });
    notify("Заметка сохранена");
  });
}
function historyShell() {
  screen.innerHTML =
    heading(
      "Ваш путь",
      "История раскладов",
      "К некоторым ответам хочется возвращаться.",
    ) +
    `<a href="#spread" class="primary wide">✧ Новый расклад</a>${profile.active_operation || activeRequest ? '<a href="#waiting" class="pending-history"><span class="pending-dot" aria-hidden="true"></span><span><strong>Ваш ответ готовится</strong><small>Вернуться к ожиданию →</small></span></a>' : ""}<label class="field" for="history-search">Поиск по вопросам</label><input type="search" id="history-search" placeholder="О чём вы спрашивали?"><div class="actions"><select id="history-kind" aria-label="Тип расклада"><option value="">Все расклады</option><option>Таро</option><option>Ицзин</option></select><button id="search" class="secondary">Найти</button></div><label class="form-check"><input type="checkbox" id="favorites">Только избранное</label><div id="history-list"></div><button class="secondary wide section" id="more" hidden>Более ранние расклады</button>`;
  bind("#search", () => loadHistory(false));
  bind("#favorites", () => loadHistory(false), "change");
  bind("#history-kind", () => loadHistory(false), "change");
  bind("#more", () => loadHistory(true));
  return loadHistory(false);
}
async function loadHistory(more) {
  const version = routeVersion;
  const params = new URLSearchParams({
    q: $("#history-search").value,
    kind: $("#history-kind").value,
    favorite: String($("#favorites").checked),
  });
  if (more && nextHistory) params.set("before", nextHistory);
  const result = await api("history?" + params);
  if (version !== routeVersion) return;
  historyItems = more ? [...historyItems, ...result.items] : result.items;
  nextHistory = result.next;
  $("#history-list").innerHTML = historyItems.length
    ? historyItems
        .map(
          (item) =>
            `<a href="#reading/${item.id}" class="history-row"><div class="meta"><span>${new Date(item.created_at).toLocaleDateString("ru-RU", { day: "numeric", month: "long" })}</span><span>${e(item.divination_type)} ${item.favorite ? "✧" : ""}</span></div><h3>${e(item.question)}</h3>${item.preview ? `<p class="history-preview">${e(item.preview)}</p>` : ""}<div class="tiny-cards">${item.divination_type === "Таро" ? item.selected_cards.map((id) => `<img src="${e(imageFor(id))}" alt="${e(catalog.cards[id]?.name || id)}">`).join("") : ""}<span class="text-link" style="margin-left:auto">Открыть →</span></div></a>`,
        )
        .join("")
    : empty(
        "Здесь будут ваши расклады",
        "Пока записей нет или ничего не найдено по вашим фильтрам.",
      );
  $("#more").hidden = !nextHistory;
}
function profileScreen() {
  const b = profile.balance;
  screen.innerHTML =
    heading("Личное пространство", profile.user.first_name || "Ваш профиль") +
    `<section class="summary"><p class="eyebrow">Ваш баланс</p><div class="balance-grid"><div><div class="number">${b.free_divinations_remaining}</div><small>подарочных</small></div><div><div class="number">${b.paid_divinations_remaining}</div><small>оплаченных</small></div></div>${b.unlimited_until ? `<p>Безлимит ${profile.access === "unlimited" ? "до" : "истёк"} ${new Date(b.unlimited_until).toLocaleDateString("ru-RU")}</p>` : ""}<a href="#shop" class="primary wide">Выбрать пакет</a></section>${consultationOverview()}<section class="section"><h2>В своём ритме</h2><label class="form-check"><input type="checkbox" id="daily-sub" ${profile.daily_subscribed ? "checked" : ""}> Напоминание о карте дня</label><p class="hint">В локальной тестовой версии автоматические рассылки отключены. Настройка сохранится.</p><a class="row-button" href="#history">Мои расклады <span>→</span></a></section><section class="section"><h2>Обратная связь</h2><label class="field" for="feedback">Что можно улучшить?</label><textarea id="feedback" maxlength="2000" placeholder="Поделитесь впечатлениями"></textarea><button class="secondary wide" id="send-feedback">Отправить отзыв</button></section>`;
  bind(
    "#daily-sub",
    async (ev) => {
      try {
        await api("settings", { daily_subscribed: ev.target.checked });
        profile.daily_subscribed = ev.target.checked;
        notify("Настройка сохранена");
      } catch (error) {
        ev.target.checked = profile.daily_subscribed;
        throw error;
      }
    },
    "change",
  );
  bind("#send-feedback", async () => {
    await api("feedback", { text: $("#feedback").value });
    $("#feedback").value = "";
    notify("Спасибо! Отзыв сохранён для команды.");
  });
}
async function dailyScreen(version) {
  const day = await api("daily");
  if (version !== routeVersion) return;
  screen.innerHTML =
    back() +
    heading(
      "Ежедневный ритуал",
      "Ваша карта дня",
      day.card
        ? "Небольшой ориентир на сегодня."
        : "Сделайте вдох и выберите одну из трёх карт.",
    ) +
    (day.card
      ? `<div style="max-width:170px;margin:30px auto">${card(day.card_id, 0, { zoom: true })}</div><h2 style="text-align:center">${e(day.card.name)}</h2><div class="reading-body">${e(day.card.meaning)}</div><p class="hint">Эта карта сохранена на сегодня по московскому времени.</p><a href="#spread" class="primary wide">Задать свой вопрос</a>`
      : `<div class="cards-grid daily-cards">${[0, 1, 2].map((i) => `<button class="card" data-daily="${i}" aria-label="Карта дня ${i + 1}"><span class="card-symbol" aria-hidden="true">☾</span></button>`).join("")}</div><p class="hint" style="text-align:center">Бесплатно · одна карта на день</p>`);
  bind("#back", () => go("home"));
  zoomCards();
  all("[data-daily]", async (el) => {
    await api("daily", { choice: Number(el.dataset.daily) });
    haptic();
    await dailyScreen(version);
  });
}
function consultationCard(p) {
  const detailed = p.id === "consult_detailed";
  const points = detailed
    ? ["Что происходит сейчас", "Скрытые моменты ситуации", "Возможное развитие событий", "Совет от карт и рекомендации"]
    : ["Расклад на один вопрос", "Картина вашей ситуации", "Конкретный совет"];
  return `<article class="consultation-card"><div class="consultation-heading"><span class="eyebrow">${detailed ? "Развёрнутая консультация" : "Один вопрос"}</span><span class="consultation-price">${e(p.amount_rub)} ₽</span></div><h2>${e(p.name)}</h2><p class="muted">${detailed ? "Для ситуации, которую хочется рассмотреть глубже и с разных сторон." : "Для конкретного вопроса, когда нужен ориентир и понятный совет."}</p><ul>${points.map(point => `<li>${e(point)}</li>`).join("")}</ul><p class="hint">Таролог: ${e(catalog.consultation.name)}. Личное общение. Контакт откроется после оплаты.</p><button class="primary wide" data-package="${e(p.id)}">Выбрать ${detailed ? "подробный" : "базовый"} разбор →</button></article>`;
}
function shop(consultation = false) {
  screen.innerHTML =
    back() +
    heading(
      consultation ? "Живой разговор" : "Продолжим знакомство",
      consultation
        ? "Консультации с тарологом"
        : "Место для новых вопросов",
      consultation
        ? `${e(catalog.consultation.name)} ответит лично в течение часа в рабочие часы: ${catalog.consultation.hours} МСК.`
        : "Выберите столько раскладов, сколько нужно вам сейчас.",
    ) +
    (consultation
      ? '<p class="hint">Выберите формат личной консультации. Оба варианта проводит таролог, а не автоматический бот.</p>'
      : "") +
    catalog.packages
      .filter((p) => (p.type === "consultation") === consultation)
      .map(
        (p) =>
          consultation ? consultationCard(p) : `<button class="package" data-package="${e(p.id)}"><span>${e(p.name)}<small>${p.type === "consultation" ? "Личное общение" : p.divinations === -1 ? "30 дней · 5 уточнений к раскладу" : "Уточнения включены"}</small></span><span class="price">${p.amount_rub} ₽</span></button>`,
      )
      .join("") +
    (!catalog.payments_enabled
      ? '<div class="status-box hint">В этой локальной версии оплата отключена. Для проверки нужно подключить тестовый магазин ЮKassa.</div>'
      : "") +
    `<div id="checkout"></div><button id="check-payment" class="secondary wide section" ${getSaved("payment") ? "" : "hidden"}>Проверить последний платёж</button>`;
  bind("#back", () => go("profile"));
  all("[data-package]", (el) => checkout(el.dataset.package));
  bind("#check-payment", checkPayment);
}
function checkout(packageId) {
  const p = catalog.packages.find((p) => p.id === packageId);
  $("#checkout").innerHTML =
    `<section class="section"><h2>${e(p.name)}</h2><p>${p.amount_rub} ₽</p><label class="field" for="email">Email для чека</label><input id="email" type="email" autocomplete="email" placeholder="you@example.ru"><p class="hint">Оплата откроется на защищённой странице ЮKassa.</p><button id="pay" class="primary wide" ${catalog.payments_enabled ? "" : "disabled"}>Перейти к тестовой оплате</button></section>`;
  $("#checkout").scrollIntoView({ behavior: "smooth" });
  bind("#pay", async () => {
    if (!$("#email").reportValidity() || !$("#email").value)
      throw new Error("Укажите email для чека.");
    const email = $("#email").value.trim();
    if (
      !paymentRequest ||
      paymentRequest.email !== email ||
      paymentRequest.package !== packageId
    )
      paymentRequest = {
        request_id: crypto.randomUUID(),
        package: packageId,
        email,
      };
    save("purchase-request", paymentRequest);
    $("#pay").disabled = true;
    try {
      const value = await api("payments", paymentRequest);
      save("payment", value.payment_id);
      $("#check-payment").hidden = false;
      track("purchase");
      if (window.WebApp?.openLink)
        window.WebApp.openLink(value.confirmation_url);
      else window.location.href = value.confirmation_url;
    } finally {
      $("#pay").disabled = false;
    }
  });
}
async function checkPayment() {
  const id = getSaved("payment");
  if (!id) return;
  const value = await api("payments/" + encodeURIComponent(id));
  if (value.status === "succeeded") {
    save("payment", null);
    save("purchase-request", null);
    paymentRequest = null;
    await refresh();
    notify("Оплата подтверждена. Баланс обновлён.");
    if (value.contact) {
      $("#checkout").innerHTML =
        `<a class="primary wide" href="${e(value.contact)}" target="_blank" rel="noopener">Написать тарологу</a>`;
    } else go("spread");
  } else
    notify(
      value.status === "canceled"
        ? "Платёж отменён."
        : "Платёж ещё не подтверждён. Повторите проверку после оплаты.",
    );
}
async function render() {
  if (!catalog) return;
  clearTimeout(operationTimer);
  const version = ++routeVersion;
  let route = location.hash.slice(1) || "home";
  if (
    !/^(home|spread|cards|chat-cards|waiting|history|profile|daily|shop|consultation|reading\/\d+)$/.test(
      route,
    )
  )
    route = "home";
  document.querySelectorAll("[data-nav]").forEach((el) => {
    const active =
      el.dataset.nav ===
      (route.startsWith("reading/")
        ? "history"
        : ["cards", "chat-cards", "waiting"].includes(route)
          ? "spread"
          : ["shop", "consultation"].includes(route)
            ? "profile"
            : route);
    el.classList.toggle("active", active);
    if (active) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
  window.scrollTo(0, 0);
  screen.innerHTML = '<p class="hint" role="status">Загрузка…</p>';
  try {
    if (route === "home") {
      await refresh();
      await home(version);
    } else if (route === "spread") spread();
    else if (route === "cards") cards();
    else if (route === "chat-cards") cards(true);
    else if (route === "waiting") await waiting(version);
    else if (route.startsWith("reading/"))
      await reading(route.split("/")[1], version);
    else if (route === "history") {
      track("history");
      await historyShell();
    } else if (route === "profile") {
      await refresh();
      if (version !== routeVersion) return;
      profileScreen();
    } else if (route === "daily") await dailyScreen(version);
    else shop(route === "consultation");
    screen.focus({ preventScroll: true });
  } catch (error) {
    if (version === routeVersion) showRetry(error, render);
  }
}
async function init() {
  const fragment = new URLSearchParams(location.hash.slice(1));
  if (fragment.getAll("WebAppData").length > 1) {
    screen.textContent =
      "Некорректные данные запуска. Откройте приложение через MAX.";
    return;
  }
  initData = window.WebApp?.initData || fragment.get("WebAppData") || "";
  try {
    if (initData) sessionStorage.setItem("sphere:max-init-data", initData);
    else initData = sessionStorage.getItem("sphere:max-init-data") || "";
  } catch {}
  try {
    window.WebApp?.ready();
  } catch {}
  // Preserve launch data in memory, remove it from routing/history.
  if (fragment.has("WebAppData"))
    history.replaceState(null, "", location.pathname + "#home");
  try {
    catalog = await api("catalog");
    await refresh();
    userKey = "sphere:" + profile.user.id + ":";
    draft = getSaved("draft", defaultDraft());
    if (!catalog.themes[draft.theme]) draft.theme = "timeline";
    activeRequest = getSaved("request");
    chatSelection = getSaved("chat-selection");
    paymentRequest = getSaved("purchase-request");
    $("#demo-banner").hidden = !catalog.demo;
    track("open");
    await render();
  } catch (error) {
    screen.innerHTML = `<div class="empty"><div class="empty-symbol">☾</div><h1>Откройте вашу Сферу</h1><p class="muted">${e(error.message)}</p><button id="reload" class="secondary">Попробовать ещё раз</button></div>`;
    bind("#reload", () => location.reload());
  }
}
window.addEventListener("hashchange", render);
window.addEventListener("online", () =>
  notify("Соединение восстановлено. Можно продолжать."),
);
window.addEventListener("offline", () =>
  notify("Нет сети. Ваш вопрос сохранён на устройстве."),
);
bind("#balance", () => go("shop"));
bind("#close-dialog", () => $("#card-dialog").close());
init();
