"use strict";

// The first report is a separate, resumable journey. The analysis and report
// are still produced by the same durable service used elsewhere in the app.
function onboardingShell(content, stage, mode = "general") {
  const steps = [
    ["name", "Nombre"], ["context", "Tu negocio"], ["purpose", "Informe"],
    ...(mode === "specific" ? [["goal", "Tu pregunta"]] : []),
    ["file", "Tus datos"], ["report", "Resultado"],
  ];
  const current = steps.findIndex(([key]) => key === stage);
  app.innerHTML = `<div class="first-run-layout"><header class="first-run-header"><a class="brand" href="#home" aria-label="Decision Room, inicio"><span class="brand-mark">d<span>r</span></span><span>decision<span class="brand-light">room</span></span></a><span class="first-run-local">${icon("shield")} Espacio local</span></header>
    <nav class="first-run-progress-nav" aria-label="Progreso del onboarding"><ol class="first-run-steps">${steps.map(([key, label], index) => `<li class="${index === current ? "current" : index < current ? "done" : ""}" ${index === current ? 'aria-current="step"' : ""}><span class="first-run-segment" aria-hidden="true"></span><span class="first-run-step-label">${label}</span></li>`).join("")}</ol><p>Paso ${current + 1} de ${steps.length}</p></nav>
    <main id="main" class="first-run ${stage === "report" ? "first-run-wide" : ""}" tabindex="-1">${content}</main></div>`;
}

function goOnboarding(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

function businessDraft() {
  const current = state.business;
  const key = "dr-first-business-" + (current?.id || "new");
  const draft = store.get(key, current ? {name: current.name, description: current.description} : {});
  return {current, key, draft, requestKey: draft.request_key || crypto.randomUUID()};
}

function onboardingBusiness() {
  const {key, draft, requestKey} = businessDraft();
  onboardingShell(`<section class="first-run-stage first-run-name"><p class="eyebrow">EMPECEMOS POR LO ESENCIAL</p><h1>Cuéntanos sobre <em>tu negocio.</em></h1><form id="first-name-form"><label for="first-name">¿Cómo se llama tu negocio?</label><input id="first-name" name="name" maxlength="100" required autocomplete="organization" value="${esc(draft.name)}" placeholder="Por ejemplo, Papelería La Esquina" autofocus><div class="first-run-actions"><button class="button primary" type="submit">Continuar ${icon("arrow")}</button></div></form></section>`, "name");
  const form = document.querySelector("#first-name-form");
  const save = () => store.set(key, {...draft, name: form.elements.name.value, request_key: requestKey});
  form.oninput = save;
  form.onsubmit = event => { event.preventDefault(); save(); goOnboarding("#onboarding/context"); };
}

function onboardingContext() {
  const {current, key, draft, requestKey} = businessDraft();
  const name = (draft.name || current?.name || "").trim();
  if (!name) { goOnboarding("#onboarding/name"); return; }
  onboardingShell(`<section class="first-run-stage first-run-context"><p class="eyebrow">${esc(name)} · UN POCO DE CONTEXTO</p><h1>Cuéntanos más sobre <em>tu negocio.</em></h1><p class="first-run-lead">Dónde está, qué vendes, quién suele venir y cómo es un día normal. Cuantos más detalles nos des, mejor conoceremos tu negocio.</p><div class="first-run-example"><strong>Por ejemplo</strong><p>«Mi papelería está en Valencia, cerca de un colegio. Abrimos de lunes a sábado; vendemos material escolar, artículos de oficina y pequeños regalos. En septiembre suele haber más movimiento por la vuelta a clase».</p></div><form id="first-business-form"><label for="first-description">Cuéntanos todo lo que consideres importante</label><textarea id="first-description" name="description" rows="10" maxlength="6000" required placeholder="Dónde estás, cuándo abres, qué vendes, quiénes son tus clientes…">${esc(draft.description ?? current?.description ?? "")}</textarea><p class="field-help">Puedes ampliar este campo mientras escribes. También podrás corregirlo más adelante.</p><div id="first-business-error" role="alert"></div><div class="first-run-actions"><a class="button secondary" href="#onboarding/name">Volver</a><button class="button primary" type="submit">Continuar ${icon("arrow")}</button></div></form></section>`, "context");
  const form = document.querySelector("#first-business-form");
  const description = form.elements.description;
  const grow = () => { description.style.height = "auto"; description.style.height = Math.max(description.scrollHeight, 260) + "px"; };
  const values = () => ({name, description: description.value, request_key: requestKey});
  grow();
  form.oninput = () => { store.set(key, values()); grow(); };
  form.onsubmit = async event => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    const body = current
      ? {...values(), business_id: current.id, profile_revision: current.profile_revision}
      : {...values(), expected_active_id: null, onboarding: true};
    store.set(key, values());
    try {
      await api("/api/business", {method: "POST", body});
      store.remove(key);
      goOnboarding("#onboarding/purpose");
    } catch (error) {
      document.querySelector("#first-business-error").innerHTML = errorBox(error.message);
      button.disabled = false;
    }
  };
}

