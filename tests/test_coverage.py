"""Three-valued (Kleene) coverage evaluator over interval facts: lexmap/coverage.py."""
from __future__ import annotations

import math
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testutil  # noqa: E402,F401

from lexmap.coverage import Trace, evaluate  # noqa: E402

INF = math.inf
AS_OF = date(2026, 10, 1)


def facts(year=None, lo=2, hi=INF):
    return {"year_built": year, "units_min": lo, "units_max": hi}


def leaf(field, op, value):
    return {"field": field, "op": op, "value": value}


def ev(pred, f, as_of=AS_OF):
    t = Trace()
    return evaluate(pred, f, as_of, t), t


class CertificateOfOccupancyCutoff(unittest.TestCase):
    """LA RSO: certificate of occupancy on or before 1978-10-01.  Guide 4.1: year built is not the
    certificate date, so a building in the cut-off year is unknown."""
    P = leaf("certificate_of_occupancy", "<=", "1978-10-01")

    def test_built_before_cutoff_year_is_true(self):
        self.assertIs(ev(self.P, facts(1962))[0], True)

    def test_built_in_cutoff_year_is_unknown(self):
        r, t = ev(self.P, facts(1978))
        self.assertIsNone(r)
        self.assertEqual(t.missing, ["certificate_of_occupancy"])

    def test_built_after_cutoff_year_is_false(self):
        self.assertIs(ev(self.P, facts(1985))[0], False)

    def test_no_year_is_unknown(self):
        r, t = ev(self.P, facts(None))
        self.assertIsNone(r)
        self.assertEqual(t.missing, ["certificate_of_occupancy"])

    def test_sf_cutoff(self):
        p = leaf("certificate_of_occupancy", "<=", "1979-06-13")
        self.assertIs(ev(p, facts(1978))[0], True)
        self.assertIsNone(ev(p, facts(1979))[0])
        self.assertIs(ev(p, facts(1980))[0], False)

    def test_year_only_value_means_whole_year(self):
        # "on or before 1978" -> through 1978-12-31; "after 1978" -> from 1979
        self.assertIs(ev(leaf("certificate_of_occupancy", "<=", "1978"), facts(1978))[0], True)
        self.assertIs(ev(leaf("certificate_of_occupancy", ">", 1978), facts(1978))[0], False)
        self.assertIs(ev(leaf("certificate_of_occupancy", ">", 1978), facts(1979))[0], True)
        self.assertIs(ev(leaf("certificate_of_occupancy", "<", "1978"), facts(1978))[0], False)
        self.assertIs(ev(leaf("certificate_of_occupancy", ">=", "1978"), facts(1978))[0], True)


class RollingCutoff(unittest.TestCase):
    """AB 1482-style rolling exemption: certificate of occupancy within the last 15 years."""

    def test_co_after_as_of_minus_15(self):
        p = leaf("certificate_of_occupancy", ">", {"as_of_minus_years": 15})   # > 2011-10-01
        self.assertIs(ev(p, facts(2010))[0], False)
        r, t = ev(p, facts(2011))
        self.assertIsNone(r)
        self.assertEqual(t.missing, ["certificate_of_occupancy"])
        self.assertIs(ev(p, facts(2012))[0], True)

    def test_co_on_or_before_as_of_minus_15(self):
        p = leaf("certificate_of_occupancy", "<=", {"as_of_minus_years": 15})
        self.assertIs(ev(p, facts(2010))[0], True)
        self.assertIsNone(ev(p, facts(2011))[0])
        self.assertIs(ev(p, facts(2012))[0], False)

    def test_rolling_moves_with_as_of(self):
        p = leaf("certificate_of_occupancy", ">", {"as_of_minus_years": 15})
        self.assertIs(ev(p, facts(2012), date(2027, 10, 1))[0], None)   # cut-off 2012-10-01
        self.assertIs(ev(p, facts(2012), date(2028, 1, 1))[0], False)   # cut-off 2013-01-01

    def test_rolling_on_year_built_is_year_scalar(self):
        p = leaf("year_built", ">", {"as_of_minus_years": 15})            # > 2011
        self.assertIs(ev(p, facts(2011))[0], False)
        self.assertIs(ev(p, facts(2012))[0], True)

    def test_feb_29_as_of(self):
        p = leaf("certificate_of_occupancy", ">", {"as_of_minus_years": 15})
        self.assertIs(ev(p, facts(2010), date(2028, 2, 29))[0], False)


