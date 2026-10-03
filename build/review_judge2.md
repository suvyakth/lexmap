# Lexmap: second strict judge review (RealPage "Rental Housing Law Navigator")

Reviewed 2026-10-04 against commit `59ff82e` (clean working tree). This was a read-only review: no installs, no model calls, no `run.py` (it can fall through to a live model call on a cache miss). I ran `python -m unittest discover -s tests` (129 OK) and `node tests/parity.js` (2000/2000 identical), and I used in-memory engine calls to check dates. Every number below was recomputed from `submission/*`, `build/*` and the corpus.

Inputs: brief `file2.pdf` (pypdf), `data/raw/PARTICIPANT_GUIDE.md`, `submission/*`, `build/*`, `lexmap/*.py`, `docs/*`, README, METHOD_NOTE, VIDEO_SCRIPTS, SUBMISSION_CHECKLIST. I formed my view first and read `build/review_judge.md` and `build/review_legal.md` last.

**Caveat on the auto-scored lines.** The pack has no `score.py` and no dev key, so they are estimates. They rest on one structural clue: 13 jurisdictions × 6 categories = 78 cells, and 58 rules + 19 no-rule findings = 77. The key is therefore roughly one record per (jurisdiction, category) cell, and it is matched by jurisdiction + category + citation.

---

## 1. Predicted score

| Rubric line | Pts | Predicted | Range | Main reasons |
|---|---|---|---|---|
| Extraction accuracy (auto) | 25 | **16** | 13–19 | See 1.1 |
| Address coverage (auto) | 20 | **13** | 11–15 | See 1.2 |
| Citations (auto) | 15 | **14** | 13–14.5 | 3,354 of 3,491 `applies` answers (96.1%) quote official corpus text. I re-verified that all 51 official primary quotes are exact raw substrings (LF endings, byte-identical to the starter pack). The other 137 answers use pages fetched into `data/supplementary/`, which the scorer's corpus will not contain: HOB-ALG-01 ×40, JC-ALG-01 ×50, LA-DEP-01 ×47. These cannot be re-sourced: D041 has only a table-of-contents heading for deposit interest. |
| Change tracking (auto) | 15 | **12.5** | 12–13 | T1 250/250 CA; T2 90 with 0 in Newark; T3 140 + 90 conflict flags (JC + Hoboken only); T4 110 MA, all `pending`; T5 empty, and no MA rent cap anywhere. **No `T6` key in `changes.json`**, which is worth about 2.5 points. |
| Plain language & usability (judges, demo) | 10 | **7.5** | 6.5–8.5 | See 1.3. Assumes the three videos are recorded as scripted. Without them, the demo-judged lines collapse. |
| Responsible design (judges) | 10 | **8.5** | 7.5–9 | See 1.4 |
| Scalability path (judges) | 5 | **4** | 3.5–4.5 | Pipeline is jurisdiction-agnostic. The what-if path works on unseen text (rehearsed: 2027-03-01, 45 addresses). A new city still needs hand-edited tables in `config.py` and `docs/app.js`, and the README now says so honestly. |
| **Total** | 100 | **≈ 75.5** | 68–82 | Up from the earlier review's ≈ 72. The fixes in §2 removed the largest false-positive sources. |

### 1.1 Extraction: 56 rules over 12 jurisdictions; Newark has none

**Likely matched (about 43–46 of 58).** All 6 CA state cells; NJ eviction, deposit, fee, screening and algorithmic; MA c.40P, §15B (deposit and fees), §87DDD½, c.151B, S.2983, H.5222, IP 25-21 (failed); SF ×5; LA RSO, JCO and deposit; SD just cause and algorithmic; Berkeley ×6; Santa Ana ×3; JC rent and algorithmic; Hoboken algorithmic; Boston and Cambridge screening.

