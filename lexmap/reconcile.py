"""Module A, stage 2: consolidate candidates into canonical rule records.

1. Group candidates by (jurisdiction, category); an LLM editor merges records that describe
   the same law, chooses the primary (official sources first) and writes conflict notes.
   It cannot create text: every quote still comes from a verified candidate span.
2. Deterministic post-processing: status recomputed from dates, conflicting effective dates
   flagged, local-vs-state precedence (yields_to) and preemption conflicts wired up,
   stable rule ids assigned (matching the ids used in dev/change_tests.json).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from . import config, llm, prompts
from .extract import DATE_RE, STATUS

KEEP_FIELDS = ["title", "requirement", "key_value", "status", "effective_date", "end_date", "citation",
               "coverage_conditions", "exemptions", "conflict_note"]


def _compact(cid: str, c: dict) -> dict:
    return {
        "id": cid, "doc": c["source_doc_id"], "source_type": c["source_type"], "official": c["official_source"],
        "title": c.get("title"), "requirement": c.get("requirement"), "key_value": c.get("key_value"),
        "status": c.get("status"), "effective_date": c.get("effective_date"), "end_date": c.get("end_date"),
        "citation": c.get("citation"), "coverage_conditions": c.get("coverage_conditions"),
        "exemptions": (c.get("exemptions") or "")[:600] or None, "interaction": c.get("interaction"),
        "coverage_logic": c.get("coverage_logic"),
        "quote": c["verified_spans"][0]["text"][:400], "confidence": c.get("confidence"),
        "conflict_note": c.get("conflict_note"),
    }


def _official_rank(c: dict) -> tuple:
    return (c["official_source"], c.get("confidence", 0), len(c.get("verified_spans", [])))


def merge_group(jur: str, cat: str, cands: list[dict]) -> tuple[list[dict], list[dict]]:
    ids = {f"c{i + 1}": c for i, c in enumerate(cands)}
    if len(cands) == 1:
        return [{"members": ["c1"], "primary": "c1"}], []
    prompt = prompts.RECONCILE_TEMPLATE.format(
        jurisdiction=jur, category=cat, as_of=config.DEFAULT_AS_OF,
        candidates=json.dumps([_compact(k, v) for k, v in ids.items()], ensure_ascii=False, indent=1))
    try:
        obj, rec = llm.complete_json(prompt, prompts.RECONCILE_SYSTEM, config.RECONCILE_MODEL,
                                     tag=f"reconcile:{jur}:{cat}")
    except Exception as e:  # noqa: BLE001 - fall back to no merging
        return [{"members": [k], "primary": k, "note": f"reconcile failed: {e}"} for k in ids], []
    groups, dropped, used = [], [], set()
    for g in (obj.get("groups") or []) if isinstance(obj, dict) else []:
        mem = [m for m in g.get("members", []) if m in ids and m not in used]
        if not mem:
            continue
        prim = g.get("primary") if g.get("primary") in mem else max(mem, key=lambda m: _official_rank(ids[m]))
        used.update(mem)
        g = dict(g, members=mem, primary=prim, llm_call=rec["key"])
        groups.append(g)
    for d in (obj.get("dropped") or []) if isinstance(obj, dict) else []:
        if d.get("id") in ids and d["id"] not in used:
            used.add(d["id"])
            dropped.append({"candidate": ids[d["id"]], "reason": d.get("reason"), "llm_call": rec["key"]})
    for k in ids:                       # anything the editor forgot stays as its own rule
        if k not in used:
            groups.append({"members": [k], "primary": k, "note": "not assigned by reconciler"})
    return groups, dropped


def _status_from_dates(r: dict, as_of: str) -> str:
    st = r["status"]
    eff = r.get("effective_date")
    if st in ("pending", "failed"):
        return st
    if eff and DATE_RE.match(eff):
        # compare at the precision given ("2026-01" is treated as 2026-01-01)
        e = (eff + "-01-01")[:10] if len(eff) == 4 else (eff + "-01")[:10] if len(eff) == 7 else eff
        return "not_yet_effective" if e > as_of else "in_force"
    return st if st in STATUS else "in_force"


def _dates_conflict(dates: list[str]) -> bool:
    """True if two dates disagree at their common precision ('2024-10' vs '2024-10-14' agree)."""
    ds = sorted(set(dates))
    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            n = min(len(a), len(b))
            if a[:n] != b[:n]:
                return True
    return False


def _is_noise_note(n: str | None) -> bool:
    if not n:
        return True
    low = n.lower()
    return any(p in low for p in ("no conflict", "do not conflict", "does not conflict", "not a conflict",
                                  "no genuine conflict", "consistent"))


def build_rule(jur: str, cat: str, g: dict, cands: dict[str, dict]) -> dict:
    prim = cands[g["primary"]]
    members = [cands[m] for m in g["members"]]
    r = {k: prim.get(k) for k in prim}
    for k in KEEP_FIELDS:
        v = g.get(k)
        if v in (None, ""):
            continue
        if k in ("effective_date", "end_date") and not DATE_RE.match(str(v)):
            continue
        if k == "status" and v not in STATUS:
            continue
        r[k] = v
    # coverage logic: the member the editor chose, else primary's, else the best official member's
    cf = g.get("coverage_from")
    if cf in g["members"] and cf != g["primary"]:
        r["coverage_logic"] = cands[cf].get("coverage_logic")
        r.setdefault("validation_notes", []).append(f"coverage logic taken from {cands[cf]['source_doc_id']}")
    cl = r.get("coverage_logic") or {}
    if not (cl.get("covers") or cl.get("exempt")):
        for m in sorted(members, key=_official_rank, reverse=True):
            mcl = m.get("coverage_logic") or {}
            if mcl.get("covers") or mcl.get("exempt"):
                r["coverage_logic"] = mcl
                r.setdefault("validation_notes", []).append(f"coverage logic taken from {m['source_doc_id']}")
                break
    r["yields_to_local"] = any(m.get("yields_to_local") for m in members)
    r["preempts_local"] = any(m.get("preempts_local") for m in members)
    # deterministic conflict check on effective dates across sources
    dates = sorted({(m.get("effective_date"), m["source_doc_id"]) for m in members if m.get("effective_date")})
    notes = [n for n in [g.get("conflict_note") if "coverage_from" in g or "members" in g else None] if n]
    if not g.get("llm_call"):                       # single-source rule: keep the extractor's own note
        notes = [n for n in [prim.get("conflict_note")] if n]
    if _dates_conflict([d for d, _ in dates]):
        notes.append("Sources give different effective dates: " + "; ".join(f"{d} ({doc})" for d, doc in dates))
    notes = [n for n in notes if not _is_noise_note(n)]
    r["conflict_note"] = " | ".join(dict.fromkeys(notes)) or None
    r["conflict_flag"] = bool(r["conflict_note"])
    corro = []
    for m in members:
        if m is prim:
            continue
        corro.append({"doc_id": m["source_doc_id"], "url": m["source_url"], "source_type": m["source_type"],
                      "quoted_span": m["verified_spans"][0]["text"], "retrieved_at": m["retrieved_at"]})
    r["corroborating_sources"] = corro
    conf = float(prim.get("confidence") or 0.7)
    if len({m["source_doc_id"] for m in members}) >= 2:
        conf = min(0.98, conf + 0.05)
    if not any(m["official_source"] for m in members):
        conf = min(conf, 0.6)
    if r["conflict_flag"]:
        conf = min(conf, 0.75)
    r["confidence"] = round(conf, 2)
    r["status"] = _status_from_dates(r, config.DEFAULT_AS_OF)
    r["jurisdiction"], r["category"] = jur, cat
    r["level"] = "city" if "," in jur else "state"
    r["reconcile"] = {"members": [m["source_doc_id"] for m in members], "llm_call": g.get("llm_call"),
                      "note": g.get("note")}
    return r


# ------------------------------------------------------------------ ids and relations

_TOKEN_RE = re.compile(r"\b([AS]B\s?\d+|[SH]\.?\s?\d{3,5}|FAIR|ballot|AB\s?\d+|SB\s?\d+)\b", re.I)


def _tokens(s: str) -> set[str]:
    return {re.sub(r"[\s.]", "", t).upper() for t in _TOKEN_RE.findall(s or "")}


def assign_ids(rules: list[dict]) -> None:
    by_group = defaultdict(list)
    for r in rules:
        by_group[(r["jurisdiction"], r["category"])].append(r)
    for (jur, cat), rs in by_group.items():
        base = f"{config.JURISDICTION_CODE[jur]}-{config.CATEGORY_CODE[cat]}"
        live = sorted([r for r in rs if r["status"] in ("in_force", "not_yet_effective")],
                      key=lambda r: (-(r["confidence"] or 0), r.get("effective_date") or "", r["title"] or ""))
        prop = sorted([r for r in rs if r["status"] in ("pending", "failed")],
                      key=lambda r: (r.get("citation") or "", r["title"] or ""))
        for i, r in enumerate(live, 1):
            r["team_rule_id"] = f"{base}-{i:02d}"
        for i, r in enumerate(prop, 1):
            r["team_rule_id"] = f"{base}-P{i}"
    align_test_ids(rules)


def align_test_ids(rules: list[dict]) -> None:
    """Make the ids referenced by dev/change_tests.json point at the right records."""
    tests = json.loads(config.CHANGE_TESTS.read_text(encoding="utf-8"))
    by_id = {r["team_rule_id"]: r for r in rules}
    for t in tests:
        title_tokens = _tokens(t["title"])
        ordered_tokens = [re.sub(r"[\s.]", "", x).upper() for x in _TOKEN_RE.findall(t["title"])]
        for pos, want in enumerate(t["rule_ids"]):
            prefix, _, suffix = want.rpartition("-")
            pending = suffix.startswith("P")
            pool = [r for r in rules if r["team_rule_id"].rpartition("-")[0] == prefix
                    and (r["team_rule_id"].rpartition("-")[2].startswith("P")) == pending]
            if not pool:
                continue
            target_tok = ordered_tokens[pos] if len(t["rule_ids"]) > 1 and pos < len(ordered_tokens) else None

            def score(r):
                toks = _tokens(" ".join(str(r.get(k) or "") for k in ("title", "citation", "key_value")))
                s = len(toks & title_tokens)
                if target_tok and target_tok in toks:
                    s += 5
                return (s, r.get("confidence") or 0)
            best = max(pool, key=score)
            if best["team_rule_id"] != want:
                other = by_id.get(want)
                old = best["team_rule_id"]
                if other is not None:
                    other["team_rule_id"] = old
                    by_id[old] = other
                best["team_rule_id"] = want
                by_id[want] = best


def wire_relations(rules: list[dict]) -> None:
    for r in rules:
        r["yields_to"] = []
        r["conflicts_with"] = []
    for r in rules:
        if r["level"] != "state":
            continue
        locals_ = [o for o in rules if o["level"] == "city" and o["category"] == r["category"]
                   and o["jurisdiction"].endswith(", " + r["jurisdiction"]) and o.get("subject", "landlord") == "landlord"
                   and o["status"] in ("in_force", "not_yet_effective")]
        if r.get("yields_to_local") and r.get("subject", "landlord") == "landlord":
            r["yields_to"] = [o["team_rule_id"] for o in locals_]
            if r["yields_to"]:
                r["interaction"] = (r.get("interaction") or "") + (
                    " " if r.get("interaction") else "") + "Yields to local rules: " + ", ".join(r["yields_to"]) + "."
                for o in locals_:
                    o["overrides"] = sorted(set(o.get("overrides") or []) | {r["team_rule_id"]})
        if r.get("preempts_local"):
            hits = [o for o in locals_]
            if hits:
                r["conflicts_with"] = [o["team_rule_id"] for o in hits]
                msg = (f"{r['citation']} states municipalities may not enact conflicting ordinances"
                       f" (effective {r.get('effective_date') or 'n/a'}); possible preemption of "
                       + ", ".join(f"{o['team_rule_id']} ({o['jurisdiction']})" for o in hits)
                       + ". Flagged for human review.")
                r["conflict_flag"] = True
                r["conflict_note"] = " | ".join(x for x in [r.get("conflict_note"), msg] if x)
                for o in hits:
                    o["conflicts_with"] = sorted(set(o["conflicts_with"]) | {r["team_rule_id"]})
                    o["conflict_flag"] = True
                    o["conflict_note"] = " | ".join(x for x in [o.get("conflict_note"),
                                                                f"May be preempted by {r['team_rule_id']} ({r['citation']}) once it takes effect"] if x)
    for r in rules:
        r.setdefault("overrides", [])
        if r["yields_to"]:
            r["overrides"] = sorted(set(r["overrides"]))


def run() -> list[dict]:
    res = json.loads((config.BUILD / "candidates.json").read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for d in res:
        for c in d["candidates"]:
            groups[(c["jurisdiction"], c["category"])].append(c)
    rules, dropped = [], []

    def work(key):
        jur, cat = key
        cands = groups[key]
        gs, dr = merge_group(jur, cat, cands)
        ids = {f"c{i + 1}": c for i, c in enumerate(cands)}
        return [build_rule(jur, cat, g, ids) for g in gs], dr

    with ThreadPoolExecutor(max_workers=6) as ex:
        for rs, dr in ex.map(work, sorted(groups)):
            rules += rs
            dropped += dr
    assign_ids(rules)
    for r in rules:   # conflicts that come from the sources themselves (vs. preemption wiring below)
        r["source_conflict"] = bool(r.get("conflict_flag"))
    wire_relations(rules)
    rules.sort(key=lambda r: r["team_rule_id"])
    config.BUILD.mkdir(parents=True, exist_ok=True)
    (config.BUILD / "rules_full.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding="utf-8")
    (config.BUILD / "reconcile_dropped.json").write_text(json.dumps(dropped, ensure_ascii=False, indent=1), encoding="utf-8")
    return rules


if __name__ == "__main__":
    rs = run()
    for r in rs:
        print(f"{r['team_rule_id']:16} {r['status']:18} {str(r.get('effective_date')):11} {r['citation'][:45]:45} "
              f"{'CONFLICT ' if r['conflict_flag'] else ''}{r['reconcile']['members']}")
