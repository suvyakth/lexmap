# Lexmap pre-submission bug hunt (commit 59ff82e)

Read-only review. Harnesses live in the session scratchpad, not in the repo: `gen.py`/`cmp.js` (engine parity), `custom.js` (custom-address flow with a stubbed Census JSONP), `norule.js`, and `clone/` (a `git archive HEAD` export with LF endings, standing in for a Linux clone).
The live site (app.js, engine.js, index.html, data/rules.json, data/meta.json) is byte-identical to HEAD.

## Summary
- **Python engine vs JS engine: no divergence on current data.** I ran 153,153 synthetic (stack, facts, date) cases: all 10 cities plus state-only, 17 build years including None, 11 unit intervals including (1,1) and (1,null), property_type `multifamily`/`null`/absent, and 21 dates including 1979-06-13/14, 2011-10-01, 2027-02-28, 2028-02-29, 2030-01-01/02 and 2032-02-29. Results, explanations, missing_facts and superseded_by were 100% identical. The divergences that exist are latent only (see L1).
- **Clean-clone reproduction works.** `LEXMAP_LLM_BACKEND=cache-only python run.py`, and also with `--extract`, ran on the LF export: 0 live calls, 170 cache hits, 44/44 self-checks. Every output was identical to HEAD apart from CRLF and two timestamps (`meta.json generated_at`, audit-log header). `python -m unittest discover -s tests` gives 129 OK. `node tests/parity.js` gives 2000/2000.
- **README and METHOD_NOTE numbers.** 56 rules, 129 quotes (90 exact + 39 normalised), 96% (3,354/3,491), 3 conflict rules, 487/500 geocoded, 27 NJ ZIP flags, 32 QA corrections, 5 event rules, 44/44, T1–T5 = 250/90/140+90/110/0, 54+13 sources and the 45-address what-if are all **true**. The one false claim is M4 below.
- **Suspected problems that turned out fine:** `renderChanges`/`renderRules` run once, so listeners are not duplicated. Every innerHTML path with external data is escaped (an injected Census place name rendered inert). The JSONP script and callback are cleaned up on success, error and timeout. Out-of-state, no-match and network-error paths give sensible messages. No `undefined`/`NaN` appeared in any scenario.

---

## HIGH (wrong answer shown)

### H1. Los Angeles post-1978 buildings: AB 1482 and the LA rent ordinance both show "unknown" instead of AB 1482 "applies"
- **Location:** rule `LA-RENT-01` coverage_logic, introduced by the QA pass (`lexmap/qa.py`). Evaluated in `lookup.py:_evaluate` (yields_to) and `engine.js:_eval`.
- **Evidence:** `LA-RENT-01.covers = any[certificate_of_occupancy <= 1978-10-01, other_fact "unit is a replacement unit under LAMC Section 151.28"]`. For any building from 1979 on, the `other_fact` branch makes LA-RENT-01 `unknown`. CA-RENT-01 yields to it, so it also becomes `unknown`: "Applies unless the local rule LA-RENT-01 covers this building ... (a building condition not in the data)".
  - In submission/lookups.json: 25 LA addresses have LA-RENT-01 `unknown` (replacement unit) and 23 have CA-RENT-01 `unknown` that should be `applies`. Example: A0437, 2969 San Marino St, built 2004, 20 units.
  - The custom form with LA, 1990, 10 units shows the same result.
  - The QA pass added this clause. With that QA cache entry removed, `covers` is just `certificate_of_occupancy <= "1978-10-01"`.
  - This is the brief's core example (AB 1482 for a post-1978 LA apartment), so a hidden answer key will very likely mark it wrong.
- **Fix:** add a post-QA normalisation step in `reconcile.run`, after `qa.run`. Inside `covers`, drop `other_fact` leaves from an `any` when a sibling leaf uses a real field. Move the text to `exemptions`/`coverage_conditions` and log it in `validation_notes`. This runs after the model call, so no cache key changes; plain `python run.py` regenerates everything. Then run `node tests/parity.js` and the unit tests again.

