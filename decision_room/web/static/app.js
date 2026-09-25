"use strict";
const app = document.querySelector("#app");
const paths = {
  home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  file: '<path d="M14 2H5a1 1 0 0 0-1 1v18a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  chat: '<path d="M21 11a8 8 0 0 1-8 8H5l-3 3V11a9 9 0 0 1 19 0z"/><path d="M7 10h10M7 14h6"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  shield:
    '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9 8a3 3 0 0 1 6 0c0 3-3 2-3 5M12 16v1"/>',
  back: '<path d="M19 12H5m5-5-5 5 5 5"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
  spark:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7"/>',
};
const icon = (name, cls = "") =>
  `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const store = {
  get(key, fallback = {}) {
    try {
      return JSON.parse(localStorage.getItem(key)) ?? fallback;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {}
  },
  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch {}
  },
};
const state = {
  analyses: [],
  configured: true,
  filter: "all",
  search: "",
  file: null,
  draft: {},
  business: null,
  memory: {},
  dashboard: null,
  selectedReport: null,
  chats: [],
  deletedChats: [],
  sidebarWidth: store.get("dr-sidebar-width", null),
  scrollToTurn: null,
  datasets: { items: [], more: false },
  launching: false,
  businesses: [],
  draftBusiness: null,
  uploading: false,
  poll: null,
  chatFollowController: null,
  signature: "",
  generation: 0,
};
const statuses = {
  queued: ["En cola", "quiet"],
  running: ["En curso", "live"],
  waiting: ["Necesita tu respuesta", "amber"],
  completed: ["Informe disponible", "green"],
  failed: ["Interrumpido", "red"],
  blocked: ["Necesita atención", "amber"],
  outdated: ["Contexto cambiado · revisar respuesta", "amber"],
  historical: ["Versión anterior", "quiet"],
  withdrawn: ["Informe retirado", "amber"],
  ready: ["Respuesta revisada · pendiente de guardar informe", "green"],
};
const phases = {
  upload: "Preparando tu archivo",
  planning: "Entendiendo tu negocio",
  research: "Analizando los datos",
  review: "Comprobando los hallazgos",
  done: "Informe disponible",
};
const fmtDate = (value) =>
  new Date(value).toLocaleDateString("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
const size = (value) =>
  value < 1024
    ? `${value} B`
    : value < 1024 ** 2
      ? `${(value / 1024).toFixed(1)} KB`
      : `${(value / 1024 ** 2).toFixed(1)} MB`;
const badge = (status) =>
  `<span class="badge ${statuses[status]?.[1] || "quiet"}"><i></i>${statuses[status]?.[0] || esc(status)}</span>`;
function toast(text) {
  const el = document.querySelector("#toast");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(state.toast);
  state.toast = setTimeout(() => el.classList.remove("show"), 5000);
}
async function api(path, { method = "GET", body } = {}) {
  const headers = { "X-Decision-Room": "1" };
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body,
      credentials: "same-origin",
    });
  } catch {
    throw new Error(
      "No hay conexión con el servidor local. Tu progreso guardado se conserva. Vuelve a intentarlo.",
    );
  }
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(
      data.error || "No hemos podido completar la petición.",
    );
    error.status = response.status;
    throw error;
  }
  return data;
}
function shell(content, active = "home", crumb = "Vista general") {
  const sidebarWidth = Math.max(216, Math.min(Number(state.sidebarWidth) || (innerWidth <= 1180 ? 216 : 250), innerWidth * .4, innerWidth - 420));
  document.documentElement.style.setProperty("--sidebar-size", `${sidebarWidth}px`);
  const hasQuestionComposer = state.business && !location.hash.startsWith("#chat/");
  const centeredQuestion = location.hash === "#ask";
  app.innerHTML = `<aside class="sidebar"><a class="brand" href="#home" aria-label="Decision Room, inicio"><span class="brand-mark">d<span>r</span></span><span>decision<span class="brand-light">room</span><small>UN ESPACIO PARA DECIDIR</small></span></a>
    <div class="workspace-label"><span class="workspace-avatar">M</span><span>${esc(state.business?.name || "Mi espacio")}<small>Espacio de trabajo local</small></span><span class="local-dot"></span></div>
    <p class="nav-label">TU ESPACIO</p><nav aria-label="Principal">${[
      ["home", "home", "Inicio"],
      ["reports", "grid", "Informes"],
      ["my-business", "file", "Mi negocio"],
    ]
      .map(
        ([route, i, label]) =>
          `<a href="#${route}" class="nav-link ${active === route ? "active" : ""}" ${active === route ? 'aria-current="page"' : ""} title="${label}">${icon(i)}<span>${label}</span></a>`,
      )
      .join("")}<a href="#chats" class="nav-link mobile-chats" title="Conversaciones" aria-label="Conversaciones">${icon("chat")}</a></nav>
    <a href="#ask" class="button sidebar-create">${icon("plus")} Nuevo chat</a>
    <div class="sidebar-history"><p class="nav-label">CHATS</p>${state.chats.slice(0, 6).map((c) => `<div class="history-row"><a class="history-link" href="#chat/${esc(c.id)}" title="${esc(c.title)}">${icon("chat")}<span>${esc(c.title)}</span></a><button class="chat-delete" type="button" data-delete-chat="${esc(c.id)}" aria-label="Eliminar chat ${esc(c.title)}" title="Eliminar chat">${icon("close")}</button></div>`).join("") || '<p class="history-empty">Aún no hay conversaciones.</p>'}<a class="history-all" href="#chats">Ver conversaciones ${icon("arrow")}</a><p class="nav-label">ANÁLISIS RECIENTES</p>${state.analyses.slice(0, 6).map((a) => `<a class="history-link" href="#analysis/${esc(a.id)}" title="${esc(a.title)}">${icon("grid")}<span>${esc(a.title)}</span></a>`).join("") || '<p class="history-empty">Aún no hay análisis.</p>'}<a class="history-all" href="#analyses">Ver todos los análisis ${icon("arrow")}</a></div>
    <div class="sidebar-bottom"><a class="nav-link" href="#how">${icon("help")}<span>Cómo funciona</span></a><div class="profile"><span>ME</span><div>Mi espacio personal<small>Versión de pruebas</small></div></div></div><div class="sidebar-resize" role="separator" tabindex="0" aria-orientation="vertical" aria-label="Cambiar anchura del panel lateral" aria-valuemin="216" aria-valuemax="${Math.floor(Math.min(innerWidth * .4, innerWidth - 420))}" aria-valuenow="${Math.round(sidebarWidth)}"></div></aside>
    <div class="workspace"><header class="topbar"><span class="breadcrumb">Mi espacio <span>/</span> <b>${esc(crumb)}</b></span><span class="environment"><i></i> Entorno local <span class="beta">BETA</span></span></header><main id="main" class="${centeredQuestion ? "new-chat-page" : ""}" tabindex="-1"><div id="memory-status" aria-live="polite"></div>${content}${hasQuestionComposer && !centeredQuestion ? questionComposer() : ""}</main><footer class="page-footer"><span>Decision Room</span><span>De los datos a decisiones con contexto.</span></footer></div>`;
  renderMemory();
  bindSidebarResize();
  if (hasQuestionComposer) bindQuestionComposer();
}
function bindSidebarResize() {
  const handle = document.querySelector(".sidebar-resize");
  if (!handle) return;
  const setWidth = (value) => {
    const width = Math.round(Math.max(216, Math.min(value, innerWidth * .4, innerWidth - 420)));
    state.sidebarWidth = width;
    document.documentElement.style.setProperty("--sidebar-size", `${width}px`);
    handle.setAttribute("aria-valuenow", String(width));
    store.set("dr-sidebar-width", width);
  };
  handle.addEventListener("pointerdown", (event) => {
    if (innerWidth <= 760) return;
    handle.setPointerCapture(event.pointerId);
    handle.classList.add("dragging");
    event.preventDefault();
  });
  handle.addEventListener("pointermove", (event) => {
    if (handle.hasPointerCapture(event.pointerId)) setWidth(event.clientX);
  });
  for (const type of ["pointerup", "pointercancel"]) handle.addEventListener(type, () => handle.classList.remove("dragging"));
  handle.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    setWidth(event.key === "Home" ? 216 : event.key === "End" ? innerWidth * .4 :
      (state.sidebarWidth || 250) + (event.key === "ArrowRight" ? 24 : -24));
  });
}
function scrollToChatTurn(id) {
  const turn = document.querySelector(`[data-chat-turn="${id}"]`);
  if (!turn) return;
  const target = turn.querySelector(".chat-answer") || turn.querySelector(".chat-owner") || turn;
  const composer = document.querySelector(".chat-composer");
  const visibleBottom = (composer?.getBoundingClientRect().top ?? innerHeight) - 18;
  const visibleTop = Math.max(0, document.querySelector(".topbar")?.getBoundingClientRect().bottom ?? 0) + 18;
  const rect = target.getBoundingClientRect();
  if (rect.top >= visibleTop && rect.bottom <= visibleBottom) return;
  const available = visibleBottom - visibleTop;
  const offset = rect.height > available || rect.top < visibleTop
    ? rect.top - visibleTop
    : rect.bottom - visibleBottom;
  scrollTo({top: Math.max(0, scrollY + offset), behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
}
async function changeChatVisibility(id, action) {
  const chat = [...state.chats, ...state.deletedChats].find(c => String(c.id) === id);
  if (!chat || !state.business) return false;
  if (action === "delete" && !confirm(`¿Eliminar «${chat.title}»? Podrás recuperarlo en Conversaciones. Los datos guardados en Mi negocio y los informes se conservan.`)) return false;
  await api(`/api/chats/${encodeURIComponent(id)}/${action}`, {method: "POST", body: {business_id: state.business.id}});
  if (action === "delete" && location.hash === `#chat/${id}`) location.hash = "#chats";
  else await route();
  return true;
}
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-chat],[data-restore-chat]");
  if (!button) return;
  event.preventDefault();
  button.disabled = true;
  try {
    const changed = await changeChatVisibility(button.dataset.deleteChat || button.dataset.restoreChat,
      button.dataset.deleteChat ? "delete" : "restore");
    if (!changed) button.disabled = false;
  } catch (error) { toast(error.message); button.disabled = false; }
});
const scrollIndicatorTimers = new WeakMap();
document.addEventListener("scroll", (event) => {
  const surface = event.target === document ? document.documentElement : event.target;
  if (!surface?.classList) return;
  surface.classList.add("is-scrolling");
  clearTimeout(scrollIndicatorTimers.get(surface));
  scrollIndicatorTimers.set(surface, setTimeout(() => surface.classList.remove("is-scrolling"), 1000));
}, true);
function renderMemory() {
  const box = document.querySelector("#memory-status");
  if (!box || !state.business) return;
  const m = state.memory || {};
  const failed = m.failed || m.uncertain;
  const message = failed
    ? "Guardé tus cambios, pero aún no he podido incorporarlos a la memoria."
    : m.pending ? "Guardé tus cambios. Estoy incorporándolos a la memoria…"
    : m.needs_review ? `Hay ${m.needs_review} ${m.needs_review === 1 ? "dato" : "datos"} de tu negocio por confirmar o aclarar.`
    : "";
  box.innerHTML = message ? `<div class="notice memory-notice"><p>${esc(message)} ${m.needs_review ? '<a href="#my-business">Revisar en Mi negocio</a>' : ""}</p>${m.uncertain ? '<p>Se interrumpió una petición al modelo. Reintentar puede repetir esa petición.</p>' : ""}${failed ? '<button type="button" class="button secondary" id="retry-memory">Reintentar memoria</button>' : ""}<span id="memory-error"></span></div>` : "";
  const retry = document.querySelector("#retry-memory");
  if (retry) retry.onclick = async () => {
    retry.disabled = true;
    try {
      const response = await api("/api/memory/retry", {method: "POST", body: {business_id: state.business.id}});
      state.memory = response.memory;
      renderMemory();
    } catch (error) {
      if (retry.isConnected) {
        document.querySelector("#memory-error").textContent = error.message;
        retry.disabled = false;
      }
    }
  };
}
function errorBox(message) {
  return `<div class="error-message" role="alert">${esc(message)}</div>`;
}
function login(error = "") {
  app.innerHTML = `<main class="login"><a class="brand" href="#"><span class="brand-mark">d<span>r</span></span><span>decision<span class="brand-light">room</span></span></a><section class="card"><p class="eyebrow">TU ESPACIO PRIVADO</p><h1>Bienvenido a<br><em>Decision Room.</em></h1><p>Un lugar para entender los datos de tu negocio y decidir con más claridad.</p><form id="login-form"><label for="access">Clave de acceso local</label><input id="access" name="access" type="password" autocomplete="current-password" required><div id="login-error">${error ? errorBox(error) : ""}</div><button class="button primary" type="submit">Entrar a mi espacio ${icon("arrow")}</button></form><details><summary>¿Dónde está mi clave?</summary><p>Abre la aplicación con <code>python -m decision_room.web --open</code> desde el entorno del proyecto. También puedes usar la clave del archivo privado <code>.web-access-key</code> en el almacenamiento local.</p></details></section><p class="subtle">${icon("shield")} Acceso restringido · Solo en este equipo</p></main>`;
  document.querySelector("#login-form").onsubmit = async (event) => {
    event.preventDefault();
    try {
      await api("/api/login", {
        method: "POST",
        body: { token: document.querySelector("#access").value },
      });
      location.hash = "#home";
      await route();
    } catch (e) {
      document.querySelector("#login-error").innerHTML = errorBox(e.message);
    }
  };
}
function illustration() {
  return `<div class="hero-art" aria-hidden="true"><span class="art-orbit orbit-one"></span><span class="art-orbit orbit-two"></span><span class="art-star">✳</span><div class="art-source"><span class="art-icon">${icon("file")}</span><div>Tu negocio<small>Datos + contexto</small></div><span class="art-check">${icon("check")}</span></div><div class="art-connector"></div><div class="art-report"><span class="art-report-label">UNA VISIÓN MÁS CLARA ${icon("spark")}</span><div class="art-chart"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><div class="art-lines"><i></i><i></i></div><span class="art-evidence">${icon("check")} Hallazgos con evidencia</span></div></div>`;
}
const reportLink = (id, claim) => `/api/jobs/${encodeURIComponent(id)}/report${claim ? `#finding-${encodeURIComponent(claim)}` : ""}`;
function dashboardChart(chart, reportId, evidenceLink = null) {
  const values = chart.points.map((point) => Number(point.value));
  const max = Math.max(1, ...values.map((value) => Math.abs(value)));
  const canPlot = values.every(Number.isFinite) && values.length > 1;
  let plot = "";
  if (canPlot && chart.kind === "line") {
    const first = Date.parse(chart.points[0].label);
    const last = Date.parse(chart.points.at(-1).label);
    const days = chart.points.map((point) => Date.parse(point.label));
    const min = Math.min(0, ...values);
    const high = Math.max(0, ...values);
    const x = (i) => 24 + 552 * (days[i] - first) / (last - first || 1);
    const y = (i) => 174 - 138 * (values[i] - min) / (high - min || 1);
    const lines = values.slice(1).map((_, i) => days[i + 1] - days[i] === 86400000
      ? `<line x1="${x(i)}" y1="${y(i)}" x2="${x(i + 1)}" y2="${y(i + 1)}"/>` : "").join("");
    plot = `<svg class="dash-trend" viewBox="0 0 600 200" role="img" aria-label="${esc(chart.title)}"><path d="M24 174H576" class="dash-axis"/>${lines}${values.map((_, i) => `<circle cx="${x(i)}" cy="${y(i)}" r="3.5"><title>${esc(chart.points[i].label)}: ${esc(chart.points[i].formatted)} ${esc(chart.unit)}</title></circle>`).join("")}</svg><div class="dash-chart-ends"><span>${esc(chart.points[0].label)}</span><span>${esc(chart.points.at(-1).label)}</span></div>`;
  } else if (canPlot && chart.kind === "bar") {
    const diverging = values.some((value) => value < 0);
    plot = `<div class="dash-bars">${chart.points.slice(0, 8).map((point, i) => {
      const width = Math.max(2, Math.abs(values[i]) / max * (diverging ? 50 : 100));
      const left = diverging ? (values[i] < 0 ? 50 - width : 50) : 0;
      return `<div class="dash-bar"><span title="${esc(point.label)}">${esc(point.label)}</span><span class="dash-bar-track ${diverging ? "diverging" : ""}"><i class="${values[i] < 0 ? "negative" : ""}" style="left:${left}%;width:${width}%"></i></span><strong>${esc(point.formatted)}</strong></div>`;
    }).join("")}</div>`;
  }
  return `<section class="dashboard-chart"><div class="dash-card-top"><span>${icon("grid")}</span>${reportId || evidenceLink ? `<a href="${reportId ? reportLink(reportId, chart.claim_key) : location.hash}" ${evidenceLink ? `data-evidence-anchor="${esc(evidenceLink.slice(1))}"` : ""} ${reportId ? 'target="_blank" rel="noopener"' : ""} aria-label="Ver evidencia de ${esc(chart.title)}">Ver evidencia ${icon("arrow")}</a>` : ""}</div><h3>${esc(chart.title)}</h3><p class="dash-chart-unit">${esc(chart.unit)}</p>${plot}<p class="dash-chart-caption">${esc(chart.caption)}</p><details><summary>Ver valores</summary><div class="dash-values">${chart.points.map((point) => `<div><span>${esc(point.label)}</span><strong>${esc(point.formatted)}</strong></div>`).join("")}</div></details></section>`;
}
function dashboardDraftKey() {
  return "dr-home-prompt-" + state.business.id;
}
function shortChatTitle(text) {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= 64) return clean;
  const prefix = clean.slice(0, 61);
  return prefix.slice(0, prefix.lastIndexOf(" ") > 30 ? prefix.lastIndexOf(" ") : 61) + "…";
}
function questionContextKey() { return "dr-question-context-" + state.business.id; }
async function launchDashboardChat(text, context = {}) {
  if (state.launching) return;
  if (!state.configured) throw new Error("Configura el modelo antes de enviar mensajes.");
  const businessId = state.business.id, generation = state.generation;
  const cacheKey = "dr-home-send-" + businessId;
  const payload = { business_id: businessId, title: shortChatTitle(text), analysis_id: context.analysis_id || "" };
  const previous = store.get(cacheKey, null);
  const pending = previous?.text === text && JSON.stringify(previous.context || {}) === JSON.stringify(context) ? previous : {
    text, context, payload, key: crypto.randomUUID(), messageKey: crypto.randomUUID()
  };
  store.set(cacheKey, pending);
  state.launching = true;
  try {
    const chat = pending.chatId ? { id: pending.chatId } : await api("/api/chats", {
      method: "POST", body: { ...pending.payload, request_key: pending.key }
    });
    pending.chatId = chat.id;
    store.set(cacheKey, pending);
    const draftKey = "dr-chat-draft-" + chat.id;
    store.set(draftKey, { text, key: pending.messageKey, finding_reference: context.finding_reference });
    const sent = await api("/api/chats/" + chat.id + "/messages", {
      method: "POST", body: { business_id: businessId, text, request_key: pending.messageKey, ...(context.finding_reference ? {finding_reference: context.finding_reference} : {}) }
    });
    if (store.get(draftKey, {}).key === pending.messageKey) store.remove(draftKey);
    store.remove(cacheKey);
    const homeKey = "dr-home-prompt-" + businessId;
    if (store.get(homeKey, "") === text) {
      store.remove(homeKey);
      if (JSON.stringify(store.get("dr-question-context-" + businessId, {})) === JSON.stringify(context)) store.remove("dr-question-context-" + businessId);
    }
    if (generation === state.generation) { state.scrollToTurn = sent.id; location.hash = "#chat/" + chat.id; }
    return chat;
  } finally { state.launching = false; }
}
function dashboardSuggestions() {
  return ["¿Qué sabes de mi negocio?", ...(state.datasets.items.length
    ? ["¿Qué datos tenemos disponibles para analizar?"] : [])];
}
function questionComposer() {
  const context = store.get(questionContextKey(), {});
  const draft = store.get(dashboardDraftKey(), "");
  return `<section class="dashboard-compose ${location.hash === "#ask" ? "new-chat-compose" : ""}" aria-label="Haz una pregunta"><form id="dashboard-question"><div class="composer-card">${context.label ? `<p class="question-context">${esc(context.label)} <button type="button" id="clear-question-context" class="text-button">Quitar selección</button></p>` : ""}<div class="composer-input-row"><label for="dashboard-prompt" class="sr-only">Escribe tu pregunta</label><textarea id="dashboard-prompt" maxlength="6000" rows="1" required placeholder="Pregunta lo que quieras…">${esc(draft)}</textarea><button class="button primary" type="submit" aria-label="Enviar pregunta">${icon("arrow")}</button></div><p id="dashboard-error" role="alert"></p></div><div class="chat-suggestions" id="dashboard-suggestions" ${draft.trim() ? "hidden" : ""}>${dashboardSuggestions().map(q => `<button type="button" data-home-suggestion="${esc(q)}">${esc(q)}</button>`).join("")}</div></form></section>`;
}
function resizeComposer(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  textarea.style.overflowY = textarea.scrollHeight > 180 ? "auto" : "hidden";
}
function bindComposerKeys(textarea, form) {
  textarea.addEventListener("keydown", event => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    if (textarea.value.trim()) form.requestSubmit();
  });
}
function bindQuestionComposer() {
  const prompt = document.querySelector("#dashboard-prompt");
  if (!prompt) return;
  const form = document.querySelector("#dashboard-question");
  const suggestions = document.querySelector("#dashboard-suggestions");
  const sync = () => {
    store.set(dashboardDraftKey(), prompt.value);
    suggestions.hidden = !!prompt.value.trim();
    resizeComposer(prompt);
  };
  prompt.addEventListener("input", sync);
  bindComposerKeys(prompt, form);
  resizeComposer(prompt);
  document.querySelector("#clear-question-context")?.addEventListener("click", () => {
    store.remove(questionContextKey());
    document.querySelector(".question-context")?.remove();
    prompt.focus();
  });
  document.querySelectorAll("[data-home-suggestion]").forEach(button => button.onclick = () => {
    prompt.value = button.dataset.homeSuggestion;
    prompt.dispatchEvent(new Event("input")); prompt.focus();
  });
  form.onsubmit = async event => {
    event.preventDefault();
    const text = prompt.value.trim();
    if (state.launching || !text) return;
    const button = event.currentTarget.querySelector("button[type=submit]"), error = document.querySelector("#dashboard-error");
    store.set(dashboardDraftKey(), text); button.disabled = true; error.textContent = "";
    try { await launchDashboardChat(text, store.get(questionContextKey(), {})); }
    catch (e) { error.textContent = e.message; }
    finally { button.disabled = false; }
  };
}
function activityMarkup(items) {
  return items.map(item => `<a class="dashboard-activity" href="${esc(item.href)}">${icon(["running", "queued"].includes(item.status) ? "clock" : "chat")}<span><strong>${esc(shortChatTitle(item.title))}</strong><small>${esc(statuses[item.status]?.[0] || item.status)}</small></span>${icon("arrow")}</a>`).join("");
}
function dashboardHome() {
  const data = state.dashboard || { report: null, reports: [] }, report = data.report;
  const activity = data.activity || [];
  const running = activity.some(a => ["queued", "running"].includes(a.status));
  const withdrawn = activity.some(a => a.status === "withdrawn");
  const empty = !state.business ? ["Empecemos por tu negocio.", "Guarda una breve descripción para empezar.", "#business-new", "Empezar"]
    : running ? ["Estamos preparando tu respuesta.", "Puedes seguir el progreso en tu conversación o análisis.", activity.find(a => ["queued", "running"].includes(a.status)).href, "Ver progreso"]
    : withdrawn ? ["El informe anterior se ha retirado.", "Cambió su contexto o evidencia. Elige los datos vigentes para hacer una nueva pregunta.", "#files", "Revisar datos"]
    : ["Todavía no hay un informe disponible.", "Pregunta con tus datos o guarda como informe una respuesta revisada del chat.", "#ask", "Hacer una pregunta"];
  const selector = report && data.reports.length > 1 ? `<label class="dashboard-select">Informe seleccionado<select id="dashboard-report">${data.reports.map(item => `<option value="${esc(item.id)}" ${item.id === data.selected_id ? "selected" : ""}>${esc(item.title)} · ${fmtDate(item.created_at)}</option>`).join("")}</select></label>` : "";
  const findings = report ? `<section class="dashboard-findings"><div class="dashboard-section-head"><h2>Hallazgos revisados</h2><a href="${reportLink(data.selected_id)}" target="_blank" rel="noopener">Abrir informe ${icon("arrow")}</a></div><p class="dashboard-summary">${esc(report.summary)}</p><div class="finding-grid">${report.claims.map((claim,index) => `<article class="finding-tile"><span>0${index+1} · HALLAZGO</span><h3>${esc(claim.title)}</h3><p>${esc(claim.statement)}</p><a href="${reportLink(data.selected_id,claim.key)}" target="_blank" rel="noopener">Ver detalle y evidencia ${icon("arrow")}</a><button type="button" class="button secondary" data-ask-finding="${esc(claim.key)}">Preguntar sobre este hallazgo</button></article>`).join("")}</div></section>` : `<section class="dashboard-empty"><div><h2>${empty[0]}</h2><p>${empty[1]}</p></div><a class="button primary" href="${empty[2]}">${empty[3]} ${icon("arrow")}</a></section>`;
  shell(`<div class="dashboard-page"><div class="dashboard-intro"><div><p class="eyebrow">${esc(state.business?.name || "TU ESPACIO")}</p><h1>Tu negocio, <em>con claridad.</em></h1></div>${state.business ? '<button class="button secondary" id="focus-question">Hacer una pregunta</button>' : ""}</div>${!state.configured ? '<p class="notice">El modelo aún no está configurado. Puedes preparar tu pregunta.</p>' : ""}${activity.length ? `<details class="daily-activity" ${!report ? "open" : ""}><summary>Actividad y pendientes · ${activity.length}</summary>${activityMarkup(activity)}</details>` : ""}${report ? `<div class="dashboard-report-meta"><div><span class="meta-mark">${icon("check")}</span><div><strong>${esc(report.title)}</strong><small>${esc(report.scope.period)} · ${data.data_version ? `Versión ${esc(data.data_version.version)} · ` : ""}${fmtDate(data.created_at)}</small></div></div>${selector}</div>${data.data_version?.superseded_by ? '<p class="notice">Este informe usa una versión anterior. Los datos nuevos aún no se han recalculado. <a href="#files">Ver datos</a></p>' : ""}` : ""}${findings}${report?.highlights.length ? `<section class="dashboard-metrics" aria-label="Cifras clave">${report.highlights.map(item => `<a class="metric-tile" href="${reportLink(data.selected_id,item.claim_key)}" target="_blank" rel="noopener"><span>${esc(item.label)}</span><strong>${esc(item.value)}</strong><small>${esc(item.unit)}</small></a>`).join("")}</section>` : ""}${report?.charts.length ? `<section class="dashboard-visuals"><h2>Gráficos del informe</h2><div class="dash-chart-grid">${report.charts.map(chart => dashboardChart(chart,data.selected_id)).join("")}</div></section>` : ""}${report ? `<div class="dashboard-coverage"><p><strong>Alcance de esta revisión</strong><br>${esc(report.scope.coverage)}</p></div>` : ""}</div>`, "home", "Inicio");
  document.querySelector("#focus-question")?.addEventListener("click", () => document.querySelector("#dashboard-prompt").focus());
  document.querySelectorAll("[data-ask-finding]").forEach(button => button.onclick = () => {
    const claim = report.claims.find(c => c.key === button.dataset.askFinding);
    store.set(questionContextKey(), {analysis_id: data.analysis_id, finding_reference: {report_id:data.report_id, report_version:data.report_version, claim_key:claim.key}, label:`Hallazgo: ${claim.title} · ${report.scope.period}`});
    if (!store.get(dashboardDraftKey(), "")) store.set(dashboardDraftKey(), `Explícame el hallazgo «${claim.title}».`);
    location.hash = "#ask";
  });
  document.querySelector("#dashboard-report")?.addEventListener("change", async event => {
    const generation = state.generation; state.selectedReport = event.target.value; event.target.disabled = true;
    try {
      const dashboard = await api("/api/dashboard?report=" + encodeURIComponent(state.selectedReport));
      if (generation !== state.generation) return;
      state.dashboard = dashboard; state.selectedReport = dashboard.selected_id; dashboardHome();
      document.querySelector("#dashboard-report")?.focus();
    } catch(error) { toast(error.message); event.target.disabled = false; }
  });
}
function reportState(item) {
  return item.presentation_status || (item.status === "completed" && item.data_version?.superseded_by ? "historical" : item.status);
}
function reportsView() {
  shell(`<div class="page-heading"><div><p class="eyebrow">TU BIBLIOTECA</p><h1>Informes y análisis</h1><p>Recupera una revisión o continúa un trabajo pendiente.</p></div><a class="button primary" href="#ask">${icon("plus")} Nuevo chat</a></div><div class="report-filters"><label>Buscar informes<input id="report-search" type="search" value="${esc(state.reportSearch || "")}" placeholder="Título o archivo"></label><label>Estado<select id="report-filter">${[["all","Todos"],["completed","Disponibles"],["historical","Versiones anteriores"],["pending","En curso o pendientes"],["withdrawn","Retirados"],["failed","Interrumpidos"]].map(([key,label]) => `<option value="${key}" ${state.reportFilter === key ? "selected" : ""}>${label}</option>`).join("")}</select></label></div><div class="reports-list" id="report-items"></div>`, "reports", "Informes");
  function render() {
    const query = (state.reportSearch || "").toLocaleLowerCase(), filter = state.reportFilter || "all";
    const items = state.analyses.filter(a => `${a.title} ${a.filename}`.toLocaleLowerCase().includes(query) && (filter === "all" || reportState(a) === filter || (filter === "pending" && ["running","queued","waiting","blocked"].includes(reportState(a)))));
    document.querySelector("#report-items").innerHTML = items.length ? items.map(a => `<a class="report-list-item" href="#analysis/${esc(a.id)}"><span class="report-list-icon">${icon(a.status === "completed" ? "grid" : "clock")}</span><span><strong>${esc(shortChatTitle(a.title))}</strong><small>${esc(a.filename)} · ${fmtDate(a.created_at)}${a.data_version ? ` · Versión ${a.data_version.version}` : ""}</small></span>${badge(reportState(a))}${icon("arrow")}</a>${a.conversation_id ? `<a class="text-button report-chat-link" href="#chat/${esc(a.conversation_id)}">Abrir conversación de este informe ${icon("chat")}</a>` : ""}`).join("") : state.analyses.length ? '<p class="empty">No hay informes que coincidan con estos filtros.</p>' : '<div class="dashboard-empty"><div><h2>Tu biblioteca está vacía.</h2><p>Guarda como informe una respuesta revisada del chat para encontrarla aquí.</p></div><a class="button primary" href="#ask">Hacer una pregunta</a><a href="#files">Añadir datos</a></div>';
  }
  document.querySelector("#report-search").oninput = event => {state.reportSearch=event.target.value;render();};
  document.querySelector("#report-filter").onchange = event => {state.reportFilter=event.target.value;render();};
  render();
}
async function myBusiness() { await dossierPage(); }
function home(compact = false) {
  const attention = state.analyses.filter((a) =>
    ["waiting", "failed", "blocked"].includes(a.status),
  ).length;
  const completed = state.analyses.filter(
    (a) => a.status === "completed",
  ).length;
  shell(
    `${compact ? `<div class="page-heading"><div><p class="eyebrow">TU ESPACIO DE TRABAJO</p><h1>Mis análisis<span class="title-dot">.</span></h1><p>Retoma una pregunta, sigue el progreso o vuelve a tus hallazgos.</p></div><a class="button primary" href="#new">${icon("plus")} Nuevo análisis</a></div>` : `<section class="hero"><div class="hero-copy"><p class="eyebrow"><span class="tiny-line"></span> MENOS HOJAS. MÁS PERSPECTIVA.</p><h1>Tus datos tienen<br>algo que <em>contarte.</em></h1><p>Comparte el contexto de tu negocio y tus datos.<br class="desktop-only"> Juntos encontraremos lo que merece tu atención.</p><a class="button primary" href="#new">Crear un análisis ${icon("arrow")}</a><span class="hero-caption">Empieza con un CSV. Nosotros hacemos las preguntas.</span></div>${illustration()}</section>`}
    ${!state.configured ? `<div class="notice">El modelo local aún no está configurado. Puedes preparar tu análisis y guardar el borrador.</div>` : ""}
    <section class="overview-stats" aria-label="Resumen del espacio"><div>${icon("grid")}<span><b>${state.analyses.length}</b> ${state.analyses.length === 1 ? "análisis creado" : "análisis creados"}</span></div><div>${icon("chat")}<span><b>${attention}</b> necesitan atención</span></div><div>${icon("check")}<span><b>${completed}</b> informes disponibles</span></div><span class="autosave">${icon("shield")} Tu progreso se conserva</span></section>
    <section class="analysis-section"><div class="section-heading"><div><p class="eyebrow">CONTINÚA DONDE LO DEJASTE</p><h2>Tus análisis</h2></div><label class="search">${icon("search")}<input type="search" id="search" placeholder="Buscar un análisis…" aria-label="Buscar análisis" value="${esc(state.search)}"></label></div><div class="filter-row" role="group" aria-label="Filtrar análisis">${[
      ["all", "Todos"],
      ["attention", "Necesitan atención"],
      ["completed", "Con informe"],
    ]
      .map(
        ([key, label]) =>
          `<button type="button" class="filter ${state.filter === key ? "selected" : ""}" data-filter="${key}" aria-pressed="${state.filter === key}">${label}</button>`,
      )
      .join("")}</div><div id="analysis-list"></div></section>
    ${!compact ? `<section class="journey"><div><span class="journey-number">01</span><h3>Cuéntanos tu negocio</h3><p>El contexto da sentido a las cifras.<br>Tú conoces el negocio; nosotros escuchamos.</p></div><div><span class="journey-number">02</span><h3>Resolvemos las dudas</h3><p>Solo las preguntas que necesitamos<br>para interpretar bien tus datos.</p></div><div><span class="journey-number">03</span><h3>Entiende lo que importa</h3><p>Hallazgos, gráficos y explicaciones.<br>Con la evidencia siempre a mano.</p></div></section>` : ""}`,
    compact ? "analyses" : "home",
    compact ? "Mis análisis" : "Vista general",
  );
  renderList();
  document.querySelector("#search").oninput = (e) => {
    state.search = e.target.value;
    renderList();
  };
  document.querySelectorAll("[data-filter]").forEach(
    (button) =>
      (button.onclick = () => {
        state.filter = button.dataset.filter;
        document.querySelectorAll("[data-filter]").forEach((b) => {
          b.classList.toggle("selected", b === button);
          b.setAttribute("aria-pressed", b === button);
        });
        renderList();
      }),
  );
}
function renderList() {
  const rows = state.analyses.filter(
    (a) =>
      (state.filter === "all" ||
        (state.filter === "completed"
          ? a.status === "completed"
          : ["waiting", "failed", "blocked"].includes(a.status))) &&
      `${a.title} ${a.business} ${a.filename}`
        .toLocaleLowerCase()
        .includes(state.search.toLocaleLowerCase()),
  );
  document.querySelector("#analysis-list").innerHTML = rows.length
    ? `<div class="list-labels"><span>ANÁLISIS / NEGOCIO</span><span>ESTADO</span><span>CREADO</span><span></span></div>${rows.map((a) => `<a class="analysis-row" href="#analysis/${esc(a.id)}"><span class="analysis-name"><span class="file-symbol">${icon("file")}</span><span><strong>${esc(a.title)}</strong><small>${esc(a.business)} <span>·</span> ${esc(a.filename)}</small></span></span>${badge(a.status)}<span class="row-date">${fmtDate(a.created_at)}</span><span class="row-arrow">${icon("arrow")}</span></a>`).join("")}`
    : state.analyses.length
      ? `<div class="empty small">${icon("search")}<h3>No hay análisis que coincidan</h3><p>Prueba con otra búsqueda o cambia el filtro.</p></div>`
      : `<div class="empty"><span class="empty-icon">${icon("spark")}</span><div><h3>Tu primera buena pregunta empieza aquí.</h3><p>Sube un archivo y descubre qué puedes aprender de tu negocio.</p></div><a class="button secondary" href="#new">Crear mi primer análisis ${icon("arrow")}</a></div>`;
}
function saveDraft() {
  store.set("dr-draft-" + state.business?.id, state.draft);
  state.requestKey = null;
}
function businessChooser() {
  shell(`<div class="page-heading"><div><h1>Elige tu negocio.</h1><p>Los negocios guardados conservan sus propios análisis y archivos.</p></div><a class="button primary" href="#business-new">Crear otro negocio</a></div>
    <section class="card form-card"><div id="business-error"></div>${state.businesses.length ? state.businesses.map(b => `<div class="review-context"><h2>${esc(b.name)}</h2><p>${b.analysis_count} análisis · ${fmtDate(b.created_at)} · ${esc(b.id.slice(0, 8))}</p><button class="button secondary" data-business="${esc(b.id)}">${b.id === state.business?.id ? "Abrir negocio activo" : "Continuar con este negocio"}</button></div>`).join("") : '<p>Todavía no has guardado un negocio.</p><a class="button primary" href="#business-new">Empezar</a>'}</section>`, "businesses", "Negocios guardados");
  document.querySelectorAll("[data-business]").forEach(button => {
    button.onclick = async () => {
      button.disabled = true;
      try {
        await api("/api/business/select", { method: "POST", body: { business_id: button.dataset.business } });
        location.hash = "#home";
      } catch (error) {
        document.querySelector("#business-error").innerHTML = errorBox(error.message);
        button.disabled = false;
      }
    };
  });
}
function businessForm(isNew = false) {
  const current = isNew ? null : state.business;
  const expectedActive = state.business?.id || null;
  const draftKey = current ? "dr-profile-" + current.id : "dr-profile-new-" + (expectedActive || "empty");
  const draft = store.get(draftKey, current ? { name: current.name, description: current.description, profile_revision: current.profile_revision } : {});
  const creationKey = draft.request_key || crypto.randomUUID();
  shell(`<a href="${current ? "#my-business" : "#businesses"}" class="back-link">${icon("back")} ${current ? "Mi negocio" : "Negocios guardados"}</a><div class="page-heading"><div><h1>${current ? "Contexto de tu negocio." : "Empecemos por tu negocio."}</h1><p>${current ? "El contexto se comparte con tus conversaciones. Los resultados afectados por un cambio necesitarán revisión." : "Guarda esta información una vez. Podrás reutilizarla en tus próximos análisis."}</p></div></div>
    <section class="card form-card"><form id="business-form"><label for="business">¿Cómo se llama tu negocio?</label><input id="business" name="name" maxlength="100" required autocomplete="organization" value="${esc(draft.name)}"><label for="context">Cuéntanos a qué te dedicas</label><textarea id="context" name="description" rows="5" maxlength="6000" required placeholder="Qué vendes y cómo funciona tu negocio…">${esc(draft.description)}</textarea><p class="field-help">Guarda el contexto y empieza a conversar. Podrás añadir datos cuando los necesites.</p><div id="business-error"></div><div class="form-actions"><a class="button ghost" href="#home">Volver</a><button class="button primary" type="submit">Guardar y continuar ${icon("arrow")}</button></div></form></section>`, "businesses", "Contexto del negocio");
  const form = document.querySelector("#business-form");
  const values = () => ({ ...Object.fromEntries(new FormData(form)), request_key: creationKey, profile_revision: draft.profile_revision ?? current?.profile_revision });
  form.oninput = () => store.set(draftKey, values());
  form.onsubmit = async event => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    if (button.disabled) return;
    button.disabled = true;
    const body = { ...values(), business_id: current?.id, expected_active_id: expectedActive };
    store.set(draftKey, values());
    try {
      await api("/api/business", { method: "POST", body });
      store.remove(draftKey);
      const next = current ? "#my-business" : "#home";
      if (location.hash === next) await route();
      else location.hash = next;
    } catch (error) {
      document.querySelector("#business-error").innerHTML = errorBox(error.message) + '<a href="#business" id="reload-profile">Cargar el contexto guardado</a>';
      document.querySelector("#reload-profile").onclick = async e => {
        e.preventDefault();
        store.remove(draftKey);
        await route();
      };
      button.disabled = false;
    }
  };
}
function newAnalysis() {
  if (!state.business) {
    if (state.businesses.length) businessChooser();
    else businessForm(true);
    return;
  }
  const b = state.business;
  const d = state.draft;
  shell(`<a href="#home" class="back-link">${icon("back")} Volver a mis análisis</a><div class="page-heading form-heading"><div><p class="eyebrow">UN NUEVO PUNTO DE VISTA</p><h1>Una nueva pregunta para <em>${esc(b.name)}.</em></h1><p>El contexto de tu negocio ya está guardado. Elige qué quieres entender y comparte tus datos.</p></div></div>
    <div class="form-layout"><section class="card form-card"><form id="new-form"><div class="form-section"><div class="review-context"><span class="eyebrow">CONTEXTO GUARDADO</span><h3>${esc(b.name)}</h3><p>${esc(b.description)}</p><a class="text-button" href="#business">Editar contexto para próximos análisis</a></div>
    <fieldset><legend>¿Qué te gustaría averiguar?</legend><label class="choice ${d.mode !== "specific" ? "chosen" : ""}"><input type="radio" name="mode" value="general" ${d.mode !== "specific" ? "checked" : ""}><span><strong>Explorar mis datos</strong><small>Identificar observaciones que merezcan atención.</small></span></label><label class="choice ${d.mode === "specific" ? "chosen" : ""}"><input type="radio" name="mode" value="specific" ${d.mode === "specific" ? "checked" : ""}><span><strong>Tengo una pregunta concreta</strong><small>Orientar este análisis hacia algo que quieres entender.</small></span></label></fieldset>
    <div id="goal-field" ${d.mode !== "specific" ? "hidden" : ""}><label for="goal">Tu pregunta</label><textarea id="goal" name="goal" rows="2" maxlength="2000" ${d.mode === "specific" ? "required" : ""}>${esc(d.goal)}</textarea></div>
    <label for="title">Nombre del análisis</label><input id="title" name="title" required maxlength="160" value="${esc(d.title || "Exploración de " + b.name)}">
    <div class="dropzone" id="dropzone"><span class="upload-icon">${icon("upload")}</span><h3>Arrastra tu CSV hasta aquí</h3><p>O selecciónalo desde tu equipo</p><label class="button secondary file-picker" for="csv">Elegir archivo CSV<input type="file" id="csv" accept=".csv,text/csv" aria-label="Elegir archivo CSV"></label><small>1 archivo CSV · UTF-8 · Máximo 20 MB</small></div><div id="selected-file"></div>
    <div class="sample-row"><span>¿Solo quieres probar el recorrido?</span><button type="button" class="text-button" id="use-sample">Usar datos de ejemplo ${icon("arrow")}</button></div><p class="field-help">Revisaremos el archivo y te preguntaremos por las aclaraciones necesarias para este análisis.</p></div>
    <div id="form-error"></div><div class="form-actions"><span class="save-hint">${icon("check")} Contexto guardado en tu negocio</span><button class="button primary" type="submit">Empezar análisis ${icon("arrow")}</button></div></form></section>
    <aside class="form-aside"><span class="aside-glyph">✳</span><h2>Tu negocio,<br>sin empezar de cero.</h2><p>Cada análisis conserva su pregunta, archivo y contexto. Puedes volver a los anteriores desde Mis análisis.</p><div class="aside-item">${icon("shield")}<div><strong>El contexto se conserva</strong><p>Puedes cerrar esta página y volver. Si todavía no has enviado el archivo, tendrás que seleccionarlo de nuevo.</p></div></div></aside></div>`, "analyses", "Nuevo análisis");
  const form = document.querySelector("#new-form");
  form.oninput = e => {
    if (!e.target.name) return;
    state.draft[e.target.name] = e.target.value;
    saveDraft();
    if (e.target.name === "mode") {
      const specific = e.target.value === "specific";
      document.querySelector("#goal-field").hidden = !specific;
      document.querySelector("#goal").required = specific;
      document.querySelectorAll(".choice").forEach(c => c.classList.toggle("chosen", c.querySelector("input").checked));
    }
  };
  form.onsubmit = async event => {
    event.preventDefault();
    if (state.uploading) return;
    for (const [key, value] of new FormData(form))
      if (key !== "csv" && typeof value === "string") state.draft[key] = value;
    if (!state.file) {
      document.querySelector("#form-error").innerHTML = errorBox("Selecciona un archivo CSV para empezar.");
      document.querySelector("#csv").focus();
      return;
    }
    state.requestKey ||= crypto.randomUUID();
    const body = new FormData();
    body.append("metadata", JSON.stringify({ request_key: state.requestKey, business_id: b.id, profile_revision: b.profile_revision, goal: state.draft.mode === "specific" ? state.draft.goal : "", title: state.draft.title }));
    body.append("file", state.file);
    state.uploading = true;
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    button.textContent = "Guardando archivo…";
    try {
      const result = await api("/api/jobs", { method: "POST", body });
      store.remove("dr-draft-" + b.id);
      state.draft = {};
      state.file = null;
      state.requestKey = null;
      location.hash = "#analysis/" + result.id;
    } catch (error) {
      document.querySelector("#form-error").innerHTML = errorBox(error.message) + '<a href="#new" id="reload-analysis">Recargar contexto</a>';
      document.querySelector("#reload-analysis").onclick = async e => { e.preventDefault(); await route(); };
      button.disabled = false;
      button.innerHTML = "Volver a intentar " + icon("arrow");
    } finally {
      state.uploading = false;
    }
  };
  document.querySelector("#csv").onchange = e => chooseFile(e.target.files[0]);
  const drop = document.querySelector("#dropzone");
  ["dragenter", "dragover"].forEach(event => drop.addEventListener(event, e => { e.preventDefault(); drop.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach(event => drop.addEventListener(event, e => { e.preventDefault(); drop.classList.remove("dragging"); }));
  drop.addEventListener("drop", e => {
    if (e.dataTransfer.files.length !== 1) document.querySelector("#form-error").innerHTML = errorBox("Selecciona un solo archivo CSV.");
    else chooseFile(e.dataTransfer.files[0]);
  });
  document.querySelector("#use-sample").onclick = async () => {
    try {
      const response = await fetch("/api/sample");
      if (!response.ok) throw new Error("No se pudo cargar el ejemplo.");
      chooseFile(new File([await response.blob()], "ventas-ejemplo.csv", { type: "text/csv" }));
      toast("Datos ficticios de ventas diarias. Revisa que el contexto describa este ejemplo.");
    } catch (error) { toast(error.message); }
  };
  showFile();
}
function chooseFile(file) {
  if (!file) return;
  if (
    !file.name.toLowerCase().endsWith(".csv") ||
    !file.size ||
    file.size > 20 * 1024 ** 2
  ) {
    document.querySelector("#form-error").innerHTML = errorBox(
      "Elige un CSV con datos, de hasta 20 MB.",
    );
    return;
  }
  state.file = file;
  state.requestKey = null;
  document.querySelector("#form-error").innerHTML = "";
  showFile();
}
function showFile() {
  const file = state.file;
  document.querySelector("#selected-file").innerHTML = file
    ? `<div class="selected-file">${icon("file")}<span><strong>${esc(file.name)}</strong><small>${size(file.size)} · Listo para subir</small></span><button class="icon-button" type="button" id="remove-file" aria-label="Quitar archivo">${icon("close")}</button></div>`
    : '<p class="field-help">El archivo se guardará al empezar. Si sales antes, tendrás que seleccionarlo de nuevo.</p>';
  if (file)
    document.querySelector("#remove-file").onclick = () => {
      state.file = null;
      document.querySelector("#csv").value = "";
      showFile();
    };
}
function progressSteps(data) {
  const ordered = ["upload", "planning", "research", "review", "done"];
  const current = ordered.indexOf(data.phase);
  return `<ol class="progress-steps">${ordered.map((phase, i) => `<li class="${i < current ? "complete" : i === current ? "current" : ""}"><span>${i < current || (phase === "done" && data.publishable) ? icon("check") : i + 1}</span><div><strong>${{ upload: "Archivo recibido", planning: "Contexto y preguntas", research: "Análisis", review: "Revisión", done: "Tu informe" }[phase]}</strong><small>${i < current ? "Completado" : i === current ? statuses[data.status]?.[0] : "Pendiente"}</small></div></li>`).join("")}</ol>`;
}
function detail(data) {
  const liveStatus = document.querySelector("#live-status");
  const description = `${statuses[data.status]?.[0]}.${data.status === "running" ? " " + phases[data.phase] + "." : ""}`;
  if (liveStatus && liveStatus.textContent !== description)
    liveStatus.textContent = description;
  const question = data.questions[0];
  let center;
  if (data.status === "waiting" && question) {
    const saved = store.get("dr-answer-" + data.id + "-" + question.id, {
      text: "",
      disposition: "answered",
    });
    center = `<section class="card question-card"><div class="card-kicker">${icon("chat")} UNA ACLARACIÓN PARA SEGUIR <span>${data.questions.length > 1 ? data.questions.length + " preguntas pendientes" : "Tu contexto importa"}</span></div><h2>${esc(question.text)}</h2><div class="question-reason"><strong>Por qué te lo preguntamos</strong><p>${esc(question.reason)}</p></div><form id="answer-form"><fieldset><legend>Tu respuesta</legend>${question.options.map((option, i) => `<label class="answer-option"><input type="radio" name="option" value="${i}"><span>${esc(option)}</span></label>`).join("")}<label for="answer-text" class="answer-label">${question.options.length ? "O cuéntanos con tus palabras" : "Cuéntanos lo que sabes"}</label><textarea id="answer-text" rows="3" maxlength="6000" placeholder="Añade tu respuesta o una aclaración…">${esc(saved.text)}</textarea><label class="unknown-choice"><input type="checkbox" id="unknown" ${saved.disposition === "unknown" ? "checked" : ""}> No lo sé / no tengo esa información</label></fieldset><p class="field-help">Si no lo sabes, continuaremos con lo que pueda analizarse y señalaremos las limitaciones.</p><div id="answer-error"></div><div class="answer-actions"><span class="save-hint">La respuesta se guarda al enviarla</span><button class="button primary" type="submit">Guardar y continuar ${icon("arrow")}</button></div></form></section>`;
  } else if (data.publishable) {
    center = `<div class="report-ready"><span>${icon("check")} Tu informe está disponible</span><a class="text-button" href="/api/jobs/${data.id}/report" target="_blank" rel="noopener">Abrir informe ${icon("external")}</a></div><p class="report-caveat">Informe elaborado con IA y revisión automática. Consulta el alcance y la evidencia; los errores analíticos de esta versión siguen en evaluación.</p><iframe id="report-frame" class="report-frame" title="Informe de ${esc(data.business)} con hallazgos, gráficos y evidencia" src="/api/jobs/${data.id}/report" sandbox="allow-same-origin"></iframe>`;
  } else if (["failed", "blocked"].includes(data.status)) {
    center = `<section class="card status-card"><span class="status-symbol amber">${icon(data.status === "failed" ? "clock" : "shield")}</span><p class="eyebrow">TU TRABAJO SIGUE GUARDADO</p><h2>${data.status === "failed" ? "Hemos hecho una pausa." : "Este análisis necesita atención."}</h2><p>${esc(data.issue)}</p>${data.status === "failed" ? `<button class="button primary" id="retry">${data.context_stale ? "Recalcular con la memoria actual" : "Reintentar análisis"} ${icon("arrow")}</button><p class="field-help">${data.context_stale ? "Se conserva la versión anterior y se prepara una nueva revisión." : "Se recupera el último paso guardado. Una petición al modelo interrumpida puede ejecutarse de nuevo."}</p>` : data.data_version?.corrected ? '<a class="button secondary" href="#my-business">Elegir la versión actual</a>' : '<a class="button secondary" href="#new">Crear otro análisis</a>'}<div id="retry-error"></div></section>`;
  } else {
    center = `<section class="card status-card"><div class="working-symbol">${icon("spark")}</div><p class="eyebrow">${data.status === "queued" ? "TODO LISTO PARA EMPEZAR" : "ESTAMOS TRABAJANDO EN ELLO"}</p><h2>${data.status === "queued" ? "Tu análisis está en cola." : phases[data.phase]}</h2><p>${{ upload: "Estamos preparando el archivo y comprobando su estructura.", planning: "El agente está revisando tus datos y el contexto. Si falta una definición importante, te preguntará aquí.", research: "El agente está realizando los cálculos que pueden responder a tu pregunta.", review: "Estamos contrastando las conclusiones con los cálculos y su evidencia.", done: "Estamos preparando la presentación de tu informe." }[data.phase]}</p>${data.activity ? `<p class="progress-update">${esc(data.activity)}</p>` : ""}<div class="live-note"><span class="pulse-dot"></span> El estado se actualiza automáticamente</div><div class="leave-note">${icon("shield")} Puedes cerrar esta página. El análisis continúa mientras el servidor local siga encendido.</div></section>`;
  }
  shell(
    `<a class="back-link" href="#analyses">${icon("back")} Todos mis análisis</a><div class="page-heading detail-heading"><div><p class="eyebrow">${esc(data.business)} <span> / </span> ${fmtDate(data.created_at)}</p><h1>${esc(data.title)}</h1></div>${badge(data.status)}</div><div class="detail-layout"><div class="detail-main">${center}${data.interpretations.length && !data.publishable ? `<details class="card interpretation-card"><summary>Lo que estamos entendiendo de tus datos <span>Interpretación provisional</span></summary>${data.interpretations.map((i) => `<p><span class="interpretation-label">${{ observed: "Observado", inferred: "Por comprobar", confirmed: "Confirmado", unresolved: "Por aclarar" }[i.status]}</span>${esc(i.text)}</p>`).join("")}</details>` : ""}${data.answers.length ? `<details class="card answer-history"><summary>Tus aclaraciones guardadas <span>${data.answers.length}</span></summary>${data.answers.map((a) => `<p>${icon("check")}${esc(a.disposition === "answered" ? a.text : a.disposition === "unknown" ? "No tengo esa información." : "Prefiero no responder.")}</p>`).join("")}</details>` : ""}</div><aside class="detail-aside"><section class="card timeline"><p class="eyebrow">EL RECORRIDO</p>${progressSteps(data)}</section><section class="card source-card"><p class="eyebrow">PUNTO DE PARTIDA</p><span class="source-file">${icon("file")}<strong>${esc(data.filename)}</strong></span><small>${size(data.byte_count)}${data.files[0]?.row_count != null ? " · " + data.files[0].row_count.toLocaleString("es-ES") + " filas" : ""}</small>${data.origin === "upload" ? `<a class="text-button" href="/api/jobs/${data.id}/file">Descargar original ${icon("download")}</a>` : `<p>Datos reutilizados de tu negocio.</p>${data.conversation_id ? `<a class="text-button" href="#chat/${esc(data.conversation_id)}">Volver a la conversación ${icon("chat")}</a>` : ""}`}${data.data_version?.superseded_by ? `<p class="notice">${data.data_version.corrected ? "Esta fuente ha sido corregida." : "Este resultado usa una versión anterior. Hay datos nuevos sin recalcular."} <a href="#my-business">Ver Mi negocio</a></p>` : ""}<hr><h3>${data.goal ? "Tu pregunta" : "Exploración general"}</h3><p>${esc(data.goal || "Identificar lo que merece atención en los datos disponibles.")}</p><details><summary>Contexto del negocio</summary><p>${esc(data.context)}</p></details></section><p class="saved-at">${icon("check")} Guardado en tu espacio local</p></aside></div>`,
    "analyses",
    "Detalle del análisis",
  );
  if (data.status === "waiting" && question) setupAnswer(data, question);
  if (document.querySelector("#retry"))
    document.querySelector("#retry").onclick = async (e) => {
      const button = e.currentTarget;
      button.disabled = true;
      button.textContent = "Comprobando modelo…";
      document.querySelector("#retry-error").innerHTML = "";
      try {
        await api(`/api/jobs/${data.id}/retry`, { method: "POST", body: {} });
        state.signature = "";
        await pollDetail(data.id);
      } catch (error) {
        if (button.isConnected) {
          document.querySelector("#retry-error").innerHTML = errorBox(
            error.message,
          );
          button.disabled = false;
          button.innerHTML = "Reintentar análisis " + icon("arrow");
        }
      }
    };
  const frame = document.querySelector("#report-frame");
  if (frame)
    frame.onload = () => {
      const doc = frame.contentDocument;
      if (doc?.body) {
        const resize = () => {
          frame.style.height =
            Math.ceil(doc.body.getBoundingClientRect().height) + 4 + "px";
        };
        resize();
        const observer = new ResizeObserver(resize);
        observer.observe(doc.body);
      }
    };
}
function setupAnswer(data, question) {
  const form = document.querySelector("#answer-form");
  const text = document.querySelector("#answer-text");
  const unknown = document.querySelector("#unknown");
  const key = "dr-answer-" + data.id + "-" + question.id;
  let requestKey = crypto.randomUUID();
  const save = () => {
    store.set(key, {
      text: text.value,
      disposition: unknown.checked ? "unknown" : "answered",
    });
    requestKey = crypto.randomUUID();
    text.disabled = unknown.checked;
  };
  text.disabled = unknown.checked;
  text.oninput = () => {
    form
      .querySelectorAll("[name=option]")
      .forEach((radio) => (radio.checked = false));
    save();
  };
  unknown.onchange = save;
  form.querySelectorAll("[name=option]").forEach(
    (radio) =>
      (radio.onchange = () => {
        text.value = question.options[Number(radio.value)];
        unknown.checked = false;
        save();
      }),
  );
  form.onsubmit = async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    if (!unknown.checked && !text.value.trim()) {
      document.querySelector("#answer-error").innerHTML = errorBox(
        "Selecciona una opción, escribe una respuesta o marca «No lo sé».",
      );
      text.focus();
      return;
    }
    button.disabled = true;
    button.textContent = "Guardando respuesta…";
    try {
      await api(`/api/jobs/${data.id}/answers`, {
        method: "POST",
        body: {
          request_key: requestKey,
          question_id: question.id,
          phase: question.phase,
          text: unknown.checked ? "" : text.value,
          disposition: unknown.checked ? "unknown" : "answered",
        },
      });
      store.remove(key);
      state.signature = "";
      toast("Respuesta guardada. Continuamos con tu análisis.");
      await pollDetail(data.id);
    } catch (error) {
      document.querySelector("#answer-error").innerHTML = errorBox(
        error.message,
      );
      button.disabled = false;
      button.innerHTML = "Guardar y continuar " + icon("arrow");
    }
  };
}
async function files() { await dossierPage("data"); }
function how() {
  shell(
    `<div class="page-heading"><div><p class="eyebrow">DE UN ARCHIVO A UNA CONVERSACIÓN</p><h1>Decide con <em>más contexto.</em></h1><p>Un recorrido sencillo, con espacio para las preguntas importantes.</p></div></div><div class="how-grid">${[
      [
        "01",
        "Comparte tu punto de partida",
        "Describe tu negocio una vez y pregunta desde Inicio. Puedes consultar el contexto, reutilizar datos o analizar un CSV nuevo desde Mi negocio.",
      ],
      [
        "02",
        "Aclara lo que los datos no cuentan",
        "El agente puede preguntarte por el significado de una columna o el alcance del archivo. Puedes responder con tus palabras o indicar que no lo sabes.",
      ],
      [
        "03",
        "Deja que el análisis avance",
        "Los cálculos se ejecutan de forma aislada y sus resultados pasan por una revisión. El progreso indica la etapa real; no estimamos tiempos ni porcentajes.",
      ],
      [
        "04",
        "Consulta y comprueba",
        "El informe reúne los hallazgos que superan la revisión, gráficos cuando aportan información y limitaciones. Abre «Ver cómo se ha calculado» para consultar archivos, método y cifras.",
      ],
    ]
      .map(
        ([n, t, p]) =>
          `<section class="card"><span class="journey-number">${n}</span><h2>${t}</h2><p>${p}</p></section>`,
      )
      .join(
        "",
      )}</div><section class="notice"><strong>Una primera versión para explorar la experiencia.</strong><p>Esta versión se ejecuta en tu equipo y utiliza el modelo configurado por el operador. Los archivos y el progreso se guardan localmente. La calidad analítica sigue en evaluación: la revisión automática puede no detectar todos los errores. Los filtros analíticos y los archivos Excel llegarán en una ampliación posterior.</p></section><a class="button primary" href="#chats">Empezar una conversación ${icon("arrow")}</a>`,
    "",
    "Cómo funciona",
  );
}
async function pollDetail(id) {
  const generation = state.generation;
  try {
    const {memory, ...data} = await api("/api/jobs/" + encodeURIComponent(id));
    if (generation !== state.generation) return;
    state.memory = memory;
    renderMemory();
    const signature = JSON.stringify(data);
    if (signature !== state.signature) {
      state.signature = signature;
      detail(data);
    }
  } catch (e) {
    if (generation !== state.generation) return;
    if (e.status === 401) {
      clearInterval(state.poll);
      login();
    } else if (e.status === 404 || e.status === 400) {
      clearInterval(state.poll);
      shell(
        `<section class="card status-card"><h1>No encontramos este análisis.</h1><p>${esc(e.message)}</p><a class="button secondary" href="#home">Volver al inicio</a></section>`,
      );
    } else toast(e.message);
  }
}
function shortGreeting(value) {
  const normalized = String(value ?? "").toLocaleLowerCase("es").replace(/[¡!¿?.,\s]+/g, " ").trim();
  return ["hola", "holi", "buenas", "buen día", "buenos días", "buenas tardes", "buenas noches", "qué tal", "que tal", "hey", "hello", "hi"].includes(normalized);
}
function chatProse(text) {
  // Escape first: model prose never introduces HTML, links or executable content.
  const inline = line => esc(line).replace(/`([^`\n]+)`/g, "<code>$1</code>").replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  return text.split(/\n\s*\n/).map(block => {
    const lines = block.split("\n");
    if (lines.every(line => /^[-*]\s+/.test(line)))
      return `<ul>${lines.map(line => `<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`).join("")}</ul>`;
    return `<p>${lines.map(inline).join("<br>")}</p>`;
  }).join("");
}
function chatResponse(r, anchor = "response", ownerText = "") {
  if (!r) return "";
  if (r.kind === "grounded_answer") {
    const labels = [...new Set((r.sources || []).map(s => s.label))];
    return chatProse(r.text)
      + (labels.length ? `<p class="muted chat-source">Fuentes: ${labels.map(esc).join(" · ")}</p>` : "")
      + (r.evidence ? `<details class="chat-evidence"><summary>Ver informe de referencia</summary>${chatResponse(r.evidence, anchor)}</details>` : "");
  }
  if (r.kind === "memory" && shortGreeting(ownerText))
    return `<p>¡Hola! ¿Qué te gustaría saber o investigar sobre ${esc(state.business?.name || "tu negocio")}?</p>`;
  if (r.kind === "evidence") {
    const paragraphs = r.paragraphs?.length ? r.paragraphs : r.claims.flatMap(c => [c.statement, c.interpretation]).filter(Boolean);
    return `${paragraphs.map(text => `<p>${esc(text)}</p>`).join("")}<p class="muted chat-source">Fuente: ${esc(r.title)}${r.scope?.period ? ` · ${esc(r.scope.period)}` : ""}</p><details class="chat-evidence"><summary>Ver datos y evidencia</summary><h3>${esc(r.title)}</h3>${r.highlights?.length ? `<div class="dashboard-metrics">${r.highlights.map(h => `<div class="metric-tile"><span>${esc(h.label)}</span><strong>${esc(h.value)}</strong><small>${esc(h.unit)}</small></div>`).join("")}</div>` : ""}<p class="muted">${esc(r.scope?.period)} · ${esc(r.scope?.coverage)}</p>${r.claims.map(c => `<section id="${esc(anchor)}-${esc(c.key)}"><h4>${esc(c.title)}</h4><p>${esc(c.statement)}</p><p>${esc(c.interpretation)}</p><details><summary>Cómo se ha comprobado</summary><p>${esc(c.method)}</p></details></section>`).join("")}<div class="dash-chart-grid">${(r.charts || []).map(c => dashboardChart(c, null, `#${anchor}-${c.claim_key}`)).join("")}</div><ul>${r.limitations.map(x => `<li>${esc(x)}</li>`).join("")}</ul></details>`;
  }
  if (r.kind === "catalog")
    return `<p>${esc(r.text)}</p>${r.items.map((x) => `<p><strong>${esc(x.description)}</strong> · ${esc(x.names.join(", "))}<br>${esc(x.columns.join(", "))}</p>`).join("") || "<p>No hay conjuntos disponibles todavía.</p>"}`;
  if (r.kind === "history")
    return `<p>${esc(r.text)}</p>${r.items.map((x) => `<blockquote>${x.preceding_question ? `<p>Pregunta: ${esc(x.preceding_question)}</p>` : ""}<p>${esc(x.text)}</p>${state.chats.some(c => String(c.id) === String(x.conversation_id)) ? `<a href="#chat/${esc(x.conversation_id)}">Abrir conversación original</a>` : ""}</blockquote>`).join("")}`;
  if (r.kind === "memory") {
    const legacy = r.text === "El mensaje está guardado. Estos son los recuerdos aplicables y su estado.";
    const intro = legacy ? (r.items?.length ? "Esto es lo que tenía guardado en ese momento:" : "En ese momento todavía no encontraba información del negocio que pudiera utilizar.") : r.text;
    return `<p>${esc(intro)}</p>${r.items?.length ? `<ul>${r.items.map((x) => `<li>${x.status === "declared" ? "" : `<strong>${esc({ proposed: "Por confirmar", conflicted: "Hay versiones diferentes" }[x.status] || x.status)}: </strong>`}${esc(x.content.statement)}${x.content.scope === "business" ? "" : `<br><small>${esc({ analysis: "Sobre este conjunto de datos", source: "Sobre este archivo" }[x.content.scope])}</small>`}</li>`).join("")}</ul>` : ""}`;
  }
  if (r.kind === "questions")
    return r.questions
      .map(
        (q) => `<p><strong>${esc(q.text)}</strong></p><p>${esc(q.reason)}</p>`,
      )
      .join("");
  return `<p>${esc(r.text)}</p>`;
}
async function chatsPage() {
  if (!state.business) { businessForm(true); return; }
  if (location.hash === "#ask") {
    const recent = state.chats.slice(0, 6);
    shell(`<div class="new-chat-landing"><div class="new-chat-heading"><p class="eyebrow">${esc(state.business.name)}</p><h1>¿Qué te gustaría entender hoy?</h1></div>${questionComposer()}<section class="new-chat-recent" aria-label="Conversaciones anteriores"><h2>Conversaciones anteriores</h2>${recent.length ? `<div class="new-chat-list">${recent.map(c => `<a href="#chat/${esc(c.id)}">${icon("chat")}<span>${esc(shortChatTitle(c.title))}</span>${icon("arrow")}</a>`).join("")}</div><a class="new-chat-all" href="#chats">Ver todas las conversaciones ${icon("arrow")}</a>` : '<p>Aquí encontrarás tus chats cuando empieces a conversar.</p>'}</section></div>`, "chats", "Nuevo chat");
    return;
  }
  shell(`<div class="page-heading"><div><p class="eyebrow">TU NEGOCIO, CON CONTEXTO</p><h1>Conversaciones</h1><p>Retoma un chat o empieza uno nuevo.</p></div><a class="button secondary" href="#ask">Nuevo chat</a></div><div class="card-grid">${state.chats.map(c => `<div class="card chat-list-card"><a href="#chat/${esc(c.id)}"><h2>${esc(c.title)}</h2><p>${fmtDate(c.created_at)}</p><span>Abrir conversación ${icon("arrow")}</span></a><button type="button" class="chat-delete" data-delete-chat="${esc(c.id)}" aria-label="Eliminar chat ${esc(c.title)}" title="Eliminar chat">${icon("close")}</button></div>`).join("") || '<p class="empty">Aquí aparecerán tus conversaciones guardadas.</p>'}</div>${state.deletedChats.length ? `<section class="chat-trash"><h2>Chats eliminados</h2><p>Se pueden recuperar. Los datos guardados en Mi negocio y los informes se conservan.</p>${state.deletedChats.map(c => `<div><span>${esc(c.title)}</span><button class="button secondary" type="button" data-restore-chat="${esc(c.id)}">Recuperar</button></div>`).join("")}</section>` : ""}`, "chats", "Conversaciones");
}
async function chatPage(id) {
  const generation = state.generation;
  let current = null,
    signature = "",
    sending = false,
    followedTurnId = null;
  const draftKey = "dr-chat-draft-" + id;
  shell(
    `<div class="page-heading"><div><a href="#chats">← Conversaciones</a><h1 id="chat-title">Conversación</h1><p>El contexto del negocio se comparte entre conversaciones.</p></div><div class="chat-heading-actions"><button class="button secondary" type="button" data-delete-chat="${esc(id)}">Eliminar chat</button><a class="button secondary" href="#ask">Nuevo chat</a></div></div>
    <p id="chat-dataset" class="question-context"></p><div id="chat-turns" aria-live="polite" aria-relevant="additions text"></div><div id="chat-conflicts"></div>
    <form class="chat-composer" id="chat-send"><div class="composer-card"><label id="question-label" hidden>Aclaración pendiente<select id="chat-question"></select></label><div class="composer-input-row"><label for="chat-message" class="sr-only">Tu mensaje</label><textarea id="chat-message" rows="1" maxlength="6000" required placeholder="Pregunta lo que quieras…"></textarea><button class="button primary" id="send-message" aria-label="Enviar mensaje">${icon("arrow")}</button></div></div><div class="chat-suggestions" id="chat-suggestions"><button type="button" data-suggestion="¿Qué sabes de mi negocio?">Qué sabemos del negocio</button><button type="button" data-suggestion="¿Qué datos tenemos disponibles para analizar?">Explorar mis datos</button></div></form>`,
    "chats",
    "Conversación",
  );
  const textarea = document.querySelector("#chat-message");
  const followController = new AbortController();
  state.chatFollowController = followController;
  const stopFollowing = (event) => {
    if (event.target.closest?.(".chat-composer")) return;
    if (event.type === "keydown" && !["PageUp", "PageDown", "Home", "End", "ArrowUp", "ArrowDown", " "].includes(event.key)) return;
    followedTurnId = null;
  };
  for (const type of ["wheel", "touchmove", "pointerdown", "keydown"])
    document.addEventListener(type, stopFollowing, {passive: true, signal: followController.signal});
  textarea.value = store.get(draftKey, { text: "" }).text;
  const chatForm = document.querySelector("#chat-send");
  const chatSuggestions = document.querySelector("#chat-suggestions");
  const syncChatComposer = () => {
    chatSuggestions.hidden = !!textarea.value.trim();
    resizeComposer(textarea);
  };
  textarea.addEventListener("input", () => {
    store.set(draftKey, { ...store.get(draftKey, {}), text: textarea.value, key: crypto.randomUUID() });
    syncChatComposer();
  });
  bindComposerKeys(textarea, chatForm);
  syncChatComposer();
  document.querySelectorAll("[data-suggestion]").forEach((b) =>
    b.addEventListener("click", () => {
      textarea.value = b.dataset.suggestion;
      textarea.dispatchEvent(new Event("input"));
      textarea.focus();
    }),
  );
  async function refresh() {
    try {
      const data = await api("/api/chats/" + encodeURIComponent(id));
      if (generation !== state.generation) return;
      const oldStatuses = new Map(current?.turns?.map(t => [String(t.id), t.status]) || []);
      const previousTarget = followedTurnId && document.querySelector(`[data-chat-turn="${followedTurnId}"]`);
      const hadReply = Boolean(previousTarget?.querySelector(".chat-answer"));
      current = data;
      state.memory = data.memory;
      renderMemory();
      const next = JSON.stringify(data);
      if (signature === next) return;
      signature = next;
      document.querySelector("#chat-title").textContent =
        shortChatTitle(data.conversation.title);
      document.querySelector("#chat-dataset").innerHTML = data.dataset ? `${esc(data.dataset.title)} · Versión ${esc(data.dataset.version)}${data.dataset.corrected ? " · Corregida: elige los datos vigentes" : data.dataset.superseded_by ? " · Hay una versión posterior" : ""} · <a href="#files">Ver datos</a>` : "Datos: el agente buscará los conjuntos pertinentes.";
      document.querySelector("#chat-turns").innerHTML =
        data.turns
          .map(
            (t, index) => {
              const queuedBehind = t.status === "queued" && data.turns.slice(0, index).some(item => item.status !== "completed");
              const queuePosition = data.turns.slice(0, index + 1).filter(item => item.status === "queued").length;
              const retryable = ["failed", "stale", "blocked"].includes(t.status) && data.turns.slice(index + 1).every(item => item.status === "queued");
              return `<article class="chat-turn" data-chat-turn="${esc(t.id)}"><div class="chat-owner"><p>${esc(t.payload.text)}</p>${queuedBehind ? `<span class="chat-queue-badge">En cola · ${queuePosition}</span>` : ""}</div>${queuedBehind ? "" : `<div class="card chat-answer"><strong>Decision Room</strong>${t.payload.finding_reference ? `<p class="question-context">Sobre: ${esc(t.payload.finding_reference.title)} · ${esc(t.payload.finding_reference.period)}</p>` : ""}${chatResponse(t.response, `turn-${t.id}`, t.payload.text)}${t.issue ? `<p class="notice">${esc(t.issue)}</p>` : ""}${["queued", "routing", "processing"].includes(t.status) ? '<span class="chat-reply-pulse" role="status" aria-label="Preparando respuesta"><i></i><i></i><i></i></span>' : ""}${retryable ? `<button class="button secondary" data-retry="${esc(t.id)}">Reintentar con el contexto actual</button>` : ""}${t.response?.report_id ? (t.report_requested ? `<a class="button secondary" target="_blank" rel="noopener" href="/api/chats/${esc(id)}/report/${esc(t.id)}">Abrir informe</a>` : `<button class="button secondary" data-report="${esc(t.id)}">Generar informe</button>`) : ""}</div>`}</article>`;
            },
          )
          .join("") ||
        '<section class="card"><h2>¿Por dónde empezamos?</h2><p>Puedes preguntar por un resultado, pedir un cálculo o explicar cómo funciona tu negocio.</p></section>';
      const conflicts = data.memory_items.filter(
        (x) => x.status === "conflicted",
      );
      document.querySelector("#chat-conflicts").innerHTML = conflicts
        .map(
          (f) =>
            `<section class="notice"><h3>Confirma qué debemos recordar</h3><p>Existe una contradicción con: ${esc(f.content.statement)}</p>${f.alternatives.map((a, i) => `<p>${esc(a.content.statement)}</p><button class="button secondary" data-fact="${esc(f.id)}" data-revision="${f.revision}" data-alternative="${i}">Usar esta versión como corrección</button>`).join("")}</section>`,
        )
        .join("");
      const waiting = data.turns.find(t => t.status === "waiting");
      const busy = !waiting && data.turns.some(t => ["queued", "routing", "processing"].includes(t.status));
      const sendButton = document.querySelector("#send-message");
      sendButton.disabled = sending;
      sendButton.classList.toggle("is-thinking", busy);
      sendButton.setAttribute("aria-label", waiting ? "Enviar aclaración" : busy ? "Añadir mensaje a la cola" : "Enviar mensaje");
      sendButton.innerHTML = busy ? '<span class="send-spinner" aria-hidden="true"></span>' : icon("arrow");
      const questions = waiting?.questions || [];
      document.querySelector("#question-label").hidden = !questions.length;
      const selector = document.querySelector("#chat-question"),
        old = selector.value;
      selector.innerHTML = questions
        .map((q) => `<option value="${esc(q.id)}">${esc(q.text)}</option>`)
        .join("");
      if (questions.some((q) => q.id === old)) selector.value = old;
      if (state.scrollToTurn && data.turns.some(t => String(t.id) === String(state.scrollToTurn))) {
        followedTurnId = String(state.scrollToTurn);
        state.scrollToTurn = null;
        const targetId = followedTurnId;
        requestAnimationFrame(() => scrollToChatTurn(targetId));
      } else if (followedTurnId) {
        const followed = data.turns.find(t => String(t.id) === followedTurnId);
        const gainedReply = !hadReply && Boolean(document.querySelector(`[data-chat-turn="${followedTurnId}"] .chat-answer`));
        if (followed && (oldStatuses.get(followedTurnId) !== followed.status || gainedReply)) {
          const targetId = followedTurnId;
          requestAnimationFrame(() => scrollToChatTurn(targetId));
          if (!["queued", "routing", "processing"].includes(followed.status)) followedTurnId = null;
        }
      }
    } catch (e) {
      if (generation === state.generation) toast(e.message);
    }
  }
  document
    .querySelector("#chat-send")
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      if (sending || !current) return;
      sending = true;
      document.querySelector("#send-message").disabled = true;
      const draft = store.get(draftKey, {}),
        key = draft.key || crypto.randomUUID(),
        sentText = textarea.value;
      store.set(draftKey, { ...draft, text: sentText, key });
      try {
        const sent = await api("/api/chats/" + id + "/messages", {
          method: "POST",
          body: {
            business_id: current.conversation.business_id,
            request_key: key,
            text: sentText,
            ...(draft.finding_reference ? {finding_reference:draft.finding_reference} : {}),
            question_id: document.querySelector("#chat-question").value,
          },
        });
        if (textarea.value === sentText) {
          store.remove(draftKey);
          textarea.value = "";
          syncChatComposer();
        }
        state.scrollToTurn = sent.id;
      } catch (e) {
        toast(e.message);
      } finally {
        sending = false;
        signature = "";
        await refresh();
      }
    });
  document.querySelector("#main").addEventListener("click", async (event) => {
    const button = event.target.closest(
      "[data-retry],[data-report],[data-fact],[data-evidence-anchor]",
    );
    if (!button || !current) return;
    if (button.dataset.evidenceAnchor) { event.preventDefault(); const section = document.getElementById(button.dataset.evidenceAnchor); section?.setAttribute("tabindex", "-1"); section?.focus(); return; }
    button.disabled = true;
    const action = button.dataset.retry
      ? "retry"
      : button.dataset.report
        ? "report"
        : "resolve";
    try {
      await api("/api/chats/" + id + "/" + action, {
        method: "POST",
        body: {
          business_id: current.conversation.business_id,
          turn_id: button.dataset.retry || button.dataset.report,
          request_key: crypto.randomUUID(),
          fact_id: button.dataset.fact,
          revision: Number(button.dataset.revision),
          alternative: Number(button.dataset.alternative),
        },
      });
      signature = "";
      await refresh();
    } catch (e) {
      toast(e.message);
      button.disabled = false;
    }
  });
  await refresh();
  if (generation === state.generation) state.poll = setInterval(refresh, 3000);
}

function composerBounds() {
  const card = document.querySelector(".dashboard-compose .composer-card, .chat-composer .composer-card");
  const rect = card?.getBoundingClientRect();
  return rect ? { left: rect.left, top: rect.top, width: rect.width } : null;
}
function animateComposerRoute(origin, fromCentered, toCentered) {
  if (!origin || fromCentered === toCentered || window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches) return;
  const composer = document.querySelector(".dashboard-compose, .chat-composer");
  const card = composer?.querySelector(".composer-card");
  if (!card) return;
  const target = card.getBoundingClientRect();
  const dx = origin.left - target.left, dy = origin.top - target.top;
  const scale = origin.width / target.width;
  composer.style.setProperty("--composer-start", `${toCentered ? "" : "translateX(-50%) "}translate3d(${dx}px, ${dy}px, 0) scale(${scale})`);
  composer.style.setProperty("--composer-end", toCentered ? "none" : "translateX(-50%)");
  composer.classList.add("composer-in-motion");
  composer.addEventListener("animationend", event => {
    if (event.target === composer) {
      composer.classList.remove("composer-in-motion");
      composer.style.removeProperty("--composer-start");
      composer.style.removeProperty("--composer-end");
    }
  }, { once: true });
  if (toCentered) {
    document.querySelector("#main")?.classList.add("is-arriving");
  }
}
const composerTransitionKey = "dr-composer-transition";
function takeComposerTransition() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(composerTransitionKey));
    sessionStorage.removeItem(composerTransitionKey);
    if (location.hash === "#ask" && saved?.origin && Date.now() - saved.at < 2000) return saved;
  } catch {}
  return { origin: composerBounds(), fromCentered: !!document.querySelector("#main.new-chat-page") };
}
async function route(transition = {}) {
  clearInterval(state.poll);
  state.chatFollowController?.abort();
  state.chatFollowController = null;
  state.generation++;
  document.querySelector("#main")?.setAttribute("inert", "");
  document.querySelector("#live-status").textContent = "";
  state.signature = "";
  const generation = state.generation;
  const hash = location.hash.slice(1) || "home";
  try {
    const data = await api("/api/workspace");
    if (generation !== state.generation) return;
    state.analyses = data.analyses;
    state.configured = data.configured;
    state.business = data.business;
    state.businesses = data.businesses;
    state.memory = data.memory;
    const chats = await api("/api/chats");
    if (generation !== state.generation) return;
    if (chats.business_id !== (state.business?.id || null)) { await route(); return; }
    state.chats = chats.conversations;
    state.deletedChats = chats.deleted_conversations || [];
    state.datasets = chats.datasets;
    const activeId = data.business?.id || null;
    if (state.draftBusiness !== activeId) {
      state.draftBusiness = activeId;
      state.draft = activeId ? store.get("dr-draft-" + activeId) : {};
      state.selectedReport = null;
      state.dashboard = null;
      state.file = null;
      state.requestKey = null;
    }
    if (hash === "business-new") businessForm(true);
    else if (hash === "businesses" || (!state.business && state.businesses.length)) businessChooser();
    else if (!state.business) businessForm(true);
    else if (hash === "business") businessForm(!state.business);
    else if (hash === "my-business") await myBusiness();
    else if (hash === "new") newAnalysis();
    else if (hash === "chats" || hash === "ask") await chatsPage();
    else if (hash.startsWith("chat/")) await chatPage(hash.slice(5));
    else if (hash.startsWith("analysis/")) {
      const id = hash.slice(9);
      await pollDetail(id);
      state.poll = setInterval(() => pollDetail(id), 3000);
    } else if (hash === "files") await files();
    else if (hash === "reports") reportsView();
    else if (hash === "how") how();
    else if (hash === "analyses") home(true);
    else {
      const dashboard = await api("/api/dashboard" + (state.selectedReport ? "?report=" + encodeURIComponent(state.selectedReport) : ""));
      if (generation !== state.generation) return;
      state.dashboard = dashboard;
      state.selectedReport = state.dashboard.selected_id;
      dashboardHome();
    }
    if (generation !== state.generation) return;
    if (state.business && ["home", "analyses", "reports"].includes(hash))
      state.poll = setInterval(async () => {
        try {
          const next = await api("/api/workspace");
          if (generation !== state.generation) return;
          const listPage = ["home", "analyses", "reports"].includes(hash);
          if (next.business?.id !== state.business?.id || next.business?.profile_revision !== state.business?.profile_revision) {
            if (listPage) await route();
            return;
          }
          if (hash === "home" && !state.launching) {
            const selected = state.selectedReport;
            const [dashboard, chats] = await Promise.all([
              api("/api/dashboard" + (state.selectedReport ? "?report=" + encodeURIComponent(state.selectedReport) : "")),
              api("/api/chats")
            ]);
            if (generation !== state.generation) return;
            if (selected !== state.selectedReport || state.launching) return;
            if (chats.business_id !== (state.business?.id || null)) { await route(); return; }
            const changed = JSON.stringify(dashboard) !== JSON.stringify(state.dashboard) || JSON.stringify(chats.conversations) !== JSON.stringify(state.chats);
            state.chats = chats.conversations;
            state.datasets = chats.datasets;
            if (changed) {
              const focused = document.activeElement?.id;
              const activityOpen = document.querySelector(".daily-activity")?.open;
              const start = document.activeElement?.selectionStart, end = document.activeElement?.selectionEnd;
              state.dashboard = dashboard;
              state.selectedReport = dashboard.selected_id;
              state.analyses = next.analyses;
              state.memory = next.memory;
              dashboardHome();
              const activity = document.querySelector(".daily-activity");
              if (activity && activityOpen != null) activity.open = activityOpen;
              if (focused) {
                const control = document.getElementById(focused);
                control?.focus({preventScroll:true});
                if (control?.tagName === "TEXTAREA") control.setSelectionRange(start, end);
              }
            }
          }
          if (JSON.stringify(next.memory) !== JSON.stringify(state.memory)) {
            state.memory = next.memory;
            renderMemory();
          }
          if (
            listPage && JSON.stringify(next.analyses) !== JSON.stringify(state.analyses)
          ) {
            state.analyses = next.analyses;
            if (hash === "home") { if (!state.launching) dashboardHome(); }
            else if (hash === "files") await files();
            else if (hash === "reports") {
              const focused = document.activeElement?.id, start = document.activeElement?.selectionStart;
              reportsView(); const control = document.getElementById(focused);
              control?.focus({preventScroll:true}); if (control?.type === "search") control.setSelectionRange(start, start);
            }
            else if (hash === "my-business") await myBusiness();
            else home(true);
          }
        } catch {}
      }, 5000);
    window.scrollTo(0, 0);
    if (hash === "ask") document.querySelector("#dashboard-prompt")?.focus();
    else document.querySelector("#main")?.focus({ preventScroll: true });
    animateComposerRoute(transition.origin, transition.fromCentered, hash === "ask");
    document.title =
      "Decision Room — " +
      (hash === "new"
        ? "Nuevo análisis"
        : hash.startsWith("analysis/")
          ? "Tu análisis"
        : hash === "home" ? "Inicio" : hash === "my-business" ? "Mi negocio" : hash === "reports" ? "Informes" : hash === "ask" ? "Nuevo chat" : "Mi espacio");
  } catch (e) {
    if (generation !== state.generation) return;
    if (e.status === 401) login();
    else
      shell(
        `<section class="card status-card"><h1>Tu espacio está en pausa.</h1><p>${esc(e.message)}</p><button class="button primary" id="reconnect">Volver a conectar</button></section>`,
      );
    document.querySelector("#reconnect")?.addEventListener("click", route);
  }
}
window.addEventListener("hashchange", () => route(takeComposerTransition()));
app.addEventListener("click", event => {
  const link = event.target.closest?.('a[href="#ask"]');
  if (!link || location.hash === "#ask" || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const origin = composerBounds();
  if (!origin) return;
  try { sessionStorage.setItem(composerTransitionKey, JSON.stringify({ origin, fromCentered: false, at: Date.now() })); } catch {}
});
document.querySelector(".skip").addEventListener("click", (event) => {
  event.preventDefault();
  document.querySelector("#main")?.focus();
});
(async () => {
  if (location.hash.startsWith("#access=")) {
    const token = location.hash.slice(8);
    history.replaceState(null, "", "/#home");
    try {
      await api("/api/login", { method: "POST", body: { token } });
    } catch (e) {
      login(e.message);
      return;
    }
  }
  await route(takeComposerTransition());
})();
