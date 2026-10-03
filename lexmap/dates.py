"""Module A, stage 5: what does each effective date mean?

The scored `effective_date` is the date the CURRENT version of a rule took effect (e.g. Civ. Code
§ 1950.5 as amended by AB 12: 2024-07-01).  For an as-of query before that date the right answer is
usually "an earlier version applied", not "not yet effective".  This stage asks, per rule, whether the
date marks a brand-new requirement or an amendment of one already in force, and (for amendments) the
earliest date the requirement is known to have been in force.  The engine uses `in_force_since` for
amendments; `effective_date` itself is left unchanged.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from . import config, llm
from .corpus import load_docs
from .extract import DATE_RE
from .qa import _excerpts

SYSTEM = ("You are a careful legal historian. You classify the effective date of a rule record using only the record "
          "and the source excerpts. Output only JSON.")

TEMPLATE = """A rule record states effective_date = {effective_date}. Decide what that date means.

- "new": before this date the requirement did not exist at all in this jurisdiction (a newly enacted law, a new ban, a new cap).
- "amendment": a version of this requirement was already in force before this date; the date is when an amendment, new figure or re-enactment took effect (e.g. a long-standing deposit statute amended in 2024; an annual rate update; a code section rewritten by a later bill).

If "amendment", give in_force_since = the earliest date the excerpts or record show the requirement in force (ISO), or null if not stated.

RULE RECORD:
{record}

SOURCE EXCERPTS:
{excerpts}

Return JSON {{"kind": "new"|"amendment", "in_force_since": "YYYY-MM-DD"|null, "reason": "one sentence"}}"""


def classify(r: dict, docs: dict) -> dict | None:
    keys = ["jurisdiction", "category", "status", "title", "requirement", "key_value", "effective_date", "citation",
            "citation_full", "coverage_conditions", "exemptions", "interaction"]
    prompt = TEMPLATE.format(effective_date=r["effective_date"],
                             record=json.dumps({k: r.get(k) for k in keys}, ensure_ascii=False, indent=1),
                             excerpts=_excerpts(r, docs, width=900, max_chars=6000))
    try:
        obj, rec = llm.complete_json(prompt, SYSTEM, config.EXTRACT_MODEL, tag=f"dates:{r['jurisdiction']}:{r['category']}")
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    if not isinstance(obj, dict) or obj.get("kind") not in ("new", "amendment"):
        return {"llm_call": rec["key"], "kind": None}
    since = obj.get("in_force_since")
    if since is not None and not (isinstance(since, str) and DATE_RE.match(since)):
        since = None
    return {"llm_call": rec["key"], "kind": obj["kind"], "in_force_since": since, "reason": obj.get("reason")}


def run(rules: list[dict], workers: int = 6) -> list[dict]:
    docs = load_docs()
    targets = [r for r in rules if r.get("effective_date") and r.get("status") in ("in_force", "not_yet_effective")]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda r: (r, classify(r, docs)), targets))
    for r, res in results:
        if not res or res.get("kind") is None:
            continue
        r["date_meaning"] = res
        if res["kind"] == "amendment" and (res.get("in_force_since") or "0000") < r["effective_date"]:
            r["amendment"] = True
            r["in_force_since"] = res.get("in_force_since")   # None = in force before the records start
    return rules