### H2. Dates before 2024 give legally wrong answers (the date picker allows them back to 2015)
- **Location:** `docs/index.html:56` (`min="2015-01-01"`) and how `effective_date` is used (`lookup.py:350`, `engine.js:229`).
- **Evidence:** several `effective_date` values are amendment dates, not the dates the laws first took effect. JS engine, A0050 (SF, 1986) at 2023-06-01:
  - `CA-RENT-01 not_yet_effective "takes effect 2024-04-01"` (AB 1482 has been in force since 2020-01-01; 2024-04-01 is SB 567).
  - `CA-EVICT-01` gives the same.
  - `CA-DEP-01 "takes effect 2024-07-01"` (§ 1950.5 is decades old; that date is AB 12).
  - `CA-SCREEN-02 "takes effect 2024-01-01"`.
  - The reverse problem also occurs: rules with a null effective_date apply at any past date. A0005 (Berkeley) at 2020-06-01 shows `BERK-ALG-01 applies`, although that is a 2025 ordinance.
- **Fix (cheapest):** set `min="2025-12-31"` on `#asof` (the earliest T-test date). In `boot()`, ignore hash dates before it. Add a hint and a README line: "earlier dates not supported: effective dates record the latest amendment".

---

## MED (misleading)

### M1. A featured example shows "No rule in this category was found in the corpus" when rules exist but exempt the building
- **Location:** `docs/app.js:143` and `noRuleCard` (app.js:168-178), plus the glance row (app.js:157).
- **Evidence:** example chip A0105 (SF, 2019) at 2026-10-01 and 2027-07-02. The rent category is empty because CA-RENT-01 (15-year new-construction exemption) and SF-RENT-01 (post-1979-06-13) both have exempt=TRUE, yet the page says no rule was found. At 2030-01-02, 50 San Diego and 7 SF addresses show the same text after the AB 1482 sunset.
- **Fix:** in `noRuleCard`, list the in-force rules in `addr.stack` for this category that the engine left out. Example: "CA-RENT-01 exists but does not cover this building (exemption: certificate-of-occupancy date after 2011-10-01 — yes, built 2019)". Run `Lexmap.evaluate(r.coverage_logic.exempt, ...)` for the reason. For rules past `end_date`, say "expired <date>". Change the text and the glance cell to "No rule in the corpus covers this building".

### M2. Custom address with building type "not sure": the "Why" text says "(apartment building)" next to "unknown"
- **Location:** `engine.js:169` `describeLeaf` (`have = "apartment building"` for property_type) and the same at `coverage.py:233`.
- **Evidence:** custom Hoboken lookup with no facts gives "property type is one of single family, duplex? unknown (apartment building)". Cambridge and unincorporated CA show the same. In the synthetic run, 37,741 explanations with `property_type: null` mention "apartment building".
- **Fix:** `have = facts.property_type === "multifamily" ? "apartment building" : (facts.property_type ? facts.property_type.replace(/_/g," ") : "property type not given")`. Mirror it in `coverage.py`; Python facts always say multifamily, so parity is unaffected.

### M3. The LA example "built 1978" shows CA-EVICT-01 "unknown" although a local just-cause law covers the building either way
- **Location:** `lookup.py:370-391`, `engine.js:243-257` (yields_to loop).
- **Evidence:** A0107 shows `CA-EVICT-01 unknown`: "Applies unless the local rule LA-EVICT-01 covers this building". LA-EVICT-01 covers built after 1978-10-01 and LA-EVICT-02 covers on or before that date, so one of them must apply and AB 1482's just-cause rule is superseded. 2 lookups are affected; the same pattern affects CA-RENT-01 once H1 is fixed.
- **Fix:** after the loop, if no yielded rule applies, evaluate `{"any": [covers of every yielded rule with no exemption, in force at D]}`. If it is TRUE, return `superseded` with `superseded_by` = the first of them ("LA-EVICT-01 or LA-EVICT-02"). Make the same change in both engines and regenerate the parity fixtures.

