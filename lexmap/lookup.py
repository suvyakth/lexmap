"""Module B, stage 2: deterministic address -> applicable rules, for any as-of date.

Decision table (first match wins) for rule R and address A at date D:
  0  R's jurisdiction not in A's stack, R failed, R repealed by D, or R only binds
     municipalities                                              -> omitted
  1  R is a pending bill/proposal                                -> pending
  2  R's effective date is after D                               -> not_yet_effective
  3  R's coverage is FALSE for A                                 -> omitted
  4  R's coverage is UNKNOWN (a needed fact is missing)          -> unknown
  5  R's exemption is TRUE                                       -> omitted
  6  R's exemption is UNKNOWN                                    -> unknown
  7  (city rules) a state law exempts A from local rules of this kind
       TRUE -> omitted, UNKNOWN -> unknown
  8  R yields to a local rule that applies at A                  -> superseded
  9  R yields to a local rule whose coverage is unknown at A     -> unknown
 10  otherwise                                                   -> applies
"""
from __future__ import annotations

import json
from datetime import date

from . import config
from .coverage import FIELD_LABEL, Trace, describe_leaf, evaluate
from .facts import facts_for, units_label
from .geocode import load_addresses

ORDER = {c: i for i, c in enumerate(config.CATEGORIES)}


def _d(s: str | None, end: bool = False) -> date | None:
    if not s:
        return None
    parts = [int(p) for p in str(s).split("-")]
    if len(parts) == 1:
        return date(parts[0], 12 if end else 1, 31 if end else 1)
    if len(parts) == 2:
        return date(parts[0], parts[1], 1)
    return date(*parts)


def load_rules(path=None) -> list[dict]:
    p = path or (config.BUILD / "rules_full.json")
    return json.loads(p.read_text(encoding="utf-8"))


def load_geocodes() -> dict[str, dict]:
    p = config.BUILD / "geocodes.json"
    return json.loads(p.read_text(encoding="utf-8"))


def address_records(geocodes: dict[str, dict] | None = None) -> list[dict]:
    geocodes = geocodes if geocodes is not None else load_geocodes()
    out = []
    for row in load_addresses():
        g = geocodes[row["address_id"]]
        out.append({"address_id": row["address_id"], "row": row, "geo": g, "facts": facts_for(row),
                    "stack": g["stack"]})
    return out


