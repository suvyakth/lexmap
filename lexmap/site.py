"""Write the static site's data files (docs/data/*.json).  The page itself (docs/index.html,
docs/app.js) re-implements the evaluator in JavaScript so any address and any as-of date can
be answered in the browser; tests/parity check that both engines agree on every answer."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone

from . import config
from .corpus import load_docs
from .lookup import Engine

PARITY_DATES = ["2025-12-31", "2026-01-02", "2026-10-01", "2027-07-02"]


def _w(name: str, obj) -> None:
    p = config.DOCS / "data" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build(rules, expl, geos, addrs, changes_detailed, ch_report, selfcheck_report) -> None:
    docs = load_docs()
    sub_rules = json.loads((config.SUBMISSION / "rules.json").read_text(encoding="utf-8"))["rules"]
    _w("rules.json", sub_rules)
    _w("addresses.json", [{
        "id": a["address_id"], "street": a["row"]["street_address"], "postal_city": a["row"]["postal_city"],
        "state": a["row"]["state"], "zip": a["row"]["zip"], "use": a["row"]["use_description"],
        "source_dataset": a["row"]["source_dataset"], "city": a["geo"]["city"], "stack": a["stack"],
        "matched": a["geo"].get("matched_address"), "geo_method": a["geo"]["method"],
        "geo_confidence": a["geo"]["confidence"], "flags": a["geo"]["flags"],
        "lat": a["geo"].get("lat"), "lon": a["geo"].get("lon"),
        "facts": {k: (None if v == float("inf") else v) for k, v in a["facts"].items()},
    } for a in addrs])
    _w("sources.json", {d.doc_id: {"url": d.url, "retrieved_at": d.retrieved_at, "source_type": d.source_type,
                                   "jurisdictions": d.jurisdictions, "supplementary": d.supplementary}
                        for d in docs.values()})
    # what we searched and found nothing for (honest "no rule at this level" view)
    have = {(r["jurisdiction"], r["category"]) for r in sub_rules if r["status"] in ("in_force", "not_yet_effective")}
    gaps = defaultdict(list)
    for j in config.JURISDICTION_CODE:
        for c in config.CATEGORIES:
            if (j, c) not in have:
                gaps[j].append(c)
    _w("gaps.json", gaps)
    from .corpus import read_manifest
    unread = defaultdict(list)
    for row in read_manifest():
        if row["doc_id"] not in docs:
            unread[row["jurisdictions"]].append({"doc_id": row["doc_id"], "url": row["url"], "source_type": row["source_type"]})
    _w("unread.json", unread)
    whatifs = []
    for f in sorted((config.BUILD / "whatif").glob("*.json")) if (config.BUILD / "whatif").exists() else []:
        w = json.loads(f.read_text(encoding="utf-8"))
        w["details"] = {k: {kk: v[kk] for kk in ("city", "before", "after")} for k, v in w.get("details", {}).items()}
        whatifs.append(w)
    _w("changes.json", {"detailed": changes_detailed, "report": ch_report, "whatif": whatifs})
    _w("selfcheck.json", selfcheck_report)
    # parity fixtures: Python answers at several dates (the JS engine must reproduce them)
    eng = Engine(rules)
    par = {}
    for d in PARITY_DATES:
        dd = date.fromisoformat(d)
        par[d] = {a["address_id"]: [[e["team_rule_id"], e["result"], e["conflict_flag"], e["event_only"]] for e in eng.lookup(a, dd)]
                  for a in addrs}
    (config.ROOT / "tests").mkdir(exist_ok=True)
    (config.ROOT / "tests" / "parity_fixtures.json").write_text(json.dumps(par), encoding="utf-8")
    _w("meta.json", {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "default_as_of": config.DEFAULT_AS_OF, "categories": config.CATEGORIES,
                     "category_label": config.CATEGORY_LABEL, "states": config.STATES,
                     "rules": len(sub_rules), "addresses": len(addrs)})