class UnitsIntervals(unittest.TestCase):
    def test_five_plus_vs_two_or_fewer_is_false(self):
        self.assertIs(ev(leaf("units", "<=", 2), facts(lo=5, hi=INF))[0], False)

    def test_cambridge_4_to_8_vs_four_or_fewer_is_unknown(self):
        r, t = ev(leaf("units", "<=", 4), facts(lo=4, hi=8))
        self.assertIsNone(r)
        self.assertEqual(t.missing, ["units"])

    def test_known_units(self):
        self.assertIs(ev(leaf("units", ">=", 5), facts(lo=20, hi=20))[0], True)
        self.assertIs(ev(leaf("units", "==", 20), facts(lo=20, hi=20))[0], True)
        self.assertIs(ev(leaf("units", "!=", 20), facts(lo=20, hi=20))[0], False)
        self.assertIs(ev(leaf("units", "<", 4), facts(lo=4, hi=8))[0], False)
        self.assertIs(ev(leaf("units", ">", 8), facts(lo=4, hi=8))[0], False)
        self.assertIsNone(ev(leaf("units", ">", 4), facts(lo=4, hi=8))[0])

    def test_missing_units_default_lower_bound_two(self):
        self.assertIs(ev(leaf("units", ">=", 2), {"year_built": None})[0], True)
        self.assertIsNone(ev(leaf("units", ">=", 3), {"year_built": None})[0])

    def test_in_on_units(self):
        p = leaf("units", "in", [2, 3, 4])
        self.assertIs(ev(p, facts(lo=3, hi=3))[0], True)
        self.assertIs(ev(p, facts(lo=6, hi=6))[0], False)
        self.assertIs(ev(p, facts(lo=5, hi=INF))[0], False)
        self.assertIsNone(ev(p, facts(lo=4, hi=8))[0])
        self.assertIsNone(ev(p, facts(lo=2, hi=INF))[0])


class PropertyType(unittest.TestCase):
    def test_duplex(self):
        p = leaf("property_type", "==", "duplex")
        self.assertIs(ev(p, facts(lo=2, hi=2))[0], True)
        self.assertIs(ev(p, facts(lo=5, hi=INF))[0], False)
        self.assertIsNone(ev(p, facts(lo=2, hi=INF))[0])

    def test_single_family_never_for_multifamily_sample(self):
        self.assertIs(ev(leaf("property_type", "==", "single_family"), facts(lo=2, hi=INF))[0], False)
        self.assertIs(ev(leaf("property_type", "==", "single-family"), facts(lo=4, hi=8))[0], False)
        self.assertIs(ev(leaf("property_type", "!=", "single family"), facts(lo=2, hi=INF))[0], True)

    def test_condo_false_multifamily_true(self):
        self.assertIs(ev(leaf("property_type", "==", "condo"), facts())[0], False)
        self.assertIs(ev(leaf("property_type", "==", "condominium"), facts())[0], False)
        self.assertIs(ev(leaf("property_type", "==", "multifamily"), facts())[0], True)
        self.assertIs(ev(leaf("property_type", "!=", "multifamily"), facts())[0], False)

    def test_in_list(self):
        self.assertIs(ev(leaf("property_type", "in", ["single_family", "condo"]), facts())[0], False)
        self.assertIs(ev(leaf("property_type", "in", ["condo", "multifamily"]), facts())[0], True)
        self.assertIsNone(ev(leaf("property_type", "in", ["condo", "duplex"]), facts(lo=2, hi=INF))[0])

    def test_unrecognised_type_is_unknown(self):
        self.assertIsNone(ev(leaf("property_type", "==", "dormitory"), facts())[0])


