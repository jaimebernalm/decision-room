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
  step: 1,
  file: null,
  draft: store.get("dr-draft"),
  uploading: false,
  poll: null,
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
  app.innerHTML = `<aside class="sidebar"><a class="brand" href="#home" aria-label="Decision Room, inicio"><span class="brand-mark">d<span>r</span></span><span>decision<span class="brand-light">room</span><small>UN ESPACIO PARA DECIDIR</small></span></a>
    <div class="workspace-label"><span class="workspace-avatar">M</span><span>Mi espacio<small>Espacio de trabajo local</small></span><span class="local-dot"></span></div>
    <p class="nav-label">ESPACIO DE TRABAJO</p><nav aria-label="Principal">${[
      ["home", "home", "Vista general"],
      ["analyses", "grid", "Mis análisis"],
      ["files", "file", "Archivos"],
    ]
      .map(
        ([route, i, label]) =>
          `<a href="#${route}" class="nav-link ${active === route ? "active" : ""}" ${active === route ? 'aria-current="page"' : ""}>${icon(i)}${label}${route === "analyses" && state.analyses.length ? `<span class="nav-count">${state.analyses.length}</span>` : ""}</a>`,
      )
      .join("")}</nav>
    <a href="#new" class="button sidebar-create">${icon("plus")} Nuevo análisis</a>
    <div class="sidebar-bottom"><div class="private-note">${icon("shield")}<strong>Tu espacio, en local</strong><p>Los archivos y el progreso se guardan en este equipo.</p></div><a class="nav-link" href="#how">${icon("help")} Cómo funciona</a><div class="profile"><span>ME</span><div>Mi espacio personal<small>Versión de pruebas</small></div></div></div></aside>
    <div class="workspace"><header class="topbar"><span class="breadcrumb">Mi espacio <span>/</span> <b>${esc(crumb)}</b></span><span class="environment"><i></i> Entorno local <span class="beta">BETA</span></span></header><main id="main" tabindex="-1">${content}</main><footer class="page-footer"><span>Decision Room</span><span>De los datos a decisiones con contexto.</span></footer></div>`;
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
  store.set("dr-draft", state.draft);
  state.requestKey = null;
}
function newAnalysis() {
  const d = state.draft;
  shell(
    `<a href="#home" class="back-link">${icon("back")} Volver a mis análisis</a><div class="page-heading form-heading"><div><p class="eyebrow">UN NUEVO PUNTO DE VISTA</p><h1>Empecemos por <em>tu negocio.</em></h1><p>No necesitas preparar un informe. Solo contarnos un poco y compartir tus datos.</p></div></div><div class="form-layout"><section class="card form-card"><ol class="form-steps"><li class="${state.step === 1 ? "current" : "complete"}"><span>${state.step > 1 ? icon("check") : "1"}</span> Contexto del negocio</li><li class="${state.step === 2 ? "current" : ""}"><span>2</span> Datos y revisión</li></ol><form id="new-form">
    ${state.step === 1 ? `<div class="form-section"><h2>Las cifras necesitan contexto.</h2><p class="subtle">Ayúdanos a entender qué hay detrás de tu archivo.</p><label for="business">¿Cómo se llama tu negocio?</label><input id="business" name="business" value="${esc(d.business)}" maxlength="100" required placeholder="Por ejemplo, La Esquina Verde" autocomplete="organization"><label for="context">Cuéntanos a qué te dedicas <span>Obligatorio</span></label><textarea id="context" name="context" rows="4" maxlength="6000" required placeholder="Qué vendes, cómo funciona tu negocio y qué información recoge el archivo…">${esc(d.context)}</textarea><p class="field-help">Lo que tú sabes del negocio nos ayuda a no asumir lo que los datos no dicen.</p><fieldset><legend>¿Qué te gustaría averiguar?</legend><label class="choice ${d.mode !== "specific" ? "chosen" : ""}"><input type="radio" name="mode" value="general" ${d.mode !== "specific" ? "checked" : ""}><span><strong>Explorar mis datos</strong><small>Identificar patrones y observaciones que merezcan atención.</small></span>${icon("spark")}</label><label class="choice ${d.mode === "specific" ? "chosen" : ""}"><input type="radio" name="mode" value="specific" ${d.mode === "specific" ? "checked" : ""}><span><strong>Tengo una pregunta concreta</strong><small>Orientar el análisis hacia algo que quieres entender.</small></span>${icon("chat")}</label></fieldset><div id="goal-field" ${d.mode !== "specific" ? "hidden" : ""}><label for="goal">Tu pregunta</label><textarea id="goal" name="goal" rows="2" maxlength="160" ${d.mode === "specific" ? "required" : ""} placeholder="Por ejemplo, ¿cómo han cambiado mis ventas durante este mes?">${esc(d.goal)}</textarea></div></div>` : `<div class="form-section"><h2>Ahora, tus datos.</h2><p class="subtle">Un archivo es suficiente para empezar a hacer buenas preguntas.</p><label for="title">Nombre del análisis</label><input id="title" name="title" required maxlength="160" value="${esc(d.title || (d.mode === "specific" ? d.goal : "Exploración de " + (d.business || "mi negocio")))}"><div class="dropzone" id="dropzone"><span class="upload-icon">${icon("upload")}</span><h3>Arrastra tu CSV hasta aquí</h3><p>O selecciónalo desde tu equipo</p><label class="button secondary file-picker" for="csv">Elegir archivo CSV<input type="file" id="csv" accept=".csv,text/csv" aria-label="Elegir archivo CSV"></label><small>1 archivo CSV · UTF-8 · Máximo 20 MB</small></div><div id="selected-file"></div><div class="sample-row"><span>¿Solo quieres probar el recorrido?</span><button type="button" class="text-button" id="use-sample">Usar datos de ejemplo ${icon("arrow")}</button></div><div class="review-context"><span class="eyebrow">ESTE ES EL PUNTO DE PARTIDA</span><h3>${esc(d.business)}</h3><p>${esc(d.context)}</p><span class="goal-pill">${icon(d.mode === "specific" ? "chat" : "spark")}${esc(d.mode === "specific" ? d.goal : "Exploración general")}</span><button type="button" class="text-button" id="edit-context">Editar contexto</button></div><p class="field-help">Antes de calcular, revisaremos el archivo. Si hay algo importante que aclarar, te lo preguntaremos.</p></div>`}
    <div id="form-error"></div><div class="form-actions"><span class="save-hint">${icon("check")} Borrador guardado en este navegador</span>${state.step === 2 ? '<button type="button" class="button ghost" id="previous">Atrás</button>' : ""}<button class="button primary" type="submit" ${state.uploading ? "disabled" : ""}>${state.step === 1 ? "Continuar" : state.uploading ? "Guardando archivo…" : "Empezar análisis"} ${icon("arrow")}</button></div></form></section><aside class="form-aside"><span class="aside-glyph">✳</span><h2>Una conversación<br>con tus datos.</h2><p>No hace falta tener todas las respuestas antes de empezar.</p><div class="aside-item">${icon("chat")}<div><strong>Preguntas con propósito</strong><p>Solo te pediremos aclaraciones que cambien la interpretación.</p></div></div><div class="aside-item">${icon("clock")}<div><strong>A tu ritmo</strong><p>Una vez enviado, puedes salir y volver. Guardamos cada respuesta.</p></div></div><div class="aside-item">${icon("shield")}<div><strong>Sin perder el contexto</strong><p>El informe conecta los hallazgos con tus archivos y aclaraciones.</p></div></div><div class="aside-footnote">PRIMERA VERSIÓN<br><span>Los resultados incluyen revisión automática. El análisis todavía puede cometer errores.</span></div></aside></div>`,
    "analyses",
    "Nuevo análisis",
  );
  const form = document.querySelector("#new-form");
  form.addEventListener("input", (e) => {
    if (!e.target.name) return;
    state.draft[e.target.name] = e.target.value;
    saveDraft();
    if (e.target.name === "mode") {
      const specific = e.target.value === "specific";
      document.querySelector("#goal-field").hidden = !specific;
      document.querySelector("#goal").required = specific;
      document
        .querySelectorAll(".choice")
        .forEach((c) =>
          c.classList.toggle("chosen", c.querySelector("input").checked),
        );
    }
  });
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (state.uploading) return;
    for (const [key, value] of new FormData(form))
      if (key !== "csv" && typeof value === "string") state.draft[key] = value;
    if (state.step === 1) {
      saveDraft();
      state.step = 2;
      newAnalysis();
      window.scrollTo(0, 0);
      return;
    }
    if (!state.file) {
      document.querySelector("#form-error").innerHTML = errorBox(
        "Selecciona un archivo CSV para empezar.",
      );
      document.querySelector("#csv").focus();
      return;
    }
    state.requestKey ||= crypto.randomUUID();
    const body = new FormData();
    body.append(
      "metadata",
      JSON.stringify({
        request_key: state.requestKey,
        business: state.draft.business,
        context: state.draft.context,
        goal: state.draft.mode === "specific" ? state.draft.goal : "",
        title: state.draft.title,
      }),
    );
    body.append("file", state.file);
    state.uploading = true;
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    button.textContent = "Guardando archivo…";
    try {
      const result = await api("/api/jobs", { method: "POST", body });
      store.remove("dr-draft");
      state.draft = {};
      state.file = null;
      state.step = 1;
      state.requestKey = null;
      location.hash = "#analysis/" + result.id;
    } catch (error) {
      document.querySelector("#form-error").innerHTML = errorBox(error.message);
      button.disabled = false;
      button.innerHTML = "Volver a intentar " + icon("arrow");
    } finally {
      state.uploading = false;
    }
  };
  if (state.step === 2) {
    document.querySelector("#previous").onclick = document.querySelector(
      "#edit-context",
    ).onclick = () => {
      state.step = 1;
      newAnalysis();
    };
    document.querySelector("#csv").onchange = (e) =>
      chooseFile(e.target.files[0]);
    const drop = document.querySelector("#dropzone");
    ["dragenter", "dragover"].forEach((event) =>
      drop.addEventListener(event, (e) => {
        e.preventDefault();
        drop.classList.add("dragging");
      }),
    );
    ["dragleave", "drop"].forEach((event) =>
      drop.addEventListener(event, (e) => {
        e.preventDefault();
        drop.classList.remove("dragging");
      }),
    );
    drop.addEventListener("drop", (e) => {
      if (e.dataTransfer.files.length !== 1)
        document.querySelector("#form-error").innerHTML = errorBox(
          "Selecciona un solo archivo CSV.",
        );
      else chooseFile(e.dataTransfer.files[0]);
    });
    document.querySelector("#use-sample").onclick = async () => {
      try {
        const response = await fetch("/api/sample");
        if (!response.ok) throw new Error("No se pudo cargar el ejemplo.");
        const blob = await response.blob();
        chooseFile(
          new File([blob], "ventas-ejemplo.csv", { type: "text/csv" }),
        );
        toast(
          "Datos ficticios de ventas diarias. Revisa que el contexto describa este ejemplo.",
        );
      } catch (e) {
        toast(e.message);
      }
    };
    showFile();
  }
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
    center = `<section class="card status-card"><span class="status-symbol amber">${icon(data.status === "failed" ? "clock" : "shield")}</span><p class="eyebrow">TU TRABAJO SIGUE GUARDADO</p><h2>${data.status === "failed" ? "Hemos hecho una pausa." : "Este análisis necesita atención."}</h2><p>${esc(data.issue)}</p>${data.status === "failed" ? `<button class="button primary" id="retry">Reintentar análisis ${icon("arrow")}</button><p class="field-help">Se recupera el último paso guardado. Una petición al modelo interrumpida puede ejecutarse de nuevo.</p>` : '<a class="button secondary" href="#new">Crear otro análisis</a>'}<div id="retry-error"></div></section>`;
  } else {
    center = `<section class="card status-card"><div class="working-symbol">${icon("spark")}</div><p class="eyebrow">${data.status === "queued" ? "TODO LISTO PARA EMPEZAR" : "ESTAMOS TRABAJANDO EN ELLO"}</p><h2>${data.status === "queued" ? "Tu análisis está en cola." : phases[data.phase]}</h2><p>${{ upload: "Estamos preparando el archivo y comprobando su estructura.", planning: "El agente está revisando tus datos y el contexto. Si falta una definición importante, te preguntará aquí.", research: "El agente está realizando los cálculos que pueden responder a tu pregunta.", review: "Estamos contrastando las conclusiones con los cálculos y su evidencia.", done: "Estamos preparando la presentación de tu informe." }[data.phase]}</p>${data.activity ? `<p class="progress-update">${esc(data.activity)}</p>` : ""}<div class="live-note"><span class="pulse-dot"></span> El estado se actualiza automáticamente</div><div class="leave-note">${icon("shield")} Puedes cerrar esta página. El análisis continúa mientras el servidor local siga encendido.</div></section>`;
  }
  shell(
    `<a class="back-link" href="#analyses">${icon("back")} Todos mis análisis</a><div class="page-heading detail-heading"><div><p class="eyebrow">${esc(data.business)} <span> / </span> ${fmtDate(data.created_at)}</p><h1>${esc(data.title)}</h1></div>${badge(data.status)}</div><div class="detail-layout"><div class="detail-main">${center}${data.interpretations.length && !data.publishable ? `<details class="card interpretation-card"><summary>Lo que estamos entendiendo de tus datos <span>Interpretación provisional</span></summary>${data.interpretations.map((i) => `<p><span class="interpretation-label">${{ observed: "Observado", inferred: "Por comprobar", confirmed: "Confirmado", unresolved: "Por aclarar" }[i.status]}</span>${esc(i.text)}</p>`).join("")}</details>` : ""}${data.answers.length ? `<details class="card answer-history"><summary>Tus aclaraciones guardadas <span>${data.answers.length}</span></summary>${data.answers.map((a) => `<p>${icon("check")}${esc(a.disposition === "answered" ? a.text : a.disposition === "unknown" ? "No tengo esa información." : "Prefiero no responder.")}</p>`).join("")}</details>` : ""}</div><aside class="detail-aside"><section class="card timeline"><p class="eyebrow">EL RECORRIDO</p>${progressSteps(data)}</section><section class="card source-card"><p class="eyebrow">PUNTO DE PARTIDA</p><span class="source-file">${icon("file")}<strong>${esc(data.filename)}</strong></span><small>${size(data.byte_count)}${data.files[0]?.row_count != null ? " · " + data.files[0].row_count.toLocaleString("es-ES") + " filas" : ""}</small><a class="text-button" href="/api/jobs/${data.id}/file">Descargar original ${icon("download")}</a><hr><h3>${data.goal ? "Tu pregunta" : "Exploración general"}</h3><p>${esc(data.goal || "Identificar lo que merece atención en los datos disponibles.")}</p><details><summary>Contexto del negocio</summary><p>${esc(data.context)}</p></details></section><p class="saved-at">${icon("check")} Guardado en tu espacio local</p></aside></div>`,
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
function files() {
  shell(
    `<div class="page-heading"><div><p class="eyebrow">TUS FUENTES, A MANO</p><h1>Archivos<span class="title-dot">.</span></h1><p>Cada original se conserva junto al análisis al que pertenece.</p></div><a class="button primary" href="#new">${icon("plus")} Nuevo análisis</a></div><section class="card files-list">${state.analyses.length ? state.analyses.map((a) => `<div class="file-row"><span class="file-symbol">${icon("file")}</span><div><strong>${esc(a.filename)}</strong><small>${esc(a.business)} · ${size(a.byte_count)} · ${fmtDate(a.created_at)}</small></div><a class="text-button" href="#analysis/${a.id}">Ver análisis ${icon("arrow")}</a><a class="icon-button" href="/api/jobs/${a.id}/file" aria-label="Descargar ${esc(a.filename)}">${icon("download")}</a></div>`).join("") : `<div class="empty"><span class="empty-icon">${icon("file")}</span><div><h3>Aquí estarán tus archivos.</h3><p>Crea tu primer análisis para añadir un CSV a tu espacio.</p></div><a class="button secondary" href="#new">Crear análisis</a></div>`}</section>`,
    "files",
    "Archivos",
  );
}
function how() {
  shell(
    `<div class="page-heading"><div><p class="eyebrow">DE UN ARCHIVO A UNA CONVERSACIÓN</p><h1>Decide con <em>más contexto.</em></h1><p>Un recorrido sencillo, con espacio para las preguntas importantes.</p></div></div><div class="how-grid">${[
      [
        "01",
        "Comparte tu punto de partida",
        "Describe tu negocio, elige una pregunta o una exploración general y sube un CSV. No hace falta reorganizarlo en una plantilla.",
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
      )}</div><section class="notice"><strong>Una primera versión para explorar la experiencia.</strong><p>Esta versión se ejecuta en tu equipo y utiliza el modelo configurado por el operador. Los archivos y el progreso se guardan localmente. La calidad analítica sigue en evaluación: la revisión automática puede no detectar todos los errores. Los filtros analíticos y los archivos Excel llegarán en una ampliación posterior.</p></section><a class="button primary" href="#new">Empezar mi análisis ${icon("arrow")}</a>`,
    "",
    "Cómo funciona",
  );
}
async function pollDetail(id) {
  const generation = state.generation;
  try {
    const data = await api("/api/jobs/" + encodeURIComponent(id));
    if (generation !== state.generation) return;
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
async function route() {
  clearInterval(state.poll);
  state.generation++;
  document.querySelector("#live-status").textContent = "";
  state.signature = "";
  const generation = state.generation;
  const hash = location.hash.slice(1) || "home";
  try {
    const data = await api("/api/workspace");
    if (generation !== state.generation) return;
    state.analyses = data.analyses;
    state.configured = data.configured;
    if (hash === "new") newAnalysis();
    else if (hash.startsWith("analysis/")) {
      const id = hash.slice(9);
      await pollDetail(id);
      state.poll = setInterval(() => pollDetail(id), 3000);
    } else if (hash === "files") files();
    else if (hash === "how") how();
    else home(hash === "analyses");
    if (["home", "analyses", "files"].includes(hash))
      state.poll = setInterval(async () => {
        try {
          const next = await api("/api/workspace");
          if (generation !== state.generation) return;
          if (
            JSON.stringify(next.analyses) !== JSON.stringify(state.analyses)
          ) {
            state.analyses = next.analyses;
            if (hash === "files") files();
            else home(hash === "analyses");
          }
        } catch {}
      }, 5000);
    window.scrollTo(0, 0);
    document.querySelector("#main")?.focus({ preventScroll: true });
    document.title =
      "Decision Room — " +
      (hash === "new"
        ? "Nuevo análisis"
        : hash.startsWith("analysis/")
          ? "Tu análisis"
          : "Mi espacio");
  } catch (e) {
    if (e.status === 401) login();
    else
      shell(
        `<section class="card status-card"><h1>Tu espacio está en pausa.</h1><p>${esc(e.message)}</p><button class="button primary" id="reconnect">Volver a conectar</button></section>`,
      );
    document.querySelector("#reconnect")?.addEventListener("click", route);
  }
}
window.addEventListener("hashchange", route);
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
  await route();
})();