### M4. False claim: "confidence capped at 0.75 for flagged conflicts"
- **Location:** README.md:125, the app.js:99 tooltip, `reconcile.py:153`.
- **Evidence:** NJ-ALG-01 has `conflict_flag: true` and `confidence: 0.98`. The cap runs in `_merge` before QA and preemption set the FAIR Act conflict, and it is never applied again.
- **Fix:** at the end of `reconcile.run`, after QA, preemption and re-sourcing: `if r["conflict_flag"]: r["confidence"] = min(r["confidence"], 0.75)`. Confidence is not part of any prompt, so the cache stays valid.

### M5. SF deposit-interest rule vanishes on 2027-02-28 and stays gone
- **Location:** rule `SF-DEP-01` (`end_date 2027-02-28`); `lookup.py:337-339`, `engine.js:220-221` (`end <= as_of` means omitted).
- **Evidence:** the quote is "4.2% for March 1, 2026 – February 28, 2027". That end date is inclusive, but the engine treats it as exclusive, so the rule disappears one day early (A0016 at 2027-02-28 has no SF-DEP-01). The end date is also only the end of a rate period: the SF duty to pay interest on deposits continues. All 80 SF addresses on the "Jul 2, 2027" demo chip show no SF deposit rule.
- **Fix:** set `end_date` to null for SF-DEP-01 (only the key_value rate is period-bound) in a post-QA override. Otherwise, document `end_date` as exclusive and make the extractor store the day after a "through" date. At minimum, compare `end < as_of` for rate-period rules.

### M6. Corpus gaps are not shown on the address page (Newark and Hoboken rent)
- **Location:** `docs/app.js` `renderAddress`/`glance`. `gaps.json` is used only on the Rules tab (app.js:411).
- **Evidence:** Newark A0249 and Hoboken A0087 show only "Anti-Eviction Act: rent increases must not be unconscionable" for rent. Both cities have local rent-control ordinances that are not in the corpus (`gaps.json` lists `rent_increase_limits` for both). Nothing on the address page says so, so a reader concludes there is no local rent control.
- **Fix:** in `glance` and in each category section, if `D.gaps[city]` includes the category, add a muted line: "<City> has no <category> text in the corpus; local rules may exist (see Gaps)".

### M7. Cache-only runs degrade silently: a missing cache entry still exits 0 and reports 44/44
- **Location:** `qa.py:96-101`, `reconcile.py:51`, `resource.py:~85`, `explain.py:38`, and the `extract.py` try/excepts that swallow `LLMError`.
- **Evidence:** in the scratch clone I removed one QA cache file (LA rent) and ran `LEXMAP_LLM_BACKEND=cache-only python run.py`. It exited 0 with "44/44 checks passed", and LA-RENT-01 changed (`qa.issues = ["QA call failed: No LLM backend available ..."]`). A judge with an incomplete cache would silently get different outputs. Today's cache is complete, so the shipped repo is unaffected.
- **Fix:** add `_stats["misses"]` in `llm.complete` before raising. In `run.py pipeline()`, `if llm.stats().get("misses"): print(...); return 2`. Or re-raise `LLMError` when `llm.backend() == "cache-only"`.

---

## LOW (polish)

