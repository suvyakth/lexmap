"""What-if: run a NEW law through the same pipeline and report which addresses it changes.

    python run.py whatif data/whatif/fictional_cambridge_ordinance.txt --jurisdiction "Cambridge, MA"

This is how Lexmap handles a surprise ordinance (or a new jurisdiction): the text is read by
the same extraction prompt, every quote is verified against the new text, the new rule is
wired into the precedence/conflict graph, and every sample address is evaluated before and
after (at the later of the as-of date and the new rule's effective date).
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date
from pathlib import Path

from . import config, llm, prompts
from .corpus import Doc
from .extract import validate_candidate, verify_spans
from .lookup import Engine, address_records, load_rules
from .reconcile import _status_from_dates, wire_relations


def extract_new(path: Path, jurisdiction: str) -> tuple[Doc, list[dict], list[dict], dict]:
    text = path.read_text(encoding="utf-8")
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    doc = Doc(doc_id=f"NEW-{h}", jurisdictions=jurisdiction, url=f"file:{path.name}", source_type="user-supplied new law",
              retrieved_at="supplied", path=path, raw=text, body=text, official=True)
    prompt = prompts.EXTRACT_TEMPLATE.format(
        doc_id=doc.doc_id, url=doc.url, source_type=doc.source_type, jurisdiction=jurisdiction,
        retrieved=doc.retrieved_at, as_of=config.DEFAULT_AS_OF, chunk_note="", text=text)
    obj, rec = llm.complete_json(prompt, prompts.EXTRACT_SYSTEM, config.EXTRACT_MODEL, tag=f"whatif:{doc.doc_id}")
    good, bad = [], []
    for r in obj.get("rules", []) if isinstance(obj, dict) else []:
        cand, notes = validate_candidate(r, doc)
        if cand is None:
            bad.append({"record": r, "reasons": notes})
            continue
        notes += verify_spans(cand, doc)
        if not cand["verified_spans"]:
            bad.append({"record": cand, "reasons": notes + ["no verifiable quote"]})
            continue
        cand.update({"source_doc_id": doc.doc_id, "source_url": doc.url, "source_type": doc.source_type,
                     "retrieved_at": doc.retrieved_at, "official_source": True, "supplementary_source": False,
                     "llm_call": rec["key"], "validation_notes": notes, "corroborating_sources": []})
        good.append(cand)
    return doc, good, bad, rec


def main(args) -> int:
    path = Path(args.path)
    jur = args.jurisdiction
    if not path.exists() or not jur:
        print("usage: python run.py whatif <law.txt> --jurisdiction 'City, ST' [--as-of YYYY-MM-DD]")
        return 2
    doc, new, bad, rec = extract_new(path, jur)
    print(f"Extracted {len(new)} rule(s) from {path.name} (model call {rec['key'][:12]}..., cached={rec.get('cached')})")
    for b in bad:
        print("  rejected:", b["reasons"][-1])
    base = load_rules()
    combined = copy.deepcopy(base)
    for i, r in enumerate(new, 1):
        r["team_rule_id"] = f"NEW-{config.JURISDICTION_CODE.get(r['jurisdiction'], 'X')}-{config.CATEGORY_CODE[r['category']]}-{i:02d}"
        r["status"] = _status_from_dates(r, args.as_of)
        r["conflict_flag"] = bool(r.get("conflict_note"))
        r["source_conflict"] = r["conflict_flag"]
        r["level"] = "city" if "," in r["jurisdiction"] else "state"
        combined.append(r)
    wire_relations(combined)
    eval_dates = sorted({args.as_of} | {r["effective_date"] for r in new if r.get("effective_date") and r["effective_date"] > args.as_of})
    d_eval = date.fromisoformat((eval_dates[-1] + "-01-01")[:10] if len(eval_dates[-1]) == 4 else eval_dates[-1][:10] if len(eval_dates[-1]) >= 10 else eval_dates[-1] + "-01")
    before_eng, after_eng = Engine(base), Engine(combined)
    addrs = address_records()
    affected = {}
    new_ids = {r["team_rule_id"] for r in new}
    for a in addrs:
        b = {e["team_rule_id"]: e["result"] for e in before_eng.lookup(a, d_eval)}
        aft = after_eng.lookup(a, d_eval)
        af = {e["team_rule_id"]: e["result"] for e in aft}
        if b != af:
            affected[a["address_id"]] = {"city": a["geo"]["city"], "before": {k: v for k, v in b.items() if af.get(k) != v},
                                         "after": {k: v for k, v in af.items() if b.get(k) != v},
                                         "explanations": {e["team_rule_id"]: e["explanation"] for e in aft if e["team_rule_id"] in new_ids}}
    now = {}
    d_now = date.fromisoformat(args.as_of)
    for a in addrs:
        for e in after_eng.lookup(a, d_now):
            if e["team_rule_id"] in new_ids:
                now[e["team_rule_id"]] = now.get(e["team_rule_id"], {})
                now[e["team_rule_id"]][e["result"]] = now[e["team_rule_id"]].get(e["result"], 0) + 1
    report = {
        "document": str(path), "jurisdiction": jur, "as_of": args.as_of, "evaluated_at": d_eval.isoformat(),
        "new_rules": [{k: r.get(k) for k in ("team_rule_id", "jurisdiction", "category", "status", "title", "requirement",
                                              "key_value", "effective_date", "citation", "coverage_logic", "conflicts_with",
                                              "conflict_note")} | {"quoted_span": r["verified_spans"][0]["text"]} for r in new],
        "status_at_as_of": now,
        "affected_address_ids": sorted(affected),
        "affected_by_city": {c: sum(1 for v in affected.values() if v["city"] == c) for c in sorted({v["city"] for v in affected.values()})},
        "details": affected,
    }
    out = config.BUILD / "whatif" / (path.stem + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in report["new_rules"]:
        print(f"  {r['team_rule_id']} [{r['status']}] {r['title']} | effective {r['effective_date']} | {r['citation']}")
        print(f"     quote: {r['quoted_span'][:160]!r}")
        print(f"     coverage: {json.dumps(r['coverage_logic'])}")
        if r.get("conflicts_with"):
            print(f"     CONFLICT with {r['conflicts_with']}: {r.get('conflict_note')}")
    print(f"  status on {args.as_of}: {now}")
    print(f"  {len(affected)} sample addresses change once it is effective ({d_eval}): {report['affected_by_city']}")
    for aid in list(affected)[:5]:
        print(f"    {aid}: before {affected[aid]['before']} -> after {affected[aid]['after']}")
    print(f"  full report: {out}")
    print(f"  llm: {llm.stats()}")
    return 0