**Dates verified correct** in the corpus: NJ-SCREEN-01 2022-01-01, NJ-FEE-01 2026-05-01, NJ-ALG-01 2027-07-01, CA-ALG-01 2026-01-01, CA-DEP-01 2024-07-01, SF-ALG-01 2024-10-14, SA-* 2021-11-19, SA-ALG-01 2026-04-02.

**Likely losses:**
- **Rules probably in the key but absent.** These are worth roughly 4–6 points of 25.
  - Not extractable (link-only, check-terms): Newark rent control, Hoboken rent control, SD source of income, MA CORI (D056 returned 403).
  - **Rejected by the extraction prompt although the corpus has the text:**
    - Boston Housing Stability Notification Act, from two official docs (D013, D014).
    - Cambridge ch. 8.71 (D031).
    - M.G.L. c.186 §§ 11, 12, 18, 31 (D050, D051, D053, D058). These produced 0 candidates (`build/candidates.json`).

    The organisers put 7 eviction-procedure documents into a 54-document corpus. That is a strong hint the key holds at least some of them under `just_cause_eviction`.
- **Null dates where the corpus or the brief has one.**
  - BERK-ALG-01: D002 says "effective January 2026"; the guide §9 says 2026-03-01.
  - SD-ALG-01: D002 says "effective June 2025", and the brief says Jun 2025.
  - LA-RENT-01: "Effective February 2, 2026" appears in D041/D042, and guide §9 makes it an open question.
- **Citation forms that differ from the brief's table.**
  - NJ-FEE-01 cites `N.J.S.A. 46:8-18.1`, where the brief has "P.L.2025, c.405".
  - CA-ALG-01 cites `Cal. Bus. & Prof. Code § 16729`, where the brief has "AB 325 / SB 763".
  - HOB-ALG-01 cites `ch. 158-2`, where the brief has "ch. 158, Art. II".
  - SF-DEP-01's citation is a page title ("San Francisco Rent Board security deposit interest rate").
  - CA-SCREEN-01's citation is a description ("California Civil Rights Council regulations on use of criminal history in housing").
- **Possible false positives** that cost precision:
  - NJ-RENT-02: the key may hold "NJ: no statewide cap" as a no-rule finding.
  - Second rules in single cells: CA-SCREEN-01/02, LA-EVICT-01/02, MA-FEE-01/02, BOS-SCREEN-01/02.
  - Event-scope records: BERK-EVICT-02, CA-EVICT-02/03, LA-EVICT-03, NJ-EVICT-02.
- **No-rule findings.** About 17–18 of 19 are handled correctly: there is no in-force rule in MA just-cause, Boston/Cambridge rent, or Newark algorithmic, among others.

### 1.2 Address coverage: 5,236 rows

Result counts: applies 3,491 · unknown 490 · superseded 305 · NYE 140 · pending 220.

**Correct.** Geocoding is right for all 500 addresses:
- 487 Census matches.
- 13 mailing-city fallbacks, all in single-city postal areas.
- A0009 is now Cambridge.
- City counts match the guide exactly (80/80/50/40/50/40/50/60/50).
- Cut-off years give `unknown`.
- Berkeley CA-EVICT-01 is now `superseded` ×40.
- A0227 now uses 93 units.

**Losses:**
1. **Missing local rent control.** Newark and Hoboken have none (90 addresses, double penalty if the key has these rules).
2. **Missing MA eviction-procedure rules** (110 MA addresses, double penalty if keyed).
3. **Post-1978 Los Angeles buildings.** For all 29 of them, the `other_fact` "replacement unit under LAMC 151.28" in LA-RENT-01 `covers.any` makes LA-RENT-01 `unknown`. That in turn makes CA-RENT-01 `unknown` through `yielded_unknown`. A human key almost certainly omits RSO for those buildings and says CA-RENT-01 `applies` where the building is more than 15 years old, e.g. A0023 (built 1987).
4. **San Diego `unknown`s.** The `unknown` rows on SD (CA-RENT/EVICT ×50, SD-EVICT-01 ×50) are defensible because SD has no year built. They earn partial credit only.

