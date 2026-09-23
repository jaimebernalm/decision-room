/* Consultable owner memory; every mutation uses the same backend as conversations. */
const factKinds = {context: "Información", priority: "Prioridad", definition: "Definición", availability: "Disponibilidad", open_question: "Duda", result_reference: "Referencia a informe"};
const factStates = {declared: "Declarado por ti", proposed: "Pendiente de confirmar", conflicted: "Contradicción pendiente", withdrawn: "Retirado", superseded: "Versión anterior"};
function factScope(content, dossier) {
  if (content.scope === "business") return "Todo el negocio";
  const dataset = dossier.datasets.find(d => d.id === content.scope_id || (d.files || []).some(f => f.id === content.scope_id));
  const file = dataset?.files?.find(f => f.id === content.scope_id);
  return file ? file.name : dataset ? dataset.title : "Fuente o conjunto específico";
}
function validity(content) {
  return content.temporal_scope === "unresolved" ? "Fecha por aclarar" : content.valid_from || content.valid_until ? `${content.valid_from || "Sin inicio indicado"} → ${content.valid_until || "Sin fin indicado"}` : "Sin periodo indicado";
}
function originDetails(fact) {
  return `<details class="fact-origin"><summary>Origen y alcance</summary><p>${esc(fact.origin_kind === "profile" ? "Perfil del negocio" : fact.origin_key?.startsWith("chat_message:") ? "Conversación" : fact.origin_kind === "manual" ? "Declaración o edición explícita" : "Aclaración de un análisis")} · ${fmtDate(fact.created_at)}</p><blockquote>${esc(fact.original_text || fact.quote)}</blockquote>${fact.question ? `<p>Pregunta: ${esc(fact.question)}</p>` : ""}${fact.conversation_id ? `<a href="#chat/${esc(fact.conversation_id)}">Abrir conversación</a>` : ""}</details>`;
}
async function dossierPage(tab = "information") {
  if (!state.business) { businessForm(true); return; }
  const generation = state.generation, business = state.business.id;
  const dossier = await api("/api/business/dossier");
  if (generation !== state.generation) return;
  if (dossier.business_id !== business) { await route(); return; }
  state.business = dossier.business;
  state.memory = dossier.memory;
  const render = (selected) => {
    const b = state.business;
    const facts = dossier.facts.filter(f => !["withdrawn", "superseded"].includes(f.status));
    const card = (f) => `<article class="dossier-card"><div class="dossier-meta"><span>${esc(factKinds[f.content.kind])}</span><span class="badge ${f.status === "declared" ? "green" : "amber"}">${esc(factStates[f.status])}</span></div><p class="fact-statement">${esc(f.content.statement)}</p><p class="field-help">${esc(factScope(f.content, dossier))} · ${esc(validity(f.content))}</p>${f.alternatives?.length ? `<details><summary>Versiones en conflicto</summary>${f.alternatives.map(a => `<p>${esc(a.content?.statement || a.statement || a.quote || "Consulta la declaración original.")}</p>`).join("")}</details>` : ""}${originDetails(f)}<div class="dossier-actions"><button class="button secondary" data-edit="${esc(f.fact_id)}">${f.status === "conflicted" ? "Resolver contradicción" : "Editar"}</button>${f.status === "proposed" && f.content.temporal_scope !== "unresolved" ? `<button class="button secondary" data-confirm="${esc(f.fact_id)}">Confirmar</button>` : ""}<button class="text-button" data-withdraw="${esc(f.fact_id)}">Retirar</button></div><p class="field-help" role="status" id="fact-status-${esc(f.fact_id)}"></p></article>`;
    shell(`<div class="page-heading"><div><p class="eyebrow">TU MEMORIA COMPARTIDA</p><h1>Mi negocio</h1><p>Revisa lo que recuerda el agente y los datos que puede consultar.</p></div><button class="button secondary" id="dossier-refresh">Actualizar ficha</button></div><div class="dossier-tabs" role="group" aria-label="Secciones de Mi negocio">${[["information", "Información"], ["data", "Datos y archivos"], ["history", "Cambios"]].map(([key, label]) => `<button class="button ${selected === key ? "primary" : "secondary"}" aria-pressed="${selected === key}" data-dossier-tab="${key}">${label}</button>`).join("")}</div><div id="dossier-content">${selected === "information" ? `<section class="dossier-card"><h2>${esc(b.name)}</h2><p class="business-description">${esc(b.description || "Añade contexto a tu ritmo; no hay campos obligatorios que completar.")}</p><a href="#business">Editar presentación del negocio</a></section><div class="section-heading"><h2>Información y definiciones</h2><button class="button secondary" id="fact-new">Añadir información</button></div><p class="field-help">Las propuestas y las dudas no se consideran hechos confirmados. Las correcciones se comparten con las conversaciones y pueden requerir revisar resultados anteriores.</p><div class="dossier-cards">${facts.filter(f => f.status !== "declared" || f.content.kind === "open_question").map(card).join("")}${facts.filter(f => f.status === "declared" && f.content.kind !== "open_question").map(card).join("") || (!facts.length ? '<p class="dossier-empty">No hay información activa en la ficha. Puedes añadirla o contarla en una conversación; las revisiones anteriores se conservan en Cambios.</p>' : "")}</div>` : selected === "data" ? datasetMarkup(dossier) : `<h2>Historial de cambios</h2><p>Se conservan las revisiones anteriores. Una información retirada no vuelve a utilizarse automáticamente.</p>${dossier.history.length ? dossier.history.map(f => `<article class="dossier-card"><div class="dossier-meta"><span>${fmtDate(f.created_at)} · Revisión ${f.revision}</span><span>${esc(factStates[f.status])}${dossier.facts.some(x => x.fact_id === f.fact_id && x.revision > f.revision) ? " · Histórica" : ""}</span></div><p>${esc(f.content.statement)}</p><p class="field-help">${esc(factScope(f.content, dossier))} · ${esc(validity(f.content))}${f.change_kind === "future" ? " · Cambio desde una fecha" : ""}</p>${originDetails(f)}${f.status === "withdrawn" && dossier.facts.some(x => x.fact_id === f.fact_id && x.revision === f.revision) ? `<button class="button secondary" data-edit="${esc(f.fact_id)}">Restaurar mediante corrección</button>` : ""}</article>`).join("") : '<p class="dossier-empty">Aún no hay cambios registrados.</p>'}`}</div><div id="dossier-editor"></div><p class="field-help"><a href="#businesses">Cambiar de negocio</a></p>`, "my-business", "Mi negocio");
    document.querySelectorAll("[data-dossier-tab]").forEach(button => button.onclick = () => render(button.dataset.dossierTab));
    document.querySelector("#dossier-refresh").onclick = () => refresh(selected);
    document.querySelector("#fact-new")?.addEventListener("click", () => editFact(null));
    document.querySelectorAll("[data-edit]").forEach(button => button.onclick = () => editFact(dossier.facts.find(f => f.fact_id === button.dataset.edit)));
    for (const action of ["confirm", "withdraw"]) document.querySelectorAll(`[data-${action}]`).forEach(button => {
      const fact = dossier.facts.find(f => f.fact_id === button.dataset[action]);
      const requestKey = crypto.randomUUID();
      button.onclick = async () => {
        button.disabled = true;
        const status = document.querySelector(`#fact-status-${fact.fact_id}`);
        try {
          await api("/api/business/memory", {method: "POST", body: {business_id: business, action, fact_id: fact.fact_id, expected_revision: fact.revision, request_key: requestKey}});
          if (generation !== state.generation) return;
          toast(action === "withdraw" ? "Información retirada de la memoria compartida." : "Información confirmada.");
          await refresh(selected);
        } catch (error) { if (status?.isConnected) status.textContent = error.message; button.disabled = false; }
      };
    });
    if (selected === "data") bindDatasetUpload(dossier, business, generation, () => refresh("data"));
  };
  const refresh = async (selected) => {
    try { await dossierPage(selected); } catch (error) { if (generation === state.generation) toast(error.message); }
  };
  const editFact = (fact) => {
    const c = fact?.content || {kind: "context", statement: "", scope: "business", scope_id: null, valid_from: null, valid_until: null, temporal_scope: "unspecified", result_id: null};
    const scopes = [["business", "Todo el negocio"], ...dossier.datasets.flatMap(d => [[`analysis:${d.id}`, `${d.title} · versión ${d.version}`], ...(d.files || []).map(f => [`source:${f.id}`, `Archivo: ${f.name}`])])];
    const target = c.scope === "business" ? "business" : `${c.scope}:${c.scope_id}`;
    const editor = document.querySelector("#dossier-editor");
    editor.innerHTML = `<section class="dossier-card"><h2>${fact ? "Corregir información" : "Añadir información"}</h2><form id="fact-form" class="dossier-form">${!fact ? '<label>Concepto<input name="concept" required maxlength="70" placeholder="Por ejemplo, margen objetivo"></label>' : ""}<label>Tipo<select name="kind">${Object.entries(factKinds).filter(([k]) => k !== "result_reference" || c.kind === k).map(([key,label]) => `<option value="${key}" ${key === c.kind ? "selected" : ""}>${label}</option>`).join("")}</select></label><label>Información<textarea name="statement" required maxlength="1600" rows="3">${esc(c.statement)}</textarea></label><label>Se aplica a<select name="scope">${scopes.map(([key,label]) => `<option value="${esc(key)}" ${target === key ? "selected" : ""}>${esc(label)}</option>`).join("")}</select></label><div class="dossier-dates"><label>Desde (opcional)<input type="date" name="valid_from" value="${esc(c.valid_from || "")}"></label><label>Hasta (opcional)<input type="date" name="valid_until" value="${esc(c.valid_until || "")}"></label></div><label class="dossier-checkbox"><input type="checkbox" name="unresolved" ${c.temporal_scope === "unresolved" ? "checked" : ""}> La fecha está pendiente de aclarar</label>${fact?.status === "declared" ? '<label>Tipo de cambio<select name="change_kind"><option value="historical">Corregir lo guardado, también para resultados anteriores</option><option value="future">Cambiar desde la fecha de inicio indicada</option></select></label>' : ""}<p class="field-help">Guardar expresa tu declaración. Puedes corregirla o retirarla después.</p><p id="fact-error" role="alert"></p><div class="dossier-actions"><button class="button primary" type="submit">Guardar información</button><button class="button secondary" type="button" id="fact-cancel">Cancelar</button></div></form></section>`;
    editor.scrollIntoView({block: "start", behavior: "smooth"});
    editor.querySelector("textarea").focus({preventScroll: true});
    document.querySelector("#fact-cancel").onclick = () => editor.replaceChildren();
    const form = document.querySelector("#fact-form");
    let pending = null;
    form.onsubmit = async (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form));
      const [scope, scopeId] = values.scope.split(":");
      const content = {...c, kind: values.kind, statement: values.statement.trim(), scope, scope_id: scopeId || null, valid_from: values.valid_from || null, valid_until: values.valid_until || null, temporal_scope: values.unresolved ? "unresolved" : values.valid_from || values.valid_until ? "dated" : "unspecified"};
      if (!fact) content.topic = "owner_" + values.concept.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0,70);
      if (content.kind !== "result_reference") content.result_id = null;
      const body = {business_id: business, action: fact ? "correct" : "declare", content, ...(fact ? {fact_id: fact.fact_id, expected_revision: fact.revision} : {}), change_kind: values.change_kind || "historical", original_text: content.statement};
      const signature = JSON.stringify(body);
      if (!pending || pending.signature !== signature) pending = {signature, key: crypto.randomUUID()};
      const button = form.querySelector("button[type=submit]"); button.disabled = true;
      try {
        await api("/api/business/memory", {method: "POST", body: {...body, request_key: pending.key}});
        if (generation !== state.generation) return;
        toast("Información guardada en la memoria compartida."); await refresh("information");
      } catch (error) { if (form.isConnected) form.querySelector("#fact-error").textContent = error.message; button.disabled = false; }
    };
  };
  render(tab);
}
function datasetMarkup(dossier) {
  return `<h2>Datos y archivos</h2><p>Sube datos para futuras preguntas. Los archivos se mantienen separados y los informes se conservan con la versión utilizada.</p><div class="dossier-cards">${dossier.datasets.map(d => `<article class="dossier-card"><div class="dossier-meta"><strong>${esc(d.title)} · v${d.version}</strong><span class="badge ${d.status !== "ready" || d.corrected ? "amber" : "quiet"}">${d.corrected ? "Corregida: no reutilizar" : d.superseded_by ? "Versión anterior" : d.status === "ready" ? "Disponible" : d.status === "importing" ? "Preparación interrumpida" : "No disponible"}</span></div><p class="field-help">Periodo declarado: ${esc(d.period_from || "Sin inicio indicado")} → ${esc(d.period_until || "Sin fin indicado")}</p>${(d.files || []).map(f => `<p>${esc(f.name)}${f.rows != null ? ` · ${f.rows} filas` : ""} <a href="/api/datasets/file/${esc(f.id)}">Descargar original</a></p>`).join("")}${d.superseded_by ? '<p class="field-help">Hay una versión posterior. Los resultados anteriores no se han recalculado.</p>' : ""}${d.status === "ready" && !d.corrected ? `<button class="button secondary" data-ask-dataset="${esc(d.id)}">Preguntar con esta versión</button>` : ""}</article>`).join("") || '<p class="dossier-empty">Todavía no hay datos. Puedes conversar sobre tu negocio y añadir un CSV cuando lo necesites.</p>'}</div><section class="dossier-card"><h2>Añadir un CSV</h2><form id="dataset-form" class="dossier-form"><label>Nombre del conjunto<input name="title" required maxlength="160" placeholder="Ventas de septiembre"></label><label>Archivo CSV UTF-8<input type="file" name="file" accept=".csv,text/csv" required></label><label>Cómo se relaciona con tus datos<select name="mode"><option value="separate">Conjunto independiente</option><option value="update">Nueva versión</option><option value="correction">Corregir una versión</option></select></label><p class="field-help" id="dataset-mode-help"></p><label id="previous-label" hidden>Versión que sustituye<select name="previous_id"><option value="">Selecciona una versión</option>${dossier.datasets.filter(d => d.status === "ready" && !d.superseded_by && !d.corrected).map(d => `<option value="${esc(d.id)}">${esc(d.title)} · v${d.version}</option>`).join("")}</select></label><div class="dossier-dates"><label>Inicio del periodo (opcional)<input type="date" name="period_from"></label><label>Fin del periodo (opcional)<input type="date" name="period_until"></label></div><p class="field-help">Si no conoces la relación o el periodo, deja el archivo separado. No se detecta ni se resuelve automáticamente el solapamiento entre filas.</p><p id="dataset-result" role="status"></p><button class="button primary" type="submit">Guardar datos</button></form></section>`;
}
function bindDatasetUpload(dossier, business, generation, refresh) {
  const form = document.querySelector("#dataset-form"), output = document.querySelector("#dataset-result");
  const storageKey = "dr-dataset-upload-" + business;
  const saved = store.get(storageKey, null);
  if (saved?.metadata?.previous_id && !Array.from(form.elements.previous_id.options).some(o => o.value === saved.metadata.previous_id)) {
    const option = document.createElement("option"); option.value = saved.metadata.previous_id; option.textContent = "Versión del envío anterior (recuperar reintento)"; form.elements.previous_id.add(option);
  }
  if (saved?.metadata) for (const name of ["title", "mode", "previous_id", "period_from", "period_until"]) form.elements[name].value = saved.metadata[name] || "";
  const mode = form.elements.mode;
  const updateMode = () => { document.querySelector("#previous-label").hidden = mode.value === "separate"; form.elements.previous_id.required = mode.value !== "separate"; document.querySelector("#dataset-mode-help").textContent = {separate: "Se guarda por separado. No se suma ni combina con otros archivos.", update: "Sustituye la versión para nuevas consultas. Los resultados anteriores se conservan como históricos y no se recalculan.", correction: "Corrige errores de la versión elegida. Sus resultados afectados dejan de estar disponibles hasta calcular y revisar de nuevo."}[mode.value]; };
  mode.onchange = updateMode; updateMode();
  form.onsubmit = async (event) => {
    event.preventDefault();
    const file = form.elements.file.files[0];
    const values = Object.fromEntries(new FormData(form));
    const metadata = {business_id: business, title: values.title, mode: values.mode, previous_id: values.mode === "separate" ? "" : values.previous_id, period_from: values.period_from, period_until: values.period_until};
    const button = form.querySelector("button[type=submit]"); button.disabled = true; output.textContent = "Preparando el CSV…";
    try {
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer()))).map(v => v.toString(16).padStart(2,"0")).join("");
      const signature = JSON.stringify([metadata, file.name, hash]);
      let pending = store.get(storageKey, null);
      if (!pending || pending.signature !== signature) pending = {signature, metadata, key: crypto.randomUUID()};
      store.set(storageKey, pending);
      const body = new FormData(); body.append("metadata", JSON.stringify({...metadata, request_key: pending.key})); body.append("file", file);
      const result = await api("/api/datasets", {method: "POST", body});
      store.remove(storageKey);
      if (generation !== state.generation) return;
      await refresh();
      const status = document.querySelector("#dataset-result"); if (status) status.textContent = result.message;
    } catch (error) { if (output.isConnected) output.textContent = error.message; button.disabled = false; }
  };
  document.querySelectorAll("[data-ask-dataset]").forEach(button => {
    const key = crypto.randomUUID();
    button.onclick = async () => {
      button.disabled = true;
      try {
        const dataset = dossier.datasets.find(d => d.id === button.dataset.askDataset);
        const chat = await api("/api/chats", {method: "POST", body: {business_id: business, request_key: key, analysis_id: dataset.id, title: dataset.title}});
        if (generation === state.generation) location.hash = "#chat/" + chat.id;
      } catch (error) { if (generation === state.generation) toast(error.message); button.disabled = false; }
    };
  });
}
