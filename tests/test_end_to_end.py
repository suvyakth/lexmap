"""Checks on the committed outputs (submission/*.json, build/*.json) and offline reproducibility.

Nothing here calls the LLM or the Census geocoder: rules come from build/rules_full.json and
jurisdictions from build/geocodes.json.
"""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _testutil import ROOT, load_json  # noqa: E402

from lexmap import config  # noqa: E402


def _addresses():
    with open(ROOT / "data/raw/data/sample_addresses.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class CommittedOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addrs = _addresses()
        cls.ids = sorted(a["address_id"] for a in cls.addrs)
        cls.state = {a["address_id"]: a["state"] for a in cls.addrs}
        cls.geo = load_json("build/geocodes.json")
        cls.city = {a: g["city"] for a, g in cls.geo.items()}
        cls.lookups = load_json("submission/lookups.json")
        cls.changes = load_json("submission/changes.json")
        cls.rules = load_json("submission/rules.json")["rules"]
        cls.by_id = {r["team_rule_id"]: r for r in cls.rules}

    def in_state(self, s):
        return sorted(a for a in self.ids if self.state[a] == s)

    def in_city(self, *cs):
        return sorted(a for a in self.ids if self.city[a] in cs)

    def test_lookups_cover_all_500(self):
        self.assertEqual(self.lookups["as_of"], "2026-10-01")
        self.assertEqual(len(self.ids), 500)
        self.assertEqual(sorted(self.lookups["lookups"]), self.ids)
        self.assertEqual(sorted(self.geo), self.ids)

    def test_lookup_entries_well_formed(self):
        for aid, es in self.lookups["lookups"].items():
            for e in es:
                self.assertEqual(set(e), {"team_rule_id", "result", "explanation", "conflict_flag"})
                self.assertIn(e["result"], config.RESULTS)
                self.assertIn(e["team_rule_id"], self.by_id)
                r = self.by_id[e["team_rule_id"]]
                self.assertIn(r["jurisdiction"], self.geo[aid]["stack"], (aid, r["team_rule_id"]))
                self.assertNotEqual(r["status"], "failed")
                self.assertTrue(e["explanation"])

    def test_t1_all_ca(self):
        self.assertEqual(sorted(self.changes["T1"]["affected_address_ids"]), self.in_state("CA"))
        self.assertEqual(self.changes["T1"]["conflict_flag_address_ids"], [])

    def test_t2_hoboken_and_jersey_city(self):
        self.assertEqual(sorted(self.changes["T2"]["affected_address_ids"]), self.in_city("Hoboken, NJ", "Jersey City, NJ"))
        self.assertEqual(self.changes["T2"]["conflict_flag_address_ids"], [])
        L = self.lookups["lookups"]
        for aid in self.ids:
            got = {e["team_rule_id"] for e in L[aid]} & {"HOB-ALG-01", "JC-ALG-01"}
            want = {"Hoboken, NJ": {"HOB-ALG-01"}, "Jersey City, NJ": {"JC-ALG-01"}}.get(self.city[aid], set())
            self.assertEqual(got, want, aid)

    def test_t3_all_nj_with_hob_jc_conflicts(self):
        self.assertEqual(sorted(self.changes["T3"]["affected_address_ids"]), self.in_state("NJ"))
        self.assertEqual(sorted(self.changes["T3"]["conflict_flag_address_ids"]),
                         self.in_city("Hoboken, NJ", "Jersey City, NJ"))

    def test_t4_all_ma(self):
        self.assertEqual(sorted(self.changes["T4"]["affected_address_ids"]), self.in_state("MA"))
        self.assertEqual(self.changes["T4"]["conflict_flag_address_ids"], [])

    def test_t5_empty(self):
        self.assertEqual(self.changes["T5"]["affected_address_ids"], [])
        self.assertEqual(self.changes["T5"]["conflict_flag_address_ids"], [])
        self.assertEqual(self.by_id["MA-RENT-P1"]["status"], "failed")

    def test_change_test_rule_statuses_at_default_date(self):
        L = self.lookups["lookups"]
        for rid, want, st in (("CA-ALG-01", "applies", "CA"), ("NJ-ALG-01", "not_yet_effective", "NJ"),
                              ("MA-ALG-P1", "pending", "MA"), ("MA-ALG-P2", "pending", "MA")):
            seen = {a: e["result"] for a, es in L.items() for e in es if e["team_rule_id"] == rid}
            self.assertEqual(sorted(seen), self.in_state(st), rid)
            self.assertEqual(set(seen.values()), {want}, rid)

    def test_no_rent_cap_in_massachusetts(self):
        L = self.lookups["lookups"]
        bad = [(a, e["team_rule_id"]) for a in self.in_state("MA") for e in L[a]
               if self.by_id[e["team_rule_id"]]["category"] == "rent_increase_limits"]
        self.assertEqual(bad, [])

    def test_quoted_spans_are_verbatim(self):
        manifest = {}
        with open(ROOT / "data/raw/corpus/corpus_manifest.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                manifest[row["doc_id"]] = row
        cache: dict[str, str] = {}
        for r in self.rules:
            did = r["source_doc_id"]
            if did not in cache:
                corpus = ROOT / "data/raw/corpus/text" / f"{did}.txt"
                supp = ROOT / "data/supplementary" / f"{did}.txt"
                path = corpus if manifest[did]["status"] == "ok" and corpus.exists() else supp
                self.assertTrue(path.exists(), (r["team_rule_id"], did))
                cache[did] = path.read_text(encoding="utf-8")
            text = cache[did]
            self.assertTrue(r["quoted_span"] and len(r["quoted_span"]) >= 20, r["team_rule_id"])
            self.assertIn(r["quoted_span"], text, r["team_rule_id"])
            for s in r.get("supporting_spans") or []:
                self.assertIn(s, text, r["team_rule_id"])

    def test_rules_have_provenance(self):
        self.assertEqual(len(self.by_id), len(self.rules))
        for r in self.rules:
            self.assertTrue(r["source_url"] and r["retrieved_at"], r["team_rule_id"])
            self.assertIn(r["category"], config.CATEGORIES)
            if r["team_rule_id"].rpartition("-")[2].startswith("P"):
                self.assertIn(r["status"], ("pending", "failed"), r["team_rule_id"])


class Reproducibility(unittest.TestCase):
    """Re-running Module B/C offline from build/ artefacts must reproduce the committed submission."""

    @classmethod
    def setUpClass(cls):
        from lexmap import lookup
        cls.lookup = lookup
        cls.rules = lookup.load_rules()
        cls.addrs = lookup.address_records()
        cls.eng = lookup.Engine(cls.rules)

    def test_rules_json_ids_match_build(self):
        sub = load_json("submission/rules.json")["rules"]
        self.assertEqual([r["team_rule_id"] for r in sub], [r["team_rule_id"] for r in self.rules])

    def test_lookups_reproduce(self):
        d = date.fromisoformat(config.DEFAULT_AS_OF)
        full = {a["address_id"]: self.eng.lookup(a, d) for a in self.addrs}
        self.assertEqual(self.lookup.to_submission(full, config.DEFAULT_AS_OF), load_json("submission/lookups.json"))

    def test_python_engine_matches_parity_fixtures(self):
        fx = load_json("tests/parity_fixtures.json")
        for as_of, expected in fx.items():
            d = date.fromisoformat(as_of)
            for a in self.addrs:
                got = [[e["team_rule_id"], e["result"], e["conflict_flag"]] for e in self.eng.lookup(a, d)]
                self.assertEqual(got, expected[a["address_id"]], (as_of, a["address_id"]))

    def test_changes_reproduce(self):
        from lexmap import changes
        out, _ = changes.run(self.rules, self.addrs)
        committed = load_json("submission/changes.json")
        self.assertEqual(sorted(out), sorted(committed))
        for tid, v in committed.items():
            self.assertEqual(out[tid]["affected_address_ids"], v["affected_address_ids"], tid)
            self.assertEqual(out[tid]["conflict_flag_address_ids"], v["conflict_flag_address_ids"], tid)

    def test_t3_flips_on_effective_date(self):
        nj = [a for a in self.addrs if a["row"]["state"] == "NJ"]
        for d, want in ((date(2026, 10, 1), "not_yet_effective"), (date(2027, 6, 30), "not_yet_effective"),
                        (date(2027, 7, 2), "applies")):
            res = {next((e["result"] for e in self.eng.lookup(a, d) if e["team_rule_id"] == "NJ-ALG-01"), None)
                   for a in nj}
            self.assertEqual(res, {want}, d)

    def test_selfcheck_passes(self):
        from lexmap import selfcheck
        rep = selfcheck.run(write=False)
        failed = [c["check"] for c in rep["checks"] if not c["ok"]]
        self.assertEqual(failed, [])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class BrowserEngine(unittest.TestCase):
    def test_parity_and_smoke(self):
        for args in (["tests/parity.js"], ["tests/smoke_app.js", "#A0107@2026-10-01"]):
            p = subprocess.run(["node", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                               timeout=300)
            self.assertEqual(p.returncode, 0, f"node {' '.join(args)}\n{p.stdout}\n{p.stderr}")


if __name__ == "__main__":
    unittest.main()