class Engine:
    def __init__(self, rules: list[dict]):
        self.rules = rules
        self.by_id = {r["team_rule_id"]: r for r in rules}
        self.state_modifiers: dict[tuple[str, str], list[dict]] = {}
        for r in rules:
            if r["level"] == "state" and r.get("subject") == "municipality":
                cov = (r.get("coverage_logic") or {}).get("covers")
                if cov:
                    self.state_modifiers.setdefault((r["jurisdiction"], r["category"]), []).append(r)

    # -------------------------------------------------------------- one rule
    def evaluate(self, rule: dict, addr: dict, as_of: date, memo: dict | None = None) -> dict | None:
        memo = memo if memo is not None else {}
        key = rule["team_rule_id"]
        if key in memo:
            return memo[key]
        memo[key] = None  # cycle guard
        res = self._evaluate(rule, addr, as_of, memo)
        memo[key] = res
        return res

    def _evaluate(self, rule: dict, addr: dict, as_of: date, memo: dict) -> dict | None:
        facts = addr["facts"]
        if rule["jurisdiction"] not in addr["stack"]:
            return None
        status = rule.get("status")
        if status == "failed" or rule.get("subject") == "municipality":
            return None
        end = _d(rule.get("end_date"))
        if end and end <= as_of:
            return None
        if status == "pending":
            return {"result": "pending", "reason": "Bill or proposal, not law.", "missing": []}
        eff = _d(rule.get("effective_date"))
        if (eff and eff > as_of) or (status == "not_yet_effective" and not eff):
            return {"result": "not_yet_effective",
                    "reason": f"Enacted; takes effect {rule.get('effective_date') or 'on a future date'}.",
                    "missing": []}
        cl = rule.get("coverage_logic") or {}
        t_cov, t_ex = Trace(), Trace()
        cov = evaluate(cl.get("covers"), facts, as_of, t_cov)
        if cov is False:
            return None
        if cov is None:
            return {"result": "unknown", "missing": t_cov.missing,
                    "reason": "Coverage depends on facts not in the data: " + _facts_text(t_cov, facts)}
        ex = evaluate(cl.get("exempt"), facts, as_of, t_ex) if cl.get("exempt") else False
        if ex is True:
            return None
        if ex is None:
            return {"result": "unknown", "missing": t_ex.missing,
                    "reason": "An exemption may apply; it depends on facts not in the data: " + _facts_text(t_ex, facts)}
        if rule["level"] == "city":
            st = rule["jurisdiction"].split(", ")[1]
            for m in self.state_modifiers.get((st, rule["category"]), []):
                meff = _d(m.get("effective_date"))
                mst = m.get("status")
                if mst in ("pending", "failed") or (meff and meff > as_of) or (mst == "not_yet_effective" and not meff):
                    continue
                tm = Trace()
                mv = evaluate(m["coverage_logic"]["covers"], facts, as_of, tm)
                if mv is True:
                    return None
                if mv is None:
                    return {"result": "unknown", "missing": tm.missing,
                            "reason": f"State law {m['citation']} exempts some buildings from local rules of this kind; "
                                      f"depends on: " + _facts_text(tm, facts)}
        yielded_unknown = []
        for yid in rule.get("yields_to") or []:
            y = self.by_id.get(yid)
            if not y:
                continue
            yr = self.evaluate(y, addr, as_of, memo)
            if yr and yr["result"] == "applies":
                return {"result": "superseded", "missing": [], "superseded_by": yid,
                        "reason": f"Covered, but the local rule {yid} ({y['citation']}) governs at this address."}
            if yr and yr["result"] == "unknown":
                yielded_unknown.append((yid, yr))
        if yielded_unknown:
            yid, yr = yielded_unknown[0]
            return {"result": "unknown", "missing": yr["missing"],
                    "reason": f"Applies unless the local rule {yid} covers this building, which depends on facts not in the data ("
                              + ", ".join(FIELD_LABEL.get(m, m) for m in yr["missing"]) + ")."}
        return {"result": "applies", "missing": [], "reason": _applies_text(rule, t_cov, t_ex, facts)}

    # -------------------------------------------------------------- one address
    def lookup(self, addr: dict, as_of: date) -> list[dict]:
        memo: dict = {}
        out = []
        for r in self.rules:
            res = self.evaluate(r, addr, as_of, memo)
            if res is None:
                continue
            out.append({"rule": r, **res})
        present = {e["rule"]["team_rule_id"] for e in out}
        entries = []
        for e in out:
            r = e["rule"]
            partners = [c for c in (r.get("conflicts_with") or []) if c in present]
            conflict = bool(r.get("source_conflict")) or bool(partners)
            expl = e["reason"]
            if partners:
                expl += f" Possible conflict with {', '.join(partners)}: flagged for human review."
            elif r.get("source_conflict"):
                expl += " Sources disagree about this rule: flagged for human review."
            entries.append({"team_rule_id": r["team_rule_id"], "result": e["result"], "explanation": expl.strip(),
                            "conflict_flag": conflict, "missing_facts": e.get("missing", []),
                            "category": r["category"], "superseded_by": e.get("superseded_by")})
        entries.sort(key=lambda x: (ORDER[x["category"]], x["team_rule_id"]))
        return entries


def _facts_text(t: Trace, facts: dict) -> str:
    seen, parts = set(), []
    for l in t.leaves:
        if l["result"] is None and not l.get("irrelevant"):
            d = describe_leaf(l, facts)
            if d not in seen:
                seen.add(d)
                parts.append(d)
    return "; ".join(parts) + "."


def _applies_text(rule: dict, t_cov: Trace, t_ex: Trace, facts: dict) -> str:
    bits = []
    if rule["level"] == "state":
        bits.append(f"Statewide {config.STATES[rule['jurisdiction']]} rule.")
    else:
        bits.append(f"{rule['jurisdiction']} city rule; the address is inside city limits.")
    cov_true = [describe_leaf(l, facts) for l in t_cov.leaves if l["result"] is True]
    if cov_true:
        bits.append("Covered: " + "; ".join(cov_true) + ".")
    ex_false = [describe_leaf(l, facts) for l in t_ex.leaves if l["result"] is False]
    if ex_false:
        bits.append("Exemption cannot apply: " + "; ".join(ex_false) + ".")
    return " ".join(bits)


def run(as_of: str = config.DEFAULT_AS_OF, rules: list[dict] | None = None) -> dict:
    rules = rules if rules is not None else load_rules()
    eng = Engine(rules)
    d = date.fromisoformat(as_of)
    full = {}
    for a in address_records():
        full[a["address_id"]] = eng.lookup(a, d)
    return full


def to_submission(full: dict, as_of: str) -> dict:
    return {"as_of": as_of, "lookups": {aid: [{k: e[k] for k in ("team_rule_id", "result", "explanation", "conflict_flag")}
                                             for e in es] for aid, es in full.items()}}


__all__ = ["Engine", "address_records", "load_rules", "run", "to_submission", "units_label"]
