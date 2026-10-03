"""Module A, stage 3: independent legal QA of every consolidated rule before publication.

A second model call reviews each record against excerpts of its own sources and the
sibling rules of the same jurisdiction, looking for the errors that matter most for
address-level answers: the direction of coverage cut-offs, landlord- vs municipality-level
rules, status/effective dates, and precedence flags.  It may only change a whitelisted set
of fields; every fix is re-validated, and every change is recorded in the rule's
provenance (qa.changes) and in the audit log.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from . import config, llm
from .corpus import load_docs
from .extract import DATE_RE, STATUS, _prune, _valid_pred, canonical_jurisdiction

QA_SYSTEM = ("You are a meticulous senior housing-law analyst doing quality control on machine-built rule records. "
             "You compare each record with its source text, fix only clear errors, and never add facts the sources "
             "do not support. Output only JSON.")

QA_TEMPLATE = """Review ONE rule record before it is used to answer "does this rule apply to this building?" for sample apartment buildings. As-of date: {as_of}.

Check, in this order:
1. status / effective_date / end_date are right as of {as_of} (in_force | not_yet_effective | pending | failed).
2. subject: "landlord" if the rule regulates landlords or tenancies; "municipality" if it only limits what cities may do or exempts buildings from LOCAL rules (e.g. a state ban on local rent control, or a state law exempting new construction from municipal rent control). For a municipality rule, coverage_logic.covers must describe the buildings the state law takes OUT of local regulation (null if it removes local regulation entirely).
3. coverage_logic encodes which buildings the requirement applies to. "covers" = buildings in scope, "exempt" = buildings excluded. Check the DIRECTION of every comparison against the text, e.g. "applies to units built on or before October 1, 1978" -> covers certificate_of_occupancy <= "1978-10-01"; "units first occupied after June 13, 1979 are exempt" -> exempt certificate_of_occupancy > "1979-06-13"; "exempt if certificate of occupancy issued within the last 15 years" -> exempt certificate_of_occupancy > {{"as_of_minus_years":15}}.
   Allowed fields: certificate_of_occupancy, year_built, units, property_type ("single_family"|"condo"|"duplex"|"multifamily"|"mobile_home"), owner_occupied, owner_type, owner_property_count, owner_unit_count, other_fact. Ops: <=, <, >=, >, ==, !=, in. Combinators: all, any, not.
   other_fact is only for a coverage condition that cannot be expressed with the other fields. If the condition is "unit is subject to <another local ordinance>" and that ordinance's coverage appears in SIBLING RULES below, copy that coverage instead of using other_fact.
   Exemptions that depend on facts outside the allowed fields (dormitories, deed-restricted affordable housing, government ownership, tenant traits, tenancy length) belong in the exemptions text, NOT in coverage_logic.
4. yields_to_local: true only if this rule does not apply where a local ordinance of the same kind applies. preempts_local: true only if it preempts / prohibits conflicting local ordinances.
5. requirement and key_value are accurate, current, and plain (1-2 sentences).
6. scope: "core" if the rule governs ordinary tenancies of a covered building; "event" if it only bites when a specific event happens to the building or tenancy (demolition or redevelopment, Ellis Act withdrawal, condominium/cooperative conversion, temporary displacement for repairs or capital improvements, sale/foreclosure). A just-cause list or a deposit cap is "core"; relocation payments that are owed only on demolition are "event".
7. applies_only_in: if the text limits a STATE statute to particular cities (e.g. a section that applies only in "a city and county", i.e. San Francisco), list those cities as "City, ST" (in-scope cities: Los Angeles, San Francisco, San Diego, Berkeley, Santa Ana, CA; Jersey City, Hoboken, Newark, NJ; Boston, Cambridge, MA); otherwise [].
8. jurisdiction: change it only if the record is a state-level bill or petition that concerns a single city (e.g. a home-rule petition for Boston) - then use that city ("Boston, MA").
9. citation: the most specific official citation for the operative requirement that the sources support (e.g. if a source says "(N.J.S.A. 46:8-21.2)" for the deposit cap, use "N.J.S.A. 46:8-21.2" rather than a range). Never invent a section number that is not in the record or the excerpts.
10. conflict: decide whether a REAL unresolved question remains - sources give different effective dates or figures that cannot both be right, or a law may preempt this one. Set conflict_unresolved true/false and a one-sentence conflict_note (null if none). A note that explains why two values are both right (e.g. operative date vs. amendment date) is resolved, not a conflict.

RULE RECORD:
{record}

SOURCE EXCERPTS (verbatim; the quoted spans are marked with >>> <<<):
{excerpts}

SIBLING RULES (same state / city; for reference only):
{siblings}

