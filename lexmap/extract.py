"""Module A, stage 1: per-document LLM extraction -> validated, span-verified candidates."""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from . import config, llm, prompts
from .corpus import Doc, chunks, filtered_text, load_docs
from .spans import SpanIndex

ALLOWED_FIELDS = {"certificate_of_occupancy", "year_built", "units", "property_type", "owner_occupied",
                  "owner_type", "owner_property_count", "owner_unit_count", "other_fact"}
ALLOWED_OPS = {"<=", "<", ">=", ">", "==", "!=", "in"}
STATUS = {"in_force", "not_yet_effective", "pending", "failed"}
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

# documents that the corpus survey showed are not law (kept in audit trail, not extracted)
SKIP_DOCS = {
    "D078": "URL resolved to the SF Human Rights Commission homepage, not the Fair Chance Ordinance",
}


def canonical_jurisdiction(j: str | None) -> str | None:
    if not j:
        return None
    s = j.strip()
    up = s.upper()
    names = {"CALIFORNIA": "CA", "NEW JERSEY": "NJ", "MASSACHUSETTS": "MA"}
    if up in config.STATES:
        return up
    if up in names:
        return names[up]
    s = re.sub(r"^(city|town) (and county )?of ", "", s, flags=re.I)
    s = re.sub(r"city and county of san francisco", "San Francisco", s, flags=re.I)
    if "county" in s.lower():
        return None          # county rules are out of scope (no county rules in the corpus)
    for city in config.CITIES:
        cname, st = city.split(", ")
        if s.lower().startswith(cname.lower()) and (st in s.upper() or "," not in s):
            return city
    return None


# ------------------------------------------------------------------ validation

def _valid_pred(p, path="covers") -> list[str]:
    errs: list[str] = []
    if p is None:
        return errs
    if not isinstance(p, dict):
        return [f"{path}: not an object"]
    if "all" in p or "any" in p:
        key = "all" if "all" in p else "any"
        if not isinstance(p[key], list) or not p[key]:
            return [f"{path}.{key}: empty"]
        for i, q in enumerate(p[key]):
            errs += _valid_pred(q, f"{path}.{key}[{i}]")
        return errs
    if "not" in p:
        return _valid_pred(p["not"], f"{path}.not")
    f, op = p.get("field"), p.get("op")
    if f not in ALLOWED_FIELDS:
        errs.append(f"{path}: field {f!r} not allowed")
    if op not in ALLOWED_OPS:
        errs.append(f"{path}: op {op!r} not allowed")
    if "value" not in p:
        errs.append(f"{path}: missing value")
    return errs


def _prune(p):
    """Drop invalid branches conservatively: an invalid child of `any` is removed; an `all`
    or `not` containing an invalid child is removed as a whole (so we never broaden it)."""
    if p is None or not isinstance(p, dict):
        return None
    if "any" in p and isinstance(p["any"], list):
        kids = [k for k in (_prune(q) for q in p["any"]) if k is not None]
        return {"any": kids} if kids else None
    if "all" in p and isinstance(p["all"], list):
        kids = [_prune(q) for q in p["all"]]
        return None if any(k is None for k in kids) or not kids else {"all": kids}
    if "not" in p:
        k = _prune(p["not"])
        return None if k is None else {"not": k}
    return p if not _valid_pred(p) else None


