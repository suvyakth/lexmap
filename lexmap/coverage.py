"""Three-valued (Kleene) evaluation of a rule's coverage logic against building facts.

Facts are intervals: a building with year_built 1962 has a certificate of occupancy
somewhere in [1962-01-01, 1962-12-31]; a Boston apartment with no unit count has units in
[4, inf).  A comparison is TRUE if it holds for the whole interval, FALSE if it fails for
the whole interval, otherwise UNKNOWN - and the missing fact is named.  This gives the
participant guide's rules for free:
  * a building in a cut-off year is "unknown" (year_built is not the certificate date),
  * an exemption that is impossible from known facts (20 units vs "2 units or fewer") is
    resolved without needing owner data.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

T, F, U = True, False, None
INF = math.inf

OWNER_FIELDS = {"owner_occupied", "owner_type", "owner_property_count", "owner_unit_count", "other_fact"}
FIELD_LABEL = {
    "certificate_of_occupancy": "certificate-of-occupancy date",
    "year_built": "year built",
    "units": "number of units",
    "property_type": "property type",
    "owner_occupied": "whether the owner lives on site",
    "owner_type": "owner type",
    "owner_property_count": "how many properties the owner has",
    "owner_unit_count": "how many units the owner has",
    "other_fact": "a building condition not in the data",
}


@dataclass
class Trace:
    leaves: list[dict] = field(default_factory=list)

    @property
    def missing(self) -> list[str]:
        out = []
        for l in self.leaves:
            if l["result"] is None and not l.get("irrelevant") and l["field"] not in out:
                out.append(l["field"])
        return out


def _parse_date(v, end: bool) -> date | None:
    s = str(v).strip()
    try:
        parts = [int(p) for p in s.split("-")]
    except ValueError:
        return None
    if len(parts) == 3:
        return date(*parts)
    if len(parts) == 2:
        y, m = parts
        if end:
            nm = date(y + (m // 12), m % 12 + 1, 1)
            return date.fromordinal(nm.toordinal() - 1)
        return date(y, m, 1)
    if len(parts) == 1:
        return date(parts[0], 12, 31) if end else date(parts[0], 1, 1)
    return None


def _minus_years(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year - n)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - n, day=28)


def _cmp_interval(lo, hi, op: str, v) -> bool | None:
    """Compare interval [lo, hi] with scalar v."""
    if op == "<=":
        return T if hi <= v else (F if lo > v else U)
    if op == "<":
        return T if hi < v else (F if lo >= v else U)
    if op == ">=":
        return T if lo >= v else (F if hi < v else U)
    if op == ">":
        return T if lo > v else (F if hi <= v else U)
    if op == "==":
        return T if lo == hi == v else (F if v < lo or v > hi else U)
    if op == "!=":
        r = _cmp_interval(lo, hi, "==", v)
        return None if r is None else (not r)
    return U


def _interval(field_: str, facts: dict, as_of: date):
    """Return (lo, hi) for numeric/date fields, or None if unknown."""
    yb = facts.get("year_built")
    if field_ == "year_built":
        return (yb, yb) if yb else None
    if field_ == "certificate_of_occupancy":
        return (date(yb, 1, 1), date(yb, 12, 31)) if yb else None
    if field_ == "units":
        return (facts.get("units_min", 2), facts.get("units_max", INF))
    return None


def _resolve_value(v, field_: str, op: str, as_of: date):
    if isinstance(v, dict) and "as_of_minus_years" in v:
        try:
            d = _minus_years(as_of, int(v["as_of_minus_years"]))
        except (TypeError, ValueError):
            return None
        return d if field_ == "certificate_of_occupancy" else d.year
    if field_ == "certificate_of_occupancy":
        if isinstance(v, (int, float)):
            v = str(int(v))
        end = op in ("<=", ">")          # "on or before 1978" -> through 1978-12-31
        return _parse_date(v, end)
    if field_ in ("year_built", "units", "owner_property_count", "owner_unit_count"):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    return v


def _property_type_value(pt, facts: dict) -> bool | None:
    """Is the building of property type `pt`?  The sample is all assessor apartment parcels."""
    if "property_type" in facts and facts["property_type"] is None:
        return U          # building type not known (e.g. a typed-in address)
    pt = str(pt).lower().replace("-", "_").replace(" ", "_")
    lo, hi = facts.get("units_min", 2), facts.get("units_max", INF)
    if pt in ("multifamily", "multi_family", "apartment", "residential", "residential_rental"):
        return T
    if pt in ("single_family", "single_family_home", "sfr"):
        return F if lo >= 2 else U
    if pt == "duplex":
        return T if lo == hi == 2 else (F if lo > 2 or hi < 2 else U)
    if pt in ("triplex",):
        return T if lo == hi == 3 else (F if lo > 3 or hi < 3 else U)
    if pt in ("condo", "condominium", "townhouse", "townhome", "mobile_home", "mobilehome"):
        return F   # parcels are whole apartment buildings, not condo units or mobile homes
    return U


def _leaf(p: dict, facts: dict, as_of: date, trace: Trace) -> bool | None:
    f, op, raw_v = p.get("field"), p.get("op"), p.get("value")
    res: bool | None
    if f in OWNER_FIELDS:
        res = U
    elif f == "property_type":
        if op == "in" and isinstance(raw_v, list):
            vals = [_property_type_value(x, facts) for x in raw_v]
            res = T if T in vals else (F if all(v is F for v in vals) else U)
        else:
            r = _property_type_value(raw_v, facts)
            res = r if op == "==" else (None if r is None else not r) if op == "!=" else U
    else:
        iv = _interval(f, facts, as_of)
        v = _resolve_value(raw_v, f, op, as_of)
        if op == "in" and isinstance(raw_v, list) and iv is not None:
            lo, hi = iv
            vals = [_resolve_value(x, f, "==", as_of) for x in raw_v]
            if f == "certificate_of_occupancy":
                res = U
            else:
                lo, hi = float(lo), float(hi)
                hits = [x for x in vals if x is not None and lo <= x <= hi]
                res = T if (lo == hi and hits) else (F if not hits and all(x is not None for x in vals) else U)
        elif iv is None or v is None:
            res = U
        else:
            lo, hi = iv
            if f != "certificate_of_occupancy":
                lo, hi = float(lo), float(hi)
            res = _cmp_interval(lo, hi, op, v)
    trace.leaves.append({"field": f, "op": op, "value": raw_v if not isinstance(raw_v, dict) else raw_v,
                         "resolved_value": str(_resolve_value(raw_v, f, op, as_of)) if f not in OWNER_FIELDS else None,
                         "result": res})
    return res


def evaluate(p, facts: dict, as_of: date, trace: Trace | None = None) -> bool | None:
    trace = trace if trace is not None else Trace()
    if p is None:
        return T
    if "all" in p or "any" in p:
        start = len(trace.leaves)
        if "all" in p:
            vals = [evaluate(q, facts, as_of, trace) for q in p["all"]]
            res = F if F in vals else (T if all(v is T for v in vals) else U)
        else:
            vals = [evaluate(q, facts, as_of, trace) for q in p["any"]]
            res = T if T in vals else (F if all(v is F for v in vals) else U)
        if res is not U:
            # unknown sub-conditions that did not change the outcome are not "missing facts"
            for l in trace.leaves[start:]:
                if l["result"] is None:
                    l["irrelevant"] = True
        return res
    if "not" in p:
        v = evaluate(p["not"], facts, as_of, trace)
        return None if v is None else (not v)
    return _leaf(p, facts, as_of, trace)


DATE_OPS = {"<=": "on or before", "<": "before", ">": "after", ">=": "on or after", "==": "on", "!=": "not on", "in": "one of"}
NUM_OPS = {"<=": "at most", "<": "fewer than", ">": "more than", ">=": "at least", "==": "exactly", "!=": "not", "in": "one of"}
CAT_OPS = {"==": "is", "!=": "is not", "in": "is one of"}


def op_words(field_: str, op: str) -> str:
    if field_ == "certificate_of_occupancy":
        return DATE_OPS.get(op, op)
    if field_ in ("year_built",):
        return {"<=": "in or before", "<": "before", ">": "after", ">=": "in or after", "==": "in", "!=": "not in"}.get(op, op)
    if field_ in ("units", "owner_property_count", "owner_unit_count"):
        return NUM_OPS.get(op, op)
    return CAT_OPS.get(op, op)


def describe_leaf(l: dict, facts: dict) -> str:
    f = l["field"]
    label = FIELD_LABEL.get(f, f)
    if f == "other_fact":
        return f"{l['value']}? unknown (not in the data)"
    val = l["value"]
    if isinstance(val, dict) and "as_of_minus_years" in val:
        val = f"{l['resolved_value']} ({val['as_of_minus_years']} years before the query date)"
    if f in ("certificate_of_occupancy", "year_built"):
        have = f"built {facts['year_built']}" if facts.get("year_built") else "year built not in the data"
    elif f == "units":
        lo, hi = facts.get("units_min"), facts.get("units_max")
        have = f"{int(lo)} units" if lo == hi else (f"{int(lo)}+ units" if hi == INF else f"{int(lo)}-{int(hi)} units")
    elif f == "property_type":
        have = "apartment building"
    else:
        have = "not in the data"
    verdict = {True: "yes", False: "no", None: "unknown"}[l["result"]]
    if isinstance(val, list):
        val = ", ".join(str(x).replace("_", " ") for x in val)
    elif isinstance(val, bool):
        val = "yes" if val else "no"
    elif isinstance(val, str):
        val = val.replace("_", " ")
    return f"{label} {op_words(f, l['op'])} {val}? {verdict} ({have})"
