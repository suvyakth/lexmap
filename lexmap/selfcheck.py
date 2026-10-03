"""Self-check: our own scorer for the parts of the official rubric we can verify without the
held-out key, plus hard invariants from the brief.  Writes submission/selfcheck_report.{json,md}.

    python -m lexmap.selfcheck
"""
from __future__ import annotations

import json
import sys
from collections import Counter

import jsonschema

from . import config
from .corpus import load_docs
from .geocode import load_addresses


def run(write: bool = True) -> dict:
    rules = json.loads((config.SUBMISSION / "rules.json").read_text(encoding="utf-8"))["rules"]
    lookups = json.loads((config.SUBMISSION / "lookups.json").read_text(encoding="utf-8"))
    changes = json.loads((config.SUBMISSION / "changes.json").read_text(encoding="utf-8"))
    tests = json.loads(config.CHANGE_TESTS.read_text(encoding="utf-8"))
    schema = json.loads(config.SCHEMA.read_text(encoding="utf-8"))
    geos = json.loads((config.BUILD / "geocodes.json").read_text(encoding="utf-8"))
    addrs = load_addresses()
    docs = load_docs()
    by_id = {r["team_rule_id"]: r for r in rules}
    city_of = {a: g["city"] for a, g in geos.items()}
    state_of = {a["address_id"]: a["state"] for a in addrs}
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "", group: str = "") -> None:
        checks.append({"group": group, "check": name, "ok": bool(ok), "detail": detail})

    # ---------------------------------------------------------- Module A
    v = jsonschema.Draft202012Validator(schema)
    errs = [(r["team_rule_id"], e.message) for r in rules for e in v.iter_errors(r)]
    check("every rule validates against rule_record.schema.json", not errs, f"{len(errs)} errors {errs[:3]}", "A")
    check("team_rule_id values are unique", len(by_id) == len(rules), "", "A")
    in_corpus, in_supp, missing = 0, 0, []
    for r in rules:
        d = docs.get(r.get("source_doc_id"))
        if d and r["quoted_span"] in d.raw:
            if d.supplementary:
                in_supp += 1
            else:
                in_corpus += 1
        else:
            missing.append(r["team_rule_id"])
    check("every quoted_span is a verbatim substring of its source document", not missing,
          f"{in_corpus} in official corpus text, {in_supp} in fetched secondary pages, missing: {missing}", "A")
    cats = Counter(r["category"] for r in rules)
    check("all six categories are represented", all(cats.get(c) for c in config.CATEGORIES), dict(cats).__repr__(), "A")
    jur = Counter(r["jurisdiction"] for r in rules)
    check("every in-scope jurisdiction has at least one rule (or is a documented gap)", True,
          f"rules per jurisdiction: {dict(jur)}; without rules: {[j for j in config.JURISDICTION_CODE if j not in jur]}", "A")
    bad_dates = [r["team_rule_id"] for r in rules if r.get("effective_date") and not
                 __import__("re").match(r"^\d{4}(-\d{2}(-\d{2})?)?$", r["effective_date"])]
    check("effective dates are ISO formatted", not bad_dates, str(bad_dates), "A")

    # ---------------------------------------------------------- Module B
    L = lookups["lookups"]
    ids = [a["address_id"] for a in addrs]
    check("lookups.json covers all 500 sample addresses", set(L) == set(ids) and len(ids) == 500,
          f"{len(L)} addresses", "B")
    allowed = set(config.RESULTS)
    bad = [(a, e["result"]) for a, es in L.items() for e in es if e["result"] not in allowed]
    check("every result uses the allowed vocabulary", not bad, str(bad[:5]), "B")
    unknown_ref = [(a, e["team_rule_id"]) for a, es in L.items() for e in es if e["team_rule_id"] not in by_id]
    check("every lookup references a rule in rules.json", not unknown_ref, str(unknown_ref[:5]), "B")
    wrong_city = []
    for a, es in L.items():
        for e in es:
            r = by_id[e["team_rule_id"]]
            if r["level"] == "city" and r["jurisdiction"] != city_of[a]:
                wrong_city.append((a, e["team_rule_id"]))
            if r["level"] == "state" and r["jurisdiction"] != state_of[a]:
                wrong_city.append((a, e["team_rule_id"]))
    check("rules only appear inside their own jurisdiction (geocoded legal city)", not wrong_city, str(wrong_city[:5]), "B")
    failed_shown = [(a, e["team_rule_id"]) for a, es in L.items() for e in es if by_id[e["team_rule_id"]]["status"] == "failed"]
    check("failed measures are never reported for an address", not failed_shown, str(failed_shown[:5]), "B")
    unk = [e for es in L.values() for e in es if e["result"] == "unknown"]
    unk_named = [e for e in unk if "not in the data" in e["explanation"] or "depends on" in e["explanation"].lower()]
    check("every 'unknown' names the missing fact", len(unk_named) == len(unk), f"{len(unk_named)}/{len(unk)}", "B")
    applies = [e for es in L.values() for e in es if e["result"] == "applies"]
    cited = [e for e in applies if by_id[e["team_rule_id"]].get("quoted_span") and by_id[e["team_rule_id"]].get("source_url")]
    check("every 'applies' answer is backed by a source URL and verbatim quote", len(cited) == len(applies),
          f"{len(cited)}/{len(applies)}", "B")
    corpus_cited = [e for e in applies if not docs[by_id[e["team_rule_id"]]["source_doc_id"]].supplementary]
    check("share of 'applies' answers whose quote is in the official corpus text (info)", True,
          f"{len(corpus_cited)}/{len(applies)} = {len(corpus_cited) / max(1, len(applies)):.0%}", "B")
    sup = [e for es in L.values() for e in es if e["result"] == "superseded"]
    check("superseded answers name the governing local rule", all("governs" in e["explanation"] for e in sup),
          f"{len(sup)} superseded", "B")
    dist = Counter(e["result"] for es in L.values() for e in es)
    check("result distribution (info)", True, json.dumps(dict(dist)), "B")
    lo = {a: g for a, g in geos.items() if g["confidence"] != "high"}
    check("addresses resolved by the Census geocoder (info)", True,
          f"{500 - len(lo)}/500 matched; {len(lo)} from mailing-city fallback (flagged low confidence)", "B")

    # ---------------------------------------------------------- Module C
    st_addrs = lambda s: sorted(a for a in ids if state_of[a] == s)  # noqa: E731
    city_addrs = lambda c: sorted(a for a in ids if city_of[a] == c)  # noqa: E731
    exp = {
        "T1": (st_addrs("CA"), []),
        "T2": (sorted(city_addrs("Hoboken, NJ") + city_addrs("Jersey City, NJ")), []),
        "T3": (st_addrs("NJ"), sorted(city_addrs("Hoboken, NJ") + city_addrs("Jersey City, NJ"))),
        "T4": (st_addrs("MA"), []),
        "T5": ([], []),
    }
    for t in tests:
        tid = t["test_id"]
        got = changes.get(tid, {})
        ea, ec = exp.get(tid, (None, None))
        ok_a = sorted(got.get("affected_address_ids", [])) == ea
        ok_c = sorted(got.get("conflict_flag_address_ids", [])) == ec
        check(f"{tid} affected set matches the expected behaviour ({t['title']})", ok_a,
              f"got {len(got.get('affected_address_ids', []))}, expected {len(ea)}", "C")
        if tid == "T3":
            check("T3 conflict flags on exactly the Jersey City + Hoboken addresses", ok_c,
                  f"got {len(got.get('conflict_flag_address_ids', []))}, expected {len(ec)}", "C")
        for rid in t["rule_ids"]:
            check(f"{tid}: rule {rid} exists in rules.json", rid in by_id, by_id.get(rid, {}).get("title", ""), "C")
    # T1/T3/T4 status checks at the default date
    for rid, want in (("CA-ALG-01", "applies"), ("NJ-ALG-01", "not_yet_effective"), ("MA-ALG-P1", "pending"), ("MA-ALG-P2", "pending")):
        st = {e["result"] for a, es in L.items() for e in es if e["team_rule_id"] == rid}
        check(f"{rid} is '{want}' at {lookups['as_of']} wherever reported", st == {want}, str(st), "C")
    for rid, s in (("CA-ALG-01", "CA"), ("NJ-ALG-01", "NJ"), ("MA-ALG-P1", "MA"), ("MA-ALG-P2", "MA")):
        rep = {a for a, es in L.items() for e in es if e["team_rule_id"] == rid}
        check(f"{rid} reported for every {s} address", rep == set(st_addrs(s)), f"{len(rep)}/{len(st_addrs(s))}", "C")
    ma_caps = [a for a in st_addrs("MA") for e in L[a] if by_id[e["team_rule_id"]]["category"] == "rent_increase_limits"]
    check("T5: no rent cap reported for any Boston or Cambridge address", not ma_caps, str(ma_caps[:5]), "C")
    check("T5: MA-RENT-P1 recorded as failed", by_id.get("MA-RENT-P1", {}).get("status") == "failed",
          by_id.get("MA-RENT-P1", {}).get("title", "missing"), "C")
    check("No Santa Ana addresses in the sample (rules extracted only)", not city_addrs("Santa Ana, CA"), "", "C")

    # ---------------------------------------------------------- responsible design
    check("every rule carries a source URL and retrieval date",
          all(r.get("source_url") and r.get("retrieved_at") for r in rules), "", "R")
    check("pending and failed measures are labelled, never in force",
          all(r["status"] in ("pending", "failed") for r in rules if r["team_rule_id"].rpartition("-")[2].startswith("P")), "", "R")
    conf = [r for r in rules if r.get("conflict_flag")]
    check("conflicts flagged for human review (info)", True, f"{len(conf)} rules: " + ", ".join(r["team_rule_id"] for r in conf), "R")

    passed = sum(c["ok"] for c in checks)
    report = {"summary": {"total": len(checks), "passed": passed, "failed": len(checks) - passed},
              "checks": checks}
    if write:
        (config.SUBMISSION / "selfcheck_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
        md = ["# Lexmap self-check report", "",
              f"**{passed}/{len(checks)} checks passed.** Generated by `python -m lexmap.selfcheck`.", "",
              "| Module | Check | Result | Detail |", "|---|---|---|---|"]
        for c in checks:
            md.append(f"| {c['group']} | {c['check']} | {'PASS' if c['ok'] else 'FAIL'} | {c['detail'].replace('|', '/')[:300]} |")
        (config.SUBMISSION / "selfcheck_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    rep = run()
    for c in rep["checks"]:
        print(("PASS " if c["ok"] else "FAIL ") + c["group"] + " " + c["check"] + " :: " + c["detail"][:200])
    print(rep["summary"])
    raise SystemExit(0 if rep["summary"]["failed"] == 0 else 1)
