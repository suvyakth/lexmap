/* Lexmap front end: vanilla JS, no dependencies.  All answers come from docs/engine.js
   evaluating docs/data/rules.json, so any address and any date can be answered client-side. */
(function () {
  "use strict";
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const D = {};
  let engine = null;
  let lang = "en";
  let current = null;           // {kind:'sample', id} | {kind:'custom', addr}
  const DEFAULT_ASOF = "2026-10-01";

  const I18N = {
    en: {
      applies: "Applies", superseded: "Superseded", unknown: "Unknown", not_yet_effective: "Not yet effective", pending: "Pending bill",
      in_force: "In force", failed: "Failed", conflict: "Flagged for review", why: "Why", source: "Source quote", key: "Key figure",
      no_rule: "No rule in this category was found in the corpus for this address's state or city.",
      year: "Year built", units: "Units", type: "Property type", owner: "Owner facts", not_in_data: "not in the data",
      jurisdiction: "Legal jurisdiction", as_of: "as of", corroborated: "Also supported by",
      superseded_by: "Governing local rule", official: "official source", secondary: "secondary source",
      retrieved: "retrieved", confidence: "confidence", none: "None",
      tally_applies: "apply", tally_unknown: "unknown", tally_superseded: "superseded", tally_nye: "not yet effective", tally_pending: "pending",
      exemptions: "Exemptions", coverage: "Coverage logic", requirement: "Requirement",
      event_only: "Only if a specific event happens (demolition, conversion, temporary displacement)",
      no_rule_short: "No rule found in the corpus", category: "Category", governs: "What governs here", citation: "Citation",
    },
    es: {
      applies: "Aplica", superseded: "Desplazada", unknown: "Desconocido", not_yet_effective: "Aún no vigente", pending: "Proyecto pendiente",
      in_force: "Vigente", failed: "Fracasó", conflict: "Marcado para revisión", why: "Por qué", source: "Cita de la fuente", key: "Dato clave",
      no_rule: "No se encontró ninguna norma de esta categoría en el corpus para el estado o la ciudad de esta dirección.",
      year: "Año de construcción", units: "Unidades", type: "Tipo de propiedad", owner: "Datos del propietario", not_in_data: "no están en los datos",
      jurisdiction: "Jurisdicción legal", as_of: "a fecha de", corroborated: "También respaldado por",
      superseded_by: "Norma local que rige", official: "fuente oficial", secondary: "fuente secundaria",
      retrieved: "consultado", confidence: "confianza", none: "Ninguna",
      tally_applies: "aplican", tally_unknown: "desconocidas", tally_superseded: "desplazadas", tally_nye: "aún no vigentes", tally_pending: "pendientes",
      exemptions: "Exenciones", coverage: "Lógica de cobertura", requirement: "Requisito",
      event_only: "Solo si ocurre un hecho específico (demolición, conversión, desplazamiento temporal)",
      no_rule_short: "No se encontró ninguna norma en el corpus", category: "Categoría", governs: "Qué rige aquí", citation: "Cita",
    },
  };
  const UI_ES = {
    tab_lookup: "Buscar dirección", tab_changes: "Qué está cambiando", tab_rules: "Todas las normas", tab_method: "Cómo funciona",
    nla: "No es asesoría legal.",
    nla_body: "Lexmap muestra lo que dice la ley pública de vivienda, a partir de un corpus fijo (consultado el 1 de octubre de 2026). No es una certificación de cumplimiento. Revise la fuente citada y consulte a un abogado o a una organización de inquilinos antes de actuar.",
    hero: "¿Qué normas de vivienda aplican en esta dirección y qué está por cambiar?",
    hero_sub: "Topes de alquiler, desalojo con causa justa, depósitos, tarifas, selección de inquilinos y fijación algorítmica de rentas en California, Nueva Jersey y Massachusetts. Cada respuesta cita la ley de la que proviene.",
    search_label: "Dirección de muestra (500 edificios en 9 ciudades)", asof_label: "Respuesta a fecha de",
    custom_title: "Buscar cualquier dirección en CA, NJ o MA (geocodificación del Censo en vivo)", custom_go: "Buscar",
    custom_hint: "La dirección se envía solo al Geocodificador del Censo de EE. UU. para encontrar su ciudad legal. Los datos que deje en blanco se tratan como desconocidos; nunca se adivinan.",
    changes_h: "Qué está cambiando", changes_sub: "Los cinco casos de cambio del reto, calculados con el mismo motor.",
    rules_h: "Todas las normas extraídas", rules_sub: "Cada norma se extrajo automáticamente del corpus, se verificó contra el texto fuente y fue revisada por un segundo modelo.",
    gaps_h: "Donde el corpus no tiene norma", gaps_sub: "Combinaciones de jurisdicción y categoría sin norma vigente en el corpus. Lexmap las muestra como vacíos en lugar de adivinar.",
    method_h: "Cómo funciona Lexmap",
  };
  const UI_EN = {};
  const t = (k) => (I18N[lang] && I18N[lang][k]) || I18N.en[k] || k;

  // ------------------------------------------------------------------ data
  async function load() {
    const names = ["rules", "addresses", "sources", "gaps", "changes", "selfcheck", "meta"];
    const res = await Promise.all(names.map((n) => fetch(`data/${n}.json`).then((r) => r.json())));
    names.forEach((n, i) => (D[n] = res[i]));
    D.byId = Object.fromEntries(D.rules.map((r) => [r.team_rule_id, r]));
    D.addrById = Object.fromEntries(D.addresses.map((a) => [a.id, a]));
    engine = new Lexmap.Engine(D.rules, D.meta.states);
  }

  // ------------------------------------------------------------------ helpers
  const catLabel = (c) => (D.meta.category_label || {})[c] || c;
  const CAT_ES = {
    rent_increase_limits: "Aumentos de renta", just_cause_eviction: "Desalojo con causa justa", security_deposits: "Depósitos de garantía",
    application_screening_fees: "Tarifas de solicitud y evaluación", screening_restrictions: "Restricciones de selección",
    algorithmic_rent_setting: "Fijación algorítmica de rentas",
  };
  const catName = (c) => (lang === "es" ? CAT_ES[c] : catLabel(c));
  function pill(status, extra) { return `<span class="pill ${status}">${esc(t(status))}${extra ? " " + extra : ""}</span>`; }
  function describePred(p) {
    if (!p) return "everyone in the jurisdiction";
    if (p.all) return "(" + p.all.map(describePred).join(" AND ") + ")";
    if (p.any) return "(" + p.any.map(describePred).join(" OR ") + ")";
    if (p.not) return "NOT " + describePred(p.not);
    let v = p.value;
    if (v && typeof v === "object" && !Array.isArray(v) && "as_of_minus_years" in v) v = `[as-of date − ${v.as_of_minus_years} years]`;
    else if (Array.isArray(v)) v = "[" + v.join(", ") + "]";
    return `${p.field.replace(/_/g, " ")} ${p.op} ${v}`;
  }
  function plain(r) {
    const pl = r.plain_language || {};
    if (lang === "es" && pl.es) return pl.es;
    return pl.en || r.requirement;
  }
  function sourceMeta(r) {
    const s = D.sources[r.source_doc_id] || {};
    const official = (r.source_type || "").startsWith("official");
    return `<span class="c">${esc(r.citation)}</span>
      <span>${official ? t("official") : t("secondary")} · <a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.source_doc_id)}</a></span>
      <span>${t("retrieved")} ${esc(r.retrieved_at || s.retrieved_at || "")}</span>
      <span class="conf">${t("confidence")} <span class="meter"><i style="width:${Math.round((r.confidence || 0) * 100)}%"></i></span> ${Math.round((r.confidence || 0) * 100)}%</span>`;
  }

  // ------------------------------------------------------------------ lookup view
  function renderAddress(addr, meta) {
    const asOf = $("#asof").value || DEFAULT_ASOF;
    const all = engine.lookup(addr, asOf);
    const entries = all.filter((e) => !e.event_only);
    const events = all.filter((e) => e.event_only);
    const by = {}, evBy = {};
    for (const e of entries) (by[e.category] = by[e.category] || []).push(e);
    for (const e of events) (evBy[e.category] = evBy[e.category] || []).push(e);
    const count = (r) => entries.filter((e) => e.result === r).length;
    const f = addr.facts;
    const stackHtml = addr.stack.map((j) => `<span class="lvl">${esc(j.length === 2 ? D.meta.states[j] : j)}</span>`).join('<span class="sep">›</span>');
    const flags = (meta.flags || []).map((x) => `<li>${esc(x)}</li>`).join("");
    const units = f.units_min == null || (f.units_min <= 1 && f.units_max == null) ? t("not_in_data") : Lexmap.unitsText(f);
    let html = `<div class="card addr">
      <div class="addr-top">
        <div>
          <h2>${esc(meta.title)}</h2>
          <div class="stack"><b>${t("jurisdiction")}:</b> ${stackHtml}</div>
          ${meta.matched ? `<div class="asof-badge">Census match: ${esc(meta.matched)}</div>` : ""}
        </div>
        <div class="asof-badge">${t("as_of")} <b>${esc(asOf)}</b> · ${esc(meta.idLabel || "")}</div>
      </div>
      <div class="facts">
        <div class="fact"><div class="k">${t("year")}</div><div class="v">${f.year_built || "—"}</div><div class="p">${esc(f.year_source || "")}</div></div>
        <div class="fact"><div class="k">${t("units")}</div><div class="v">${esc(units)}</div><div class="p">${esc(f.units_source || "")}</div></div>
        <div class="fact"><div class="k">${t("type")}</div><div class="v">${esc(f.property_type === "multifamily" ? "apartment building" : (f.property_type || "unknown"))}</div><div class="p">${esc(f.property_type_source || "")}</div></div>
        <div class="fact"><div class="k">${t("owner")}</div><div class="v">${t("not_in_data")}</div><div class="p">No owner names in the sample; owner-based exemptions resolve to “unknown” unless building facts rule them out.</div></div>
      </div>
      ${flags ? `<ul class="flags">${flags}</ul>` : ""}
      <div class="tally">
        ${pill("applies", count("applies"))} ${pill("unknown", count("unknown"))} ${pill("superseded", count("superseded"))}
        ${pill("not_yet_effective", count("not_yet_effective"))} ${pill("pending", count("pending"))}
        ${entries.some((e) => e.conflict_flag) ? `<span class="pill conflict">⚑ ${t("conflict")}: ${entries.filter((e) => e.conflict_flag).length}</span>` : ""}
      </div>
    </div>`;
    html += glance(by);
    for (const c of D.meta.categories) {
      const es = by[c] || [];
      const ev = evBy[c] || [];
      html += `<section class="cat" id="cat-${c}"><div class="cat-h"><h3>${esc(catName(c))}</h3><span class="n">${es.length} rule${es.length === 1 ? "" : "s"}</span></div>`;
      if (!es.length) html += noRuleCard(c, addr);
      for (const e of es) html += ruleCard(e);
      if (ev.length) html += `<details class="src evgroup"><summary>${t("event_only")} (${ev.length})</summary>${ev.map(ruleCard).join("")}</details>`;
      html += `</section>`;
    }
    $("#result").innerHTML = html;
  }

  // One line per category: what governs here, at a glance (mirrors the brief's illustrative output).
  function glance(by) {
    const rank = { applies: 0, unknown: 1, not_yet_effective: 2, superseded: 3, pending: 4 };
    let rows = "";
    for (const c of D.meta.categories) {
      const es = (by[c] || []).slice().sort((a, b) => rank[a.result] - rank[b.result]);
      if (!es.length) { rows += `<tr><td>${esc(catName(c))}</td><td colspan="2" class="muted">${t("no_rule_short")}</td></tr>`; continue; }
      const main = es[0], r = main.rule;
      const more = es.length > 1 ? ` <span class="muted">+${es.length - 1} more</span>` : "";
      rows += `<tr><td><a href="#cat-${c}" class="catlink">${esc(catName(c))}</a></td>
        <td>${pill(main.result)} <b>${esc(r.title)}</b>${more}${r.key_value ? `<div class="muted">${esc(r.key_value)}</div>` : ""}</td>
        <td class="c">${esc(r.citation)}</td></tr>`;
    }
    return `<div class="card glance"><table><thead><tr><th>${t("category")}</th><th>${t("governs")}</th><th>${t("citation")}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  // "No rule" is still an answer: show what the corpus says (state bars on local rules, failed measures).
  function noRuleCard(c, addr) {
    const bits = [];
    for (const r of D.rules) {
      if (r.category !== c || !addr.stack.includes(r.jurisdiction)) continue;
      if (r.subject === "municipality" && r.status === "in_force" && !(r.coverage_logic || {}).covers)
        bits.push(`<li><b>${esc(r.citation)}</b>: ${esc(plain(r))}</li>`);
      if (r.status === "failed")
        bits.push(`<li>${pill("failed")} <b>${esc(r.title)}</b> (${esc(r.citation)}): never became law, so it is not reported.</li>`);
    }
    return `<div class="empty">${t("no_rule")}${bits.length ? `<ul class="flags">${bits.join("")}</ul>` : ""}</div>`;
  }

  function ruleCard(e) {
    const r = e.rule;
    const corro = (r.corroborating_sources || []).map((c) => `<a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.doc_id)}</a>`).join(", ");
    const sup = e.superseded_by ? `<div class="kv"><b>${t("superseded_by")}:</b> ${esc(e.superseded_by)} — ${esc((D.byId[e.superseded_by] || {}).citation || "")}</div>` : "";
    return `<article class="card rule ${e.result}">
      <div class="rule-top">
        <div><div class="rule-title">${esc(r.title)}</div><div class="rid">${esc(r.team_rule_id)} · ${esc(r.jurisdiction)}${r.effective_date ? " · effective " + esc(r.effective_date) : ""}</div></div>
        <div>${pill(e.result)} ${e.conflict_flag ? `<span class="pill conflict">⚑ ${t("conflict")}</span>` : ""}</div>
      </div>
      <p class="plain">${esc(plain(r))}</p>
      ${r.key_value ? `<div class="kv"><b>${t("key")}:</b> ${esc(r.key_value)}</div>` : ""}
      ${sup}
      <div class="why"><b>${t("why")}:</b> ${esc(e.explanation)}</div>
      ${e.conflict_flag && r.conflict_note ? `<div class="conflict-box">⚑ ${esc(r.conflict_note)}</div>` : ""}
      <div class="cite">${sourceMeta(r)}</div>
      <details class="src"><summary>${t("source")}</summary>
        <blockquote>${esc(r.quoted_span)}</blockquote>
        ${(r.supporting_spans || []).map((s) => `<blockquote>${esc(s)}</blockquote>`).join("")}
        ${corro ? `<div class="kv">${t("corroborated")}: ${corro}</div>` : ""}
        ${r.exemptions ? `<div class="kv"><b>${t("exemptions")}:</b> ${esc(r.exemptions)}</div>` : ""}
        <div class="kv"><b>${t("coverage")}:</b></div>
        <div class="logic">covers: ${esc(describePred((r.coverage_logic || {}).covers))}\nexempt: ${esc((r.coverage_logic || {}).exempt ? describePred(r.coverage_logic.exempt) : t("none"))}</div>
      </details>
    </article>`;
  }

  function showSample(id, push) {
    const a = D.addrById[id];
    if (!a) return;
    current = { kind: "sample", id };
    $("#q").value = `${a.street}, ${a.postal_city}, ${a.state}`;
    renderAddress({ stack: a.stack, facts: a.facts }, {
      title: `${a.street}, ${a.postal_city}, ${a.state}`, matched: a.matched, flags: a.flags,
      idLabel: `${a.id} · ${a.source_dataset}`,
    });
    if (push !== false) setHash();
  }

  function setHash() {
    const asOf = $("#asof").value;
    if (current && current.kind === "sample") history.replaceState(null, "", `#${current.id}@${asOf}`);
  }

  // ------------------------------------------------------------------ search
  function setupSearch() {
    const q = $("#q"), box = $("#suggest");
    let sel = -1, items = [];
    const norm = (s) => s.toLowerCase().replace(/[^a-z0-9 ]/g, " ");
    const index = D.addresses.map((a) => ({ a, k: norm(`${a.id} ${a.street} ${a.postal_city} ${a.city || ""} ${a.state} ${a.zip || ""}`) }));
    function render() {
      const s = norm(q.value).trim();
      if (!s) { box.hidden = true; return; }
      const toks = s.split(/\s+/);
      items = index.filter((x) => toks.every((tk) => x.k.includes(tk))).slice(0, 12).map((x) => x.a);
      box.innerHTML = items.map((a, i) => `<li role="option" data-id="${a.id}" ${i === sel ? 'aria-selected="true"' : ""}><span>${esc(a.street)}, ${esc(a.postal_city)}</span><span class="m">${esc(a.city || a.state)} · ${a.id}</span></li>`).join("") ||
        `<li class="m">No sample address matches. Use “Look up any address” below.</li>`;
      box.hidden = false;
    }
    q.addEventListener("input", () => { sel = -1; render(); });
    q.addEventListener("keydown", (ev) => {
      if (box.hidden) return;
      if (ev.key === "ArrowDown") { sel = Math.min(items.length - 1, sel + 1); render(); ev.preventDefault(); }
      else if (ev.key === "ArrowUp") { sel = Math.max(0, sel - 1); render(); ev.preventDefault(); }
      else if (ev.key === "Enter") { const a = items[Math.max(0, sel)]; if (a) { box.hidden = true; showSample(a.id); } ev.preventDefault(); }
      else if (ev.key === "Escape") box.hidden = true;
    });
    box.addEventListener("mousedown", (ev) => { const li = ev.target.closest("li[data-id]"); if (li) { box.hidden = true; showSample(li.dataset.id); } });
    document.addEventListener("click", (ev) => { if (!ev.target.closest(".search-box")) box.hidden = true; });
    const examples = [
      ["A0016", "San Francisco, 1926"], ["A0105", "San Francisco, 2019"], ["A0107", "Los Angeles, built 1978"],
      ["A0065", "Dorchester → Boston"], ["A0002", "Hoboken"], ["A0003", "Newark"], ["A0005", "Berkeley (no year)"],
    ].filter(([id]) => D.addrById[id]);
    $("#examples").innerHTML = examples.map(([id, l]) => `<button class="chip" data-id="${id}">${esc(l)}</button>`).join("");
    $("#examples").addEventListener("click", (ev) => { const b = ev.target.closest("button[data-id]"); if (b) showSample(b.dataset.id); });
  }

  function setupDates() {
    const chips = [["2025-12-31", "Dec 31, 2025"], ["2026-01-02", "Jan 2, 2026"], ["2026-10-01", "Oct 1, 2026 (corpus date)"], ["2027-07-02", "Jul 2, 2027"]];
    $("#date-chips").innerHTML = chips.map(([d, l]) => `<button class="chip${d === DEFAULT_ASOF ? " active" : ""}" data-d="${d}">${l}</button>`).join("");
    const rerender = () => {
      $$("#date-chips .chip").forEach((c) => c.classList.toggle("active", c.dataset.d === $("#asof").value));
      if (!current) return;
      if (current.kind === "sample") showSample(current.id);
      else renderAddress(current.addr, current.meta);
    };
    $("#date-chips").addEventListener("click", (ev) => { const b = ev.target.closest("button[data-d]"); if (b) { $("#asof").value = b.dataset.d; rerender(); } });
    $("#asof").addEventListener("change", rerender);
  }

  // ------------------------------------------------------------------ live geocoding (JSONP)
  const STATE_CODES = { California: "CA", "New Jersey": "NJ", Massachusetts: "MA" };
  const PLACE_TO_CITY = {
    "CA|Los Angeles city": "Los Angeles, CA", "CA|San Francisco city": "San Francisco, CA", "CA|San Diego city": "San Diego, CA",
    "CA|Berkeley city": "Berkeley, CA", "CA|Santa Ana city": "Santa Ana, CA", "NJ|Jersey City city": "Jersey City, NJ",
    "NJ|Hoboken city": "Hoboken, NJ", "NJ|Newark city": "Newark, NJ", "MA|Boston city": "Boston, MA", "MA|Cambridge city": "Cambridge, MA",
  };
  function jsonp(url) {
    return new Promise((resolve, reject) => {
      const cb = "lexmap_cb_" + Math.random().toString(36).slice(2);
      const s = document.createElement("script");
      const timer = setTimeout(() => { cleanup(); reject(new Error("Census geocoder timed out")); }, 20000);
      function cleanup() { clearTimeout(timer); delete window[cb]; s.remove(); }
      window[cb] = (data) => { cleanup(); resolve(data); };
      s.onerror = () => { cleanup(); reject(new Error("Census geocoder unreachable")); };
      s.src = url + "&format=jsonp&callback=" + cb;
      document.body.appendChild(s);
    });
  }
  function setupCustom() {
    $("#custom-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const address = $("#c-addr").value.trim();
      if (!address) return;
      $("#result").innerHTML = `<div class="spinner">Asking the U.S. Census Geocoder for the legal jurisdiction…</div>`;
      try {
        const data = await jsonp("https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?benchmark=Public_AR_Current&vintage=Current_Current&address=" + encodeURIComponent(address));
        const m = ((data.result || {}).addressMatches || [])[0];
        if (!m) { $("#result").innerHTML = `<div class="empty">The Census geocoder found no match for that address. Check the spelling and include city and state.</div>`; return; }
        const g = m.geographies || {};
        const stName = ((g.States || [])[0] || {}).NAME;
        const st = STATE_CODES[stName];
        if (!st) { $("#result").innerHTML = `<div class="empty">That address is in ${esc(stName || "another state")}. Lexmap's corpus covers California, New Jersey and Massachusetts only.</div>`; return; }
        const place = ((g["Incorporated Places"] || [])[0] || {}).NAME;
        let city = place ? PLACE_TO_CITY[st + "|" + place] : null;
        if (!city) for (const cs of g["County Subdivisions"] || []) city = city || PLACE_TO_CITY[st + "|" + cs.NAME];
        const year = parseInt($("#c-year").value, 10);
        const units = parseInt($("#c-units").value, 10);
        const apt = $("#c-type").value === "multifamily";
        const facts = {
          year_built: isNaN(year) ? null : year, year_source: isNaN(year) ? "not provided: treated as unknown" : "entered by you",
          units_min: isNaN(units) ? (apt ? 2 : 1) : units, units_max: isNaN(units) ? null : units,
          units_source: isNaN(units) ? "not provided: treated as unknown" : "entered by you",
          property_type: apt ? "multifamily" : null, property_type_source: apt ? "entered by you" : "not provided: treated as unknown",
        };
        const flags = [];
        if (!city) flags.push(`Census places this address in ${place || "an unincorporated area"}, outside the 10 cities in the corpus: only ${D.meta.states[st]} statewide rules are evaluated.`);
        const addr = { stack: [st].concat(city ? [city] : []), facts };
        const meta = { title: address, matched: m.matchedAddress, flags, idLabel: "live lookup" };
        current = { kind: "custom", addr, meta };
        renderAddress(addr, meta);
      } catch (e) {
        $("#result").innerHTML = `<div class="empty">${esc(e.message)}. The 500 sample addresses still work offline.</div>`;
      }
    });
  }

  // ------------------------------------------------------------------ change tests
  function renderChanges() {
    const rep = D.changes.report, det = D.changes.detailed;
    const checks = D.selfcheck.checks.filter((c) => c.group === "C");
    let html = "";
    for (const [tid, r] of Object.entries(rep)) {
      const mine = checks.filter((c) => c.check.startsWith(tid) && !c.check.includes("(info)"));
      const ok = mine.every((c) => c.ok);
      const verdict = mine.length ? (ok ? '<span class="ok">✓ matches expected behaviour</span>' : '<span class="bad">✗ check failed</span>')
        : '<span class="muted">computed; no expected set was supplied</span>';
      const d = det[tid];
      const ids = d.affected_address_ids;
      const example = ids[0];
      html += `<article class="card test">
        <div class="test-top"><h3>${esc(tid)} · ${esc(r.title)}</h3>${verdict}</div>
        <div class="exp"><b>Expected:</b> ${esc(r.expected_behavior)}</div>
        <div class="res"><b>${r.affected}</b> addresses affected${r.conflict_flags ? ` · <b>${r.conflict_flags}</b> flagged for possible conflict` : ""}. ${esc(r.notes)}</div>
        ${example ? `<div class="kv" style="margin-top:6px"><b>Example ${esc(example)}:</b> ${esc(JSON.stringify(d.details[example]))}</div>` : ""}
        ${ids.length ? `<details class="src"><summary>Affected addresses (${ids.length})</summary><div class="addr-list">${ids.map((i) => `<button data-id="${i}" data-t="${tid}">${i}</button>`).join("")}</div></details>` : `<div class="kv" style="margin-top:6px">No address is affected.</div>`}
      </article>`;
    }
    for (const w of D.changes.whatif || []) {
      const ids = w.affected_address_ids || [];
      html += `<article class="card test">
        <div class="test-top"><h3>What-if · a new ordinance, read by the same pipeline</h3><span class="pill pending">fictional test document</span></div>
        <div class="exp">Document <code>${esc(w.document.split(/[\/]/).pop())}</code> (${esc(w.jurisdiction)}) was written by us to show how Lexmap handles a law it has never seen. It is not a real law.</div>
        ${(w.new_rules || []).map((r) => `<div class="kv" style="margin-top:6px"><b>${esc(r.team_rule_id)}</b> · ${esc(r.title)} · ${pill(r.status)} effective <b>${esc(r.effective_date || "?")}</b> · ${esc(r.citation)}</div>
          <blockquote>${esc(r.quoted_span)}</blockquote>
          <div class="logic">covers: ${esc(describePred((r.coverage_logic || {}).covers))}
exempt: ${esc((r.coverage_logic || {}).exempt ? describePred(r.coverage_logic.exempt) : "none")}</div>`).join("")}
        <div class="res" style="margin-top:8px"><b>${ids.length}</b> sample addresses change once it takes effect (${esc(w.evaluated_at)}): ${esc(JSON.stringify(w.affected_by_city))}.</div>
        ${ids.length ? `<details class="src"><summary>Affected addresses (${ids.length})</summary><div class="addr-list">${ids.map((i) => `<button data-id="${i}" data-asof="${esc(w.evaluated_at)}">${i}</button>`).join("")}</div></details>` : ""}
      </article>`;
    }
    $("#changes").innerHTML = html;
    $("#changes").addEventListener("click", (ev) => {
      const b = ev.target.closest("button[data-id]");
      if (!b) return;
      const test = { T1: "2026-01-02", T3: "2027-07-02" }[b.dataset.t];
      if (test) $("#asof").value = test;
      if (b.dataset.asof) $("#asof").value = b.dataset.asof;
      switchTab("lookup");
      showSample(b.dataset.id);
    });
  }

  // ------------------------------------------------------------------ rules table
  function renderRules() {
    const cat = $("#rf-cat");
    cat.innerHTML = `<option value="">All categories</option>` + D.meta.categories.map((c) => `<option value="${c}">${esc(catLabel(c))}</option>`).join("");
    const draw = () => {
      const q = $("#rf-q").value.toLowerCase(), st = $("#rf-state").value, c = $("#rf-cat").value, s = $("#rf-status").value;
      const rows = D.rules.filter((r) => (!st || r.jurisdiction === st || r.jurisdiction.endsWith(", " + st)) && (!c || r.category === c) && (!s || r.status === s) &&
        (!q || JSON.stringify([r.team_rule_id, r.title, r.citation, r.requirement, r.jurisdiction]).toLowerCase().includes(q)));
      $("#rules-table").innerHTML = `<div class="tbl-wrap"><table><thead><tr><th>ID</th><th>Jurisdiction</th><th>Category</th><th>Status</th><th>Effective</th><th>Citation</th><th>Conf.</th></tr></thead><tbody>
        ${rows.map((r) => `<tr class="r-row" data-id="${r.team_rule_id}"><td class="rid">${esc(r.team_rule_id)}</td><td>${esc(r.jurisdiction)}</td><td>${esc(catLabel(r.category))}</td>
          <td>${pill(r.status)}${r.conflict_flag ? ' <span class="pill conflict">⚑</span>' : ""}</td><td>${esc(r.effective_date || "—")}</td><td>${esc(r.citation)}</td><td>${Math.round(r.confidence * 100)}%</td></tr>`).join("")}
        </tbody></table></div><p class="hint">${rows.length} of ${D.rules.length} rules.</p>`;
    };
    ["#rf-q", "#rf-state", "#rf-cat", "#rf-status"].forEach((s) => $(s).addEventListener("input", draw));
    $("#rules-table").addEventListener("click", (ev) => {
      const tr = ev.target.closest("tr.r-row");
      if (!tr) return;
      const nx = tr.nextElementSibling;
      if (nx && nx.classList.contains("detail")) { nx.remove(); return; }
      const r = D.byId[tr.dataset.id];
      const qa = (r.provenance || {});
      const det = document.createElement("tr");
      det.className = "detail";
      det.innerHTML = `<td colspan="7">
        <p class="plain"><b>${t("requirement")}:</b> ${esc(r.requirement)}</p>
        ${r.key_value ? `<div class="kv"><b>${t("key")}:</b> ${esc(r.key_value)}</div>` : ""}
        ${r.exemptions ? `<div class="kv"><b>${t("exemptions")}:</b> ${esc(r.exemptions)}</div>` : ""}
        ${r.interaction ? `<div class="kv"><b>Interaction:</b> ${esc(r.interaction)}</div>` : ""}
        ${r.conflict_note ? `<div class="conflict-box">⚑ ${esc(r.conflict_note)}</div>` : ""}
        <blockquote>${esc(r.quoted_span)}</blockquote>
        <div class="cite">${sourceMeta(r)}</div>
        <div class="logic">covers: ${esc(describePred((r.coverage_logic || {}).covers))}\nexempt: ${esc((r.coverage_logic || {}).exempt ? describePred(r.coverage_logic.exempt) : "none")}\nyields to: ${esc((r.yields_to || []).join(", ") || "none")}\nconflicts with: ${esc((r.conflicts_with || []).join(", ") || "none")}\nsources merged: ${esc(((qa.reconcile || {}).members || []).join(", "))}\nextraction call: ${esc(qa.extraction_llm_call || "")}</div>
      </td>`;
      tr.after(det);
    });
    draw();
    const g = D.gaps;
    $("#gaps").innerHTML = `<div class="gaps">${Object.entries(g).filter(([, v]) => v.length).map(([j, cats]) => `<div class="card gap"><b>${esc(j.length === 2 ? D.meta.states[j] + " (statewide)" : j)}</b>${cats.map((c) => esc(catLabel(c))).join(" · ")}</div>`).join("")}</div>`;
  }

  // ------------------------------------------------------------------ method
  function renderMethod() {
    const sc = D.selfcheck.summary;
    const nSrc = Object.keys(D.sources).length;
    const nSupp = Object.values(D.sources).filter((s) => s.supplementary).length;
    const conflicts = D.rules.filter((r) => r.conflict_flag).length;
    $("#method").innerHTML = `
      <div class="steps">
        <div class="card step"><div class="num">${nSrc}</div><h3>Sources read</h3><p>${nSrc - nSupp} official corpus texts plus ${nSupp} organiser-listed secondary pages. Code publishers marked “check terms” were not fetched.</p></div>
        <div class="card step"><div class="num">${D.rules.length}</div><h3>Rules extracted</h3><p>An LLM reads each document and emits schema records with executable coverage logic. Every quote is matched verbatim against the source file.</p></div>
        <div class="card step"><div class="num">2×</div><h3>Reconciled and reviewed</h3><p>A stronger model merges duplicates across sources and flags conflicts. A separate QA pass checks the direction of every cut-off.</p></div>
        <div class="card step"><div class="num">${D.addresses.length}</div><h3>Addresses resolved</h3><p>Census Geocoder gives the legal city (Dorchester resolves to Boston). Out-of-state owner ZIPs are detected and ignored.</p></div>
        <div class="card step"><div class="num">${sc.passed}/${sc.total}</div><h3>Self-checks passing</h3><p>Schema, verbatim citations, jurisdiction boundaries, T1–T5, and no rent cap in Massachusetts.</p></div>
      </div>
      <div class="two" style="margin-top:14px">
        <div class="card"><h3>What makes an answer trustworthy</h3><ul>
          <li><b>Deterministic.</b> The model extracts. A three-valued evaluator decides “applies / unknown / superseded / not yet effective / pending”, the same way every time, for any date.</li>
          <li><b>Honest unknowns.</b> Year built is not the certificate-of-occupancy date, so a building in a cut-off year is “unknown”, and the missing fact is named.</li>
          <li><b>Exemptions resolved from facts.</b> A 20-unit building cannot use a “2 units or fewer” exemption, so no owner data is needed.</li>
          <li><b>Precedence.</b> State caps yield to local rent control. Possible preemption, such as the NJ FAIR Act against city bans, is flagged for human review.</li>
          <li><b>${conflicts} rules flagged</b> where sources disagree or the law is in doubt.</li>
        </ul></div>
        <div class="card"><h3>Guardrails</h3><ul>
          <li>Not legal advice, on every screen. No compliance verdicts.</li>
          <li>No invented rules or citations. Quotes that cannot be found verbatim are rejected.</li>
          <li>Plain-language summaries are checked: a number not in the rule record discards the summary.</li>
          <li>Enacted, not-yet-effective, pending and failed measures are kept separate.</li>
          <li>Public data only. Every model call is cached with its prompt hash, so <code>python run.py</code> reproduces this site exactly.</li>
          <li>The full audit log covers sources and hashes, model calls, rejected candidates and every answer.</li>
        </ul></div>
      </div>
      <h2>Submission files</h2>
      <p class="sub"><a href="https://github.com/suvyakth/lexmap/blob/main/submission/rules.json">rules.json</a> ·
        <a href="https://github.com/suvyakth/lexmap/blob/main/submission/lookups.json">lookups.json</a> ·
        <a href="https://github.com/suvyakth/lexmap/blob/main/submission/changes.json">changes.json</a> ·
        <a href="https://github.com/suvyakth/lexmap/blob/main/submission/selfcheck_report.md">self-check report</a> ·
        <a href="https://github.com/suvyakth/lexmap/blob/main/submission/audit_log.jsonl">audit log</a> ·
        <a href="https://github.com/suvyakth/lexmap/blob/main/METHOD_NOTE.md">method note</a></p>`;
    $("#foot-meta").textContent = `Data generated ${D.meta.generated_at} · ${D.rules.length} rules · ${D.addresses.length} addresses`;
  }

  // ------------------------------------------------------------------ tabs, language, boot
  function switchTab(name) {
    $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
    window.scrollTo({ top: 0 });
  }
  function applyLang() {
    $$("[data-i18n]").forEach((el) => {
      const k = el.dataset.i18n;
      if (!(k in UI_EN)) UI_EN[k] = el.textContent;
      el.textContent = lang === "es" && UI_ES[k] ? UI_ES[k] : UI_EN[k];
    });
    document.documentElement.lang = lang;
    $$(".lang button").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
    if (current) { if (current.kind === "sample") showSample(current.id, false); else renderAddress(current.addr, current.meta); }
  }

  async function boot() {
    try { await load(); } catch (e) { $("#result").innerHTML = `<div class="empty">Could not load data: ${esc(e.message)}</div>`; return; }
    $$(".tabs button").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
    $$(".lang button").forEach((b) => b.addEventListener("click", () => { lang = b.dataset.lang; applyLang(); }));
    setupSearch(); setupDates(); setupCustom(); renderChanges(); renderRules(); renderMethod();
    const m = location.hash.match(/^#(A\d{4})(?:@(\d{4}-\d{2}-\d{2}))?/);
    if (m) { if (m[2]) $("#asof").value = m[2]; showSample(m[1], false); }
    else showSample("A0016", false);
  }
  boot();
})();