### 1.3 Plain language & usability (code read; live site not re-crawled)

**Strong:**
- At-a-glance table per address, which mirrors the brief's mock-up.
- EN/ES summaries for all 56 rules, number-guarded.
- Evidence-backed no-rule cards.
- Date chips for T1/T3.
- Change-test tab; custom-address form that now defaults to "not sure".

**Weak:**
- **Mechanical explanations in `lookups.json`,** e.g. "Exemption cannot apply: number of units exactly 2? no (5+ units); number of units exactly 1? no (5+ units)".
- **CA-DEP-01 says only "Statewide California rule."** The brief's own illustrative output for this rule is "small-landlord exception does not apply at 20 units". All 250 CA rows are 5+ units, so the evaluator could say exactly that if the exception were encoded.
- **The date slider gives wrong answers for amended statutes (new finding).** The engine treats an *amendment's* operative date as the rule's start date. On the demo's own "Dec 31, 2025" chip:
  - CA-FEE-01 (§1950.6, in force since 1998, amended eff. 2026-01-01) shows **`not_yet_effective`** for every CA address.
  - SF-DEP-01 shows NYE (2026-03-01 is just the start of a rate period).
  - Before 2024-04-01, AB 1482's rent cap and just cause (CA-RENT-01 and CA-EVICT-01, in force since 2020) show NYE.
  - CA-SCREEN-02 shows NYE before 2024-01-01.

  I reproduced this in memory for A0050. It is invisible to the auto-scorer, which uses 2026-10-01 and CA-ALG-01 only for T1. A judge who clicks the T1 "before" chip will see it.

### 1.4 Responsible design

**Strong:**
- Verbatim-quote verification.
- `unknown` that names the missing fact.
- Enacted, NYE, pending and failed are kept separate.
- Conflict flags cut from 14 rules to the 3 genuine ones (FAIR Act vs JC/Hoboken).
- A secondary-source caveat in every affected explanation.
- No hand-coded skip list (`SKIP_DOCS = {}`).
- Event-only rules held out of `lookups.json`.
- Cached, hashed model calls.
- "Not legal advice" on the site banner.

**Gaps:**
- **CLI output has no "Not legal advice" line.** `python run.py --address …` and `whatif` print none (grep finds no "advice" in `run.py` or `lexmap/whatif.py`). The guide says "every interface".
- **The QA corrections are not in the submission.** The 32 corrections live only in `build/rules_full.json` (`qa`). They are absent from `submission/rules.json` provenance and from `submission/audit_log.jsonl`.
- **The audit log covers 71 of 173 cached model calls.** Only extraction is logged; reconcile, QA, re-source and explain calls are missing.
- **Low-confidence answers are not flagged for review.** The brief asks for this; only conflicts are flagged.
- **Only 1 of the guide §9's 4 open questions is surfaced** (the FAIR Act). Berkeley's date, LA RSO's date and the CA fee figure are not.

---

## 2. Earlier findings: fixed vs still open

### From `build/review_judge.md`

