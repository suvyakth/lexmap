"""Fetch the organiser-listed *secondary* sources that have no supplied text.

Scope and etiquette (Responsible design):
* Only rows of corpus_manifest.csv with source_type "secondary (law firm / news / mirror)".
  Code publishers marked "check-terms" (ecode360, American Legal, gocodebook) are NOT fetched.
* One polite GET per URL, cached to data/supplementary/<doc_id>.txt with the same
  SOURCE/RETRIEVED header as the official corpus.  Pages that refuse (403/429) are skipped.
* Rules extracted only from these pages are marked secondary and get confidence <= 0.6.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from . import config
from .corpus import read_manifest

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36 Lexmap-hackathon-research")
MAX_CHARS = 60000


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "nav", "header", "footer", "form", "aside", "iframe"]):
        t.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text("\n")
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.splitlines()]
    out, blank = [], False
    for l in lines:
        if not l:
            if not blank:
                out.append("")
            blank = True
            continue
        out.append(l)
        blank = False
    return "\n".join(out).strip()


def fetch_all(force: bool = False) -> list[dict]:
    config.SUPPLEMENTARY.mkdir(parents=True, exist_ok=True)
    log = []
    for row in read_manifest():
        if row["status"] == "ok" or not row["source_type"].startswith("secondary"):
            continue
        did, url = row["doc_id"], row["url"]
        path = config.SUPPLEMENTARY / f"{did}.txt"
        if path.exists() and not force:
            log.append({"doc_id": did, "status": "cached"})
            continue
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"}, timeout=30)
        except requests.RequestException as e:
            log.append({"doc_id": did, "status": f"error {type(e).__name__}"})
            continue
        if r.status_code != 200:
            log.append({"doc_id": did, "status": f"http {r.status_code} (skipped)"})
            continue
        text = html_to_text(r.text)[:MAX_CHARS]
        if len(text) < 400:
            log.append({"doc_id": did, "status": "too little text (skipped)"})
            continue
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        path.write_text(f"SOURCE: {url}\nRETRIEVED: {ts}\n\n{text}\n", encoding="utf-8")
        log.append({"doc_id": did, "status": "fetched", "chars": len(text)})
    (config.SUPPLEMENTARY / "fetch_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    return log


if __name__ == "__main__":
    for row in fetch_all(force="--force" in sys.argv):
        print(row)
