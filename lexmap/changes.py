"""Module C: change tracking, driven generically by dev/change_tests.json.

Test types
  as_of     - evaluate the rule set at as_of_before and as_of_after; affected = addresses whose
              result for a listed rule changes.
  boundary  - affected = addresses where a listed rule applies at as_of (per-rule sets in notes).
  pending   - "if enacted": evaluate a copy of each bill as if in force on as_of; affected = addresses
              it would cover (applies/unknown/superseded).  Current result stays "pending".
  negative  - affected = addresses where a listed rule is reported at all (expected empty).
Conflict flags: addresses where a listed rule's entry carries conflict_flag (e.g. NJ FAIR Act vs.
the Jersey City and Hoboken ordinances).
"""
from __future__ import annotations

import copy
import json
from datetime import date

from . import config
from .lookup import Engine, address_records


def _entry(entries: list[dict], rid: str) -> dict | None:
    return next((e for e in entries if e["team_rule_id"] == rid), None)


def hour16_tests(rules: list[dict], start: int) -> list[dict]:
    """One extra test per organiser hour-16 document: which addresses change once its rules take effect."""
    from datetime import timedelta
    from .corpus import hour16_docs
    out = []
    for i, d in enumerate(hour16_docs()):
        ids = [r["team_rule_id"] for r in rules if r.get("source_doc_id") == d.doc_id]
        effs = [r.get("effective_date") for r in rules if r.get("source_doc_id") == d.doc_id and r.get("effective_date")]
        last = max(((e + "-01-01")[:10] if len(e) == 4 else (e + "-01")[:10] if len(e) == 7 else e) for e in effs) if effs else None
        after = (date.fromisoformat(last) + timedelta(days=1)).isoformat() if last and last >= config.DEFAULT_AS_OF else config.DEFAULT_AS_OF
        st = (d.jurisdictions.split(", ")[-1] if d.jurisdictions else "")
        out.append({"test_id": f"T{start + i}", "title": f"Hour-16 release {d.path.name} ({d.jurisdictions})",
                    "type": "as_of", "hour16": True, "rule_ids": ids, "as_of_before": config.DEFAULT_AS_OF, "as_of_after": after,
                    "states": [st] if st in config.STATES else [],
                    "expected_behavior": "Extract the new ordinance unaided, get its effective date right, and list the "
                                         "addresses whose answers change once it takes effect.",
                    "extracted_effective_dates": effs})
    return out


