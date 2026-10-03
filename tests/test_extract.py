"""Candidate validation (no LLM): lexmap/extract.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testutil  # noqa: E402,F401

from lexmap.corpus import Doc  # noqa: E402
from lexmap.extract import _prune, _valid_pred, canonical_jurisdiction, compute_effective_rule, validate_candidate  # noqa: E402

GOOD = {"field": "units", "op": ">=", "value": 5}
GOOD2 = {"field": "year_built", "op": "<", "value": 1980}
BAD_FIELD = {"field": "zoning", "op": "==", "value": "R3"}
BAD_OP = {"field": "units", "op": "~", "value": 5}


def doc(jur="Jersey City, NJ", official=True):
    return Doc("DTEST", jur, "https://example.org", "official_ordinance" if official else "news", "2026-09-01",
               Path("x.txt"), "raw", "raw", official=official)


def eff(enacted, n):
    return compute_effective_rule({"effective_rule": {"type": "first_day_of_nth_month_after", "enacted": enacted, "n": n}})


class EffectiveRule(unittest.TestCase):
    def test_fair_act(self):
        self.assertEqual(eff("2026-07-20", 12), "2027-07-01")

    def test_four_months(self):
        self.assertEqual(eff("2026-01-20", 4), "2026-05-01")

    def test_year_rollover(self):
        self.assertEqual(eff("2021-06-18", 7), "2022-01-01")
        self.assertEqual(eff("2026-12-05", 1), "2027-01-01")
        self.assertEqual(eff("2026-11-30", 26), "2029-01-01")

    def test_not_applicable(self):
        self.assertIsNone(compute_effective_rule({}))
        self.assertIsNone(compute_effective_rule({"effective_rule": {"type": "fixed", "date": "2026-01-01"}}))
        self.assertIsNone(eff("July 2026", 3))


class Jurisdiction(unittest.TestCase):
    def test_cases(self):
        cases = {
            "City and County of San Francisco": "San Francisco, CA",
            "Los Angeles County": None,
            "New Jersey": "NJ",
            "NJ": "NJ",
            "ca": "CA",
            "Massachusetts": "MA",
            "City of Jersey City": "Jersey City, NJ",
            "Hoboken, NJ": "Hoboken, NJ",
            "Berkeley": "Berkeley, CA",
            "Boston, MA": "Boston, MA",
            "Cambridge, MA": "Cambridge, MA",
            "Santa Ana, CA": "Santa Ana, CA",
            "Oakland, CA": None,
            "": None,
            None: None,
        }
        for inp, want in cases.items():
            self.assertEqual(canonical_jurisdiction(inp), want, inp)


class Prune(unittest.TestCase):
    def test_any_drops_invalid_children(self):
        self.assertEqual(_prune({"any": [GOOD, BAD_FIELD, GOOD2, BAD_OP]}), {"any": [GOOD, GOOD2]})

    def test_any_all_invalid_is_none(self):
        self.assertIsNone(_prune({"any": [BAD_FIELD, BAD_OP]}))

    def test_all_with_invalid_child_dropped_whole(self):
        self.assertIsNone(_prune({"all": [GOOD, BAD_FIELD]}))

    def test_valid_all_kept(self):
        self.assertEqual(_prune({"all": [GOOD, GOOD2]}), {"all": [GOOD, GOOD2]})

    def test_not_with_invalid_child_dropped(self):
        self.assertIsNone(_prune({"not": BAD_OP}))
        self.assertEqual(_prune({"not": GOOD}), {"not": GOOD})

    def test_nested(self):
        p = {"any": [{"all": [GOOD, BAD_FIELD]}, {"all": [GOOD, GOOD2]}]}
        self.assertEqual(_prune(p), {"any": [{"all": [GOOD, GOOD2]}]})

    def test_missing_value_invalid(self):
        self.assertTrue(_valid_pred({"field": "units", "op": ">="}))
        self.assertIsNone(_prune({"field": "units", "op": ">="}))


class ValidateCandidate(unittest.TestCase):
    def base(self, **kw):
        r = {"category": "algorithmic_rent_setting", "jurisdiction": "New Jersey", "status": "not_yet_effective",
             "title": "FAIR Act", "citation": "P.L.2026", "confidence": 0.9,
             "coverage_logic": {"covers": None, "exempt": None}}
        r.update(kw)
        return r

    def test_bad_category_rejected(self):
        r, notes = validate_candidate(self.base(category="parking"), doc())
        self.assertIsNone(r)

    def test_out_of_scope_jurisdiction_rejected(self):
        r, _ = validate_candidate(self.base(jurisdiction="Los Angeles County"), doc("Los Angeles County"))
        self.assertIsNone(r)

    def test_falls_back_to_doc_jurisdiction(self):
        r, _ = validate_candidate(self.base(jurisdiction=None), doc("Jersey City, NJ"))
        self.assertEqual((r["jurisdiction"], r["level"]), ("Jersey City, NJ", "city"))

    def test_state_level_and_computed_date(self):
        r, notes = validate_candidate(self.base(effective_date="2027-07-20", effective_rule={
            "type": "first_day_of_nth_month_after", "enacted": "2026-07-20", "n": 12}), doc())
        self.assertEqual((r["jurisdiction"], r["level"]), ("NJ", "state"))
        self.assertEqual(r["effective_date"], "2027-07-01")
        self.assertTrue(any("replaced by computed" in n for n in notes))

    def test_bad_status_and_dates(self):
        r, _ = validate_candidate(self.base(status="enacted", effective_date="July 1, 2027", end_date=2027), doc())
        self.assertEqual(r["status"], "in_force")
        self.assertIsNone(r["effective_date"])
        self.assertIsNone(r["end_date"])

    def test_unofficial_confidence_capped(self):
        r, _ = validate_candidate(self.base(confidence=0.95), doc(official=False))
        self.assertEqual(r["confidence"], 0.6)
        r, _ = validate_candidate(self.base(confidence="high"), doc())
        self.assertEqual(r["confidence"], 0.7)
        r, _ = validate_candidate(self.base(confidence=3), doc())
        self.assertEqual(r["confidence"], 1.0)

    def test_subject_and_flags_normalised(self):
        r, _ = validate_candidate(self.base(subject="tenant", yields_to_local="yes", citation=""), doc())
        self.assertEqual(r["subject"], "landlord")
        self.assertIs(r["yields_to_local"], True)
        self.assertIs(r["preempts_local"], False)
        self.assertEqual(r["citation"], "FAIR Act")

    def test_invalid_coverage_branches_pruned(self):
        cl = {"covers": {"any": [GOOD, BAD_FIELD]}, "exempt": {"all": [GOOD2, BAD_OP]}}
        r, notes = validate_candidate(self.base(coverage_logic=cl), doc())
        self.assertEqual(r["coverage_logic"], {"covers": {"any": [GOOD]}, "exempt": None})
        self.assertEqual(sum("pruned" in n for n in notes), 2)


if __name__ == "__main__":
    unittest.main()