| # | Finding | Status |
|---|---|---|
| 1 | D078 hand-skipped; SF Fair Chance missing | **Fixed.** `SKIP_DOCS = {}`; SF-SCREEN-01 is `unknown` ×80. |
| 2 | T6 not first-class; NYE evaluated before coverage | **Partly fixed.** The drop-in flow exists (`data/hour16/`, T6 in `changes.py`), and coverage is now evaluated before status (what-if gives 45, not 49). **Still open:** no organiser T6 in `changes.json`, and the `lookup.py` docstring still lists pending/NYE before coverage. |
| 3 | Special-subset rows (NJ-EVICT-02, BOS-SCREEN-01) | **Mostly fixed.** NJ-EVICT-02 is event-scope and omitted. BOS-SCREEN-01 is deliberately kept as `unknown` ×60, which is acceptable. |
| 4 | A0009 placed in Boston | **Fixed** (house-number check; now Cambridge). |
| 5 | `applies_only_in` + event scope | **Fixed.** §1947.9 is SF-only and event; 5 event rules are omitted. |
| 6 | Re-source secondary quotes | **Fixed as far as the corpus allows** (91% → 96%). LA-DEP-01, HOB and JC have no official text. |
| 7 | Citation canonicaliser | **Partly fixed.** Fixed: NJ-DEP-01 46:8-21.2, §87DDD½, CA-ALG-01 tail, Berkeley ch. 13.76 / §13.76.110(A). **Open:** HOB ch. 158-2, SF-DEP-01 and CA-SCREEN-01 non-citations, and the bill aliases (AB 325, P.L.2025 c.405) are missing from `citation`. |
| 8 | Dates from secondary sources; open-questions panel | **Panel fixed. Dates open.** SD-ALG-01 and BERK-ALG-01 are still null, and the panel lists only flagged rules (FAIR Act). |
| 9 | Manual capture of D056 / Newark / Hoboken | **Open** (the user's decision; documented as gaps). |
| 10 | At-a-glance, no-rule cards, plain why-lines, custom-form defaults | **Fixed** for the at-a-glance table, no-rule cards and custom-form defaults. Why-lines in `lookups.json` are still templated. |
| 11 | Conflict-flag hygiene; `needs_review` | **Hygiene fixed (3 rules); `needs_review` open.** |
| 12 | README scores block, id-alignment note, verbatim wording | **Fixed** in README. CHECKLIST still says "character-for-character" (minor). |
| — | Red flag: test-shaped ids | **Fixed** (explained in README). |
| — | Red flag: over-precise confidence | **Fixed.** README labels confidence model-reported and uncalibrated. NJ-ALG-01 still shows 0.98 while flagged (see §4). |

### From `build/review_legal.md`

| # | Finding | Status |
|---|---|---|
| 1–3 | CA-EVICT-03, CA-EVICT-02, LA-EVICT-03 reported as `applies` statewide or citywide | **Fixed** (event scope; §1947.9 is SF-only) |
| 4 | Spurious conflict flags | **Fixed** for the spurious ones. **Open:** the guide §9 items (BERK-ALG-01, LA-RENT-01, CA-FEE-01) are still unflagged. |
| 5 | Boston HSNA missing | **Open** (D013/D014 still give 0 candidates) |
| 6 | Cambridge 8.71 missing | **Open** |
| 7 | MA c.186 §§ 11/12/18/31 missing | **Open** |
| 8 | SF Fair Chance missing | **Fixed** |
| 9 | A0009 | **Fixed** |
| 10 | Berkeley CA-EVICT-01 should be superseded | **Fixed** (superseded ×40) |
| 11 | BERK-ALG-01 date | **Open** |
| 12 | LA-RENT-01 date / key value | **Date open.** Its key_value saying "current percentage not stated" is in fact right: the 3% in D042 is for 2025-07 to 2026-06, which has expired. |
| 13 | SD-ALG-01 date | **Open** |
| 14 | NJ-DEP-01 citation | **Fixed** |
| 15 | CA-SCREEN-02 secondary duplicate | **Fixed.** It is now Gov. Code §12955 from official D027, a distinct law. |
| 16 | BERK-EVICT-02 | **Fixed** (event scope) |
| 17 | Berkeley citation forms | **Mostly fixed** |
| 18 | A0227 unit count | **Fixed** (NJ-FEE-01 applies) |
| 19 | CA-FEE-01 2026 figure ($68.96 in D005) and flag | **Open** |
| 20 | SF-RENT-01 quote is about eviction coverage | **Open, and worse than "LOW".** The stored span "This includes tenancies in newly constructed rental units that first obtained a Certificate of Occupancy after June 13, 1979" reads, out of context, as if post-1979 units *are* rent-controlled. |
| 21 | SA-ALG-01 quote reads as pending ("set for a final vote on March 3") | **Open** |
| 22 | H.3744 duplicate filed at state level | **Fixed** (BOS-*-P1, Boston, failed) |
| 23 | JC-RENT-01 note and flag | **Flag fixed.** Quote is still boilerplate. |
| 24 | NJ-RENT-02 citation | **Fixed** |
| 25 | NJ-RENT-01 as a standalone rule | **Fixed** (municipality-subject, never emitted) |
| 26 | NJ-ALG-01 quote is the preemption clause, not the ban | **Open** |
| 27 | LA-DEP-01 key value | **Fixed** (4.320% for 2025 is mentioned) |
| 28 | CA-ALG-01 citation tail | **Fixed** |
| 29 | CA-SCREEN-02 quote (aggregate income, not source of income) | **Open** (low) |
| 30 | CA 2024-04-01 dates | **Open, with a new consequence:** it causes the date-slider error in §1.3 |
| 31 | MA-ALG-P1 source D047 vs D046 | **Open** (low) |
| 32 | BOS-SCREEN-01 weak quote | **Open** (low) |
| 33 | Newark / Hoboken / SD not extractable | **Open** (documented) |

---

## 3. The 8 most valuable remaining improvements (under 6 hours, ranked by points per hour)

**Rules that apply to all eight:**
- After each change, run the guard set: `python run.py` (cached), `python -m lexmap.selfcheck` (must stay at 44/44 + T6), `python -m unittest discover -s tests`, `node tests/parity.js`.
- Items 1 and 6 need live model calls, which the user runs. Everything else is deterministic and changes no cache key.
- **Never edit the shared extraction, reconcile or QA *system prompts*.** That changes every cache key and re-runs all 173 calls, which can move T1–T5 and every auto-scored file.

**Not counted below, but non-negotiable (about 1.5 hours):** record the three ≤ 60 s videos. The brief requires scores on screen, T1–T6, and the hour-16 file being processed. Plain language & usability is scored from the demo, so without the videos up to 10 points are at risk. Fix the VIDEO_SCRIPTS issues in §4 first.

| Rank | Change | Exp. pts | Hours | Pts/h | Risk to T1–T5 / auto files |
|---|---|---|---|---|---|
| 1 | Organiser hour-16 file → T6 | +2.5–3.0 | 0.75 | ≈ 3.7 | Low |
| 2 | CLI disclaimer + doc consistency fixes | +0.5 | 0.4 | ≈ 1.3 | None |
| 3 | Deterministic date backfill + guide §9 open questions | +0.8–1.0 | 0.75 | ≈ 1.2 | Low |
| 4 | Audit-trail completeness (QA + all model calls) | +0.5–0.7 | 0.5 | ≈ 1.2 | None |
| 5 | Citation aliases in the brief's form | +0.3–0.6 | 0.4 | ≈ 1.1 | Low–medium (see note) |
| 6 | Targeted second pass for zero-candidate docs (MA eviction procedure) | EV +1.0–2.0 | 1.5 | ≈ 1.0 | Low; changes auto files |
| 7 | Primary-quote selection by relevance | +0.3 | 0.5 | ≈ 0.6 | Low |
| 8 | Amendment dates must not gate in-force rules (date slider) | +0.4 | 0.75 | ≈ 0.5 | Medium; touches the engine |

Total: about 5.6 hours.

### 1. Get the organiser's hour-16 ordinance and run the drop-in (T6)
The brief says it is released "via the Google Drive folder" at hour 16. "no-hour16" in the folder name describes the pack version, not proof that it was never released. Check the Drive folder now.

Steps:
- Save the file as `data/hour16/<name>.txt` and `data/hour16/<name>.json` with `{"jurisdiction": "Cambridge, MA"}`.
- Run `python run.py --extract` (live calls only for the new document and any reconcile/QA group it joins).
- Then:
  - Confirm `changes.json` has `T6`, with the extracted future date and its affected set.
  - Confirm the rule is in `rules.json` and is `not_yet_effective` in `lookups.json`.
- Update the "five change cases" string (`index.html` `changes_sub`, and in app.js if repeated), the README table (T6 row), METHOD_NOTE §9 and the VIDEO_SCRIPTS demo row.
- Record the live run for the technical video.

**Risk:** low. If the new rule lands in an existing (Cambridge, category) group, that group's reconcile and QA calls re-run and can rewrite CAM-SCREEN-01 or a sibling. T1–T5 involve no Cambridge-only rule, and the self-check's T1–T5 rows guard them. Do **not** substitute the team's fictional `data/whatif` file as T6.

### 2. "Not legal advice" + as-of line on every CLI output, plus doc consistency (no outputs change)
- `run.py`, the address printer (about lines 116–123): print `As of <date> · Not legal advice. Summarises public law; check the cited source.` before and after the rows.
- `lexmap/whatif.py`: print the same line wherever it prints results.
- `lexmap/lookup.py` docstring: reorder the decision table to match the code (coverage and exemption *before* pending/NYE), as METHOD_NOTE step 8 already states.
- Fix the §4 items: VIDEO_SCRIPTS `provenance.qa`, README's confidence-cap sentence, and CHECKLIST's "character-for-character".

**Risk:** none. This is text only.

### 3. Deterministic date backfill + surface guide §9's open questions
Add a post-merge, no-LLM step in `lexmap/reconcile.py` (after `build_rule`, near lines 140–160) or a small `lexmap/dates.py` called from `run.py`.

**SD-ALG-01 and BERK-ALG-01:**
- If `effective_date` is null and any member or corroborating candidate in `build/candidates.json` carries an ISO date, set it. This gives SD `2025-06` and Berkeley `2026-01`.
- Record `date_source: "secondary (D002)"`, append to `source_notes`, and keep confidence at or below 0.75.

**BERK-ALG-01:** also set `source_conflict: true` with the note "official ordinance text in corpus gives no date; law-firm alert (D002) says January 2026; organiser guide §9 reports 2026-03-01 in the ordinance".

**LA-RENT-01:** do **not** set `effective_date` (the engine would make RSO NYE before Feb 2026). Instead:
- Add `amendment_effective_date: "2026-02-02"` from D041 ("Effective February 2, 2026").
- Set `source_conflict: true` (guide: 2026-01-24 per a landlord association).

**CA-FEE-01:** add a `source_notes` line quoting D005 ("The maximum tenant screening fee for 2026 is $68.96", a Berkeley Rent Board figure) and "no single official statewide figure".

**README:** add an "Open questions in the law (guide §9)" section that lists the four items and what Lexmap does with each. Update the "3 rules flagged" sentences in README, METHOD_NOTE and the app.

**Risk:** low.
- T3 conflict sets use only `conflict_with` between test rules (`changes.py`, lines 96–98), so new Berkeley and LA flags do not touch T3.
- The SD and Berkeley dates are before 2026-10-01, so no 2026-10-01 result changes.
- `conflict_flag` becomes true on 40 Berkeley and about 55 LA lookup rows. That is intended.

### 4. Audit-trail completeness
- **`run.py` (about line 55).** Add `"qa": r.get("qa")` and `"resource": r.get("provenance_resource")` to `provenance`.
- **`lexmap/audit.py`:**
  - Emit one `llm_call` event per cache entry *used* in the run, with stage tag (extract, reconcile, qa, resource or explain), model, key and created_at, so all 173 calls appear, not 71.
  - Emit one `qa_change` event per changed field. Fields: rule, field, before, after, reason.
  - Add both `manifest_sha256` (from `corpus_manifest.csv`) and `file_sha256` to source events. They differ: the manifest hashes the original capture.

**Risk:** none. These are extra keys; the schema has no `additionalProperties: false`.

### 5. Citation aliases in the brief's form
In `reconcile.clean_citation` (deterministic): when `citation_full` contains a session law or bill designator that the short `citation` lacks, append it in parentheses. Designators: `P.L.\d{4}, c\.\d+`, `\b(AB|SB) \d+`, `Ord(inance)? No\.`.

Examples:
- `N.J.S.A. 46:8-18.1 (P.L.2025, c.405)`
- `Cal. Bus. & Prof. Code § 16729 (AB 325)`

Leave already-matching forms untouched.

**Risk:** low–medium, and it cuts both ways. Containment or fuzzy matching gains; strict string equality could lose. Applying it only where the short form is *not* the brief's form keeps the risk small. It does not touch T-test ids.

### 6. Targeted second pass for documents that gave zero candidates
Create `lexmap/recheck.py` with a **new** system prompt `prompts.RECHECK_SYSTEM`. It runs only for corpus documents whose `build/candidates.json` entry has 0 candidates: D013, D014, D031, D050, D051, D053, D058.

The prompt should state:
- Required pre-termination notices, notice-to-quit periods and anti-retaliation presumptions are `just_cause_eviction` rules.
- The `requirement` must say honestly when the state has *no* just-cause requirement.

Then:
- Append the results to the candidates and call it from `run.py` after extraction.
- The original extraction prompt and its 67 cache entries stay valid. Only new groups get new reconcile/QA calls: (MA, just cause), (Cambridge, just cause), and (Boston, just cause), which already holds the failed BOS-EVICT-P1.

**Why it pays:**
- Missing an applicable rule costs double; an extra row costs single. Adding is therefore positive expected value if P(key has it) > ⅓.
- Seven official documents on this exact topic were placed in the corpus.

**Risk:**
- T1–T5: low, because the new rules are just-cause category. The T5 checks look for rent caps, and the self-check verifies "failed never reported".
- It **does** change `rules.json`, `lookups.json` (110 MA rows), the self-check counts and the README numbers. Re-run everything and update the numbers.

### 7. Primary-quote selection by relevance (deterministic)
In `run.py`'s export (where `quoted_span = r["verified_spans"][0]["text"]`):
- Choose the verified span **from the same `source_doc_id`** with the highest token overlap with `requirement` + `key_value`.
- Optionally extend it to sentence boundaries in the raw file (`lexmap/spans.py`), keeping the exact raw characters.

This fixes:
- SF-RENT-01: the misleading post-1979 fragment. Prefer the full "Some tenancies that are exempt from the rent increase limitations…" sentence.
- NJ-ALG-01: the preemption clause. Prefer "shall be unlawful … for:".
- SA-ALG-01: reads as pending.
- BOS-SCREEN-01: weak span.

**Risk:** low. The self-check's verbatim check guards the citation auto-score. Keep the same document so the official share does not drop.

### 8. Amendment dates must not gate in-force rules
**Problem:** the date-slider bug in §1.3.

**Fix without touching the scored `effective_date` field:**
- Add a deterministic `in_force_since` field in reconcile post-processing:
  - If the primary source contains a CA history line `(Amended by Stats. …  Effective <date>.)` matching `effective_date`, or `shall become operative on <date>` for a re-enacted section, set `in_force_since = null`.
  - If `key_value` begins with a rate period ("for March 1, 2026 – February 28, 2027", as in SF-DEP-01), also set `in_force_since = null`.
  - Otherwise `in_force_since = effective_date`.
- Make the NYE branch use `in_force_since` in **both** `lexmap/lookup.py` (the `eff = _d(...)` line) and `docs/engine.js`, then re-run parity.
- Earlier dates then answer `applies` with a note: "current text operative from X; an earlier version applied before".

**Rules affected:** CA-FEE-01, CA-RENT-01, CA-EVICT-01, CA-SCREEN-02, SF-DEP-01. CA-ALG-01 is "Section 16729 is added" (D022), so it is not matched and T1 is unchanged.

**Risk:** medium, because it touches the engine. T1 must still show 250 NYE on 2025-12-31; the self-check and parity confirm it. The 2026-10-01 auto outputs do not change.

**Considered, not ranked.**
- **LA post-1978 "replacement unit" `unknown`s** (§1.2). Treating a rare re-inclusion `other_fact` inside `covers.any` as non-blocking would fix about 6 held-out LA addresses × 2 rules (+0.3–0.5). It needs a principled rule in `coverage.py` plus `engine.js`, and it argues against the "never guess" stance.
- **`needs_review` on lookup rows** (confidence < 0.65 or secondary). This is cheap and serves responsible design (+0.3). An extra key in `lookups.json` entries carries a small risk if the scorer is strict, so add it only to `docs/data` and the UI, not the submission.

---

## 4. Overclaims and inconsistencies (checked against `submission/*`)

**Verified accurate:**
- Self-check 44/44.
- T1 250, T2 90 / 0 Newark, T3 140 / 90, T4 110, T5 0.
- Official-quote share 3,354 / 3,491 = 96%.
- 129/129 quotes = 56 primary + 73 supporting.
- 129 tests; parity 2000/2000.
- 487/500 geocoded; 27 NJ owner ZIPs.
- 54 official + 13 secondary = 67 documents.
- 5 event-only rules; 3 conflict-flagged rules.
- QA changed 32 of 56 (in `build/rules_full.json`).
- What-if 2027-03-01 / 45; models Sonnet 5.5 / Opus 5.5 (`config.py`).

**Problems:**
1. **VIDEO_SCRIPTS, technical video 22–32 s,** says to show "`provenance.qa`" in `submission/rules.json`. That key does not exist; provenance has only `extraction_llm_call`, `reconcile` and `validation_notes`. Either show `build/rules_full.json` → `qa` or do improvement 4.
2. **README §5 and METHOD_NOTE "every change is logged"** and README's "audit_log … model-call keys". The QA changes are not in `submission/`, and the audit log has 71 `llm_call` events of 173 cached calls (extraction only).
3. **README Responsible design, "capped … 0.75 for flagged conflicts".** NJ-ALG-01 is flagged with confidence **0.98**. The cap runs in `reconcile.py` (line 154) before the FAIR-Act conflict is wired.
4. **README "'Not legal advice' on every screen"** and the guide's "every interface". The CLI `--address` and `whatif` outputs print no disclaimer.
5. **README and site "answers … for any date".** Wrong for amended statutes before their amendment date (§1.3): CA-FEE-01 is NYE on the demo's own 2025-12-31 chip; AB 1482 is NYE before 2024-04-01.
6. **README "plus the decision table in the `lookup.py` docstring".** The docstring order (pending/NYE before coverage) contradicts the code and METHOD_NOTE step 8.
7. **METHOD_NOTE "Only 3 rules carry conflict flags, all genuinely open questions"** and the site's "Open questions in the law" panel. Three of the guide's four §9 open questions (Berkeley date, LA RSO date, CA fee figure) are absent, so the panel's title over-promises.
8. **SUBMISSION_CHECKLIST paragraph "every quote is verified character-for-character".** README says 39 of 129 matched only after whitespace normalisation (the stored text is raw). Use README's wording.
9. **VIDEO_SCRIPTS "Our scores: 44 of 44 self-checks pass"** could be read as the organiser score. The brief asks for "score.py on the dev set". Say on screen that no `score.py` or dev key was in the pack and that this is the team's own check-set.
10. **Minor.** Audit `sha256` (file bytes, e.g. D001 `7f24…`) differs from the manifest `sha256` (`764e…`). Both are valid, but unexplained it looks like a mismatch; record both.
11. **Minor.** Self-check "51 in official corpus text, 5 in fetched secondary pages" and README "129/129" use different denominators (primary only vs primary + supporting). Both are true; say which is which.

*Not legal advice. This is a review of a hackathon prototype.*