def run(rules: list[dict], addrs: list[dict] | None = None) -> tuple[dict, dict]:
    tests = json.loads(config.CHANGE_TESTS.read_text(encoding="utf-8"))
    if not any(t["test_id"] == "T6" for t in tests):
        tests += hour16_tests(rules, start=6)
    addrs = addrs if addrs is not None else address_records()
    eng = Engine(rules)
    by_id = eng.by_id
    out, report = {}, {}
    cache: dict[str, dict[str, list[dict]]] = {}

    def look(as_of: str) -> dict[str, list[dict]]:
        if as_of not in cache:
            d = date.fromisoformat(as_of)
            cache[as_of] = {a["address_id"]: eng.lookup(a, d) for a in addrs}
        return cache[as_of]

    for t in tests:
        tid, ids = t["test_id"], t["rule_ids"]
        missing = [i for i in ids if i not in by_id]
        states = set(t.get("states") or [])
        in_scope = [a for a in addrs if not states or a["row"]["state"] in states]
        affected, conflicts, details, notes = [], set(), {}, []
        if missing:
            notes.append(f"Rule ids not found in rules.json: {missing}")
        if t["type"] == "as_of":
            b = look(t["as_of_before"])
            if t.get("hour16"):
                # an organiser release is evaluated as enacted on its own effective date, even if its
                # adoption post-dates the default query date (status would otherwise stay "pending")
                h_rules = []
                for r in rules:
                    if r["team_rule_id"] in ids and r.get("status") == "pending":
                        r = dict(r, status="in_force")
                    h_rules.append(r)
                heng = Engine(h_rules)
                da = date.fromisoformat(t["as_of_after"])
                a_ = {ad["address_id"]: heng.lookup(ad, da) for ad in addrs}
            else:
                a_ = look(t["as_of_after"])
            for ad in in_scope:
                aid = ad["address_id"]
                before = {i: (_entry(b[aid], i) or {}).get("result", "not reported") for i in ids}
                after = {i: (_entry(a_[aid], i) or {}).get("result", "not reported") for i in ids}
                if before != after:
                    affected.append(aid)
                    details[aid] = {"before": before, "after": after}
                for snap in (b[aid], a_[aid]):
                    for i in ids:
                        e = _entry(snap, i)
                        if e and e["conflict_flag"] and t.get("conflict_with"):
                            if any(_entry(snap, c) for c in t["conflict_with"]):
                                conflicts.add(aid)
            notes.append(f"{len(affected)} of {len(in_scope)} {'/'.join(sorted(states)) or 'all'} addresses change between "
                         f"{t['as_of_before']} and {t['as_of_after']}.")
            if t.get("extracted_effective_dates") is not None:
                notes.append(f"Extracted rules {ids} with effective date(s) {t['extracted_effective_dates']}.")
        elif t["type"] == "boundary":
            snap = look(t["as_of"])
            per_rule = {i: [] for i in ids}
            for ad in addrs:
                aid = ad["address_id"]
                hit = False
                for i in ids:
                    e = _entry(snap[aid], i)
                    if e and e["result"] in ("applies", "unknown", "superseded"):
                        per_rule[i].append(aid)
                        hit = True
                if hit:
                    affected.append(aid)
                    details[aid] = {i: (_entry(snap[aid], i) or {}).get("result", "not reported") for i in ids}
            for i in ids:
                cities = sorted({next(a["geo"]["city"] for a in addrs if a["address_id"] == x) for x in per_rule[i]})
                notes.append(f"{i}: {len(per_rule[i])} addresses, all in {cities}.")
            nwk = [a["address_id"] for a in addrs if a["geo"]["city"] == "Newark, NJ" and a["address_id"] in affected]
            notes.append(f"Newark addresses affected: {len(nwk)}.")
        elif t["type"] == "pending":
            snap = look(t["as_of"])
            hypo_rules = []
            for r in rules:
                if r["team_rule_id"] in ids:
                    h = copy.deepcopy(r)
                    h["status"], h["effective_date"] = "in_force", t["as_of"]
                    hypo_rules.append(h)
                else:
                    hypo_rules.append(r)
            heng = Engine(hypo_rules)
            d = date.fromisoformat(t["as_of"])
            for ad in addrs:
                aid = ad["address_id"]
                cur = {i: (_entry(snap[aid], i) or {}).get("result", "not reported") for i in ids}
                hyp_entries = heng.lookup(ad, d)
                hyp = {i: (_entry(hyp_entries, i) or {}).get("result", "not reported") for i in ids}
                if any(v in ("applies", "unknown", "superseded") for v in hyp.values()):
                    affected.append(aid)
                    details[aid] = {"current": cur, "if_enacted": hyp}
            bad = [aid for aid in affected if any(v != "pending" for v in details[aid]["current"].values())]
            notes.append(f"Currently reported as pending (never in force) for every affected address: {not bad}. "
                         f"{len(affected)} addresses would be covered if enacted.")
        elif t["type"] == "negative":
            snap = look(t["as_of"])
            for ad in in_scope if states else addrs:
                aid = ad["address_id"]
                hits = [e for e in snap[aid] if e["team_rule_id"] in ids]
                if hits:
                    affected.append(aid)
                    details[aid] = {e["team_rule_id"]: e["result"] for e in hits}
            caps = [ad["address_id"] for ad in in_scope
                    if any(e["category"] == "rent_increase_limits" and e["result"] in ("applies", "unknown", "superseded")
                           for e in snap[ad["address_id"]])]
            st = [by_id[i]["status"] for i in ids if i in by_id]
            notes.append(f"Listed rule status: {st}. Addresses in {sorted(states)} with any rent cap reported: {len(caps)}.")
        out[tid] = {"affected_address_ids": sorted(affected), "conflict_flag_address_ids": sorted(conflicts),
                    "notes": " ".join(notes), "details": details}
        report[tid] = {"title": t["title"], "expected_behavior": t["expected_behavior"],
                       "affected": len(affected), "conflict_flags": len(conflicts), "notes": " ".join(notes)}
    return out, report