function onboardingPurpose() {
  const business = state.business;
  const key = "dr-first-data-" + business.id;
  const draft = store.get(key, {});
  const mode = draft.mode === "specific" ? "specific" : "general";
  onboardingShell(`<section class="first-run-stage"><p class="eyebrow">TU PRIMER INFORME</p><h1>¿Qué te gustaría <em>descubrir?</em></h1><p class="first-run-lead">Elige por dónde empezamos. Podrás hacer más preguntas después.</p><form id="first-purpose-form"><fieldset><legend class="sr-only">Tipo de informe</legend><label class="first-run-choice"><input type="radio" name="mode" value="general" ${mode === "general" ? "checked" : ""}><span><strong>Quiero un informe general</strong><small>Explorar los datos y destacar lo que merece atención.</small></span></label><label class="first-run-choice"><input type="radio" name="mode" value="specific" ${mode === "specific" ? "checked" : ""}><span><strong>Tengo una pregunta concreta</strong><small>Enfocar el primer informe en lo que quieres averiguar.</small></span></label></fieldset><div class="first-run-actions"><a class="button secondary" href="#onboarding/context">Volver</a><button class="button primary" type="submit">Continuar ${icon("arrow")}</button></div></form></section>`, "purpose", mode);
  const form = document.querySelector("#first-purpose-form");
  form.onchange = () => store.set(key, {...draft, mode: new FormData(form).get("mode")});
  form.onsubmit = event => {
    event.preventDefault();
    const selected = new FormData(form).get("mode");
    store.set(key, {...draft, mode: selected});
    goOnboarding(selected === "specific" ? "#onboarding/goal" : "#onboarding/data");
  };
}

function onboardingGoal() {
  const key = "dr-first-data-" + state.business.id;
  const draft = store.get(key, {});
  if (draft.mode !== "specific") { goOnboarding("#onboarding/purpose"); return; }
  onboardingShell(`<section class="first-run-stage"><p class="eyebrow">TU PREGUNTA</p><h1>¿Qué quieres <em>saber?</em></h1><p class="first-run-lead">Escribe una pregunta que te gustaría resolver con tus datos.</p><form id="first-goal-form"><label for="first-goal">Tu pregunta</label><textarea id="first-goal" rows="4" maxlength="2000" required placeholder="Por ejemplo, ¿cómo cambiaron las ventas durante el mes?">${esc(draft.goal)}</textarea><div class="first-run-actions"><a class="button secondary" href="#onboarding/purpose">Volver</a><button class="button primary" type="submit">Continuar ${icon("arrow")}</button></div></form></section>`, "goal", "specific");
  const form = document.querySelector("#first-goal-form");
  form.oninput = () => store.set(key, {...draft, goal: form.querySelector("#first-goal").value});
  form.onsubmit = event => {
    event.preventDefault();
    store.set(key, {...draft, goal: form.querySelector("#first-goal").value.trim()});
    goOnboarding("#onboarding/data");
  };
}

