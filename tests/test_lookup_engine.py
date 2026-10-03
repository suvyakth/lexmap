"""Engine decision table on tiny synthetic rule sets: lexmap/lookup.py."""
from __future__ import annotations

import math
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testutil  # noqa: E402,F401

from lexmap.lookup import Engine  # noqa: E402

INF = math.inf
AS_OF = date(2026, 10, 1)
CAT = "algorithmic_rent_setting"


def rule(rid, jur, *, status="in_force", eff=None, covers=None, exempt=None, subject="landlord", cat=CAT,
         yields_to=(), conflicts_with=(), end=None, source_conflict=False):
    return {"team_rule_id": rid, "jurisdiction": jur, "level": "city" if "," in jur else "state", "category": cat,
            "status": status, "effective_date": eff, "end_date": end, "subject": subject, "citation": f"cite {rid}",
            "coverage_logic": {"covers": covers, "exempt": exempt}, "yields_to": list(yields_to),
            "conflicts_with": list(conflicts_with), "source_conflict": source_conflict}


def addr(stack, year=None, lo=2, hi=INF):
    return {"address_id": "X", "stack": stack, "facts": {"year_built": year, "units_min": lo, "units_max": hi}}


LA = ["CA", "Los Angeles, CA"]
JC = ["NJ", "Jersey City, NJ"]
NWK = ["NJ", "Newark, NJ"]
PRE_1978 = {"field": "certificate_of_occupancy", "op": "<=", "value": "1978-10-01"}
OWNER_OCC = {"field": "owner_occupied", "op": "==", "value": True}


def results(rules, a, as_of=AS_OF):
    return {e["team_rule_id"]: e for e in Engine(rules).lookup(a, as_of)}


class StatusAndDates(unittest.TestCase):
    def test_pending(self):
        r = results([rule("MA-ALG-P1", "MA", status="pending", eff="2026-01-01")], addr(["MA", "Boston, MA"]))
        self.assertEqual(r["MA-ALG-P1"]["result"], "pending")

    def test_pending_respects_coverage(self):
        # coverage is checked first: a bill is only reported where it would reach the building
        r = results([rule("P", "CA", status="pending", covers={"field": "units", "op": "<=", "value": 1})], addr(LA))
        self.assertNotIn("P", r)
        r = results([rule("P", "CA", status="pending", covers={"field": "units", "op": ">=", "value": 2})], addr(LA))
        self.assertEqual(r["P"]["result"], "pending")
        # unknown coverage still reports the bill as pending (status is the more useful fact)
        r = results([rule("P", "CA", status="pending", covers={"field": "owner_occupied", "op": "==", "value": True})], addr(LA))
        self.assertEqual(r["P"]["result"], "pending")

    def test_future_effective(self):
        rs = [rule("NJ-ALG-01", "NJ", status="not_yet_effective", eff="2027-07-01")]
        self.assertEqual(results(rs, addr(NWK))["NJ-ALG-01"]["result"], "not_yet_effective")
        self.assertEqual(results(rs, addr(NWK), date(2027, 6, 30))["NJ-ALG-01"]["result"], "not_yet_effective")
        self.assertEqual(results(rs, addr(NWK), date(2027, 7, 1))["NJ-ALG-01"]["result"], "applies")

    def test_in_force_rule_before_its_date(self):
        rs = [rule("CA-ALG-01", "CA", eff="2026-01-01")]
        self.assertEqual(results(rs, addr(LA), date(2025, 12, 31))["CA-ALG-01"]["result"], "not_yet_effective")
        self.assertEqual(results(rs, addr(LA), date(2026, 1, 2))["CA-ALG-01"]["result"], "applies")

    def test_not_yet_effective_without_date(self):
        rs = [rule("X", "CA", status="not_yet_effective")]
        self.assertEqual(results(rs, addr(LA))["X"]["result"], "not_yet_effective")

    def test_failed_omitted(self):
        self.assertEqual(results([rule("MA-RENT-P1", "MA", status="failed")], addr(["MA", "Boston, MA"])), {})

    def test_municipality_subject_omitted(self):
        self.assertEqual(results([rule("M", "CA", subject="municipality")], addr(LA)), {})

    def test_repealed_omitted(self):
        rs = [rule("R", "CA", end="2026-06-30")]
        self.assertEqual(results(rs, addr(LA)), {})
        self.assertIn("R", results(rs, addr(LA), date(2026, 6, 1)))

    def test_outside_stack_omitted(self):
        rs = [rule("JC-ALG-01", "Jersey City, NJ"), rule("CA-ALG-01", "CA")]
        self.assertEqual(set(results(rs, addr(NWK))), set())
        self.assertEqual(set(results(rs, addr(JC))), {"JC-ALG-01"})


