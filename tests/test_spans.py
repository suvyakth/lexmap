"""Verbatim span matching: lexmap/spans.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testutil  # noqa: E402,F401

from lexmap.spans import SpanIndex, normalise  # noqa: E402

RAW = ("SOURCE: https://example.org\nRETRIEVED: 2026-09-01\n\n"
       "Section 3. Fees.\n"
       "(a) A landlord shall not charge an applicant\n   a screening fee that exceeds the “actual cost”\n"
       "of the screening — including the credit report.\n"
       "(b) This section does not apply to owner‑occupied units.\n")


class SpanMatching(unittest.TestCase):
    def setUp(self):
        self.idx = SpanIndex(RAW)

    def test_exact(self):
        q = "(a) A landlord shall not charge an applicant"
        m = self.idx.find(q)
        self.assertIsNotNone(m)
        self.assertEqual(m.method, "exact")
        self.assertEqual(m.span, q)
        self.assertEqual(RAW[m.start:m.end], q)

    def test_normalised_returns_raw_substring_with_newlines(self):
        q = 'A landlord shall not charge an applicant a screening fee that exceeds the "actual cost" of the screening - including'
        self.assertNotIn(q, RAW)
        m = self.idx.find(q)
        self.assertIsNotNone(m)
        self.assertEqual(m.method, "normalised")
        self.assertIn(m.span, RAW)
        self.assertEqual(RAW[m.start:m.end], m.span)
        self.assertIn("\n   a screening fee", m.span)          # original line break + indentation kept
        self.assertIn("“actual cost”", m.span)       # original curly quotes kept
        self.assertIn("—", m.span)
        self.assertTrue(m.span.startswith("A landlord"))
        self.assertTrue(m.span.endswith("including"))

    def test_case_and_extra_spaces_tolerated(self):
        q = "  a LANDLORD   shall not charge an applicant  "
        m = self.idx.find(q)
        self.assertIsNotNone(m)
        self.assertEqual(m.span, "A landlord shall not charge an applicant")

    def test_paraphrase_is_rejected(self):
        q = "Landlords may not charge applicants screening fees above what the screening actually costs."
        self.assertIsNone(self.idx.find(q))

    def test_too_short_is_rejected(self):
        self.assertIsNone(self.idx.find("fee"))
        self.assertIsNone(self.idx.find(""))

    def test_normalise(self):
        self.assertEqual(normalise("  “A” –\n  B  "), '"a" - b')


if __name__ == "__main__":
    unittest.main()
