"""Deterministic reconciliation helpers (no LLM): lexmap/reconcile.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testutil  # noqa: E402,F401

from lexmap.reconcile import _dates_conflict, _status_from_dates, align_test_ids, wire_relations  # noqa: E402


class DatesConflict(unittest.TestCase):
    def test_common_precision_agrees(self):
        self.assertFalse(_dates_conflict(["2024-10", "2024-10-14"]))
        self.assertFalse(_dates_conflict(["2026", "2026-03-01", "2026-03"]))
        self.assertFalse(_dates_conflict(["2026-03-01", "2026-03-01"]))
        self.assertFalse(_dates_conflict([]))

    def test_disagreement(self):
        self.assertTrue(_dates_conflict(["2026-03-01", "2026-01"]))          # Berkeley
        self.assertTrue(_dates_conflict(["2026-02-02", "2026-01-24"]))       # LA RSO formula
        self.assertTrue(_dates_conflict(["2025", "2026-01-01"]))


class StatusFromDates(unittest.TestCase):
    def st(self, status, eff, as_of="2026-10-01"):
        return _status_from_dates({"status": status, "effective_date": eff}, as_of)

    def test_pending_and_failed_kept(self):
        self.assertEqual(self.st("pending", "2020-01-01"), "pending")
        self.assertEqual(self.st("failed", None), "failed")

    def test_recomputed_from_date(self):
        self.assertEqual(self.st("in_force", "2027-07-01"), "not_yet_effective")
        self.assertEqual(self.st("not_yet_effective", "2026-01-01"), "in_force")
        self.assertEqual(self.st("in_force", "2026-10-01"), "in_force")
        self.assertEqual(self.st("in_force", "2026-10-02"), "not_yet_effective")

    def test_partial_dates(self):
        self.assertEqual(self.st("in_force", "2026"), "in_force")
        self.assertEqual(self.st("in_force", "2027"), "not_yet_effective")
        self.assertEqual(self.st("in_force", "2026-10"), "in_force")
        self.assertEqual(self.st("in_force", "2026-11"), "not_yet_effective")

    def test_no_or_bad_date_keeps_status(self):
        self.assertEqual(self.st("not_yet_effective", None), "not_yet_effective")
        self.assertEqual(self.st("in_force", "soon"), "in_force")


def r(rid, title="", citation="", status="in_force", conf=0.8):
    return {"team_rule_id": rid, "title": title, "citation": citation, "key_value": "", "status": status,
            "confidence": conf}


class AlignTestIds(unittest.TestCase):
    """dev/change_tests.json references fixed ids; align_test_ids must point them at the right laws."""

    def test_single_id_moves_to_matching_law(self):
        rules = [r("CA-ALG-01", "Some other algorithm law", conf=0.99),
                 r("CA-ALG-02", "AB 325 coordinated pricing algorithms", "Cal. AB 325", conf=0.7)]
        align_test_ids(rules)
        by = {x["team_rule_id"]: x["title"] for x in rules}
        self.assertTrue(by["CA-ALG-01"].startswith("AB 325"))
        self.assertEqual(by["CA-ALG-02"], "Some other algorithm law")

    def test_pending_pair_order_follows_test_title(self):
        # T4 title: "Massachusetts pending bills S.2983 and H.5222" -> P1 = S.2983, P2 = H.5222
        rules = [r("MA-ALG-P1", "Algorithm bill", "H.5222", "pending"),
                 r("MA-ALG-P2", "Algorithm bill", "S.2983", "pending")]
        align_test_ids(rules)
        by = {x["team_rule_id"]: x["citation"] for x in rules}
        self.assertEqual(by, {"MA-ALG-P1": "S.2983", "MA-ALG-P2": "H.5222"})

    def test_ids_stay_unique(self):
        rules = [r("NJ-ALG-01", "Other"), r("NJ-ALG-02", "FAIR Act"), r("NJ-ALG-03", "Third")]
        align_test_ids(rules)
        ids = [x["team_rule_id"] for x in rules]
        self.assertEqual(sorted(ids), ["NJ-ALG-01", "NJ-ALG-02", "NJ-ALG-03"])
        self.assertEqual(next(x["title"] for x in rules if x["team_rule_id"] == "NJ-ALG-01"), "FAIR Act")


class WireRelations(unittest.TestCase):
    def rule(self, rid, jur, cat="algorithmic_rent_setting", **kw):
        d = {"team_rule_id": rid, "jurisdiction": jur, "level": "city" if "," in jur else "state", "category": cat,
             "status": "in_force", "subject": "landlord", "citation": rid}
        d.update(kw)
        return d

    def test_yields_and_preemption(self):
        rules = [self.rule("CA-RENT-01", "CA", "rent_increase_limits", yields_to_local=True),
                 self.rule("LA-RENT-01", "Los Angeles, CA", "rent_increase_limits"),
                 self.rule("NJ-ALG-01", "NJ", status="not_yet_effective", preempts_local=True),
                 self.rule("JC-ALG-01", "Jersey City, NJ"),
                 self.rule("HOB-ALG-01", "Hoboken, NJ"),
                 self.rule("HOB-ALG-P1", "Hoboken, NJ", status="pending"),
                 self.rule("LA-ALG-01", "Los Angeles, CA")]
        wire_relations(rules)
        by = {x["team_rule_id"]: x for x in rules}
        self.assertEqual(by["CA-RENT-01"]["yields_to"], ["LA-RENT-01"])
        self.assertEqual(by["LA-RENT-01"]["overrides"], ["CA-RENT-01"])
        self.assertEqual(sorted(by["NJ-ALG-01"]["conflicts_with"]), ["HOB-ALG-01", "JC-ALG-01"])
        self.assertEqual(by["JC-ALG-01"]["conflicts_with"], ["NJ-ALG-01"])
        self.assertTrue(by["JC-ALG-01"]["conflict_flag"])
        self.assertEqual(by["HOB-ALG-P1"]["conflicts_with"], [])
        self.assertEqual(by["LA-ALG-01"]["conflicts_with"], [])
        self.assertEqual(by["NJ-ALG-01"]["yields_to"], [])


if __name__ == "__main__":
    unittest.main()