class CoverageOutcomes(unittest.TestCase):
    def test_covers_false_omitted_true_applies_unknown(self):
        rs = [rule("LA-RENT-01", "Los Angeles, CA", covers=PRE_1978, cat="rent_increase_limits")]
        self.assertEqual(results(rs, addr(LA, 1962))["LA-RENT-01"]["result"], "applies")
        self.assertEqual(results(rs, addr(LA, 1985)), {})
        e = results(rs, addr(LA, 1978))["LA-RENT-01"]
        self.assertEqual(e["result"], "unknown")
        self.assertEqual(e["missing_facts"], ["certificate_of_occupancy"])
        self.assertIn("certificate-of-occupancy", e["explanation"])

    def test_exemption(self):
        small = {"all": [{"field": "units", "op": "<=", "value": 2}, OWNER_OCC]}
        rs = [rule("X", "CA", exempt=small)]
        self.assertEqual(results(rs, addr(LA, lo=20, hi=20))["X"]["result"], "applies")  # exemption impossible
        e = results(rs, addr(LA, lo=2, hi=2))["X"]
        self.assertEqual(e["result"], "unknown")
        self.assertEqual(e["missing_facts"], ["owner_occupied"])
        rs = [rule("X", "CA", exempt={"field": "units", "op": ">=", "value": 2})]
        self.assertEqual(results(rs, addr(LA)), {})

    def test_category_ordering(self):
        rs = [rule("B", "CA", cat="algorithmic_rent_setting"), rule("A", "CA", cat="security_deposits"),
              rule("C", "CA", cat="rent_increase_limits")]
        self.assertEqual([e["team_rule_id"] for e in Engine(rs).lookup(addr(LA), AS_OF)], ["C", "A", "B"])


class Precedence(unittest.TestCase):
    def rules(self, local_covers):
        return [rule("CA-RENT-01", "CA", cat="rent_increase_limits", yields_to=["LA-RENT-01"]),
                rule("LA-RENT-01", "Los Angeles, CA", cat="rent_increase_limits", covers=local_covers)]

    def test_superseded_when_local_applies(self):
        r = results(self.rules(PRE_1978), addr(LA, 1962))
        self.assertEqual(r["CA-RENT-01"]["result"], "superseded")
        self.assertEqual(r["CA-RENT-01"]["superseded_by"], "LA-RENT-01")
        self.assertIn("governs", r["CA-RENT-01"]["explanation"])
        self.assertEqual(r["LA-RENT-01"]["result"], "applies")

    def test_unknown_when_local_unknown(self):
        r = results(self.rules(PRE_1978), addr(LA, 1978))
        self.assertEqual(r["CA-RENT-01"]["result"], "unknown")
        self.assertEqual(r["CA-RENT-01"]["missing_facts"], ["certificate_of_occupancy"])
        self.assertEqual(r["LA-RENT-01"]["result"], "unknown")

    def test_applies_when_local_does_not_cover(self):
        r = results(self.rules(PRE_1978), addr(LA, 1990))
        self.assertEqual(r["CA-RENT-01"]["result"], "applies")
        self.assertNotIn("LA-RENT-01", r)

    def test_applies_when_local_not_yet_effective(self):
        rs = [rule("CA-ALG-01", "CA", yields_to=["LA-ALG-01"]), rule("LA-ALG-01", "Los Angeles, CA", eff="2027-01-01")]
        r = results(rs, addr(LA))
        self.assertEqual(r["CA-ALG-01"]["result"], "applies")
        self.assertEqual(r["LA-ALG-01"]["result"], "not_yet_effective")

    def test_yield_target_outside_stack_ignored(self):
        rs = self.rules(None)
        r = results(rs, addr(["CA", "San Diego, CA"]))
        self.assertEqual(r["CA-RENT-01"]["result"], "applies")


