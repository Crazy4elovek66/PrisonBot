/**
 * PRISONBOT WEBAPP CONTROLLER
 * Full SPA controller for player profile, bosses, prisons, routine, notifications & settings.
 */

const API_BASE = "/api/v1";

// Original Game Assets Icons Map
const GAME_ICONS = {
  rubles: "/static/assets/icons/rubles.webp",
  soap: "/static/assets/icons/soap.webp",
  sugar: "/static/assets/icons/sugar.webp",
  cigarettes: "/static/assets/icons/cigarettes.webp",
  paper: "/static/assets/icons/paper.webp?v=2",
  knife: "/static/assets/icons/knife.webp",
  poison: "/static/assets/icons/poison.webp",
  gunshot: "/static/assets/icons/gunshot.webp",
  energy: "/static/assets/icons/energy.webp",
  authority: "/static/assets/icons/authority.webp",
  respect: "/static/assets/icons/respect.webp",
  rating: "/static/assets/icons/respect.webp",
  biceps: "/static/assets/icons/biceps.webp?v=2",
  keys: "/static/assets/icons/keys.webp",
  talents: "/static/assets/icons/talents.webp?v=2",
  boss: "/static/assets/icons/boss.webp",
  vote: "/static/assets/icons/vote.webp",
  punchChest: "/static/assets/icons/punchChest.webp",
  kickBalls: "/static/assets/icons/kickBalls.webp",
  pokeEyes: "/static/assets/icons/pokeEyes.webp",
  kneeEar: "/static/assets/icons/kneeEar.webp",
  kolsik: "/static/assets/icons/kolsik.webp",
  baul: "/static/assets/icons/baul.webp",
  stash: "/static/assets/icons/stash.webp",
  combo: "/static/assets/icons/combo.webp",
};

function gameIcon(key, alt = "", cls = "game-icon") {
  const src = GAME_ICONS[key];
  if (!src) return alt ? `<span>${alt}</span>` : "";
  return `<img src="${src}" class="${cls}" alt="${alt}" onerror="this.onerror=null;this.replaceWith('${alt || ''}')">`;
}

// Unified Resource Icon Map (Делюги -> Список предприятий & Центр уведомлений)
const RESOURCE_ICON_MAP = {
  authority: { src: "/static/assets/icons/authority.webp", label: "Авторитет" },
  respect: { src: "/static/assets/icons/respect.webp", label: "Уважение" },
  rating: { src: "/static/assets/icons/respect.webp", label: "Уважение" },
  cigarettes: { src: "/static/assets/icons/cigarettes.webp", label: "Папиросы" },
  cigs: { src: "/static/assets/icons/cigarettes.webp", label: "Папиросы" },
  rubles: { src: "/static/assets/icons/rubles.webp", label: "Рубли" },
  coins: { src: "/static/assets/icons/rubles.webp", label: "Рубли" },
  sugar: { src: "/static/assets/icons/sugar.webp", label: "Сахар" },
  paper: { src: "/static/assets/icons/paper.webp", label: "Туалетная бумага" },
  toiletpaper: { src: "/static/assets/icons/paper.webp", label: "Туалетная бумага" },
  toilet_paper: { src: "/static/assets/icons/paper.webp", label: "Туалетная бумага" },
  soap: { src: "/static/assets/icons/soap.webp", label: "Мыло" },
  energy: { src: "/static/assets/icons/energy.webp", label: "Энергия" },
  biceps: { src: "/static/assets/icons/biceps.webp?v=2", label: "Бицепс" },
  talents: { src: "/static/assets/icons/talents.webp?v=2", label: "Таланты" },
  intellect: { src: "/static/assets/icons/talents.webp?v=2", label: "Интеллект" },
  keys: { src: "/static/assets/icons/keys.webp", label: "Ключи" },
  stash: { src: "/static/assets/icons/stash.webp", label: "Нычка" },
  stashes: { src: "/static/assets/icons/stash.webp", label: "Нычка" },
  signet: { src: "/static/assets/icons/signet.webp", label: "Перстень" },
  ore_signet: { src: "/static/assets/icons/ore_signet.webp", label: "Перстень рудный" },
  knife: { src: "/static/assets/icons/knife.webp", label: "Финка" },
  poison: { src: "/static/assets/icons/poison.webp", label: "Яд" },
  gunshot: { src: "/static/assets/icons/gunshot.webp", label: "Самопал" },
};

function resolveResourceMeta(key, fallbackLabel = "") {
  const norm = String(key || "").trim().toLowerCase();
  if (RESOURCE_ICON_MAP[norm]) return RESOURCE_ICON_MAP[norm];
  const noPrefix = norm.replace(/^reward/, "");
  if (RESOURCE_ICON_MAP[noPrefix]) return RESOURCE_ICON_MAP[noPrefix];
  return { src: null, label: fallbackLabel || key || "Ресурс" };
}

function renderResourceIcon(key, cls = "res-icon", fallbackLabel = "") {
  const meta = resolveResourceMeta(key, fallbackLabel);
  if (!meta.src) {
    return `<span class="res-fallback-label" title="${meta.label}">${meta.label}</span>`;
  }
  return `<img src="${meta.src}" class="${cls}" title="${meta.label}" alt="${meta.label}" onerror="this.onerror=null;this.replaceWith('${meta.label}')">`;
}

function renderResourceBadge(reward) {
  if (!reward) return "";
  const rawKey = reward.currency || reward.type || reward.rewardType || "";
  const meta = resolveResourceMeta(rawKey, reward.label || rawKey);
  const amt = Number(reward.amount ?? reward.value ?? 0);
  const iconHtml = meta.src
    ? `<img src="${meta.src}" class="res-icon" title="${meta.label}" alt="${meta.label}">`
    : `<span style="color: var(--muted-foreground); font-size: 10px;">${meta.label}</span>`;
  return `
    <span class="res-badge" title="${meta.label}">
      ${iconHtml}
      <span class="res-amt">+${formatNum(amt)}</span>
    </span>
  `;
}

// Global App State
let activeSection = "main";
let botConfig = {};
let playerProfile = {};
let bossData = {};
let prisonsData = {};
let catalogsData = { bosses: [], prisons: [], masters: [] };
let currentCatFilter = "all";
let currentPrisonId = 1;
let currentIsDay = true;

// Wardrobe & Fitting Room State
let wardrobeData = null;
let wardrobeTab = "regular"; // "regular" or "blind_kolsik"
let wardrobeSubtab = "tattoos"; // "tattoos", "clothing", "cameras"
let wardrobeFilterStatus = "all"; // "all", "owned", "unowned"
let wardrobeFilterCanBuy = false;
let wardrobeFilterBonus = "all"; // "all", "knife", "poison", "gunshot", "energy", "biceps", "special"
let wardrobeFilterSource = "all";
let wardrobeSearchQuery = "";
let fittingRoomPreview = null; // item or set previewed
let imageCache = new Map();

// ============================================================================
// 1. TELEGRAM WEBAPP & AUTH
// ============================================================================

const tg = window.Telegram?.WebApp;
if (tg) {
  try {
    tg.ready();
    tg.expand();
    if (tg.enableClosingConfirmation) {
      tg.enableClosingConfirmation();
    }
  } catch (e) {
    console.warn("Telegram WebApp initialization error:", e);
  }
}

function getAuthHeaders() {
  const headers = { "Content-Type": "application/json" };
  const adminToken = localStorage.getItem("prison_admin_token") || localStorage.getItem("admin_token") || "1488";
  if (adminToken) {
    headers["X-Admin-Token"] = adminToken;
  }
  const tgInitData = tg?.initData;
  if (tgInitData && tgInitData.length > 0) {
    headers["X-Telegram-Init-Data"] = tgInitData;
  }
  return headers;
}

async function apiFetch(endpoint, options = {}) {
  const headers = { ...getAuthHeaders(), ...(options.headers || {}) };
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });

    if (res.status === 401 || res.status === 403) {
      document.getElementById("auth-modal").style.display = "flex";
      throw new Error("Unauthorized");
    }

    const data = await res.json();
    return data;
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    throw err;
  }
}

function updatePing(ms) {
  const el = document.getElementById("hud-ping");
  if (el) {
    el.textContent = `${ms} мс`;
    if (ms < 150) {
      el.style.color = "#34d399";
    } else if (ms < 400) {
      el.style.color = "#fbbf24";
    } else {
      el.style.color = "#f87171";
    }
  }
}

let _pingInFlight = false;
let _pingAbort = null;
let _pingTimerId = null;

async function measurePing() {
  if (_pingInFlight) return;
  _pingInFlight = true;
  if (_pingAbort) {
    try { _pingAbort.abort(); } catch (e) { }
  }
  _pingAbort = new AbortController();
  const timer = setTimeout(() => {
    try { _pingAbort?.abort(); } catch (e) { }
  }, 4000);
  const t0 = performance.now();
  try {
    const res = await fetch(`${API_BASE}/ping`, {
      headers: getAuthHeaders(),
      signal: _pingAbort.signal,
    });
    if (res.ok) {
      const rtt = Math.round(performance.now() - t0);
      const data = await res.json();
      if (data && data.ok) {
        updatePing(rtt);
      }
    }
  } catch (e) {
    // silent fallback
  } finally {
    clearTimeout(timer);
    _pingInFlight = false;
  }
}

function scheduleNextPing() {
  if (_pingTimerId) clearTimeout(_pingTimerId);
  _pingTimerId = setTimeout(async () => {
    if (!document.hidden) {
      await measurePing();
    }
    scheduleNextPing();
  }, 15000);
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3500);
}

// ============================================================================
// STALE-WHILE-REVALIDATE (SWR) CACHE (Мгновенное переключение вкладок 0 мс)
// ============================================================================
const _swrMemoryCache = new Map();

async function fetchWithSWR(cacheKey, fetcher, onData) {
  let cachedEntry = _swrMemoryCache.get(cacheKey);

  if (!cachedEntry) {
    try {
      const stored = sessionStorage.getItem("prison_swr_" + cacheKey);
      if (stored) {
        cachedEntry = JSON.parse(stored);
        _swrMemoryCache.set(cacheKey, cachedEntry);
      }
    } catch (e) { }
  }

  // 1. Немедленный показ кэшированных данных (0 мс)
  if (cachedEntry && cachedEntry.data) {
    try {
      onData(cachedEntry.data, true /* fromCache */);
    } catch (e) {
      console.debug("SWR cached render error:", e);
    }
  }

  // 2. Фоновое обновление с предотвращением лишней перерисовки DOM
  try {
    const freshData = await fetcher();
    const freshJson = JSON.stringify(freshData);
    if (!cachedEntry || cachedEntry.json !== freshJson) {
      _swrMemoryCache.set(cacheKey, { ts: Date.now(), json: freshJson, data: freshData });
      try {
        sessionStorage.setItem("prison_swr_" + cacheKey, JSON.stringify({ ts: Date.now(), json: freshJson, data: freshData }));
      } catch (e) { }
      onData(freshData, false /* fromCache */);
    }
    return freshData;
  } catch (err) {
    if (!cachedEntry) throw err;
    console.warn("SWR background update failed:", err);
  }
}

// ============================================================================
// 2. NAVIGATION & DRAWER
// ============================================================================

const drawer = document.getElementById("drawer");
const drawerOverlay = document.getElementById("drawer-overlay");
const btnDrawerOpen = document.getElementById("btn-drawer-open");
const btnDrawerClose = document.getElementById("btn-drawer-close");
const btnBell = document.getElementById("btn-bell");
const hudSectionTitle = document.getElementById("hud-section-title");

function openDrawer() {
  drawer.classList.add("open");
  drawerOverlay.classList.add("open");
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawerOverlay.classList.remove("open");
}

btnDrawerOpen?.addEventListener("click", openDrawer);
btnDrawerClose?.addEventListener("click", closeDrawer);
drawerOverlay?.addEventListener("click", closeDrawer);

const sectionTitles = {
  main: "Главная (Профиль)",
  bosses: "Боссы и Рейды",
  prisons: "Ходки и Мастера",
  wardrobe: "Тату и Шмот",
  routine: "Делюги",
  friends: "Кореша (Заявки в друзья)",
  raids: "Рейды и Новости",
  notifications: "Центр уведомлений",
  settings: "Настройки (Мозг)",
};

function setTextIfChanged(el, nextText) {
  if (!el) return;
  const s = String(nextText ?? "");
  if (el.textContent !== s) el.textContent = s;
}

function setWidthIfChanged(el, pctStr) {
  if (!el) return;
  if (el.style.width !== pctStr) el.style.width = pctStr;
}

/**
 * Ключевой патчер DOM-списков: обновляет только изменившиеся элементы,
 * сохраняя существующие узлы DOM, фокус, hover и позицию скролла без мерцания.
 */
function reconcileKeyedList(container, items, getKey, getFp, createEl, updateEl, emptyHtml = "") {
  if (!container) return;
  const list = Array.isArray(items) ? items : [];
  if (list.length === 0) {
    if (container.dataset.emptySig !== "empty" || container.children.length !== 1) {
      container.innerHTML = emptyHtml;
      container.dataset.emptySig = "empty";
    }
    return;
  }

  if (container.dataset.emptySig === "empty") {
    container.innerHTML = "";
  }
  container.dataset.emptySig = "";

  const existingMap = new Map();
  Array.from(container.children).forEach(child => {
    const k = child.getAttribute("data-item-key");
    if (k) {
      existingMap.set(k, child);
    } else {
      child.remove();
    }
  });

  const keepKeys = new Set();
  list.forEach((item, idx) => {
    keepKeys.add(String(getKey(item, idx)));
  });

  existingMap.forEach((el, k) => {
    if (!keepKeys.has(k)) {
      el.remove();
      existingMap.delete(k);
    }
  });

  list.forEach((item, idx) => {
    const key = String(getKey(item, idx));
    const fp = String(getFp(item, idx));
    let el = existingMap.get(key);
    if (el) {
      if (el.dataset.fp !== fp) {
        updateEl(el, item, idx);
        el.dataset.fp = fp;
      }
    } else {
      el = createEl(item, idx);
      el.setAttribute("data-item-key", key);
      el.dataset.fp = fp;
    }
    const curAtIdx = container.children[idx] || null;
    if (curAtIdx !== el) {
      container.insertBefore(el, curAtIdx);
    }
  });
}

// Global LiveStateHub cache (warm slices & versions)
const liveSlices = {
  versions: {},
  data: {},
};

// Switch section with instant 0 ms synchronous hydration from warm LiveStateHub slices
function switchSection(secName) {
  if (!sectionTitles[secName]) secName = "main";
  activeSection = secName;

  try {
    document.documentElement.setAttribute("data-active-sec", secName);
    localStorage.setItem("prison_active_section", secName);
    window.location.hash = secName;
  } catch (e) { }

  document.querySelectorAll(".drawer-item").forEach(item => {
    if (item.getAttribute("data-sec") === secName) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  document.querySelectorAll(".section-pane").forEach(pane => {
    if (pane.id === `sec-${secName}`) {
      pane.classList.add("active");
    } else {
      pane.classList.remove("active");
    }
  });

  if (hudSectionTitle) {
    hudSectionTitle.textContent = sectionTitles[secName] || "PrisonBot";
  }

  closeDrawer();

  // Instant 0 ms synchronous render from warm LiveStateHub cache (if already warmed)
  if (secName === "main") {
    if (liveSlices.data.profile) renderProfileData(liveSlices.data.profile);
    else loadProfile();
    loadTalents();
    if (liveSlices.data.collections) {
      if (typeof renderCollectionsData === "function") renderCollectionsData(liveSlices.data.collections);
    } else {
      loadCollections();
    }
  }
  if (secName === "bosses") {
    if (liveSlices.data.boss) renderBossData(liveSlices.data.boss);
    else loadBoss();
    loadBossBuffs();
  }
  if (secName === "prisons") {
    if (liveSlices.data.prisons) renderPrisonsData(liveSlices.data.prisons);
    else loadPrisons();
  }
  if (secName === "wardrobe") loadWardrobe();
  if (secName === "routine") {
    renderBusinesses();
    if (liveSlices.data.monthly) renderMonthlyStateData(liveSlices.data.monthly);
    else loadMonthlyState();
    if (liveSlices.data.bauls) renderBaulsData(liveSlices.data.bauls);
    else loadBauls();
  }
  if (secName === "friends") {
    if (liveSlices.data.friends) renderFriendsSummaryData(liveSlices.data.friends);
    else loadFriendsSummary();
    if (liveSlices.data.friend_requests) renderFriendRequestsData(liveSlices.data.friend_requests);
    else loadFriendRequests();
    if (liveSlices.data.friends_stats) renderFriendsAuditData(liveSlices.data.friends_stats);
    else loadFriendsAudit();
  }
  if (secName === "raids") {
    if (liveSlices.data.radar && typeof renderActivePlayersRadarFromData === "function") {
      renderActivePlayersRadarFromData(liveSlices.data.radar);
    }
    loadRaidsSection({ silent: Boolean(liveSlices.data.radar) });
  }
  if (secName === "notifications") loadNotifications(currentCatFilter);
}

document.querySelectorAll(".drawer-item").forEach(item => {
  item.addEventListener("click", () => {
    const sec = item.getAttribute("data-sec");
    if (sec) switchSection(sec);
  });
});

btnBell?.addEventListener("click", () => {
  switchSection("notifications");
});

// ============================================================================
// 3. NUMBER & TIME FORMATTERS
// ============================================================================

function formatNum(num) {
  if (num === null || num === undefined) return "-";
  return Number(num).toLocaleString("ru-RU");
}

function formatCountdown(sec) {
  if (sec <= 0) return "00:00:00";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// ============================================================================
// 4. DATA LOADERS & RENDERING
// ============================================================================

// --- 4.1 Base State & Config ---
function applyStateData(data) {
  if (!data || !data.success) return;
  liveSlices.data.state = data;

  botConfig = data.config || {};
  updateConfigUI(botConfig);

  const isPaused = data.scheduler?.is_paused;
  const badge = document.getElementById("hud-status-badge");
  const drawerState = document.getElementById("drawer-scheduler-state");
  if (badge) {
    setTextIfChanged(badge, isPaused ? "⏸ Пауза" : "🟢 Активен");
    badge.classList.toggle("paused", Boolean(isPaused));
  }
  if (drawerState) {
    setTextIfChanged(drawerState, isPaused ? "Планировщик: На паузе" : "Планировщик: Активен");
  }

  updateNotificationCounts(data.counts || {});
}

async function refreshState() {
  try {
    const data = await apiFetch("/state");
    applyStateData(data);
    if (!liveSlices.data.monthly) {
      loadMonthlyState();
    }
  } catch (err) {
    console.warn("refreshState error:", err);
  }
}

function updateNotificationCounts(counts) {
  const unread = counts.unread || 0;
  const bellBadge = document.getElementById("hud-bell-count");
  const drawerBadge = document.getElementById("drawer-unread-badge");

  if (bellBadge) {
    bellBadge.textContent = unread;
    bellBadge.style.display = unread > 0 ? "flex" : "none";
  }
  if (drawerBadge) {
    drawerBadge.textContent = unread;
    drawerBadge.style.display = unread > 0 ? "inline-block" : "none";
  }

  // Update pills badges
  ["all", "unread", "bosses", "prisons", "business", "other"].forEach(cat => {
    const el = document.getElementById(`cnt-${cat}`);
    if (el) el.textContent = counts[cat] || 0;
  });
}

function updateConfigUI(cfg) {
  // Sync HUD Master Switch
  const isPaused = Boolean(cfg.is_paused);
  const masterSwitch = document.getElementById("hud-master-switch");
  const masterText = document.getElementById("hud-master-text");
  if (masterSwitch) masterSwitch.checked = !isPaused;
  if (masterText) masterText.textContent = isPaused ? "БОТ: ВЫКЛ" : "БОТ: ВКЛ";

  // Sync checkboxes
  const checkboxKeys = [
    "is_paused", "sleep_mode_enabled", "auto_toilet_paper", "auto_business",
    "auto_beard", "auto_podogrev", "auto_podogrev_send", "auto_katala", "auto_monthly_tasks",
    "auto_boss_enabled", "auto_boss_hits", "auto_boss_summon", "boss_auto_melee",
    "boss_allow_paid_weapons", "auto_prison", "auto_masters", "auto_gifts",
    "auto_friends", "auto_events", "friend_accept_all", "friend_auto_decline_below",
    "auto_kolsik"
  ];
  checkboxKeys.forEach(k => {
    const el = document.getElementById(`cfg-${k}`);
    if (el && cfg[k] !== undefined) {
      el.checked = Boolean(cfg[k]);
    }
  });

  // Sync Boss Queue UI
  updateBossQueueUI(cfg.boss_targets || []);

  // Sync Kolsik Currency
  if (cfg.kolsik_currency) {
    const isRub = cfg.kolsik_currency === "rubles";
    const rubRadio = document.getElementById("kolsik-cur-rubles");
    const papRadio = document.getElementById("kolsik-cur-paper");
    if (rubRadio) rubRadio.checked = isRub;
    if (papRadio) papRadio.checked = !isRub;
  }

  const autoFriendsSec = document.getElementById("cfg-auto_friends_sec");
  if (autoFriendsSec && cfg.auto_friends !== undefined) {
    autoFriendsSec.checked = Boolean(cfg.auto_friends);
  }

  // Filter mode AND / OR
  const filterMode = cfg.friend_filter_mode || "and";
  document.getElementById("btn-filter-mode-and")?.classList.toggle("active", filterMode === "and");
  document.getElementById("btn-filter-mode-or")?.classList.toggle("active", filterMode === "or");

  // Auto-parse news toggle
  const autoParseNewsEl = document.getElementById("cfg-auto_parse_news_raids");
  if (autoParseNewsEl && cfg.auto_parse_news_raids !== undefined) {
    autoParseNewsEl.checked = Boolean(cfg.auto_parse_news_raids);
  }

  // Auto-cleanup controls
  const autoCleanupEl = document.getElementById("cfg-auto_friend_cleanup");
  if (autoCleanupEl && cfg.auto_friend_cleanup !== undefined) {
    autoCleanupEl.checked = Boolean(cfg.auto_friend_cleanup);
  }
  const inactDaysEl = document.getElementById("cfg-friend_cleanup_inactive_days");
  if (inactDaysEl && cfg.friend_cleanup_inactive_days !== undefined) {
    inactDaysEl.value = cfg.friend_cleanup_inactive_days;
  }
  const dailyLimEl = document.getElementById("cfg-friend_cleanup_daily_limit");
  if (dailyLimEl && cfg.friend_cleanup_daily_limit !== undefined) {
    dailyLimEl.value = cfg.friend_cleanup_daily_limit;
  }

  // Sleep hours
  const startEl = document.getElementById("cfg-sleep_start_hour");
  const endEl = document.getElementById("cfg-sleep_end_hour");
  if (startEl && cfg.sleep_start_hour !== undefined) startEl.value = cfg.sleep_start_hour;
  if (endEl && cfg.sleep_end_hour !== undefined) endEl.value = cfg.sleep_end_hour;

  // Friend filter thresholds
  const friendInputs = [
    "friend_min_talents", "friend_min_poison_damage",
    "friend_min_level", "friend_min_authority", "friend_min_biceps"
  ];
  friendInputs.forEach(k => {
    const el = document.getElementById(`cfg-${k}`);
    if (el && cfg[k] !== undefined) {
      el.value = cfg[k];
    }
  });
}

// --- 4.2 Live Profile (Главная) ---
function renderProfileData(data) {
  if (!data || !data.success) return;
  liveSlices.data.profile = data;
  playerProfile = data;
  if (data.characterLayers) {
    window.characterLayers = data.characterLayers;
  }
  const prof = data.profile || {};
  const cur = data.currencies || {};
  const wep = data.weapons || {};

  setTextIfChanged(document.getElementById("player-nickname"), prof.nickname || "Арестант");
  setTextIfChanged(document.getElementById("player-level-badge"), `Ур. ${prof.level || 1}`);
  setTextIfChanged(document.getElementById("player-avatar-badge"), (prof.nickname || "П")[0].toUpperCase());

  setTextIfChanged(document.getElementById("stat-authority"), formatNum(prof.authority));
  setTextIfChanged(document.getElementById("stat-biceps"), formatNum(prof.biceps));
  const totalTalents = window.totalTalentsCached || prof.talentPointsTotal || prof.talents || 0;
  setTextIfChanged(document.getElementById("stat-talents"), formatNum(totalTalents));

  const curEnergy = prof.energy || 0;
  const maxEnergy = prof.maxEnergy || 50;
  setTextIfChanged(document.getElementById("stat-energy"), `${curEnergy}/${maxEnergy}`);
  const energyPct = Math.min(100, Math.round((curEnergy / maxEnergy) * 100));
  setWidthIfChanged(document.getElementById("energy-progress-fill"), `${energyPct}%`);
  updateEnergyTimer();

  setTextIfChanged(document.getElementById("cur-cigs"), formatNum(cur.cigarettes));
  setTextIfChanged(document.getElementById("cur-sugar"), formatNum(cur.sugar));
  setTextIfChanged(document.getElementById("cur-rubles"), formatNum(cur.rubles));
  setTextIfChanged(document.getElementById("cur-paper"), formatNum(cur.paper));
  setTextIfChanged(document.getElementById("cur-soap"), formatNum(cur.soap));

  setTextIfChanged(document.getElementById("inv-poison-count"), `${wep.poisonCount || 0} шт.`);
  setTextIfChanged(document.getElementById("inv-gunshot-count"), `${wep.gunshotCount || 0} шт.`);
  setTextIfChanged(document.getElementById("inv-knife-count"), `${wep.knifeCount || 0} шт.`);

  setTextIfChanged(document.getElementById("boss-poison-count"), `${wep.poisonCount || 0} шт.`);
  setTextIfChanged(document.getElementById("boss-gunshot-count"), `${wep.gunshotCount || 0} шт.`);
  setTextIfChanged(document.getElementById("boss-knife-count"), `${wep.knifeCount || 0} шт.`);

  renderBusinesses();

  if (data.toiletPaper || prof.toiletPaper) {
    updateToiletPaperState(data.toiletPaper || prof.toiletPaper);
  } else {
    updateToiletPaperState({ canClaim: Boolean(prof.canClaimToiletPaper), resetMode: "midnight_msk" });
  }
}

async function loadProfile() {
  try {
    const data = await apiFetch("/live/profile");
    renderProfileData(data);
  } catch (err) {
    console.warn("loadProfile error:", err);
  }
}

let toiletPaperResetState = null;
let _tpRefreshTriggered = false;

function updateToiletPaperState(tpObj) {
  if (!tpObj) return;
  const targetMs = tpObj.nextResetAt
    ? Date.parse(tpObj.nextResetAt)
    : (tpObj.secondsUntilReset ? Date.now() + Number(tpObj.secondsUntilReset) * 1000 : null);
  toiletPaperResetState = {
    canClaim: Boolean(tpObj.canClaim),
    resetMode: tpObj.resetMode || "midnight_msk",
    nextResetMs: Number.isFinite(targetMs) ? targetMs : null,
  };
  _tpRefreshTriggered = false;
  updateToiletPaperTimer();
}

function updateToiletPaperTimer() {
  const badge = document.getElementById("toilet-paper-timer-badge");
  const btn = document.querySelector('.btn-routine-action[data-target="toilet_paper"]');
  if (!badge) return;

  if (!toiletPaperResetState) {
    badge.className = "tp-timer-badge";
    badge.textContent = "⏱️ Загрузка статуса...";
    return;
  }

  if (toiletPaperResetState.canClaim) {
    badge.className = "tp-timer-badge tp-timer-ready";
    badge.textContent = "✅ Доступно сейчас";
    if (btn) btn.disabled = false;
    return;
  }

  const nowMs = Date.now();
  let remSec = 0;
  if (toiletPaperResetState.nextResetMs) {
    remSec = Math.max(0, Math.floor((toiletPaperResetState.nextResetMs - nowMs) / 1000));
  } else {
    // Fallback compute next 00:00 MSK (UTC+3)
    const mskOffsetMs = 3 * 3600 * 1000;
    const nowMsk = new Date(nowMs + mskOffsetMs);
    const nextMidnightMsk = Date.UTC(nowMsk.getUTCFullYear(), nowMsk.getUTCMonth(), nowMsk.getUTCDate() + 1, 0, 0, 0) - mskOffsetMs;
    remSec = Math.max(0, Math.floor((nextMidnightMsk - nowMs) / 1000));
  }

  if (remSec <= 0) {
    badge.className = "tp-timer-badge tp-timer-ready";
    badge.textContent = "✅ Сброс наступил — обновление...";
    if (!_tpRefreshTriggered) {
      _tpRefreshTriggered = true;
      loadProfile();
    }
    return;
  }

  const hh = String(Math.floor(remSec / 3600)).padStart(2, "0");
  const mm = String(Math.floor((remSec % 3600) / 60)).padStart(2, "0");
  const ss = String(remSec % 60).padStart(2, "0");
  badge.className = "tp-timer-badge tp-timer-wait";
  badge.textContent = `⏱️ Сброс через ${hh}:${mm}:${ss}`;
}

function updateEnergyTimer() {
  const el = document.getElementById("energy-restore-timer");
  if (!playerProfile || !playerProfile.profile) return;
  const prof = playerProfile.profile;
  const rawEnergy = Number(prof.energy || 0);
  const maxEnergy = Number(prof.maxEnergy || 50);

  const lastTimeStr = prof.lastEnergyRestoreTime;
  const interval = Number(prof.energyRestoreIntervalSeconds || 300);

  let effectiveEnergy = rawEnergy;
  let remaining = interval;
  if (lastTimeStr && rawEnergy < maxEnergy) {
    const lastSec = new Date(lastTimeStr).getTime() / 1000;
    const nowSec = Date.now() / 1000;
    if (!isNaN(lastSec) && lastSec > 0 && nowSec >= lastSec) {
      const diff = nowSec - lastSec;
      const regenTicks = Math.floor(diff / interval);
      if (regenTicks > 0) {
        effectiveEnergy = Math.min(maxEnergy, rawEnergy + regenTicks);
      }
      const elapsed = diff % interval;
      remaining = Math.max(0, Math.floor(interval - elapsed));
    }
  }

  // Плавная локальная интерполяция энергии в заголовке между пушами сервера
  const statEnergyEl = document.getElementById("stat-energy");
  const fillEnergyEl = document.getElementById("energy-progress-fill");
  if (statEnergyEl) {
    setTextIfChanged(statEnergyEl, `${effectiveEnergy}/${maxEnergy}`);
  }
  if (fillEnergyEl && maxEnergy > 0) {
    const pct = Math.min(100, Math.round((effectiveEnergy / maxEnergy) * 100));
    setWidthIfChanged(fillEnergyEl, `${pct}%`);
  }

  if (!el) return;
  if (effectiveEnergy >= maxEnergy) {
    setTextIfChanged(el, "восстановление: Максимум");
    return;
  }
  if (!lastTimeStr || isNaN(new Date(lastTimeStr).getTime())) {
    setTextIfChanged(el, "восстановление: --:--");
    return;
  }

  const m = Math.floor(remaining / 60);
  const s = Math.floor(remaining % 60);
  setTextIfChanged(el, `восстановление: ${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`);
}

// --- 4.3 Live Boss (Боссы) ---
function renderBossData(data) {
  if (!data || !data.success) return;
  liveSlices.data.boss = data;
  bossData = data;
  if (data.bosses && Array.isArray(data.bosses)) {
    bossCatalog = data.bosses;
    bossCatalogMap = new Map(bossCatalog.map(b => [String(b.id), b.name]));
  }
  const session = data.session;
  const activeCard = document.getElementById("boss-active-card");
  const claimBtn = document.getElementById("btn-boss-claim");
  const manualAttackCard = document.getElementById("boss-manual-attack-card") || document.getElementById("boss-single-attack-card");
  const slotTop = document.getElementById("boss-attack-slot-top");
  const slotBottom = document.getElementById("boss-attack-slot-bottom");

  if (session && session.currentHp > 0) {
    if (activeCard) activeCard.style.display = "block";
    if (manualAttackCard && slotBottom && manualAttackCard.parentElement !== slotBottom) {
      slotBottom.appendChild(manualAttackCard);
    }
    if (manualAttackCard) manualAttackCard.style.display = "block";

    setTextIfChanged(document.getElementById("boss-title"), `⚔️ ${session.title || session.bossName || 'Босс #' + session.bossId}`);
    const bossModes = {
      pacansky: "Пацанский",
      blotnoy: "Блатной",
      avtoritetny: "Авторитетный",
      vorovskoy: "Воровской",
      odin: "В одного",
      brigade: "Бригадный",
    };
    const modeLabel = bossModes[session.mode] || session.mode || "Пацанский";
    setTextIfChanged(document.getElementById("boss-mode-badge"), `Режим: ${modeLabel}`);

    const curHp = session.currentHp || 0;
    const maxHp = session.maxHp || 1;
    const hpPct = Math.max(0, Math.min(100, Math.round((curHp / maxHp) * 100)));

    setTextIfChanged(document.getElementById("boss-hp-numbers"), `${formatNum(curHp)} / ${formatNum(maxHp)}`);
    setTextIfChanged(document.getElementById("boss-hp-percent"), `${hpPct}%`);
    setWidthIfChanged(document.getElementById("boss-hp-fill"), `${hpPct}%`);
    setTextIfChanged(document.getElementById("boss-personal-damage"), formatNum(session.personalDamage || 0));

    if (claimBtn) {
      claimBtn.style.display = data.hasReward ? "inline-flex" : "none";
    }
  } else {
    if (activeCard) activeCard.style.display = "none";
    if (manualAttackCard && slotTop && manualAttackCard.parentElement !== slotTop) {
      slotTop.appendChild(manualAttackCard);
    }
    if (manualAttackCard) manualAttackCard.style.display = "block";
  }

  const wepDmgs = data.weaponDamages || {};
  setTextIfChanged(document.getElementById("boss-poison-damage"), `⚔️ ${wepDmgs.poison || 250}`);
  setTextIfChanged(document.getElementById("boss-gunshot-damage"), `⚔️ ${wepDmgs.gunshot || 60}`);
  setTextIfChanged(document.getElementById("boss-knife-damage"), `⚔️ ${wepDmgs.knife || 30}`);

  updateMeleeTimers();
  if (botConfig) updateBossQueueUI(botConfig.boss_targets || []);
  loadBossPresets();
}

async function loadBoss() {
  try {
    const data = await apiFetch("/live/boss");
    renderBossData(data);
  } catch (err) {
    console.warn("loadBoss error:", err);
  }
}

function updateMeleeTimers() {
  if (!bossData || !bossData.meleeTimestamps) return;
  const nowSec = Date.now() / 1000;

  const attacks = [
    { key: "punchChest", timeKey: "lastPunchChestTime", cdKey: "punchChestCooldownSec" },
    { key: "kickBalls", timeKey: "lastKickBallsTime", cdKey: "kickBallsCooldownSec" },
    { key: "pokeEyes", timeKey: "lastPokeEyesTime", cdKey: "pokeEyesCooldownSec" },
    { key: "kneeEar", timeKey: "lastKneeEarTime", cdKey: "kneeEarCooldownSec" },
  ];

  attacks.forEach(att => {
    const timerEl = document.getElementById(`timer-${att.key}`);
    const btnEl = document.querySelector(`.btn-melee-hit[data-weapon="${att.key}"]`);
    if (!timerEl) return;

    const lastTimeStr = bossData.meleeTimestamps[att.timeKey];
    const cdSec = (bossData.cooldowns && bossData.cooldowns[att.cdKey]) || 28800;

    if (!lastTimeStr) {
      timerEl.textContent = "Готов!";
      timerEl.className = "attack-timer attack-ready";
      if (btnEl) btnEl.disabled = false;
      return;
    }

    const lastSec = new Date(lastTimeStr).getTime() / 1000;
    const diff = (lastSec + cdSec) - nowSec;

    if (diff <= 0) {
      timerEl.textContent = "Готов!";
      timerEl.className = "attack-timer attack-ready";
      if (btnEl) btnEl.disabled = false;
    } else {
      timerEl.textContent = formatCountdown(diff);
      timerEl.className = "attack-timer";
      if (btnEl) btnEl.disabled = true;
    }
  });

  // Boss remaining timer
  const bossTimerEl = document.getElementById("boss-timer");
  if (bossTimerEl && bossData.session?.endsAt) {
    const endsSec = new Date(bossData.session.endsAt).getTime() / 1000;
    const diff = endsSec - nowSec;
    bossTimerEl.textContent = diff > 0 ? formatCountdown(diff) : "Бой завершен";
  }
}

// --- 4.4 Live Prisons (Ходки и Мастера) ---
function renderPrisonsData(data) {
  if (!data || !data.success) return;
  liveSlices.data.prisons = data;
  prisonsData = data;
  currentPrisonId = data.targetId || 1;
  currentIsDay = Boolean(data.isDay);

  const btnDay = document.getElementById("btn-shift-day");
  const btnNight = document.getElementById("btn-shift-night");
  if (btnDay && btnNight) {
    btnDay.className = currentIsDay ? "btn btn-sm btn-primary" : "btn btn-sm btn-secondary";
    btnNight.className = currentIsDay ? "btn btn-sm btn-secondary" : "btn btn-sm btn-primary";
  }

  const currentPrison = (data.prisons || []).find(p => p.id === currentPrisonId);
  const pName = currentPrison?.name || `Тюрьма #${currentPrisonId}`;
  setTextIfChanged(document.getElementById("current-prison-name"), `⛓️ ${pName}`);

  const cps = data.checkpoints || [];
  const stateObj = (data.state && typeof data.state === "object" && data.state.data) ? data.state.data : (data.state || {});
  const pInfo = data.progressInfo || null;

  const totalCps = pInfo ? Number(pInfo.totalCheckpoints || 0) : cps.length;
  const completedCps = pInfo
    ? Number(pInfo.completedCheckpoints || 0)
    : Number((currentIsDay ? stateObj.dayCurrentCheckpoint : stateObj.nightCurrentCheckpoint) || 0);
  const currentClicks = pInfo
    ? Number(pInfo.currentClicks || 0)
    : Number((currentIsDay ? stateObj.dayClicksInCheckpoint : stateObj.nightClicksInCheckpoint) || 0);

  let reqClicks = pInfo ? Number(pInfo.requiredClicks || 1) : 1;
  let energyCost = pInfo ? Number(pInfo.energyCost || 5) : 5;
  if (!pInfo && totalCps > 0) {
    const activeIdx = Math.min(Math.max(completedCps, 0), totalCps - 1);
    const activeCp = cps[activeIdx] || {};
    reqClicks = Number(activeCp.clicksRequired || 1);
    energyCost = Number(activeCp.energyCost || 5);
  }

  let cpPct = 0;
  let cpText = "0 / 0";
  if (pInfo && typeof pInfo.progressPercent === "number") {
    cpPct = Math.max(0, Math.min(100, Math.round(pInfo.progressPercent * 10) / 10));
  } else if (totalCps > 0) {
    if (completedCps >= totalCps) {
      cpPct = 100;
    } else {
      cpPct = Math.max(0, Math.min(100, Math.round(((completedCps + (currentClicks / Math.max(reqClicks, 1))) / totalCps) * 1000) / 10));
    }
  }
  if (totalCps > 0) {
    const curStage = Math.min(totalCps, completedCps + 1);
    const shiftWord = currentIsDay ? "День" : "Ночь";
    cpText = `${shiftWord} ${curStage} / ${totalCps} (шаг ${currentClicks}/${reqClicks})`;
  }

  setTextIfChanged(document.getElementById("prison-checkpoint-text"), cpText);
  setTextIfChanged(document.getElementById("prison-checkpoint-percent"), `${cpPct}%`);
  setWidthIfChanged(document.getElementById("prison-checkpoint-fill"), `${cpPct}%`);

  const workOneBtn = document.getElementById("btn-prison-work-one");
  if (workOneBtn) {
    setTextIfChanged(workOneBtn, `Выполнить 1 действие (⚡ ${energyCost})`);
  }

  renderPrisonsGrid(data.prisons || []);
  renderMastersSelect(data.masters || []);
}

async function loadPrisons(opts = {}) {
  try {
    const q = opts.force ? "?force=1" : "";
    const data = await apiFetch(`/live/prisons${q}`);
    renderPrisonsData(data);
  } catch (err) {
    console.warn("loadPrisons error:", err);
  }
}

function renderPrisonsGrid(prisons) {
  const container = document.getElementById("prisons-catalog-grid");
  if (!container) return;

  const patchTile = (tile, p) => {
    const isSelected = Number(p.id) === Number(currentPrisonId);
    const isUnlocked = p.isUnlocked !== false;
    tile.className = `prison-tile ${isSelected ? 'selected' : ''} ${!isUnlocked ? 'locked' : ''}`;
    tile.setAttribute("data-prison-id", String(p.id));
    setTextIfChanged(tile.querySelector(".prison-tile-name"), p.name || `Тюрьма #${p.id}`);
    setTextIfChanged(tile.querySelector(".prison-tile-lock"), isUnlocked ? "🔓" : "🔒");
    const unlockReq = p.unlockRequirement || p.unlock_requirement || (p.requiredLevel ? `Требуется ур. ${p.requiredLevel}` : "Пройдите предыдущую тюрьму");
    const runsInfo = isUnlocked
      ? `☀️ День: ${p.dayRuns || 0}  |  🌙 Ночь: ${p.nightRuns || 0}`
      : `🔒 ${unlockReq}`;
    setTextIfChanged(tile.querySelector(".prison-tile-meta"), runsInfo);
  };

  reconcileKeyedList(
    container,
    prisons || [],
    p => p.id,
    p => `${p.id}|${p.name}|${Number(p.id) === Number(currentPrisonId)}|${p.isUnlocked !== false}|${p.unlockRequirement || p.unlock_requirement || p.requiredLevel || ''}|${p.dayRuns || 0}|${p.nightRuns || 0}`,
    p => {
      const tile = document.createElement("div");
      tile.setAttribute("data-prison-id", String(p.id));
      tile.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="prison-tile-name" style="font-weight: 700; font-size: 12px; color: #fff;"></span>
          <span class="prison-tile-lock"></span>
        </div>
        <div class="prison-tile-meta" style="font-size: 10px; color: var(--muted-foreground);"></div>
      `;
      tile.addEventListener("click", async () => {
        if (tile.classList.contains("locked")) return;
        currentPrisonId = p.id;
        renderPrisonsGrid(prisonsData.prisons || prisons);
        await apiFetch("/config", {
          method: "PATCH",
          body: JSON.stringify({ prison_target_id: p.id }),
        });
        showToast(`Выбрана тюрьма: ${p.name}`, "info");
        loadPrisons({ force: true });
      });
      patchTile(tile, p);
      return tile;
    },
    (tile, p) => patchTile(tile, p),
    '<div style="color: var(--muted-foreground); font-size: 11px;">Нет доступных тюрем</div>'
  );
}

function renderMastersSelect(masters) {
  const select = document.getElementById("select-master");
  if (!select) return;
  select.innerHTML = "";

  if (masters.length === 0) {
    select.innerHTML = '<option value="">Нет доступных мастеров</option>';
    return;
  }

  masters.forEach(m => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = `${m.name || 'Мастер #' + m.id} (ур. ${m.level || 1})`;
    select.appendChild(opt);
  });
}

// --- 4.5 Live Catalogs ---
async function loadCatalogs() {
  try {
    const data = await apiFetch("/catalogs");
    if (!data.success) return;
    catalogsData = data;

    // Populate Daily Boss Queue Checklist
    renderBossQueueChecklist(data.bosses || []);
  } catch (err) {
    console.warn("loadCatalogs error:", err);
  }
}

function renderBossQueueChecklist(bosses) {
  const container = document.getElementById("boss-queue-checklist");
  if (!container) return;

  const normalizeTarget = item => {
    if (typeof item === "object" && item !== null) {
      return {
        bossId: Number(item.bossId ?? item.boss_id ?? item.id),
        name: item.name || item.bossName,
        mode: item.mode || "pacansky",
        limit: Number(item.limit || 7),
        enabled: item.enabled !== false,
      };
    }
    return { bossId: Number(item), mode: "pacansky", limit: 7, enabled: true };
  };

  const currentTargets = (Array.isArray(botConfig.boss_targets) ? botConfig.boss_targets : []).map(normalizeTarget);
  const patchRow = (row, b) => {
    const isChecked = currentTargets.some(t => t.bossId === Number(b.id) && t.enabled !== false);
    const chk = row.querySelector("input");
    const lbl = row.querySelector(".boss-q-label");
    setTextIfChanged(lbl, `${b.name} (${formatNum(b.hp)} HP)`);
    if (chk && chk.checked !== isChecked) chk.checked = isChecked;
  };

  reconcileKeyedList(
    container,
    bosses || [],
    b => b.id,
    b => `${b.id}|${b.name}|${b.hp}|${currentTargets.some(t => t.bossId === Number(b.id) && t.enabled !== false)}`,
    b => {
      const isChecked = currentTargets.some(t => t.bossId === Number(b.id) && t.enabled !== false);
      const row = document.createElement("label");
      row.setAttribute("data-boss-id", String(b.id));
      row.style.cssText = "display: flex; align-items: center; justify-content: space-between; background: var(--secondary); padding: 6px 10px; border-radius: 6px; cursor: pointer;";
      row.innerHTML = `
        <span class="boss-q-label" style="font-size: 12px; font-weight: 600;">${b.name} (${formatNum(b.hp)} HP)</span>
        <input type="checkbox" value="${b.id}" ${isChecked ? 'checked' : ''} style="width: 16px; height: 16px;">
      `;
      const chk = row.querySelector("input");
      chk.addEventListener("change", async () => {
        let targets = (Array.isArray(botConfig.boss_targets) ? botConfig.boss_targets : []).map(normalizeTarget);
        if (chk.checked) {
          const idx = targets.findIndex(t => t.bossId === Number(b.id));
          if (idx >= 0) {
            targets[idx].enabled = true;
          } else {
            targets.push({ bossId: Number(b.id), name: b.name, mode: "pacansky", limit: 7, enabled: true });
          }
        } else {
          targets = targets.filter(t => t.bossId !== Number(b.id));
        }
        botConfig.boss_targets = targets;
        updateBossQueueUI(targets);
        await apiFetch("/config", {
          method: "PATCH",
          body: JSON.stringify({ boss_targets: targets }),
        });
        showToast("Очередь боссов обновлена", "info");
      });
      return row;
    },
    (row, b) => patchRow(row, b),
    '<div style="color: var(--muted-foreground); font-size: 11px;">Каталог боссов пуст</div>'
  );
}

// --- 4.6 Routine & Businesses ---
let isBusinessesExpanded = false;

function renderBusinesses() {
  const container = document.getElementById("businesses-list");
  const pillsContainer = document.getElementById("biz-pending-pills");
  const bizList = playerProfile.businesses || [];

  // 1. Pending rewards pills in accordion header
  if (pillsContainer) {
    const pending = playerProfile.pendingResources || {};
    const orderedKeys = ["cigarettes", "rubles", "authority", "respect", "rating", "sugar"];
    const pills = [];
    for (const key of orderedKeys) {
      if (pending[key]) {
        pills.push(`<span class="biz-pending-pill">${renderResourceBadge({ currency: key, amount: pending[key] })}</span>`);
      }
    }
    for (const [key, val] of Object.entries(pending)) {
      if (val && !orderedKeys.includes(key)) {
        pills.push(`<span class="biz-pending-pill">${renderResourceBadge({ currency: key, amount: val })}</span>`);
      }
    }
    if (pills.length === 0) {
      pills.push('<span class="biz-pending-pill">0 ресурсов</span>');
    }
    pillsContainer.innerHTML = pills.join("");
  }

  const btnToggleText = document.getElementById("btn-toggle-biz-text");
  const btnToggleIcon = document.getElementById("btn-toggle-biz-icon");
  setTextIfChanged(btnToggleText, `(${bizList.length})`);
  setTextIfChanged(btnToggleIcon, isBusinessesExpanded ? "▴" : "▾");

  if (!container) return;
  const patchBiz = (item, b) => {
    const rewardAmount = b.rewardPerLevel ? b.rewardPerLevel * (b.level || 1) : (b.currentReward || 0);
    const rewardInfo = rewardAmount ? `+${formatNum(rewardAmount)} / 8ч` : "";
    const titleEl = item.querySelector(".biz-title");
    if (titleEl) {
      const zoneBadge = b.prisonName ? ` <span style="font-weight: 500; font-size: 10px; color: var(--muted-foreground);">· ${b.prisonName}</span>` : "";
      const titleHtml = `${b.title || b.name || `Бизнес #${b.businessId || ''}`}${zoneBadge}`;
      if (titleEl.innerHTML !== titleHtml) titleEl.innerHTML = titleHtml;
    }
    const subEl = item.querySelector(".biz-sub");
    if (subEl) {
      const html = `${renderResourceIcon(b.rewardType || 'cigarettes', 'res-icon')} <span>${rewardInfo || 'Доход'}</span>`;
      if (subEl.innerHTML !== html) subEl.innerHTML = html;
    }
    setTextIfChanged(item.querySelector(".biz-lvl"), `Ур. ${b.level || 0}/${b.maxLevel || 8}`);
  };

  reconcileKeyedList(
    container,
    bizList,
    b => `${b.businessId}-${b.prisonId || 1}`,
    b => `${b.businessId}|${b.prisonId}|${b.prisonName || ''}|${b.title}|${b.level}|${b.rewardPerLevel}`,
    b => {
      const item = document.createElement("div");
      item.setAttribute("data-biz-id", String(b.businessId));
      item.style.cssText = "display: flex; justify-content: space-between; align-items: center; background: var(--secondary); padding: 8px 10px; border-radius: 6px;";
      item.innerHTML = `
        <div>
          <div class="biz-title" style="font-weight: 700; color: #fff;"></div>
          <div class="biz-sub" style="font-size: 10px; color: var(--muted-foreground);"></div>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="biz-lvl" style="color: #34d399; font-weight: 700; font-size: 12px;"></span>
          <button class="btn btn-secondary btn-sm btn-upgrade-biz" data-biz-id="${b.businessId}" data-prison-id="${b.prisonId}" style="padding: 3px 8px; font-size: 11px;">
            Улучшить
          </button>
        </div>
      `;
      item.querySelector(".btn-upgrade-biz").addEventListener("click", async () => {
        try {
          const res = await apiFetch("/actions/business/upgrade", {
            method: "POST",
            body: JSON.stringify({ businessId: b.businessId, prisonId: b.prisonId }),
          });
          if (res.success) {
            showToast(`Бизнес ${b.title || ''} успешно улучшен!`, "success");
            loadProfile();
          }
        } catch (e) {
          showToast(`Ошибка улучшения: ${e.message}`, "error");
        }
      });
      patchBiz(item, b);
      return item;
    },
    (item, b) => patchBiz(item, b),
    '<div style="color: var(--muted-foreground); font-size: 11px; padding: 6px;">Нет приобретенных бизнесов</div>'
  );
}

function renderMonthlyStateData(data) {
  const el = document.getElementById("monthly-progress-text");
  if (!el) return;
  if (data) liveSlices.data.monthly = data;
  if (data && data.success && data.state) {
    const st = data.state;
    const completed = st.summary?.completedDisplay || (st.user?.claimedTiers ? `${st.user.claimedTiers.length}/30` : "-");
    const claimable = Array.isArray(st.user?.claimableTiers) ? st.user.claimableTiers.length : 0;
    let text = `Выполнено этапов: <b>${completed}</b> • Готово к сбору наград: <b>${claimable}</b>`;
    if (st.today?.title) {
      const cur = Number(st.today.current ?? st.today.progress ?? 0);
      const tgt = Number(st.today.target ?? 0);
      const progSuffix = tgt > 0 ? ` (${cur}/${tgt} выполнено)` : "";
      text += ` • Сегодня: <i>${st.today.title}</i>${progSuffix}`;
    }
    if (el.innerHTML !== text) el.innerHTML = text;
  } else {
    setTextIfChanged(el, "Ежемесячные задания и награды активны");
  }
}

async function loadMonthlyState() {
  const el = document.getElementById("monthly-progress-text");
  if (!el) return;
  try {
    const data = await apiFetch("/monthly/state");
    renderMonthlyStateData(data);
  } catch (e) {
    setTextIfChanged(el, "Месячные делюги активны");
  }
}

async function loadRoutine() {
  renderBusinesses();
  loadMonthlyState();
}

function updateBusinessCountdown() {
  const el = document.getElementById("biz-countdown");
  const card = document.getElementById("biz-collect-card");
  const collectBtn = document.getElementById("btn-collect-business");
  if (!el) return;

  let diff = 0;
  const nextAtStr = playerProfile.nextBusinessCollectAt;
  const lastCollectStr = playerProfile.lastBusinessCollectTime || playerProfile.lastCollectTime;

  if (nextAtStr && !isNaN(Date.parse(nextAtStr))) {
    diff = (Date.parse(nextAtStr) - Date.now()) / 1000;
  } else if (lastCollectStr && !isNaN(Date.parse(lastCollectStr))) {
    const lastSec = Date.parse(lastCollectStr) / 1000;
    const nowSec = Date.now() / 1000;
    const cdSec = Number(playerProfile.businessCooldownTotalSec || 8 * 3600);
    diff = (lastSec + cdSec) - nowSec;
  }

  if (!diff || diff <= 0) {
    el.textContent = "Готово!";
    el.style.color = "#34d399";
    if (card) card.classList.remove("business-cooldown-locked");
    if (collectBtn) {
      collectBtn.disabled = false;
      setTextIfChanged(collectBtn, "💰 Собрать прибыль сейчас");
    }
  } else {
    const cdStr = formatCountdown(diff);
    el.textContent = cdStr;
    el.style.color = "#fbbf24";
    if (card) card.classList.add("business-cooldown-locked");
    if (collectBtn) {
      collectBtn.disabled = true;
      setTextIfChanged(collectBtn, `⏳ Доступно через ${cdStr}`);
    }
  }
}

// --- 4.7 Notifications (Центр дропов) ---
async function loadNotifications(category = "all") {
  currentCatFilter = category;
  const container = document.getElementById("notifications-list");
  if (!container) return;

  try {
    const data = await apiFetch(`/notifications?category=${category}&limit=50`);
    if (!data.success) return;

    updateNotificationCounts(data.counts || {});
    container.innerHTML = "";

    const notifs = data.notifications || [];
    if (notifs.length === 0) {
      const isPaused = Boolean(botConfig && botConfig.is_paused);
      const activeAutos = autoConfigKeys.filter(k => botConfig && botConfig[k]).length;
      container.innerHTML = `
        <div class="card" style="text-align: center; color: var(--muted-foreground); padding: 32px 16px;">
          <div style="font-size: 28px; margin-bottom: 8px;">🔔</div>
          <div style="font-weight: 700; font-size: 14px; color: #fff; margin-bottom: 4px;">
            ${isPaused ? '⏸️ Бот на паузе' : '🟢 Бот активен'}
          </div>
          <div style="font-size: 11px; margin-bottom: 12px; color: var(--muted-foreground);">
            Включено авто-функций: <b style="color: var(--primary);">${activeAutos}</b>. Лента наполняется при выполнении действий и завершении циклов.
          </div>
          <button id="btn-check-events-now" class="btn btn-primary btn-sm" style="display: inline-flex; align-items: center; gap: 6px; margin: 0 auto;">
            ⚡ Проверить события сейчас
          </button>
        </div>
      `;

      document.getElementById("btn-check-events-now")?.addEventListener("click", async () => {
        const btn = document.getElementById("btn-check-events-now");
        if (btn) {
          btn.disabled = true;
          btn.textContent = "⏳ Проверка событий...";
        }
        try {
          const res = await apiFetch("/actions/run-now", { method: "POST" });
          if (res.success) {
            showToast("События проверены", "success");
            loadNotifications(currentCatFilter);
          }
        } catch (err) {
          showToast(`Ошибка проверки: ${err.message}`, "error");
        } finally {
          if (btn) {
            btn.disabled = false;
            btn.textContent = "⚡ Проверить события сейчас";
          }
        }
      });
      return;
    }

    notifs.forEach(n => {
      const card = document.createElement("div");
      const meta = n.meta_json || {};
      const isDefeat = meta.type === "boss_defeat" || meta.outcome === "defeat";
      card.className = `notif-card notif-${n.category || 'other'}${isDefeat ? ' notif-defeat' : ''}${n.is_read ? ' is-read' : ''}`;

      let rewardsHtml = "";
      if (Array.isArray(n.rewards) && n.rewards.length > 0) {
        rewardsHtml = `
          <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
            ${n.rewards.map(r => renderResourceBadge(r)).join("")}
          </div>
        `;
      }

      let defeatBarHtml = "";
      if (isDefeat && meta.max_hp) {
        const remHp = Math.max(0, Number(meta.remaining_hp || 0));
        const maxHp = Math.max(1, Number(meta.max_hp || 1));
        const hpPct = Math.max(0, Math.min(100, Math.round((remHp / maxHp) * 1000) / 10));
        defeatBarHtml = `
          <div class="defeat-hp-wrap">
            <div class="defeat-hp-label">
              <span>Осталось HP: ${formatNum(remHp)} / ${formatNum(maxHp)}</span>
              <span>${hpPct}%</span>
            </div>
            <div class="defeat-hp-bar">
              <div class="defeat-hp-fill" style="width: ${hpPct}%;"></div>
            </div>
          </div>
        `;
      }

      const rawDrops = Array.isArray(n.drops) && n.drops.length > 0
        ? n.drops
        : (Array.isArray(meta.cosmetic_drops) ? meta.cosmetic_drops : []);

      let dropsHtml = "";
      const clickableDrops = [];
      if (rawDrops.length > 0) {
        dropsHtml = `
          <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
            ${rawDrops.map((d, idx) => {
          const isCosmetic = ["tattoo", "clothing", "room", "camera", "item"].includes(String(d.type || d.kind || "").toLowerCase())
            && (d.itemId || d.setId || d.imageUrl || String(d.kind) === "tattoo" || String(d.kind) === "clothing" || String(d.type) === "room");
          if (isCosmetic) {
            clickableDrops.push({ idx, drop: d });
          }
          return `
                <span class="drop-pill ${isCosmetic ? 'drop-pill-clickable' : ''}" ${isCosmetic ? `data-drop-idx="${idx}" title="Нажмите для примерки"` : ''}>
                  <span>${isCosmetic ? '👕 ' : '🎁 '}${d.title || d.name || 'Дроп'}</span>
                  ${d.subtitle ? `<span style="font-size: 9px; opacity: 0.8;">(${d.subtitle})</span>` : ''}
                </span>
              `;
        }).join("")}
          </div>
        `;
      }

      const timeStr = n.created_at ? new Date(n.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : "";

      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <div>
            <div style="font-weight: 700; font-size: 13px; color: #fff;">${n.title || 'Событие'}</div>
            ${n.subtitle ? `<div style="font-size: 11px; color: var(--muted-foreground);">${n.subtitle}</div>` : ''}
          </div>
          <span style="font-size: 10px; color: var(--muted-foreground);">${timeStr}</span>
        </div>
        ${defeatBarHtml}
        ${rewardsHtml}
        ${dropsHtml}
      `;

      clickableDrops.forEach(({ idx, drop }) => {
        const pillEl = card.querySelector(`.drop-pill-clickable[data-drop-idx="${idx}"]`);
        pillEl?.addEventListener("click", () => {
          openItemPreviewModal({
            type: drop.type || drop.kind || "tattoo",
            itemId: drop.itemId || drop.id || null,
            setId: drop.setId || null,
            name: drop.name || drop.title || "",
            imageUrl: drop.imageUrl || drop.previewUrl || "",
            zone: drop.zone || 1,
          });
        });
      });

      container.appendChild(card);
    });
  } catch (err) {
    console.warn("loadNotifications error:", err);
  }
}

// Notification Filter Pills
document.querySelectorAll(".filter-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    const cat = pill.getAttribute("data-cat") || "all";
    loadNotifications(cat);
  });
});

document.getElementById("btn-read-all-notifs")?.addEventListener("click", async () => {
  await apiFetch("/notifications/read-all", { method: "POST" });
  document.querySelectorAll("#notifications-list .notif-card").forEach(el => el.classList.add("is-read"));
  showToast("Все уведомления прочитаны", "info");
  loadNotifications(currentCatFilter);
});

document.getElementById("btn-clear-notifs")?.addEventListener("click", async () => {
  await apiFetch("/notifications?read_only=true", { method: "DELETE" });
  showToast("Прочитанные уведомления очищены", "info");
  loadNotifications(currentCatFilter);
});

const SOURCE_LABELS = {
  radar: "📡 Радар",
  radar_batch: "📡 Радар (пакет)",
  guild: "🏰 Из бригад",
  weekly_top: "🏆 Топ недели",
  achievements: "🎖️ Достижения",
  news_ad: "📰 Новости",
  tg_channel: "📡 ТГ-каналы",
  auto_outreach: "🤖 Авто-набор",
  raid: "⚔️ Рейд",
  import: "📋 Импорт",
  manual: "✋ Вручную",
  search: "🔍 Поиск",
  top: "🏆 Топ",
  accessible: "👥 Доступные",
};

// --- 4.8.1 Friends Summary (Счетчик, Дельта 24ч, Конверсия) ---
function renderFriendsSummaryData(data) {
  const countEl = document.getElementById("friends-total-count");
  const deltaBadge = document.getElementById("friends-delta-badge");
  const baseInfo = document.getElementById("friends-baseline-info");
  const tbody = document.getElementById("friends-conversion-table-body");
  if (!countEl || !data) return;

  liveSlices.data.friends = data;
  const total = (data.totalFriends !== undefined ? data.totalFriends : data.friendsCount) || 0;
  const delta = data.delta24h || 0;
  const base = data.baselineCount !== undefined ? data.baselineCount : total;

  setTextIfChanged(countEl, formatNum(total));

  if (deltaBadge) {
    if (delta > 0) {
      deltaBadge.className = "friends-delta-pos";
      setTextIfChanged(deltaBadge, `(+${delta})`);
    } else if (delta < 0) {
      deltaBadge.className = "friends-delta-neg";
      setTextIfChanged(deltaBadge, `(${delta})`);
    } else {
      deltaBadge.className = "friends-delta-zero";
      setTextIfChanged(deltaBadge, "(0)");
    }
    const timeStr = data.baselineAt ? new Date(data.baselineAt).toLocaleString() : "";
    deltaBadge.title = `Изменение за 24ч (база: ${base} корешей, замер: ${timeStr})`;
  }

  if (baseInfo) {
    setTextIfChanged(baseInfo, data.has24hHistory ? `База 24ч: ${formatNum(base)}` : `База: ${formatNum(base)} (история <24ч)`);
  }

  if (tbody) {
    const sources = data.conversionBySource || [];
    reconcileKeyedList(
      tbody,
      sources,
      s => s.source,
      s => `${s.source}|${s.sent}|${s.accepted}|${s.conversionRate}|${s.avgDamage}`,
      s => {
        const srcName = SOURCE_LABELS[s.source] || s.source || "Неизвестно";
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="col-src" style="text-align: left; font-weight: 600;">${srcName}</td>
          <td class="col-sent" style="text-align: right;">${s.sent}</td>
          <td class="col-acc" style="text-align: right; color: #22c55e;">${s.accepted}</td>
          <td class="col-rate" style="text-align: right; font-weight: 700;">${s.conversionRate}%</td>
          <td class="col-dmg" style="text-align: right; color: #fbbf24;">${s.avgDamage > 0 ? formatNum(s.avgDamage) : '-'}</td>
        `;
        return tr;
      },
      (tr, s) => {
        setTextIfChanged(tr.querySelector(".col-sent"), s.sent);
        setTextIfChanged(tr.querySelector(".col-acc"), s.accepted);
        setTextIfChanged(tr.querySelector(".col-rate"), `${s.conversionRate}%`);
        setTextIfChanged(tr.querySelector(".col-dmg"), s.avgDamage > 0 ? formatNum(s.avgDamage) : '-');
      },
      '<tr><td colspan="5" style="text-align: center; color: var(--muted-foreground); padding: 8px;">Нет данных по отправленным заявкам</td></tr>'
    );
  }
}

async function loadFriendsSummary() {
  const countEl = document.getElementById("friends-total-count");
  if (!countEl) return;
  try {
    await fetchWithSWR("friends_summary", () => apiFetch("/friends/summary"), data => renderFriendsSummaryData(data));
  } catch (err) {
    console.warn("Failed to load friends summary:", err);
  }
}

// --- 4.8.2 Friends Audit & Cleanup ---
let currentAuditSort = "damage_7d";

function renderFriendsAuditData(data) {
  const container = document.getElementById("friends-audit-list");
  if (!container || !data) return;
  liveSlices.data.friends_stats = data;
  const friends = data.friends || [];

  const patchCard = (card, f) => {
    const isWl = Boolean(f.isWhitelisted);
    card.setAttribute("data-user-id", String(f.userId));
    card.style.border = isWl ? "1px solid rgba(234, 179, 8, 0.4)" : "1px solid var(--border-color, #383838)";
    const cb = card.querySelector(".audit-friend-cb");
    if (cb) cb.disabled = isWl;
    setTextIfChanged(card.querySelector(".fa-nick"), f.nickname);
    setTextIfChanged(card.querySelector(".fa-meta"), `ID: ${f.userId} · Ур. ${f.level} · 👑 ${formatNum(f.authority)}`);
    const btnWl = card.querySelector(".btn-toggle-whitelist");
    if (btnWl) {
      btnWl.className = `btn btn-xs ${isWl ? "btn-warning btn-whitelist-active" : "btn-secondary"} btn-toggle-whitelist`;
      btnWl.setAttribute("data-whitelisted", String(isWl));
      btnWl.disabled = false;
      setTextIfChanged(btnWl, isWl ? "🛡️ Защищен" : "⭐ Защитить");
    }
    setTextIfChanged(card.querySelector(".fa-dmg7"), f.damage7d > 0 ? formatNum(f.damage7d) : "-");
    setTextIfChanged(card.querySelector(".fa-dmgtot"), f.totalDamageToMyBosses > 0 ? formatNum(f.totalDamageToMyBosses) : "-");
    const inactEl = card.querySelector(".fa-inact");
    if (inactEl) {
      setTextIfChanged(inactEl, `${f.daysInactive} дн.`);
      inactEl.style.color = f.daysInactive >= 14 ? "#e62e1e" : "var(--muted-foreground)";
    }
  };

  reconcileKeyedList(
    container,
    friends,
    f => f.userId,
    f => `${f.userId}|${f.nickname}|${f.level}|${f.authority}|${f.damage7d}|${f.totalDamageToMyBosses}|${f.daysInactive}|${Boolean(f.isWhitelisted)}`,
    f => {
      const initial = (f.nickname || "К")[0].toUpperCase();
      const avatarHtml = f.photoUrl
        ? `<img src="${f.photoUrl}" alt="" style="width: 28px; height: 28px; border-radius: 50%; object-fit: cover;" onerror="this.onerror=null;this.parentElement.textContent='${initial}'">`
        : `<span style="background: var(--primary); color: #000; width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800;">${initial}</span>`;
      const isWl = Boolean(f.isWhitelisted);
      const card = document.createElement("div");
      card.className = "friend-card";
      card.setAttribute("data-user-id", String(f.userId));
      card.style.cssText = "display: flex; flex-direction: column; gap: 6px; padding: 10px;";
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <input type="checkbox" class="audit-friend-cb" data-user-id="${f.userId}" ${isWl ? 'disabled' : ''}>
            ${avatarHtml}
            <div>
              <div class="fa-nick" style="font-weight: 700; font-size: 13px; color: #fff;"></div>
              <div class="fa-meta" style="font-size: 10px; color: var(--muted-foreground);"></div>
            </div>
          </div>
          <button class="btn btn-xs btn-toggle-whitelist" data-user-id="${f.userId}"></button>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 4px;">
          <div class="stat-chip" style="padding: 4px;">
            <div class="stat-chip-lbl" style="font-size: 9px;">Урон 7д</div>
            <div class="stat-chip-val fa-dmg7" style="color: #22c55e; font-size: 12px;"></div>
          </div>
          <div class="stat-chip" style="padding: 4px;">
            <div class="stat-chip-lbl" style="font-size: 9px;">Всего в боссов</div>
            <div class="stat-chip-val fa-dmgtot" style="color: #fbbf24; font-size: 12px;"></div>
          </div>
          <div class="stat-chip" style="padding: 4px;">
            <div class="stat-chip-lbl" style="font-size: 9px;">Неактивен</div>
            <div class="stat-chip-val fa-inact" style="font-size: 12px;"></div>
          </div>
        </div>
      `;
      const btnWl = card.querySelector(".btn-toggle-whitelist");
      btnWl?.addEventListener("click", async () => {
        btnWl.disabled = true;
        const curWl = btnWl.getAttribute("data-whitelisted") === "true";
        try {
          await apiFetch("/friends/whitelist", {
            method: "POST",
            body: JSON.stringify({ userId: f.userId, whitelisted: !curWl }),
          });
          showToast(!curWl ? `Друг ${f.nickname} защищен от кика` : `Защита снята с ${f.nickname}`, "info");
          loadFriendsAudit();
        } catch (e) {
          showToast(`Ошибка: ${e.message}`, "error");
          btnWl.disabled = false;
        }
      });
      patchCard(card, f);
      return card;
    },
    (card, f) => patchCard(card, f),
    '<div style="color: var(--muted-foreground); text-align: center; padding: 16px; font-size: 12px;">Список друзей пуст. Запустите цикл или обновите профили.</div>'
  );
}

async function loadFriendsAudit() {
  const container = document.getElementById("friends-audit-list");
  if (!container) return;
  try {
    const data = await apiFetch(`/friends/stats?sort=${currentAuditSort}&limit=100`);
    renderFriendsAuditData(data);
  } catch (err) {
    if (!container.querySelector(".friend-card")) {
      container.innerHTML = `<div style="color: var(--destructive); text-align: center; padding: 16px; font-size: 12px;">Ошибка загрузки аудита: ${err.message}</div>`;
    }
  }
}

// --- 4.8 Friend Requests (Кореша) ---
function renderFriendRequestsData(data) {
  const container = document.getElementById("friend-requests-list");
  if (!container || !data) return;
  liveSlices.data.friend_requests = data;
  const reqs = data.requests || data.items || [];
  const countEl = document.getElementById("friend-requests-count");
  const badgeEl = document.getElementById("drawer-friends-badge");
  setTextIfChanged(countEl, reqs.length);
  if (badgeEl) {
    setTextIfChanged(badgeEl, reqs.length);
    badgeEl.style.display = reqs.length > 0 ? "inline-block" : "none";
  }

  reconcileKeyedList(
    container,
    reqs,
    r => r.userId || r.fromUserId || r.id,
    r => `${r.userId || r.fromUserId || r.id}|${r.authority}|${r.level || r.lvl}|${r.talentsCount || r.talents}`,
    r => {
      const uId = r.userId || r.fromUserId || r.id;
      const nick = r.nickname || `Игрок #${uId}`;
      const talents = r.talents !== undefined ? r.talents : (r.talentsCount || r.TalentsCount || 0);
      const wDmg = r.weaponDamage || r.WeaponDamage || {};
      const poison = r.poisonDamage !== undefined ? r.poisonDamage : (wDmg.poison || wDmg.Poison || 0);
      const gunshot = r.gunshotDamage !== undefined ? r.gunshotDamage : (wDmg.gunshot || wDmg.Gunshot || 0);
      const knife = r.knifeDamage !== undefined ? r.knifeDamage : (wDmg.knife || wDmg.Knife || 0);
      const lvl = r.level !== undefined ? r.level : (r.lvl || 0);
      const auth = r.authority !== undefined ? r.authority : 0;
      const biceps = (r.biceps !== null && r.biceps !== undefined && r.biceps > 0) ? r.biceps : null;
      const bicepsHtml = biceps !== null ? `
        <div class="stat-chip"><div class="stat-chip-lbl">${gameIcon('biceps', '', 'game-icon-sm')} Бицуха</div><div class="stat-chip-val" style="color: #f97316;">${formatNum(biceps)}</div></div>
      ` : '';

      const card = document.createElement("div");
      card.className = "friend-card";
      card.setAttribute("data-user-id", String(uId));
      card.innerHTML = `
        <div class="friend-header">
          <div class="friend-name">
            <span style="background: var(--primary); color: #000; width: 22px; height: 22px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800;">${nick[0].toUpperCase()}</span>
            <span>${nick}</span>
            <span style="font-size: 10px; background: rgba(255,255,255,0.1); padding: 1px 5px; border-radius: 4px;">Ур. ${lvl}</span>
          </div>
          <span style="font-size: 10px; color: var(--muted-foreground);">ID: ${uId}</span>
        </div>
        <div class="friend-stats-grid">
          <div class="stat-chip"><div class="stat-chip-lbl">Уровень</div><div class="stat-chip-val" style="color: #a78bfa;">${lvl}</div></div>
          <div class="stat-chip"><div class="stat-chip-lbl">${gameIcon('authority', '', 'game-icon-sm')} Авторитет</div><div class="stat-chip-val" style="color: #fbbf24;">${formatNum(auth)}</div></div>
          ${bicepsHtml}
          <div class="stat-chip"><div class="stat-chip-lbl">${gameIcon('talents', '', 'game-icon-sm')} Таланты</div><div class="stat-chip-val" style="color: #60a5fa;">${formatNum(talents)}</div></div>
          <div class="stat-chip"><div class="stat-chip-lbl">${gameIcon('knife', '', 'game-icon-sm')} Финка</div><div class="stat-chip-val" style="color: #f87171;">${formatNum(knife)}</div></div>
          <div class="stat-chip"><div class="stat-chip-lbl">${gameIcon('poison', '', 'game-icon-sm')} Яд</div><div class="stat-chip-val" style="color: #34d399;">${formatNum(poison)}</div></div>
          <div class="stat-chip"><div class="stat-chip-lbl">${gameIcon('gunshot', '', 'game-icon-sm')} Самопал</div><div class="stat-chip-val" style="color: #fbbf24;">${formatNum(gunshot)}</div></div>
        </div>
        <div class="friend-actions">
          <button class="btn btn-primary btn-sm btn-accept-friend" data-user-id="${uId}" style="flex: 1;">✓ Принять</button>
          <button class="btn btn-secondary btn-sm btn-decline-friend" data-user-id="${uId}" style="flex: 1; color: var(--destructive);">✕ Отклонить</button>
        </div>
      `;

      const btnAccept = card.querySelector(".btn-accept-friend");
      const btnDecline = card.querySelector(".btn-decline-friend");

      const updateFriendBadgeAndCount = () => {
        const currentCount = parseInt(countEl?.textContent || "0", 10);
        const newCount = Math.max(0, currentCount - 1);
        if (countEl) countEl.textContent = newCount;
        if (badgeEl) {
          badgeEl.textContent = newCount;
          badgeEl.style.display = newCount > 0 ? "inline-block" : "none";
        }
        if (newCount === 0) {
          container.innerHTML = '<div style="color: var(--muted-foreground); font-size: 12px; text-align: center; padding: 16px;">Входящих заявок в друзья нет</div>';
          container.dataset.emptySig = "empty";
        }
      };

      const animateCardRemoval = () => {
        card.style.transition = "opacity 0.25s ease, transform 0.25s ease";
        card.style.opacity = "0";
        card.style.transform = "translateY(-6px)";
        setTimeout(() => {
          card.remove();
          updateFriendBadgeAndCount();
        }, 250);
      };

      btnAccept.addEventListener("click", async () => {
        btnAccept.disabled = true;
        btnDecline.disabled = true;
        const origText = btnAccept.innerHTML;
        btnAccept.textContent = "...";
        try {
          const res = await apiFetch("/actions/friendship/accept", {
            method: "POST",
            body: JSON.stringify({ fromUserId: uId }),
          });
          if (res.success) {
            showToast(`Заявка от ${nick} принята`, "success");
            animateCardRemoval();
          } else {
            showToast(res.error || res.detail || "Не удалось принять заявку", "error");
            btnAccept.disabled = false;
            btnDecline.disabled = false;
            btnAccept.innerHTML = origText;
          }
        } catch (e) {
          showToast(`Ошибка: ${e.message}`, "error");
          btnAccept.disabled = false;
          btnDecline.disabled = false;
          btnAccept.innerHTML = origText;
        }
      });

      btnDecline.addEventListener("click", async () => {
        btnAccept.disabled = true;
        btnDecline.disabled = true;
        const origText = btnDecline.innerHTML;
        btnDecline.textContent = "...";
        try {
          const res = await apiFetch("/actions/friendship/decline", {
            method: "POST",
            body: JSON.stringify({ fromUserId: uId }),
          });
          if (res.success) {
            showToast(`Заявка от ${nick} отклонена`, "info");
            animateCardRemoval();
          } else {
            showToast(res.error || res.detail || "Не удалось отклонить заявку", "error");
            btnAccept.disabled = false;
            btnDecline.disabled = false;
            btnDecline.innerHTML = origText;
          }
        } catch (e) {
          showToast(`Ошибка: ${e.message}`, "error");
          btnAccept.disabled = false;
          btnDecline.disabled = false;
          btnDecline.innerHTML = origText;
        }
      });

      return card;
    },
    () => { },
    '<div style="color: var(--muted-foreground); font-size: 12px; text-align: center; padding: 16px;">Входящих заявок в друзья нет</div>'
  );
}

async function loadFriendRequests() {
  const container = document.getElementById("friend-requests-list");
  if (!container) return;
  try {
    const data = await apiFetch("/friendship/requests");
    renderFriendRequestsData(data);
  } catch (err) {
    console.warn("loadFriendRequests error:", err);
  }
}

// --- 4.9 Boss Buffs (🔥 Усиления: Обычные и Бригадные) ---
let currentBuffsTab = "ordinary";

async function loadBossBuffs() {
  const ordContainer = document.getElementById("boss-buffs-list");
  const brigContainer = document.getElementById("boss-brigade-buffs-list");
  const chip = document.getElementById("buffs-summary-chip");
  if (!ordContainer) return;
  try {
    const data = await apiFetch("/boss/buffs");
    const rawBuffs = data.ordinary || data.buffs || [];
    const ordinary = Array.isArray(rawBuffs) ? rawBuffs : (Array.isArray(rawBuffs.buffs) ? rawBuffs.buffs : Object.values(rawBuffs));
    const brigade = data.brigade || [];

    // Summary chip calculations
    let activeCount = 0;
    let totalCount = 0;
    ordinary.forEach(b => {
      totalCount++;
      if (b.isActive) activeCount++;
    });
    brigade.forEach(group => {
      (group.items || []).forEach(b => {
        totalCount++;
        if (b.isActive) activeCount++;
      });
    });

    if (chip) {
      chip.textContent = `Активно: ${activeCount} | Доступно: ${totalCount}`;
    }

    // Render Ordinary Buffs
    if (ordinary.length === 0) {
      ordContainer.innerHTML = '<div style="color: var(--muted-foreground); font-size: 11px;">Нет доступных баффов</div>';
    } else {
      ordContainer.innerHTML = "";
      ordinary.forEach(b => {
        const card = document.createElement("div");
        card.className = `boss-buff-card ${b.isActive ? 'active' : ''}`;
        const isPermanent = b.category === "permanent";
        const catBadge = isPermanent
          ? '<span class="badge" style="background: rgba(168, 85, 247, 0.2); color: #c084fc; font-size: 9.5px;">Постоянный</span>'
          : '<span class="badge" style="background: rgba(59, 130, 246, 0.2); color: #60a5fa; font-size: 9.5px;">Временный (8 ч)</span>';

        const priceHtml = b.priceTp > 0
          ? `<span class="boss-buff-price" style="color: #fbbf24;"><img src="/static/assets/icons/paper.webp" class="game-icon-xs" alt="Бумага"> ${b.priceTp} шт.</span>`
          : '<span class="boss-buff-price" style="color: #34d399;">Бесплатно</span>';

        card.innerHTML = `
          <div class="boss-buff-card-header">
            <img src="${b.iconUrl || '/static/assets/icons/punchChest.webp'}" class="boss-buff-icon" alt="${b.title || ''}" onerror="this.src='/static/assets/icons/punchChest.webp'">
            <div class="boss-buff-content">
              <div class="boss-buff-title-row">
                <span class="boss-buff-title">${b.title || b.titleRu || b.name || 'Бафф'}</span>
                ${catBadge}
              </div>
              <div class="boss-buff-desc">${b.description || b.descriptionRu || ''}</div>
            </div>
          </div>
          <div class="boss-buff-footer">
            ${priceHtml}
            ${b.isActive
            ? '<button class="btn btn-secondary btn-sm" disabled style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3);">✓ Активен</button>'
            : `<button class="btn btn-primary btn-sm btn-activate-buff" data-buff-id="${b.id}">Активировать</button>`
          }
          </div>
        `;

        card.querySelector(".btn-activate-buff")?.addEventListener("click", async () => {
          try {
            const res = await apiFetch("/actions/boss/buffs/activate", {
              method: "POST",
              body: JSON.stringify({ buffId: b.id }),
            });
            if (res.success) {
              showToast(`Усиление "${b.title || b.id}" успешно активировано!`, "success");
              loadBossBuffs();
              loadBoss();
            }
          } catch (e) {
            showToast(`Ошибка активации: ${e.message}`, "error");
          }
        });

        ordContainer.appendChild(card);
      });
    }

    // Render Brigade Buffs
    if (brigContainer) {
      if (brigade.length === 0) {
        brigContainer.innerHTML = '<div style="color: var(--muted-foreground); font-size: 11px;">Нет данных о бригадных усилениях</div>';
      } else {
        brigContainer.innerHTML = "";
        brigade.forEach(group => {
          const groupCard = document.createElement("div");
          groupCard.className = "brigade-group-card";

          const itemsHtml = (group.items || []).map(b => {
            let itemClass = "brigade-buff-item";
            let btnHtml = "";
            let statusBadge = "";

            if (b.isActive) {
              itemClass += " buff-active";
              statusBadge = '<span class="badge badge-active">✓ Активно</span>';
              btnHtml = '<button class="btn btn-secondary btn-sm" disabled style="background: rgba(52, 211, 153, 0.15); color: #34d399;">✓ Активен</button>';
            } else if (b.isLocked) {
              itemClass += " buff-locked";
              statusBadge = `<span class="badge badge-locked">🔒 ${b.unlockReason || 'Закрыто'}</span>`;
              btnHtml = `<button class="btn btn-secondary btn-sm" disabled style="opacity: 0.5;">🔒 ${b.requirement || 'Закрыто'}</button>`;
            } else if (b.cooldownEndsAt) {
              itemClass += " buff-cooldown";
              statusBadge = '<span class="badge badge-cooldown">⏳ Откат</span>';
              btnHtml = '<button class="btn btn-secondary btn-sm" disabled>Откат</button>';
            } else if (b.canActivate) {
              itemClass += " buff-available";
              btnHtml = `<button class="btn btn-primary btn-sm btn-activate-brigade-buff" data-buff-id="${b.id}">Активировать</button>`;
            } else {
              btnHtml = `<button class="btn btn-secondary btn-sm" disabled>${b.unlockReason || 'Недоступно'}</button>`;
            }

            return `
              <div class="${itemClass}" data-buff-id="${b.id}">
                <div class="brigade-buff-icon-wrapper">
                  <img src="${b.icon || b.iconUrl || '/static/assets/icons/punchChest.webp'}" alt="${b.title}" onerror="this.src='/static/assets/icons/punchChest.webp'">
                </div>
                <div class="brigade-buff-info">
                  <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                    <span class="brigade-buff-title">${b.title}</span>
                    ${statusBadge}
                  </div>
                  <div class="brigade-buff-desc">${b.description}</div>
                  <div class="brigade-buff-req" style="color: ${b.isLocked ? '#f87171' : 'var(--muted-foreground)'};">${b.unlockReason || b.requirement || ''}</div>
                </div>
                <div>${btnHtml}</div>
              </div>
            `;
          }).join("");

          groupCard.innerHTML = `
            <div class="brigade-group-header">
              <div class="brigade-group-title">⚡ ${group.categoryTitle || group.category}</div>
              <div class="brigade-group-subtitle">${group.description || ''}</div>
            </div>
            <div class="brigade-group-items">
              ${itemsHtml}
            </div>
          `;

          groupCard.querySelectorAll(".btn-activate-brigade-buff").forEach(btn => {
            btn.addEventListener("click", async () => {
              const bId = btn.getAttribute("data-buff-id");
              try {
                const res = await apiFetch("/actions/boss/buffs/activate", {
                  method: "POST",
                  body: JSON.stringify({ buffId: bId }),
                });
                if (res.success) {
                  showToast(`Бригадное усиление успешно активировано!`, "success");
                  loadBossBuffs();
                  loadBoss();
                }
              } catch (e) {
                showToast(`Ошибка активации: ${e.message}`, "error");
              }
            });
          });

          brigContainer.appendChild(groupCard);
        });
      }
    }

  } catch (e) {
    console.warn("loadBossBuffs error:", e);
  }
}

// Subtabs inside 🔥 Усиления
document.getElementById("btn-buffs-tab-ordinary")?.addEventListener("click", () => {
  currentBuffsTab = "ordinary";
  document.getElementById("btn-buffs-tab-ordinary")?.classList.add("active");
  document.getElementById("btn-buffs-tab-brigade")?.classList.remove("active");
  const ord = document.getElementById("boss-buffs-ordinary-pane");
  const brig = document.getElementById("boss-buffs-brigade-pane");
  if (ord) ord.style.display = "block";
  if (brig) brig.style.display = "none";
});

document.getElementById("btn-buffs-tab-brigade")?.addEventListener("click", () => {
  currentBuffsTab = "brigade";
  document.getElementById("btn-buffs-tab-brigade")?.classList.add("active");
  document.getElementById("btn-buffs-tab-ordinary")?.classList.remove("active");
  const ord = document.getElementById("boss-buffs-ordinary-pane");
  const brig = document.getElementById("boss-buffs-brigade-pane");
  if (ord) ord.style.display = "none";
  if (brig) brig.style.display = "block";
});

// --- 4.10 Talents ---
function renderBossTalentsWidget(state) {
  const s = state || {};
  const totalPts = s.totalPoints !== undefined ? s.totalPoints : ((s.spentPoints || 0) + (s.unspentPoints || 0));
  const unspentPts = Number(s.unspentPoints || 0);
  const curDmg = Number(s.currentDamage || 0);
  const reqDmg = Math.max(1, Number(s.requiredDamage || 1));
  const dmgPct = Math.min(100, Math.round((curDmg / reqDmg) * 100));

  const dmgFill = document.getElementById("boss-talents-dmg-fill");
  const dmgNum = document.getElementById("boss-talents-dmg-numbers");
  const totalEl = document.getElementById("boss-talents-total");
  const newEl = document.getElementById("boss-talents-new");
  const newBadge = document.getElementById("boss-talents-new-badge");

  if (dmgFill) dmgFill.style.width = `${dmgPct}%`;
  if (dmgNum) dmgNum.textContent = `${formatNum(curDmg)} / ${formatNum(reqDmg)}`;
  if (totalEl) totalEl.textContent = formatNum(totalPts);
  if (newEl) newEl.textContent = formatNum(unspentPts);
  if (newBadge) {
    newBadge.classList.toggle("has-new", unspentPts > 0);
  }
}

async function loadTalents() {
  const container = document.getElementById("talents-list");
  try {
    const data = await apiFetch("/talents");
    const state = data.state || {};
    renderBossTalentsWidget(state);
    if (!container) return;
    const talentsList = data.talents || [];

    const totalPts = state.totalPoints !== undefined ? state.totalPoints : ((state.spentPoints || 0) + (state.unspentPoints || 0));
    const unspentPts = state.unspentPoints || 0;
    const curDmg = state.currentDamage || 0;
    const reqDmg = state.requiredDamage || 1;
    const dmgPct = Math.min(100, Math.round((curDmg / reqDmg) * 100));

    const totalEl = document.getElementById("talents-total-points");
    const availEl = document.getElementById("talents-available-points");
    const dmgNumEl = document.getElementById("talents-dmg-numbers");
    const dmgPctEl = document.getElementById("talents-dmg-percent");
    const dmgFillEl = document.getElementById("talents-dmg-fill");
    const chip = document.getElementById("talents-summary-chip");

    if (totalEl) totalEl.textContent = totalPts;
    if (availEl) availEl.textContent = unspentPts;
    if (dmgNumEl) dmgNumEl.textContent = `${formatNum(curDmg)} / ${formatNum(reqDmg)}`;
    if (dmgPctEl) dmgPctEl.textContent = `${dmgPct}%`;
    if (dmgFillEl) dmgFillEl.style.width = `${dmgPct}%`;
    if (chip) {
      chip.textContent = `Очков: ${totalPts} (свободно: ${unspentPts}) | До следующего: ${dmgPct}%`;
    }

    window.totalTalentsCached = totalPts;
    const statTalentsEl = document.getElementById("stat-talents");
    if (statTalentsEl) statTalentsEl.textContent = formatNum(totalPts);

    if (talentsList.length === 0) {
      container.innerHTML = '<div style="color: var(--muted-foreground); font-size: 11px;">Нет данных о талантах</div>';
      return;
    }

    container.innerHTML = "";
    talentsList.forEach(t => {
      const item = document.createElement("div");
      item.className = "hook-item";
      const isMax = t.currentLevel >= t.maxLevel;
      const canUpgrade = unspentPts >= (t.cost || 1) && !isMax;

      item.innerHTML = `
        <div>
          <div class="hook-item-title">${t.name || 'Талант #' + t.id}</div>
          <div class="hook-item-desc">${t.description || ''}</div>
          <div style="font-size: 11px; font-weight: 700; color: #60a5fa; margin-top: 4px;">
            Ур. ${t.currentLevel}/${t.maxLevel}
          </div>
        </div>
        <button class="btn btn-sm ${canUpgrade ? 'btn-primary' : 'btn-secondary'} btn-upgrade-talent" data-talent-id="${t.id}" ${!canUpgrade ? 'disabled' : ''} style="width: 100%; margin-top: 4px;">
          ${isMax ? 'Максимум' : `Прокачать (${t.cost || 1} очк.)`}
        </button>
      `;
      if (canUpgrade) {
        item.querySelector(".btn-upgrade-talent").addEventListener("click", async () => {
          try {
            const res = await apiFetch("/actions/talents/upgrade", {
              method: "POST",
              body: JSON.stringify({ talentId: t.id }),
            });
            if (res.success) {
              showToast(`Талант «${t.name}» прокачан!`, "success");
              loadTalents();
              loadProfile();
            }
          } catch (e) {
            showToast(`Ошибка: ${e.message}`, "error");
          }
        });
      }
      container.appendChild(item);
    });
  } catch (e) {
    console.warn("loadTalents error:", e);
  }
}

// --- 4.11 Collections (Нычки) ---
async function loadCollections() {
  const container = document.getElementById("collections-list");
  if (!container) return;
  try {
    const data = await apiFetch("/collections");
    const list = data.collections || [];
    const stashes = data.stashes || [];

    const stashesCountEl = document.getElementById("collections-stashes-count");
    if (stashesCountEl) stashesCountEl.textContent = stashes.length;

    const readyToExchange = list.filter(c => c.canExchange).length;
    const chip = document.getElementById("collections-summary-chip");
    if (chip) {
      chip.textContent = `Нычек: ${stashes.length} | Готово к обмену: ${readyToExchange}`;
    }

    const stashesPillsEl = document.getElementById("collections-stashes-pills");
    if (stashesPillsEl) {
      if (stashes.length === 0) {
        stashesPillsEl.innerHTML = '<span style="font-size: 11px; color: var(--muted-foreground);">Нычек в инвентаре нет</span>';
      } else {
        stashesPillsEl.innerHTML = stashes.map(s => `
          <span class="reward-pill" style="background: rgba(251, 191, 36, 0.1); border-color: rgba(251, 191, 36, 0.25); color: #fbbf24;">
            ${gameIcon('stash', '', 'game-icon-sm')} ${s.name || 'Нычка #' + (s.id || '')}
          </span>
        `).join("");
      }
    }

    if (list.length === 0) {
      container.innerHTML = '<div style="color: var(--muted-foreground); font-size: 11px;">Нет данных о коллекциях</div>';
      return;
    }

    // Сортировка: готовые к обмену коллекции всегда первыми
    list.sort((a, b) => (b.canExchange ? 1 : 0) - (a.canExchange ? 1 : 0));

    container.innerHTML = "";
    list.forEach(c => {
      const isComplete = Boolean(c.canExchange);
      const card = document.createElement("div");
      card.className = `collection-card ${isComplete ? 'ready' : ''}`;

      const itemsHtml = (c.items || []).map((itm, idx) => {
        const owned = (itm.count || 0) > 0;
        const itmNum = itm.itemNumber || (idx + 1);
        const displayName = itm.name || `Предмет #${itmNum}`;
        return `
          <div class="col-item-thumb ${!owned ? 'unowned' : ''}" title="${displayName} (x${itm.count || 0})">
            ${itm.icon ? `<img src="${itm.icon}" alt="${displayName}" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.style.display='none'">` : `<span style="font-size:10px; font-weight:700;">#${itmNum}</span>`}
            <span class="col-item-count">x${itm.count || 0}</span>
          </div>
        `;
      }).join("");

      const prisonLabel = c.prisonName ? `<span class="badge" style="background: rgba(255,255,255,0.08); font-size: 10px; margin-right: 6px;">${c.prisonName}</span>` : "";
      const readyBadge = isComplete ? `<span class="badge-can-exchange">⚡️ Готово к обмену</span>` : "";

      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
          <div>
            <div style="font-size: 12px; font-weight: 700; color: #fff; display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
              ${prisonLabel}
              <span>${c.name}</span>
              ${readyBadge}
            </div>
            <div style="font-size: 10px; color: var(--muted-foreground); margin-top: 2px;">Собрано предметов: <b style="color: ${isComplete ? '#34d399' : '#fff'};">${c.collected || 0}/${c.total || 7}</b></div>
          </div>
          <button class="btn btn-sm ${isComplete ? 'btn-primary' : 'btn-secondary'} btn-exchange-coll" ${!isComplete ? 'disabled' : ''}>
            ${isComplete ? 'Обменять (впарить)' : 'Не собрана'}
          </button>
        </div>
        <div class="collection-items-row">
          ${itemsHtml}
        </div>
      `;

      if (isComplete) {
        card.querySelector(".btn-exchange-coll").addEventListener("click", async () => {
          try {
            const res = await apiFetch("/actions/collections/exchange", {
              method: "POST",
              body: JSON.stringify({ collectionId: c.collectionId, prisonId: c.prisonId }),
            });
            if (res.success) {
              showToast(`Коллекция «${c.name}» успешно обменена!`, "success");
              loadCollections();
              loadProfile();
            }
          } catch (e) {
            showToast(`Ошибка сдачи коллекции: ${e.message}`, "error");
          }
        });
      }
      container.appendChild(card);
    });
  } catch (e) {
    console.warn("loadCollections error:", e);
  }
}

// --- 4.12 Bauls ---
function renderBaulsData(data) {
  const card = document.getElementById("bauls-card");
  if (!card || !data) return;
  liveSlices.data.bauls = data;
  const stats = data.stats || {};

  const lvl = stats.level || 0;
  const maxLvl = stats.maxLevel || 30;
  const curExp = stats.currentExp || 0;
  const nextExp = stats.expToNext || 1;
  const pct = Math.min(100, Math.round((curExp / nextExp) * 100));

  setTextIfChanged(document.getElementById("baul-level-text"), `Ур. ${lvl}/${maxLvl}`);
  setTextIfChanged(document.getElementById("baul-exp-text"), `${formatNum(curExp)} / ${formatNum(nextExp)}`);
  setTextIfChanged(document.getElementById("baul-exp-percent"), `${pct}%`);
  setWidthIfChanged(document.getElementById("baul-exp-fill"), `${pct}%`);

  const pendingRewardsEl = document.getElementById("baul-pending-rewards");
  if (pendingRewardsEl) {
    const rewards = stats.pendingRewards || [];
    if (rewards.length === 0) {
      if (pendingRewardsEl.dataset.emptySig !== "empty") {
        pendingRewardsEl.innerHTML = '<span style="font-size: 11px; color: var(--muted-foreground);">Нет накопленных наград</span>';
        pendingRewardsEl.dataset.emptySig = "empty";
      }
    } else {
      const nextSig = JSON.stringify(rewards.map(r => [r.type, r.id, r.amount || r.count]));
      if (pendingRewardsEl.dataset.sig !== nextSig) {
        pendingRewardsEl.dataset.emptySig = "";
        pendingRewardsEl.dataset.sig = nextSig;
        pendingRewardsEl.innerHTML = rewards.map(r => {
          const iconSrc = r.imageUrl || (r.iconKey ? `/static/assets/icons/${r.iconKey}.webp` : '/static/assets/icons/rubles.webp');
          const lbl = r.label || r.title || r.type || 'Награда';
          const amt = r.amount !== undefined ? r.amount : (r.count || 0);
          return `
            <span class="baul-reward-pill" title="${lbl}: +${formatNum(amt)}">
              <img src="${iconSrc}" class="game-icon-sm" alt="${lbl}" onerror="this.src='/static/assets/icons/rubles.webp'">
              <span class="baul-reward-amount">+${formatNum(amt)}</span>
              <span class="baul-reward-label">${lbl}</span>
            </span>
          `;
        }).join("");
      }
    }
  }
}

async function loadBauls() {
  const card = document.getElementById("bauls-card");
  if (!card) return;
  try {
    const data = await apiFetch("/bauls");
    renderBaulsData(data);
  } catch (e) {
    console.warn("loadBauls error:", e);
  }
}

// ============================================================================
// 5. ACTION HANDLERS
// ============================================================================

// --- 5.1 Melee Hit ---
document.querySelectorAll(".btn-melee-hit").forEach(btn => {
  btn.addEventListener("click", async () => {
    const weapon = btn.getAttribute("data-weapon");
    btn.disabled = true;
    try {
      const res = await apiFetch("/actions/boss/hit", {
        method: "POST",
        body: JSON.stringify({ weapon, count: 1 }),
      });
      if (res.success) {
        showToast(`Удар нанесен!`, "success");
        loadBoss();
        loadTalents();
      }
    } catch (e) {
      showToast(`Ошибка удара: ${e.message}`, "error");
    } finally {
      btn.disabled = false;
    }
  });
});

// --- 5.2 Paid Weapons Hit ---
document.querySelectorAll(".btn-weapon-hit").forEach(btn => {
  btn.addEventListener("click", async () => {
    const weapon = btn.getAttribute("data-weapon");
    if (!confirm(`Вы действительно хотите использовать ${weapon}?`)) return;
    btn.disabled = true;
    try {
      const res = await apiFetch("/actions/boss/hit", {
        method: "POST",
        body: JSON.stringify({ weapon, count: 1 }),
      });
      if (res.success) {
        showToast(`Оружие использовано!`, "success");
        loadBoss();
        loadProfile();
        loadTalents();
      }
    } catch (e) {
      showToast(`Ошибка: ${e.message}`, "error");
    } finally {
      btn.disabled = false;
    }
  });
});

// --- 5.4 Boss Claim Reward ---
document.getElementById("btn-boss-claim")?.addEventListener("click", async () => {
  try {
    const res = await apiFetch("/actions/boss/claim", { method: "POST" });
    if (res.success) {
      showToast("Награда за босса получена!", "success");
      loadBoss();
      loadProfile();
      refreshState();
    }
  } catch (e) {
    showToast(`Ошибка сбора: ${e.message}`, "error");
  }
});

// --- 5.5 Prison Work (1 Walk) ---
document.getElementById("btn-prison-work-one")?.addEventListener("click", async () => {
  try {
    const res = await apiFetch("/actions/prison/work", {
      method: "POST",
      body: JSON.stringify({ prisonId: currentPrisonId, isDay: currentIsDay, count: 1 }),
    });
    if (res.success) {
      showToast("Ходка завершена!", "success");
      loadPrisons();
      loadProfile();
      refreshState();
    }
  } catch (e) {
    showToast(`Ошибка ходки: ${e.message}`, "error");
  }
});

// --- 5.6 Prison Work (All Energy Drain) ---
document.getElementById("btn-prison-work-all")?.addEventListener("click", async () => {
  const btnAll = document.getElementById("btn-prison-work-all");
  const btnOne = document.getElementById("btn-prison-work-one");
  const origHtml = btnAll ? btnAll.innerHTML : "";
  if (btnAll) {
    btnAll.disabled = true;
    btnAll.textContent = "⏳ Сливаем энергию...";
  }
  if (btnOne) btnOne.disabled = true;

  try {
    const res = await apiFetch("/prisons/drain", {
      method: "POST",
      body: JSON.stringify({ prisonId: currentPrisonId, isDay: currentIsDay, collectPodogrev: false }),
    });
    if (res.success) {
      const runs = res.runsCompleted !== undefined ? res.runsCompleted : (res.works_done || 0);
      const remEn = res.remainingEnergy !== undefined ? res.remainingEnergy : (res.remaining_energy ?? 0);
      const stCost = res.stageCost || 0;

      if (playerProfile && playerProfile.profile) {
        playerProfile.profile.energy = remEn;
        updateEnergyTimer();
      }

      if (runs > 0) {
        showToast(`⚡ Выполнено ходок: ${runs} • Остаток энергии: ${remEn}`, "success");
      } else {
        showToast(`Недостаточно энергии: ${remEn}/${stCost} ⚡`, "info");
      }
      loadPrisons({ force: true });
      loadProfile();
      refreshState();
    } else {
      showToast(res.error || res.detail || "Не удалось слить энергию", "error");
    }
  } catch (e) {
    showToast(`Ошибка: ${e.message}`, "error");
  } finally {
    if (btnAll) {
      btnAll.disabled = false;
      btnAll.innerHTML = origHtml || "⚡ Слить всю энергию";
    }
    if (btnOne) btnOne.disabled = false;
  }
});

// --- 5.7 Day / Night Shift ---
document.getElementById("btn-shift-day")?.addEventListener("click", async () => {
  currentIsDay = true;
  await apiFetch("/config", {
    method: "PATCH",
    body: JSON.stringify({ prison_prefer_night: false }),
  });
  loadPrisons();
});

document.getElementById("btn-shift-night")?.addEventListener("click", async () => {
  currentIsDay = false;
  await apiFetch("/config", {
    method: "PATCH",
    body: JSON.stringify({ prison_prefer_night: true }),
  });
  loadPrisons();
});

// --- 5.8 Master Training ---
document.getElementById("btn-master-train")?.addEventListener("click", async () => {
  const masterId = document.getElementById("select-master")?.value;
  if (!masterId) return;
  try {
    const res = await apiFetch("/actions/master/work", {
      method: "POST",
      body: JSON.stringify({ masterId: parseInt(masterId) }),
    });
    if (res.success) {
      showToast("Тренировка у мастера завершена!", "success");
      loadPrisons();
      loadProfile();
    }
  } catch (e) {
    showToast(`Ошибка тренировки: ${e.message}`, "error");
  }
});

// --- 5.9 Routine Collect Buttons ---
document.getElementById("btn-collect-business")?.addEventListener("click", async () => {
  try {
    const res = await apiFetch("/actions/routine/collect", {
      method: "POST",
      body: JSON.stringify({ target: "business" }),
    });
    if (res.success) {
      showToast("Прибыль с бизнесов собрана!", "success");
      loadProfile();
      refreshState();
    }
  } catch (e) {
    showToast(`Ошибка: ${e.message}`, "error");
  }
});

document.querySelectorAll(".btn-routine-action").forEach(btn => {
  btn.addEventListener("click", async () => {
    const target = btn.getAttribute("data-target");
    btn.disabled = true;
    try {
      let res;
      let msg = "Действие успешно выполнено!";
      if (target === "toilet_paper") {
        res = await apiFetch("/daily/toilet-paper", { method: "POST" });
        const inner = res.result || {};
        if (inner.success === false) {
          msg = inner.message || "Ещё рано! Приходи завтра.";
          if (res.toiletPaper) updateToiletPaperState(res.toiletPaper);
          showToast(msg, "info");
          loadProfile();
          return;
        }
        if (res.toiletPaper) updateToiletPaperState(res.toiletPaper);
        msg = "Бесплатная туалетная бумага успешно получена!";
      } else if (target === "podogrev_send") {
        res = await apiFetch("/daily/podogrev-send", { method: "POST" });
        const cnt = res.result?.sent || res.result?.count || 0;
        msg = `Подогревы друзьям отправлены (отправлено: ${cnt})!`;
      } else if (target === "katala") {
        res = await apiFetch("/daily/katala-play", { method: "POST" });
        const r = res.result || {};
        if (r.status === "already_played") {
          msg = "Бесплатная суточная партия уже была сыграна!";
        } else {
          msg = `Партия у Каталы завершена! Комбинация: ${r.hand_name || r.reward || 'Успех'}`;
        }
      } else if (target === "monthly") {
        res = await apiFetch("/daily/monthly-claim", { method: "POST" });
        const claimed = (res.claimed || []).length;
        msg = claimed > 0 ? `Собрано ${claimed} наград месячных делюг!` : "Нет доступных для сбора наград месячных делюг.";
      } else {
        res = await apiFetch("/actions/routine/collect", {
          method: "POST",
          body: JSON.stringify({ target }),
        });
      }

      if (res && res.success !== false) {
        showToast(msg, "success");
        loadProfile();
        refreshState();
        if (target === "monthly") loadMonthlyState();
      } else if (res && res.message) {
        showToast(res.message, "info");
      }
    } catch (e) {
      showToast(`Ошибка: ${e.message}`, "error");
    } finally {
      btn.disabled = false;
    }
  });
});

// --- 5.10 Master Switch in HUD ---
const hudMasterSwitch = document.getElementById("hud-master-switch");
hudMasterSwitch?.addEventListener("change", async () => {
  const isPaused = !hudMasterSwitch.checked;
  const masterText = document.getElementById("hud-master-text");
  if (masterText) masterText.textContent = isPaused ? "БОТ: ВЫКЛ" : "БОТ: ВКЛ";
  await apiFetch("/config", {
    method: "PATCH",
    body: JSON.stringify({ is_paused: isPaused }),
  });
  showToast(isPaused ? "Бот выключен (пауза)" : "Бот включен (активен)", "info");
  refreshState();
});

// --- 5.12 Business Accordion Toggle ---
const btnToggleBiz = document.getElementById("btn-toggle-businesses");
btnToggleBiz?.addEventListener("click", () => {
  isBusinessesExpanded = !isBusinessesExpanded;
  const wrap = document.getElementById("businesses-collapsible");
  if (wrap) wrap.style.display = isBusinessesExpanded ? "block" : "none";
  const bizList = (playerProfile && playerProfile.businesses) || [];
  const textEl = document.getElementById("btn-toggle-biz-text");
  const iconEl = document.getElementById("btn-toggle-biz-icon");
  if (textEl) textEl.textContent = `(${bizList.length})`;
  if (iconEl) iconEl.textContent = isBusinessesExpanded ? "▴" : "▾";
});

// --- 5.13 Refresh Buttons for Hooks ---
document.getElementById("btn-refresh-buffs")?.addEventListener("click", () => {
  loadBossBuffs();
  showToast("Баффы обновляются...", "info");
});
document.getElementById("btn-refresh-talents")?.addEventListener("click", () => {
  loadTalents();
  showToast("Таланты обновляются...", "info");
});
document.getElementById("btn-refresh-collections")?.addEventListener("click", () => {
  loadCollections();
  showToast("Коллекции обновляются...", "info");
});
document.getElementById("btn-refresh-bauls")?.addEventListener("click", () => {
  loadBauls();
  showToast("Баулы обновляются...", "info");
});
document.getElementById("btn-refresh-friends")?.addEventListener("click", () => {
  loadFriendsSummary();
  loadFriendRequests();
  loadFriendsAudit();
  showToast("Заявки и статистика корешей обновляются...", "info");
});

document.getElementById("btn-refresh-friends-summary")?.addEventListener("click", () => {
  loadFriendsSummary();
  showToast("Сводка корешей обновлена", "info");
});

document.getElementById("btn-refresh-audit")?.addEventListener("click", () => {
  loadFriendsAudit();
  showToast("Список аудита обновлен", "info");
});

document.getElementById("btn-audit-tab-top")?.addEventListener("click", () => {
  currentAuditSort = "damage_7d";
  document.getElementById("btn-audit-tab-top")?.classList.add("active");
  document.getElementById("btn-audit-tab-inactive")?.classList.remove("active");
  loadFriendsAudit();
});

document.getElementById("btn-audit-tab-inactive")?.addEventListener("click", () => {
  currentAuditSort = "inactive";
  document.getElementById("btn-audit-tab-inactive")?.classList.add("active");
  document.getElementById("btn-audit-tab-top")?.classList.remove("active");
  loadFriendsAudit();
});

document.getElementById("btn-filter-mode-and")?.addEventListener("click", async () => {
  document.getElementById("btn-filter-mode-and")?.classList.add("active");
  document.getElementById("btn-filter-mode-or")?.classList.remove("active");
  await apiFetch("/config", { method: "PATCH", body: JSON.stringify({ friend_filter_mode: "and" }) });
  showToast("Режим фильтра: Все пороги (И)", "success");
});

document.getElementById("btn-filter-mode-or")?.addEventListener("click", async () => {
  document.getElementById("btn-filter-mode-or")?.classList.add("active");
  document.getElementById("btn-filter-mode-and")?.classList.remove("active");
  await apiFetch("/config", { method: "PATCH", body: JSON.stringify({ friend_filter_mode: "or" }) });
  showToast("Режим фильтра: Любой порог (ИЛИ)", "success");
});

document.getElementById("cfg-auto_parse_news_raids")?.addEventListener("change", async (e) => {
  const val = e.target.checked;
  await apiFetch("/config", { method: "PATCH", body: JSON.stringify({ auto_parse_news_raids: val }) });
  showToast(val ? "Автопарсинг новостей включен" : "Автопарсинг новостей выключен", "info");
});

document.getElementById("cfg-auto_friend_cleanup")?.addEventListener("change", async (e) => {
  const val = e.target.checked;
  await apiFetch("/config", { method: "PATCH", body: JSON.stringify({ auto_friend_cleanup: val }) });
  showToast(val ? "Авточистка друзей включена" : "Авточистка друзей выключена", "info");
});

document.getElementById("cfg-friend_cleanup_inactive_days")?.addEventListener("change", async (e) => {
  const val = parseInt(e.target.value, 10);
  if (!isNaN(val) && val >= 1) {
    await apiFetch("/config", { method: "PATCH", body: JSON.stringify({ friend_cleanup_inactive_days: val }) });
    showToast("Дней неактивности сохранено", "success");
  }
});

document.getElementById("cfg-friend_cleanup_daily_limit")?.addEventListener("change", async (e) => {
  const val = parseInt(e.target.value, 10);
  if (!isNaN(val) && val >= 1 && val <= 50) {
    await apiFetch("/config", { method: "PATCH", body: JSON.stringify({ friend_cleanup_daily_limit: val }) });
    showToast("Лимит удалений сохранен", "success");
  }
});

document.getElementById("btn-preview-cleanup")?.addEventListener("click", async () => {
  const infoEl = document.getElementById("cleanup-preview-info");
  if (!infoEl) return;
  infoEl.style.display = "block";
  infoEl.innerHTML = "Поиск кандидатов на чистку...";

  try {
    const data = await apiFetch("/friends/cleanup/preview");
    const cands = data.candidates || [];
    infoEl.innerHTML = `
      <div style="font-weight: 600; margin-bottom: 4px; color: var(--foreground);">
        Кандидатов на удаление: ${data.totalEligible} (лимит сегодня: ${data.removedLast24h} / ${data.dailyLimit}, доступно к удалению: ${data.remainingDailyLimit})
      </div>
      ${cands.slice(0, 5).map(c => `<div>• ${c.nickname} (ID ${c.userId}) — неактивен ${c.daysInactive} дн., урон: 0</div>`).join("")}
      ${cands.length > 5 ? `<div style="font-style: italic;">... и еще ${cands.length - 5} друзей</div>` : ''}
    `;
  } catch (e) {
    infoEl.innerHTML = `<span style="color: var(--destructive);">Ошибка предпросмотра: ${e.message}</span>`;
  }
});

document.getElementById("btn-run-cleanup")?.addEventListener("click", async () => {
  const checkedBoxes = Array.from(document.querySelectorAll(".audit-friend-cb:checked"));
  const userIds = checkedBoxes.map(cb => parseInt(cb.getAttribute("data-user-id"), 10)).filter(Boolean);

  const confirmMsg = userIds.length > 0
    ? `Удалить выбранных ${userIds.length} друзей?`
    : `Запустить безопасную авточистку неактивных друзей?`;

  if (!confirm(confirmMsg)) return;

  const btn = document.getElementById("btn-run-cleanup");
  if (btn) btn.disabled = true;

  try {
    const payload = userIds.length > 0 ? { userIds } : {};
    const res = await apiFetch("/friends/cleanup/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast(res.message || `Удалено ${res.removedCount} друзей`, "success");
    loadFriendsSummary();
    loadFriendsAudit();
  } catch (e) {
    showToast(`Ошибка удаления: ${e.message}`, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
});

document.getElementById("btn-sync-top")?.addEventListener("click", async () => {
  const btn = document.getElementById("btn-sync-top");
  if (btn) btn.disabled = true;
  showToast("Синхронизация с Топом и Достижениями...", "info");
  try {
    const res = await apiFetch("/raids/sync-top", { method: "POST", body: JSON.stringify({ force: true }) });
    showToast(res.message || "Синхронизация завершена", res.success ? "success" : "info");
    await loadActivePlayersRadar({ silent: true });
  } catch (e) {
    showToast(`Ошибка синхронизации: ${e.message}`, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
});

document.getElementById("btn-scan-news")?.addEventListener("click", async () => {
  const btn = document.getElementById("btn-scan-news");
  if (btn) btn.disabled = true;
  showToast("Парсинг постов новостей...", "info");
  try {
    const res = await apiFetch("/raids/scan-news", { method: "POST" });
    showToast(res.message || "Парсинг новостей завершен", res.success ? "success" : "info");
    await loadActivePlayersRadar({ silent: true });
  } catch (e) {
    showToast(`Ошибка парсинга новостей: ${e.message}`, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
});

// --- 5.14 Config Toggles & Inputs Auto-Save ---
const autoConfigKeys = [
  "is_paused", "sleep_mode_enabled", "auto_toilet_paper", "auto_business",
  "auto_beard", "auto_podogrev", "auto_podogrev_send", "auto_katala", "auto_monthly_tasks",
  "auto_boss_enabled", "auto_boss_hits", "auto_boss_summon", "boss_auto_melee",
  "boss_allow_paid_weapons", "auto_prison", "auto_masters", "auto_gifts",
  "auto_friends", "auto_events", "friend_accept_all", "friend_auto_decline_below",
  "auto_kolsik"
];

autoConfigKeys.forEach(k => {
  const el = document.getElementById(`cfg-${k}`);
  if (el) {
    el.addEventListener("change", async () => {
      const val = el.checked;
      try {
        await apiFetch("/config", {
          method: "PATCH",
          body: JSON.stringify({ [k]: val }),
        });
        showToast(`Настройка сохранена`, "info");
        refreshState();
      } catch (e) {
        el.checked = !val;
        showToast(`Ошибка сохранения настройки: ${e.message}`, "error");
      }
    });
  }
});

// Kolsik currency selector
document.querySelectorAll('input[name="kolsik_currency"]').forEach(radio => {
  radio.addEventListener("change", async () => {
    const currency = radio.value;
    try {
      await apiFetch("/config", {
        method: "PATCH",
        body: JSON.stringify({ kolsik_currency: currency }),
      });
      showToast(`Валюта Кольщика: ${currency === "paper" ? "Туалетная бумага" : "Рубли"}`, "info");
      refreshState();
    } catch (e) {
      showToast(`Ошибка сохранения валюты: ${e.message}`, "error");
    }
  });
});

// Kolsik manual roll button
document.getElementById("btn-kolsik-roll")?.addEventListener("click", async () => {
  const btn = document.getElementById("btn-kolsik-roll");
  if (btn) btn.disabled = true;
  const selRadio = document.querySelector('input[name="kolsik_currency"]:checked');
  const currency = selRadio ? selRadio.value : "paper";
  try {
    const res = await apiFetch("/actions/kolsik/roll", {
      method: "POST",
      body: JSON.stringify({ currency }),
    });
    if (res.success) {
      const dropTitle = res.parsed?.drops?.[0]?.title || "Наколка набита!";
      showToast(`🎨 Кольщик: ${dropTitle}`, "success");
      loadNotifications(currentCatFilter);
      loadProfile();
      refreshState();
    }
  } catch (e) {
    showToast(`Ошибка у Кольщика: ${e.message}`, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
});

// Auto-friends toggle in friends section
const autoFriendsSec = document.getElementById("cfg-auto_friends_sec");
if (autoFriendsSec) {
  autoFriendsSec.addEventListener("change", async () => {
    const val = autoFriendsSec.checked;
    try {
      await apiFetch("/config", {
        method: "PATCH",
        body: JSON.stringify({ auto_friends: val }),
      });
      showToast(`Авто-прием заявок: ${val ? 'ВКЛ' : 'ВЫКЛ'}`, "info");
      refreshState();
    } catch (e) {
      autoFriendsSec.checked = !val;
      showToast(`Ошибка сохранения: ${e.message}`, "error");
    }
  });
}

// Friend filter thresholds inputs
const friendFilterIds = [
  "cfg-friend_min_talents", "cfg-friend_min_poison_damage",
  "cfg-friend_min_level", "cfg-friend_min_authority", "cfg-friend_min_biceps"
];
friendFilterIds.forEach(id => {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener("change", async () => {
      const key = id.replace("cfg-", "");
      const val = parseInt(el.value) || 0;
      await apiFetch("/config", {
        method: "PATCH",
        body: JSON.stringify({ [key]: val }),
      });
      showToast(`Фильтр друзей обновлен`, "info");
      refreshState();
    });
  }
});

// Sleep hours change
["cfg-sleep_start_hour", "cfg-sleep_end_hour"].forEach(id => {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener("change", async () => {
      const k = id.replace("cfg-", "");
      await apiFetch("/config", {
        method: "PATCH",
        body: JSON.stringify({ [k]: parseInt(el.value) || 0 }),
      });
      showToast(`Интервал сна обновлен`, "info");
    });
  }
});

// Full Run Now Button
document.getElementById("btn-run-all-workers")?.addEventListener("click", async () => {
  await apiFetch("/actions/run-now", { method: "POST" });
  showToast("Запущен полный цикл всех воркеров!", "success");
});

// Profile Refresh Button
document.getElementById("btn-refresh-profile")?.addEventListener("click", () => {
  loadProfile();
  showToast("Профиль обновляется...", "info");
});

// Token Save
document.getElementById("btn-save-token")?.addEventListener("click", () => {
  const val = document.getElementById("input-admin-token")?.value;
  if (val) {
    localStorage.setItem("prison_admin_token", val.trim());
    showToast("Токен сохранен!", "success");
    refreshState();
    loadProfile();
  }
});

document.getElementById("btn-logout-token")?.addEventListener("click", () => {
  const current = localStorage.getItem("prison_admin_token") || "";
  const newToken = prompt("Введите новый WEB_ADMIN_TOKEN:", current);
  if (newToken !== null) {
    localStorage.setItem("prison_admin_token", newToken.trim());
    location.reload();
  }
});

// Auth Modal Submit
document.getElementById("btn-auth-modal-submit")?.addEventListener("click", () => {
  const val = document.getElementById("auth-modal-token")?.value;
  if (val) {
    localStorage.setItem("prison_admin_token", val.trim());
    document.getElementById("auth-modal").style.display = "none";
    location.reload();
  }
});

// ============================================================================
// 5. WARDROBE CONTROLLER & FITTING ROOM
// ============================================================================

async function loadWardrobe() {
  try {
    const data = await apiFetch("/wardrobe/overview");
    if (!data.success) return;
    wardrobeData = data;
    renderWardrobe();
  } catch (err) {
    console.warn("loadWardrobe error:", err);
  }
}

function renderWardrobe() {
  if (!wardrobeData) return;

  // Изоляция Слепого кольщика: скрываем Одежда и Хаты, оставляем только Татуировки
  const isBlindKolsik = wardrobeTab === "blind_kolsik";
  document.querySelectorAll(".wardrobe-subtab").forEach(s => {
    const sub = s.getAttribute("data-wsub");
    if (isBlindKolsik) {
      if (sub === "tattoos") {
        s.style.display = "";
        s.classList.add("active");
      } else {
        s.style.display = "none";
        s.classList.remove("active");
      }
    } else {
      s.style.display = "";
      if (sub === wardrobeSubtab) {
        s.classList.add("active");
      } else {
        s.classList.remove("active");
      }
    }
  });

  if (isBlindKolsik) {
    wardrobeSubtab = "tattoos";
  }

  // Toggle subtab views
  const isCameras = wardrobeSubtab === "cameras";
  const filtersPane = document.getElementById("wardrobe-filters-pane");
  const summaryPane = document.getElementById("wardrobe-summary-pane");
  const setsList = document.getElementById("wardrobe-sets-list");
  const camerasPane = document.getElementById("wardrobe-cameras-pane");

  if (isCameras) {
    if (filtersPane) filtersPane.style.display = "none";
    if (summaryPane) summaryPane.style.display = "none";
    if (setsList) setsList.style.display = "none";
    if (camerasPane) camerasPane.style.display = "block";
    renderWardrobeCameras();
    return;
  }

  if (filtersPane) filtersPane.style.display = "block";
  if (summaryPane) summaryPane.style.display = "block";
  if (setsList) setsList.style.display = "flex";
  if (camerasPane) camerasPane.style.display = "none";

  renderWardrobeSummary();
  renderWardrobeSets();
}

function renderWardrobeSummary() {
  // Суммарная статистика по всему гардеробу (в точности как сводная таблица @pro_prison_bot)
  const allStats = (wardrobeData && wardrobeData.summaryStats) || {};
  const totalSummary = {
    collected: { knife: 0, poison: 0, gunshot: 0, energy: 0, biceps: 0, punchChest: 0, kickBalls: 0, pokeEyes: 0, kneeEar: 0 },
    missing: { knife: 0, poison: 0, gunshot: 0, energy: 0, biceps: 0, punchChest: 0, kickBalls: 0, pokeEyes: 0, kneeEar: 0 },
    max: { knife: 0, poison: 0, gunshot: 0, energy: 0, biceps: 0, punchChest: 0, kickBalls: 0, pokeEyes: 0, kneeEar: 0 },
    special: { bossAttackLimit: { collected: 0, max: 1 }, comboSaveChance: { collected: 0, max: 5 } }
  };

  Object.values(allStats).forEach(st => {
    for (const [k, v] of Object.entries(st.collected || {})) {
      if (totalSummary.collected[k] !== undefined) totalSummary.collected[k] += Number(v);
    }
    for (const [k, v] of Object.entries(st.missing || {})) {
      if (totalSummary.missing[k] !== undefined) totalSummary.missing[k] += Number(v);
    }
    for (const [k, v] of Object.entries(st.max || {})) {
      if (totalSummary.max[k] !== undefined) totalSummary.max[k] += Number(v);
    }
  });

  const sublabel = document.getElementById("wardrobe-summary-sublabel");
  if (sublabel) {
    sublabel.textContent = "(Всего: Тату и Шмот)";
  }

  const col = totalSummary.collected || {};
  const mis = totalSummary.missing || {};
  const max = totalSummary.max || {};
  const spec = totalSummary.special || {};

  // Row Collected
  const elColKnife = document.getElementById("summ-col-knife");
  const elColPoison = document.getElementById("summ-col-poison");
  const elColGun = document.getElementById("summ-col-gunshot");
  const elColEnergy = document.getElementById("summ-col-energy");
  if (elColKnife) elColKnife.textContent = `+${formatNum(col.knife || 0)}`;
  if (elColPoison) elColPoison.textContent = `+${formatNum(col.poison || 0)}`;
  if (elColGun) elColGun.textContent = `+${formatNum(col.gunshot || 0)}`;
  if (elColEnergy) elColEnergy.textContent = `+${formatNum(col.energy || 0)}`;

  // Row Missing
  const elMisKnife = document.getElementById("summ-mis-knife");
  const elMisPoison = document.getElementById("summ-mis-poison");
  const elMisGun = document.getElementById("summ-mis-gunshot");
  const elMisEnergy = document.getElementById("summ-mis-energy");
  if (elMisKnife) elMisKnife.textContent = `+${formatNum(mis.knife || 0)}`;
  if (elMisPoison) elMisPoison.textContent = `+${formatNum(mis.poison || 0)}`;
  if (elMisGun) elMisGun.textContent = `+${formatNum(mis.gunshot || 0)}`;
  if (elMisEnergy) elMisEnergy.textContent = `+${formatNum(mis.energy || 0)}`;

  // Row Special
  const elSpecBoss = document.getElementById("summ-spec-boss-limit");
  const elSpecCombo = document.getElementById("summ-spec-combo-chance");
  const bossLim = spec.bossAttackLimit || {};
  const comboSave = spec.comboSaveChance || {};
  if (elSpecBoss) elSpecBoss.textContent = `+${bossLim.collected || 0} / ${bossLim.max || 1}`;
  if (elSpecCombo) elSpecCombo.textContent = `+${comboSave.collected || 0}% / ${comboSave.max || 5}%`;

  // Details
  const elDetBiceps = document.getElementById("summ-det-biceps");
  const elDetPunch = document.getElementById("summ-det-punch");
  const elDetKick = document.getElementById("summ-det-kick");
  const elDetPoke = document.getElementById("summ-det-poke");
  const elDetKnee = document.getElementById("summ-det-knee");
  if (elDetBiceps) elDetBiceps.textContent = `+${col.biceps || 0} / ${max.biceps || 0}`;
  if (elDetPunch) elDetPunch.textContent = `+${col.punchChest || 0} / ${max.punchChest || 0}`;
  if (elDetKick) elDetKick.textContent = `+${col.kickBalls || 0} / ${max.kickBalls || 0}`;
  if (elDetPoke) elDetPoke.textContent = `+${col.pokeEyes || 0} / ${max.pokeEyes || 0}`;
  if (elDetKnee) elDetKnee.textContent = `+${col.kneeEar || 0} / ${max.kneeEar || 0}`;
}

function renderWardrobeSets() {
  const container = document.getElementById("wardrobe-sets-list");
  if (!container || !wardrobeData) return;

  const rawSets = (wardrobeData.sets && wardrobeData.sets[wardrobeTab] && wardrobeData.sets[wardrobeTab][wardrobeSubtab]) || [];

  // Filter sets
  const filtered = rawSets.filter(s => {
    // Search query
    if (wardrobeSearchQuery) {
      const q = wardrobeSearchQuery.toLowerCase();
      const inName = (s.setName || "").toLowerCase().includes(q);
      const inDesc = (s.description || "").toLowerCase().includes(q);
      const inSrc = (s.sourceText || "").toLowerCase().includes(q);
      const inParts = (s.parts || []).some(p => (p.name || "").toLowerCase().includes(q));
      if (!inName && !inDesc && !inSrc && !inParts) return false;
    }

    // Status filter
    if (wardrobeFilterStatus === "owned" && s.ownedParts < s.totalParts) return false;
    if (wardrobeFilterStatus === "unowned" && s.ownedParts >= s.totalParts && s.totalParts > 0) return false;

    // Can buy filter
    if (wardrobeFilterCanBuy) {
      const hasCanBuyPart = (s.parts || []).some(p => p.canBuy);
      if (!hasCanBuyPart) return false;
    }

    // Bonus filter
    if (wardrobeFilterBonus !== "all") {
      const maxB = s.maxBonus || {};
      if (wardrobeFilterBonus === "special") {
        if (!maxB.bossLimit && !maxB.comboSaveChance && !maxB.punchChest && !maxB.kickBalls && !maxB.pokeEyes && !maxB.kneeEar) return false;
      } else {
        if (!maxB[wardrobeFilterBonus] || maxB[wardrobeFilterBonus] <= 0) return false;
      }
    }

    // Source filter
    if (wardrobeFilterSource !== "all") {
      if (s.sourceCategory !== wardrobeFilterSource) return false;
    }

    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div style="color: var(--muted-foreground); font-size: 12px; text-align: center; padding: 24px;">По заданным фильтрам сеты не найдены</div>';
    return;
  }

  container.innerHTML = "";
  filtered.forEach(s => {
    const card = document.createElement("div");
    card.className = `wardrobe-set-card ${s.isComplete ? 'is-complete' : ''}`;

    let prefetchTimer = null;
    card.addEventListener("pointerenter", () => {
      prefetchTimer = setTimeout(() => {
        const urls = (s.parts || []).map(p => p.imageUrl || p.cardPreviewUrl || p.imageBackUrl).filter(Boolean);
        if (urls.length > 0) batchLoadAssets(urls);
      }, 120);
    });
    card.addEventListener("pointerleave", () => {
      if (prefetchTimer) clearTimeout(prefetchTimer);
    });

    const bonuses = [];
    const maxB = s.maxBonus || {};
    const colB = s.collectedBonus || {};
    ["knife", "poison", "gunshot", "energy", "biceps"].forEach(b => {
      if (maxB[b]) {
        bonuses.push(`
          <span class="set-bonus-badge ${colB[b] ? 'green' : 'gold'}">
            ${gameIcon(b, '', 'game-icon-sm')} +${colB[b] || 0}/${maxB[b]}
          </span>
        `);
      }
    });

    const isAllOwned = s.totalParts > 0 && s.ownedParts === s.totalParts;
    const hasAnyEquipped = (s.parts || []).some(p => p.equipped);
    const ownedPartsList = (s.parts || []).filter(p => p.owned);

    card.innerHTML = `
      <div class="set-header">
        <div class="set-top-row">
          <div class="set-title-group">
            <div class="set-name">
              <span>${s.setName || 'Сет'}</span>
              ${s.isComplete ? '<span style="color: #34d399; font-size: 11px;">✓</span>' : ''}
            </div>
            ${s.sourceText ? `<span class="set-source-pill">${s.sourceText}</span>` : ''}
          </div>
          <span class="set-progress-badge ${s.isComplete ? 'complete' : ''}">
            ${s.progress || '0/0'}
          </span>
        </div>

        <div class="set-bonuses-row">
          ${bonuses.join("")}
        </div>

        <div class="set-controls-row">
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-primary btn-sm btn-equip-set" ${ownedPartsList.length === 0 ? 'disabled' : ''}>
              ${isAllOwned ? 'Надеть сет' : `Надеть (${ownedPartsList.length})`}
            </button>
            ${hasAnyEquipped ? '<button class="btn btn-secondary btn-sm btn-unequip-set">Снять</button>' : ''}
            <button class="btn btn-secondary btn-sm btn-preview-set" title="Примерить весь сет">
              🪞 Примерка
            </button>
          </div>
          <button class="btn btn-secondary btn-sm btn-toggle-parts" style="font-size: 11px;">
            Части (${s.totalParts}) ▼
          </button>
        </div>
      </div>

      <div class="set-parts-container" style="display: none;"></div>
    `;

    // Toggle accordion (ленивая отрисовка карточек частей)
    const toggleBtn = card.querySelector(".btn-toggle-parts");
    const partsCont = card.querySelector(".set-parts-container");
    toggleBtn?.addEventListener("click", () => {
      const isHidden = partsCont.style.display === "none";
      if (isHidden && !partsCont.hasChildNodes()) {
        renderLazySetParts(partsCont, s);
      }
      partsCont.style.display = isHidden ? "block" : "none";
      toggleBtn.textContent = isHidden ? `Части (${s.totalParts}) ▲` : `Части (${s.totalParts}) ▼`;
    });

    // Equip Set button
    card.querySelector(".btn-equip-set")?.addEventListener("click", async () => {
      const zonesMap = {};
      ownedPartsList.forEach(p => {
        zonesMap[String(p.zone)] = {
          id: p.id,
          imageUrl: p.imageUrl,
        };
      });
      try {
        const kind = wardrobeSubtab === "tattoos" ? "tattoo_set" : "clothing_set";
        const res = await apiFetch("/actions/wardrobe/equip", {
          method: "POST",
          body: JSON.stringify({ kind, zonesMap }),
        });
        if (res.success) {
          showToast(`Сет «${s.setName}» надет!`, "success");
          loadWardrobe();
          loadProfile();
        }
      } catch (e) {
        showToast(`Ошибка: ${e.message}`, "error");
      }
    });

    // Unequip Set button
    card.querySelector(".btn-unequip-set")?.addEventListener("click", async () => {
      const equippedParts = (s.parts || []).filter(p => p.equipped);
      try {
        const kind = wardrobeSubtab === "tattoos" ? "tattoo" : "clothing";
        for (const p of equippedParts) {
          await apiFetch("/actions/wardrobe/equip", {
            method: "POST",
            body: JSON.stringify({ kind, action: "unequip", zone: p.zone }),
          });
        }
        showToast(`Сет «${s.setName}» снят`, "info");
        loadWardrobe();
        loadProfile();
      } catch (e) {
        showToast(`Ошибка: ${e.message}`, "error");
      }
    });

    // Preview Set in Fitting Room
    card.querySelector(".btn-preview-set")?.addEventListener("click", () => {
      openFittingRoom({ type: "set", set: s, kind: wardrobeSubtab });
    });

    container.appendChild(card);
  });
}

function renderLazySetParts(partsCont, s) {
  partsCont.innerHTML = `
    <div class="set-parts-grid">
      ${(s.parts || []).map(p => `
        <div class="set-part-card ${!p.owned ? 'dim' : ''}" data-part-id="${p.id}">
          <div class="part-thumb-wrap" title="Нажмите для примерки">
            ${p.cardPreviewUrl || p.imageUrl ? `<img src="${p.cardPreviewUrl || p.imageUrl}" class="part-thumb-img" alt="${p.name}" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ''}
            ${p.equipped ? '<span class="part-status-badge equipped">★</span>' : (p.owned ? '<span class="part-status-badge owned">✓</span>' : '')}
          </div>
          <div class="part-name" title="${p.name}">${p.name}</div>
          <div class="part-bonus-text">
            ${Object.entries(p.bonuses || {}).map(([k, v]) => `${gameIcon(k, '', 'game-icon-sm')} +${v}`).join(" ")}
          </div>
          <div style="margin-top: 4px;">
            ${p.equipped ? `
              <button class="btn btn-secondary btn-sm btn-part-action" data-action="unequip" data-id="${p.id}" data-zone="${p.zone}" style="width: 100%; font-size: 10px; padding: 2px 4px;">
                Снять
              </button>
            ` : (p.owned ? `
              <button class="btn btn-primary btn-sm btn-part-action" data-action="equip" data-id="${p.id}" data-zone="${p.zone}" data-img="${p.imageUrl || ''}" style="width: 100%; font-size: 10px; padding: 2px 4px;">
                Надеть
              </button>
            ` : (p.canBuy ? `
              <button class="btn btn-sm btn-part-buy" data-id="${p.id}" style="width: 100%; font-size: 10px; padding: 2px 4px; background: rgba(251, 191, 36, 0.15); border-color: #fbbf24; color: #fbbf24;">
                Купить ${p.price} ${gameIcon(p.currency, '', 'game-icon-sm')}
              </button>
            ` : `
              <span style="font-size: 9px; color: var(--muted-foreground); text-align: center; display: block;">Недоступно</span>
            `))}
          </div>
        </div>
      `).join("")}
    </div>
  `;

  // Навешиваем слушатели на кнопки части
  partsCont.querySelectorAll(".btn-part-action").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const action = btn.getAttribute("data-action");
      const itemId = btn.getAttribute("data-id");
      const zone = btn.getAttribute("data-zone");
      const imageUrl = btn.getAttribute("data-img") || "";
      const kind = wardrobeSubtab === "tattoos" ? "tattoo" : "clothing";
      try {
        const res = await apiFetch("/actions/wardrobe/equip", {
          method: "POST",
          body: JSON.stringify({ kind, action, id: parseInt(itemId), zone: parseInt(zone), imageUrl }),
        });
        if (res.success) {
          showToast(action === "equip" ? "Предмет надет" : "Предмет снят", "success");
          loadWardrobe();
          loadProfile();
        }
      } catch (err) {
        showToast(`Ошибка: ${err.message}`, "error");
      }
    });
  });

  partsCont.querySelectorAll(".btn-part-buy").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const itemId = btn.getAttribute("data-id");
      const kind = wardrobeSubtab === "tattoos" ? "tattoo" : "clothing";
      if (!confirm(`Купить этот предмет?`)) return;
      try {
        const res = await apiFetch("/actions/wardrobe/buy", {
          method: "POST",
          body: JSON.stringify({ kind, id: parseInt(itemId) }),
        });
        if (res.success) {
          showToast("Предмет успешно куплен!", "success");
          loadWardrobe();
          loadProfile();
        }
      } catch (err) {
        showToast(`Ошибка покупки: ${err.message}`, "error");
      }
    });
  });

  partsCont.querySelectorAll(".part-thumb-wrap").forEach(thumb => {
    thumb.addEventListener("click", () => {
      const partCard = thumb.closest(".set-part-card");
      const pid = parseInt(partCard.getAttribute("data-part-id"));
      const part = (s.parts || []).find(p => p.id === pid);
      if (part) {
        openFittingRoom({ type: "item", item: part, kind: wardrobeSubtab });
      }
    });
  });
}

function renderWardrobeCameras() {
  const container = document.getElementById("wardrobe-cameras-grid");
  if (!container || !wardrobeData) return;

  const cameras = wardrobeData.cameras || [];
  const ownedCount = wardrobeData.ownedCamerasCount || 0;
  const totalCount = wardrobeData.totalCamerasCount || cameras.length;
  const pct = totalCount > 0 ? Math.round((ownedCount / totalCount) * 100) : 0;

  const progText = document.getElementById("cameras-progress-text");
  const progFill = document.getElementById("cameras-progress-fill");
  if (progText) progText.textContent = `${ownedCount} / ${totalCount}`;
  if (progFill) progFill.style.width = `${pct}%`;

  container.innerHTML = "";
  cameras.forEach(cam => {
    const card = document.createElement("div");
    card.className = `camera-card ${cam.equipped ? 'equipped' : ''}`;
    card.innerHTML = `
      <div class="camera-thumb-wrap" title="Нажмите для примерки">
        ${cam.imageUrl ? `<img src="${cam.imageUrl}" class="camera-thumb-img" alt="${cam.name}" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ''}
        ${cam.equipped ? '<span class="part-status-badge equipped" style="top:4px;right:4px;">Выбрана</span>' : ''}
      </div>
      <div class="camera-details">
        <div class="camera-name">${cam.name}</div>
        <div style="margin-top: 6px;">
          ${cam.equipped ? `
            <button class="btn btn-secondary btn-sm" disabled style="width: 100%; font-size: 11px;">Выбрана</button>
          ` : (cam.owned ? `
            <button class="btn btn-primary btn-sm btn-select-camera" data-id="${cam.id}" style="width: 100%; font-size: 11px;">
              Выбрать
            </button>
          ` : (cam.price > 0 ? `
            <button class="btn btn-sm btn-buy-camera" data-id="${cam.id}" style="width: 100%; font-size: 11px; background: rgba(251, 191, 36, 0.15); border-color: #fbbf24; color: #fbbf24;">
              Купить (${cam.price} ${gameIcon(cam.currency, '', 'game-icon-sm')})
            </button>
          ` : `
            <button class="btn btn-secondary btn-sm" disabled style="width: 100%; font-size: 11px;">Недоступна</button>
          `))}
        </div>
      </div>
    `;

    card.querySelector(".camera-thumb-wrap")?.addEventListener("click", () => {
      openFittingRoom({ type: "camera", camera: cam });
    });

    card.querySelector(".btn-select-camera")?.addEventListener("click", async () => {
      try {
        const res = await apiFetch("/actions/wardrobe/equip", {
          method: "POST",
          body: JSON.stringify({ kind: "camera", id: cam.id }),
        });
        if (res.success) {
          showToast(`Хата «${cam.name}» выбрана!`, "success");
          loadWardrobe();
          loadProfile();
        }
      } catch (e) {
        showToast(`Ошибка: ${e.message}`, "error");
      }
    });

    card.querySelector(".btn-buy-camera")?.addEventListener("click", async () => {
      if (!confirm(`Купить хату «${cam.name}»?`)) return;
      try {
        const res = await apiFetch("/actions/wardrobe/buy", {
          method: "POST",
          body: JSON.stringify({ kind: "camera", id: cam.id }),
        });
        if (res.success) {
          showToast(`Хата «${cam.name}» успешно куплена!`, "success");
          loadWardrobe();
          loadProfile();
        }
      } catch (e) {
        showToast(`Ошибка покупки: ${e.message}`, "error");
      }
    });

    container.appendChild(card);
  });
}

// ============================================================================
// FITTING ROOM MODAL & CANVAS RENDERER
// ============================================================================

// ============================================================================
// FITTING ROOM MODAL & ANIMATED CANVAS RENDERER (1-v-1 REFERENCE ENGINE)
// ============================================================================

let fittingRoomAnimFrameId = null;
let fittingRoomLayersReady = false;
let fittingRoomActiveLayers = [];
let fittingRoomRoomData = null;
let drawFittingRoomToken = 0;

const _atlasCache = new Map();
const _canvasImgCache = new Map();

function proxyAssetUrl(url) {
  if (!url) return "";
  let clean = String(url).trim();
  if (clean.startsWith(`${API_BASE}/assets/proxy`) || clean.startsWith("/api/v1/assets/proxy") || clean.startsWith("/static")) {
    return clean;
  }
  const cdnMarker = "/assets/";
  const idx = clean.indexOf(cdnMarker);
  if (idx !== -1) {
    const relPath = "assets/" + clean.substring(idx + cdnMarker.length);
    return `${API_BASE}/assets/proxy?path=${encodeURIComponent(relPath)}`;
  }
  if (clean.startsWith("http://") || clean.startsWith("https://")) {
    try {
      const parsed = new URL(clean);
      const p = parsed.pathname.replace(/^\/+/, "");
      return `${API_BASE}/assets/proxy?path=${encodeURIComponent(p)}`;
    } catch (e) { }
  }
  const p = clean.replace(/^\/+/, "");
  return `${API_BASE}/assets/proxy?path=${encodeURIComponent(p)}`;
}

function extractRawAssetPath(url) {
  if (!url) return "";
  let clean = String(url).trim();
  if (clean.includes("path=")) {
    try {
      const parts = clean.split("path=");
      return decodeURIComponent(parts[1].split("&")[0]).replace(/^\/+/, "");
    } catch {
      // fallback
    }
  }
  const cdnMarker = "/assets/";
  const idx = clean.indexOf(cdnMarker);
  if (idx !== -1) {
    return "assets/" + clean.substring(idx + cdnMarker.length);
  }
  return clean.replace(/^\/+/, "");
}

let _assetCachePromise = null;
function getBrowserAssetCache() {
  if (!_assetCachePromise) {
    if (typeof window !== "undefined" && "caches" in window) {
      _assetCachePromise = caches.open("prison-assets-v1").catch(() => null);
    } else {
      _assetCachePromise = Promise.resolve(null);
    }
  }
  return _assetCachePromise;
}

async function batchLoadAssets(urls) {
  if (!Array.isArray(urls) || urls.length === 0) return;
  const uncached = [];
  for (const u of urls) {
    if (!u) continue;
    const cleanUrl = proxyAssetUrl(u);
    if (!_canvasImgCache.has(cleanUrl)) {
      const rawPath = extractRawAssetPath(u);
      if (rawPath && !rawPath.startsWith("/static")) {
        uncached.push(rawPath);
      }
    }
  }
  if (uncached.length >= 3) {
    try {
      const resp = await fetch(`${API_BASE}/assets/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paths: uncached.slice(0, 50) }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const items = data.items || {};
        for (const [p, durl] of Object.entries(items)) {
          const proxiedUrl = proxyAssetUrl(p);
          if (!_canvasImgCache.has(proxiedUrl)) {
            const img = new Image();
            img.crossOrigin = "anonymous";
            const pLoad = new Promise((resolve) => {
              img.onload = () => resolve(img);
              img.onerror = () => resolve(null);
              img.src = durl;
            });
            _canvasImgCache.set(proxiedUrl, pLoad);
          }
        }
      }
    } catch (e) {
      console.debug("Batch asset load error:", e);
    }
  }
}

function getCanvasImage(url) {
  if (!url) return Promise.resolve(null);
  const cleanUrl = proxyAssetUrl(url);
  if (_canvasImgCache.has(cleanUrl)) {
    return _canvasImgCache.get(cleanUrl);
  }
  const promise = (async () => {
    try {
      const cache = await getBrowserAssetCache();
      if (cache) {
        const cachedResp = await cache.match(cleanUrl);
        if (cachedResp) {
          const blob = await cachedResp.blob();
          const objUrl = URL.createObjectURL(blob);
          const img = new Image();
          img.crossOrigin = "anonymous";
          return await new Promise((resolve) => {
            img.onload = () => {
              URL.revokeObjectURL(objUrl);
              resolve(img);
            };
            img.onerror = () => {
              URL.revokeObjectURL(objUrl);
              resolve(null);
            };
            img.src = objUrl;
          });
        }
      }
    } catch (e) {
      // fallback to direct load
    }

    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        try {
          if (cleanUrl.startsWith("/api/v1/assets/proxy")) {
            getBrowserAssetCache().then(cache => {
              if (cache) {
                fetch(cleanUrl, { mode: "cors" }).then(res => {
                  if (res.ok) cache.put(cleanUrl, res.clone());
                }).catch(() => { });
              }
            });
          }
        } catch (e) { }
        resolve(img);
      };
      img.onerror = () => resolve(null);
      img.src = cleanUrl;
    });
  })();

  _canvasImgCache.set(cleanUrl, promise);
  return promise;
}

const FITTING_CONFIG = {
  U: { x: 485, y: 217, w: 755, h: 562, r: 20 },
  o: { x: 1055, y: 780, scale: 0.811 },
  e: { cx: 1000, cy: 800, dx: -138, dy: -302, scale: 1.302 },
  b: { x: -241, y: -382, scale: 1.183 },
  f: { x: -245, y: -342, scale: 1.192 },
  h: { x: -244, y: -378, scale: 1.2 },
  m: { x: -244, y: -380, scale: 1.183 },
  defaultKist: "assets/PrisonV3/Clotch/C_Zone6DefaultKist.png",
  playerSprite: "/static/assets/icons/PlayerSprite.png",
  playerSpriteBack: "/static/assets/icons/PlayerSpriteBack.png",
  rotateButton: "/static/assets/icons/back_poworot.webp",
  shiftRooms: new Set(["30", "31", "32", "33", "34", "35", "37"]),
  density: {
    body: { legacyWidth: 489, density: 2 },
    bodyBack: { legacyWidth: 410, density: 880 / 410 },
    eyes: { legacyWidth: 78, density: 2 },
    nose: { legacyWidth: 198, density: 2 },
    mouth: { legacyWidth: 230, density: 2 },
    beard: { legacyWidth: 410, density: 2.4 },
  },
  brushOffsets: {
    1: { x: -14, y: 83, scale: 1.183 },
    2: { x: -151, y: -24, scale: 1.183 },
    3: { x: -222, y: -256, scale: 1.283 },
    4: { x: -235, y: -265, scale: 1.2 },
    5: { x: -215, y: -285, scale: 1.3 },
    6: { x: -215, y: -250, scale: 1.2 },
    7: { x: -238, y: -255, scale: 1.2 },
    8: { x: -236, y: -159, scale: 1.2 },
    9: { x: -246, y: -305, scale: 1.5 },
    10: { x: -246, y: -305, scale: 1.5 },
    11: { x: -212, y: -275, scale: 1.5 },
    12: { x: -228, y: -300, scale: 1.5 },
    13: { x: -265, y: -205, scale: 1.5 },
    14: { x: -245, y: -310, scale: 1.1 },
    15: { x: -250, y: -250, scale: 1.3 },
    16: { x: -230, y: -190, scale: 1.5 },
    17: { x: -210, y: -225, scale: 1.5 },
    18: { x: -232, y: -302, scale: 1.5 },
    19: { x: -222, y: -250, scale: 1.3 },
    20: { x: -242, y: -250, scale: 1.3 },
    21: { x: -218, y: -212, scale: 1.5 },
    22: { x: -225, y: -228, scale: 1.6 },
    23: { x: -235, y: -280, scale: 1.5 },
    24: { x: -235, y: -225, scale: 1.7 },
    25: { x: -215, y: -245, scale: 1.3 },
    26: { x: -220, y: -222, scale: 1.3 },
    27: { x: -253, y: -276, scale: 1.63 },
    28: { x: -265, y: -191, scale: 1.25 },
    29: { x: -245, y: -343, scale: 1.2 },
    30: { x: -205, y: -259, scale: 1.2 },
    31: { x: -213, y: -268, scale: 1.2 },
    32: { x: -265, y: -292, scale: 1.2 },
    33: { x: -350, y: -390, scale: 1.2 },
    34: { x: -205, y: -162, scale: 1.2 },
    35: { x: -305, y: -250, scale: 1.6 },
    36: { x: -305, y: -280, scale: 1.45 },
    37: { x: -215, y: -252, scale: 1.45 },
    38: { x: -245, y: -283, scale: 1.15 },
    39: { x: -225, y: -240, scale: 1.15 },
    40: { x: -298, y: -254, scale: 1.16 },
    41: { x: -242, y: -288, scale: 1.15 },
    42: { x: -230, y: -180, scale: 1.2 },
    43: { x: -205, y: -246, scale: 1.6 },
    44: { x: -255, y: -262, scale: 1.5 },
    45: { x: -248, y: -130, scale: 1.65 },
    46: { x: -282, y: -298, scale: 1.5 },
    47: { x: -249, y: -255, scale: 1.52 },
    48: { x: -205, y: -197, scale: 1.52 },
    49: { x: -322, y: -288, scale: 1.73 },
    50: { x: -206, y: -406, scale: 1.559 },
    51: { x: -260, y: -246, scale: 1.38, angle: 25 },
    52: { x: -312.8, y: -387.3, scale: 1.42 },
    53: { x: -255.35, y: -249.57, scale: 0.53007 },
    89: { x: -263.3, y: -295.68, scale: 0.79511 },
  },
  staticClothingOffsets: {
    1: { x: -244, y: -382, scale: 1.183 },
    2: { x: -244, y: -380, scale: 1.183 },
    3: { x: -200, y: -650, scale: 0 },
    4: { x: -244, y: -382, scale: 1.183 },
    5: { x: -244, y: -380, scale: 1.183 },
    6: { x: 690, y: 460, scale: 1.183 },
    7: { x: -244, y: -380, scale: 1.183 },
    8: { x: -244, y: -380, scale: 1.183 },
  },
  eyesOffsets: {
    Eyes1: { x: -202, y: -602, scale: 1 },
    Eyes2: { x: -201, y: -598, scale: 0.95 },
    Eyes3: { x: -202, y: -602, scale: 1 },
    Eyes4: { x: -201, y: -602, scale: 1 },
    Eyes5: { x: -202, y: -602, scale: 1 },
    Eyes6: { x: -202, y: -600, scale: 1 },
    Eyes7: { x: -202, y: -599, scale: 1 },
    Eyes8: { x: -202, y: -599, scale: 1 },
    Eyes9: { x: -202, y: -591, scale: 1 },
  },
  faceOffsets: {
    nose: { x: -205, y: -582, scale: 1 },
    mouth: { x: -207, y: -543, scale: 1 },
  },
};

function getResolutionDensity(dim, resConfig) {
  if (!resConfig) return 1;
  const { legacyWidth, density } = resConfig;
  return dim > (legacyWidth * (1 + density)) / 2 ? density : 1;
}

function getSequenceFrame(atlas, timeMs) {
  if (!atlas.sequence || atlas.sequence.length === 0) {
    const firstKey = atlas.order[0];
    return firstKey ? atlas.frames.get(firstKey) : null;
  }
  const total = atlas.sequence.reduce((acc, step) => acc + step.delay, 0);
  if (total <= 0) return atlas.frames.get(atlas.sequence[0].frame);
  let rem = timeMs % total;
  for (const step of atlas.sequence) {
    if (rem < step.delay) {
      let f = atlas.frames.get(step.frame);
      if (!f) {
        const clean = String(step.frame).replace(/\.(png|webp)$/i, "");
        f = atlas.frames.get(clean) || atlas.frames.get(`${clean}.webp`) || atlas.frames.get(`${clean}.png`);
      }
      return f || atlas.frames.values().next().value;
    }
    rem -= step.delay;
  }
  const last = atlas.sequence[atlas.sequence.length - 1];
  return atlas.frames.get(last.frame) || atlas.frames.values().next().value;
}

async function loadAtlas(folder, name, type) {
  const cleanRawFolder = extractRawAssetPath(folder).replace(/\/[^/]+\.(?:png|webp|json)$/i, "").replace(/\/+$/, "") + "/";
  const cacheKey = `${cleanRawFolder}|${name}|${type}`;
  if (_atlasCache.has(cacheKey)) {
    return _atlasCache.get(cacheKey);
  }
  const promise = (async () => {
    try {
      const jsonPath = `${cleanRawFolder}${name}.json`;
      const configPath = `${cleanRawFolder}${name}_config.json`;

      const [atlasJson, configJson] = await Promise.all([
        apiFetch(`/assets/proxy?path=${encodeURIComponent(jsonPath)}`).catch(() => null),
        apiFetch(`/assets/proxy?path=${encodeURIComponent(configPath)}`).catch(() => null),
      ]);
      if (!atlasJson || !atlasJson.frames) return null;

      const metaImg = atlasJson.meta?.image;
      const candidates = type === "png" ? [`${name}.png`] : [metaImg, `${name}.webp`, `${name}.png`].filter(Boolean);
      let pageImg = null;
      for (const cand of new Set(candidates)) {
        pageImg = await getCanvasImage(`${cleanRawFolder}${cand}`);
        if (pageImg) break;
      }
      if (!pageImg) return null;

      const frames = new Map();
      const order = [];
      const rawFrames = atlasJson.frames;
      const parseFrame = (f) => {
        const r = f.frame || f;
        const sss = f.spriteSourceSize || { x: 0, y: 0 };
        const ss = f.sourceSize || { w: r.w, h: r.h };
        return {
          x: r.x,
          y: r.y,
          w: r.w,
          h: r.h,
          ox: sss.x || 0,
          oy: sss.y || 0,
          sw: ss.w,
          sh: ss.h,
        };
      };

      if (Array.isArray(rawFrames)) {
        for (const f of rawFrames) {
          const k = String(f.filename ?? order.length);
          frames.set(k, parseFrame(f));
          order.push(k);
        }
      } else if (rawFrames && typeof rawFrames === "object") {
        for (const [k, f] of Object.entries(rawFrames)) {
          frames.set(k, parseFrame(f));
          order.push(k);
        }
      }
      if (order.length === 0) return null;

      let sequence = null;
      if (Array.isArray(configJson?.sequence) && configJson.sequence.length) {
        sequence = configJson.sequence.map((s) => ({
          frame: String(s.frame),
          delay: Math.max(1, Number(s.delay) || 100),
        }));
      } else if (type === "clothing") {
        sequence = [...order]
          .sort((a, b) => a.localeCompare(b, "en", { numeric: true }))
          .map((f) => ({ frame: f, delay: 45 }));
      } else if (type === "png" || type === "eyes") {
        sequence = [...order]
          .sort((a, b) => a.localeCompare(b, "en", { numeric: true }))
          .map((f) => ({ frame: f, delay: 42 }));
      }

      return {
        page: pageImg,
        frames,
        order,
        sequence,
        zoom: Number(configJson?.zoom) || 1,
      };
    } catch (e) {
      console.warn("Failed to load atlas:", folder, name, e);
      return null;
    }
  })();
  _atlasCache.set(cacheKey, promise);
  return promise;
}

function drawLayer(ctx, layer, timeMs) {
  const [ox, oy] = layer.origin || [0.5, 0.5];
  if (layer.img) {
    const w = layer.trim?.w ?? layer.img.naturalWidth;
    const h = layer.trim?.h ?? layer.img.naturalHeight;
    const density = getResolutionDensity(w, layer.resolution);
    const c = layer.scale / density;
    const fw = layer.img.naturalWidth * c;
    const fh = layer.img.naturalHeight * c;
    if (!fw || !fh) return;
    const dx = layer.x + (((layer.trim?.x ?? 0) - ox * w) * c);
    const dy = layer.y + (((layer.trim?.y ?? 0) - oy * h) * c);
    ctx.drawImage(layer.img, dx, dy, fw, fh);
    return;
  }
  const atlas = layer.atlas;
  if (!atlas) return;
  const frame = getSequenceFrame(atlas, timeMs);
  if (!frame || !frame.w || !frame.h) return;
  const density = getResolutionDensity(frame.sw, layer.resolution);
  const d = layer.scale / density;
  const m = layer.x - ox * frame.sw * d;
  const g = layer.y - oy * frame.sh * d;
  ctx.drawImage(
    atlas.page,
    frame.x,
    frame.y,
    frame.w,
    frame.h,
    m + frame.ox * d,
    g + frame.oy * d,
    frame.w * d,
    frame.h * d
  );
}

let fittingRoomStaticCanvas = null;
let fittingRoomStaticCtx = null;
let fittingRoomTopStaticCanvas = null;
let fittingRoomTopStaticCtx = null;
let fittingRoomAnimLayers = [];

function canRotateFittingPreview(previewData) {
  if (!previewData) return true;
  if (previewData.type === "camera" || previewData.type === "room") return false;
  if (previewData.type === "item") {
    const k = String(previewData.kind || previewData.item?.kind || "").toLowerCase();
    if (k.includes("cloth") || k === "camera" || k === "room") return false;
    return true;
  }
  if (previewData.type === "set") {
    const k = String(previewData.kind || previewData.set?.kind || "").toLowerCase();
    if (k.includes("cloth")) return false;
    return true;
  }
  if (previewData.type === "loot") {
    const itm = previewData.item || {};
    const k = String(itm.kind || "").toLowerCase();
    if (k.includes("cloth") || k === "camera" || k === "room") return false;
    if (Array.isArray(itm.previewParts) && itm.previewParts.length > 0) {
      return itm.previewParts.some(p => String(p.kind || "").toLowerCase().includes("tattoo"));
    }
    return k.includes("tattoo");
  }
  return true;
}

function formatFittingBonusesHtml(bonuses) {
  if (!bonuses || typeof bonuses !== "object") return "";
  const entries = Object.entries(bonuses).filter(([, v]) => Number(v) > 0);
  if (entries.length === 0) return "";
  return entries
    .map(([k, v]) => `<span class="set-bonus-badge gold" style="margin-right:4px;">${gameIcon(k, '', 'game-icon-sm')} +${v}</span>`)
    .join("");
}

function extractRoomFolderId(cameraUrl, fallbackId = "1") {
  const s = String(cameraUrl || "");
  const m1 = s.match(/RoomCameraUrl\/([^/?#&]+)\//i);
  if (m1) return m1[1];
  const m2 = s.match(/room_(\d+)\.(?:webp|png)/i);
  if (m2) return m2[1];
  return String(fallbackId || "1");
}

function drawFittingRoomImage(ctx, img, roomFolderId) {
  if (!ctx || !img || img.naturalWidth <= 1 || img.naturalHeight <= 1) return;
  ctx.save();
  try {
    ctx.translate(-FITTING_CONFIG.U.x, -FITTING_CONFIG.U.y);
    if (img.naturalWidth === 755 && img.naturalHeight === 562) {
      ctx.drawImage(img, FITTING_CONFIG.U.x, FITTING_CONFIG.U.y, FITTING_CONFIG.U.w, FITTING_CONFIG.U.h);
    } else {
      const scale = 1.302 * (580 / (img.naturalWidth || 580));
      const nw = img.naturalWidth * scale;
      const nh = img.naturalHeight * scale;
      const isShift = FITTING_CONFIG.shiftRooms.has(String(roomFolderId));
      const dx = isShift ? FITTING_CONFIG.e.dx - 376 : FITTING_CONFIG.e.dx;
      const dy = isShift ? FITTING_CONFIG.e.dy - 279 : FITTING_CONFIG.e.dy;
      ctx.drawImage(
        img,
        FITTING_CONFIG.e.cx + dx - nw / 2,
        FITTING_CONFIG.e.cy + dy - nh / 2,
        nw,
        nh
      );
    }
  } finally {
    ctx.restore();
  }
}

function startFittingRoomLoop() {
  if (fittingRoomAnimFrameId) {
    cancelAnimationFrame(fittingRoomAnimFrameId);
    fittingRoomAnimFrameId = null;
  }

  const stage = document.getElementById("fitting-stage");
  if (!stage) return;
  const canvas = stage.querySelector("#fitting-main-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  function renderFrame(timeMs) {
    const modal = document.getElementById("modal-fitting-room");
    if (!modal || modal.style.display === "none") {
      fittingRoomAnimFrameId = null;
      return;
    }

    if (document.hidden) {
      fittingRoomAnimFrameId = requestAnimationFrame(renderFrame);
      return;
    }

    const dpr = canvas.width / FITTING_CONFIG.U.w; // 2 (1510 / 755)
    let curRoomId = null;
    ctx.save();
    try {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, FITTING_CONFIG.U.w, FITTING_CONFIG.U.h);

      // 1. Фон хаты: официальный Spine / room.bundle ("back") или статический оригинальный фон + эффекты effect_config
      curRoomId = fittingRoomRoomData
        ? (Number(extractRoomFolderId(fittingRoomRoomData.url || fittingRoomRoomData.img?.src, fittingRoomRoomData.id)) || fittingRoomRoomData.id)
        : null;
      const roomPlayer = window.SpineRoomPlayer;
      let fullBgDrawn = false;
      if (curRoomId && roomPlayer && roomPlayer.hasFullBackground(curRoomId)) {
        fullBgDrawn = roomPlayer.renderBack(ctx, FITTING_CONFIG.U.w, FITTING_CONFIG.U.h, timeMs, curRoomId);
      }
      if (!fullBgDrawn) {
        if (fittingRoomRoomData && fittingRoomRoomData.img && fittingRoomRoomData.img.naturalWidth > 1) {
          drawFittingRoomImage(ctx, fittingRoomRoomData.img, curRoomId);
        } else {
          ctx.fillStyle = "#1e2124";
          ctx.fillRect(0, 0, FITTING_CONFIG.U.w, FITTING_CONFIG.U.h);
        }
      }
      if (curRoomId && roomPlayer && roomPlayer.isReady(curRoomId)) {
        roomPlayer.renderEffects(ctx, FITTING_CONFIG.U.w, FITTING_CONFIG.U.h, timeMs, curRoomId);
      }

      // 2. Персонаж (тело + тату + шмот) строго поверх фона
      if (fittingRoomStaticCanvas) {
        ctx.drawImage(fittingRoomStaticCanvas, 0, 0, FITTING_CONFIG.U.w, FITTING_CONFIG.U.h);
      }

      // 3. Живые анимационные слои персонажа (EyesAnim, BrushAnim)
      if (fittingRoomAnimLayers && fittingRoomAnimLayers.length > 0) {
        ctx.save();
        ctx.translate(-FITTING_CONFIG.U.x, -FITTING_CONFIG.U.y);
        ctx.translate(FITTING_CONFIG.o.x, FITTING_CONFIG.o.y);
        ctx.scale(FITTING_CONFIG.o.scale, FITTING_CONFIG.o.scale);

        for (const layer of fittingRoomAnimLayers) {
          if (layer.angle) {
            ctx.save();
            ctx.translate(layer.x, layer.y);
            ctx.rotate((layer.angle * Math.PI) / 180);
            drawLayer(ctx, { ...layer, x: 0, y: 0 }, timeMs);
            ctx.restore();
          } else {
            drawLayer(ctx, layer, timeMs);
          }
        }
        ctx.restore();
      }

      // 4. Головные уборы и верхняя одежда (зоны 4, 8, 3) строго поверх EyesAnim
      if (fittingRoomTopStaticCanvas) {
        ctx.drawImage(fittingRoomTopStaticCanvas, 0, 0, FITTING_CONFIG.U.w, FITTING_CONFIG.U.h);
      }

      // 4. Передний слой room.bundle (для хаты 54 — gameBirthday_back_front со столом, тортом, свечами и котом строго поверх персонажа)
      if (curRoomId && roomPlayer && roomPlayer.hasBundleFront(curRoomId)) {
        roomPlayer.renderFront(ctx, FITTING_CONFIG.U.w, FITTING_CONFIG.U.h, timeMs, curRoomId);
      }
    } finally {
      ctx.restore();
    }

    const needAnimLoop =
      (fittingRoomAnimLayers && fittingRoomAnimLayers.length > 0) ||
      (curRoomId && window.SpineRoomPlayer && window.SpineRoomPlayer.isReady(curRoomId));

    if (needAnimLoop) {
      fittingRoomAnimFrameId = requestAnimationFrame(renderFrame);
    } else {
      fittingRoomAnimFrameId = null;
    }
  }

  renderFrame(performance.now());
}

function normalizeSetName(name) {
  if (!name) return "";
  let s = String(name).replace(/^(?:Комплект|Сет|Сборка)\s+/i, "");
  return s.replace(/["'«»]/g, "").trim().toLowerCase();
}

let fittingRenderToken = 0;
let fittingViewSide = "front"; // "front" | "back"

async function prepareFittingRoomLayers(currentToken = null) {
  let charLayers = (wardrobeData && wardrobeData.characterLayers && Object.keys(wardrobeData.characterLayers.clothingZones || {}).length > 0)
    ? wardrobeData.characterLayers
    : (window.characterLayers || (playerProfile && playerProfile.characterLayers) || {});

  if (!charLayers || !charLayers.clothingZones || Object.keys(charLayers.clothingZones).length === 0) {
    try {
      const res = await apiFetch("/wardrobe/overview");
      if (res && res.characterLayers) {
        window.wardrobeData = res;
        charLayers = res.characterLayers;
      } else {
        const prof = await apiFetch("/live/profile");
        if (prof && prof.characterLayers) {
          charLayers = prof.characterLayers;
          window.characterLayers = prof.characterLayers;
        }
      }
    } catch (e) {
      console.warn("Could not preload character layers:", e);
    }
  }

  // 1. Camera Room (Хата) — извлекаем реальный ID папки RoomCameraUrl (например 27 для Бугра, 30 для Гризли, 54 для Торта Люськи)
  let cameraUrl = charLayers.roomCameraUrl || "assets/PrisonV3/RoomCameraUrl/1/1.png";
  let roomFolderId = extractRoomFolderId(charLayers.roomCameraRaw || cameraUrl, "1");
  let cameraId = Number(roomFolderId) || 1;
  if (fittingRoomPreview) {
    if (fittingRoomPreview.type === "camera") {
      cameraUrl = fittingRoomPreview.camera.imageUrl || cameraUrl;
      cameraId = fittingRoomPreview.camera.id || cameraId;
      roomFolderId = String(
        extractRoomFolderId(
          fittingRoomPreview.camera.rawImageUrl || cameraUrl,
          fittingRoomPreview.camera.folderId || fittingRoomPreview.camera.id
        )
      );
    } else if (fittingRoomPreview.type === "loot" && fittingRoomPreview.item.kind === "camera") {
      cameraUrl = fittingRoomPreview.item.previewUrl || cameraUrl;
      cameraId = fittingRoomPreview.item.id || cameraId;
      roomFolderId = extractRoomFolderId(cameraUrl, fittingRoomPreview.item.id);
    }
  }

  const roomImg = await getCanvasImage(cameraUrl);
  if (currentToken && currentToken !== fittingRenderToken) return;

  let resolvedRoomImg = roomImg;
  if (!resolvedRoomImg || resolvedRoomImg.naturalWidth <= 1) {
    resolvedRoomImg = await getCanvasImage(charLayers.roomCameraUrl || "assets/PrisonV3/RoomCameraUrl/default/1.png");
    if (currentToken && currentToken !== fittingRenderToken) return;
  }

  fittingRoomRoomData = { id: roomFolderId, cameraId, img: resolvedRoomImg, url: cameraUrl };

  const layers = [];

  // Tattoos merge from preview
  const tattooZones = { ...(charLayers.tattooZones || {}) };
  if (fittingRoomPreview) {
    if (fittingRoomPreview.type === "item" && (fittingRoomPreview.kind === "tattoos" || fittingRoomPreview.item.kind === "tattoo")) {
      tattooZones[String(fittingRoomPreview.item.zone || 1)] = {
        imageUrl: fittingRoomPreview.item.imageUrl || fittingRoomPreview.item.previewUrl || fittingRoomPreview.item.cardPreviewUrl
      };
    } else if (fittingRoomPreview.type === "set" && (fittingRoomPreview.kind === "tattoos" || fittingRoomPreview.set.kind === "tattoo_set")) {
      (fittingRoomPreview.set.parts || []).forEach(p => {
        tattooZones[String(p.zone || 1)] = { imageUrl: p.imageUrl || p.previewUrl || p.cardPreviewUrl };
      });
    } else if (fittingRoomPreview.type === "loot") {
      const itm = fittingRoomPreview.item;
      if (itm.previewParts && Array.isArray(itm.previewParts) && itm.previewParts.length > 0) {
        itm.previewParts.forEach(p => {
          if (p.kind === "tattoo") {
            tattooZones[String(p.zone || 1)] = { imageUrl: p.imageUrl };
          }
        });
      } else if (itm.kind === "tattoo_set") {
        const norm = normalizeSetName(itm.name);
        if (wardrobeData && wardrobeData.sets) {
          const allTattooSets = [
            ...(wardrobeData.sets.regular?.tattoos || []),
            ...(wardrobeData.sets.blind_kolsik?.tattoos || []),
          ];
          const matchedSet = allTattooSets.find(s => normalizeSetName(s.setName) === norm);
          if (matchedSet && Array.isArray(matchedSet.parts)) {
            matchedSet.parts.forEach(p => {
              tattooZones[String(p.zone || 1)] = { imageUrl: p.imageUrl || p.cardPreviewUrl };
            });
          }
        }
      } else if (itm.kind === "tattoo") {
        tattooZones[String(itm.zone || 1)] = { imageUrl: itm.previewUrl };
      }
    }
  }

  // ========================================================================
  // RENDER BACK VIEW (Вид со спины: PlayerSpriteBack + зоны 23..42 + back clothing)
  // ========================================================================
  if (fittingViewSide === "back") {
    // 2a. PlayerSpriteBack Base Body (410 x 574 normalized, density: 880 / 410)
    const backBodyImg = await getCanvasImage(FITTING_CONFIG.playerSpriteBack);
    if (currentToken && currentToken !== fittingRenderToken) return;
    if (backBodyImg) {
      layers.push({
        x: 0,
        y: 0,
        scale: 1.192,
        img: backBodyImg,
        origin: [1, 1],
        resolution: FITTING_CONFIG.density.bodyBack || { legacyWidth: 410, density: 880 / 410 },
      });
    }

    // 2b. Back Tattoos (strictly zones 23..42, identical 410x574 geometry)
    for (const [zStr, tObj] of Object.entries(tattooZones)) {
      const zNum = Number(zStr);
      if (zNum < 23 || zNum > 42) continue;
      const tUrl = typeof tObj === "object" ? tObj.imageUrl || tObj.url : String(tObj);
      if (!tUrl) continue;
      const tImg = await getCanvasImage(tUrl);
      if (currentToken && currentToken !== fittingRenderToken) return;
      if (tImg) {
        layers.push({
          x: 0,
          y: 0,
          scale: 1.192,
          origin: [1, 1],
          img: tImg,
          resolution: { legacyWidth: 410, density: 1 },
        });
      }
    }

    // 2c. Back Clothing (clothingBackZones - only clothing with confirmed back image)
    const clothingBackZones = { ...(charLayers.clothingBackZones || {}) };
    if (fittingRoomPreview) {
      if (fittingRoomPreview.type === "item" && (fittingRoomPreview.kind === "clothing" || fittingRoomPreview.item?.kind === "clothing")) {
        const itm = fittingRoomPreview.item;
        if (itm.imageBackUrl || itm.backImageUrl) {
          clothingBackZones[String(itm.zone || 1)] = itm.imageBackUrl || itm.backImageUrl;
        }
      } else if (fittingRoomPreview.type === "set" && (fittingRoomPreview.kind === "clothing" || fittingRoomPreview.set?.kind === "clothing_set")) {
        (fittingRoomPreview.set.parts || []).forEach(p => {
          if (p.imageBackUrl || p.backImageUrl) {
            clothingBackZones[String(p.zone || 1)] = p.imageBackUrl || p.backImageUrl;
          }
        });
      } else if (fittingRoomPreview.type === "loot") {
        const itm = fittingRoomPreview.item;
        if (itm.previewParts && Array.isArray(itm.previewParts)) {
          itm.previewParts.forEach(p => {
            if (p.kind === "clothing" && (p.imageBackUrl || p.backImageUrl)) {
              clothingBackZones[String(p.zone || 1)] = p.imageBackUrl || p.backImageUrl;
            }
          });
        }
      }
    }
    for (const [z, cVal] of Object.entries(clothingBackZones)) {
      if (!cVal) continue;
      const cUrl = typeof cVal === "object" ? cVal.imageUrl || cVal.url : String(cVal);
      if (!cUrl) continue;
      const cImg = await getCanvasImage(cUrl);
      if (currentToken && currentToken !== fittingRenderToken) return;
      if (cImg) {
        layers.push({
          x: 0,
          y: 0,
          scale: 1.192,
          origin: [1, 1],
          img: cImg,
          resolution: { legacyWidth: 410, density: 1 },
        });
      }
    }

    // 2d. Beard if any
    const beardPhase = Number(charLayers.beardPhase) || 0;
    if (beardPhase > 0) {
      const beardUrl = `assets/PrisonV3/Beard/BardDayBack/${beardPhase}.png`;
      let beardImg = await getCanvasImage(beardUrl);
      if (!beardImg) {
        beardImg = await getCanvasImage(`assets/Beard/BardDayBack/${beardPhase}.png`);
      }
      if (currentToken && currentToken !== fittingRenderToken) return;
      if (beardImg) {
        layers.push({
          x: 0,
          y: 0,
          scale: 1.192,
          origin: [1, 1],
          img: beardImg,
          resolution: FITTING_CONFIG.density.beard,
        });
      }
    }

  } else {
    // ========================================================================
    // RENDER FRONT VIEW (Вид спереди: PlayerSprite + зоны 1..22 + лицо + одежда)
    // ========================================================================

    // 2a. Base Player Body Sprite
    const bodyImg = await getCanvasImage(FITTING_CONFIG.playerSprite);
    if (currentToken && currentToken !== fittingRenderToken) return;
    if (bodyImg) {
      layers.push({
        x: 0,
        y: 0,
        scale: 1,
        img: bodyImg,
        origin: [1, 1],
        resolution: FITTING_CONFIG.density.body,
      });
    }

    // 2b. Front Tattoos: zones 1..13, 15..22
    for (const [zStr, tObj] of Object.entries(tattooZones)) {
      const zNum = Number(zStr);
      if (zNum === 14) continue;
      if (zNum >= 23) continue; // CRITICAL: zones 23..42 are strictly for PlayerSpriteBack, not front view!
      const tUrl = typeof tObj === "object" ? tObj.imageUrl || tObj.url : String(tObj);
      if (!tUrl) continue;
      const tImg = await getCanvasImage(tUrl);
      if (currentToken && currentToken !== fittingRenderToken) return;
      if (tImg) {
        layers.push({ ...FITTING_CONFIG.f, img: tImg });
      }
    }

    // 2c. Face (Eyes atlas, Nose, Mouth) - Drawn strictly ABOVE tattoos so chest/neck tattoos never occlude face!
    const face = charLayers.face || {};
    const eyesUrl = face.eyes || face.eyesUrl || "assets/PrisonV3/Face/EyesAnim/Eyes3/Eyes3.png";
    const rawEyesFolder = extractRawAssetPath(eyesUrl).replace(/\/[^/]+\.(?:png|webp|json)$/i, "").replace(/\/+$/, "") + "/";
    const eyesName = rawEyesFolder.split("/").filter(Boolean).pop() || "Eyes3";
    if (eyesUrl.includes("/EyesAnim/")) {
      const atlas = await loadAtlas(rawEyesFolder, eyesName, "png");
      const offset = FITTING_CONFIG.eyesOffsets[eyesName] || { x: -202, y: -602, scale: 1 };
      if (atlas) {
        layers.push({ ...offset, atlas, resolution: FITTING_CONFIG.density.eyes });
      }
    } else {
      const eyesImg = await getCanvasImage(eyesUrl);
      if (eyesImg) {
        layers.push({ ...FITTING_CONFIG.eyesOffsets.Eyes3, img: eyesImg, resolution: FITTING_CONFIG.density.eyes });
      }
    }

    const noseUrl = face.nose || face.noseUrl || "assets/PrisonV3/Face/Nose/Nose1.png";
    const noseImg = await getCanvasImage(noseUrl);
    if (noseImg) {
      layers.push({ ...FITTING_CONFIG.faceOffsets.nose, img: noseImg, resolution: FITTING_CONFIG.density.nose });
    }

    const mouthUrl = face.mouth || face.mouthUrl || "assets/PrisonV3/Face/Mouth/Mouth1.png";
    const mouthImg = await getCanvasImage(mouthUrl);
    if (mouthImg) {
      layers.push({ ...FITTING_CONFIG.faceOffsets.mouth, img: mouthImg, resolution: FITTING_CONFIG.density.mouth });
    }

    // 2d. Clothing & Beard
    const clothingZones = { ...(charLayers.clothingZones || {}) };
    if (fittingRoomPreview) {
      if (fittingRoomPreview.type === "item" && (fittingRoomPreview.kind === "clothing" || fittingRoomPreview.item.kind === "clothing")) {
        clothingZones[String(fittingRoomPreview.item.zone || 1)] = fittingRoomPreview.item.imageUrl || fittingRoomPreview.item.previewUrl || fittingRoomPreview.item.cardPreviewUrl;
      } else if (fittingRoomPreview.type === "set" && (fittingRoomPreview.kind === "clothing" || fittingRoomPreview.set.kind === "clothing_set")) {
        (fittingRoomPreview.set.parts || []).forEach(p => {
          clothingZones[String(p.zone || 1)] = p.imageUrl || p.previewUrl || p.cardPreviewUrl;
        });
      } else if (fittingRoomPreview.type === "loot") {
        const itm = fittingRoomPreview.item;
        if (itm.previewParts && Array.isArray(itm.previewParts) && itm.previewParts.length > 0) {
          itm.previewParts.forEach(p => {
            if (p.kind === "clothing") {
              clothingZones[String(p.zone || 1)] = p.imageUrl;
            }
          });
        } else if (itm.kind === "clothing_set") {
          const norm = normalizeSetName(itm.name);
          if (wardrobeData && wardrobeData.sets) {
            const allClothingSets = [
              ...(wardrobeData.sets.regular?.clothing || []),
              ...(wardrobeData.sets.blind_kolsik?.clothing || []),
            ];
            const matchedSet = allClothingSets.find(s => normalizeSetName(s.setName) === norm);
            if (matchedSet && Array.isArray(matchedSet.parts)) {
              matchedSet.parts.forEach(p => {
                clothingZones[String(p.zone || 1)] = p.imageUrl || p.cardPreviewUrl;
              });
            }
          }
        } else if (itm.kind === "clothing") {
          clothingZones[String(itm.zone || 1)] = itm.previewUrl;
        }
      }
    }

    if (!clothingZones["6"]) {
      clothingZones["6"] = FITTING_CONFIG.defaultKist;
    }

    // Footwear / lower clothing: Zone 7 (shoes/socks) first, then Zone 5 (pants) on top
    for (const z of ["7", "5"]) {
      if (clothingZones[z]) {
        const cVal = clothingZones[z];
        const cUrl = typeof cVal === "object" ? cVal.imageUrl || cVal.url : String(cVal);
        if (cUrl) {
          const cImg = await getCanvasImage(cUrl);
          if (cImg) {
            const offset = FITTING_CONFIG.staticClothingOffsets[Number(z)] || { x: 0, y: 0, scale: 1 };
            layers.push({ ...offset, img: cImg });
          }
        }
      }
    }

    // Beard
    const beardPhase = Number(charLayers.beardPhase) || 0;
    if (beardPhase > 0) {
      const beardUrl = `assets/PrisonV3/Beard/BeardDay/${beardPhase}.png`;
      const beardImg = await getCanvasImage(beardUrl);
      if (beardImg) {
        layers.push({ ...FITTING_CONFIG.h, img: beardImg, resolution: FITTING_CONFIG.density.beard });
      }
    }

    // Front clothing: Zone 4 (jacket/shirt), Zone 8 (raven), Zone 2 (mask/glasses), Zone 1 (hat/cap/hood)
    for (const z of ["4", "8", "2", "1"]) {
      if (clothingZones[z]) {
        const cVal = clothingZones[z];
        const cUrl = typeof cVal === "object" ? cVal.imageUrl || cVal.url : String(cVal);
        if (cUrl) {
          const cImg = await getCanvasImage(cUrl);
          if (cImg) {
            const offset = FITTING_CONFIG.staticClothingOffsets[Number(z)] || { x: 0, y: 0, scale: 1 };
            layers.push({ ...offset, img: cImg, overEyes: (z === "1" || z === "2") });
          }
        }
      }
    }

    // Zone 6: Brush hand / item
    if (clothingZones["6"]) {
      const cVal = clothingZones["6"];
      const cUrl = typeof cVal === "object" ? cVal.imageUrl || cVal.url : String(cVal);
      if (cUrl) {
        const isBrushAnim = cUrl.includes("BrushAnim");
        if (isBrushAnim) {
          const match = cUrl.match(/BrushAnim\/(\d+)\//i);
          const brushId = match ? Number(match[1]) : 12;
          const rawFolder = extractRawAssetPath(cUrl).replace(/\/[^/]+\.(?:png|webp|json)$/i, "").replace(/\/+$/, "") + "/";
          const atlas = await loadAtlas(rawFolder, `Brush${brushId}`, "clothing");
          const offset = FITTING_CONFIG.brushOffsets[brushId] || FITTING_CONFIG.b;
          if (atlas) {
            layers.push({ ...offset, atlas });
          }
        } else {
          const kistImg = await getCanvasImage(cUrl);
          if (kistImg) {
            layers.push({ ...FITTING_CONFIG.b, img: kistImg });
          }
        }
      }
    }

    // Zone 3: Face mask / accessory
    if (clothingZones["3"]) {
      const cVal = clothingZones["3"];
      const cUrl = typeof cVal === "object" ? cVal.imageUrl || cVal.url : String(cVal);
      if (cUrl) {
        const cImg = await getCanvasImage(cUrl);
        if (cImg) {
          const offset = FITTING_CONFIG.staticClothingOffsets[3] || { x: 0, y: 0, scale: 1 };
          layers.push({ ...offset, img: cImg, overEyes: true });
        }
      }
    }

    // Zone 14 tattoo (drawn over hand)
    if (tattooZones["14"]) {
      const t14Url = typeof tattooZones["14"] === "object" ? tattooZones["14"].imageUrl : String(tattooZones["14"]);
      if (t14Url) {
        const t14Img = await getCanvasImage(t14Url);
        if (t14Img) {
          layers.push({ ...FITTING_CONFIG.f, img: t14Img, overEyes: true });
        }
      }
    }
  }

  if (currentToken && currentToken !== fittingRenderToken) return;

  fittingRoomActiveLayers = layers;
  fittingRoomLayersReady = true;

  // Render static layers (room + body + tattoos + static clothing) to offscreen composite buffer ONCE
  if (!fittingRoomStaticCanvas) {
    fittingRoomStaticCanvas = document.createElement("canvas");
    fittingRoomStaticCanvas.width = 1510;
    fittingRoomStaticCanvas.height = 1124;
    fittingRoomStaticCtx = fittingRoomStaticCanvas.getContext("2d");
  }
  if (!fittingRoomTopStaticCanvas) {
    fittingRoomTopStaticCanvas = document.createElement("canvas");
    fittingRoomTopStaticCanvas.width = 1510;
    fittingRoomTopStaticCanvas.height = 1124;
    fittingRoomTopStaticCtx = fittingRoomTopStaticCanvas.getContext("2d");
  }

  const staticLayers = [];
  const topStaticLayers = [];
  const animLayers = [];
  for (const l of layers) {
    if (l.atlas) {
      animLayers.push(l);
    } else if (l.overEyes) {
      topStaticLayers.push(l);
    } else {
      staticLayers.push(l);
    }
  }
  fittingRoomAnimLayers = animLayers;

  const drawStaticBucket = (targetCtx, bucket) => {
    targetCtx.save();
    try {
      targetCtx.setTransform(2, 0, 0, 2, 0, 0);
      targetCtx.clearRect(0, 0, FITTING_CONFIG.U.w, FITTING_CONFIG.U.h);
      targetCtx.translate(-FITTING_CONFIG.U.x, -FITTING_CONFIG.U.y);
      targetCtx.save();
      targetCtx.translate(FITTING_CONFIG.o.x, FITTING_CONFIG.o.y);
      targetCtx.scale(FITTING_CONFIG.o.scale, FITTING_CONFIG.o.scale);

      for (const layer of bucket) {
        if (layer.angle) {
          targetCtx.save();
          targetCtx.translate(layer.x, layer.y);
          targetCtx.rotate((layer.angle * Math.PI) / 180);
          drawLayer(targetCtx, { ...layer, x: 0, y: 0 }, 0);
          targetCtx.restore();
        } else {
          drawLayer(targetCtx, layer, 0);
        }
      }
      targetCtx.restore();
    } finally {
      targetCtx.restore();
    }
  };

  drawStaticBucket(fittingRoomStaticCtx, staticLayers);
  drawStaticBucket(fittingRoomTopStaticCtx, topStaticLayers);
}

function openFittingRoom(previewData = null) {
  fittingRoomPreview = previewData;
  const currentToken = ++fittingRenderToken;

  // 1. Immediately cancel running animation loop
  if (fittingRoomAnimFrameId) {
    cancelAnimationFrame(fittingRoomAnimFrameId);
    fittingRoomAnimFrameId = null;
  }

  // 2. Clear out active layers immediately so previous preview item never lingers
  fittingRoomActiveLayers = [];
  fittingRoomLayersReady = false;
  if (fittingRoomStaticCtx) {
    fittingRoomStaticCtx.save();
    fittingRoomStaticCtx.setTransform(1, 0, 0, 1, 0, 0);
    fittingRoomStaticCtx.clearRect(0, 0, fittingRoomStaticCanvas.width, fittingRoomStaticCanvas.height);
    fittingRoomStaticCtx.restore();
  }
  if (fittingRoomTopStaticCtx) {
    fittingRoomTopStaticCtx.save();
    fittingRoomTopStaticCtx.setTransform(1, 0, 0, 1, 0, 0);
    fittingRoomTopStaticCtx.clearRect(0, 0, fittingRoomTopStaticCanvas.width, fittingRoomTopStaticCanvas.height);
    fittingRoomTopStaticCtx.restore();
  }

  // Smart side selection:
  // If preview item/set contains ONLY back zones (zone >= 23 or side === "back"), open in "back" view!
  // If front or mixed (front + back), start in "front" view with rotate button to toggle!
  let hasFront = false;
  let hasBack = false;

  if (previewData) {
    if (previewData.type === "item") {
      const itm = previewData.item || {};
      const z = Number(itm.zone || 1);
      if (z >= 23 || itm.side === "back") {
        hasBack = true;
      } else {
        hasFront = true;
      }
    } else if (previewData.type === "set") {
      const parts = previewData.set?.parts || [];
      parts.forEach(p => {
        const z = Number(p.zone || 1);
        if (z >= 23 || p.side === "back") {
          hasBack = true;
        } else {
          hasFront = true;
        }
      });
    } else if (previewData.type === "loot") {
      const itm = previewData.item || {};
      if (itm.previewParts && Array.isArray(itm.previewParts) && itm.previewParts.length > 0) {
        itm.previewParts.forEach(p => {
          const z = Number(p.zone || 1);
          if (z >= 23 || p.side === "back") {
            hasBack = true;
          } else {
            hasFront = true;
          }
        });
      } else {
        const z = Number(itm.zone || 1);
        if (z >= 23 || itm.side === "back") {
          hasBack = true;
        } else {
          hasFront = true;
        }
      }
    }
  }

  if (!canRotateFittingPreview(previewData)) {
    fittingViewSide = "front";
  } else if (hasBack && !hasFront) {
    fittingViewSide = "back";
  } else {
    fittingViewSide = "front";
  }

  const overlay = document.getElementById("fitting-loading-overlay");
  if (overlay) overlay.style.display = "flex";

  const modal = document.getElementById("modal-fitting-room");
  const badgeEl = document.getElementById("fitting-item-badge");
  const descEl = document.getElementById("fitting-item-desc");
  const applyBtn = document.getElementById("btn-apply-fitting");

  if (previewData) {
    if (previewData.type === "item") {
      badgeEl.textContent = `Примерка: ${previewData.item.name}`;
      const bonusHtml = formatFittingBonusesHtml(previewData.item.bonuses);
      descEl.innerHTML = `Зона: ${previewData.item.zone} ${bonusHtml ? `| ${bonusHtml}` : `| ${previewData.item.description || 'Часть сета'}`}`;
      if (applyBtn) {
        if (previewData.item.owned) {
          applyBtn.style.display = "block";
          applyBtn.textContent = "Надеть в игре";
        } else if (previewData.item.price && Number(previewData.item.price) > 0) {
          applyBtn.style.display = "block";
          applyBtn.textContent = `Купить в игре (${previewData.item.price} ${previewData.item.currency || ''})`;
        } else {
          applyBtn.style.display = "none";
        }
      }
    } else if (previewData.type === "set") {
      badgeEl.textContent = `Примерка сета: ${previewData.set.setName}`;
      const bonusHtml = formatFittingBonusesHtml(previewData.set.maxBonus || previewData.set.bonuses);
      descEl.innerHTML = `Всего частей: ${previewData.set.totalParts} | Собрано: ${previewData.set.ownedParts}${bonusHtml ? ` | ${bonusHtml}` : ''}`;
      if (applyBtn) {
        applyBtn.style.display = "block";
        applyBtn.textContent = "Надеть сет в игре";
      }
    } else if (previewData.type === "camera") {
      badgeEl.textContent = `Примерка хаты: ${previewData.camera.name}`;
      const bonusHtml = formatFittingBonusesHtml(previewData.camera.bonuses);
      const statusTxt = previewData.camera.owned ? "В наличии" : `Цена: ${previewData.camera.price} ${previewData.camera.currency}`;
      descEl.innerHTML = `${statusTxt}${bonusHtml ? ` | ${bonusHtml}` : ''}`;
      if (applyBtn) {
        applyBtn.style.display = "block";
        applyBtn.textContent = previewData.camera.owned ? "Выбрать хату" : "Купить хату";
      }
    } else if (previewData.type === "loot") {
      const itm = previewData.item;
      badgeEl.textContent = `Примерка лута: ${itm.name}`;
      descEl.textContent = `${itm.bonusText || 'Дроп'} | Награда за босса ${previewData.boss?.name || ''}`;
      if (applyBtn) {
        applyBtn.style.display = "none";
      }
    }
  } else {
    if (badgeEl) badgeEl.textContent = "Мой персонаж";
    if (descEl) descEl.textContent = "Текущий образ арестанта";
    if (applyBtn) applyBtn.style.display = "none";
  }

  if (badgeEl) badgeEl.title = badgeEl.textContent;
  if (modal) modal.style.display = "flex";
  drawFittingRoomStage(currentToken);
}

function closeFittingRoom() {
  const modal = document.getElementById("modal-fitting-room");
  if (modal) modal.style.display = "none";
  if (fittingRoomAnimFrameId) {
    cancelAnimationFrame(fittingRoomAnimFrameId);
    fittingRoomAnimFrameId = null;
  }
  const staleSpineCanvas = document.getElementById("spine-room-canvas");
  if (staleSpineCanvas) staleSpineCanvas.remove();
  if (window.SpineRoomPlayer) {
    window.SpineRoomPlayer.stop();
  }
  fittingRoomPreview = null;
}

/**
 * Единый метод открытия модального окна Примерочной с предпросмотром вещи/сета/хаты.
 * Используется и в разделе "Тату и Шмот", и при клике на дроп в Уведомлениях.
 */
async function openItemPreviewModal(opts = {}) {
  const { type = "tattoo", itemId = null, setId = null, name = "", imageUrl = "", kind = "", zone = 1, set = null } = opts || {};
  if (!wardrobeData) {
    try {
      const ov = await apiFetch("/wardrobe/overview");
      if (ov && ov.success) {
        wardrobeData = ov;
        window.wardrobeData = ov;
      }
    } catch (e) {
      console.debug("Could not preload wardrobe overview for preview modal:", e);
    }
  }

  const normType = String(type || kind || "").toLowerCase();
  if (normType === "room" || normType === "camera") {
    const cams = wardrobeData?.cameras || [];
    const matchedCam = cams.find(c => (itemId != null && String(c.id) === String(itemId)) || (name && c.name === name));
    openFittingRoom({
      type: "camera",
      camera: matchedCam || { id: itemId || 1, name: name || "Камера", imageUrl: proxyAssetUrl(imageUrl), owned: false, price: 0, currency: "" },
    });
    return;
  }

  const subKind = normType.includes("cloth") ? "clothing" : "tattoos";
  const allSets = [
    ...(wardrobeData?.sets?.regular?.[subKind] || []),
    ...(wardrobeData?.sets?.blind_kolsik?.[subKind] || []),
    ...(wardrobeData?.sets?.regular?.tattoos || []),
    ...(wardrobeData?.sets?.regular?.clothing || []),
    ...(wardrobeData?.sets?.blind_kolsik?.tattoos || []),
    ...(wardrobeData?.sets?.blind_kolsik?.clothing || []),
  ];

  // Try matching by set object or setId / setName first
  if (set && Array.isArray(set.parts)) {
    openFittingRoom({ type: "set", set, kind: subKind });
    return;
  }
  if (setId || (!itemId && name)) {
    const normTarget = normalizeSetName(name || String(setId || ""));
    const matchedSet = allSets.find(s =>
      (setId != null && (String(s.id) === String(setId) || String(s.setName) === String(setId)))
      || (normTarget && normalizeSetName(s.setName) === normTarget)
    );
    if (matchedSet) {
      const resolvedKind = (wardrobeData?.sets?.regular?.clothing || []).includes(matchedSet) || (wardrobeData?.sets?.blind_kolsik?.clothing || []).includes(matchedSet)
        ? "clothing"
        : "tattoos";
      openFittingRoom({ type: "set", set: matchedSet, kind: resolvedKind });
      return;
    }
  }

  // Try matching individual part across sets
  let matchedPart = null;
  let matchedKind = subKind;
  for (const s of allSets) {
    const found = (s.parts || []).find(p =>
      (itemId != null && String(p.id) === String(itemId))
      || (name && String(p.name || "").toLowerCase() === String(name).toLowerCase())
    );
    if (found) {
      matchedPart = found;
      matchedKind = ((wardrobeData?.sets?.regular?.clothing || []).includes(s) || (wardrobeData?.sets?.blind_kolsik?.clothing || []).includes(s))
        ? "clothing"
        : "tattoos";
      break;
    }
  }

  if (matchedPart) {
    openFittingRoom({ type: "item", item: matchedPart, kind: matchedKind });
    return;
  }

  // Fallback direct loot/item preview using provided metadata
  openFittingRoom({
    type: "loot",
    item: {
      id: itemId,
      name: name || "Предмет",
      kind: normType.includes("cloth") ? (normType.includes("set") ? "clothing_set" : "clothing") : (normType.includes("set") ? "tattoo_set" : "tattoo"),
      zone: Number(zone) || 1,
      previewUrl: proxyAssetUrl(imageUrl),
      bonusText: "Дроп / награда",
    },
    boss: { name: "" },
  });
}
window.openItemPreviewModal = openItemPreviewModal;

async function drawFittingRoomStage(currentToken = null) {
  const stage = document.getElementById("fitting-stage");
  if (!stage) return;

  const myToken = currentToken || ++fittingRenderToken;

  // Clean up any legacy separate spine canvas so querySelector("#fitting-main-canvas") is unambiguous
  const staleSpine = stage.querySelector("#spine-room-canvas");
  if (staleSpine) staleSpine.remove();

  let canvas = stage.querySelector("#fitting-main-canvas");
  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.id = "fitting-main-canvas";
    canvas.width = 1510;
    canvas.height = 1124;
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.objectFit = "contain";
    canvas.style.display = "block";
    stage.prepend(canvas);
  }

  // Rotate character button (front <-> back toggle)
  let rotBtn = stage.querySelector("#btn-fitting-rotate");
  if (!rotBtn) {
    rotBtn = document.createElement("button");
    rotBtn.id = "btn-fitting-rotate";
    rotBtn.className = "btn-fitting-rotate";
    rotBtn.title = "Развернуть персонажа (перед / спина)";
    rotBtn.setAttribute("aria-label", "Развернуть персонажа");
    rotBtn.innerHTML = '<img src="/static/assets/icons/back_poworot.webp" alt="Развернуть" draggable="false" />';
    stage.appendChild(rotBtn);
  } else {
    const rotImg = rotBtn.querySelector("img");
    if (!rotImg || (rotImg.complete && rotImg.naturalWidth === 0)) {
      rotBtn.innerHTML = '<img src="/static/assets/icons/back_poworot.webp" alt="Развернуть" draggable="false" />';
    }
  }
  rotBtn.style.display = canRotateFittingPreview(fittingRoomPreview) ? "flex" : "none";
  rotBtn.onclick = (e) => {
    e.stopPropagation();
    fittingViewSide = (fittingViewSide === "front" ? "back" : "front");
    const overlay = document.getElementById("fitting-loading-overlay");
    if (overlay) overlay.style.display = "flex";
    const nextToken = ++fittingRenderToken;
    prepareFittingRoomLayers(nextToken).then(() => {
      if (nextToken !== fittingRenderToken) return;
      if (overlay) overlay.style.display = "none";
      startFittingRoomLoop();
    });
  };

  let overlay = stage.querySelector("#fitting-loading-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "fitting-loading-overlay";
    overlay.className = "fitting-loading-overlay";
    overlay.style.display = "flex";
    overlay.innerHTML = '<div class="spinner-sm"></div><span style="font-size: 11px; color: #fff; margin-top: 6px;">Загрузка спрайтов...</span>';
    stage.appendChild(overlay);
  }

  await prepareFittingRoomLayers(myToken);
  if (myToken !== fittingRenderToken) return;

  const curRoomId = fittingRoomRoomData
    ? (Number(extractRoomFolderId(fittingRoomRoomData.url || fittingRoomRoomData.img?.src, fittingRoomRoomData.id)) || fittingRoomRoomData.id)
    : null;
  if (curRoomId && window.SpineRoomPlayer && window.SpineRoomPlayer.isAnimatedRoom(curRoomId)) {
    await window.SpineRoomPlayer.preload(curRoomId);
    if (myToken !== fittingRenderToken) return;
  } else if (window.SpineRoomPlayer) {
    window.SpineRoomPlayer.stop();
  }

  if (overlay) overlay.style.display = "none";

  // Start rendering only after BOTH character layers and room foreground (Spine/bundle) are ready
  startFittingRoomLoop();

  // Background preheat for opposite side
  setTimeout(() => {
    try {
      const charL = wardrobeData?.characterLayers || window.characterLayers || {};
      if (fittingViewSide === "front") {
        const backUrls = [
          FITTING_CONFIG.playerSpriteBack,
          ...Object.entries(charL.tattooZones || {}).filter(([z]) => Number(z) >= 23).map(([, t]) => (typeof t === "object" ? t.imageUrl : t)),
          ...Object.values(charL.clothingBackZones || {}).map(c => (typeof c === "object" ? c.imageUrl : c)),
        ].filter(Boolean);
        if (backUrls.length > 0) batchLoadAssets(backUrls);
      } else {
        const frontUrls = [
          FITTING_CONFIG.playerSprite,
          ...Object.entries(charL.tattooZones || {}).filter(([z]) => Number(z) < 23).map(([, t]) => (typeof t === "object" ? t.imageUrl : t)),
          ...Object.values(charL.clothingZones || {}).map(c => (typeof c === "object" ? c.imageUrl : c)),
        ].filter(Boolean);
        if (frontUrls.length > 0) batchLoadAssets(frontUrls);
      }
    } catch (e) { }
  }, 100);
}

// Wardrobe Tab switching
document.querySelectorAll(".wardrobe-nav-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".wardrobe-nav-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    wardrobeTab = tab.getAttribute("data-wtab");
    renderWardrobe();
  });
});

// Wardrobe Subtabs switching
document.querySelectorAll(".wardrobe-subtab").forEach(subtab => {
  subtab.addEventListener("click", () => {
    document.querySelectorAll(".wardrobe-subtab").forEach(s => s.classList.remove("active"));
    subtab.classList.add("active");
    wardrobeSubtab = subtab.getAttribute("data-wsub");
    renderWardrobe();
  });
});

// Show Character Button
document.getElementById("btn-show-character")?.addEventListener("click", () => {
  openFittingRoom(null);
});

// Wardrobe Search Input
document.getElementById("wardrobe-search")?.addEventListener("input", (e) => {
  wardrobeSearchQuery = e.target.value.trim();
  renderWardrobeSets();
});

// Wardrobe Status Pills
document.querySelectorAll("#wardrobe-status-pills .filter-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll("#wardrobe-status-pills .filter-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    wardrobeFilterStatus = pill.getAttribute("data-wstatus");
    renderWardrobeSets();
  });
});

// Can Buy Toggle
document.getElementById("filter-can-buy")?.addEventListener("change", (e) => {
  wardrobeFilterCanBuy = e.target.checked;
  renderWardrobeSets();
});

// Bonus Filter Buttons
document.querySelectorAll(".bonus-filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".bonus-filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    wardrobeFilterBonus = btn.getAttribute("data-wbonus");
    renderWardrobeSets();
  });
});

// Source Filter Pills
document.querySelectorAll("#wardrobe-source-pills .filter-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll("#wardrobe-source-pills .filter-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    wardrobeFilterSource = pill.getAttribute("data-wsource");
    renderWardrobeSets();
  });
});

// Summary Details Toggle
document.getElementById("btn-toggle-summary-details")?.addEventListener("click", () => {
  const det = document.getElementById("wardrobe-summary-details");
  const btn = document.getElementById("btn-toggle-summary-details");
  if (!det) return;
  const isHidden = det.style.display === "none";
  det.style.display = isHidden ? "block" : "none";
  if (btn) btn.textContent = isHidden ? "Подробности ▲" : "Подробности ▼";
});

// Filters Collapsible Toggle
document.getElementById("btn-toggle-filters")?.addEventListener("click", () => {
  const cont = document.getElementById("wardrobe-filters-content");
  const btn = document.getElementById("btn-toggle-filters");
  if (!cont) return;
  const isHidden = cont.style.display === "none";
  cont.style.display = isHidden ? "block" : "none";
  if (btn) btn.textContent = isHidden ? "Развернуть" : "Свернуть";
});

// Fitting Room Controls
document.getElementById("btn-close-fitting")?.addEventListener("click", closeFittingRoom);
document.getElementById("modal-fitting-room")?.addEventListener("click", (e) => {
  if (e.target.id === "modal-fitting-room") closeFittingRoom();
});
document.getElementById("btn-reset-fitting")?.addEventListener("click", () => {
  openFittingRoom(null);
});
document.getElementById("btn-apply-fitting")?.addEventListener("click", async () => {
  if (!fittingRoomPreview) return;
  try {
    if (fittingRoomPreview.type === "item") {
      const itm = fittingRoomPreview.item;
      const kind = fittingRoomPreview.kind === "tattoos" ? "tattoo" : "clothing";
      if (itm.owned) {
        await apiFetch("/actions/wardrobe/equip", {
          method: "POST",
          body: JSON.stringify({ kind, action: "equip", id: itm.id, zone: itm.zone, imageUrl: itm.imageUrl }),
        });
        showToast("Предмет успешно надет!", "success");
      } else {
        await apiFetch("/actions/wardrobe/buy", {
          method: "POST",
          body: JSON.stringify({ kind, id: itm.id }),
        });
        showToast("Предмет успешно куплен!", "success");
      }
    } else if (fittingRoomPreview.type === "set") {
      const s = fittingRoomPreview.set;
      const kind = fittingRoomPreview.kind === "tattoos" ? "tattoo_set" : "clothing_set";
      const zonesMap = {};
      (s.parts || []).filter(p => p.owned).forEach(p => {
        zonesMap[String(p.zone)] = { id: p.id, imageUrl: p.imageUrl };
      });
      await apiFetch("/actions/wardrobe/equip", {
        method: "POST",
        body: JSON.stringify({ kind, zonesMap }),
      });
      showToast(`Сет «${s.setName}» надет!`, "success");
    } else if (fittingRoomPreview.type === "camera") {
      const cam = fittingRoomPreview.camera;
      if (cam.owned) {
        await apiFetch("/actions/wardrobe/equip", {
          method: "POST",
          body: JSON.stringify({ kind: "camera", id: cam.id }),
        });
        showToast(`Хата «${cam.name}» выбрана!`, "success");
      } else {
        await apiFetch("/actions/wardrobe/buy", {
          method: "POST",
          body: JSON.stringify({ kind: "camera", id: cam.id }),
        });
        showToast(`Хата «${cam.name}» куплена!`, "success");
      }
    }
    closeFittingRoom();
    loadWardrobe();
    loadProfile();
  } catch (e) {
    showToast(`Ошибка: ${e.message}`, "error");
  }
});

// Open Baul button
document.getElementById("btn-open-baul")?.addEventListener("click", async () => {
  try {
    const res = await apiFetch("/actions/bauls/buy", {
      method: "POST",
      body: JSON.stringify({ baulId: 1 }),
    });
    if (res.success) {
      showToast("Баул успешно открыт!", "success");
      loadBauls();
      loadProfile();
    }
  } catch (e) {
    showToast(`Ошибка открытия баула: ${e.message}`, "error");
  }
});

// Refresh buttons
document.getElementById("btn-refresh-talents")?.addEventListener("click", () => {
  loadTalents();
  showToast("Таланты обновляются...", "info");
});
document.getElementById("btn-refresh-collections")?.addEventListener("click", () => {
  loadCollections();
  showToast("Коллекции обновляются...", "info");
});
document.getElementById("btn-refresh-bauls")?.addEventListener("click", () => {
  loadBauls();
  showToast("Баулы обновляются...", "info");
});

// ============================================================================
// 6. LIVESTATEHUB SSE CLIENT & LOCAL TIMERS
// ============================================================================

const liveSyncClient = (() => {
  let evtSource = null;
  let deltaTimer = null;
  let reconnectTimer = null;
  let retryDelayMs = 2000;
  let started = false;
  const pendingUpdates = new Map();

  function applyLiveSlice(slice, data, version) {
    if (!slice || data === undefined) return;
    if (version && Number(liveSlices.versions[slice] || 0) >= Number(version)) {
      return;
    }
    if (version) {
      liveSlices.versions[slice] = Number(version);
    }
    liveSlices.data[slice] = data;

    if (slice === "profile") renderProfileData(data);
    else if (slice === "state") applyStateData(data);
    else if (slice === "config" && data) {
      botConfig = data;
      updateConfigUI(botConfig);
    } else if (slice === "boss") renderBossData(data);
    else if (slice === "presets" && data && Array.isArray(data.presets)) {
      bossPresets = data.presets;
      renderBossPresets();
    } else if (slice === "prisons") renderPrisonsData(data);
    else if (slice === "friends") renderFriendsSummaryData(data);
    else if (slice === "friend_requests") renderFriendRequestsData(data);
    else if (slice === "friends_stats") renderFriendsAuditData(data);
    else if (slice === "monthly") renderMonthlyStateData(data);
    else if (slice === "bauls") renderBaulsData(data);
    else if (slice === "radar" && typeof renderActivePlayersRadarFromData === "function") {
      renderActivePlayersRadarFromData(data);
    } else if (slice === "routine" && data) {
      if (data.monthly) renderMonthlyStateData(data.monthly);
      if (data.bauls) renderBaulsData(data.bauls);
    }
  }

  function flushPending() {
    if (pendingUpdates.size === 0) return;
    const entries = Array.from(pendingUpdates.entries());
    pendingUpdates.clear();
    requestAnimationFrame(() => {
      entries.forEach(([slice, payload]) => applyLiveSlice(slice, payload.data, payload.version));
    });
  }

  function handleIncomingSlice(slice, data, version) {
    if (document.hidden) {
      pendingUpdates.set(slice, { data, version });
      return;
    }
    applyLiveSlice(slice, data, version);
  }

  async function pollDeltaFallback() {
    if (document.hidden) return;
    try {
      const vParam = encodeURIComponent(JSON.stringify(liveSlices.versions || {}));
      const res = await apiFetch(`/live/delta?versions=${vParam}`);
      if (!res || !res.success) return;
      const changed = res.changed || {};
      const vers = res.versions || {};
      Object.entries(changed).forEach(([slice, data]) => {
        handleIncomingSlice(slice, data, vers[slice]);
      });
    } catch (e) {
      console.debug("Delta fallback error:", e);
    }
  }

  function startDeltaFallback() {
    if (deltaTimer) return;
    deltaTimer = setInterval(pollDeltaFallback, 10000);
  }

  function stopDeltaFallback() {
    if (deltaTimer) {
      clearInterval(deltaTimer);
      deltaTimer = null;
    }
  }

  function buildStreamUrl() {
    const adminToken = localStorage.getItem("prison_admin_token") || localStorage.getItem("admin_token") || "1488";
    const tgInitData = tg?.initData;
    const params = new URLSearchParams();
    if (adminToken) params.set("token", adminToken);
    else if (tgInitData) params.set("init_data", tgInitData);
    return `${API_BASE}/live/stream?${params.toString()}`;
  }

  function connect() {
    if (evtSource) {
      try { evtSource.close(); } catch (e) { }
      evtSource = null;
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    try {
      evtSource = new EventSource(buildStreamUrl());

      evtSource.addEventListener("snapshot", e => {
        retryDelayMs = 2000;
        stopDeltaFallback();
        try {
          const payload = JSON.parse(e.data);
          const vers = payload.versions || {};
          const slices = payload.slices || {};
          Object.entries(slices).forEach(([slice, data]) => {
            handleIncomingSlice(slice, data, vers[slice]);
          });
        } catch (err) {
          console.debug("SSE snapshot parse error:", err);
        }
      });

      evtSource.addEventListener("slice_update", e => {
        try {
          const payload = JSON.parse(e.data);
          handleIncomingSlice(payload.slice, payload.data, payload.version);
        } catch (err) {
          console.debug("SSE slice_update parse error:", err);
        }
      });

      evtSource.onerror = () => {
        try { evtSource.close(); } catch (e) { }
        evtSource = null;
        startDeltaFallback();
        if (!document.hidden && !reconnectTimer) {
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connect();
          }, retryDelayMs);
          retryDelayMs = Math.min(30000, Math.round(retryDelayMs * 1.7));
        }
      };
    } catch (err) {
      console.warn("EventSource init failed, falling back to delta polling:", err);
      startDeltaFallback();
    }
  }

  return {
    start() {
      if (started) return;
      started = true;
      connect();
    },
    onVisibilityChange() {
      if (!document.hidden) {
        flushPending();
        if (!evtSource || evtSource.readyState === 2) {
          retryDelayMs = 2000;
          connect();
        }
        pollDeltaFallback();
      }
    },
    applyLiveSlice,
  };
})();

// 1-second local countdown & energy interpolation tick (0 network calls)
setInterval(() => {
  if (document.hidden) return;
  updateMeleeTimers();
  updateBusinessCountdown();
  updateEnergyTimer();
  updateToiletPaperTimer();
}, 1000);

// 15-second sequential ping measurement (non-overlapping)
scheduleNextPing();

// Пауза / возобновление при сворачивании и возврате на вкладку браузера
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    measurePing();
    liveSyncClient.onVisibilityChange();
  }
});

// ============================================================================
// ACCORDIONS (Сворачивание длинных блоков: Таланты, Нычки, Усиления)
// ============================================================================
function initAccordions() {
  const cards = ["talents-card", "collections-card", "boss-buffs-card"];
  cards.forEach(cardId => {
    const card = document.getElementById(cardId);
    if (!card) return;
    const saved = localStorage.getItem("prison_accordion_" + cardId);
    // Collapsed by default: only expand if user explicitly chose "expanded" or "open"
    if (saved === "expanded" || saved === "open") {
      card.classList.remove("collapsed");
    } else {
      card.classList.add("collapsed");
    }
    const btn = card.querySelector(".accordion-toggle-btn");
    btn?.addEventListener("click", () => {
      card.classList.toggle("collapsed");
      const isNowCollapsed = card.classList.contains("collapsed");
      localStorage.setItem("prison_accordion_" + cardId, isNowCollapsed ? "collapsed" : "expanded");
    });
  });
}

// Init on load
window.addEventListener("DOMContentLoaded", async () => {
  // Preload token into input
  const storedToken = localStorage.getItem("prison_admin_token");
  if (storedToken && document.getElementById("input-admin-token")) {
    document.getElementById("input-admin-token").value = storedToken;
  }

  initAccordions();
  initBossPresetsUI();

  // Instant restoration of active section UI
  let savedSec = (window.location.hash || "").replace(/^#/, "").trim();
  if (savedSec === "home") savedSec = "main";
  if (!savedSec || !sectionTitles[savedSec]) {
    try {
      savedSec = localStorage.getItem("prison_active_section") || "main";
      if (savedSec === "home") savedSec = "main";
    } catch (e) {
      savedSec = "main";
    }
  }
  if (!sectionTitles[savedSec]) savedSec = "main";

  // Switch to restored section immediately so drawer and HUD title are updated at 0 ms
  switchSection(savedSec);

  // Start real-time LiveStateHub SSE sync
  liveSyncClient.start();

  // Quick health check
  measurePing();
  await refreshState();
  await loadProfile();

  // Prioritize loading active section data first
  if (savedSec === "wardrobe") {
    await loadWardrobe();
  } else if (savedSec === "bosses") {
    await Promise.all([loadBoss(), loadBossBuffs()]);
  } else if (savedSec === "prisons") {
    await loadPrisons();
  } else if (savedSec === "routine") {
    await Promise.all([loadRoutine(), loadBauls()]);
  } else if (savedSec === "friends") {
    await Promise.all([loadFriendsSummary(), loadFriendRequests(), loadFriendsAudit()]);
  } else if (savedSec === "raids") {
    await loadRaidsSection();
  }

  // Ленивая фоновая подгрузка общих справочников без перегрузки сети
  setTimeout(() => {
    loadCatalogs();
  }, 2000);
});


// ============================================================================
// BOSS MENU & QUEUE MANAGEMENT
// ============================================================================
let bossCatalog = [];
let bossPlayerStats = {};
let bossCatalogMap = new Map();
let bossTargetsWorkingCopy = [];
let currentBossCategoryFilter = "all";
let bossSearchQuery = "";

function updateBossQueueUI(targets) {
  const queue = Array.isArray(targets) ? targets.filter(t => t && t.enabled !== false) : [];
  const count = queue.length;

  const countBadge = document.getElementById("badge-boss-queue-count");
  if (countBadge) {
    countBadge.textContent = `выбрано: ${count}`;
  }

  const headerBadge = document.getElementById("boss-menu-header-badge");
  if (headerBadge) {
    headerBadge.textContent = `В очереди: ${count}`;
  }

  const summaryEl = document.getElementById("boss-active-queue-summary");
  if (summaryEl) {
    if (count === 0) {
      summaryEl.textContent = "Очередь автоатаки пуста. Нажмите «Меню боссов», чтобы настроить список целей.";
      summaryEl.style.color = "var(--muted-foreground)";
    } else {
      const modeLabels = { pacansky: "Пац", blotnoy: "Блат", avtoritetny: "Авторитет" };
      const items = queue.map(t => {
        const bName = t.name || (bossCatalogMap.get(String(t.bossId))) || `Босс #${t.bossId}`;
        const mLabel = modeLabels[t.mode] || t.mode || "Пац";
        return `${bName} [${mLabel}]`;
      });
      summaryEl.innerHTML = `<span style="color: #60a5fa; font-weight: 600;">В очереди (${count}):</span> <span style="color: #fff;">${items.join(" → ")}</span>`;
    }
  }
}

async function openBossMenu() {
  const modal = document.getElementById("modal-boss-menu");
  if (!modal) return;
  modal.style.display = "flex";

  const currentTargets = (botConfig && botConfig.boss_targets) || [];
  bossTargetsWorkingCopy = JSON.parse(JSON.stringify(currentTargets));

  try {
    const data = await apiFetch("/bosses/catalog");
    if (data.success) {
      bossCatalog = data.bosses || [];
      bossPlayerStats = data.playerStats || {};
      bossCatalogMap = new Map(bossCatalog.map(b => [String(b.id), b.name]));
      updateBossQueueUI(bossTargetsWorkingCopy);
    }
  } catch (err) {
    console.warn("Error fetching boss catalog:", err);
  }

  renderBossMenuList();
}

function closeBossMenu() {
  const modal = document.getElementById("modal-boss-menu");
  if (modal) modal.style.display = "none";
}

function renderBossDropHtml(b, mode) {
  const modeData = (b.modes && b.modes[mode]) || {};
  const currencies = modeData.currencies || [];
  const items = modeData.items || [];

  if (currencies.length === 0 && items.length === 0) {
    return '<div style="font-size: 10px; color: var(--muted-foreground);">Нет данных о дропе для этого режима</div>';
  }

  const curIcons = {
    authority: "/static/assets/icons/authority.webp",
    cigarettes: "/static/assets/icons/cigarettes.webp",
    sugar: "/static/assets/icons/sugar.webp",
    keys: "/static/assets/icons/keys.webp",
    rubles: "/static/assets/icons/rubles.webp",
    toiletPaper: "/static/assets/icons/paper.webp",
    paper: "/static/assets/icons/paper.webp?v=2",
    soap: "/static/assets/icons/soap.webp",
  };

  let currenciesHtml = "";
  if (currencies.length > 0) {
    currenciesHtml = `
      <div class="boss-drop-currencies">
        ${currencies.map(c => {
      const icon = curIcons[c.currency] || "/static/assets/icons/rubles.webp";
      return `
            <span class="loot-currency" title="${c.label || c.currency}">
              <img src="${icon}" alt="${c.label || c.currency}" onerror="this.style.display='none'">
              +${formatNum(c.amount)}
            </span>
          `;
    }).join("")}
      </div>
    `;
  }

  let itemsHtml = "";
  if (items.length > 0) {
    itemsHtml = `
      <div class="boss-drop-items">
        ${items.map((it, idx) => {
      const fallbackIcon = it.kind === "stash" ? "/static/assets/icons/stash.webp" : (it.kind === "camera" ? "/static/assets/icons/punchChest.webp" : "/static/assets/icons/kolsik.webp");
      const thumb = it.previewUrl ? proxyAssetUrl(it.previewUrl) : fallbackIcon;
      const isOwned = Boolean(it.owned);
      const hasCount = it.totalCount && it.totalCount > 1;
      const countBadge = hasCount ? `<span class="boss-loot-parts-badge">${it.ownedCount || 0}/${it.totalCount}</span>` : "";
      const checkBadge = isOwned ? '<span class="boss-loot-owned-badge">✓</span>' : '';
      return `
            <div class="boss-loot-item-chip ${isOwned ? 'owned' : ''}" data-boss-id="${b.id}" data-item-idx="${idx}" title="Кликните для примерки в Примерочной">
              <img src="${thumb}" class="boss-loot-item-thumb" onerror="this.src='${fallbackIcon}'">
              <div class="boss-loot-item-info">
                <span class="boss-loot-item-name">${it.name}</span>
                <span class="boss-loot-item-bonus">${it.bonusText || ''}</span>
              </div>
              ${checkBadge}
              ${countBadge}
            </div>
          `;
    }).join("")}
      </div>
    `;
  }

  return `${currenciesHtml}${itemsHtml}`;
}

function bindLootClickHandlers(cardEl, bossObj, modeKey) {
  const modeInfo = (bossObj.modes && bossObj.modes[modeKey]) || {};
  const items = modeInfo.items || [];
  cardEl.querySelectorAll(".boss-loot-item-chip").forEach(chip => {
    let prefetchTimer = null;
    chip.addEventListener("pointerenter", () => {
      prefetchTimer = setTimeout(() => {
        const idx = Number(chip.getAttribute("data-item-idx"));
        const itm = items[idx];
        if (itm) {
          const urls = [
            itm.previewUrl,
            itm.imageUrl,
            ...(itm.previewParts || []).map(p => p.imageUrl),
          ].filter(Boolean);
          if (urls.length > 0) batchLoadAssets(urls);
        }
      }, 120);
    });
    chip.addEventListener("pointerleave", () => {
      if (prefetchTimer) clearTimeout(prefetchTimer);
    });

    chip.addEventListener("click", () => {
      const idx = Number(chip.getAttribute("data-item-idx"));
      const itm = items[idx];
      if (itm) {
        openFittingRoom({ type: "loot", item: itm, boss: bossObj });
      }
    });
  });
}

function renderBossMenuList() {
  const container = document.getElementById("boss-menu-list");
  if (!container) return;

  const headerBadge = document.getElementById("boss-menu-header-badge");
  const enabledCount = bossTargetsWorkingCopy.filter(t => t.enabled !== false).length;
  if (headerBadge) {
    headerBadge.textContent = `В очереди: ${enabledCount}`;
  }

  let filtered = bossCatalog.slice();
  if (currentBossCategoryFilter !== "all") {
    filtered = filtered.filter(b => String(b.categoryId) === String(currentBossCategoryFilter));
  }
  if (bossSearchQuery.trim()) {
    const q = bossSearchQuery.trim().toLowerCase();
    filtered = filtered.filter(b => (b.name || "").toLowerCase().includes(q));
  }

  // Strict sorting by sortOrder (0..57)
  filtered.sort((a, b) => (a.sortOrder !== undefined ? a.sortOrder : 999) - (b.sortOrder !== undefined ? b.sortOrder : 999));

  if (filtered.length === 0) {
    container.innerHTML = '<div style="color: var(--muted-foreground); text-align: center; padding: 24px; font-size: 12px;">Боссы не найдены</div>';
    return;
  }

  container.innerHTML = "";

  filtered.forEach(b => {
    const bIdStr = String(b.id);
    const targetIdx = bossTargetsWorkingCopy.findIndex(t => String(t.bossId) === bIdStr);
    const target = targetIdx !== -1 ? bossTargetsWorkingCopy[targetIdx] : null;
    const isEnabled = Boolean(target && target.enabled !== false);

    const hasPacansky = Boolean(b.modes && b.modes.pacansky);
    const hasBlotnoy = Boolean(b.modes && b.modes.blotnoy);
    const hasAvtoritetny = Boolean(b.modes && b.modes.avtoritetny);

    let currentMode = (target && target.mode) || "pacansky";
    if (currentMode === "blotnoy" && !hasBlotnoy) currentMode = "pacansky";
    if (currentMode === "avtoritetny" && !hasAvtoritetny) currentMode = "pacansky";

    const winLimit = (target && target.limit !== undefined) ? target.limit : 7;

    const dailyWinsMap = bossPlayerStats.dailyWins || {};
    const keysMap = bossPlayerStats.keys || {};
    const dailyWins = dailyWinsMap[bIdStr] || b.dailyWins || 0;
    const totalWins = b.totalWins || 0;
    const reqKeyBossId = b.requiredKeyBossId !== undefined ? b.requiredKeyBossId : null;
    const keyReq = b.requiredKeysCount !== undefined ? b.requiredKeysCount : (b.keyRequirement || 0);
    const keyBoss = b.requiredKeyBossName || b.keyBoss || "";
    const heldKeys = (reqKeyBossId !== null && reqKeyBossId !== undefined)
      ? (keysMap[String(reqKeyBossId)] !== undefined ? keysMap[String(reqKeyBossId)] : (b.availableKeys !== undefined && b.availableKeys !== null ? b.availableKeys : 0))
      : (b.availableKeys !== undefined && b.availableKeys !== null ? b.availableKeys : 0);

    const modeData = (b.modes && b.modes[currentMode]) || (b.modes && b.modes.pacansky) || {};
    const currentHp = modeData.hp || b.baseHp || b.hp || 500;

    const isLocked = Boolean(b.isLocked);
    const item = document.createElement("div");
    item.className = `boss-menu-item ${isEnabled ? 'in-queue' : ''} ${isLocked ? 'boss-locked' : ''}`;
    item.dataset.bossId = b.id;

    item.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
          <input type="checkbox" class="boss-queue-toggle" data-boss-id="${b.id}" ${isEnabled ? 'checked' : ''} ${isLocked ? 'disabled' : ''} style="width: 16px; height: 16px; cursor: pointer; accent-color: var(--primary);">
          <img src="${b.avatarUrl || '/static/assets/icons/boss.webp'}" class="game-icon-sm" alt="${b.name}" onerror="this.src='/static/assets/icons/boss.webp'">
          <div style="min-width: 0;">
            <div style="font-weight: 700; font-size: 13px; color: #fff; display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
              <span>${b.name}</span>
              <span style="font-size: 10px; padding: 1px 6px; border-radius: 4px; background: rgba(255,255,255,0.08); color: var(--muted-foreground);">${b.categoryName || 'Категория ' + b.categoryId}</span>
              ${isLocked ? `<span class="boss-locked-badge">🔒 Закрыт</span>` : ''}
              ${isLocked && b.progressText ? `<span class="boss-progress-pill">${b.progressText}</span>` : ''}
            </div>
            ${isLocked && b.unlockReason ? `<div class="boss-locked-reason"><span>⚠️</span> <span>${b.unlockReason}</span></div>` : ''}
            <div style="font-size: 11px; color: var(--muted-foreground); margin-top: 2px;">
              <span>HP: <b class="boss-hp-val" style="color: #f87171;">${formatNum(currentHp)}</b></span>
              <span style="margin: 0 4px;">•</span>
              <span>Ключи: <b style="color: ${heldKeys >= keyReq || keyReq === 0 ? '#34d399' : '#fbbf24'};">${keyReq > 0 ? (heldKeys + '/' + keyReq + (keyBoss ? ' (от ' + keyBoss + ')' : '')) : 'Без ключей'}</b></span>
            </div>
          </div>
        </div>
        <div style="display: flex; gap: 4px; align-items: center;">
          <button class="btn btn-secondary btn-sm boss-priority-btn btn-boss-up" data-boss-id="${b.id}" title="Повысить приоритет" ${!isEnabled || isLocked ? 'disabled' : ''}>▲</button>
          <button class="btn btn-secondary btn-sm boss-priority-btn btn-boss-down" data-boss-id="${b.id}" title="Понизить приоритет" ${!isEnabled || isLocked ? 'disabled' : ''}>▼</button>
        </div>
      </div>

      <!-- Mode selection pills -->
      <div style="display: flex; gap: 4px; margin-top: 6px;">
        <button class="boss-mode-pill ${currentMode === 'pacansky' ? 'active' : ''} ${!hasPacansky ? 'disabled' : ''}" data-boss-id="${b.id}" data-mode="pacansky" ${!hasPacansky ? 'disabled' : ''}>Пацанский</button>
        <button class="boss-mode-pill ${currentMode === 'blotnoy' ? 'active' : ''} ${!hasBlotnoy ? 'disabled' : ''}" data-boss-id="${b.id}" data-mode="blotnoy" ${!hasBlotnoy ? 'disabled' : ''}>Блатной</button>
        <button class="boss-mode-pill ${currentMode === 'avtoritetny' ? 'active' : ''} ${!hasAvtoritetny ? 'disabled' : ''}" data-boss-id="${b.id}" data-mode="avtoritetny" ${!hasAvtoritetny ? 'disabled' : ''}>Авторитетный</button>
      </div>

      <!-- Drop Block -->
      <div class="boss-drop-block" data-boss-id="${b.id}">
        ${renderBossDropHtml(b, currentMode)}
      </div>

      <!-- Bottom row: Win counters & limit input -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.05); gap: 8px; flex-wrap: wrap;">
        <div style="display: flex; gap: 6px; align-items: center;">
          <span class="badge" style="background: rgba(96, 165, 250, 0.15); color: #60a5fa; font-size: 11px; padding: 2px 6px;" title="Всего побед над боссом">Всего: <b>${totalWins}</b></span>
          <span class="badge" style="background: rgba(52, 211, 153, 0.15); color: #34d399; font-size: 11px; padding: 2px 6px;" title="Побед за сегодня / суточный лимит">За день: <b>${dailyWins}/${b.dailyLimit || 7}</b></span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--muted-foreground); margin-left: auto;">
          <span>Лимит:</span>
          <input type="number" min="1" max="50" class="boss-limit-input btn btn-secondary btn-sm" data-boss-id="${b.id}" value="${winLimit}" style="width: 50px; text-align: center; padding: 2px 4px; font-size: 11px;">
        </div>
      </div>
    `;

    bindLootClickHandlers(item, b, currentMode);

    const chk = item.querySelector(".boss-queue-toggle");
    chk.addEventListener("change", () => {
      const checked = chk.checked;
      const idx = bossTargetsWorkingCopy.findIndex(t => String(t.bossId) === bIdStr);
      if (checked) {
        if (idx !== -1) {
          bossTargetsWorkingCopy[idx].enabled = true;
        } else {
          bossTargetsWorkingCopy.push({
            bossId: b.id,
            name: b.name,
            mode: currentMode,
            limit: winLimit,
            enabled: true,
          });
        }
        item.classList.add("in-queue");
        item.querySelectorAll(".boss-priority-btn").forEach(btn => btn.disabled = false);
      } else {
        if (idx !== -1) {
          bossTargetsWorkingCopy.splice(idx, 1);
        }
        item.classList.remove("in-queue");
        item.querySelectorAll(".boss-priority-btn").forEach(btn => btn.disabled = true);
      }
      const count = bossTargetsWorkingCopy.filter(t => t.enabled !== false).length;
      if (headerBadge) headerBadge.textContent = `В очереди: ${count}`;
    });

    item.querySelectorAll(".boss-mode-pill").forEach(pBtn => {
      pBtn.addEventListener("click", () => {
        if (pBtn.classList.contains("disabled")) return;
        const newMode = pBtn.getAttribute("data-mode");
        item.querySelectorAll(".boss-mode-pill").forEach(m => m.classList.remove("active"));
        pBtn.classList.add("active");

        const newModeHp = (b.modes && b.modes[newMode] && b.modes[newMode].hp) || b.hp || 500;
        const hpEl = item.querySelector(".boss-hp-val");
        if (hpEl) hpEl.textContent = formatNum(newModeHp);

        const dropEl = item.querySelector(".boss-drop-block");
        if (dropEl) {
          dropEl.innerHTML = renderBossDropHtml(b, newMode);
          bindLootClickHandlers(item, b, newMode);
        }

        const idx = bossTargetsWorkingCopy.findIndex(t => String(t.bossId) === bIdStr);
        if (idx !== -1) {
          bossTargetsWorkingCopy[idx].mode = newMode;
        } else if (chk.checked) {
          bossTargetsWorkingCopy.push({
            bossId: b.id,
            name: b.name,
            mode: newMode,
            limit: winLimit,
            enabled: true,
          });
        }
      });
    });

    const limitInput = item.querySelector(".boss-limit-input");
    if (limitInput) {
      limitInput.addEventListener("change", () => {
        const val = Math.max(1, parseInt(limitInput.value) || 7);
        limitInput.value = val;
        const idx = bossTargetsWorkingCopy.findIndex(t => String(t.bossId) === bIdStr);
        if (idx !== -1) {
          bossTargetsWorkingCopy[idx].limit = val;
        }
      });
    }

    const btnUp = item.querySelector(".btn-boss-up");
    const btnDown = item.querySelector(".btn-boss-down");
    if (btnUp) {
      btnUp.addEventListener("click", () => {
        const idx = bossTargetsWorkingCopy.findIndex(t => String(t.bossId) === bIdStr);
        if (idx > 0) {
          const temp = bossTargetsWorkingCopy[idx];
          bossTargetsWorkingCopy[idx] = bossTargetsWorkingCopy[idx - 1];
          bossTargetsWorkingCopy[idx - 1] = temp;
          renderBossMenuList();
        }
      });
    }
    if (btnDown) {
      btnDown.addEventListener("click", () => {
        const idx = bossTargetsWorkingCopy.findIndex(t => String(t.bossId) === bIdStr);
        if (idx !== -1 && idx < bossTargetsWorkingCopy.length - 1) {
          const temp = bossTargetsWorkingCopy[idx];
          bossTargetsWorkingCopy[idx] = bossTargetsWorkingCopy[idx + 1];
          bossTargetsWorkingCopy[idx + 1] = temp;
          renderBossMenuList();
        }
      });
    }

    container.appendChild(item);
  });
}

// Modal open/close and buttons setup
document.getElementById("btn-open-boss-menu")?.addEventListener("click", openBossMenu);
document.getElementById("btn-close-boss-menu")?.addEventListener("click", closeBossMenu);
document.getElementById("modal-boss-menu")?.addEventListener("click", (e) => {
  if (e.target.id === "modal-boss-menu") closeBossMenu();
});

document.getElementById("btn-clear-boss-queue")?.addEventListener("click", () => {
  bossTargetsWorkingCopy = [];
  renderBossMenuList();
});

document.getElementById("btn-save-boss-queue")?.addEventListener("click", async () => {
  try {
    await apiFetch("/config", {
      method: "PATCH",
      body: JSON.stringify({ boss_targets: bossTargetsWorkingCopy }),
    });
    if (botConfig) botConfig.boss_targets = bossTargetsWorkingCopy;
    updateBossQueueUI(bossTargetsWorkingCopy);
    closeBossMenu();
    showToast("Очередь боссов сохранена", "success");
    refreshState();
  } catch (err) {
    showToast(`Ошибка сохранения очереди: ${err.message}`, "error");
  }
});

document.querySelectorAll("#boss-category-tabs .filter-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll("#boss-category-tabs .filter-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    currentBossCategoryFilter = pill.getAttribute("data-bcat") || "all";
    renderBossMenuList();
  });
});

document.getElementById("boss-menu-search")?.addEventListener("input", (e) => {
  bossSearchQuery = e.target.value || "";
  renderBossMenuList();
});

// ============================================================================
// SINGLE BOSS ATTACK (Атака босса: одиночный бой + режим «В одного»)
// ============================================================================
let selectedSingleBossId = null;
let selectedSingleBossMode = "pacansky";
let singleBossSearchQuery = "";
let singleBossCategoryFilter = "all";

async function openSingleBossAttackModal() {
  const modal = document.getElementById("modal-single-boss-attack");
  if (!modal) return;
  modal.style.display = "flex";

  try {
    const data = await apiFetch("/bosses/catalog");
    if (data.success) {
      bossCatalog = data.bosses || [];
      bossPlayerStats = data.playerStats || {};
      bossCatalogMap = new Map(bossCatalog.map(b => [String(b.id), b.name]));
    }
  } catch (err) {
    console.warn("Error fetching boss catalog:", err);
  }

  // Pre-select first available boss if none selected
  if (!selectedSingleBossId && bossCatalog.length > 0) {
    const firstOpen = bossCatalog.find(b => !b.isLocked) || bossCatalog[0];
    selectedSingleBossId = firstOpen.id;
    selectedSingleBossMode = "pacansky";
  }

  renderSingleBossAttackList();
}

function closeSingleBossAttackModal() {
  const modal = document.getElementById("modal-single-boss-attack");
  if (modal) modal.style.display = "none";
}

function renderSingleBossAttackList() {
  const container = document.getElementById("single-boss-list");
  if (!container) return;

  const badgeEl = document.getElementById("single-boss-selected-badge");
  const execBtn = document.getElementById("btn-execute-single-boss-attack");

  let filtered = bossCatalog.slice();
  if (singleBossCategoryFilter !== "all") {
    filtered = filtered.filter(b => String(b.categoryId) === String(singleBossCategoryFilter));
  }
  if (singleBossSearchQuery.trim()) {
    const q = singleBossSearchQuery.trim().toLowerCase();
    filtered = filtered.filter(b => (b.name || "").toLowerCase().includes(q));
  }

  filtered.sort((a, b) => (a.sortOrder !== undefined ? a.sortOrder : 999) - (b.sortOrder !== undefined ? b.sortOrder : 999));

  if (filtered.length === 0) {
    container.innerHTML = '<div style="color: var(--muted-foreground); text-align: center; padding: 24px; font-size: 12px;">Боссы не найдены</div>';
    if (execBtn) execBtn.disabled = true;
    return;
  }

  container.innerHTML = "";

  const selectedBoss = bossCatalog.find(b => String(b.id) === String(selectedSingleBossId));
  if (badgeEl) {
    if (selectedBoss) {
      badgeEl.textContent = `Выбран: ${selectedBoss.name}`;
      badgeEl.style.background = selectedBoss.isLocked ? "rgba(239, 68, 68, 0.3)" : "var(--primary)";
      badgeEl.style.color = selectedBoss.isLocked ? "#f87171" : "#000";
    } else {
      badgeEl.textContent = "Выберите босса";
      badgeEl.style.background = "var(--secondary)";
      badgeEl.style.color = "#fff";
    }
  }

  if (execBtn) {
    execBtn.disabled = !selectedBoss || Boolean(selectedBoss.isLocked);
  }

  filtered.forEach(b => {
    const bIdStr = String(b.id);
    const isSelected = String(selectedSingleBossId) === bIdStr;
    const isLocked = Boolean(b.isLocked);

    const hasPacansky = Boolean(b.modes && b.modes.pacansky);
    const hasBlotnoy = Boolean(b.modes && b.modes.blotnoy);
    const hasAvtoritetny = Boolean(b.modes && b.modes.avtoritetny);
    const hasOdin = Boolean(b.modes && b.modes.odin);

    let currentMode = isSelected ? selectedSingleBossMode : "pacansky";
    if (currentMode === "blotnoy" && !hasBlotnoy) currentMode = "pacansky";
    if (currentMode === "avtoritetny" && !hasAvtoritetny) currentMode = "pacansky";
    if (currentMode === "odin" && !hasOdin) currentMode = "pacansky";

    const modeData = (b.modes && b.modes[currentMode]) || (b.modes && b.modes.pacansky) || {};
    const currentHp = modeData.hp || b.baseHp || b.hp || 500;

    const dailyWinsMap = bossPlayerStats.dailyWins || {};
    const keysMap = bossPlayerStats.keys || {};
    const dailyWins = dailyWinsMap[bIdStr] || b.dailyWins || 0;
    const totalWins = b.totalWins || 0;
    const reqKeyBossId = b.requiredKeyBossId;
    const keyReq = b.requiredKeysCount || 0;
    const keyBoss = b.requiredKeyBossName || "";
    const heldKeys = (reqKeyBossId !== null && reqKeyBossId !== undefined) ? (keysMap[String(reqKeyBossId)] || 0) : 0;

    const item = document.createElement("div");
    item.className = `boss-menu-item ${isSelected ? 'in-queue' : ''} ${isLocked ? 'boss-locked' : ''}`;
    item.dataset.bossId = b.id;

    const dropHtml = renderBossDropHtml(b, currentMode);

    item.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
          <input type="radio" name="single_boss_select" class="single-boss-radio" data-boss-id="${b.id}" ${isSelected ? 'checked' : ''} ${isLocked ? 'disabled' : ''} style="width: 18px; height: 18px; cursor: pointer; accent-color: var(--primary);">
          <img src="${b.avatarUrl || '/static/assets/icons/boss.webp'}" class="game-icon-sm" alt="${b.name}" onerror="this.src='/static/assets/icons/boss.webp'">
          <div style="min-width: 0;">
            <div style="font-weight: 700; font-size: 13px; color: #fff; display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
              <span>${b.name}</span>
              <span style="font-size: 10px; padding: 1px 6px; border-radius: 4px; background: rgba(255,255,255,0.08); color: var(--muted-foreground);">${b.categoryName || 'Категория ' + b.categoryId}</span>
              ${isLocked ? `<span class="boss-locked-badge">🔒 Закрыт</span>` : ''}
              ${isLocked && b.progressText ? `<span class="boss-progress-pill">${b.progressText}</span>` : ''}
            </div>
            <div style="font-size: 11px; color: var(--muted-foreground); margin-top: 2px;">
              <span>Побед: <b style="color: #60a5fa;">${dailyWins}/${b.dailyLimit || 7}</b> сег.</span>
              <span style="margin: 0 4px;">•</span>
              <span>Всего: <b style="color: #34d399;">${totalWins}</b></span>
            </div>
          </div>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 13px; font-weight: 700; color: #f87171;" class="boss-hp-display">❤️ ${formatNum(currentHp)}</div>
          <div style="font-size: 10px; color: var(--muted-foreground);" class="boss-keys-info">
            ${keyReq > 0 ? `Ключи: <b style="color: ${heldKeys >= keyReq ? '#34d399' : '#f87171'};">${heldKeys}/${keyReq}</b>` : '<span style="color: #34d399;">Без ключей</span>'}
          </div>
        </div>
      </div>

      ${isLocked && b.unlockReason ? `
        <div class="boss-locked-reason">
          <span>⚠️</span> <span>${b.unlockReason}</span>
        </div>
      ` : ''}

      <!-- Mode Selector (включая В одного) -->
      <div style="display: flex; gap: 4px; margin-top: 8px; flex-wrap: wrap;" class="single-mode-selector">
        <button class="boss-mode-pill ${currentMode === 'pacansky' ? 'active' : ''} ${!hasPacansky || isLocked ? 'disabled' : ''}" data-boss-id="${b.id}" data-mode="pacansky" ${!hasPacansky || isLocked ? 'disabled' : ''}>Пацанский</button>
        <button class="boss-mode-pill ${currentMode === 'blotnoy' ? 'active' : ''} ${!hasBlotnoy || isLocked ? 'disabled' : ''}" data-boss-id="${b.id}" data-mode="blotnoy" ${!hasBlotnoy || isLocked ? 'disabled' : ''}>Блатной</button>
        <button class="boss-mode-pill ${currentMode === 'avtoritetny' ? 'active' : ''} ${!hasAvtoritetny || isLocked ? 'disabled' : ''}" data-boss-id="${b.id}" data-mode="avtoritetny" ${!hasAvtoritetny || isLocked ? 'disabled' : ''}>Авторитетный</button>
        <button class="boss-mode-pill ${currentMode === 'odin' ? 'active' : ''} ${!hasOdin || isLocked ? 'disabled' : ''}" data-boss-id="${b.id}" data-mode="odin" ${!hasOdin || isLocked ? 'disabled' : ''} style="display: inline-flex; align-items: center; gap: 4px;">
          <img src="/static/assets/icons/icon_Solo.png" style="width: 14px; height: 14px; object-fit: contain;">
          <span>В одного</span>
        </button>
      </div>

      <!-- Loot Drop Section -->
      <div class="boss-drop-section" style="margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 6px;">
        ${dropHtml}
      </div>
    `;

    // Radio change
    item.querySelector(".single-boss-radio")?.addEventListener("change", (e) => {
      if (e.target.checked && !isLocked) {
        selectedSingleBossId = b.id;
        selectedSingleBossMode = currentMode;
        renderSingleBossAttackList();
      }
    });

    item.addEventListener("click", (e) => {
      if (e.target.closest("button") || e.target.closest(".boss-loot-item-chip") || e.target.closest("input")) return;
      if (!isLocked) {
        selectedSingleBossId = b.id;
        selectedSingleBossMode = currentMode;
        renderSingleBossAttackList();
      }
    });

    // Mode buttons
    item.querySelectorAll(".single-mode-selector .boss-mode-pill").forEach(mBtn => {
      mBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (isLocked) return;
        const m = mBtn.dataset.mode;
        selectedSingleBossId = b.id;
        selectedSingleBossMode = m;
        renderSingleBossAttackList();
      });
    });

    bindLootClickHandlers(item, b, currentMode);
    container.appendChild(item);
  });
}

// Single Boss Attack Modal Event Listeners
document.getElementById("btn-open-single-boss-attack")?.addEventListener("click", openSingleBossAttackModal);
document.getElementById("btn-close-single-boss-attack")?.addEventListener("click", closeSingleBossAttackModal);
document.getElementById("btn-cancel-single-boss-attack")?.addEventListener("click", closeSingleBossAttackModal);
document.getElementById("modal-single-boss-attack")?.addEventListener("click", (e) => {
  if (e.target.id === "modal-single-boss-attack") closeSingleBossAttackModal();
});

document.getElementById("btn-execute-single-boss-attack")?.addEventListener("click", async () => {
  if (!selectedSingleBossId) return;
  try {
    const res = await apiFetch("/actions/boss/start", {
      method: "POST",
      body: JSON.stringify({ bossId: selectedSingleBossId, mode: selectedSingleBossMode }),
    });
    if (res.success) {
      showToast("Бой с боссом успешно запущен!", "success");
      closeSingleBossAttackModal();
      loadBoss();
      refreshState();
    }
  } catch (err) {
    showToast(`Ошибка запуска боя: ${err.message}`, "error");
  }
});

document.querySelectorAll("#single-boss-category-tabs .filter-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll("#single-boss-category-tabs .filter-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    singleBossCategoryFilter = pill.getAttribute("data-sbcat") || "all";
    renderSingleBossAttackList();
  });
});

document.getElementById("single-boss-search")?.addEventListener("input", (e) => {
  singleBossSearchQuery = e.target.value || "";
  renderSingleBossAttackList();
});


// ============================================================================
// SECTION: ПРЕСЕТЫ БОССОВ С РАСПИСАНИЕМ МСК (UTC+3)
// ============================================================================
let bossPresets = [];
let editingPresetId = null;
let presetWorkingSteps = [];

async function loadBossPresets() {
  try {
    const res = await apiFetch("/boss/presets");
    if (!res.success) return;
    bossPresets = Array.isArray(res.presets) ? res.presets : [];
    renderBossPresets();
  } catch (err) {
    console.warn("loadBossPresets error:", err);
  }
}

function renderBossPresets() {
  const container = document.getElementById("boss-presets-list");
  if (!container) return;

  const modeLabels = {
    pacansky: "Пацанский",
    blotnoy: "Блатной",
    avtoritetny: "Авторитетный",
    vorovskoy: "Воровской",
    odin: "В одного",
    brigade: "Бригадный"
  };

  const buildInnerHtml = preset => {
    const items = Array.isArray(preset.items) ? preset.items : [];
    const isRunning = Boolean(preset.is_running);
    const curIdx = Number(preset.current_step_index || 0);
    const totalSteps = Number(preset.totalSteps || preset.total_steps) || items.reduce((acc, s) => acc + Math.max(1, Number(s.count) || 1), 0) || items.length;
    let runningOffset = 0;
    const stepsChipsHtml = items.map((step, idx) => {
      const bId = step.bossId !== undefined ? step.bossId : step.boss_id;
      const bName = bossCatalogMap?.get(String(bId)) || (bossCatalog || []).find(b => String(b.id) === String(bId))?.name || step.bossName || `Босс #${bId}`;
      const mLabel = modeLabels[step.mode] || step.mode || "Пацанский";
      const count = Math.max(1, Number(step.count) || 1);
      const stepStart = runningOffset;
      const stepEnd = stepStart + count;
      runningOffset = stepEnd;
      const isCurrentStep = isRunning && curIdx >= stepStart && curIdx < stepEnd;
      return `<span class="preset-step-chip ${isCurrentStep ? 'active' : ''}">${idx + 1}. ${bName} (${mLabel}) × ${count}</span>`;
    }).join("");

    const displayStep = Math.min(totalSteps, curIdx + 1);
    return `
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <span style="font-weight: 700; font-size: 13px; color: #fff;">${preset.name || 'Без названия'}</span>
          <span class="preset-time-badge">⏰ ${preset.schedule_time_msk || '09:00'} МСК</span>
          ${preset.daily_enabled ? `<span class="badge" style="background: rgba(52, 211, 153, 0.15); color: #34d399; font-size: 10px;">Ежедневно</span>` : '<span class="badge" style="background: rgba(255, 255, 255, 0.08); color: var(--muted-foreground); font-size: 10px;">По вызову</span>'}
          ${isRunning ? `<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171; font-size: 10px; font-weight: 700;">⚔️ В процессе (${displayStep}/${totalSteps})</span>` : ''}
          ${preset.last_status ? `<span style="font-size: 10px; color: var(--muted-foreground); max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${preset.last_status}">${preset.last_status}</span>` : ''}
        </div>
        <div style="display: flex; gap: 6px; align-items: center;">
          ${isRunning ? `
            <button class="btn btn-danger btn-sm btn-stop-preset" data-preset-id="${preset.id}" style="padding: 4px 8px; font-size: 11px;">⏹️ Стоп</button>
          ` : `
            <button class="btn btn-primary btn-sm btn-run-preset" data-preset-id="${preset.id}" style="padding: 4px 8px; font-size: 11px;">▶️ Запустить</button>
          `}
          <button class="btn btn-secondary btn-sm btn-edit-preset" data-preset-id="${preset.id}" title="Редактировать" style="padding: 4px 8px; font-size: 11px;">✏️</button>
          <button class="btn btn-secondary btn-sm btn-delete-preset" data-preset-id="${preset.id}" title="Удалить" style="padding: 4px 8px; font-size: 11px; color: #f87171;">🗑️</button>
        </div>
      </div>
      <div style="display: flex; gap: 4px; flex-wrap: wrap; margin-top: 8px;">
        ${stepsChipsHtml || '<span style="font-size: 11px; color: var(--muted-foreground);">Нет шагов</span>'}
      </div>
    `;
  };

  const bindPresetCard = (card, preset) => {
    card.className = `preset-card ${preset.is_running ? 'preset-running' : ''}`;
    card.dataset.presetId = String(preset.id);
    card.innerHTML = buildInnerHtml(preset);
    card.querySelector(".btn-run-preset")?.addEventListener("click", () => runPreset(preset.id));
    card.querySelector(".btn-stop-preset")?.addEventListener("click", () => stopPreset(preset.id));
    card.querySelector(".btn-edit-preset")?.addEventListener("click", () => openPresetModal(preset));
    card.querySelector(".btn-delete-preset")?.addEventListener("click", () => deletePreset(preset.id));
  };

  reconcileKeyedList(
    container,
    bossPresets || [],
    p => p.id,
    p => `${p.id}|${p.name}|${p.schedule_time_msk}|${Boolean(p.daily_enabled)}|${Boolean(p.is_running)}|${p.current_step_index}|${p.last_status}|${JSON.stringify(p.items || [])}`,
    preset => {
      const card = document.createElement("div");
      bindPresetCard(card, preset);
      return card;
    },
    (card, preset) => bindPresetCard(card, preset),
    `<div style="font-size: 11px; color: var(--muted-foreground); text-align: center; padding: 14px; background: rgba(0,0,0,0.1); border-radius: 6px; border: 1px dashed var(--border);">
      Нет созданных пресетов. Нажмите «+ Создать пресет», чтобы настроить цепочку атак боссов с ежедневным расписанием.
    </div>`
  );
}

function openPresetModal(preset = null) {
  const modal = document.getElementById("modal-boss-preset");
  if (!modal) return;
  modal.style.display = "flex";

  const titleEl = document.getElementById("preset-modal-title");
  const nameInput = document.getElementById("preset-input-name");
  const timeInput = document.getElementById("preset-input-time");
  const dailyInput = document.getElementById("preset-input-daily");

  if (preset) {
    editingPresetId = preset.id;
    if (titleEl) titleEl.textContent = "✏️ Редактирование пресета";
    if (nameInput) nameInput.value = preset.name || "";
    if (timeInput) timeInput.value = preset.schedule_time_msk || "09:00";
    if (dailyInput) dailyInput.checked = Boolean(preset.daily_enabled);
    presetWorkingSteps = (preset.items || []).map(s => ({
      boss_id: s.bossId !== undefined ? s.bossId : s.boss_id,
      mode: s.mode || "pacansky",
      count: s.count || 1
    }));
  } else {
    editingPresetId = null;
    if (titleEl) titleEl.textContent = "📋 Новый пресет боссов";
    if (nameInput) nameInput.value = "";
    if (timeInput) timeInput.value = "09:00";
    if (dailyInput) dailyInput.checked = true;
    const defaultBossId = bossCatalog && bossCatalog.length > 0 ? bossCatalog[0].id : 1;
    presetWorkingSteps = [{ boss_id: defaultBossId, mode: "pacansky", count: 1 }];
  }

  renderPresetModalSteps();
}

function closePresetModal() {
  const modal = document.getElementById("modal-boss-preset");
  if (modal) modal.style.display = "none";
  editingPresetId = null;
  presetWorkingSteps = [];
}

function renderPresetModalSteps() {
  const container = document.getElementById("preset-steps-container");
  if (!container) return;

  if (!presetWorkingSteps || presetWorkingSteps.length === 0) {
    container.innerHTML = `<div style="color: var(--muted-foreground); text-align: center; padding: 10px; font-size: 11px;">Шагов пока нет. Нажмите «+ Добавить шаг».</div>`;
    return;
  }

  container.innerHTML = "";

  const bossesList = Array.isArray(bossCatalog) && bossCatalog.length > 0 ? bossCatalog : [{ id: 1, name: "Кирпич" }];

  presetWorkingSteps.forEach((step, idx) => {
    const row = document.createElement("div");
    row.style.cssText = "display: flex; gap: 6px; align-items: center; background: rgba(255,255,255,0.03); padding: 6px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.06);";

    // Boss options
    const bossOpts = bossesList.map(b => {
      const isSel = String(b.id) === String(step.boss_id);
      const lockMark = b.isLocked ? " 🔒" : "";
      return `<option value="${b.id}" ${isSel ? 'selected' : ''}>${b.name}${lockMark}</option>`;
    }).join("");

    row.innerHTML = `
      <span style="font-size: 11px; font-weight: 700; color: var(--muted-foreground); width: 18px;">${idx + 1}.</span>
      <select class="btn btn-secondary btn-sm preset-step-boss-select" style="flex: 1; min-width: 110px; text-align: left; padding: 4px 6px; font-size: 11px;">
        ${bossOpts}
      </select>
      <select class="btn btn-secondary btn-sm preset-step-mode-select" style="width: 100px; padding: 4px 6px; font-size: 11px;">
        <option value="pacansky" ${step.mode === 'pacansky' ? 'selected' : ''}>Пацанский</option>
        <option value="blotnoy" ${step.mode === 'blotnoy' ? 'selected' : ''}>Блатной</option>
        <option value="avtoritetny" ${step.mode === 'avtoritetny' ? 'selected' : ''}>Авторитетный</option>
        <option value="odin" ${step.mode === 'odin' ? 'selected' : ''}>В одного</option>
      </select>
      <input type="number" min="1" max="100" class="btn btn-secondary btn-sm preset-step-count-input" value="${step.count || 1}" title="Количество боев" style="width: 48px; text-align: center; padding: 4px; font-size: 11px;">
      <button class="btn btn-secondary btn-sm preset-step-up" title="Вверх" ${idx === 0 ? 'disabled' : ''} style="padding: 2px 6px; font-size: 10px;">▲</button>
      <button class="btn btn-secondary btn-sm preset-step-down" title="Вниз" ${idx === presetWorkingSteps.length - 1 ? 'disabled' : ''} style="padding: 2px 6px; font-size: 10px;">▼</button>
      <button class="btn btn-secondary btn-sm preset-step-del" title="Удалить" style="padding: 2px 6px; font-size: 10px; color: #f87171;">✕</button>
    `;

    row.querySelector(".preset-step-boss-select")?.addEventListener("change", (e) => {
      step.boss_id = parseInt(e.target.value, 10);
    });

    row.querySelector(".preset-step-mode-select")?.addEventListener("change", (e) => {
      step.mode = e.target.value;
    });

    row.querySelector(".preset-step-count-input")?.addEventListener("change", (e) => {
      step.count = Math.max(1, parseInt(e.target.value, 10) || 1);
      e.target.value = step.count;
    });

    row.querySelector(".preset-step-up")?.addEventListener("click", () => {
      if (idx > 0) {
        const tmp = presetWorkingSteps[idx];
        presetWorkingSteps[idx] = presetWorkingSteps[idx - 1];
        presetWorkingSteps[idx - 1] = tmp;
        renderPresetModalSteps();
      }
    });

    row.querySelector(".preset-step-down")?.addEventListener("click", () => {
      if (idx < presetWorkingSteps.length - 1) {
        const tmp = presetWorkingSteps[idx];
        presetWorkingSteps[idx] = presetWorkingSteps[idx + 1];
        presetWorkingSteps[idx + 1] = tmp;
        renderPresetModalSteps();
      }
    });

    row.querySelector(".preset-step-del")?.addEventListener("click", () => {
      presetWorkingSteps.splice(idx, 1);
      renderPresetModalSteps();
    });

    container.appendChild(row);
  });
}

async function savePreset() {
  const nameInput = document.getElementById("preset-input-name");
  const timeInput = document.getElementById("preset-input-time");
  const dailyInput = document.getElementById("preset-input-daily");

  const nameVal = (nameInput?.value || "").trim();
  if (!nameVal) {
    showToast("Укажите название пресета", "error");
    return;
  }

  const timeVal = (timeInput?.value || "09:00").trim();
  const timeRegex = /^([01]\d|2[0-3]):[0-5]\d$/;
  if (!timeRegex.test(timeVal)) {
    showToast("Время должно быть в формате ЧЧ:ММ (00:00 - 23:59)", "error");
    return;
  }

  if (!presetWorkingSteps || presetWorkingSteps.length === 0) {
    showToast("Добавьте хотя бы одного босса в пресет", "error");
    return;
  }

  const payload = {
    name: nameVal,
    schedule_time_msk: timeVal,
    daily_enabled: Boolean(dailyInput?.checked),
    items: presetWorkingSteps.map(s => {
      const bIdNum = parseInt(s.boss_id !== undefined ? s.boss_id : s.bossId, 10);
      const bObj = (bossCatalog || []).find(b => b.id === bIdNum);
      return {
        bossId: bIdNum,
        boss_id: bIdNum,
        bossName: bObj?.name || `Босс #${bIdNum}`,
        mode: s.mode || "pacansky",
        count: Math.max(1, parseInt(s.count, 10) || 1)
      };
    })
  };

  try {
    let res;
    if (editingPresetId) {
      res = await apiFetch(`/boss/presets/${editingPresetId}`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      });
    } else {
      res = await apiFetch("/boss/presets", {
        method: "POST",
        body: JSON.stringify(payload)
      });
    }

    if (res.success) {
      showToast(editingPresetId ? "Пресет обновлен" : "Пресет успешно создан", "success");
      closePresetModal();
      loadBossPresets();
    } else {
      showToast(res.error || "Ошибка сохранения пресета", "error");
    }
  } catch (err) {
    showToast(`Ошибка сохранения: ${err.message}`, "error");
  }
}

async function runPreset(presetId) {
  try {
    const res = await apiFetch(`/boss/presets/${presetId}/run`, {
      method: "POST"
    });
    if (res.success) {
      showToast("Пресет запущен!", "success");
      loadBossPresets();
      loadBoss();
    } else {
      showToast(res.error || "Не удалось запустить пресет", "error");
    }
  } catch (err) {
    showToast(`Ошибка запуска пресета: ${err.message}`, "error");
  }
}

async function stopPreset(presetId) {
  try {
    const res = await apiFetch(`/boss/presets/${presetId}/stop`, {
      method: "POST"
    });
    if (res.success) {
      showToast("Пресет остановлен", "info");
      loadBossPresets();
    } else {
      showToast(res.error || "Не удалось остановить пресет", "error");
    }
  } catch (err) {
    showToast(`Ошибка остановки пресета: ${err.message}`, "error");
  }
}

async function deletePreset(presetId) {
  if (!confirm("Вы уверены, что хотите удалить этот пресет?")) return;
  try {
    const res = await apiFetch(`/boss/presets/${presetId}`, {
      method: "DELETE"
    });
    if (res.success) {
      showToast("Пресет удален", "success");
      loadBossPresets();
    } else {
      showToast(res.error || "Ошибка удаления пресета", "error");
    }
  } catch (err) {
    showToast(`Ошибка удаления: ${err.message}`, "error");
  }
}

function initBossPresetsUI() {
  document.getElementById("btn-create-preset")?.addEventListener("click", () => openPresetModal(null));
  document.getElementById("btn-close-preset-modal")?.addEventListener("click", closePresetModal);
  document.getElementById("btn-cancel-preset")?.addEventListener("click", closePresetModal);
  document.getElementById("modal-boss-preset")?.addEventListener("click", (e) => {
    if (e.target.id === "modal-boss-preset") closePresetModal();
  });

  document.getElementById("btn-preset-add-step")?.addEventListener("click", () => {
    const defaultBossId = bossCatalog && bossCatalog.length > 0 ? bossCatalog[0].id : 1;
    presetWorkingSteps.push({ boss_id: defaultBossId, mode: "pacansky", count: 1 });
    renderPresetModalSteps();
  });

  document.getElementById("btn-save-preset")?.addEventListener("click", savePreset);
}


// ============================================================================
// SECTION: РЕЙДЫ И НОВОСТИ & РАДАР ДАМАГЕРОВ
// ============================================================================

let currentRaidsTab = "raids";
let radarPlayers = [];
let batchInProgress = false;
let stopBatchRequested = false;
let raidsInitialized = false;
let raidsSafetyStatus = null;
let configuredTgChannels = ["pro_prison", "pro_prison_chat"];
let guildScanCooldownTimer = null;
let tgScanCooldownTimer = null;

function initRaidsSection() {
  if (raidsInitialized) return;
  raidsInitialized = true;

  // Segment Tab switching
  document.querySelectorAll(".raids-segment-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-raids-tab");
      if (tab) switchRaidsTab(tab);
    });
  });

  // Action buttons
  document.getElementById("btn-raids-goto-radar")?.addEventListener("click", () => {
    switchRaidsTab("radar");
  });

  document.getElementById("btn-refresh-raids")?.addEventListener("click", () => {
    loadRaids();
  });

  document.getElementById("btn-refresh-news")?.addEventListener("click", () => {
    loadNews();
  });

  document.getElementById("btn-refresh-radar")?.addEventListener("click", () => {
    loadActivePlayersRadar();
  });

  document.getElementById("btn-refresh-safety")?.addEventListener("click", async () => {
    await loadSafetyStatus();
    showToast("Статус безопасности обновлен", "info");
  });

  // Guild Scanner Button
  document.getElementById("btn-scan-guilds")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-scan-guilds");
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    const oldText = btn.innerHTML;
    btn.innerHTML = '<div class="spinner-sm" style="display:inline-block; vertical-align:middle; margin-right:4px;"></div> Сканирование...';
    try {
      const tier = document.getElementById("radar-filter-tier")?.value || "accessible";
      const minAuth = Number(document.getElementById("radar-filter-min-auth")?.value || 0);
      const maxAuth = Number(document.getElementById("radar-filter-max-auth")?.value || 0);
      const res = await apiFetch("/raids/scan-guilds", {
        method: "POST",
        body: JSON.stringify({ tier, minAuthority: minAuth, maxAuthority: maxAuth }),
      });
      if (res.status === "cooldown") {
        showToast(res.message, "warning");
        if (res.cooldownSeconds) startGuildCooldownCountdown(res.cooldownSeconds);
      } else if (res.success) {
        showToast(res.message || "Сканирование бригад завершено!", "success");
        startGuildCooldownCountdown(300);
        await loadActivePlayersRadar();
      } else {
        showToast(res.message || "Ошибка сканирования", "error");
      }
    } catch (err) {
      showToast(`Ошибка: ${err.message}`, "error");
    } finally {
      if (!guildScanCooldownTimer) btn.disabled = false;
      btn.innerHTML = oldText;
      const badge = document.getElementById("badge-guild-cooldown");
      if (guildScanCooldownTimer && badge) badge.style.display = "inline";
    }
  });

  // TG Channels Scanner
  document.getElementById("btn-scan-channels")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-scan-channels");
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    const oldText = btn.innerHTML;
    btn.innerHTML = '<div class="spinner-sm" style="display:inline-block; vertical-align:middle; margin-right:4px;"></div> Проверка...';
    try {
      const res = await apiFetch("/raids/scan-channels", {
        method: "POST",
        body: JSON.stringify({ channels: configuredTgChannels }),
      });
      if (res.status === "cooldown") {
        showToast(res.message, "warning");
        if (res.cooldownSeconds) startTgCooldownCountdown(res.cooldownSeconds);
      } else if (res.status === "flood_wait") {
        showToast(res.message, "warning");
        if (res.floodWaitSeconds) startTgCooldownCountdown(res.floodWaitSeconds);
      } else if (res.status === "tg_not_configured") {
        showToast(res.message, "warning");
      } else if (res.success) {
        showToast(res.message || `Найдено постов: ${res.foundPosts}`, "success");
        startTgCooldownCountdown(900);
        await loadRaids();
      } else {
        showToast(res.message || "Ошибка проверки каналов", "error");
      }
    } catch (err) {
      showToast(`Ошибка: ${err.message}`, "error");
    } finally {
      if (!tgScanCooldownTimer) btn.disabled = false;
      btn.innerHTML = oldText;
      const badge = document.getElementById("badge-tg-cooldown");
      if (tgScanCooldownTimer && badge) badge.style.display = "inline";
    }
  });

  // Add TG Channel Button
  document.getElementById("btn-add-tg-channel")?.addEventListener("click", async () => {
    const input = document.getElementById("input-new-tg-channel");
    if (!input) return;
    let val = (input.value || "").trim();
    val = val.replace(/^https?:\/\/t\.me\//i, "").replace(/^@/, "").split("/")[0].split("?")[0].trim();
    if (!val) {
      showToast("Укажите юзернейм канала", "warning");
      return;
    }
    if (configuredTgChannels.includes(val)) {
      showToast("Канал уже в списке", "info");
      return;
    }
    if (configuredTgChannels.length >= 10) {
      showToast("Максимум 10 каналов", "warning");
      return;
    }
    configuredTgChannels.push(val);
    input.value = "";
    renderTgChannelsChips();
    await saveTgChannelsConfig();
  });

  // Accordion for safe outreach
  document.getElementById("btn-toggle-outreach-accordion")?.addEventListener("click", () => {
    const body = document.getElementById("radar-outreach-accordion-body");
    const arrow = document.getElementById("icon-outreach-accordion-arrow");
    if (!body) return;
    const isHidden = body.style.display === "none" || !body.style.display;
    body.style.display = isHidden ? "block" : "none";
    if (arrow) arrow.textContent = isHidden ? "▲" : "▼";
  });

  document.getElementById("btn-save-outreach-cfg")?.addEventListener("click", async () => {
    await saveOutreachConfig();
  });

  // Radar Filter changes
  document.getElementById("radar-filter-source")?.addEventListener("change", () => {
    loadActivePlayersRadar();
  });

  document.getElementById("radar-filter-tier")?.addEventListener("change", async (e) => {
    const tier = e.target.value || "accessible";
    const minEl = document.getElementById("radar-filter-min-auth");
    const maxEl = document.getElementById("radar-filter-max-auth");
    const presets = {
      accessible: [0, 2000000],
      mid: [200000, 15000000],
      top: [15000000, 0],
    };
    if (presets[tier]) {
      if (minEl) minEl.value = presets[tier][0] > 0 ? String(presets[tier][0]) : "";
      if (maxEl) maxEl.value = presets[tier][1] > 0 ? String(presets[tier][1]) : "";
    }
    try {
      await apiFetch("/config", {
        method: "PATCH",
        body: JSON.stringify({
          friends_parser_tier: tier,
          friends_parser_min_authority: Number(minEl?.value || 0),
          friends_parser_max_authority: Number(maxEl?.value || 0),
        }),
      });
    } catch (err) { }
    loadActivePlayersRadar();
  });

  const onAuthFilterChange = async () => {
    const tierEl = document.getElementById("radar-filter-tier");
    if (tierEl) tierEl.value = "custom";
    const minA = Number(document.getElementById("radar-filter-min-auth")?.value || 0);
    const maxA = Number(document.getElementById("radar-filter-max-auth")?.value || 0);
    try {
      await apiFetch("/config", {
        method: "PATCH",
        body: JSON.stringify({
          friends_parser_tier: "custom",
          friends_parser_min_authority: minA,
          friends_parser_max_authority: maxA,
        }),
      });
    } catch (err) { }
    loadActivePlayersRadar();
  };
  document.getElementById("radar-filter-min-auth")?.addEventListener("change", onAuthFilterChange);
  document.getElementById("radar-filter-max-auth")?.addEventListener("change", onAuthFilterChange);

  document.getElementById("radar-filter-min-dmg")?.addEventListener("change", () => {
    loadActivePlayersRadar();
  });

  document.getElementById("radar-filter-max-dmg")?.addEventListener("change", () => {
    loadActivePlayersRadar();
  });

  document.getElementById("radar-filter-limit")?.addEventListener("change", () => {
    loadActivePlayersRadar();
  });

  document.getElementById("radar-filter-exclude-friends")?.addEventListener("change", () => {
    loadActivePlayersRadar();
  });

  // Batch actions
  document.getElementById("btn-radar-add-batch")?.addEventListener("click", () => {
    startRadarBatchAdd();
  });

  document.getElementById("btn-radar-stop-batch")?.addEventListener("click", () => {
    stopBatchRequested = true;
    showToast("Остановка отправки заявок...", "info");
  });

  // Parse raid text
  document.getElementById("btn-parse-raid-text")?.addEventListener("click", () => {
    parseRaidText();
  });
}

function switchRaidsTab(tabName, opts = {}) {
  initRaidsSection();
  currentRaidsTab = tabName;

  // Update tabs
  document.querySelectorAll(".raids-segment-tab").forEach(btn => {
    if (btn.getAttribute("data-raids-tab") === tabName) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // Update subviews
  document.querySelectorAll(".raids-subview").forEach(view => {
    view.classList.remove("active");
    view.style.display = "none";
  });

  const activeView = document.getElementById(`raids-view-${tabName}`);
  if (activeView) {
    activeView.classList.add("active");
    activeView.style.display = "block";
  }

  // Load data for active tab
  if (tabName === "raids") loadRaids();
  else if (tabName === "news") loadNews();
  else if (tabName === "radar") loadActivePlayersRadar(opts);
}

async function loadRaidsSection(opts = {}) {
  initRaidsSection();
  await loadSafetyStatus();
  switchRaidsTab(currentRaidsTab || "raids", opts);
}

// --- Safety Bar & Status ---
async function loadSafetyStatus() {
  try {
    const res = await apiFetch("/raids/safety-status");
    if (res && res.safety) {
      raidsSafetyStatus = res.safety;
      renderSafetyBar(res.safety);
    }
  } catch (err) {
    console.warn("Failed to load raids safety status:", err);
  }
}

function renderSafetyBar(safety) {
  const limitText = document.getElementById("raids-safety-limit-text");
  const circuitBadge = document.getElementById("raids-safety-circuit-badge");

  if (limitText) {
    const sent = safety.sentLast24h || 0;
    const limit = safety.dailyLimit || 50;
    const rem = safety.remaining24h !== undefined ? safety.remaining24h : Math.max(0, limit - sent);
    limitText.textContent = `Лимит за 24ч: ${sent} / ${limit} (осталось ${rem})`;
    if (rem === 0) {
      limitText.style.color = "#f87171";
    } else if (rem <= 5) {
      limitText.style.color = "#fbbf24";
    } else {
      limitText.style.color = "#34d399";
    }
  }

  if (circuitBadge) {
    if (safety.circuitOpen) {
      circuitBadge.className = "raids-safety-status-badge safety-status-paused";
      circuitBadge.textContent = `⏸ Пауза: ${safety.circuitReason || "Предохранитель"}`;
    } else {
      circuitBadge.className = "raids-safety-status-badge safety-status-ok";
      circuitBadge.textContent = "🛡️ Защита: Активна (OK)";
    }
  }

  // Update Guild Cooldown
  if (safety.guildScanCooldownSec && safety.guildScanCooldownSec > 0) {
    startGuildCooldownCountdown(safety.guildScanCooldownSec);
  }

  // Update TG Cooldown
  if (safety.tgScanCooldownSec && safety.tgScanCooldownSec > 0) {
    startTgCooldownCountdown(safety.tgScanCooldownSec);
  }
}

function startGuildCooldownCountdown(seconds) {
  if (guildScanCooldownTimer) clearInterval(guildScanCooldownTimer);
  let rem = seconds;
  const btn = document.getElementById("btn-scan-guilds");
  const badge = document.getElementById("badge-guild-cooldown");

  if (btn) btn.disabled = true;
  if (badge) {
    badge.style.display = "inline";
    badge.textContent = `(${rem}c)`;
  }

  guildScanCooldownTimer = setInterval(() => {
    rem--;
    if (rem <= 0) {
      clearInterval(guildScanCooldownTimer);
      guildScanCooldownTimer = null;
      if (btn) btn.disabled = false;
      if (badge) {
        badge.style.display = "none";
        badge.textContent = "";
      }
    } else if (badge) {
      badge.textContent = `(${rem}c)`;
    }
  }, 1000);
}

function startTgCooldownCountdown(seconds) {
  if (tgScanCooldownTimer) clearInterval(tgScanCooldownTimer);
  let rem = seconds;
  const btn = document.getElementById("btn-scan-channels");
  const badge = document.getElementById("badge-tg-cooldown");

  if (btn) btn.disabled = true;
  if (badge) {
    badge.style.display = "inline";
    badge.textContent = `(${rem}c)`;
  }

  tgScanCooldownTimer = setInterval(() => {
    rem--;
    if (rem <= 0) {
      clearInterval(tgScanCooldownTimer);
      tgScanCooldownTimer = null;
      if (btn) btn.disabled = false;
      if (badge) {
        badge.style.display = "none";
        badge.textContent = "";
      }
    } else if (badge) {
      badge.textContent = `(${rem}c)`;
    }
  }, 1000);
}

// --- TG Channels Manager ---
function renderTgChannelsChips() {
  const container = document.getElementById("tg-channels-chips");
  const countBadge = document.getElementById("badge-tg-count");
  if (!container) return;

  if (countBadge) countBadge.textContent = configuredTgChannels.length;

  if (configuredTgChannels.length === 0) {
    container.innerHTML = '<span style="font-size: 11px; color: var(--muted-foreground);">Каналы не настроены. Добавьте публичный канал.</span>';
    return;
  }

  container.innerHTML = "";
  configuredTgChannels.forEach((ch, idx) => {
    const chip = document.createElement("div");
    chip.className = "tg-channel-chip";
    chip.innerHTML = `
      <span>@${ch}</span>
      <span class="btn-remove-chip" data-idx="${idx}" title="Удалить">×</span>
    `;
    chip.querySelector(".btn-remove-chip")?.addEventListener("click", async (e) => {
      e.stopPropagation();
      configuredTgChannels.splice(idx, 1);
      renderTgChannelsChips();
      await saveTgChannelsConfig();
    });
    container.appendChild(chip);
  });
}

async function saveTgChannelsConfig() {
  try {
    await apiFetch("/config", {
      method: "PATCH",
      body: JSON.stringify({ raid_tg_channels: configuredTgChannels }),
    });
    showToast("Список Telegram-каналов обновлен", "info");
  } catch (err) {
    showToast(`Ошибка сохранения каналов: ${err.message}`, "error");
  }
}

// --- Outreach Accordion Config ---
async function loadOutreachConfig() {
  try {
    const cfg = window.currentBotConfig || (await apiFetch("/config")).config;
    if (cfg) {
      if (Array.isArray(cfg.raid_tg_channels) && cfg.raid_tg_channels.length > 0) {
        configuredTgChannels = [...cfg.raid_tg_channels];
        renderTgChannelsChips();
      }
      const autoEn = document.getElementById("cfg-auto-friend-outreach");
      const limitIn = document.getElementById("cfg-friend-outreach-daily-limit");
      const minDmgIn = document.getElementById("cfg-friend-outreach-min-damage");
      const maxDmgIn = document.getElementById("cfg-friend-outreach-max-damage");
      const onlyActIn = document.getElementById("cfg-friend-outreach-only-active");
      const badgeStatus = document.getElementById("badge-outreach-status");

      if (autoEn) autoEn.checked = Boolean(cfg.auto_friend_outreach);
      if (limitIn) limitIn.value = cfg.friend_outreach_daily_limit || 50;
      if (minDmgIn) minDmgIn.value = cfg.friend_outreach_min_damage || 0;
      if (maxDmgIn) maxDmgIn.value = cfg.friend_outreach_max_damage || 0;
      if (onlyActIn) onlyActIn.checked = cfg.friend_outreach_only_active !== undefined ? Boolean(cfg.friend_outreach_only_active) : true;

      if (badgeStatus) {
        if (cfg.auto_friend_outreach) {
          badgeStatus.textContent = "Вкл";
          badgeStatus.style.background = "rgba(52, 211, 153, 0.2)";
          badgeStatus.style.color = "#34d399";
        } else {
          badgeStatus.textContent = "Выкл";
          badgeStatus.style.background = "rgba(255, 255, 255, 0.1)";
          badgeStatus.style.color = "var(--muted-foreground)";
        }
      }
    }
  } catch (err) {
    console.warn("Failed to load outreach config:", err);
  }
}

async function saveOutreachConfig() {
  const autoEn = Boolean(document.getElementById("cfg-auto-friend-outreach")?.checked);
  const limitVal = parseInt(document.getElementById("cfg-friend-outreach-daily-limit")?.value || "50", 10);
  const minDmg = parseInt(document.getElementById("cfg-friend-outreach-min-damage")?.value || "0", 10);
  const maxDmg = parseInt(document.getElementById("cfg-friend-outreach-max-damage")?.value || "0", 10);
  const onlyAct = Boolean(document.getElementById("cfg-friend-outreach-only-active")?.checked);

  if (isNaN(limitVal) || limitVal < 1 || limitVal > 500) {
    showToast("Суточный лимит должен быть от 1 до 500 заявок", "warning");
    return;
  }

  try {
    const res = await apiFetch("/config", {
      method: "PATCH",
      body: JSON.stringify({
        auto_friend_outreach: autoEn,
        friend_outreach_daily_limit: limitVal,
        friend_outreach_min_damage: minDmg,
        friend_outreach_max_damage: maxDmg,
        friend_outreach_only_active: onlyAct,
      }),
    });
    if (res.success) {
      if (window.currentBotConfig) {
        window.currentBotConfig.friend_outreach_daily_limit = limitVal;
        window.currentBotConfig.auto_friend_outreach = autoEn;
        window.currentBotConfig.friend_outreach_min_damage = minDmg;
        window.currentBotConfig.friend_outreach_max_damage = maxDmg;
        window.currentBotConfig.friend_outreach_only_active = onlyAct;
      }
      if (raidsSafetyStatus) {
        const sent = raidsSafetyStatus.sentLast24h || 0;
        raidsSafetyStatus.dailyLimit = limitVal;
        raidsSafetyStatus.remaining24h = Math.max(0, limitVal - sent);
        renderSafetyBar(raidsSafetyStatus);
      }
      showToast("Настройки авто-набора сохранены!", "success");
      const badgeStatus = document.getElementById("badge-outreach-status");
      if (badgeStatus) {
        if (autoEn) {
          badgeStatus.textContent = "Вкл";
          badgeStatus.style.background = "rgba(52, 211, 153, 0.2)";
          badgeStatus.style.color = "#34d399";
        } else {
          badgeStatus.textContent = "Выкл";
          badgeStatus.style.background = "rgba(255, 255, 255, 0.1)";
          badgeStatus.style.color = "var(--muted-foreground)";
        }
      }
      await loadSafetyStatus();
    }
  } catch (err) {
    showToast(`Ошибка сохранения: ${err.message}`, "error");
  }
}

let _lastRaidsHash = "";
let _raidsFetchSeq = 0;

// --- Subview 1: Рейды ---
async function loadRaids() {
  const container = document.getElementById("raids-list-container");
  const banner = document.getElementById("raids-source-banner");
  if (!container) return;

  const seq = ++_raidsFetchSeq;
  renderTgChannelsChips();

  const hasCards = Boolean(container.querySelector(".raid-card"));
  if (!hasCards && container.children.length === 0) {
    container.innerHTML = '<div style="color: var(--muted-foreground); text-align: center; padding: 24px; font-size: 12px;"><div class="spinner-sm" style="margin: 0 auto 8px auto;"></div>Загрузка рейдов...</div>';
  }

  try {
    const res = await apiFetch("/raids");
    if (seq !== _raidsFetchSeq) return;
    const raids = res.raids || [];
    const tgRaids = res.telegramRaids || [];

    const allRaidsToRender = [];
    tgRaids.forEach(tgr => {
      allRaidsToRender.push({
        id: `tg_${tgr.id}`,
        brigadeName: tgr.title || `Рейд из @${tgr.channelUsername}`,
        bossName: "Telegram Raid",
        isTelegram: true,
        channelUsername: tgr.channelUsername,
        postDate: tgr.postDate,
        rawPreview: tgr.rawPreview,
        participants: tgr.participants || [],
      });
    });

    raids.forEach(r => allRaidsToRender.push(r));

    if (res.isPaywalled && allRaidsToRender.length === 0) {
      if (banner) {
        banner.style.display = "flex";
        const titleEl = document.getElementById("raids-banner-title");
        const descEl = document.getElementById("raids-banner-desc");
        if (titleEl) titleEl.textContent = `Источник: ${res.sourceStatus || "403 Paywall"}`;
        if (descEl) descEl.textContent = res.sourceMessage || "Требуется платная подписка. Доступны радар игроков из игры и TG-рейды.";
      }
      container.innerHTML = `
        <div style="text-align: center; padding: 28px 16px; color: var(--muted-foreground);">
          <div style="font-size: 32px; margin-bottom: 8px;">🔒</div>
          <div style="font-weight: 700; color: #fff; font-size: 14px; margin-bottom: 6px;">Закрытый источник рейдов @pro_prison_bot</div>
          <div style="font-size: 12px; max-width: 420px; margin: 0 auto 16px auto; line-height: 1.4;">
            Эндпоинт ProPrisonBot требует подписку. Используйте кнопку «Проверить каналы» выше для чтения рейдов из публичных Telegram-сообществ или перейдите в Радар!
          </div>
          <div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;">
            <button class="btn btn-primary btn-sm" onclick="switchRaidsTab('radar')">🔥 Перейти к радару дамагеров</button>
          </div>
        </div>
      `;
      return;
    }

    if (banner) {
      if (res.isPaywalled) {
        banner.style.display = "flex";
        const titleEl = document.getElementById("raids-banner-title");
        const descEl = document.getElementById("raids-banner-desc");
        if (titleEl) titleEl.textContent = `Источник ProPrisonBot: 403 Paywall (Отображаются рейды из Telegram)`;
        if (descEl) descEl.textContent = "Показаны рейды, спарсенные из ваших открытых Telegram-каналов.";
      } else {
        banner.style.display = "none";
      }
    }

    if (allRaidsToRender.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 28px 16px; color: var(--muted-foreground);">
          <div style="font-size: 32px; margin-bottom: 8px;">🚩</div>
          <div style="font-weight: 700; color: #fff; font-size: 14px; margin-bottom: 6px;">Нет активных рейдов</div>
          <div style="font-size: 12px; max-width: 420px; margin: 0 auto 16px auto; line-height: 1.4;">
            В данный момент активных рейдов не найдено. Нажмите «Проверить каналы» или наберите друзей через радар!
          </div>
          <button class="btn btn-primary btn-sm" onclick="switchRaidsTab('radar')">🔥 Открыть радар дамагеров</button>
        </div>
      `;
      return;
    }

    renderRaidsList(allRaidsToRender, container);
  } catch (err) {
    container.innerHTML = `<div style="color: var(--destructive); text-align: center; padding: 20px; font-size: 12px;">Ошибка загрузки рейдов: ${err.message}</div>`;
  }
}

function renderRaidsList(raids, container) {
  const raidsHash = JSON.stringify(raids.map(r => [r.id, r.status, (r.participants || []).map(p => [p.userId, p.friendStatus])]));
  if (raidsHash === _lastRaidsHash && container.querySelectorAll(".raid-card").length === raids.length) {
    return;
  }
  _lastRaidsHash = raidsHash;

  const frag = document.createDocumentFragment();
  raids.forEach(r => {
    const card = document.createElement("div");
    card.className = "raid-card";

    const participants = r.participants || [];
    const minDmgStr = r.minDamage ? formatNum(r.minDamage) : "любой";

    let partHtml = "";
    participants.forEach(p => {
      let actionBtn = "";
      if (p.friendStatus === "friend") {
        actionBtn = '<button class="btn btn-sm btn-friend-added" disabled>✓ В друзьях</button>';
      } else if (p.friendStatus === "sent") {
        actionBtn = '<button class="btn btn-sm btn-friend-sent" disabled>✓ Заявка</button>';
      } else {
        actionBtn = `<button class="btn btn-primary btn-sm btn-add-friend" data-user-id="${p.userId}" data-nickname="${p.nickname || ''}">+ В друзья</button>`;
      }

      const dmgDisplay = p.damage ? formatNum(p.damage) : (p.claimedDamage ? formatNum(p.claimedDamage) : '');

      partHtml += `
        <div class="raid-participant-item">
          <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
            <div style="font-size: 12px; font-weight: 600; color: #fff;">${p.nickname || 'Игрок'}</div>
            <div style="font-size: 10px; color: var(--muted-foreground); font-family: monospace;">${p.userId}</div>
            <div style="font-size: 11px; color: #fbbf24; font-weight: 700;">${dmgDisplay ? '💥 ' + dmgDisplay : ''}</div>
          </div>
          <div>${actionBtn}</div>
        </div>
      `;
    });

    const isTg = r.isTelegram;
    const badgeHtml = isTg
      ? `<span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #818cf8;">📡 TG @${r.channelUsername || ''}</span>`
      : `<span class="badge" style="background: rgba(52, 211, 153, 0.2); color: #34d399;">${r.status || 'Активен'}</span>`;

    card.innerHTML = `
      <div class="raid-card-header">
        <div>
          <div class="raid-brigade-name">${r.brigadeName || "Бригадный рейд"}</div>
          <div class="raid-meta-row">
            <span>Босс: <strong style="color: #fff;">${r.bossName || r.bossId || 'Рейд'}</strong></span>
            <span>Мин. урон: <strong style="color: #fbbf24;">${minDmgStr}</strong></span>
            <span>Участников: <strong style="color: #fff;">${participants.length}</strong></span>
          </div>
        </div>
        <div>${badgeHtml}</div>
      </div>
      <div class="raid-participants-list">
        ${partHtml}
      </div>
    `;

    bindFriendshipButtons(card);
    frag.appendChild(card);
  });
  container.replaceChildren(frag);
}

let _lastNewsHash = "";
let _newsFetchSeq = 0;

// --- Subview 2: Новости ---
async function loadNews() {
  const container = document.getElementById("news-list-container");
  if (!container) return;

  const seq = ++_newsFetchSeq;
  const hasCards = Boolean(container.querySelector(".news-post-card"));
  if (!hasCards) {
    container.innerHTML = '<div style="color: var(--muted-foreground); text-align: center; padding: 24px; font-size: 12px;"><div class="spinner-sm" style="margin: 0 auto 8px auto;"></div>Загрузка новостей...</div>';
  }

  try {
    const res = await apiFetch("/news");
    if (seq !== _newsFetchSeq) return;
    const posts = res.news || res.posts || res.items || [];
    if (posts.length === 0) {
      _lastNewsHash = "empty";
      container.innerHTML = '<div style="color: var(--muted-foreground); text-align: center; padding: 24px; font-size: 12px;">Новостей и объявлений пока нет</div>';
      return;
    }

    const newsHash = JSON.stringify(posts.map(p => [p.id || p.title, p.date, (p.text || p.content || "").slice(0, 60)]));
    if (newsHash === _lastNewsHash && hasCards) return;
    _lastNewsHash = newsHash;

    const frag = document.createDocumentFragment();
    posts.forEach(p => {
      const card = document.createElement("div");
      card.className = "news-post-card";

      const title = p.title || p.header || "Объявление";
      const dateStr = p.date ? new Date(p.date * 1000).toLocaleString("ru-RU") : (p.created_at || "");
      const body = p.text || p.content || p.body || "";

      let imagesHtml = "";
      const images = p.images || p.photos || [];
      if (Array.isArray(images) && images.length > 0) {
        imagesHtml = '<div class="news-post-images">';
        images.forEach(imgUrl => {
          imagesHtml += `<img src="${imgUrl}" class="news-post-img" alt="Медиа" onerror="this.style.display='none'">`;
        });
        imagesHtml += '</div>';
      }

      card.innerHTML = `
        <div class="news-post-header">
          <div class="news-post-title">${title}</div>
          <div class="news-post-date">${dateStr}</div>
        </div>
        <div class="news-post-body">${body}</div>
        ${imagesHtml}
      `;
      frag.appendChild(card);
    });
    container.replaceChildren(frag);
  } catch (err) {
    if (!hasCards) {
      container.innerHTML = `<div style="color: var(--destructive); text-align: center; padding: 20px; font-size: 12px;">Ошибка загрузки новостей: ${err.message}</div>`;
    }
  }
}

// --- Subview 3: Радар активных дамагеров ---
let _radarFetchSeq = 0;
let _isLoadingRadar = false;
let _lastRadarFingerprint = "";

function renderActivePlayersRadarFromData(res) {
  const container = document.getElementById("radar-players-container");
  const statsText = document.getElementById("radar-stats-text");
  const dbStatsEl = document.getElementById("radar-db-stats");
  if (!container || !res) return;

  liveSlices.data.radar = res;
  radarPlayers = res.players || [];

  setTextIfChanged(statsText, `Найдено активных игроков: ${radarPlayers.length}`);

  const activeCount = radarPlayers.filter(p => p.isActiveRecently || (p.authorityDelta && p.authorityDelta > 0)).length;
  setTextIfChanged(dbStatsEl, `Отобрано: ${radarPlayers.length} игроков (${activeCount} активных за 24ч)`);

  if (res.safety) {
    raidsSafetyStatus = res.safety;
    renderSafetyBar(res.safety);
  }

  if (radarPlayers.length === 0) {
    _lastRadarFingerprint = "empty";
    container.innerHTML = '<div style="color: var(--muted-foreground); text-align: center; padding: 24px; font-size: 12px;">Игроков с заданными параметрами не найдено. Нажмите «Сканировать бригады» для наполнения базы!</div>';
    return;
  }

  const fingerprint = JSON.stringify(
    radarPlayers.map((p, i) => [
      p.userId, p.rank || (i + 1), p.nickname, p.level, p.authority, p.authorityDelta,
      p.damage, p.damageDelta, p.score, p.poisonDamage, p.gunshotDamage, p.knifeDamage,
      p.talents, p.friendStatus, p.source, p.guildName,
    ])
  );

  if (fingerprint === _lastRadarFingerprint && container.querySelectorAll(".radar-player-row[data-user-id]").length === radarPlayers.length) {
    return;
  }
  _lastRadarFingerprint = fingerprint;
  renderRadarPlayers(radarPlayers, container);
}

async function loadActivePlayersRadar(opts = {}) {
  const container = document.getElementById("radar-players-container");
  const statsText = document.getElementById("radar-stats-text");
  if (!container) return;

  if (_isLoadingRadar && opts.silent) return;
  _isLoadingRadar = true;
  const seq = ++_radarFetchSeq;

  const hasRows = Boolean(container.querySelector(".radar-player-row[data-user-id]"));
  if (!hasRows && !liveSlices.data.radar) {
    container.innerHTML = '<div style="color: var(--muted-foreground); text-align: center; padding: 24px; font-size: 12px;"><div class="spinner-sm" style="margin: 0 auto 8px auto;"></div>Сканирование кандидатов и активных игроков...</div>';
    if (statsText) statsText.textContent = "Загрузка игроков...";
  } else if (hasRows && !opts.silent && statsText) {
    statsText.innerHTML = `Найдено активных игроков: ${radarPlayers.length} <span class="radar-sync-pill">🔄 Синхронизация...</span>`;
  }

  const source = document.getElementById("radar-filter-source")?.value || "all";
  const tier = document.getElementById("radar-filter-tier")?.value || "";
  const minDmg = document.getElementById("radar-filter-min-dmg")?.value || "0";
  const maxDmg = document.getElementById("radar-filter-max-dmg")?.value || "0";
  const minAuth = document.getElementById("radar-filter-min-auth")?.value || "0";
  const maxAuth = document.getElementById("radar-filter-max-auth")?.value || "0";
  const limit = document.getElementById("radar-filter-limit")?.value || "30";
  const excludeFriends = Boolean(document.getElementById("radar-filter-exclude-friends")?.checked);

  try {
    await loadOutreachConfig();
    const qs = new URLSearchParams({
      source,
      minDamage: minDmg || "0",
      maxDamage: maxDmg || "0",
      minAuthority: minAuth || "0",
      maxAuthority: maxAuth || "0",
      limit,
      excludeFriends: String(excludeFriends),
    });
    if (tier) qs.set("tier", tier);
    const res = await apiFetch(`/raids/active-players?${qs.toString()}`);
    if (seq !== _radarFetchSeq) return;
    renderActivePlayersRadarFromData(res);
  } catch (err) {
    if (!hasRows) {
      container.innerHTML = `<div style="color: var(--destructive); text-align: center; padding: 20px; font-size: 12px;">Ошибка сканирования игроков: ${err.message}</div>`;
    }
    if (statsText) statsText.textContent = hasRows ? `Найдено активных игроков: ${radarPlayers.length}` : "Ошибка загрузки";
  } finally {
    if (seq === _radarFetchSeq) {
      _isLoadingRadar = false;
    }
  }
}

const loadRadarPlayers = loadActivePlayersRadar;

function _buildRadarRowData(p, idx) {
  const rank = p.rank || (idx + 1);
  let rankCls = "";
  if (rank === 1) rankCls = "rank-top1";
  else if (rank === 2) rankCls = "rank-top2";
  else if (rank === 3) rankCls = "rank-top3";

  const authVal = p.authority || 0;
  let lvlVal = p.level || 0;
  if ((!lvlVal || lvlVal <= 1) && authVal > 0) {
    lvlVal = Math.max(1, Math.floor((-40 + Math.sqrt(1600 + 80 * authVal)) / 40));
  }
  const levelDisplay = lvlVal > 0 ? `Ур. ${lvlVal}` : "Ур. 1";

  const dmgVal = p.damage || p.weeklyDamage || 0;
  const dmgStr = dmgVal > 0 ? formatNum(dmgVal) : "-";

  const isAct = p.isActiveRecently || (p.authorityDelta && p.authorityDelta > 0);
  const deltaStr = p.authorityDelta && p.authorityDelta > 0 ? ` (+${formatNum(p.authorityDelta)})` : "";
  const activeBadge = isAct ? `<span class="radar-badge-active">🔥 Активен${deltaStr}</span>` : "";

  const dmgDeltaBadge = (p.damageDelta && p.damageDelta > 0)
    ? `<span class="radar-badge-delta" style="color: #22c55e; font-weight: 700; font-size: 11px; background: rgba(34, 197, 94, 0.15); padding: 1px 5px; border-radius: 4px;">+Δ ${formatNum(p.damageDelta)}</span>`
    : "";

  const srcLabel = SOURCE_LABELS[p.source] || (p.source ? String(p.source) : "");
  const srcBadge = srcLabel ? `<span class="radar-badge-source" style="background: rgba(59, 130, 246, 0.2); color: #93c5fd; padding: 1px 5px; border-radius: 4px; font-size: 10px;">${srcLabel}</span>` : "";

  const scoreBadge = (p.score !== undefined && p.score !== null)
    ? `<span class="radar-badge-score" style="background: rgba(168, 85, 247, 0.2); color: #c084fc; font-weight: 700; padding: 1px 6px; border-radius: 4px; font-size: 11px;">⚡ Score ${p.score}</span>`
    : "";

  const talentsBadge = (p.talents && p.talents > 0)
    ? `<span class="radar-stat-badge radar-stat-talents">⭐ ${p.talents} тал.</span>`
    : "";

  const guildBadge = p.guildName
    ? `<span class="radar-badge-guild" title="Бригада">🏰 ${p.guildName}</span>`
    : "";

  const poisonVal = p.poisonDamage > 0 ? formatNum(p.poisonDamage) : "—";
  const gunshotVal = p.gunshotDamage > 0 ? formatNum(p.gunshotDamage) : "—";
  const knifeVal = p.knifeDamage > 0 ? formatNum(p.knifeDamage) : "—";

  let actionBtn = "";
  if (p.friendStatus === "friend") {
    actionBtn = '<button class="btn btn-sm btn-friend-added" disabled>✓ В друзьях</button>';
  } else if (p.friendStatus === "sent") {
    actionBtn = '<button class="btn btn-sm btn-friend-sent" disabled>✓ Заявка</button>';
  } else {
    actionBtn = `<button class="btn btn-primary btn-sm btn-add-friend" data-user-id="${p.userId}" data-nickname="${p.nickname || ''}">+ В друзья</button>`;
  }

  return {
    rank, rankCls, levelDisplay, dmgStr, authStr: formatNum(authVal),
    poisonVal, gunshotVal, knifeVal,
    scoreBadge, srcBadge, dmgDeltaBadge, activeBadge, guildBadge, talentsBadge,
    actionBtn, friendStatus: p.friendStatus || "none",
  };
}

function renderRadarPlayers(players, container) {
  const existingRows = Array.from(container.querySelectorAll(".radar-player-row[data-user-id]"));
  const sameOrder =
    existingRows.length === players.length &&
    players.every((p, i) => existingRows[i].getAttribute("data-user-id") === String(p.userId));

  // Keyed in-place DOM patching (zero flicker, preserves avatars & weapon icon elements)
  if (sameOrder) {
    players.forEach((p, idx) => {
      const row = existingRows[idx];
      const d = _buildRadarRowData(p, idx);

      const rankEl = row.querySelector(".radar-player-rank");
      if (rankEl) {
        const nextRankText = `#${d.rank}`;
        const nextRankClass = `radar-player-rank ${d.rankCls}`.trim();
        if (rankEl.textContent !== nextRankText) rankEl.textContent = nextRankText;
        if (rankEl.className !== nextRankClass) rankEl.className = nextRankClass;
      }

      const badgesRow = row.querySelector(".radar-player-name-row");
      if (badgesRow) {
        const nextBadges = `
          <span style="font-weight: 700; color: #fff;">${p.nickname || 'Арестант'}</span>
          <span style="font-size: 10px; background: rgba(255,255,255,0.08); padding: 1px 5px; border-radius: 4px;">${d.levelDisplay}</span>
          ${d.scoreBadge}${d.srcBadge}${d.dmgDeltaBadge}${d.activeBadge}${d.guildBadge}
        `;
        if (badgesRow.dataset.sig !== nextBadges) {
          badgesRow.innerHTML = nextBadges;
          badgesRow.dataset.sig = nextBadges;
        }
      }

      const dmgEl = row.querySelector(".radar-val-damage");
      if (dmgEl && dmgEl.textContent !== d.dmgStr) dmgEl.textContent = d.dmgStr;
      const authEl = row.querySelector(".radar-val-auth");
      if (authEl && authEl.textContent !== d.authStr) authEl.textContent = d.authStr;
      const pEl = row.querySelector(".radar-val-poison");
      if (pEl && pEl.textContent !== d.poisonVal) pEl.textContent = d.poisonVal;
      const gEl = row.querySelector(".radar-val-gunshot");
      if (gEl && gEl.textContent !== d.gunshotVal) gEl.textContent = d.gunshotVal;
      const kEl = row.querySelector(".radar-val-knife");
      if (kEl && kEl.textContent !== d.knifeVal) kEl.textContent = d.knifeVal;

      const statsWrap = row.querySelector(".radar-player-stats");
      if (statsWrap) {
        const existingTal = statsWrap.querySelector(".radar-stat-talents");
        if (d.talentsBadge) {
          if (existingTal) {
            const nextTxt = `⭐ ${p.talents} тал.`;
            if (existingTal.textContent !== nextTxt) existingTal.textContent = nextTxt;
          } else {
            statsWrap.insertAdjacentHTML("beforeend", d.talentsBadge);
          }
        } else if (existingTal) {
          existingTal.remove();
        }
      }

      const actWrap = row.querySelector(".radar-player-action");
      if (actWrap && actWrap.dataset.status !== d.friendStatus) {
        actWrap.innerHTML = d.actionBtn;
        actWrap.dataset.status = d.friendStatus;
        bindFriendshipButtons(actWrap);
      }
    });
    return;
  }

  // Atomic fragment swap when order or membership changed
  const frag = document.createDocumentFragment();
  players.forEach((p, idx) => {
    const row = document.createElement("div");
    row.className = "radar-player-row";
    row.id = `radar-player-${p.userId}`;
    row.setAttribute("data-user-id", String(p.userId));

    const d = _buildRadarRowData(p, idx);
    const initial = (p.nickname || "А")[0].toUpperCase();
    const avatarHtml = (p.photoUrl || p.avatarUrl)
      ? `<img src="${p.photoUrl || p.avatarUrl}" alt="Аватар" loading="lazy" decoding="async" onerror="this.onerror=null;this.parentElement.textContent='${initial}'">`
      : initial;

    row.innerHTML = `
      <div class="radar-player-left">
        <div class="radar-player-rank ${d.rankCls}">#${d.rank}</div>
        <div class="radar-player-avatar">${avatarHtml}</div>
        <div class="radar-player-info">
          <div class="radar-player-name-row" style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span style="font-weight: 700; color: #fff;">${p.nickname || 'Арестант'}</span>
            <span style="font-size: 10px; background: rgba(255,255,255,0.08); padding: 1px 5px; border-radius: 4px;">${d.levelDisplay}</span>
            ${d.scoreBadge}${d.srcBadge}${d.dmgDeltaBadge}${d.activeBadge}${d.guildBadge}
          </div>
          <div class="radar-player-id">ID: ${p.userId}</div>
          <div class="radar-player-stats">
            <span class="radar-stat-badge radar-stat-damage" title="Боевой урон">💥 <span class="radar-val-damage">${d.dmgStr}</span></span>
            <span class="radar-stat-badge radar-stat-auth" title="Авторитет"><img src="/static/assets/icons/authority.webp" class="radar-stat-icon" alt="Авторитет"> <span class="radar-val-auth">${d.authStr}</span></span>
            <span class="radar-stat-badge radar-stat-weapon" title="Урон ядом"><img src="/static/assets/icons/poison.webp" class="radar-weapon-icon" alt="Яд"> <span class="radar-val-poison">${d.poisonVal}</span></span>
            <span class="radar-stat-badge radar-stat-weapon" title="Урон самопалом"><img src="/static/assets/icons/gunshot.webp" class="radar-weapon-icon" alt="Самопал"> <span class="radar-val-gunshot">${d.gunshotVal}</span></span>
            <span class="radar-stat-badge radar-stat-weapon" title="Урон финкой"><img src="/static/assets/icons/knife.webp" class="radar-weapon-icon" alt="Финка"> <span class="radar-val-knife">${d.knifeVal}</span></span>
            ${d.talentsBadge}
          </div>
        </div>
      </div>
      <div class="radar-player-action" data-status="${d.friendStatus}">
        ${d.actionBtn}
      </div>
    `;

    bindFriendshipButtons(row);
    frag.appendChild(row);
  });
  container.replaceChildren(frag);
}

function bindFriendshipButtons(parentEl) {
  parentEl.querySelectorAll(".btn-add-friend").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const userId = btn.getAttribute("data-user-id");
      const nickname = btn.getAttribute("data-nickname");
      if (!userId) return;
      await sendFriendRequestSingle(userId, nickname, btn);
    });
  });
}

async function sendFriendRequestSingle(userId, nickname, btnEl) {
  btnEl.disabled = true;
  btnEl.textContent = "Отправка...";

  try {
    const res = await apiFetch("/actions/friendship/send", {
      method: "POST",
      body: JSON.stringify({ toUserId: Number(userId), nickname: nickname, source: "radar" }),
    });

    if (res.success) {
      btnEl.className = "btn btn-sm btn-friend-sent";
      btnEl.textContent = "✓ Отправлено";
      showToast(`Заявка отправлена игроку ${nickname || userId}!`, "success");
      await loadSafetyStatus();
    } else {
      btnEl.disabled = false;
      btnEl.textContent = "+ В друзья";
      showToast(res.message || "Не удалось отправить заявку", "warning");
      await loadSafetyStatus();
    }
  } catch (err) {
    btnEl.disabled = false;
    btnEl.textContent = "+ В друзья";
    showToast(`Ошибка: ${err.message}`, "error");
    await loadSafetyStatus();
  }
}

// --- Batch Friend Request ---
async function startRadarBatchAdd() {
  if (batchInProgress) return;

  const candidates = radarPlayers.filter(p => p.friendStatus !== "friend" && p.friendStatus !== "sent");
  if (candidates.length === 0) {
    showToast("Все найденные игроки уже в друзьях или заявка отправлена", "info");
    return;
  }

  const batchBtn = document.getElementById("btn-radar-add-batch");
  const stopBtn = document.getElementById("btn-radar-stop-batch");
  const progressBox = document.getElementById("radar-batch-progress-box");
  const progressFill = document.getElementById("radar-batch-progress-fill");
  const progressLabel = document.getElementById("radar-batch-progress-label");

  const toSend = candidates.slice(0, 15);
  batchInProgress = true;
  stopBatchRequested = false;

  if (batchBtn) batchBtn.style.display = "none";
  if (stopBtn) stopBtn.style.display = "inline-flex";
  if (progressBox) progressBox.style.display = "block";
  if (progressFill) progressFill.style.width = "0%";
  if (progressLabel) progressLabel.textContent = `Отправка 0/${toSend.length}...`;

  let sentCount = 0;
  let failedCount = 0;

  for (let i = 0; i < toSend.length; i++) {
    if (stopBatchRequested) {
      showToast("Пакетная отправка остановлена пользователем", "info");
      break;
    }

    const p = toSend[i];
    const pct = Math.round((i / toSend.length) * 100);
    if (progressFill) progressFill.style.width = `${pct}%`;
    if (progressLabel) progressLabel.textContent = `Отправка ${i + 1}/${toSend.length} (${p.nickname || p.userId})...`;

    const playerRow = document.getElementById(`radar-player-${p.userId}`);
    const btn = playerRow?.querySelector(".btn-add-friend");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Отправка...";
    }

    try {
      const res = await apiFetch("/actions/friendship/send", {
        method: "POST",
        body: JSON.stringify({ toUserId: Number(p.userId), nickname: p.nickname, source: "radar_batch" }),
      });

      if (res.success) {
        sentCount++;
        p.friendStatus = "sent";
        if (btn) {
          btn.className = "btn btn-sm btn-friend-sent";
          btn.textContent = "✓ Отправлено";
        }
      } else {
        failedCount++;
        if (btn) {
          btn.disabled = false;
          btn.textContent = "+ В друзья";
        }
        if (res.message && (res.message.includes("лимит") || res.message.includes("limit"))) {
          showToast("Достигнут игровой лимит друзей!", "warning");
          break;
        }
      }
    } catch (err) {
      failedCount++;
      if (btn) {
        btn.disabled = false;
        btn.textContent = "+ В друзья";
      }
      if (err.message && err.message.includes("429")) {
        showToast("Rate limit игрового сервера. Остановка.", "warning");
        break;
      }
    }

    if (i < toSend.length - 1 && !stopBatchRequested) {
      const delay = 1500 + Math.random() * 1000;
      await new Promise(r => setTimeout(r, delay));
    }
  }

  if (progressFill) progressFill.style.width = "100%";
  if (progressLabel) progressLabel.textContent = `Готово! Отправлено: ${sentCount}, Ошибок: ${failedCount}`;

  showToast(`Пакетная отправка завершена: отправлено ${sentCount} заявок`, sentCount > 0 ? "success" : "info");

  batchInProgress = false;
  if (batchBtn) batchBtn.style.display = "inline-flex";
  if (stopBtn) stopBtn.style.display = "none";
  setTimeout(() => {
    if (!batchInProgress && progressBox) progressBox.style.display = "none";
  }, 4000);

  await loadSafetyStatus();
}

// --- Subview 4: Импорт текста рейда ---
async function parseRaidText() {
  const input = document.getElementById("import-raid-text");
  const container = document.getElementById("import-results-container");
  const btn = document.getElementById("btn-parse-raid-text");
  if (!input || !container) return;

  const text = (input.value || "").trim();
  if (!text) {
    showToast("Вставьте текст поста с рейдом", "warning");
    return;
  }

  btn.disabled = true;
  btn.textContent = "🔍 Распознавание...";

  try {
    const res = await apiFetch("/raids/parse-text", {
      method: "POST",
      body: JSON.stringify({ text: text }),
    });

    const parsed = res.result || {};
    const participants = parsed.participants || [];

    if (participants.length === 0) {
      container.style.display = "block";
      container.innerHTML = '<div class="card" style="padding: 16px; text-align: center; color: var(--muted-foreground); font-size: 12px;">Не удалось распознать участников или ID игроков из текста</div>';
      return;
    }

    container.style.display = "block";
    let partHtml = "";
    participants.forEach(p => {
      let actionBtn = "";
      if (p.friendStatus === "friend") {
        actionBtn = '<button class="btn btn-sm btn-friend-added" disabled>✓ В друзьях</button>';
      } else if (p.friendStatus === "sent") {
        actionBtn = '<button class="btn btn-sm btn-friend-sent" disabled>✓ Заявка</button>';
      } else {
        actionBtn = `<button class="btn btn-primary btn-sm btn-add-friend" data-user-id="${p.userId}" data-nickname="${p.nickname || ''}">+ В друзья</button>`;
      }

      const dmgStr = p.declaredDamageText || (p.claimedDamage ? formatNum(p.claimedDamage) : (p.declaredDamage ? formatNum(p.declaredDamage) : "-"));

      partHtml += `
        <div class="raid-participant-item">
          <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
            <div style="font-size: 12px; font-weight: 600; color: #fff;">${p.nickname || 'Участник'}</div>
            <div style="font-size: 10px; color: var(--muted-foreground); font-family: monospace;">${p.userId}</div>
            <div style="font-size: 11px; color: #fbbf24; font-weight: 700;">💥 ${dmgStr}</div>
          </div>
          <div>${actionBtn}</div>
        </div>
      `;
    });

    container.innerHTML = `
      <div class="card" style="padding: 12px;">
        <div class="card-header-row" style="margin-bottom: 8px;">
          <div>
            <div class="card-title">${parsed.title || "Распознанный рейд"}</div>
            <div class="card-subtitle">Распознано участников: ${participants.length}</div>
          </div>
          <button id="btn-import-add-all" class="btn btn-primary btn-sm">➕ Добавить всех подходящих</button>
        </div>
        <div class="raid-participants-list">
          ${partHtml}
        </div>
      </div>
    `;

    bindFriendshipButtons(container);

    // Bind batch add for import
    document.getElementById("btn-import-add-all")?.addEventListener("click", async () => {
      const candidates = participants.filter(p => p.friendStatus !== "friend" && p.friendStatus !== "sent");
      if (candidates.length === 0) {
        showToast("Все участники уже добавлены или в друзьях", "info");
        return;
      }
      const uids = candidates.map(c => Number(c.userId));
      showToast(`Отправка заявок (${uids.length} чел)...`, "info");
      try {
        const batchRes = await apiFetch("/actions/friendship/send-batch", {
          method: "POST",
          body: JSON.stringify({ userIds: uids, maxCount: 15, source: "import" }),
        });
        showToast(`Отправлено: ${batchRes.sentCount}, пропущено: ${batchRes.skippedCount}`, "success");
        candidates.forEach(c => {
          c.friendStatus = "sent";
        });
        container.querySelectorAll(".btn-add-friend").forEach(b => {
          b.className = "btn btn-sm btn-friend-sent";
          b.textContent = "✓ Заявка";
        });
        await loadSafetyStatus();
      } catch (err) {
        showToast(`Ошибка пакетной отправки: ${err.message}`, "error");
      }
    });

  } catch (err) {
    showToast(`Ошибка парсинга: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "🔍 Распознавать участников";
  }
}

// --- Subview 4: Импорт текста рейда ---
async function parseRaidText() {
  const input = document.getElementById("import-raid-text");
  const container = document.getElementById("import-results-container");
  const btn = document.getElementById("btn-parse-raid-text");
  if (!input || !container) return;

  const text = (input.value || "").trim();
  if (!text) {
    showToast("Вставьте текст поста с рейдом", "warning");
    return;
  }

  btn.disabled = true;
  btn.textContent = "🔍 Распознавание...";

  try {
    const res = await apiFetch("/raids/parse-text", {
      method: "POST",
      body: JSON.stringify({ text: text }),
    });

    const parsed = res.result || {};
    const participants = parsed.participants || [];

    if (participants.length === 0) {
      container.style.display = "block";
      container.innerHTML = '<div class="card" style="padding: 16px; text-align: center; color: var(--muted-foreground); font-size: 12px;">Не удалось распознать участников или ID игроков из текста</div>';
      return;
    }

    container.style.display = "block";
    let partHtml = "";
    participants.forEach(p => {
      let actionBtn = "";
      if (p.friendStatus === "friend") {
        actionBtn = '<button class="btn btn-sm btn-friend-added" disabled>✓ В друзьях</button>';
      } else if (p.friendStatus === "sent") {
        actionBtn = '<button class="btn btn-sm btn-friend-sent" disabled>✓ Заявка</button>';
      } else {
        actionBtn = `<button class="btn btn-primary btn-sm btn-add-friend" data-user-id="${p.userId}" data-nickname="${p.nickname || ''}">+ В друзья</button>`;
      }

      const dmgStr = p.declaredDamageText || (p.claimedDamage ? formatNum(p.claimedDamage) : (p.declaredDamage ? formatNum(p.declaredDamage) : "-"));

      partHtml += `
        <div class="raid-participant-item">
          <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
            <div style="font-size: 12px; font-weight: 600; color: #fff;">${p.nickname || 'Участник'}</div>
            <div style="font-size: 10px; color: var(--muted-foreground); font-family: monospace;">${p.userId}</div>
            <div style="font-size: 11px; color: #fbbf24; font-weight: 700;">💥 ${dmgStr}</div>
          </div>
          <div>${actionBtn}</div>
        </div>
      `;
    });

    container.innerHTML = `
      <div class="card" style="padding: 12px;">
        <div class="card-header-row" style="margin-bottom: 8px;">
          <div>
            <div class="card-title">${parsed.title || "Распознанный рейд"}</div>
            <div class="card-subtitle">Распознано участников: ${participants.length}</div>
          </div>
          <button id="btn-import-add-all" class="btn btn-primary btn-sm">➕ Добавить всех подходящих</button>
        </div>
        <div class="raid-participants-list">
          ${partHtml}
        </div>
      </div>
    `;

    bindFriendshipButtons(container);

    // Bind batch add for import
    document.getElementById("btn-import-add-all")?.addEventListener("click", async () => {
      const candidates = participants.filter(p => p.friendStatus !== "friend" && p.friendStatus !== "sent");
      if (candidates.length === 0) {
        showToast("Все участники уже добавлены или в друзьях", "info");
        return;
      }
      const uids = candidates.map(c => Number(c.userId));
      showToast(`Отправка заявок (${uids.length} чел)...`, "info");
      try {
        const batchRes = await apiFetch("/actions/friendship/send-batch", {
          method: "POST",
          body: JSON.stringify({ userIds: uids, maxCount: 15, source: "import" }),
        });
        showToast(`Отправлено: ${batchRes.sentCount}, пропущено: ${batchRes.skippedCount}`, "success");
        // Update statuses
        candidates.forEach(c => {
          c.friendStatus = "sent";
        });
        container.querySelectorAll(".btn-add-friend").forEach(b => {
          b.className = "btn btn-sm btn-friend-sent";
          b.textContent = "✓ Заявка";
        });
      } catch (err) {
        showToast(`Ошибка пакетной отправки: ${err.message}`, "error");
      }
    });

  } catch (err) {
    showToast(`Ошибка парсинга: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "🔍 Распознать участников";
  }
}

if (typeof navigator !== "undefined" && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    try {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    } catch (e) {}
  });
}
