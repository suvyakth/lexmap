"""Append-only style audit log (rebuilt each run) so any answer can be reproduced and checked.

Each line is one JSON event:
  source        - every document used: doc id, URL, retrieval date, sha256 of the text file
  llm_call      - every model call behind a rule: cache key (sha256 of model+prompt), model, backend, time
  rule          - every published rule: primary + corroborating sources, verified span offsets, notes
  rejected      - candidates dropped by validation or by the reconciler, with reasons
  lookup        - every (address, rule) answer at the default as-of date with the facts used
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from . import config
from .corpus import load_docs


def write(rules: list[dict], full_lookups: dict, as_of: str) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = []
    for d in load_docs().values():
        lines.append({"event": "source", "doc_id": d.doc_id, "url": d.url, "retrieved_at": d.retrieved_at,
                      "source_type": d.source_type, "file": str(d.path.relative_to(config.ROOT)).replace("\\", "/"),
                      "sha256": hashlib.sha256(d.raw.encode("utf-8")).hexdigest(), "supplementary": d.supplementary})
    cands = json.loads((config.BUILD / "candidates.json").read_text(encoding="utf-8"))
    for c in cands:
        for call in c.get("calls", []):
            lines.append({"event": "llm_call", "doc_id": c["doc_id"], **call})
        for rj in c.get("rejected", []):
            lines.append({"event": "rejected", "stage": "extraction", "doc_id": c["doc_id"],
                          "title": (rj.get("record") or {}).get("title"), "reasons": rj.get("reasons")})
    dropped = config.BUILD / "reconcile_dropped.json"
    if dropped.exists():
        for d in json.loads(dropped.read_text(encoding="utf-8")):
            lines.append({"event": "rejected", "stage": "reconcile", "doc_id": d["candidate"]["source_doc_id"],
                          "title": d["candidate"].get("title"), "reasons": [d.get("reason")], "llm_call": d.get("llm_call")})
    from . import llm as _llm
    for key in sorted(_llm._used):
        cp = config.LLM_CACHE / f"{key}.json"
        if cp.exists():
            rec = json.loads(cp.read_text(encoding="utf-8"))
            lines.append({"event": "llm_call", "key": key, "tag": rec.get("tag"), "model": rec.get("model"),
                          "backend": rec.get("backend"), "created_at": rec.get("created_at")})
    for r in rules:
        for field, ch in ((r.get("qa") or {}).get("changes") or {}).items():
            lines.append({"event": "qa_change", "team_rule_id": r["team_rule_id"], "field": field,
                          "from": ch.get("from"), "to": ch.get("to"), "llm_call": (r.get("qa") or {}).get("llm_call")})
    for r in rules:
        lines.append({"event": "rule", "team_rule_id": r["team_rule_id"], "status": r["status"],
                      "source_doc_id": r["source_doc_id"], "source_url": r["source_url"],
                      "retrieved_at": r.get("retrieved_at"),
                      "spans": [{"start": s["start"], "end": s["end"], "match": s["method"]} for s in r["verified_spans"]],
                      "corroborating": [c["doc_id"] for c in r.get("corroborating_sources", [])],
                      "extraction_llm_call": r.get("llm_call"), "reconcile": r.get("reconcile"),
                      "validation_notes": r.get("validation_notes"), "conflict_note": r.get("conflict_note")})
    for aid, entries in full_lookups.items():
        for e in entries:
            lines.append({"event": "lookup", "as_of": as_of, "address_id": aid, "team_rule_id": e["team_rule_id"],
                          "result": e["result"], "missing_facts": e.get("missing_facts"), "conflict_flag": e["conflict_flag"]})
    header = {"event": "run", "generated_at": now, "as_of": as_of, "rules": len(rules), "addresses": len(full_lookups)}
    config.AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(config.AUDIT_LOG, "w", encoding="utf-8") as f:
        for l in [header] + lines:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