def compute_effective_rule(rule: dict) -> str | None:
    """'first day of the Nth month next following enactment' -> ISO date (deterministic)."""
    er = rule.get("effective_rule")
    if not isinstance(er, dict) or er.get("type") != "first_day_of_nth_month_after":
        return None
    try:
        n = int(er["n"])
        y, m, _ = (int(x) for x in str(er["enacted"]).split("-"))
    except Exception:  # noqa: BLE001
        return None
    m0 = m - 1 + n
    return date(y + m0 // 12, m0 % 12 + 1, 1).isoformat()


def validate_candidate(r: dict, doc: Doc) -> tuple[dict | None, list[str]]:
    notes: list[str] = []
    if not isinstance(r, dict):
        return None, ["not an object"]
    cat = r.get("category")
    if cat not in config.CATEGORIES:
        return None, [f"bad category {cat!r}"]
    jur = canonical_jurisdiction(r.get("jurisdiction")) or canonical_jurisdiction(doc.jurisdictions)
    if jur is None:
        return None, [f"out-of-scope jurisdiction {r.get('jurisdiction')!r}"]
    r["jurisdiction"] = jur
    r["level"] = "city" if "," in jur else "state"
    if r.get("status") not in STATUS:
        notes.append(f"status {r.get('status')!r} -> in_force")
        r["status"] = "in_force"
    computed = compute_effective_rule(r)
    if computed:
        if r.get("effective_date") and r["effective_date"] != computed:
            notes.append(f"effective_date {r['effective_date']} replaced by computed {computed}")
        r["effective_date"] = computed
    for k in ("effective_date", "enacted_date", "end_date"):
        v = r.get(k)
        if v is not None and not (isinstance(v, str) and DATE_RE.match(v)):
            notes.append(f"{k} {v!r} not ISO -> null")
            r[k] = None
    cl = r.get("coverage_logic") or {}
    if not isinstance(cl, dict):
        cl = {}
    for part in ("covers", "exempt"):
        errs = _valid_pred(cl.get(part), part)
        if errs:
            pruned = _prune(cl.get(part))
            notes.append(f"coverage_logic.{part}: invalid branches pruned {errs}")
            cl[part] = pruned
    r["coverage_logic"] = {"covers": cl.get("covers"), "exempt": cl.get("exempt")}
    if r.get("subject") not in ("landlord", "municipality"):
        r["subject"] = "landlord"
    try:
        c = float(r.get("confidence", 0.7))
    except (TypeError, ValueError):
        c = 0.7
    if not doc.official:
        c = min(c, 0.6)
    r["confidence"] = round(max(0.0, min(1.0, c)), 2)
    for k in ("yields_to_local", "preempts_local"):
        r[k] = bool(r.get(k))
    if not r.get("citation"):
        r["citation"] = r.get("title") or ""
    return r, notes


def verify_spans(r: dict, doc: Doc, repair: bool = True) -> list[str]:
    """Replace quoted_span/supporting_spans with exact raw substrings; repair via LLM if needed."""
    notes: list[str] = []
    idx = SpanIndex(doc.raw)
    verified: list[dict] = []
    raw_spans = [r.get("quoted_span")] + list(r.get("supporting_spans") or [])
    for i, q in enumerate(raw_spans):
        if not isinstance(q, str) or len(q.strip()) < 20:
            continue
        m = idx.find(q)
        if m is None and repair and i == 0:
            passages = idx.closest_passages(q, 6)
            prompt = prompts.REPAIR_TEMPLATE.format(
                doc_id=doc.doc_id, quote=q, requirement=r.get("requirement", ""),
                passages="\n".join(f"- {p}" for p in passages))
            try:
                obj, _ = llm.complete_json(prompt, prompts.EXTRACT_SYSTEM, config.EXTRACT_MODEL, tag="repair")
                q2 = obj.get("quoted_span") if isinstance(obj, dict) else None
                if q2:
                    m = idx.find(q2)
                    if m:
                        notes.append("quoted_span repaired by LLM re-selection")
            except Exception as e:  # noqa: BLE001
                notes.append(f"repair failed: {e}")
        if m is None:
            notes.append(f"span {i} not found in {doc.doc_id}: {q[:60]!r}")
            continue
        if m.method == "fuzzy":
            notes.append(f"span {i} fuzzy-matched ({m.score})")
        verified.append({"text": m.span, "start": m.start, "end": m.end, "method": m.method})
    # de-duplicate
    seen, uniq = set(), []
    for v in verified:
        if v["text"] not in seen:
            seen.add(v["text"])
            uniq.append(v)
    r["verified_spans"] = uniq
    return notes


# ------------------------------------------------------------------ driver

def extract_doc(doc: Doc, use_cache: bool = True) -> dict:
    if doc.doc_id in SKIP_DOCS:
        return {"doc_id": doc.doc_id, "candidates": [], "rejected": [], "notes": [SKIP_DOCS[doc.doc_id]], "calls": []}
    text = filtered_text(doc)
    parts = chunks(text)
    out = {"doc_id": doc.doc_id, "candidates": [], "rejected": [], "notes": [], "calls": []}
    for ci, part in enumerate(parts):
        chunk_note = f"\n- This is part {ci + 1} of {len(parts)} of a long document." if len(parts) > 1 else ""
        prompt = prompts.EXTRACT_TEMPLATE.format(
            doc_id=doc.doc_id, url=doc.url, source_type=doc.source_type, jurisdiction=doc.jurisdictions,
            retrieved=doc.retrieved_at, as_of=config.DEFAULT_AS_OF, chunk_note=chunk_note, text=part)
        try:
            obj, rec = llm.complete_json(prompt, prompts.EXTRACT_SYSTEM, config.EXTRACT_MODEL,
                                         use_cache=use_cache, tag=f"extract:{doc.doc_id}:{ci}")
        except Exception as e:  # noqa: BLE001
            out["notes"].append(f"chunk {ci}: extraction failed: {e}")
            continue
        out["calls"].append({"key": rec["key"], "model": rec["model"], "backend": rec.get("backend"),
                             "created_at": rec.get("created_at"), "chunk": ci})
        if isinstance(obj, dict) and obj.get("notes"):
            out["notes"].append(str(obj["notes"]))
        for r in (obj.get("rules", []) if isinstance(obj, dict) else []):
            cand, vnotes = validate_candidate(r, doc)
            if cand is None:
                out["rejected"].append({"record": r, "reasons": vnotes})
                continue
            vnotes += verify_spans(cand, doc)
            if not cand["verified_spans"]:
                out["rejected"].append({"record": cand, "reasons": vnotes + ["no verifiable quoted span"]})
                continue
            cand["source_doc_id"] = doc.doc_id
            cand["source_url"] = doc.url
            cand["source_type"] = doc.source_type
            cand["retrieved_at"] = doc.retrieved_at
            cand["official_source"] = doc.official
            cand["supplementary_source"] = doc.supplementary
            cand["llm_call"] = rec["key"]
            cand["validation_notes"] = vnotes
            out["candidates"].append(cand)
    return out


def run(doc_ids: list[str] | None = None, workers: int = 6, use_cache: bool = True) -> list[dict]:
    docs = load_docs()
    ids = doc_ids or sorted(docs)
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(extract_doc, docs[i], use_cache): i for i in ids}
        for f in as_completed(futs):
            i = futs[f]
            try:
                results[i] = f.result()
            except Exception as e:  # noqa: BLE001
                results[i] = {"doc_id": i, "candidates": [], "rejected": [], "notes": [f"crashed: {e}"], "calls": []}
            r = results[i]
            print(f"  {i}: {len(r['candidates'])} candidates, {len(r['rejected'])} rejected", flush=True)
    ordered = [results[i] for i in ids]
    config.BUILD.mkdir(parents=True, exist_ok=True)
    if doc_ids is None:
        (config.BUILD / "candidates.json").write_text(json.dumps(ordered, ensure_ascii=False, indent=1), encoding="utf-8")
    return ordered


if __name__ == "__main__":
    ids = sys.argv[1:] or None
    res = run(ids)
    if ids:
        print(json.dumps(res, ensure_ascii=False, indent=1)[:20000])