function onboardingData() {
  const business = state.business;
  const key = "dr-first-data-" + business.id;
  const draft = store.get(key, {});
  const requestKey = draft.request_key || crypto.randomUUID();
  const mode = draft.mode === "specific" ? "specific" : "general";
  if (mode === "specific" && !draft.goal?.trim()) { goOnboarding("#onboarding/goal"); return; }
  onboardingShell(`<section class="first-run-stage"><p class="eyebrow">TUS DATOS</p><h1>Vamos a mirar <em>tus datos.</em></h1><p class="first-run-lead">Sube un CSV para preparar tu primer informe. El agente te preguntará si necesita aclarar algo.</p><form id="first-data-form"><label for="first-csv">Elige tu primer archivo</label><input id="first-csv" type="file" accept=".csv,text/csv" aria-describedby="first-file-help"><p id="first-file-help" class="field-help">CSV UTF-8 de hasta 20 MB. Más adelante podrás añadir otros archivos.</p><div id="first-file-selected"></div><button type="button" class="text-button" id="first-sample">Usar datos ficticios de ejemplo</button><div id="first-data-error" role="alert"></div><div class="first-run-actions"><a class="button secondary" href="${mode === "specific" ? "#onboarding/goal" : "#onboarding/purpose"}">Volver</a><button class="button primary" type="submit">Empezar el análisis ${icon("arrow")}</button></div></form></section>`, "file", mode);
  const form = document.querySelector("#first-data-form");
  const showFile = () => {
    document.querySelector("#first-file-selected").textContent = state.onboardingFile
      ? `${state.onboardingFile.name} · ${size(state.onboardingFile.size)}` : "Todavía no has seleccionado un archivo.";
  };
  document.querySelector("#first-csv").onchange = event => {
    state.onboardingFile = event.target.files[0] || null;
    showFile();
  };
  document.querySelector("#first-sample").onclick = async event => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const response = await fetch("/api/sample", {credentials: "same-origin"});
      if (!response.ok) throw new Error("No se pudieron cargar los datos de ejemplo.");
      state.onboardingFile = new File([await response.blob()], "ventas-ejemplo.csv", {type: "text/csv"});
      showFile();
    } catch (error) {
      document.querySelector("#first-data-error").innerHTML = errorBox(error.message);
    } finally {
      button.disabled = false;
    }
  };
  form.onsubmit = async event => {
    event.preventDefault();
    const file = state.onboardingFile;
    const goal = mode === "specific" ? draft.goal.trim() : "";
    const error = document.querySelector("#first-data-error");
    if (!file) { error.innerHTML = errorBox("Selecciona un archivo CSV para continuar."); return; }
    if (!file.name.toLowerCase().endsWith(".csv") || file.size > 20 * 1024 ** 2) {
      error.innerHTML = errorBox("Selecciona un CSV de hasta 20 MB."); return;
    }
    if (!state.configured) {
      error.innerHTML = errorBox("El modelo local aún no está configurado. Tu contexto está guardado; vuelve cuando esté disponible."); return;
    }
    store.set(key, {...draft, mode, request_key: requestKey});
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = "Guardando el archivo…";
    const body = new FormData();
    body.append("metadata", JSON.stringify({request_key: requestKey, business_id: business.id,
      profile_revision: business.profile_revision, onboarding: true, goal,
      title: goal ? goal.slice(0, 160) : `Primera exploración de ${business.name}`.slice(0, 160)}));
    body.append("file", file);
    try {
      await api("/api/jobs", {method: "POST", body});
      store.remove(key);
      state.onboardingFile = null;
      goOnboarding("#onboarding/progress");
    } catch (caught) {
      error.innerHTML = errorBox(caught.message);
      button.disabled = false;
      button.innerHTML = "Volver a intentar " + icon("arrow");
    }
  };
  showFile();
}

