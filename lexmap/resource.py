"""Module A, stage 4: prefer official text for every citation.

For a rule whose primary quote comes from a secondary page (law firm / news), look for a passage in
the OFFICIAL corpus documents of the same jurisdiction that states the same requirement.  An LLM
picks one of the candidate passages or answers null; the pick is verified verbatim like every
other quote.  The secondary quote is kept as corroboration.  Nothing is invented: if no official
document states the rule, the rule keeps its secondary source and its confidence cap.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

from . import config, llm
from .corpus import load_docs
from .spans import SpanIndex

SYSTEM = ("You match legal requirements to supporting passages in official documents. You only select a passage "
          "that states the same legal requirement; otherwise you answer null. Output only JSON.")

TEMPLATE = """Rule: {title}
Jurisdiction: {jurisdiction}; category: {category}; citation: {citation}
Requirement: {requirement}
Key figure: {key_value}

Below are passages from OFFICIAL government documents. Choose the ONE passage (or a contiguous part of it, at least 40 characters, copied exactly) that itself states this requirement or its key figure. A passage that merely mentions the topic, describes a different law, or a different jurisdiction does not count.

{passages}

Return JSON {{"doc_id": "Dxxx", "quoted_span": "<exact text>"}} or {{"doc_id": null, "quoted_span": null}}."""

WORD = re.compile(r"[a-z][a-z0-9.§]{3,}")
STOP = {"that", "this", "with", "from", "have", "shall", "must", "will", "than", "into", "under", "after", "before",
        "within", "their", "there", "which", "rental", "tenant", "tenants", "landlord", "landlords", "unit", "units"}


def _terms(r: dict) -> set[str]:
    text = " ".join(str(r.get(k) or "") for k in ("title", "requirement", "key_value", "citation")).lower()
    return {w for w in WORD.findall(text) if w not in STOP}


def _candidate_docs(r: dict, docs: dict) -> list:
    jur = r["jurisdiction"]
    st = jur.split(", ")[-1]
    out = []
    for d in docs.values():
        if not d.official or d.supplementary:
            continue
        mj = d.jurisdictions.strip()
        if r["level"] == "city" and mj == jur:
            out.append(d)
        elif r["level"] == "state" and (mj == st or mj.endswith(", " + st)):
            out.append(d)
    return out


def _passages(r: dict, docs: list, k: int = 14) -> list[tuple[str, str]]:
    terms = _terms(r)
    scored = []
    for d in docs:
        for s in re.split(r"(?<=[.;])\s+|\n{2,}", d.raw):
            s = s.strip()
            if len(s) < 50 or len(s) > 900:
                continue
            words = set(WORD.findall(s.lower()))
            score = len(words & terms)
            if score >= 3:
                scored.append((score, d.doc_id, s))
    scored.sort(key=lambda x: -x[0])
    return [(doc, s) for _, doc, s in scored[:k]]


def resource_rule(r: dict, docs: dict) -> dict | None:
    cands = _candidate_docs(r, docs)
    if not cands:
        return None
    ps = _passages(r, cands)
    if not ps:
        return None
    prompt = TEMPLATE.format(title=r.get("title"), jurisdiction=r["jurisdiction"], category=r["category"],
                             citation=r.get("citation"), requirement=r.get("requirement"), key_value=r.get("key_value"),
                             passages="\n".join(f"[{doc}] {s}" for doc, s in ps))
    try:
        obj, rec = llm.complete_json(prompt, SYSTEM, config.RECONCILE_MODEL, tag=f"resource:{r['jurisdiction']}:{r['category']}")
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict) or not obj.get("doc_id") or not obj.get("quoted_span"):
        return {"found": False, "llm_call": rec["key"]}
    d = docs.get(obj["doc_id"])
    if d is None or d not in cands:
        return {"found": False, "llm_call": rec["key"]}
    m = SpanIndex(d.raw).find(obj["quoted_span"])
    if m is None or len(m.span) < 40 or m.method == "fuzzy":
        return {"found": False, "llm_call": rec["key"], "note": "selected passage not verifiable"}
    return {"found": True, "llm_call": rec["key"], "doc": d,
            "span": {"text": m.span, "start": m.start, "end": m.end, "method": m.method}}


def run(rules: list[dict], workers: int = 6) -> list[dict]:
    docs = load_docs()
    targets = [r for r in rules if not r.get("official_source")]

    def one(r):
        return r, resource_rule(r, docs)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one, targets))
    for r, res in results:
        if not res:
            continue
        r.setdefault("provenance_resource", {})["llm_call"] = res.get("llm_call")
        if not res.get("found"):
            continue
        d = res["doc"]
        r.setdefault("corroborating_sources", []).insert(0, {
            "doc_id": r["source_doc_id"], "url": r["source_url"], "source_type": r["source_type"],
            "quoted_span": r["verified_spans"][0]["text"], "retrieved_at": r.get("retrieved_at")})
        r["verified_spans"] = [res["span"]]
        r.update({"source_doc_id": d.doc_id, "source_url": d.url, "source_type": d.source_type,
                  "retrieved_at": d.retrieved_at, "official_source": True})
        r["confidence"] = round(min(0.85, float(r.get("confidence") or 0.6) + 0.15), 2)
        r.setdefault("validation_notes", []).append(
            f"primary quote re-sourced to official document {d.doc_id}; secondary quote kept as corroboration")
    return rules
