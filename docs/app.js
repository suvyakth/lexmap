/* Lexmap front end: vanilla JS.  All answers come from docs/engine.js evaluating
   docs/data/rules.json, so any address and any date can be answered client-side.
   Typed-in addresses: the U.S. Census Geocoder gives the legal city; in New Jersey the statewide
   public parcel layer adds building facts; anything still missing is asked, never guessed. */
(function () {
  "use strict";
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const D = {};
  let engine = null;
  let lang = "en";
  let current = null;   // { kind: "sample"|"live", id?, base: {stack, facts}, meta: {...}, answers: {} }
  let mapInstance = null;
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
      exemptions: "Exemptions", coverage: "Coverage logic", requirement: "Requirement",
      event_only: "Only if a specific event happens (demolition, conversion, temporary displacement)",
      no_rule_short: "No rule found in the corpus", no_rule_covers: "No rule in the corpus covers this building", category: "Category", governs: "What governs here", citation: "Citation",
      details: "Property facts and sources", ask_h: "Settle the unknowns", nla_inline: "Not legal advice",
    },
    es: {
      applies: "Aplica", superseded: "Desplazada", unknown: "Desconocido", not_yet_effective: "Aún no vigente", pending: "Proyecto pendiente",
      in_force: "Vigente", failed: "Fracasó", conflict: "Marcado para revisión", why: "Por qué", source: "Cita de la fuente", key: "Dato clave",
      no_rule: "No se encontró ninguna norma de esta categoría en el corpus para el estado o la ciudad de esta dirección.",
      year: "Año de construcción", units: "Unidades", type: "Tipo de propiedad", owner: "Datos del propietario", not_in_data: "no están en los datos",
      jurisdiction: "Jurisdicción legal", as_of: "a fecha de", corroborated: "También respaldado por",
      superseded_by: "Norma local que rige", official: "fuente oficial", secondary: "fuente secundaria",
      retrieved: "consultado", confidence: "confianza", none: "Ninguna",
      exemptions: "Exenciones", coverage: "Lógica de cobertura", requirement: "Requisito",
      event_only: "Solo si ocurre un hecho específico (demolición, conversión, desplazamiento temporal)",
      no_rule_short: "No se encontró ninguna norma en el corpus", no_rule_covers: "Ninguna norma del corpus cubre este edificio", category: "Categoría", governs: "Qué rige aquí", citation: "Cita",
      details: "Datos de la propiedad y fuentes", ask_h: "Resolver lo desconocido", nla_inline: "No es asesoría legal",
    },
  };
  const UI_ES = {
    tab_lookup: "Buscar dirección", tab_changes: "Qué está cambiando", tab_rules: "Todas las normas", tab_method: "Cómo funciona",
    nla: "No es asesoría legal.",
    nla_body: "Lexmap muestra lo que dice la ley pública de vivienda, a partir de un corpus fijo (consultado el 1 de octubre de 2026). No es una certificación de cumplimiento. Revise la fuente citada y consulte a un abogado o a una organización de inquilinos antes de actuar.",
    eyebrow: "California · Nueva Jersey · Massachusetts",
    hero: "¿Qué normas de vivienda aplican en esta dirección y qué está por cambiar?",
    hero_sub: "Topes de alquiler, desalojo con causa justa, depósitos, tarifas, selección de inquilinos y fijación algorítmica de rentas. Cada respuesta cita la ley de la que proviene y dice «desconocido» en lugar de adivinar.",
    search_go: "Buscar", asof_label: "Respuesta a fecha de",
    f1_h: "Cita la ley, palabra por palabra", f2_h: "Honesto sobre lo que no sabe", f3_h: "Cualquier fecha", f4_h: "Marca conflictos para revisión",
    how_h: "Cómo se construye una respuesta",
    changes_h: "Qué está cambiando", changes_sub: "Los casos de cambio del reto, calculados con el mismo motor.",
    rules_h: "Todas las normas extraídas", rules_sub: "Cada norma se extrajo automáticamente del corpus, se verificó contra el texto fuente y fue revisada por un segundo modelo.",
    gaps_h: "Donde el corpus no tiene norma", gaps_sub: "Combinaciones de jurisdicción y categoría sin norma vigente en el corpus. Lexmap las muestra como vacíos en lugar de adivinar.",
    method_h: "Cómo funciona Lexmap",
  };
  const UI_EN = {};
  const t = (k) => (I18N[lang] && I18N[lang][k]) || I18N.en[k] || k;

  // ------------------------------------------------------------------ data
  async function load() {
    const names = ["rules", "addresses", "sources", "gaps", "changes", "selfcheck", "meta", "unread"];
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
  function pill(status, extra) { return `<span class="pill ${status}">${esc(t(status))}${extra != null && extra !== "" ? " " + extra : ""}</span>`; }
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
      <span class="conf" title="Model-reported confidence (not a calibrated probability), capped at 0.6 for secondary-only sources and 0.75 for rules flagged for review">${t("confidence")} <span class="meter"><i style="width:${Math.round((r.confidence || 0) * 100)}%"></i></span> ${Math.round((r.confidence || 0) * 100)}%</span>`;
  }

  // ------------------------------------------------------------------ follow-up questions
  // Each missing fact the engine names becomes one question; answers are applied to the
  // building facts and every rule is re-evaluated immediately.
  const QUESTIONS = {
    residential: { label: "Is this a residential rental (homes or apartments people rent)?", type: "select",
      options: [["", "Not sure"], ["yes", "Yes"], ["no", "No (shop, office, owner's own home, vacant land…)"]] },
    property_type: { label: "What kind of building is it?", type: "select",
      options: [["", "Not sure"], ["multifamily", "Apartment building (3+ units)"], ["duplex", "Two-unit house (duplex)"], ["single_family", "Single-family house"], ["condo", "Condo or townhouse unit"]] },
    year_built: { label: "Year the building was built (or first occupied)", type: "number", min: 1700, max: 2035, hint: "Many rent and eviction rules turn on building age." },
    units: { label: "Number of units in the building", type: "number", min: 1, max: 5000, hint: "Small buildings are often exempt." },
    owner_occupied: { label: "Does the owner live in the building?", type: "select", options: [["", "Not sure"], ["yes", "Yes"], ["no", "No"]] },
    owner_type: { label: "Who owns it?", type: "select",
      options: [["", "Not sure"], ["natural_person", "A person or family"], ["llc", "An LLC"], ["corporation", "A corporation"], ["reit", "A REIT"], ["government", "A government body"]] },
    owner_unit_count: { label: "How many rental units does the owner have in total?", type: "number", min: 1, max: 100000 },
    owner_property_count: { label: "How many rental properties does the owner have?", type: "number", min: 1, max: 100000 },
  };
  const FIELD_TO_Q = { certificate_of_occupancy: "year_built", year_built: "year_built", units: "units", property_type: "property_type",
    owner_occupied: "owner_occupied", owner_type: "owner_type", owner_unit_count: "owner_unit_count", owner_property_count: "owner_property_count" };

  function mergedFacts(c) {
    const f = Object.assign({}, c.base.facts);
    const a = c.answers || {};
    if (a.year_built) { f.year_built = Number(a.year_built); f.year_source = "your answer"; }
    if (a.units) { f.units_min = f.units_max = Number(a.units); f.units_source = "your answer"; }
    if (a.property_type) {
      f.property_type = a.property_type; f.property_type_source = "your answer";
      if (!a.units && a.property_type === "single_family") { f.units_min = f.units_max = 1; }
      if (!a.units && a.property_type === "duplex") { f.units_min = f.units_max = 2; }
      if (!a.units && a.property_type === "multifamily" && (f.units_min == null || f.units_min < 3)) { f.units_min = 3; }
    }
    if (a.owner_occupied) f.owner_occupied = a.owner_occupied === "yes";
    if (a.owner_type) f.owner_type = a.owner_type;
    if (a.owner_unit_count) f.owner_unit_count = Number(a.owner_unit_count);
    if (a.owner_property_count) f.owner_property_count = Number(a.owner_property_count);
    return f;
  }

  function questionsPanel(entries, c, facts) {
    const unknown = entries.filter((e) => e.result === "unknown");
    const wanted = new Set();
    for (const e of unknown) for (const m of e.missing_facts || []) if (FIELD_TO_Q[m]) wanted.add(FIELD_TO_Q[m]);
    const keys = [];
    if (c.kind === "live") keys.push("residential");
    if (facts.property_type === null || (c.kind === "live" && !c.answers.property_type && !c.meta.parcel)) keys.push("property_type");
    for (const k of ["year_built", "units", "owner_occupied", "owner_type", "owner_unit_count", "owner_property_count"]) if (wanted.has(k)) keys.push(k);
    for (const k of Object.keys(c.answers)) if (!keys.includes(k) && QUESTIONS[k]) keys.push(k);   // keep answered questions visible
    if (!keys.length) return "";
    const fields = [...new Set(keys)].map((k) => {
      const q = QUESTIONS[k], val = c.answers[k] != null ? c.answers[k] : (k === "residential" ? (c.meta.residential || "") : "");
      const input = q.type === "select"
        ? `<select data-q="${k}" id="q-${k}">${q.options.map(([v, l]) => `<option value="${v}"${String(val) === v ? " selected" : ""}>${esc(l)}</option>`).join("")}</select>`
        : `<input data-q="${k}" id="q-${k}" type="number" min="${q.min}" max="${q.max}" value="${esc(val)}" placeholder="Not sure">`;
      return `<div class="q"><label for="q-${k}">${esc(q.label)}</label>${input}${q.hint ? `<div class="hint">${esc(q.hint)}</div>` : ""}</div>`;
    }).join("");
    const head = unknown.length
      ? `${unknown.length} answer${unknown.length === 1 ? " is" : "s are"} unknown because a fact is missing. Answer what you know and every rule is re-checked instantly. Leave a question as “Not sure” and Lexmap keeps saying “unknown”.`
      : `Answer what you know to refine the result. Nothing is guessed.`;
    return `<div class="card ask"><h3>${t("ask_h")}</h3><p>${esc(head)}</p><div class="qs">${fields}</div></div>`;
  }

  // ------------------------------------------------------------------ lookup view
  function render() {
    if (!current) return;
    const asOf = $("#asof").value || DEFAULT_ASOF;
    const facts = mergedFacts(current);
    const addr = { stack: current.base.stack, facts };
    const all = engine.lookup(addr, asOf);
    const residential = current.answers.residential || current.meta.residential || "";
    document.body.classList.add("has-result");
    $("#landing").hidden = true;
    let html = addressCard(addr, all, asOf);
    if (residential === "no") {
      html += questionsPanel([], current, facts);
      html += `<div class="card notres"><h3>Not a residential rental, so these rules do not apply</h3>
        <p>${esc(current.meta.residentialWhy || "You said this property is not a residential rental.")} The rules Lexmap covers govern residential tenancies: rent increases, evictions, deposits, application fees, tenant screening and rent-setting software. If part of the property is rented as housing, change the answer above to “Yes”.</p></div>`;
      $("#result").innerHTML = html;
      initMap();
      return;
    }
    const entries = all.filter((e) => !e.event_only);
    const events = all.filter((e) => e.event_only);
    const by = {}, evBy = {};
    for (const e of entries) (by[e.category] = by[e.category] || []).push(e);
    for (const e of events) (evBy[e.category] = evBy[e.category] || []).push(e);
    html += questionsPanel(entries, current, facts);
    html += glance(by, addr, asOf);
    for (const c of D.meta.categories) {
      const es = by[c] || [];
      const ev = evBy[c] || [];
      html += `<section class="cat" id="cat-${c}"><div class="cat-h"><h3>${esc(catName(c))}</h3><span class="n">${es.length} rule${es.length === 1 ? "" : "s"}</span></div>`;
      if (!es.length) html += noRuleCard(c, addr, asOf);
      for (const e of es) html += ruleCard(e);
      if (ev.length) html += `<details class="src evgroup"><summary>${t("event_only")} (${ev.length})</summary>${ev.map(ruleCard).join("")}</details>`;
      html += `</section>`;
    }
    $("#result").innerHTML = html;
    initMap();
  }

  function addressCard(addr, all, asOf) {
    const c = current, f = addr.facts, m = c.meta;
    const entries = all.filter((e) => !e.event_only);
    const count = (r) => entries.filter((e) => e.result === r).length;
    const stackHtml = addr.stack.map((j) => `<span class="lvl">${esc(j.length === 2 ? D.meta.states[j] : j)}</span>`).join('<span class="sep">›</span>');
    const unread = addr.stack.filter((j) => j.includes(",")).flatMap((j) => (D.unread[j] || []).map((u) => [j, u]));
    const unreadNote = unread.length ? [`${unread.length} ${unread[0][0]} source document${unread.length === 1 ? " is" : "s are"} link-only (${[...new Set(unread.map(([, u]) => u.source_type))].join(", ")}) and could not be read, so local rules they contain (for example rent control) are not reflected here.`] : [];
    const flags = (m.flags || []).concat((f.flags || []).map((x) => "Assessor flag: " + x), unreadNote).map((x) => `<li>${esc(x)}</li>`).join("");
    const unitsTxt = f.units_min == null || (f.units_min <= 1 && f.units_max == null) ? t("not_in_data") : Lexmap.unitsText(f);
    const typeTxt = f.property_type === undefined || f.property_type === "multifamily" ? (f.units_max != null && f.units_max <= 4 && f.units_min < 3 ? "small residential (1–4 units)" : "apartment building")
      : f.property_type === null ? "unknown" : f.property_type.replace(/_/g, " ");
    const ownerTxt = f.owner_occupied != null || f.owner_type ? [f.owner_occupied != null ? (f.owner_occupied ? "owner lives there" : "owner does not live there") : "", f.owner_type ? f.owner_type.replace(/_/g, " ") : ""].filter(Boolean).join(", ") : t("not_in_data");
    const details = (m.details || []).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
    const hasMap = m.lat != null && m.lon != null;
    return `<div class="card addr">
      <div class="addr-grid">
        <div>
          <h2>${esc(m.title)}</h2>
          <div class="stack"><b>${t("jurisdiction")}:</b> ${stackHtml}</div>
          <div class="meta-line">${t("as_of")} <b>${esc(asOf)}</b> · ${esc(m.idLabel || "")} · <span class="nla-inline">${t("nla_inline")}</span></div>
          <div class="facts">
            <div class="fact"><div class="k">${t("year")}</div><div class="v">${f.year_built || "—"}</div><div class="p">${esc(f.year_source || "")}</div></div>
            <div class="fact"><div class="k">${t("units")}</div><div class="v">${esc(unitsTxt)}</div><div class="p">${esc(f.units_source || "")}</div></div>
            <div class="fact"><div class="k">${t("type")}</div><div class="v">${esc(typeTxt)}</div><div class="p">${esc(f.property_type_source || "")}</div></div>
            <div class="fact"><div class="k">${t("owner")}</div><div class="v">${esc(ownerTxt)}</div><div class="p">${ownerTxt === t("not_in_data") ? "No owner data is used; owner-based exemptions stay “unknown” unless you answer or building facts rule them out." : "your answer"}</div></div>
          </div>
          ${details ? `<details class="details" open><summary>${t("details")}</summary><dl class="dl">${details}</dl></details>` : ""}
          ${flags ? `<ul class="flags">${flags}</ul>` : ""}
        </div>
        <div>${hasMap ? `<div id="map" class="map" role="img" aria-label="Map of the address"></div>` : `<div class="map nomap">No coordinates for this address (the Census geocoder found no exact match), so no map.</div>`}</div>
      </div>
      <div class="tally">
        ${pill("applies", count("applies"))} ${pill("unknown", count("unknown"))} ${pill("superseded", count("superseded"))}
        ${pill("not_yet_effective", count("not_yet_effective"))} ${pill("pending", count("pending"))}
        ${entries.some((e) => e.conflict_flag) ? `<span class="pill conflict">⚑ ${t("conflict")}: ${entries.filter((e) => e.conflict_flag).length}</span>` : ""}
      </div>
    </div>`;
  }

  function initMap() {
    const m = current && current.meta;
    if (mapInstance) { try { mapInstance.remove(); } catch (e) { /* ignore */ } mapInstance = null; }
    if (!m || m.lat == null || m.lon == null || typeof window.L === "undefined" || !document.getElementById) return;
    const el = document.getElementById("map");
    if (!el) return;
    try {
      mapInstance = L.map(el, { scrollWheelZoom: false }).setView([m.lat, m.lon], 17);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(mapInstance);
      L.marker([m.lat, m.lon]).addTo(mapInstance).bindPopup(esc(m.matched || m.title));
    } catch (e) { el.classList.add("nomap"); el.textContent = "Map unavailable."; }
  }

  // One line per category: what governs here, at a glance (mirrors the brief's illustrative output).
  function glance(by, addr, asOf) {
    const rank = { applies: 0, unknown: 1, not_yet_effective: 2, superseded: 3, pending: 4 };
    let rows = "";
    for (const c of D.meta.categories) {
      const es = (by[c] || []).slice().sort((a, b) => rank[a.result] - rank[b.result]);
      const link = `<button class="catlink" data-cat="${c}">${esc(catName(c))}</button>`;
      if (!es.length) {
        const why = omittedRules(c, addr, asOf);
        const bars = D.rules.filter((r) => r.category === c && addr.stack.includes(r.jurisdiction) && r.subject === "municipality" && r.status === "in_force" && !(r.coverage_logic || {}).covers);
        const txt = bars.length ? `State law bars local rules of this kind (${bars.map((r) => r.citation).join(", ")})`
          : why.length ? t("no_rule_covers") : t("no_rule_short");
        rows += `<tr><td>${link}</td><td colspan="2" class="muted">${esc(txt)}</td></tr>`;
        continue;
      }
      const main = es[0], r = main.rule;
      const more = es.length > 1 ? ` <span class="muted">+${es.length - 1} more</span>` : "";
      rows += `<tr><td>${link}</td>
        <td>${pill(main.result)} ${main.conflict_flag ? '<span class="pill conflict">⚑</span> ' : ""}<b>${esc(r.title)}</b>${more}${r.key_value ? `<div class="muted">${esc(r.key_value)}</div>` : ""}</td>
        <td class="c">${esc(r.citation)}</td></tr>`;
    }
    return `<div class="card glance"><table><thead><tr><th>${t("category")}</th><th>${t("governs")}</th><th>${t("citation")}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  // Rules of this category in force here that the engine left out, with the reason (exempt / not covered).
  function omittedRules(c, addr, asOf) {
    const out = [];
    for (const r of D.rules) {
      if (r.category !== c || !addr.stack.includes(r.jurisdiction) || r.subject === "municipality" || r.scope === "event") continue;
      if (r.status === "failed" || r.status === "pending") continue;
      const only = r.applies_only_in || [];
      if (only.length && !only.some((x) => addr.stack.includes(x))) continue;
      if (r.end_date && r.end_date <= asOf) { out.push([r, `expired ${r.end_date}`]); continue; }
      const tc = [], te = [];
      const cov = Lexmap.evaluate((r.coverage_logic || {}).covers, addr.facts, asOf, tc);
      if (cov === false) { out.push([r, "outside its coverage: " + tc.filter((l) => l.result === false && !l.irrelevant).map((l) => Lexmap.describeLeaf(l, addr.facts)).join("; ")]); continue; }
      const ex = (r.coverage_logic || {}).exempt ? Lexmap.evaluate(r.coverage_logic.exempt, addr.facts, asOf, te) : false;
      if (ex === true) out.push([r, "exempt: " + te.filter((l) => l.result === true && !l.irrelevant).map((l) => Lexmap.describeLeaf(l, addr.facts)).join("; ")]);
      else if (r.level === "city") out.push([r, "a state law exempts this building from local rules of this kind"]);
    }
    return out;
  }

  // "No rule" is still an answer: show what the corpus says (state bars on local rules, failed measures).
  function noRuleCard(c, addr, asOf) {
    const omitted = omittedRules(c, addr, asOf);
    const bits = omitted.map(([r, why]) => `<li><b>${esc(r.team_rule_id)}</b> (${esc(r.citation)}) does not cover this building: ${esc(why)}.</li>`);
    for (const r of D.rules) {
      if (r.category !== c || !addr.stack.includes(r.jurisdiction)) continue;
      if (r.subject === "municipality" && r.status === "in_force" && !(r.coverage_logic || {}).covers)
        bits.push(`<li><b>${esc(r.citation)}</b>: ${esc(plain(r))}</li>`);
      if (r.status === "failed")
        bits.push(`<li>${pill("failed")} <b>${esc(r.title)}</b> (${esc(r.citation)}): never became law, so it is not reported.</li>`);
    }
    return `<div class="empty">${omitted.length ? t("no_rule_covers") + "." : t("no_rule")}${bits.length ? `<ul class="flags">${bits.join("")}</ul>` : ""}</div>`;
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

  // ------------------------------------------------------------------ sample addresses
  function showSample(id, push) {
    const a = D.addrById[id] || D.addrById["A0016"];
    if (!a) return;
    syncChips();
    const details = [
      ["Assessor record", `${a.source_dataset}; use code ${a.use_code || "—"} (${a.use || "—"})`],
      ["Census match", a.matched || "no exact match (mailing city used)"],
      ["County", a.county || "—"],
      ["Census place", a.census_place || "—"],
      ["Geocoding", `${a.geo_method.replace(/_/g, " ")} (${a.geo_confidence} confidence)`],
    ];
    if (a.lat != null) details.push(["Coordinates", `${Number(a.lat).toFixed(5)}, ${Number(a.lon).toFixed(5)}`]);
    current = { kind: "sample", id: a.id, base: { stack: a.stack, facts: a.facts }, answers: (current && current.id === a.id) ? current.answers : {},
      meta: { title: `${a.street}, ${a.postal_city}, ${a.state}`, matched: a.matched, flags: a.flags, idLabel: `${a.id} · sample address`,
        lat: a.lat, lon: a.lon, details, residential: "yes" } };
    $("#q").value = `${a.street}, ${a.postal_city}, ${a.state}`;
    render();
    if (push !== false) setHash();
  }

  function setHash() {
    const asOf = $("#asof").value;
    if (current && current.kind === "sample") history.replaceState(null, "", `#${current.id}@${asOf}`);
    else history.replaceState(null, "", location.pathname);
  }

  // ------------------------------------------------------------------ live lookup: Census + NJ parcels
  const STATE_CODES = { California: "CA", "New Jersey": "NJ", Massachusetts: "MA" };
  const PLACE_TO_CITY = {
    "CA|Los Angeles city": "Los Angeles, CA", "CA|San Francisco city": "San Francisco, CA", "CA|San Diego city": "San Diego, CA",
    "CA|Berkeley city": "Berkeley, CA", "CA|Santa Ana city": "Santa Ana, CA", "NJ|Jersey City city": "Jersey City, NJ",
    "NJ|Hoboken city": "Hoboken, NJ", "NJ|Newark city": "Newark, NJ", "MA|Boston city": "Boston, MA", "MA|Cambridge city": "Cambridge, MA",
  };
  const NJ_CLASS = {
    "1": ["Vacant land", "no"], "2": ["Residential (four families or fewer)", "yes"], "3A": ["Farm (regular)", "no"], "3B": ["Farm (qualified)", "no"],
    "4A": ["Commercial", "no"], "4B": ["Industrial", "no"], "4C": ["Apartment (five or more units)", "yes"],
    "5A": ["Railroad", "no"], "5B": ["Railroad", "no"], "6A": ["Business personal property", "no"], "6B": ["Petroleum refinery", "no"],
    "15A": ["Public school", "no"], "15B": ["Other school", "no"], "15C": ["Public property", ""], "15D": ["Church or charitable", "no"],
    "15E": ["Cemetery", "no"], "15F": ["Other exempt", ""],
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
  async function njParcel(lon, lat, matched) {
    const params = new URLSearchParams({
      geometry: JSON.stringify({ x: lon, y: lat, spatialReference: { wkid: 4326 } }), geometryType: "esriGeometryPoint",
      spatialRel: "esriSpatialRelIntersects", distance: "30", units: "esriSRUnit_Meter", returnGeometry: "false", f: "json",
      outFields: "PROP_CLASS,PROP_LOC,PCLBLOCK,PCLLOT,MUN_NAME,COUNTY,BLDG_DESC,LAND_DESC,CALC_ACRE,YR_CONSTR,DWELL,COMM_DWELL,NET_VALUE,LAST_YR_TX,PROP_USE",
    });
    const ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctl ? setTimeout(() => ctl.abort(), 12000) : null;
    try {
      const r = await fetch("https://services2.arcgis.com/XVOqAjTOJ5P6ngMu/arcgis/rest/services/Parcels_Composite_NJ_WM/FeatureServer/0/query?" + params, ctl ? { signal: ctl.signal } : {});
      const j = await r.json();
      const feats = (j.features || []).map((f) => f.attributes);
      if (!feats.length) return null;
      // only accept the parcel whose assessed location carries this house number (never a neighbour's)
      const num = parseInt((String(matched || "").match(/^\s*(\d+)/) || [])[1], 10);
      if (isNaN(num)) return feats.length === 1 ? feats[0] : null;
      const rank = (a) => (/PARKING|GARAGE/i.test(a.BLDG_DESC || "") ? 2 : 0) + (["2", "4C"].includes(String(a.PROP_CLASS || "").toUpperCase()) ? 0 : 1);
      const ranked = feats.slice().sort((a, b) => rank(a) - rank(b));
      return ranked.find((a) => {
        const mm = String(a.PROP_LOC || "").match(/^\s*(\d+)(?:\s*-\s*(\d+))?/);
        if (!mm) return false;
        const lo = parseInt(mm[1], 10), hi = mm[2] ? parseInt(mm[2], 10) : lo;
        return num >= Math.min(lo, hi) && num <= Math.max(lo, hi);
      }) || null;
    } catch (e) { return null; } finally { if (timer) clearTimeout(timer); }
  }
  function njFacts(p) {
    const cls = String(p.PROP_CLASS || "").toUpperCase().trim();
    const [clsName, resi] = NJ_CLASS[cls] || [`Class ${cls || "?"}`, ""];
    const yr = parseInt(p.YR_CONSTR, 10);
    const dwell = Math.max(parseInt(p.DWELL, 10) || 0, parseInt(p.COMM_DWELL, 10) || 0);
    const facts = { year_built: yr > 1700 && yr <= 2035 ? yr : null, year_source: yr > 1700 ? "NJ parcel record (MOD-IV)" : "not in the parcel record",
      units_min: 1, units_max: null, units_source: "not in the parcel record", property_type_source: `NJ property class ${cls}: ${clsName}` };
    if (dwell > 0) { facts.units_min = facts.units_max = dwell; facts.units_source = "NJ parcel record (dwellings)"; }
    else if (cls === "4C") {
      const comps = (String(p.BLDG_DESC || "").match(/(\d+)\s*U(?![A-Z])/g) || []).map((x) => parseInt(x, 10));
      facts.units_min = Math.max(5, ...comps); facts.units_source = comps.length ? `building description ${p.BLDG_DESC}` : "class 4C means 5+ units";
    } else if (cls === "2") { facts.units_min = 1; facts.units_max = 4; facts.units_source = "class 2 means four families or fewer"; }
    const condoUnit = cls === "2" && /(\d\s*BR|CONDO|STUDIO|UNIT|PARKING|GARAGE)/i.test(String(p.BLDG_DESC || ""));
    if (condoUnit) {
      facts.units_min = 1; facts.units_max = null; facts.units_source = "this parcel is one condominium unit; building size not in the record";
    }
    if (cls === "4C") facts.property_type = "multifamily";
    else if (condoUnit) facts.property_type = "condo";
    else if (cls === "2") {
      if (facts.units_min === facts.units_max && facts.units_min === 1) facts.property_type = "single_family";
      else if (facts.units_min === facts.units_max && facts.units_min === 2) facts.property_type = "duplex";
      else if (facts.units_min >= 3) facts.property_type = "multifamily";
    } else facts.property_type = null;
    const details = [
      ["Parcel", `Block ${p.PCLBLOCK || "?"}, Lot ${p.PCLLOT || "?"}, ${p.MUN_NAME || ""}${p.COUNTY ? ", " + p.COUNTY + " County" : ""}`],
      ["Assessed location", p.PROP_LOC || "—"],
      ["Property class", `${cls} · ${clsName}`],
      ["Building description", p.BLDG_DESC || "—"],
      ["Year built", yr > 1700 ? String(yr) : "not recorded"],
      ["Dwellings", dwell > 0 ? String(dwell) : "not recorded"],
      ["Lot", p.LAND_DESC || (p.CALC_ACRE ? `${p.CALC_ACRE} acres` : "—")],
      ["Net assessed value", p.NET_VALUE ? "$" + Number(p.NET_VALUE).toLocaleString("en-US") : "—"],
    ];
    return { facts, details, residential: resi, residentialWhy: resi === "no" ? `New Jersey's parcel record classes this property as ${cls} (${clsName}), not housing.` : "", cls };
  }

  async function liveLookup(address) {
    $("#suggest").hidden = true;
    $("#landing").hidden = true;
    $("#result").innerHTML = `<div class="spinner">Finding the legal jurisdiction with the U.S. Census Geocoder…</div>`;
    $("#result").scrollIntoView && $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      const data = await jsonp("https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?benchmark=Public_AR_Current&vintage=Current_Current&address=" + encodeURIComponent(address));
      const m = ((data.result || {}).addressMatches || [])[0];
      if (!m) { $("#result").innerHTML = `<div class="empty">The Census geocoder found no match for that address. Check the spelling and include the city and state.</div>`; current = null; setHash(); return; }
      const g = m.geographies || {};
      const stName = ((g.States || [])[0] || {}).NAME;
      const st = STATE_CODES[stName];
      if (!st) { $("#result").innerHTML = `<div class="empty">That address is in ${esc(stName || "another state")}. Lexmap's corpus covers California, New Jersey and Massachusetts only.</div>`; current = null; setHash(); return; }
      const place = ((g["Incorporated Places"] || [])[0] || {}).NAME;
      let city = place ? PLACE_TO_CITY[st + "|" + place] : null;
      if (!city) for (const cs of g["County Subdivisions"] || []) city = city || PLACE_TO_CITY[st + "|" + cs.NAME];
      const lon = m.coordinates && m.coordinates.x, lat = m.coordinates && m.coordinates.y;
      const county = ((g.Counties || [])[0] || {}).NAME;
      const flags = [];
      if (!city) flags.push(`Census places this address in ${place || "an unincorporated area"}, outside the 10 cities in the corpus, so only ${D.meta.states[st]} statewide rules are evaluated.`);
      let facts = { year_built: null, year_source: "not known: answer below", units_min: 1, units_max: null, units_source: "not known: answer below",
        property_type: null, property_type_source: "not known: answer below" };
      const details = [["Census match", m.matchedAddress], ["County", county || "—"], ["Census place", place || "unincorporated"],
        ["Coordinates", lat != null ? `${lat.toFixed(5)}, ${lon.toFixed(5)}` : "—"]];
      let residential = "", residentialWhy = "", parcel = false;
      if (st === "NJ" && lon != null) {
        $("#result").innerHTML = `<div class="spinner">Reading New Jersey's public parcel record for building facts…</div>`;
        const p = await njParcel(lon, lat, m.matchedAddress);
        if (p) {
          const nf = njFacts(p);
          facts = nf.facts; details.push(...nf.details); residential = nf.residential; residentialWhy = nf.residentialWhy; parcel = true;
          details.push(["Parcel source", "NJ Parcels & MOD-IV composite (NJOGIS), public record; owner names not used"]);
        } else flags.push("No matching New Jersey parcel record was found, so building facts are asked below.");
      } else {
        flags.push("Building facts for this state are not looked up automatically; answer the questions below to settle unknowns.");
      }
      current = { kind: "live", base: { stack: [st].concat(city ? [city] : []), facts }, answers: {},
        meta: { title: address, matched: m.matchedAddress, flags, idLabel: "live lookup", lat, lon, details, residential, residentialWhy, parcel } };
      setHash();
      render();
    } catch (e) {
      current = null;
      setHash();
      $("#result").innerHTML = `<div class="empty">${esc(e.message)}. The 500 sample addresses still work offline.</div>`;
    }
  }

  // ------------------------------------------------------------------ search (samples + any address)
  function setupSearch() {
    const q = $("#q"), box = $("#suggest");
    let sel = -1, items = [];
    const norm = (s) => s.toLowerCase().replace(/[^a-z0-9 ]/g, " ");
    const index = D.addresses.map((a) => ({ a, k: norm(`${a.id} ${a.street} ${a.postal_city} ${a.city || ""} ${a.state} ${a.zip || ""}`) }));
    function draw() {
      const raw = q.value.trim(), s = norm(raw).trim();
      if (!s) { box.hidden = true; return; }
      const toks = s.split(/\s+/);
      items = index.filter((x) => toks.every((tk) => x.k.includes(tk))).slice(0, 8).map((x) => ({ id: x.a.id, a: x.a }));
      if (raw.length >= 6) items.push({ live: raw });
      box.innerHTML = items.map((it, i) => it.live
        ? `<li role="option" class="live" data-live="1" ${i === sel ? 'aria-selected="true"' : ""}><span>Look up “${esc(it.live)}” (any CA, NJ or MA address)</span><span class="m">live</span></li>`
        : `<li role="option" data-id="${it.id}" ${i === sel ? 'aria-selected="true"' : ""}><span>${esc(it.a.street)}, ${esc(it.a.postal_city)}</span><span class="m">${esc(it.a.city || it.a.state)} · sample ${it.id}</span></li>`).join("");
      box.hidden = !items.length;
    }
    function choose(it) {
      box.hidden = true;
      if (!it) return;
      if (it.live) liveLookup(it.live); else { showSample(it.id); $("#result").scrollIntoView && $("#result").scrollIntoView({ behavior: "smooth", block: "start" }); }
    }
    function submit() {
      const raw = q.value.trim();
      if (!raw) return;
      if (sel >= 0 && items[sel]) return choose(items[sel]);
      const idm = raw.toUpperCase().match(/^A\d{4}$/);
      if (idm && D.addrById[idm[0]]) return choose({ id: idm[0] });
      const exact = D.addresses.find((a) => `${a.street}, ${a.postal_city}, ${a.state}`.toLowerCase() === raw.toLowerCase());
      if (exact) return choose({ id: exact.id });
      choose({ live: raw });
    }
    q.addEventListener("input", () => { sel = -1; draw(); });
    q.addEventListener("keydown", (ev) => {
      if (ev.key === "ArrowDown" && !box.hidden) { sel = Math.min(items.length - 1, sel + 1); draw(); ev.preventDefault(); }
      else if (ev.key === "ArrowUp" && !box.hidden) { sel = Math.max(0, sel - 1); draw(); ev.preventDefault(); }
      else if (ev.key === "Enter") { submit(); ev.preventDefault(); }
      else if (ev.key === "Escape") box.hidden = true;
    });
    $("#go").addEventListener("click", submit);
    box.addEventListener("mousedown", (ev) => {
      const li = ev.target.closest("li[data-id], li[data-live]");
      if (!li) return;
      ev.preventDefault();
      choose(li.dataset.live ? { live: q.value.trim() } : { id: li.dataset.id });
    });
    document.addEventListener("click", (ev) => { if (!ev.target.closest(".search-box")) box.hidden = true; });
    const examples = [
      ["A0016", "San Francisco, 1926"], ["A0105", "San Francisco, 2019"], ["A0107", "Los Angeles, built 1978"],
      ["A0065", "Dorchester → Boston"], ["A0002", "Hoboken"], ["A0005", "Berkeley (no year)"],
    ].filter(([id]) => D.addrById[id]);
    $("#examples").innerHTML = examples.map(([id, l]) => `<button class="chip" data-id="${id}">${esc(l)}</button>`).join("")
      + `<button class="chip" data-live="1118 Main St, River Edge, NJ 07661">A shop in NJ (live)</button>`;
    $("#examples").addEventListener("click", (ev) => {
      const b = ev.target.closest("button");
      if (!b) return;
      if (b.dataset.live) { q.value = b.dataset.live; liveLookup(b.dataset.live); }
      else if (b.dataset.id) { showSample(b.dataset.id); $("#result").scrollIntoView && $("#result").scrollIntoView({ behavior: "smooth", block: "start" }); }
    });
  }

  function setupQuestions() {
    $("#result").addEventListener("change", (ev) => {
      const el = ev.target.closest("[data-q]");
      if (!el || !current) return;
      const k = el.dataset.q, v = String(el.value || "").trim();
      if (v) current.answers[k] = v; else delete current.answers[k];
      const y = window.scrollY;
      render();
      window.scrollTo(0, y);
    });
  }

  function syncChips() {
    $$("#date-chips .chip").forEach((c) => c.classList.toggle("active", c.dataset.d === $("#asof").value));
  }

  function setupDates() {
    const chips = [["2025-12-31", "Dec 31, 2025"], ["2026-01-02", "Jan 2, 2026"], ["2026-10-01", "Oct 1, 2026 (corpus date)"], ["2027-07-02", "Jul 2, 2027"]];
    $("#date-chips").innerHTML = chips.map(([d, l]) => `<button class="chip${d === DEFAULT_ASOF ? " active" : ""}" data-d="${d}">${l}</button>`).join("");
    const rerender = () => { syncChips(); if (current) { render(); setHash(); } };
    $("#date-chips").addEventListener("click", (ev) => { const b = ev.target.closest("button[data-d]"); if (b) { $("#asof").value = b.dataset.d; rerender(); } });
    $("#asof").addEventListener("change", rerender);
  }

  function renderStats() {
    const sc = D.selfcheck.summary;
    const cities = new Set(D.addresses.map((a) => a.city).filter(Boolean)).size;
    $("#stats").innerHTML = [
      [D.rules.length, "rules extracted from 67 law documents"],
      [D.addresses.length, `sample buildings in ${cities} cities, plus any address you type`],
      ["100%", "of quotes found word for word in their source"],
      [`${sc.passed}/${sc.total}`, "self-checks passing, incl. all change tests"],
    ].map(([n, l]) => `<div class="card stat"><div class="n">${esc(n)}</div><div class="l">${esc(l)}</div></div>`).join("");
  }

  function goHome() {
    current = null;
    if (mapInstance) { try { mapInstance.remove(); } catch (e) { /* ignore */ } mapInstance = null; }
    $("#result").innerHTML = "";
    $("#landing").hidden = false;
    document.body.classList.remove("has-result");
    $("#q").value = "";
    history.replaceState(null, "", location.pathname);
    switchTab("lookup");
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
        <div class="exp">Document <code>${esc(String(w.document).split(/[\/]/).pop())}</code> (${esc(w.jurisdiction)}) was written by us to show how Lexmap handles a law it has never seen. It is not a real law.</div>
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
      syncChips();
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
        ${r.source_notes ? `<div class="kv"><b>Resolved source discrepancy:</b> ${esc(r.source_notes)}</div>` : ""}
        ${r.scope === "event" ? `<div class="kv"><b>Scope:</b> event-only (applies only when a specific event happens; not reported as applying to buildings in lookups.json)</div>` : ""}
        ${(r.applies_only_in || []).length ? `<div class="kv"><b>Applies only in:</b> ${esc(r.applies_only_in.join(", "))}</div>` : ""}
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
        <div class="card step"><div class="num">3×</div><h3>Reconciled, reviewed, re-sourced</h3><p>A stronger model merges duplicates across sources. An independent QA pass checks every cut-off, its scope, citation and status. A third pass swaps secondary quotes for official text where one exists.</p></div>
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
      <h2>Open questions in the law</h2>
      <p class="sub">Generated from the rule records. Unresolved conflicts are flagged on every affected answer. Resolved discrepancies are kept so a reviewer can see what the sources disagreed on and why one reading was chosen.</p>
      <div class="two">
        <div class="card"><h3>Flagged for human review</h3><ul>${D.rules.filter((r) => r.conflict_flag).map((r) => `<li><b>${esc(r.team_rule_id)}</b> (${esc(r.citation)}): ${esc(r.conflict_note || "")}</li>`).join("") || "<li>None</li>"}</ul></div>
        <div class="card"><h3>Source discrepancies resolved by review</h3><ul>${D.rules.filter((r) => r.source_notes).map((r) => `<li><b>${esc(r.team_rule_id)}</b>: ${esc(r.source_notes)}</li>`).join("") || "<li>None</li>"}</ul></div>
      </div>
      <div class="two" style="margin-top:14px">
        <div class="card"><h3>Event-only rules (not counted as applying to a building)</h3><ul>${D.rules.filter((r) => r.scope === "event").map((r) => `<li><b>${esc(r.team_rule_id)}</b>: ${esc(r.title)}${(r.applies_only_in || []).length ? " (only in " + esc(r.applies_only_in.join(", ")) + ")" : ""}</li>`).join("") || "<li>None</li>"}</ul></div>
        <div class="card"><h3>Secondary-source rules (confidence capped at 0.6)</h3><ul>${D.rules.filter((r) => !r.official_source).map((r) => `<li><b>${esc(r.team_rule_id)}</b>: ${esc(r.title)} (<a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.source_doc_id)}</a>)</li>`).join("") || "<li>None</li>"}</ul></div>
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
    $$(".tabs button").forEach((b) => { b.classList.toggle("active", b.dataset.tab === name); b.setAttribute && b.setAttribute("aria-selected", String(b.dataset.tab === name)); });
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
    if (current) render();
  }

  async function boot() {
    try { await load(); } catch (e) { $("#result").innerHTML = `<div class="empty">Could not load data: ${esc(e.message)}</div>`; return; }
    $$(".tabs button").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
    $("#result").addEventListener("click", (ev) => {
      const b = ev.target.closest("button.catlink");
      if (!b) return;
      const sec = document.getElementById("cat-" + b.dataset.cat);
      if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $$(".lang button").forEach((b) => b.addEventListener("click", () => { lang = b.dataset.lang; applyLang(); }));
    $("#home").addEventListener("click", (ev) => { ev.preventDefault(); goHome(); });
    setupSearch(); setupDates(); setupQuestions(); renderStats(); renderChanges(); renderRules(); renderMethod();
    const m = location.hash.match(/^#(A\d{4})(?:@(\d{4}-\d{2}-\d{2}))?/);
    if (m) { if (m[2] && m[2] >= "2024-01-01") $("#asof").value = m[2]; syncChips(); showSample(m[1], false); }
    window.__lexmap = { liveLookup, showSample, render, answer: (k, v) => { if (current) { if (v) current.answers[k] = v; else delete current.answers[k]; render(); } }, state: () => current };
  }
  boot();
})();