let previewJobId = null;
let previewOffset = 0;

function referencedColumns(question, columns) {
  const cited = (question.references || []).filter(ref => ref.kind === "column")
    .map(ref => String(ref.column).normalize("NFKC").toLocaleLowerCase("es"));
  const linked = columns.map((name, index) => cited.includes(String(name).normalize("NFKC").toLocaleLowerCase("es")) ? index : -1)
    .filter(index => index !== -1);
  if (linked.length) return linked;
  const source = `${question.text || ""} ${question.reason || ""}`.normalize("NFKC").toLocaleLowerCase("es");
  const word = character => /[\p{L}\p{N}_]/u.test(character || "");
  return columns.map((name, index) => {
    const needle = String(name).normalize("NFKC").toLocaleLowerCase("es");
    if (!needle) return -1;
    let at = source.indexOf(needle);
    while (at !== -1) {
      if (!word(source[at - 1]) && !word(source[at + needle.length])) return index;
      at = source.indexOf(needle, at + 1);
    }
    return -1;
  }).filter(index => index !== -1);
}

async function loadOnboardingPreview(jobId, question, offset = previewOffset) {
  const box = document.querySelector("#first-data-preview");
  if (!box) return;
  if (previewJobId !== jobId) {
    previewJobId = jobId;
    previewOffset = 0;
    offset = 0;
  }
  box.innerHTML = `<p class="eyebrow">TUS DATOS</p><p class="first-run-preview-state">Abriendo la tabla…</p>`;
  try {
    const preview = await api(`/api/jobs/${encodeURIComponent(jobId)}/preview?offset=${offset}`);
    if (!box.isConnected || state.onboarding?.job_id !== jobId) return;
    previewOffset = offset;
    const highlighted = referencedColumns(question, preview.columns);
    const note = highlighted.length
      ? `Esta pregunta se refiere a ${highlighted.map(i => `<strong>${esc(preview.columns[i])}</strong>`).join(", ")}. Hemos señalado ${highlighted.length === 1 ? "esa columna" : "esas columnas"} en la tabla.`
      : "No podemos señalar una columna concreta con seguridad. Revisa las cabeceras y las filas antes de responder.";
    box.innerHTML = `<div class="first-run-data-heading"><div><p class="eyebrow">TUS DATOS</p><h2>Consulta tu archivo</h2><p>${esc(preview.filename)}</p></div><span class="first-run-data-badge">CSV</span></div>
      <p class="first-run-data-note">${note}</p><div class="first-run-table-scroll" role="region" tabindex="0" aria-label="Filas del CSV, desplazamiento horizontal disponible"><table class="first-run-table"><thead><tr><th scope="col">Fila</th>${preview.columns.map((column, i) => `<th scope="col" class="${highlighted.includes(i) ? "is-referenced" : ""}" ${highlighted.includes(i) ? 'title="Columna relacionada con la pregunta"' : ""}>${esc(column)}</th>`).join("")}</tr></thead><tbody>${preview.rows.map(row => `<tr><th scope="row">${row.number}</th>${preview.columns.map((_, i) => `<td class="${highlighted.includes(i) ? "is-referenced" : ""}">${esc(row.cells[i] ?? "")}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${preview.columns.length + 1}">No hay más filas en este archivo.</td></tr>`}</tbody></table></div>
      <div class="first-run-table-footer"><span>Filas ${preview.rows.length ? preview.rows[0].number : offset + 1}–${preview.rows.length ? preview.rows.at(-1).number : offset} · Vista de 30 filas</span><div><button type="button" id="first-preview-prev" ${offset === 0 ? "disabled" : ""} aria-label="Filas anteriores">Anterior</button><button type="button" id="first-preview-next" ${!preview.has_more ? "disabled" : ""} aria-label="Filas siguientes">Siguiente</button></div></div><p class="first-run-preview-footnote">Las celdas largas se cortan a 200 caracteres en esta vista. <a href="/api/jobs/${encodeURIComponent(jobId)}/file">Descargar CSV original ${icon("download")}</a></p>`;
    box.querySelector("#first-preview-prev").onclick = () => loadOnboardingPreview(jobId, question, Math.max(0, offset - 30));
    box.querySelector("#first-preview-next").onclick = () => loadOnboardingPreview(jobId, question, offset + preview.rows.length);
  } catch (error) {
    if (!box.isConnected) return;
    box.innerHTML = `<p class="eyebrow">TUS DATOS</p><p class="first-run-preview-state">${esc(error.message)}</p><button type="button" class="button secondary" id="first-preview-retry">Volver a abrir la tabla</button>`;
    box.querySelector("#first-preview-retry").onclick = () => loadOnboardingPreview(jobId, question, offset);
  }
}

function onboardingProgress(data) {
  const question = data.questions?.[0];
  let content;
  if (data.status === "waiting" && question) {
    const saved = store.get("dr-answer-" + data.id + "-" + question.id, {text: "", disposition: "answered"});
    content = `<div class="first-run-question-layout"><section class="card first-run-card first-run-progress"><p class="eyebrow">UNA ACLARACIÓN PARA SEGUIR</p><h1>${esc(question.text)}</h1><p class="first-question-reason">${esc(question.reason)}</p><button class="first-run-data-jump" id="first-data-jump" type="button">${icon("grid")} Ver mis datos ${icon("arrow")}</button><form id="answer-form">${answerFields(question, saved, 4)}<p class="field-help">Si no lo sabes, seguiremos con los datos disponibles y lo indicaremos en el informe.</p><div id="answer-error" role="alert"></div><button class="button primary" type="submit">Guardar y continuar ${icon("arrow")}</button></form></section><aside class="first-run-data" id="first-data-preview" aria-label="Vista del CSV"><p class="eyebrow">TUS DATOS</p><p>Cargando el archivo…</p></aside></div>`;
  } else if (data.publishable) {
    content = `<section class="first-run-report"><p class="eyebrow">TU PRIMER INFORME</p><h1>Ya tienes un punto <em>de partida.</em></h1><p>El agente ha revisado los datos y tus respuestas. Lee el informe y comprueba las cifras antes de pasar a tu espacio.</p><div class="first-run-report-actions"><a class="button secondary" href="/api/jobs/${encodeURIComponent(data.id)}/report" target="_blank" rel="noopener">Abrir informe completo ${icon("external")}</a><button class="button primary" id="first-finish">Entrar a mi espacio ${icon("arrow")}</button></div><div id="first-finish-error"></div><p class="report-caveat">Informe elaborado con IA y revisión automática. Consulta el alcance, las limitaciones y la evidencia antes de tomar decisiones.</p><iframe id="first-report-frame" class="report-frame" title="Primer informe de ${esc(data.business)}" src="/api/jobs/${encodeURIComponent(data.id)}/report" sandbox="allow-same-origin"></iframe></section>`;
  } else if (data.status === "failed" || data.status === "blocked") {
    content = `<section class="card first-run-card first-run-progress"><p class="eyebrow">TU TRABAJO ESTÁ GUARDADO</p><h1>El análisis se ha detenido.</h1><p>${esc(data.issue || "No se pudo entregar un informe revisado con estos datos.")}</p><div id="first-progress-error"></div><div class="first-run-report-actions">${data.status === "failed" ? `<button class="button primary" id="first-retry">${data.context_stale ? "Recalcular con la memoria actual" : "Reintentar análisis"} ${icon("arrow")}</button>` : ""}<button class="button secondary" id="first-restart">Empezar con otro archivo</button></div>${data.status === "failed" ? '<p class="field-help">Una petición interrumpida al modelo puede ejecutarse de nuevo al reintentar.</p>' : ""}</section>`;
  } else {
    content = `<section class="card first-run-card first-run-progress"><div class="working-symbol">${icon("spark")}</div><p class="eyebrow">PREPARANDO TU PRIMER INFORME</p><h1>${esc(phases[data.phase] || "Estamos analizando tus datos")}</h1><p>El agente está contrastando tu contexto con el archivo. Si necesita aclarar algo importante, te preguntará aquí antes de crear el informe.</p>${data.activity ? `<p class="progress-update">${esc(data.activity)}</p>` : ""}<p class="field-help">Puedes cerrar esta página y volver. El trabajo continúa mientras el servidor local esté encendido.</p></section>`;
  }
  onboardingShell(`<div class="first-run-result"><p class="eyebrow"><span class="tiny-line"></span> TU PRIMER INFORME · ${esc(data.business)}</p>${content}</div>`, "report", data.goal ? "specific" : "general");
  document.querySelector("#first-data-jump")?.addEventListener("click", () =>
    document.querySelector("#first-data-preview")?.scrollIntoView({behavior: "smooth", block: "start"}));
  if (question && data.status === "waiting") {
    setupAnswer(data, question, pollOnboarding);
    loadOnboardingPreview(data.id, question);
  }
  const finish = document.querySelector("#first-finish");
  if (finish) finish.onclick = async () => {
    finish.disabled = true;
    try {
      await api("/api/onboarding/complete", {method: "POST", body: {}});
      if (location.hash === "#home") await route();
      else location.hash = "#home";
    } catch (error) {
      document.querySelector("#first-finish-error").innerHTML = errorBox(error.message);
      finish.disabled = false;
    }
  };
  const retry = document.querySelector("#first-retry");
  if (retry) retry.onclick = async () => {
    retry.disabled = true;
    try {
      await api(`/api/jobs/${encodeURIComponent(data.id)}/retry`, {method: "POST", body: {}});
      state.signature = "";
      await pollOnboarding(data.id);
    } catch (error) {
      document.querySelector("#first-progress-error").innerHTML = errorBox(error.message);
      retry.disabled = false;
    }
  };
  const restart = document.querySelector("#first-restart");
  if (restart) restart.onclick = async () => {
    restart.disabled = true;
    try {
      await api("/api/onboarding/restart", {method: "POST", body: {}});
      if (location.hash === "#onboarding/data") await route();
      else location.hash = "#onboarding/data";
    } catch (error) {
      document.querySelector("#first-progress-error").innerHTML = errorBox(error.message);
      restart.disabled = false;
    }
  };
  const frame = document.querySelector("#first-report-frame");
  if (frame) frame.onload = () => {
    const doc = frame.contentDocument;
    if (doc?.body) {
      const resize = () => { frame.style.height = Math.ceil(doc.body.getBoundingClientRect().height) + 4 + "px"; };
      resize();
      new ResizeObserver(resize).observe(doc.body);
    }
  };
}

async function pollOnboarding(id) {
  const generation = state.generation;
  try {
    const {memory, ...data} = await api("/api/jobs/" + encodeURIComponent(id));
    if (generation !== state.generation) return;
    state.memory = memory;
    const signature = JSON.stringify(data);
    if (signature !== state.signature) {
      state.signature = signature;
      onboardingProgress(data);
    }
  } catch (error) {
    if (generation !== state.generation) return;
    if (error.status === 401) {
      clearInterval(state.poll);
      login();
    } else {
      onboardingShell(`<section class="card first-run-card first-run-progress"><h1>No pudimos abrir tu análisis.</h1><p>${esc(error.message)}</p><button class="button secondary" id="first-reload">Volver a intentar</button></section>`, "report");
      document.querySelector("#first-reload").onclick = route;
    }
  }
}
