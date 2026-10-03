"""Building facts per address, with explicit provenance and honest intervals.

Only facts in the sample CSV are used.  Where the CSV leaves `units` blank we derive a
*lower bound* from the assessor's own use code / description (documented below); we
never guess a year.  Owner facts are always unknown (the data has no owner names).
"""
from __future__ import annotations

import math
import re

INF = math.inf

# (source_dataset prefix, use_code or regex on description) -> (units_min, units_max, provenance)
DESCRIPTION_RULES = [
    (r"\(5\+ units\)", (5, INF, "assessor use code description says 5+ units")),
    (r"^Five or more apartments$", (5, INF, "LA County use code 05xx: five or more apartments")),
    (r"Apartment 5 to 14 Units|Flats 5 to 14 units|Flat & Store 5 to 14 units", (5, 14, "SF use code: 5 to 14 units")),
    (r"Apartment 15 Units or more", (15, INF, "SF use code A15: 15 or more units")),
    (r"TIC Bldg 4 units or less", (1, 4, "SF use code TIC: 4 units or less")),
    (r"^APT 7-30 UNITS$", (7, 30, "Boston property type 112: apartment 7-30 units")),
    (r"^4-8-UNIT-APT$", (4, 8, "Cambridge property class 111: 4-8 unit apartment")),
    (r">8-UNIT-APT", (9, INF, "Cambridge property class 112: more than 8 units")),
]


def _int(v: str | None) -> int | None:
    if v is None:
        return None
    v = str(v).strip()
    if not v:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def derive_units(row: dict) -> tuple[float, float, str]:
    u = _int(row.get("units"))
    if u is not None and u > 0:
        return u, u, "units column (assessor record)"
    desc = (row.get("use_description") or "").strip()
    code = (row.get("use_code") or "").strip()
    lo, hi, prov = 2, INF, "multifamily sample (units not recorded)"
    for pat, (a, b, p) in DESCRIPTION_RULES:
        if re.search(pat, desc, flags=re.I):
            lo, hi, prov = a, b, p
            break
    if row.get("state") == "NJ" and code == "4C":
        # N.J.A.C. 18:12-2.2: class 2 = residential of four families or less; class 4C = apartment.
        lo, prov = max(lo, 5), "NJ property class 4C (apartment; 1-4 family homes are class 2)"
        comps = [int(x.replace("O", "0")) for x in re.findall(r"(?:^|[-/,\s.])(\d[\dO]*)\s*U(?![A-Z])", desc)]
        if comps and max(comps) > lo:
            lo, prov = max(comps), f"assessor building description '{desc}' ({max(comps)} units)"
    if code.startswith("A/") and lo < 4:
        lo, prov = 4, "Boston land use 'A' (apartment building); conservative lower bound of 4 units"
    return lo, hi, prov


def facts_for(row: dict) -> dict:
    yb = _int(row.get("year_built"))
    if yb is not None and not (1700 <= yb <= 2030):
        yb = None
    lo, hi, prov = derive_units(row)
    desc = (row.get("use_description") or "").upper()
    return {
        "year_built": yb,
        "year_source": "year_built column (assessor record)" if yb else "not in the data",
        "units_min": lo,
        "units_max": hi,
        "units_source": prov,
        "property_type": "multifamily",
        "property_type_source": "every sample row is an assessor multifamily/apartment parcel",
        "flags": [f for f, ok in (("co-op", "CO-OP" in desc),
                                  ("affordable/subsidised (assessor description)", "AFFORDABL" in desc or "SUBSD" in desc))
                  if ok],
    }


def units_label(f: dict) -> str:
    lo, hi = f["units_min"], f["units_max"]
    if lo == hi:
        return f"{int(lo)} units"
    if hi == INF:
        return f"{int(lo)}+ units (derived)"
    return f"{int(lo)}-{int(hi)} units (derived)"
