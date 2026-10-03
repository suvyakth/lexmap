"""Verify that a quoted span exists in a source document and return the exact raw substring.

The scorer checks that each quoted span is found in the corpus.  LLMs routinely change
whitespace, curly quotes and dashes, so we match on a normalised view of the raw file and
then return the *exact* raw characters (including any original line breaks).
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

_TRANS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "‒": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", "﻿": " ",
    "§": "§",
})


def _normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace runs to one space, unify quotes/dashes; keep index map to raw."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = True
    for i, ch in enumerate(text.translate(_TRANS)):
        if ch.isspace():
            if prev_space:
                continue
            out.append(" ")
            idx.append(i)
            prev_space = True
        else:
            out.append(ch.lower())
            idx.append(i)
            prev_space = False
    return "".join(out), idx


def normalise(text: str) -> str:
    return _normalise_with_map(text)[0].strip()


@dataclass
class SpanMatch:
    span: str          # exact raw substring
    start: int         # offset in raw file
    end: int
    method: str        # "exact" | "normalised" | "fuzzy"
    score: float


class SpanIndex:
    def __init__(self, raw: str):
        self.raw = raw
        self.norm, self.map = _normalise_with_map(raw)
        self._sentences: list[tuple[int, int]] | None = None

    def _raw_slice(self, ns: int, ne: int) -> tuple[int, int]:
        start = self.map[ns]
        end = self.map[ne - 1] + 1
        return start, end

    def find(self, quote: str, fuzzy_threshold: float = 0.9) -> SpanMatch | None:
        if not quote or len(quote.strip()) < 8:
            return None
        if quote in self.raw:
            s = self.raw.index(quote)
            return SpanMatch(quote, s, s + len(quote), "exact", 1.0)
        q = normalise(quote)
        # tolerate ellipses inside a quote by taking the longest piece
        if "..." in q or "…" in q:
            parts = [p.strip() for p in re.split(r"\.\.\.|…", q) if len(p.strip()) >= 20]
            if parts:
                q = max(parts, key=len)
        pos = self.norm.find(q)
        if pos >= 0:
            s, e = self._raw_slice(pos, pos + len(q))
            return SpanMatch(self.raw[s:e], s, e, "normalised", 1.0)
        return self._fuzzy(q, fuzzy_threshold)

    def _fuzzy(self, q: str, threshold: float) -> SpanMatch | None:
        """Find the best window of similar length (handles a few changed characters)."""
        n = len(q)
        if n < 20:
            return None
        anchor_len = 24
        best = (0.0, -1, -1)
        anchors = {q[:anchor_len], q[n // 2: n // 2 + anchor_len], q[-anchor_len:]}
        cands: set[int] = set()
        for k, a in enumerate(anchors):
            start = 0
            while True:
                p = self.norm.find(a, start)
                if p < 0:
                    break
                off = 0 if a == q[:anchor_len] else (n // 2 if a == q[n // 2: n // 2 + anchor_len] else n - anchor_len)
                cands.add(max(0, p - off))
                start = p + 1
        for c in cands:
            for delta in (-10, -3, 0, 3, 10):
                s = max(0, c + delta)
                window = self.norm[s:s + n]
                r = difflib.SequenceMatcher(None, q, window, autojunk=False).ratio()
                if r > best[0]:
                    best = (r, s, s + n)
        if best[0] >= threshold:
            s, e = self._raw_slice(best[1], min(best[2], len(self.norm)))
            # trim to word boundaries in raw
            return SpanMatch(self.raw[s:e].strip(), s, e, "fuzzy", round(best[0], 3))
        return None

    def closest_passages(self, quote: str, k: int = 5) -> list[str]:
        """Candidate sentences for an LLM repair prompt."""
        q = normalise(quote)
        sents = [s.strip() for s in re.split(r"(?<=[.;:])\s+|\n+", self.raw) if len(s.strip()) > 25]
        scored = sorted(sents, key=lambda s: difflib.SequenceMatcher(None, q, normalise(s)).ratio(), reverse=True)
        return scored[:k]
