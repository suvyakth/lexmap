"""Corpus loading, boilerplate filtering and chunking.

The text shown to the LLM is a *filtered view* of the source file: whole boilerplate
lines are removed, nothing is rewritten.  Quoted spans are always verified against the
untouched raw file (see spans.py), so filtering can never create a citation that is not
in the corpus.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from . import config

HEADER_RE = re.compile(r"^SOURCE: (\S+)\r?\nRETRIEVED: ([^\n]+?)\r?\n\r?\n", re.S)


@dataclass
class Doc:
    doc_id: str
    jurisdictions: str
    url: str
    source_type: str
    retrieved_at: str
    path: Path
    raw: str                     # full file text, untouched
    body: str                    # file text after the 3-line header
    official: bool
    supplementary: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def host(self) -> str:
        return urlparse(self.url).netloc.lower().removeprefix("www.")


def read_manifest() -> list[dict]:
    with open(config.MANIFEST, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _parse(path: Path) -> tuple[str, str, str, str]:
    raw = path.read_text(encoding="utf-8")
    m = HEADER_RE.match(raw)
    if not m:
        return raw, "", "", raw
    return raw, m.group(1), m.group(2).strip(), raw[m.end():]


@lru_cache(maxsize=1)
def load_docs() -> dict[str, Doc]:
    """All documents that have text: the 54 corpus files plus fetched supplementary pages."""
    docs: dict[str, Doc] = {}
    for row in read_manifest():
        did = row["doc_id"]
        corpus_path = config.CORPUS_TEXT / f"{did}.txt"
        supp_path = config.SUPPLEMENTARY / f"{did}.txt"
        if row["status"] == "ok" and corpus_path.exists():
            raw, url, retrieved, body = _parse(corpus_path)
            docs[did] = Doc(did, row["jurisdictions"], url or row["url"], row["source_type"],
                            retrieved or row["retrieved_at"], corpus_path, raw, body,
                            official=row["source_type"].startswith("official"))
        elif supp_path.exists():
            raw, url, retrieved, body = _parse(supp_path)
            docs[did] = Doc(did, row["jurisdictions"], url or row["url"], row["source_type"],
                            retrieved, supp_path, raw, body, official=False, supplementary=True)
    for path in sorted(config.HOUR16.glob("*.txt")) if config.HOUR16.exists() else []:
        meta_path = path.with_suffix(".json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        raw, url, retrieved, body = _parse(path)
        did = "H16-" + re.sub(r"[^A-Za-z0-9]+", "-", path.stem).strip("-").upper()
        docs[did] = Doc(did, meta.get("jurisdiction", ""), url or meta.get("url", f"file:{path.name}"),
                        "official (organiser hour-16 release)", retrieved or meta.get("retrieved_at", "supplied"),
                        path, raw, body, official=True)
    return docs


def hour16_docs() -> list[Doc]:
    return [d for d in load_docs().values() if d.doc_id.startswith("H16-")]


def manifest_jurisdiction(doc: Doc) -> str:
    """Manifest jurisdiction -> canonical form ('CA' or 'City, ST')."""
    j = doc.jurisdictions.strip()
    return j


# ---------------------------------------------------------------- boilerplate filter

def _norm_line(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("﻿", "")).strip()


@lru_cache(maxsize=1)
def _site_boilerplate() -> dict[str, set[str]]:
    """Lines that recur across >=2 documents from the same host are navigation chrome."""
    # De-duplicate identical documents first (D002/D037 and D046/D047 are the same page twice);
    # otherwise every line of a duplicated page would look like site chrome.
    per_host: dict[str, Counter] = defaultdict(Counter)
    distinct: dict[str, set[str]] = defaultdict(set)
    for d in load_docs().values():
        key = _norm_line(d.body)[:5000]
        if key in distinct[d.host]:
            continue
        distinct[d.host].add(key)
        seen = {_norm_line(l) for l in d.body.splitlines() if _norm_line(l)}
        per_host[d.host].update(seen)
    out: dict[str, set[str]] = {}
    for host, cnt in per_host.items():
        if len(distinct[host]) < 3:      # too few pages to tell chrome from content
            out[host] = set()
            continue
        out[host] = {l for l, n in cnt.items() if n >= 2 and len(l) < 120}
    return out


def filtered_text(doc: Doc) -> str:
    """Remove navigation chrome and repeated page headers; keep every substantive line verbatim."""
    boiler = _site_boilerplate().get(doc.host, set())
    lines = doc.body.splitlines()
    counts = Counter(_norm_line(l) for l in lines)
    kept: list[str] = []
    blank = False
    for line in lines:
        n = _norm_line(line)
        if not n:
            if not blank:
                kept.append("")
            blank = True
            continue
        if n in boiler:
            continue
        # repeated short page headers/footers inside one PDF (e.g. "Page 3 of 9", running titles)
        if counts[n] >= 3 and len(n) < 90:
            continue
        if re.fullmatch(r"(page )?\d+( of \d+)?", n, flags=re.I):
            continue
        kept.append(line.replace("﻿", ""))
        blank = False
    return "\n".join(kept).strip()


def chunks(text: str, max_chars: int = 45000, overlap: int = 1500) -> list[str]:
    """Split long documents at line boundaries (or sentence boundaries for very long lines)."""
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    for line in text.splitlines(keepends=True):
        if len(line) > max_chars // 2:
            pieces.extend(re.split(r"(?<=[.;])\s+", line))
        else:
            pieces.append(line)
    out, cur = [], ""
    for p in pieces:
        if len(cur) + len(p) > max_chars and cur:
            out.append(cur)
            cur = cur[-overlap:]
        cur += p if p.endswith("\n") else p + " "
    if cur.strip():
        out.append(cur)
    return out
