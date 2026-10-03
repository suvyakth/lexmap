"""Module B, stage 1: resolve each address to its legal jurisdiction stack.

The CSV gives a *mailing* city, which is not always the legal city ("Dorchester" is in the
City of Boston; a "Los Angeles" mailing address can be in unincorporated county land).
We ask the U.S. Census Geocoder for the Incorporated Place.  Every answer is cached in
data/cache/geocode.json with the matched address, so the run is reproducible offline.

Data-quality guard: many New Jersey rows carry an out-of-state ZIP (e.g. Brooklyn 11211,
Austin 78746), apparently the owner's mailing ZIP.  A ZIP whose prefix does not belong to
the row's state is ignored and the row is flagged.
"""
from __future__ import annotations

import csv
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

from . import config

URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
CACHE_FILE = config.CACHE / "geocode.json"
ZIP_PREFIX = {"CA": ("90", "91", "92", "93", "94", "95", "96"), "NJ": ("07", "08"), "MA": ("01", "02")}
# Fallback gazetteer, used ONLY when the Census geocoder returns no match.  Boston's
# neighbourhood mailing names are inside the City of Boston (no separate municipality).
BOSTON_NEIGHBOURHOODS = {"allston", "brighton", "charlestown", "dorchester", "east boston", "hyde park",
                         "jamaica plain", "mattapan", "roslindale", "roxbury", "south boston", "west roxbury",
                         "mission hill", "back bay", "south end"}

_lock = threading.Lock()


def load_addresses() -> list[dict]:
    with open(config.ADDRESSES, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _zip5(z: str) -> str:
    z = (z or "").strip()
    if not z:
        return ""
    z = z.split(".")[0].split("-")[0]
    return z.zfill(5) if z.isdigit() else ""


def zip_consistent(state: str, z: str) -> bool | None:
    if not z:
        return None
    return z.startswith(ZIP_PREFIX.get(state, ("",)))


def _query(address: str) -> dict | None:
    r = requests.get(URL, params={"address": address, "benchmark": "Public_AR_Current",
                                  "vintage": "Current_Current", "format": "json"}, timeout=40)
    r.raise_for_status()
    matches = r.json().get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    m = matches[0]
    g = m.get("geographies", {})
    names = lambda k: [x.get("NAME") for x in g.get(k, [])]  # noqa: E731
    return {"matched_address": m.get("matchedAddress"), "lon": m["coordinates"]["x"], "lat": m["coordinates"]["y"],
            "state": names("States"), "county": names("Counties"), "place": names("Incorporated Places"),
            "county_subdivision": names("County Subdivisions"), "n_matches": len(matches)}


def attempts(row: dict) -> list[str]:
    street = row["street_address"].strip()
    city, st, z = row["postal_city"].strip(), row["state"].strip(), _zip5(row["zip"])
    out = []
    if z and zip_consistent(st, z):
        out.append(f"{street}, {city}, {st} {z}")
    out.append(f"{street}, {city}, {st}")
    m = re.match(r"^(\d+)[A-Z]?\s*-\s*\d+[A-Z]?\s+(.*)$", street)
    if m:  # "1031-1035 CLINTON ST" -> "1031 CLINTON ST"
        out.append(f"{m.group(1)} {m.group(2)}, {city}, {st}")
    return list(dict.fromkeys(out))


def resolve(row: dict, cache: dict) -> dict:
    st = row["state"].strip()
    z = _zip5(row["zip"])
    flags = []
    if z and not zip_consistent(st, z):
        flags.append(f"ZIP {z} is not a {st} ZIP (likely an owner mailing ZIP); ignored for geocoding")
    hit, used = None, None
    for q in attempts(row):
        if q in cache:
            res = cache[q]
        else:
            try:
                res = _query(q)
            except requests.RequestException as e:
                res = {"error": str(e)}
            if not (isinstance(res, dict) and "error" in res):
                with _lock:
                    cache[q] = res
        if res and "error" not in res:
            hit, used = res, q
            break
    out = {"address_id": row["address_id"], "state": st, "query": used, "flags": flags}
    if hit:
        place = next((p for p in hit["place"] if p), None)
        city = config.CENSUS_PLACE_TO_JURISDICTION.get((st, place)) if place else None
        if city is None:  # NJ/MA municipalities are also county subdivisions
            for cs in hit["county_subdivision"]:
                city = config.CENSUS_PLACE_TO_JURISDICTION.get((st, cs)) or city
        out.update({"method": "census_geocoder", "confidence": "high", "matched_address": hit["matched_address"],
                    "lat": hit["lat"], "lon": hit["lon"], "county": (hit["county"] or [None])[0],
                    "census_place": place, "city": city})
        if city is None:
            out["flags"].append(f"Census places this address in {place or 'unincorporated ' + str((hit['county'] or ['?'])[0])}, "
                                f"outside the in-scope cities; only state rules are evaluated")
        pc = row["postal_city"].strip()
        if city and pc.lower() != city.split(",")[0].lower():
            out["flags"].append(f"Mailing city '{pc}' resolved to legal jurisdiction {city}")
    else:
        pc = row["postal_city"].strip()
        city = None
        cand = f"{pc}, {st}"
        if cand in config.CITIES:
            city = cand
        elif st == "MA" and pc.lower() in BOSTON_NEIGHBOURHOODS:
            city = "Boston, MA"
        out.update({"method": "fallback_postal_city" if city else "unresolved", "confidence": "low",
                    "matched_address": None, "lat": None, "lon": None, "county": None,
                    "census_place": None, "city": city})
        out["flags"].append("Census geocoder found no match; jurisdiction from mailing city (low confidence)"
                            if city else "Census geocoder found no match; city unknown, only state rules evaluated")
    out["stack"] = [st] + ([out["city"]] if out["city"] else [])
    return out


def geocode_all(workers: int = 8) -> dict[str, dict]:
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    rows = load_addresses()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda r: resolve(r, cache), rows))
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
    return {r["address_id"]: r for r in results}


if __name__ == "__main__":
    from collections import Counter
    res = geocode_all()
    print(Counter((r["state"], r["city"], r["method"]) for r in res.values()))
    for r in res.values():
        if r["flags"]:
            print(r["address_id"], r["flags"])
