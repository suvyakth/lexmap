"""Plain-language EN/ES summaries per rule, with a hallucination guard.

The model may only restate the record.  Any number in its output that does not occur in
the rule record is treated as invented: that summary is discarded and the extracted
`requirement` text is shown instead.
"""
from __future__ import annotations

import json
import re

from . import config, llm, prompts

FIELDS = ["team_rule_id", "jurisdiction", "category", "status", "title", "requirement", "key_value",
          "coverage_conditions", "exemptions", "effective_date", "end_date", "penalty", "citation"]
NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(s: str) -> set[str]:
    return {n.replace(",", "") for n in NUM_RE.findall(s or "")}


def _guard(text: str, record: dict) -> bool:
    allowed = _numbers(json.dumps(record, ensure_ascii=False))
    # tolerate formatting differences such as "1.5" vs "1,5" and percentages written out
    extra = {n for n in _numbers(text) if n not in allowed and n.rstrip("0").rstrip(".") not in allowed}
    return not extra


def run(rules: list[dict], batch: int = 10) -> dict:
    recs = [{k: r.get(k) for k in FIELDS} for r in rules]
    out: dict[str, dict] = {}
    for i in range(0, len(recs), batch):
        chunk = recs[i:i + batch]
        prompt = prompts.EXPLAIN_TEMPLATE.format(records=json.dumps(chunk, ensure_ascii=False, indent=1))
        try:
            obj, _ = llm.complete_json(prompt, prompts.EXPLAIN_SYSTEM, config.EXTRACT_MODEL, tag="explain")
        except Exception as e:  # noqa: BLE001
            obj = {}
            print(f"   explain batch {i // batch} failed: {e}")
        for rec in chunk:
            rid = rec["team_rule_id"]
            got = obj.get(rid) if isinstance(obj, dict) else None
            en = (got or {}).get("en") if isinstance(got, dict) else None
            es = (got or {}).get("es") if isinstance(got, dict) else None
            ok_en = bool(en) and _guard(en, rec)
            ok_es = bool(es) and _guard(es, rec)
            out[rid] = {"en": en if ok_en else rec["requirement"], "es": es if ok_es else None,
                        "guard": {"en": "ok" if ok_en else "fallback_to_extracted_requirement",
                                  "es": "ok" if ok_es else "omitted"}}
            for k in ("renter", "landlord", "renter_es", "landlord_es"):
                v = got.get(k) if isinstance(got, dict) else None
                ok = isinstance(v, str) and bool(v.strip()) and _guard(v, rec)
                out[rid][k] = v.strip() if ok else None
                out[rid]["guard"][k] = "ok" if ok else "omitted"
    return out
