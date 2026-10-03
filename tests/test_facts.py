"""Building facts (units interval, year) derived from the sample CSV: lexmap/facts.py."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _testutil  # noqa: E402,F401

from lexmap.facts import derive_units, facts_for, units_label  # noqa: E402

INF = math.inf


def nj(desc, units=""):
    return {"state": "NJ", "use_code": "4C", "use_description": desc, "units": units, "year_built": ""}


def units_of(row):
    lo, hi, _ = derive_units(row)
    return lo, hi


class NewJerseyClass4C(unittest.TestCase):
    def test_class_4c_is_at_least_five_units(self):
        for desc in ("", "4SB", "3S.F.", "Apartments (class 4C)", "1SCB"):
            self.assertEqual(units_of(nj(desc)), (5, INF), desc)

    def test_description_unit_counts(self):
        self.assertEqual(units_of(nj("6B-20U-G")), (20, INF))
        self.assertEqual(units_of(nj("5B-1OU")), (10, INF))           # letter O typed for zero
        self.assertEqual(units_of(nj("3B-7U/4B-24U-G")), (24, INF))
        self.assertEqual(units_of(nj("10S-B-A-151U-HE")), (151, INF))
        self.assertEqual(units_of(nj("2,4B-16U-H-X")), (16, INF))

    def test_story_codes_are_not_units(self):
        self.assertEqual(units_of(nj("2SF2UG")), (5, INF))
        self.assertEqual(units_of(nj("3SB2UG")), (5, INF))
        self.assertEqual(units_of(nj("3SF3UG")), (5, INF))

    def test_small_description_count_never_lowers_bound(self):
        self.assertEqual(units_of(nj("2F-4U/2F-2U")), (5, INF))
        self.assertEqual(units_of(nj("4B-5U-H-BA")), (5, INF))

    def test_units_column_wins(self):
        self.assertEqual(units_of(nj("6B-20U-G", units="12")), (12, 12))

    def test_other_nj_codes_not_bumped(self):
        self.assertEqual(units_of({"state": "NJ", "use_code": "2", "use_description": "6B-20U-G", "units": ""}), (2, INF))


class DescriptionRules(unittest.TestCase):
    def test_boston_apt_7_30(self):
        row = {"state": "MA", "use_code": "A/112", "use_description": "APT 7-30 UNITS", "units": ""}
        self.assertEqual(units_of(row), (7, 30))

    def test_boston_apartment_land_use_lower_bound(self):
        row = {"state": "MA", "use_code": "A/125", "use_description": "SUBSD HOUSING S- 8", "units": ""}
        self.assertEqual(units_of(row), (4, INF))

    def test_cambridge_classes(self):
        self.assertEqual(units_of({"state": "MA", "use_code": "111", "use_description": "4-8-UNIT-APT", "units": ""}), (4, 8))
        self.assertEqual(units_of({"state": "MA", "use_code": "112", "use_description": ">8-UNIT-APT", "units": ""}), (9, INF))
        self.assertEqual(units_of({"state": "MA", "use_code": "112", "use_description": "MXD >8-UNIT-APT", "units": ""}), (9, INF))

    def test_la_and_sf_codes(self):
        self.assertEqual(units_of({"state": "CA", "use_code": "0500", "use_description": "Five or more apartments", "units": ""}), (5, INF))
        self.assertEqual(units_of({"state": "CA", "use_code": "A", "use_description": "Apartment 5 to 14 Units", "units": ""}), (5, 14))

    def test_unknown_defaults_to_multifamily_lower_bound(self):
        self.assertEqual(units_of({"state": "CA", "use_code": "", "use_description": "", "units": ""}), (2, INF))
        self.assertEqual(units_of({"state": "CA", "use_code": "", "use_description": "", "units": "0"}), (2, INF))


class Years(unittest.TestCase):
    def row(self, y):
        return {"state": "CA", "use_code": "", "use_description": "", "units": "8", "year_built": y}

    def test_valid_year(self):
        f = facts_for(self.row("1962"))
        self.assertEqual(f["year_built"], 1962)
        self.assertIn("assessor", f["year_source"])
        self.assertEqual(facts_for(self.row("1962.0"))["year_built"], 1962)

    def test_out_of_range_year_is_none(self):
        for y in ("0", "1699", "2031", "9999", "", "n/a"):
            f = facts_for(self.row(y))
            self.assertIsNone(f["year_built"], y)
            self.assertEqual(f["year_source"], "not in the data")

    def test_boundaries_kept(self):
        self.assertEqual(facts_for(self.row("1700"))["year_built"], 1700)
        self.assertEqual(facts_for(self.row("2030"))["year_built"], 2030)

    def test_flags_and_labels(self):
        f = facts_for(nj("5B-26U-H-CO-OP"))
        self.assertIn("co-op", f["flags"])
        self.assertEqual(units_label(f), "26+ units (derived)")
        self.assertEqual(units_label({"units_min": 8, "units_max": 8}), "8 units")
        self.assertEqual(units_label({"units_min": 4, "units_max": 8}), "4-8 units (derived)")


if __name__ == "__main__":
    unittest.main()
