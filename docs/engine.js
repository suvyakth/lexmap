/* Lexmap rule engine (browser + Node).  A line-by-line port of lexmap/coverage.py and
   lexmap/lookup.py.  tests/parity.js checks that it returns exactly the same answers as the
   Python engine for all 500 sample addresses at four dates. */
(function (root) {
  "use strict";
  const T = true, F = false, U = null;
  const INF = Infinity;
  const OWNER_FIELDS = new Set(["owner_occupied", "owner_type", "owner_property_count", "owner_unit_count", "other_fact"]);
  const FIELD_LABEL = {
    certificate_of_occupancy: "certificate-of-occupancy date", year_built: "year built",
    units: "number of units", property_type: "property type",
    owner_occupied: "whether the owner lives on site", owner_type: "owner type",
    owner_property_count: "how many properties the owner has", owner_unit_count: "how many units the owner has",
    other_fact: "a building condition not in the data",
  };
  const pad = (n, w) => String(n).padStart(w || 2, "0");
  const iso = (y, m, d) => `${pad(y, 4)}-${pad(m)}-${pad(d)}`;
  const lastDay = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate();

  function parseDate(v, end) {
    const s = String(v).trim();
    const parts = s.split("-");
    if (!parts.every((p) => /^\d+$/.test(p))) return null;
    const n = parts.map(Number);
    if (n.length === 3) return iso(n[0], n[1], n[2]);
    if (n.length === 2) return end ? iso(n[0], n[1], lastDay(n[0], n[1])) : iso(n[0], n[1], 1);
    if (n.length === 1) return end ? iso(n[0], 12, 31) : iso(n[0], 1, 1);
    return null;
  }
  function minusYears(asOf, n) {
    let [y, m, d] = asOf.split("-").map(Number);
    const ty = y - n;
    if (m === 2 && d === 29 && !((ty % 4 === 0 && ty % 100 !== 0) || ty % 400 === 0)) d = 28;
    return iso(y - n, m, d);
  }
  function cmpInterval(lo, hi, op, v) {
    switch (op) {
      case "<=": return hi <= v ? T : (lo > v ? F : U);
      case "<": return hi < v ? T : (lo >= v ? F : U);
      case ">=": return lo >= v ? T : (hi < v ? F : U);
      case ">": return lo > v ? T : (hi <= v ? F : U);
      case "==": return (lo === hi && hi === v) ? T : ((v < lo || v > hi) ? F : U);
      case "!=": { const r = cmpInterval(lo, hi, "==", v); return r === U ? U : !r; }
      default: return U;
    }
  }
  function interval(field, facts) {
    const yb = facts.year_built;
    if (field === "year_built") return yb ? [yb, yb] : null;
    if (field === "certificate_of_occupancy") return yb ? [iso(yb, 1, 1), iso(yb, 12, 31)] : null;
    if (field === "units") {
      const lo = facts.units_min == null ? 2 : facts.units_min;
      const hi = facts.units_max == null ? INF : facts.units_max;
      return [lo, hi];
    }
    return null;
  }
  function resolveValue(v, field, op, asOf) {
    if (v && typeof v === "object" && !Array.isArray(v) && "as_of_minus_years" in v) {
      const n = parseInt(v.as_of_minus_years, 10);
      if (isNaN(n)) return null;
      const d = minusYears(asOf, n);
      return field === "certificate_of_occupancy" ? d : Number(d.slice(0, 4));
    }
    if (field === "certificate_of_occupancy") {
      if (Array.isArray(v) || v === null || v === undefined) return null;
      if (typeof v === "number") v = String(Math.trunc(v));
      return parseDate(v, op === "<=" || op === ">");
    }
    if (["year_built", "units", "owner_property_count", "owner_unit_count"].includes(field)) {
      if (Array.isArray(v) || v === null || v === undefined || v === "" || typeof v === "boolean") return null;
      const x = Number(v);
      return isNaN(x) ? null : x;
    }
    return v;
  }
  const PT_ALIASES = { multi_family: "multifamily", apartment: "multifamily", residential: "multifamily",
    residential_rental: "multifamily", single_family_home: "single_family", sfr: "single_family",
    condominium: "condo", townhouse: "condo", townhome: "condo", mobilehome: "mobile_home" };
  const normPt = (pt) => { const s = String(pt).toLowerCase().replace(/-/g, "_").replace(/ /g, "_"); return PT_ALIASES[s] || s; };
  function ownerValue(f, op, rawV, facts) {
    const v = facts[f];
    if (f === "other_fact" || v === null || v === undefined) return U;
    if (f === "owner_occupied") {
      const want = typeof rawV === "boolean" ? rawV : ["true", "yes", "1"].includes(String(rawV).toLowerCase());
      if (op === "==") return !!v === want;
      if (op === "!=") return !!v !== want;
      return U;
    }
    if (f === "owner_type") {
      const have = String(v).toLowerCase();
      if (op === "in" && Array.isArray(rawV)) return rawV.map((x) => String(x).toLowerCase()).includes(have);
      if (op === "==") return have === String(rawV).toLowerCase();
      if (op === "!=") return have !== String(rawV).toLowerCase();
      return U;
    }
    const n = Number(v), target = Number(rawV);
    if (isNaN(n) || isNaN(target) || rawV === null || rawV === "" || typeof rawV === "boolean") return U;
    return cmpInterval(n, n, op, target);
  }
  function propertyTypeValue(pt, facts) {
    if (facts.property_type === null) return U;   // building type unknown (typed-in address)
    const declared = facts.property_type;
    if (declared !== undefined && normPt(declared) !== "multifamily") return normPt(pt) === normPt(declared) ? T : F;
    pt = String(pt).toLowerCase().replace(/-/g, "_").replace(/ /g, "_");
    const lo = facts.units_min == null ? 2 : facts.units_min;
    const hi = facts.units_max == null ? INF : facts.units_max;
    if (["multifamily", "multi_family", "apartment", "residential", "residential_rental"].includes(pt)) return T;
    if (["single_family", "single_family_home", "sfr"].includes(pt)) return lo >= 2 ? F : U;
    if (pt === "duplex") return (lo === hi && hi === 2) ? T : ((lo > 2 || hi < 2) ? F : U);
    if (pt === "triplex") return (lo === hi && hi === 3) ? T : ((lo > 3 || hi < 3) ? F : U);
    if (["condo", "condominium", "townhouse", "townhome", "mobile_home", "mobilehome"].includes(pt)) return F;
    return U;
  }
  function leaf(p, facts, asOf, trace) {
    const f = p.field, op = p.op, rawV = p.value;
    let res;
    if (OWNER_FIELDS.has(f)) res = ownerValue(f, op, rawV, facts);
    else if (f === "property_type") {
      if (op === "in" && Array.isArray(rawV)) {
        const vals = rawV.map((x) => propertyTypeValue(x, facts));
        res = vals.includes(T) ? T : (vals.every((x) => x === F) ? F : U);
      } else {
        const r = propertyTypeValue(rawV, facts);
        res = op === "==" ? r : (op === "!=" ? (r === U ? U : !r) : U);
      }
    } else {
      const iv = interval(f, facts);
      const v = resolveValue(rawV, f, op, asOf);
      if (op === "in" && Array.isArray(rawV) && iv !== null) {
        if (f === "certificate_of_occupancy") res = U;
        else {
          const [lo, hi] = iv;
          const vals = rawV.map((x) => resolveValue(x, f, "==", asOf));
          const hits = vals.filter((x) => x !== null && lo <= x && x <= hi);
          res = (lo === hi && hits.length) ? T : ((!hits.length && vals.every((x) => x !== null)) ? F : U);
        }
      } else if (iv === null || v === null || v === undefined) res = U;
      else res = cmpInterval(iv[0], iv[1], op, v);
    }
    trace.push({ field: f, op, value: rawV, resolved: OWNER_FIELDS.has(f) ? null : resolveValue(rawV, f, op, asOf), result: res });
    return res;
  }
  function evaluate(p, facts, asOf, trace) {
    trace = trace || [];
    if (p === null || p === undefined || (typeof p === "object" && !Array.isArray(p) && !Object.keys(p).length)) return T;
    if ("all" in p || "any" in p) {
      const start = trace.length;
      let res;
      if ("all" in p) {
        const vals = p.all.map((q) => evaluate(q, facts, asOf, trace));
        res = vals.includes(F) ? F : (vals.every((x) => x === T) ? T : U);
      } else {
        const vals = p.any.map((q) => evaluate(q, facts, asOf, trace));
        res = vals.includes(T) ? T : (vals.every((x) => x === F) ? F : U);
      }
      if (res !== U) for (let i = start; i < trace.length; i++) if (trace[i].result === U) trace[i].irrelevant = true;
      return res;
    }
    if ("not" in p) { const v = evaluate(p.not, facts, asOf, trace); return v === U ? U : !v; }
    return leaf(p, facts, asOf, trace);
  }
  function missingFields(trace) {
    const out = [];
    for (const l of trace) if (l.result === U && !l.irrelevant && !out.includes(l.field)) out.push(l.field);
    return out;
  }
  function unitsText(facts) {
    const lo = facts.units_min, hi = facts.units_max;
    if (lo != null && lo === hi) return `${lo} unit${lo === 1 ? "" : "s"}`;
    if (hi == null) return `${lo}+ units`;
    return `${lo}-${hi} units`;
  }
  const DATE_OPS = { "<=": "on or before", "<": "before", ">": "after", ">=": "on or after", "==": "on", "!=": "not on", in: "one of" };
  const YEAR_OPS = { "<=": "in or before", "<": "before", ">": "after", ">=": "in or after", "==": "in", "!=": "not in" };
  const NUM_OPS = { "<=": "at most", "<": "fewer than", ">": "more than", ">=": "at least", "==": "exactly", "!=": "not", in: "one of" };
  const CAT_OPS = { "==": "is", "!=": "is not", in: "is one of" };
  function opWords(field, op) {
    const m = field === "certificate_of_occupancy" ? DATE_OPS : field === "year_built" ? YEAR_OPS
      : ["units", "owner_property_count", "owner_unit_count"].includes(field) ? NUM_OPS : CAT_OPS;
    return m[op] || op;
  }
  function describeLeaf(l, facts) {
    if (l.field === "other_fact") return `${l.value}? unknown (not in the data)`;
    const label = FIELD_LABEL[l.field] || l.field;
    let val = l.value;
    if (val && typeof val === "object" && !Array.isArray(val) && "as_of_minus_years" in val)
      val = `${l.resolved} (${val.as_of_minus_years} years before the query date)`;
    else if (Array.isArray(val)) val = val.map((x) => String(x).replace(/_/g, " ")).join(", ");
    else if (typeof val === "boolean") val = val ? "yes" : "no";
    else if (typeof val === "string") val = val.replace(/_/g, " ");
    let have;
    if (l.field === "certificate_of_occupancy" || l.field === "year_built")
      have = facts.year_built ? `built ${facts.year_built}` : "year built not in the data";
    else if (l.field === "units") have = unitsText(facts);
    else if (l.field === "property_type") {
      const pt = facts.property_type === undefined ? "multifamily" : facts.property_type;
      have = pt === null ? "building type not given" : (pt === "multifamily" ? "apartment building" : String(pt).replace(/_/g, " "));
    }
    else have = "not in the data";
    const verdict = l.result === T ? "yes" : l.result === F ? "no" : "unknown";
    return `${label} ${opWords(l.field, l.op)} ${val}? ${verdict} (${have})`;
  }
  function factsText(trace, facts) {
    const seen = new Set(), parts = [];
    for (const l of trace) if (l.result === U && !l.irrelevant) {
      const d = describeLeaf(l, facts);
      if (!seen.has(d)) { seen.add(d); parts.push(d); }
    }
    return parts.join("; ") + ".";
  }
  const dt = (s) => {
    if (!s) return null;
    const n = String(s).split("-").map(Number);
    if (n.length === 1) return iso(n[0], 1, 1);
    if (n.length === 2) return iso(n[0], n[1], 1);
    return iso(n[0], n[1], n[2]);
  };

  class Engine {
    constructor(rules, states) {
      this.rules = rules;
      this.states = states || { CA: "California", NJ: "New Jersey", MA: "Massachusetts" };
      this.byId = Object.fromEntries(rules.map((r) => [r.team_rule_id, r]));
      this.mods = {};
      for (const r of rules) {
        if (r.level === "state" && r.subject === "municipality" && r.coverage_logic && r.coverage_logic.covers) {
          const k = r.jurisdiction + "|" + r.category;
          (this.mods[k] = this.mods[k] || []).push(r);
        }
      }
      this.order = ["rent_increase_limits", "just_cause_eviction", "security_deposits",
        "application_screening_fees", "screening_restrictions", "algorithmic_rent_setting"];
    }
    evalRule(rule, addr, asOf, memo) {
      const key = rule.team_rule_id;
      if (key in memo) return memo[key];
      memo[key] = null;
      const res = this._eval(rule, addr, asOf, memo);
      memo[key] = res;
      return res;
    }
    _eval(rule, addr, asOf, memo) {
      const facts = addr.facts;
      if (!addr.stack.includes(rule.jurisdiction)) return null;
      const only = rule.applies_only_in || [];
      if (only.length && !only.some((c) => addr.stack.includes(c))) return null;
      const status = rule.status;
      if (status === "failed" || rule.subject === "municipality") return null;
      const end = dt(rule.end_date);
      if (end && end <= asOf) return null;
      const cl = rule.coverage_logic || {};
      const tCov = [], tEx = [];
      const cov = evaluate(cl.covers, facts, asOf, tCov);
      if (cov === F) return null;
      const hasEx = cl.exempt && typeof cl.exempt === "object" && Object.keys(cl.exempt).length;
      const ex = hasEx ? evaluate(cl.exempt, facts, asOf, tEx) : F;
      if (ex === T) return null;
      if (status === "pending") return { result: "pending", reason: "Bill or proposal, not law.", missing: [] };
      const eff = rule.amendment ? dt(rule.in_force_since) : dt(rule.effective_date);
      if ((eff && eff > asOf) || (status === "not_yet_effective" && !eff && !rule.amendment))
        return { result: "not_yet_effective", reason: `Enacted; takes effect ${rule.effective_date || "on a future date"}.`, missing: [] };
      if (rule.level === "city") {
        const st = rule.jurisdiction.split(", ")[1];
        for (const m of this.mods[st + "|" + rule.category] || []) {
          const meff = dt(m.effective_date);
          if (m.status === "pending" || m.status === "failed" || (meff && meff > asOf) || (m.status === "not_yet_effective" && !meff)) continue;
          const tm = [];
          const mv = evaluate(m.coverage_logic.covers, facts, asOf, tm);
          if (mv === T) return null;
          if (mv === U) return { result: "unknown", missing: missingFields(tm), reason: `State law ${m.citation} exempts some buildings from local rules of this kind; depends on: ` + factsText(tm, facts) };
        }
      }
      const yieldedUnknown = [];
      for (const yid of rule.yields_to || []) {
        const y = this.byId[yid];
        if (!y) continue;
        const yr = this.evalRule(y, addr, asOf, memo);
        if (yr && yr.result === "applies")
          return { result: "superseded", missing: [], superseded_by: yid, reason: `The local rule ${yid} (${y.citation}) governs at this address, so this state rule is superseded.` };
        if (yr && yr.result === "unknown") yieldedUnknown.push([yid, yr]);
      }
      if (cov === U) return { result: "unknown", missing: missingFields(tCov), reason: "Coverage depends on facts not in the data: " + factsText(tCov, facts), trace: tCov };
      if (ex === U) return { result: "unknown", missing: missingFields(tEx), reason: "An exemption may apply; it depends on facts not in the data: " + factsText(tEx, facts), trace: tEx };
      if (yieldedUnknown.length) {
        const [yid, yr] = yieldedUnknown[0];
        return { result: "unknown", missing: yr.missing, reason: `Applies unless the local rule ${yid} covers this building, which depends on facts not in the data (` + yr.missing.map((m) => FIELD_LABEL[m] || m).join(", ") + ")." };
      }
      return { result: "applies", missing: [], reason: this._appliesText(rule, tCov, tEx, facts), trace: tCov.concat(tEx) };
    }
    _appliesText(rule, tCov, tEx, facts) {
      const bits = [];
      if (rule.level === "state") bits.push(`Statewide ${this.states[rule.jurisdiction]} rule.`);
      else bits.push(`${rule.jurisdiction} city rule; the address is inside city limits.`);
      const covTrue = tCov.filter((l) => l.result === T).map((l) => describeLeaf(l, facts));
      if (covTrue.length) bits.push("Covered: " + covTrue.join("; ") + ".");
      const exFalse = tEx.filter((l) => l.result === F).map((l) => describeLeaf(l, facts));
      if (exFalse.length) bits.push("Exemption cannot apply: " + exFalse.join("; ") + ".");
      return bits.join(" ");
    }
    lookup(addr, asOf) {
      const memo = {}, out = [];
      for (const r of this.rules) {
        const res = this.evalRule(r, addr, asOf, memo);
        if (res) out.push(Object.assign({ rule: r }, res));
      }
      const present = new Set(out.map((e) => e.rule.team_rule_id));
      const entries = out.map((e) => {
        const r = e.rule;
        const partners = (r.conflicts_with || []).filter((c) => present.has(c));
        const conflict = !!r.source_conflict || partners.length > 0;
        let expl = e.reason;
        const ce = dt(r.effective_date);
        if (r.amendment && ce && ce > asOf && ["applies", "superseded", "unknown"].includes(e.result))
          expl += ` The version quoted takes effect ${r.effective_date}; an earlier version applies before then.`;
        const official = !!r.official_source || String(r.source_type || "").startsWith("official") || String(r.source_type || "").startsWith("user-supplied");
        if (!official) expl += " Source: a secondary summary (law-firm or news page); the enacting text is not in the corpus.";
        if (partners.length) expl += ` Possible conflict with ${partners.join(", ")}: flagged for human review.`;
        else if (r.source_conflict) expl += " Sources disagree about this rule: flagged for human review.";
        return { team_rule_id: r.team_rule_id, result: e.result, explanation: expl.trim(), conflict_flag: conflict,
          missing_facts: e.missing || [], category: r.category, superseded_by: e.superseded_by || null,
          event_only: r.scope === "event", rule: r };
      });
      entries.sort((a, b) => (this.order.indexOf(a.category) - this.order.indexOf(b.category)) ||
        (a.team_rule_id < b.team_rule_id ? -1 : a.team_rule_id > b.team_rule_id ? 1 : 0));
      return entries;
    }
  }
  const api = { Engine, evaluate, describeLeaf, FIELD_LABEL, unitsText };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Lexmap = api;
})(typeof window !== "undefined" ? window : globalThis);
