"""Lexmap end-to-end pipeline.

    python run.py                 # reproduce everything from cached model calls (no API key needed)
    python run.py --live          # re-run extraction/reconciliation with the LLM, ignoring the cache
    python run.py --as-of 2027-07-02 --address A0002   # one lookup, printed
    python run.py whatif path/to/new_ordinance.txt --jurisdiction "Cambridge, MA"

Stages: fetch secondary pages -> extract (Module A) -> reconcile -> geocode -> lookups (Module B)
        -> change tests (Module C) -> plain-language EN/ES -> self-check -> static site data.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from lexmap import config, llm  # noqa: E402

SCHEMA_FIELDS = ["team_rule_id", "jurisdiction", "level", "category", "status", "title", "requirement", "key_value",
                 "coverage_conditions", "exemptions", "overrides", "interaction", "effective_date", "citation",
                 "source_doc_id", "source_url", "quoted_span", "confidence", "conflict_flag", "conflict_note"]


def export_rules(rules: list[dict], explain: dict) -> dict:
    out = []
    for r in rules:
        rec = {k: r.get(k) for k in SCHEMA_FIELDS}
        rec["quoted_span"] = r["verified_spans"][0]["text"]
        rec["overrides"] = sorted(set(r.get("overrides") or []) | set(r.get("yields_to") or []))
        rec["conflict_flag"] = bool(r.get("conflict_flag"))
        if rec["effective_date"] in ("",):
            rec["effective_date"] = None
        rec.update({
            "penalty": r.get("penalty"),
            "end_date": r.get("end_date"),
            "retrieved_at": r.get("retrieved_at"),
            "source_type": r.get("source_type"),
            "coverage_logic": r.get("coverage_logic"),
            "subject": r.get("subject", "landlord"),
            "yields_to": r.get("yields_to") or [],
            "conflicts_with": r.get("conflicts_with") or [],
            "supporting_spans": [s["text"] for s in r["verified_spans"][1:]],
            "corroborating_sources": r.get("corroborating_sources") or [],
            "plain_language": explain.get(r["team_rule_id"]),
            "provenance": {"extraction_llm_call": r.get("llm_call"), "reconcile": r.get("reconcile"),
                           "validation_notes": r.get("validation_notes") or []},
        })
        out.append(rec)
    return {"rules": out}


def write_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def pipeline(args) -> int:
    from lexmap import audit, changes, explain, extract, fetch_links, geocode, lookup, reconcile, selfcheck, site
    t0 = time.time()
    use_cache = not args.live
    if args.fetch:
        print("[0] fetching organiser-listed secondary pages ...")
        fetch_links.fetch_all()
    if args.extract or args.live or not (config.BUILD / "candidates.json").exists():
        print("[A1] extracting rules from corpus ...")
        extract.run(workers=args.workers, use_cache=use_cache)
    print("[A2] reconciling candidates ...")
    rules = reconcile.run()
    print(f"     {len(rules)} rules")
    print("[B1] geocoding addresses ...")
    geos = geocode.geocode_all()
    write_json(config.BUILD / "geocodes.json", geos)
    addrs = lookup.address_records(geos)
    print("[B2] address lookups ...")
    eng = lookup.Engine(rules)
    d = date.fromisoformat(args.as_of)
    full = {a["address_id"]: eng.lookup(a, d) for a in addrs}
    print("[C ] change tests ...")
    ch, ch_report = changes.run(rules, addrs)
    print("[E ] plain-language summaries (EN/ES) ...")
    expl = explain.run(rules)
    print("[S ] writing submission ...")
    write_json(config.SUBMISSION / "rules.json", export_rules(rules, expl))
    write_json(config.SUBMISSION / "lookups.json", lookup.to_submission(full, args.as_of))
    write_json(config.SUBMISSION / "changes.json", {k: {kk: v[kk] for kk in ("affected_address_ids", "conflict_flag_address_ids", "notes")}
                                                    for k, v in ch.items()})
    write_json(config.BUILD / "changes_detailed.json", ch)
    audit.write(rules, full, args.as_of)
    print("[V ] self-check ...")
    report = selfcheck.run(write=True)
    print("[W ] site data ...")
    site.build(rules, expl, geos, addrs, ch, ch_report, report)
    print(f"done in {time.time() - t0:.0f}s; llm {llm.stats()}; self-check: "
          f"{report['summary']['passed']}/{report['summary']['total']} checks passed")
    return 0 if report["summary"]["failed"] == 0 else 1


def one_lookup(args) -> int:
    from lexmap import lookup
    rules = lookup.load_rules()
    eng = lookup.Engine(rules)
    addrs = {a["address_id"]: a for a in lookup.address_records()}
    a = addrs[args.address]
    print(f"{a['row']['street_address']}, {a['row']['postal_city']} -> {a['stack']} | facts: "
          f"year {a['facts']['year_built']}, {lookup.units_label(a['facts'])} | as of {args.as_of}")
    for e in eng.lookup(a, date.fromisoformat(args.as_of)):
        print(f"  {e['team_rule_id']:16} {e['result']:18} {'CONFLICT ' if e['conflict_flag'] else ''}{e['explanation']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="all", choices=["all", "whatif"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--live", action="store_true", help="ignore the LLM cache and call the model again")
    ap.add_argument("--extract", action="store_true", help="re-run extraction (cached calls are reused)")
    ap.add_argument("--fetch", action="store_true", help="fetch the secondary link-only pages")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--as-of", default=config.DEFAULT_AS_OF)
    ap.add_argument("--address")
    ap.add_argument("--jurisdiction")
    args = ap.parse_args()
    if args.command == "whatif":
        from lexmap import whatif
        return whatif.main(args)
    if args.address:
        return one_lookup(args)
    return pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