class StateMunicipalityModifier(unittest.TestCase):
    """A state law limiting what cities may regulate (e.g. buildings with a certificate of occupancy
    in the last 30 years are exempt from local rent control)."""
    NEW = {"field": "certificate_of_occupancy", "op": ">", "value": {"as_of_minus_years": 30}}  # > 1996-10-01

    def rules(self, **mod):
        m = dict(status="in_force", eff="2020-01-01")
        m.update(mod)
        return [rule("NJ-RENT-01", "NJ", subject="municipality", covers=self.NEW, cat="rent_increase_limits",
                     status=m["status"], eff=m["eff"]),
                rule("JC-RENT-01", "Jersey City, NJ", cat="rent_increase_limits")]

    def test_new_building_suppressed(self):
        self.assertEqual(results(self.rules(), addr(JC, 2010)), {})

    def test_old_building_applies(self):
        r = results(self.rules(), addr(JC, 1950))
        self.assertEqual(r["JC-RENT-01"]["result"], "applies")
        self.assertNotIn("NJ-RENT-01", r)      # the modifier binds municipalities, never reported

    def test_cutoff_year_or_no_year_unknown(self):
        for y in (1996, None):
            e = results(self.rules(), addr(JC, y))["JC-RENT-01"]
            self.assertEqual(e["result"], "unknown", y)
            self.assertEqual(e["missing_facts"], ["certificate_of_occupancy"])
            self.assertIn("cite NJ-RENT-01", e["explanation"])

    def test_other_category_unaffected(self):
        rs = self.rules() + [rule("JC-ALG-01", "Jersey City, NJ")]
        self.assertEqual(results(rs, addr(JC, 2010))["JC-ALG-01"]["result"], "applies")

    def test_modifier_not_yet_in_force_ignored(self):
        self.assertEqual(results(self.rules(eff="2027-01-01"), addr(JC, 2010))["JC-RENT-01"]["result"], "applies")
        self.assertEqual(results(self.rules(status="pending"), addr(JC, 2010))["JC-RENT-01"]["result"], "applies")

    # Regression test (bug fixed 2026-10-03).
    def test_not_yet_effective_modifier_takes_effect_after_its_date(self):
        rs = self.rules(status="not_yet_effective", eff="2027-01-01")
        self.assertEqual(results(rs, addr(JC, 2010), date(2027, 7, 2)), {})


class ConflictFlags(unittest.TestCase):
    def rules(self, jc_covers=None):
        return [rule("NJ-ALG-01", "NJ", status="not_yet_effective", eff="2027-07-01",
                     conflicts_with=["JC-ALG-01", "HOB-ALG-01"]),
                rule("JC-ALG-01", "Jersey City, NJ", covers=jc_covers, conflicts_with=["NJ-ALG-01"]),
                rule("HOB-ALG-01", "Hoboken, NJ", conflicts_with=["NJ-ALG-01"])]

    def test_partner_present(self):
        r = results(self.rules(), addr(JC))
        self.assertTrue(r["NJ-ALG-01"]["conflict_flag"])
        self.assertTrue(r["JC-ALG-01"]["conflict_flag"])
        self.assertIn("JC-ALG-01", r["NJ-ALG-01"]["explanation"])
        self.assertEqual(r["NJ-ALG-01"]["result"], "not_yet_effective")

    def test_partner_absent(self):
        r = results(self.rules(), addr(NWK))
        self.assertEqual(set(r), {"NJ-ALG-01"})
        self.assertFalse(r["NJ-ALG-01"]["conflict_flag"])

    def test_partner_in_stack_but_not_covering(self):
        r = results(self.rules(jc_covers={"field": "units", "op": "<=", "value": 1}), addr(JC))
        self.assertEqual(set(r), {"NJ-ALG-01"})
        self.assertFalse(r["NJ-ALG-01"]["conflict_flag"])

    def test_source_conflict_always_flagged(self):
        r = results([rule("CA-DEP-01", "CA", source_conflict=True)], addr(LA))
        self.assertTrue(r["CA-DEP-01"]["conflict_flag"])
        self.assertIn("Sources disagree", r["CA-DEP-01"]["explanation"])


if __name__ == "__main__":
    unittest.main()
