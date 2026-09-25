"use strict";

// The first report is a separate, resumable journey. The analysis and report
// are still produced by the same durable service used elsewhere in the app.
function onboardingShell(content, step) {
  const labels = ["Tu negocio", "Tus datos", "Primer informe"];
  app.innerHTML = `<div class="first-run-layout"><aside class="first-run-sidebar">
    <a class="brand" href="#home" aria-label="Decision Room, inicio"><span class="brand-mark">d<span>r</span></span><span>decision<span class="brand-light">room</span><small>UN ESPACIO PARA DECIDIR</small></span></a>
    <div class="first-run-workspace-label"><span class="workspace-avatar">${esc(state.business?.name?.charAt(0).toUpperCase() || "M")}</span><span>${esc(state.business?.name || "Mi nuevo espacio")}<small>Preparando tu primer informe</small></span></div>
    <p class="nav-label">TU RECORRIDO</p><ol class="first-run-steps" aria-label="Progreso del onboarding">${labels.map((label, i) => `<li class="${i === step - 1 ? "current" : i < step - 1 ? "done" : ""}" ${i === step - 1 ? 'aria-current="step"' : ""}><span>${i < step - 1 ? icon("check") : i + 1}</span>${label}</li>`).join("")}</ol>
    ${content.includes('id="first-data-preview"') ? `<button class="first-run-data-jump" id="first-data-jump" type="button">${icon("grid")} Ver mis datos ${icon("arrow")}</button>` : ""}
    <div class="first-run-sidebar-footer">${icon("shield")} Tu trabajo se guarda en este espacio local.</div>
    </aside><div class="first-run-workspace"><header class="first-run-topbar"><span class="breadcrumb">Preparando tu espacio <span>/</span> <b>${labels[step - 1]}</b></span><span class="environment"><i></i> Entorno local <span class="beta">BETA</span></span></header><main id="main" class="first-run" tabindex="-1">${content}</main></div></div>`;
  document.querySelector("#first-data-jump")?.addEventListener("click", () =>
    document.querySelector("#first-data-preview")?.scrollIntoView({behavior: "smooth", block: "start"}));
}

function onboardingBusiness() {
  const current = state.business;
  const key = "dr-first-business-" + (current?.id || "new");
  const draft = store.get(key, current ? {name: current.name, description: current.description} : {});
  const requestKey = draft.request_key || crypto.randomUUID();
  onboardingShell(`<div class="first-run-grid"><section class="first-run-intro"><p class="eyebrow"><span class="tiny-line"></span> PRIMER PASO</p><h1>Cuéntanos sobre <em>tu negocio.</em></h1><p>El nombre y tu explicación nos ayudarán a interpretar los datos. Comparte lo que vendes, cómo trabajas y cualquier detalle que cambie el significado de las cifras.</p><div class="first-run-tip"><strong>Por ejemplo</strong><p>«Tengo una papelería. Vendemos material escolar y regalos; cada fila del archivo representa una venta de caja».</p></div></section>
    <section class="card first-run-card"><p class="eyebrow">EL CONTEXTO INICIAL</p><h2>Lo que sabes de tu negocio</h2><form id="first-business-form"><label for="first-name">Nombre del negocio</label><input id="first-name" name="name" maxlength="100" required autocomplete="organization" value="${esc(draft.name)}" placeholder="Por ejemplo, Papelería La Esquina"><label for="first-description">Cuéntanos todo lo que consideres importante</label><textarea id="first-description" name="description" rows="8" maxlength="6000" required placeholder="Qué vendes, quiénes son tus clientes, cómo registras las ventas, qué te gustaría entender…">${esc(draft.description)}</textarea><p class="field-help">Podrás corregir este contexto más adelante.</p><div id="first-business-error"></div><button class="button primary" type="submit">Continuar con mis datos ${icon("arrow")}</button></form></section></div>`, 1);
  const form = document.querySelector("#first-business-form");
  const values = () => ({...Object.fromEntries(new FormData(form)), request_key: requestKey});
  form.oninput = () => store.set(key, values());
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
      if (location.hash === "#onboarding/data") await route();
      else location.hash = "#onboarding/data";
    } catch (error) {
      document.querySelector("#first-business-error").innerHTML = errorBox(error.message);
      button.disabled = false;
    }
  };
}