class KleeneLogic(unittest.TestCase):
    T_ = leaf("units", ">=", 2)                       # true for every building
    F_ = leaf("units", "<=", 1)                       # false for every building
    U_ = leaf("owner_occupied", "==", True)           # always unknown

    def test_none_predicate_is_true(self):
        self.assertIs(evaluate(None, facts(), AS_OF), True)

    def test_owner_fields_unknown(self):
        for f in ("owner_occupied", "owner_type", "owner_property_count", "owner_unit_count", "other_fact"):
            r, t = ev(leaf(f, "==", 1), facts(1950, 5, 5))
            self.assertIsNone(r, f)
            self.assertEqual(t.missing, [f])

    def test_all(self):
        F = facts()
        self.assertIs(evaluate({"all": [self.T_, self.T_]}, F, AS_OF), True)
        self.assertIs(evaluate({"all": [self.T_, self.F_]}, F, AS_OF), False)
        self.assertIsNone(evaluate({"all": [self.T_, self.U_]}, F, AS_OF))
        self.assertIs(evaluate({"all": [self.U_, self.F_]}, F, AS_OF), False)

    def test_any(self):
        F = facts()
        self.assertIs(evaluate({"any": [self.F_, self.T_]}, F, AS_OF), True)
        self.assertIs(evaluate({"any": [self.F_, self.F_]}, F, AS_OF), False)
        self.assertIsNone(evaluate({"any": [self.F_, self.U_]}, F, AS_OF))
        self.assertIs(evaluate({"any": [self.U_, self.T_]}, F, AS_OF), True)

    def test_not(self):
        F = facts()
        self.assertIs(evaluate({"not": self.T_}, F, AS_OF), False)
        self.assertIs(evaluate({"not": self.F_}, F, AS_OF), True)
        self.assertIsNone(evaluate({"not": self.U_}, F, AS_OF))
        self.assertIs(evaluate({"not": {"all": [self.U_, self.F_]}}, F, AS_OF), True)


class IrrelevantUnknowns(unittest.TestCase):
    """An unknown leaf that cannot change the outcome is not a missing fact."""

    def test_false_all_does_not_report_other_unknown(self):
        p = {"all": [leaf("units", "<=", 2), leaf("owner_occupied", "==", True)]}
        r, t = ev(p, facts(lo=5, hi=INF))
        self.assertIs(r, False)
        self.assertEqual(t.missing, [])

    def test_true_any_does_not_report_other_unknown(self):
        p = {"any": [leaf("owner_type", "==", "natural_person"), leaf("units", ">=", 5)]}
        r, t = ev(p, facts(lo=20, hi=20))
        self.assertIs(r, True)
        self.assertEqual(t.missing, [])

    def test_unknown_all_reports_only_relevant_fields(self):
        p = {"all": [leaf("units", "<=", 4), leaf("owner_occupied", "==", True)]}
        r, t = ev(p, facts(lo=4, hi=8))
        self.assertIsNone(r)
        self.assertEqual(t.missing, ["units", "owner_occupied"])

    def test_nested_resolved_group_inside_unknown_group(self):
        # any[ all[F, U_owner] (= F), U_units ] -> unknown, only `units` is missing
        p = {"any": [{"all": [leaf("units", "<=", 1), leaf("owner_occupied", "==", True)]},
                     leaf("units", "<=", 4)]}
        r, t = ev(p, facts(lo=4, hi=8))
        self.assertIsNone(r)
        self.assertEqual(t.missing, ["units"])

    def test_outer_resolution_marks_nested_unknowns(self):
        # all[ any[U_owner, U_units], F ] -> False; nothing missing
        p = {"all": [{"any": [leaf("owner_occupied", "==", True), leaf("units", "<=", 4)]},
                     leaf("certificate_of_occupancy", "<=", "1978-10-01")]}
        r, t = ev(p, facts(1990, 4, 8))
        self.assertIs(r, False)
        self.assertEqual(t.missing, [])


if __name__ == "__main__":
    unittest.main()