| # | Location | Evidence | Fix |
|---|---|---|---|
| L1 | engine.js vs coverage.py (latent) | (a) `exempt: {}` gives Python `ex=False` (applies) but JS `unknown` with the text "undefined undefined undefined? unknown". Checked with a synthetic rule. (b) `minusYears` always clamps Feb 29 to Feb 28, while Python keeps Feb 29 when the target year is a leap year (explanation text differs for n divisible by 4). (c) Python raises TypeError if facts carry `units_min/units_max = None` (`_interval`). None of these occur with the current data. | JS: `if (p == null \|\| (typeof p === "object" && !Object.keys(p).length))` handled like Python, and `cl.exempt && Object.keys(cl.exempt).length`. minusYears: clamp only if the target year is not a leap year. Python: `facts.get("units_min") or 2`, `facts.get("units_max") or INF`. |
| L2 | `whatif.py:94` and `app.js:351` | `docs/data/changes.json` has `"document": "data\\whatif\\fictional_cambridge_ordinance.txt"` (written on Windows), and `split(/[\/]/)` does not split on a backslash, so the full Windows path shows. A Linux rerun writes `/`, so the output is not byte-reproducible. | `str(path.relative_to(config.ROOT).as_posix())`; regex `/[\\/]/`. |
| L3 | `app.js:160` glance links `href="#cat-…"` | Clicking a category link replaces `#A0016@2026-10-01` in the address bar; a reload or shared link then falls back to A0016 at the default date. | Use `data-cat` with `scrollIntoView` and `preventDefault`. |
| L4 | `app.js:258/365/489` | The date-chip highlight is not updated when the date comes from the hash or from the Changes-tab jumps (T1/T3/what-if). | Call the chip-toggle code (move it out of `rerender`) after setting `#asof`. |
| L5 | `app.js:318` and `setHash` | A custom lookup never updates the hash, so the URL still points at the previous sample. After a failed custom lookup `current` is unchanged, so changing the date replaces the error with the old address. | Clear `current`/hash on error; for custom lookups clear the hash or encode `#q=`. |
| L6 | `app.js:489` | `#A9999` leaves the result panel empty. | Fall back to `showSample("A0016")` when the id is unknown. |
| L7 | `engine.js:143`, `facts.py:90` | "1 units"; a custom apartment with no unit count shows "2+ units" while the source says "not provided: treated as unknown". | Pluralise; show "2+ (apartment)". |
| L8 | `app.js:212` | `facts.flags` (27 "affordable/subsidised", 2 "co-op") is never displayed; only geocoder flags are. SF-SCREEN-01 and BOS-SCREEN-01 stay "unknown" even for those buildings. | Concatenate `a.facts.flags` into `meta.flags`. |
| L9 | `app.js:157` | The Boston/Cambridge rent glance says "No rule found in the corpus" while the card below cites M.G.L. c. 40P (a state ban on rent control) and the struck ballot question. | Show the c. 40P line in the glance row. |
| L10 | `app.js:342-343`, `style.css .kv` | `JSON.stringify(details)` is a 76-character unbreakable string that overflows a 360px phone. | `.kv { overflow-wrap: anywhere }`, or JSON with spaces. |
| L11 | `app.js` ES mode | Explanations, "+N more", "rule(s)" and the Changes/Rules/Method tabs stay in English. | Note it, or translate the fixed strings. |
| L12 | Glance (app.js:161) | The conflict flag is not shown in the at-a-glance row (Hoboken/JC algorithmic rows). | Append ⚑ when `main.conflict_flag`. |
| L13 | `extract.py:_prune` | The comment says it "never broadens", but pruning an invalid `exempt` branch to None removes an exemption, which broadens coverage. | For `exempt`, keep the rule but flag it in validation_notes, or set `scope` for review. |
| L14 | Reproducibility | A run rewrites tracked files with new timestamps (`docs/data/meta.json`, audit-log header, `tests/parity_fixtures.json` mtime) and, on Windows, CRLF working copies. | Use a fixed `generated_at` (corpus date), or document that diffs are timestamp-only. |
| L15 | Python version | `str.removeprefix` (`corpus.py:40`) needs Python 3.9 or later; the README does not say so. | Add "Python ≥ 3.9" to Run it. |
| L16 | Docs nits | `corpus.py` docstring says "55 corpus files" (there are 54). The Method tab says "2× reconciled and reviewed" but there are 3 passes (reconcile, QA, re-source). `run.py` calls `sys.stdout.reconfigure` without a guard (fails if stdout is not a TextIOWrapper, e.g. some IDE runners). | Fix the text; `if hasattr(sys.stdout, "reconfigure")`. |

## Linux/Mac checklist (item 5)
- Paths use `pathlib`; the audit log normalises `\` to `/`; `.gitattributes` sets `* text=auto eol=lf`; all files are read with `read_text`/`newline=""`, so CRLF is harmless. Prompt hashes match from an LF checkout (proved by 0 misses).
- Manifest files are lower-case, and doc ids match the `text/` filenames exactly, so there is no case-sensitivity problem.
- Node tests are skipped if `node` is missing (`test_end_to_end.py:185`).
- The only Windows artefact is L2 (the backslash path in the what-if JSON).