function onboardingData() {
  const business = state.business;
  const key = "dr-first-data-" + business.id;
  const draft = store.get(key, {});
  const requestKey = draft.request_key || crypto.randomUUID();
  const selected = draft.mode === "specific" ? "specific" : "general";
  onboardingShell(`<div class="first-run-grid"><section class="first-run-intro"><p class="eyebrow"><span class="tiny-line"></span> SEGUNDO PASO</p><h1>Ahora, <em>tus datos.</em></h1><p>Elige qué quieres averiguar y comparte un primer archivo. El agente revisará el contexto y los datos, te preguntará lo que falte e intentará preparar un informe con evidencia.</p><div class="first-run-tip"><strong>${esc(business.name)}</strong><p>${esc(business.description)}</p><a class="text-button" href="#onboarding/business">Editar el negocio</a></div></section>
    <section class="card first-run-card"><p class="eyebrow">TU PRIMER INFORME</p><h2>¿Qué quieres entender?</h2><form id="first-data-form"><fieldset><legend>Tipo de informe</legend><label class="first-run-choice"><input type="radio" name="mode" value="general" ${selected === "general" ? "checked" : ""}><span><strong>Informe general</strong><small>Explorar los datos y destacar lo que merece atención.</small></span></label><label class="first-run-choice"><input type="radio" name="mode" value="specific" ${selected === "specific" ? "checked" : ""}><span><strong>Responder a una pregunta</strong><small>Orientar el primer informe hacia un objetivo concreto.</small></span></label></fieldset><div id="first-goal-field" ${selected !== "specific" ? "hidden" : ""}><label for="first-goal">¿Qué pregunta tienes?</label><textarea id="first-goal" rows="3" maxlength="2000" ${selected === "specific" ? "required" : ""} placeholder="Por ejemplo, ¿qué productos se vendieron mejor este mes?">${esc(draft.goal)}</textarea></div><label for="first-csv">Tu primer archivo CSV</label><input id="first-csv" type="file" accept=".csv,text/csv" aria-describedby="first-file-help"><p id="first-file-help" class="field-help">CSV UTF-8 de hasta 20 MB. Podrás añadir más archivos desde Mi negocio tras este primer informe.</p><div id="first-file-selected"></div><button type="button" class="text-button" id="first-sample">Usar datos ficticios de ejemplo</button><div id="first-data-error"></div><button class="button primary" type="submit">Empezar el análisis ${icon("arrow")}</button></form></section></div>`, 2);
  const form = document.querySelector("#first-data-form");
  const mode = () => new FormData(form).get("mode");
  const values = () => ({mode: mode(), goal: document.querySelector("#first-goal").value, request_key: requestKey});
  const save = () => store.set(key, values());
  const showFile = () => {
    document.querySelector("#first-file-selected").textContent = state.onboardingFile
      ? `${state.onboardingFile.name} · ${size(state.onboardingFile.size)}` : "Todavía no has seleccionado un archivo.";
  };
  form.oninput = save;
  form.onchange = event => {
    if (event.target.name === "mode") {
      const specific = mode() === "specific";
      document.querySelector("#first-goal-field").hidden = !specific;
      document.querySelector("#first-goal").required = specific;
      save();
    }
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
    const goal = mode() === "specific" ? document.querySelector("#first-goal").value.trim() : "";
    const error = document.querySelector("#first-data-error");
    if (!file) { error.innerHTML = errorBox("Selecciona un archivo CSV para continuar."); return; }
    if (!file.name.toLowerCase().endsWith(".csv") || file.size > 20 * 1024 ** 2) {
      error.innerHTML = errorBox("Selecciona un CSV de hasta 20 MB."); return;
    }
    if (!state.configured) {
      error.innerHTML = errorBox("El modelo local aún no está configurado. Tu contexto está guardado; vuelve cuando esté disponible."); return;
    }
    save();
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
      if (location.hash === "#onboarding/progress") await route();
      else location.hash = "#onboarding/progress";
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
    content = `<div class="first-run-question-layout"><section class="card first-run-card first-run-progress"><p class="eyebrow">UNA ACLARACIÓN PARA SEGUIR</p><h1>${esc(question.text)}</h1><p class="first-question-reason">${esc(question.reason)}</p><form id="answer-form">${answerFields(question, saved, 4)}<p class="field-help">Si no lo sabes, seguiremos con los datos disponibles y lo indicaremos en el informe.</p><div id="answer-error" role="alert"></div><button class="button primary" type="submit">Guardar y continuar ${icon("arrow")}</button></form></section><aside class="first-run-data" id="first-data-preview" aria-label="Vista del CSV"><p class="eyebrow">TUS DATOS</p><p>Cargando el archivo…</p></aside></div>`;
  } else if (data.publishable) {
    content = `<section class="first-run-report"><p class="eyebrow">TU PRIMER INFORME</p><h1>Ya tienes un punto <em>de partida.</em></h1><p>El agente ha revisado los datos y tus respuestas. Lee el informe y comprueba las cifras antes de pasar a tu espacio.</p><div class="first-run-report-actions"><a class="button secondary" href="/api/jobs/${encodeURIComponent(data.id)}/report" target="_blank" rel="noopener">Abrir informe completo ${icon("external")}</a><button class="button primary" id="first-finish">Entrar a mi espacio ${icon("arrow")}</button></div><div id="first-finish-error"></div><p class="report-caveat">Informe elaborado con IA y revisión automática. Consulta el alcance, las limitaciones y la evidencia antes de tomar decisiones.</p><iframe id="first-report-frame" class="report-frame" title="Primer informe de ${esc(data.business)}" src="/api/jobs/${encodeURIComponent(data.id)}/report" sandbox="allow-same-origin"></iframe></section>`;
  } else if (data.status === "failed" || data.status === "blocked") {
    content = `<section class="card first-run-card first-run-progress"><p class="eyebrow">TU TRABAJO ESTÁ GUARDADO</p><h1>El análisis se ha detenido.</h1><p>${esc(data.issue || "No se pudo entregar un informe revisado con estos datos.")}</p><div id="first-progress-error"></div><div class="first-run-report-actions">${data.status === "failed" ? `<button class="button primary" id="first-retry">${data.context_stale ? "Recalcular con la memoria actual" : "Reintentar análisis"} ${icon("arrow")}</button>` : ""}<button class="button secondary" id="first-restart">Empezar con otro archivo</button></div>${data.status === "failed" ? '<p class="field-help">Una petición interrumpida al modelo puede ejecutarse de nuevo al reintentar.</p>' : ""}</section>`;
  } else {
    content = `<section class="card first-run-card first-run-progress"><div class="working-symbol">${icon("spark")}</div><p class="eyebrow">PREPARANDO TU PRIMER INFORME</p><h1>${esc(phases[data.phase] || "Estamos analizando tus datos")}</h1><p>El agente está contrastando tu contexto con el archivo. Si necesita aclarar algo importante, te preguntará aquí antes de crear el informe.</p>${data.activity ? `<p class="progress-update">${esc(data.activity)}</p>` : ""}<p class="field-help">Puedes cerrar esta página y volver. El trabajo continúa mientras el servidor local esté encendido.</p></section>`;
  }
  onboardingShell(`<div class="first-run-result"><p class="eyebrow"><span class="tiny-line"></span> TERCER PASO · ${esc(data.business)}</p>${content}</div>`, 3);
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
      onboardingShell(`<section class="card first-run-card first-run-progress"><h1>No pudimos abrir tu análisis.</h1><p>${esc(error.message)}</p><button class="button secondary" id="first-reload">Volver a intentar</button></section>`, 3);
      document.querySelector("#first-reload").onclick = route;
    }
  }
}