Return JSON (always include scope, applies_only_in, conflict_unresolved and conflict_note):
{{"ok": true|false, "issues": ["..."], "scope": "core"|"event", "applies_only_in": [], "conflict_unresolved": false, "conflict_note": null,
  "fix": {{only the fields to change, from: status, effective_date, end_date, subject, coverage_logic, yields_to_local, preempts_local, requirement, key_value, citation, jurisdiction}}}}"""

FIXABLE = {"status", "effective_date", "subject", "coverage_logic", "yields_to_local", "preempts_local",
           "requirement", "key_value", "citation", "jurisdiction"}


def _excerpts(r: dict, docs: dict, width: int = 1400, max_chars: int = 9000) -> str:
    out = []
    d = docs.get(r["source_doc_id"])
    if d:
        for s in r["verified_spans"][:3]:
            a, b = max(0, s["start"] - width), min(len(d.raw), s["end"] + width)
            out.append(f"[{d.doc_id} {d.source_type}] ..." + d.raw[a:s["start"]] + ">>>" + d.raw[s["start"]:s["end"]]
                       + "<<<" + d.raw[s["end"]:b] + "...")
    for c in r.get("corroborating_sources", [])[:3]:
        out.append(f"[{c['doc_id']} {c['source_type']}] >>>{c['quoted_span']}<<<")
    text = "\n\n".join(out)
    return text[:max_chars]


def _record(r: dict) -> dict:
    keys = ["jurisdiction", "level", "category", "status", "title", "requirement", "key_value", "coverage_conditions",
            "exemptions", "coverage_logic", "subject", "interaction", "yields_to_local", "preempts_local",
            "effective_date", "end_date", "citation", "conflict_note"]
    return {k: r.get(k) for k in keys}


def _siblings(r: dict, rules: list[dict]) -> str:
    st = r["jurisdiction"].split(", ")[-1]
    if r["level"] == "city":
        sib = [o for o in rules if o is not r and o["jurisdiction"] in (r["jurisdiction"], st)]
    else:
        sib = [o for o in rules if o is not r and (o["jurisdiction"] == st or
                                                   (o["jurisdiction"].endswith(", " + st) and o["category"] == r["category"]))]
    return json.dumps([{"jurisdiction": o["jurisdiction"], "category": o["category"], "title": o["title"],
                        "citation": o["citation"], "status": o["status"], "coverage_logic": o.get("coverage_logic")}
                       for o in sib][:25], ensure_ascii=False)


def review(r: dict, rules: list[dict], docs: dict) -> dict:
    sib_pool = [o for o in rules if not (o["jurisdiction"] == r["jurisdiction"] and o["category"] == r["category"]
                                         and o.get("title") == r.get("title") and o.get("citation") == r.get("citation"))]
    prompt = QA_TEMPLATE.format(as_of=config.DEFAULT_AS_OF, record=json.dumps(_record(r), ensure_ascii=False, indent=1),
                                excerpts=_excerpts(r, docs), siblings=_siblings(r, sib_pool))
    qa = {"llm_call": None, "ok": None, "issues": [], "changes": {}}
    try:
        obj, rec = llm.complete_json(prompt, QA_SYSTEM, config.RECONCILE_MODEL, tag=f"qa:{r['jurisdiction']}:{r['category']}")
    except Exception as e:  # noqa: BLE001
        qa["issues"].append(f"QA call failed: {e}")
        r["qa"] = qa
        return r
    qa["llm_call"] = rec["key"]
    if not isinstance(obj, dict):
        r["qa"] = qa
        return r
    qa["ok"] = bool(obj.get("ok"))
    qa["issues"] = [str(x) for x in obj.get("issues") or []]
    scope = obj.get("scope")
    r["scope"] = scope if scope in ("core", "event") else "core"
    only = [canonical_jurisdiction(c) for c in (obj.get("applies_only_in") or []) if isinstance(c, str)]
    st = r["jurisdiction"].split(", ")[-1]
    r["applies_only_in"] = sorted({c for c in only if c and "," in c and c.endswith(", " + st)}) if r["level"] == "state" else []
    if isinstance(obj.get("conflict_unresolved"), bool):
        qa["conflict_unresolved"] = obj["conflict_unresolved"]
        qa["conflict_note"] = obj.get("conflict_note") if isinstance(obj.get("conflict_note"), str) else None
    fix = obj.get("fix") or {}
    for k, v in fix.items() if isinstance(fix, dict) else []:
        if k not in FIXABLE:
            continue
        if k == "status" and v not in STATUS:
            continue
        if k in ("effective_date", "end_date") and v is not None and not DATE_RE.match(str(v)):
            continue
        if k == "subject" and v not in ("landlord", "municipality"):
            continue
        if k in ("yields_to_local", "preempts_local"):
            v = bool(v)
        if k == "jurisdiction":
            v = canonical_jurisdiction(v) if isinstance(v, str) else None
            st = r["jurisdiction"].split(", ")[-1]
            # only state -> one of its own cities (home-rule petitions); never across states
            if not v or r["level"] != "state" or "," not in v or not v.endswith(", " + st):
                continue
        if k == "citation" and (not isinstance(v, str) or len(v) < 4):
            continue
        if k == "coverage_logic":
            if not isinstance(v, dict):
                continue
            cl = {}
            for part in ("covers", "exempt"):
                p = v.get(part)
                cl[part] = p if not _valid_pred(p) else _prune(p)
            v = cl
        if r.get(k) != v:
            qa["changes"][k] = {"from": r.get(k), "to": v}
            r[k] = v
            if k == "jurisdiction":
                r["level"] = "city"
    r["qa"] = qa
    return r


def run(rules: list[dict], workers: int = 6) -> list[dict]:
    """Review every rule.  Sibling context comes from a frozen pre-QA snapshot so prompts (and
    therefore cached answers) are identical on every run regardless of thread timing."""
    import copy
    docs = load_docs()
    snapshot = copy.deepcopy(rules)
    pairs = list(zip(rules, snapshot))

    def one(pair):
        live, frozen = pair
        reviewed = review(copy.deepcopy(frozen), snapshot, docs)
        live.clear()
        live.update(reviewed)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, pairs))
    return rules
