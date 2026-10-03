# Lexmap: strict judge review (RealPage "Rental Housing Law Navigator")

Reviewed 2026-10-03 ~23:30 EEST against commit `1b9b9e9` (citations cleaned, 129-test suite). Other files were being edited while I reviewed. Inputs: brief (`file2.pdf`), `PARTICIPANT_GUIDE.md`, `submission/*`, `build/*`, `lexmap/*.py`, `docs/*`, README, METHOD_NOTE, VIDEO_SCRIPTS. The live site https://suvyakth.github.io/lexmap/ is up and shows the "Not legal advice" banner.

Neither `score.py` nor the dev answer key is in the pack. The folder is literally `participant-final-no-hour16 ... no-scoring`. So every auto-score below is an estimate. I built it by checking the brief's named laws against `rules.json` and by guessing the hidden key's shape. One structural clue: 3 states + 10 cities = 13 jurisdictions, and 13 × 6 categories = 78 cells. The key has 58 rules + 19 "no rule" findings = 77, so it is very likely about one entry per (jurisdiction, category) cell.

---

## 1. Predicted score

| Rubric line | Pts | Predicted | Range | Basis |
|---|---|---|---|---|
| Extraction accuracy (auto) | 25 | **15** | 12–18 | See 1.1 |
| Address coverage (auto) | 20 | **12** | 10–14 | See 1.2 |
| Citations (auto) | 15 | **13.5** | 12–14.5 | 3,739 of 4,126 `applies` answers (91%) quote official corpus text. The other 9% quote fetched secondary pages, which the scorer's corpus does not contain |
| Change tracking (auto) | 15 | **12.5** | 12–13 | T1–T5 look right: T1 250/250 CA, T2 90 (0 Newark), T3 140 + 90 conflict flags, T4 110 MA, T5 empty. **T6 is missing entirely**: no `T6` key in `changes.json`, worth about 2.5 pts |
| Plain language & usability (judges) | 10 | **7** | 6–8 | See 1.3 |
| Responsible design (judges) | 10 | **8** | 7–9 | See 1.4 |
| Scalability path (judges) | 5 | **4** | 3–4 | What-if pipeline exists, but jurisdiction tables are hard-coded |
| **Total** | 100 | **≈72** | 63–80 | **≈81–85** is reachable with the top 6 fixes below |

### 1.1 Extraction (rules.json: 55 rules, 13 jurisdictions)

**Brief-named laws that are present, with a matchable citation (good):**
- CA: §1947.12, §1946.2, §1950.5 (2024-07-01, correct), §1950.6, Gov §12955
- CA AB 325: cited as `Cal. Bus. & Prof. Code § 16729`. If the key cites "AB 325 / SB 763", a fuzzy match may fail, and SB 763 is not separately represented.
- SF: ch. 37, §37.9, §37.10C (2024-10-14). LA: RSO
- NJ: 2A:18-61.1, P.L.2025 c.405 (2026-05-01), P.L.2021 c.110, FAIR Act P.L.2026 c.43 (2027-07-01, NYE)
- MA: c.40P, c.186 §15B (deposit and fees), c.112 §87DDD½ (2025-08-01), S.2983/H.5222 pending, IP 25-21 failed
- Santa Ana NS-3090 (2026-04-02). JC §218-12 (2025-06). SD §§98.1101–98.1104

**Citation and field risks:**
- `NJ-DEP-01` cites `N.J.S.A. 46:8-19 to 46:8-21.5`. The brief and the key use **46:8-21.2**, which the team's own quoted span contains: "(N.J.S.A. 46:8-21.2)". This is a likely citation miss.
- `MA-FEE-02` writes `§ 87DDD 1/2`; the brief writes `87DDD½`. A naive normaliser will not match them.
- `HOB-ALG-01` cites `ch. 158-2`; the brief says `ch. 158, Art. II`.
- `BERK-DEP-01`, `BERK-EVICT-01` and `BERK-EVICT-02` have no code cite, only ordinance names. Should be `Berkeley Mun. Code ch. 13.76`.
- `SF-DEP-01` cites "San Francisco Rent Board security deposit interest rate". That is not a citation.
- `CA-SCREEN-02` cites "California Civil Rights Council regulations…": no cite, and it comes from a secondary page (D015).
- **Effective dates that are null although a source gives one:**
  - `SD-ALG-01`: brief says Jun 2025; D002 says "effective June 2025".
  - `BERK-ALG-01`: brief says 2026. D002 says January 2026, and the guide says the ordinance text says 2026-03-01. This is a named open question, and the team neither surfaces it nor flags it.
- `CA-SCREEN-01` is dated 2024-01-01 (SB 267). The brief anchors this rule to SB 329 (2020-01-01). Possible date miss.

**Likely missing rules** (each costs extraction recall and address coverage):
1. **Newark rent control.** Newark has **0 rules**: D070–D072 are link-only on ecode360.
2. **Hoboken rent control.** D032/D033 are link-only.
3. **SF Fair Chance Ordinance.** D078 is hand-excluded in `extract.py:SKIP_DOCS` as "homepage". But D078 line 115 says verbatim: "San Francisco's Fair Chance Ordinance protects residents with arrest or conviction history in affordable housing decisions."
4. **SD source-of-income ordinance.** D075 is link-only on gocodebook.
5. **MA CORI housing regulations, 803 CMR 5.** D056 is official but capture failed with a 403. A human can download it in a browser.

**Likely false positives.** Each is unmatched in extraction and generates wrong lookup rows:
- `CA-EVICT-03` (Civ. Code §1947.9). This applies only in the City and County of SF, but it is modelled as statewide and marked `applies` at 170 LA/SD/Berkeley addresses.
- `CA-EVICT-02` (Housing Crisis Act demolition relocation), `applies` at 250 CA addresses.
- `LA-EVICT-03` (RPO demolition), `applies` at 80 LA addresses.
- `NJ-EVICT-02` (condo-conversion protected tenancy), `unknown` at 140 NJ addresses.
- `NJ-RENT-02` ("not unconscionable", `applies` at 140 NJ addresses). The key may hold "NJ: no statewide rent cap" as a no-rule finding, which would make this a false positive.
- Duplicates: `MA-EVICT-P1` and `MA-RENT-P2` are the same Boston home-rule bill H.3744, filed at state level.

**Estimate:** about 40–44 of 58 rules matched, field accuracy about 0.7, precision about 0.8. That gives roughly 15 of 25.

### 1.2 Address coverage

Lookups have 5,301 rows: applies 4,126, unknown 550, superseded 265, NYE 140, pending 220. The engine is principled:
- A building in a cut-off year is `unknown`.
- Missing year in SD and Berkeley gives `unknown`.
- `superseded` is correct for CA caps under SF and LA rent control (47 + 71). The 21 post-1978 LA buildings and 6 post-1979 SF buildings correctly get the CA cap as `applies`.

**Losses:**
- **Missing rows (double penalty).** Newark and Hoboken rent control (90 addresses), SF Fair Chance (80), SD source of income (50), MA CORI (110).
- **Extra rows.** About 1,000 or more rows from the false-positive rules above, plus `BOS-SCREEN-01` (`unknown` ×61: DND-funded housing only), and `CA-SCREEN-02` ×250 if the key has a single CA screening rule.
- **One wrong geocode.** A0009 (322 Western Ave, Cambridge, from the Cambridge assessor DB) matched "5 WESTERN AVE … 02163", so it was placed in **Boston**. That is why the split is Boston 61 / Cambridge 49 when it should be 60/50.

Estimate: about 12 of 20.

### 1.3 Plain language & usability (code reading only)

**Strengths:**
- Clean static UI: address search with examples, as-of date chips, live Census lookup.
- EN/ES toggle.
- Per-category cards with a plain summary, key figure, source quote, retrieval date and confidence meter.
- Change-test tab.
- Rules table with gaps.

**Weaknesses:**
- **No "at a glance" summary.** There is no single per-category line ("Rent: SF Rent Ordinance, 1.6% this year, S.F. Admin. Code ch. 37"), which is exactly the brief's illustrative output.
- **"Why" lines are predicate syntax** ("certificate-of-occupancy date > 1979-06-13? no (built 1926)"), shown in English even in ES mode.
- **Weak "no rule" message for Boston and Cambridge.** The rent card says "No rule … found in the corpus". It should say "Massachusetts bars local rent control (G.L. c.40P §4); the 2026 ballot question was struck (IP 25-21)", which is the answer a renter needs.
- **Niche rules clutter real addresses.** Demolition, Ellis and temporary-displacement rules appear on every address.
- **Stale and inaccurate copy.**
  - The changes tab says "five change cases".
  - The "Look up any address" path *assumes* multifamily and sets `units_min: 1`, while claiming "never guessed".

### 1.4 Responsible design

**Strong:**
- Verbatim-quote verification
- Number-guard on summaries
- Named missing facts
- Enacted / NYE / pending / failed kept separate
- Audit log with hashes
- Cached model calls for reproducibility
- "Not legal advice" on every screen, as-of date on every answer

**Weak:**
- **Over-flagging.** `CA-DEP-01` and `CA-SCREEN-01` carry `conflict_flag` for "disagreements" that the note itself resolves. This dilutes the signal.
- **No `needs_review` for low-confidence answers.** The brief asks for low-confidence answers to be flagged too.
- **Secondary-only rules look official.** `HOB-ALG-01` and `JC-ALG-01` (law-firm summary, confidence 0.6) say `applies` with no "secondary source" note in the lookup explanation.
- **Hand-coded skip list.** `SKIP_DOCS` contains a factual error (see D078 above).

---

## 2. The 12 highest-leverage improvements

Ranked by expected points ÷ effort hours. "Pts" is expected gain against the predicted score.

| # | Change | Pts | Hrs | Ratio |
|---|---|---|---|---|
| 1 | Un-skip D078 (SF Fair Chance) | +1.0 | 0.3 | 3.3 |
| 2 | T6 wired into `changes.json`, `rules.json` and `lookups.json`, plus a coverage-before-NYE fix | +2.5–3 | 1 | 2.7 |
| 3 | Omit "special-subset only" rules from lookups | +0.8 | 0.4 | 2.0 |
| 4 | Fix A0009 geocode (house-number check) | +0.3 | 0.3 | 1.0 (cheap, and protects T6) |
| 5 | Geographic limit + "incidental" scope classification in QA | +1.5–2 | 1.5 | 1.2 |
| 6 | Re-source secondary-quoted rules to official spans | +1.0 | 1 | 1.0 |
| 7 | Citation canonicaliser, second pass | +0.8 | 1 | 0.8 |
| 8 | Effective dates from secondary sources + open-questions panel | +0.6 | 0.7 | 0.9 |
| 9 | Manual capture of D056, D070–72, D032–33, D035 (user decision) | +2–4 | 2 | 1–2 |
| 10 | UI "at a glance" + evidence-backed "no rule" cards + ES why-lines | +1.5 | 2 | 0.75 |
| 11 | Conflict-flag hygiene + `needs_review` | +0.6 | 0.5 | 1.2 |
| 12 | Videos, README and method-note content (score evidence, T6, live rerun) | +1.5 | 1.5 | 1.0 |

### Details

**1. Remove `"D078"` from `SKIP_DOCS` in `lexmap/extract.py`**, then run `python run.py --extract`. Only D078 is a cache miss.
- The page contains a verifiable sentence about the SF Fair Chance Ordinance. The extractor will emit `SF-SCREEN-01` with coverage `other_fact: affordable housing`, which gives `unknown` (partial credit) instead of a missing row (double penalty) on all 80 SF addresses.
- It also removes a hand-coded exclusion, which a judge reads as a red flag.

**2. T6 must be a first-class test, not only a what-if.**
- **(a)** When the hour-16 file arrives, put it in `data/raw/corpus/text/` (or `data/hour16/`) and add a manifest row, so `run.py` extracts it in the normal pass. That way the rule lands in `rules.json` and in `lookups.json`, where it will be `not_yet_effective`.
- **(b)** In `changes.py`, accept a `T6` entry. Either append it to a local copy of the change tests, or add `--extra-test`. Use type `as_of`, with `as_of_before` = 2026-10-01 and `as_of_after` = the effective date + 1 day.
- **(c)** Write `T6` into `submission/changes.json` with `affected_address_ids` and `notes` stating the extracted effective date.
- **(d) Bug.** In `lexmap/lookup.py` and `docs/engine.js`, the `pending` and `not_yet_effective` branches return *before* coverage is evaluated. A future Cambridge rule limited to buildings with 6 or more units is therefore reported NYE on all 49 Cambridge addresses. This already happens in `build/whatif` (`not_yet_effective: 49`). Fix: evaluate coverage and exemptions first. Omit the rule if coverage is False, give `unknown` if coverage is unknown, otherwise return `pending` or NYE.
- **(e)** Re-run `node tests/parity.js`.

**3. In `lookup.to_submission`, drop rows whose only missing fact is `other_fact` inside `covers`**, meaning the rule targets a special subset such as DND-funded or condo-conversion buildings.
- Keep these rows in the site, under a collapsed group "may apply to special housing types".
- This removes `NJ-EVICT-02` ×140 and `BOS-SCREEN-01` ×61 unknown rows.
- It is a generic rule, not hand-picking.

**4. In `lexmap/geocode.py`, reject a Census match whose leading house number is outside the query's number range** (A0009 asked for 322 and got "5 WESTERN AVE").
- Retry with the first number only ("322 Western Ave").
- If it still fails, fall back to the source-dataset city: "Cambridge Property Database" means Cambridge. Flag it.
- Add a unit test. A0009 has 6 units, so it matters for any Cambridge T6 rule with a unit threshold.

**5. Add two fields to the QA prompt and output in `lexmap/qa.py`, and honour them in `lookup.py`.**
- `applies_only_in`: a list of cities. Use it for state statutes that the text limits to one city, such as Civ. Code §1947.9, which applies only in the City and County of SF. The engine treats this as a jurisdiction filter.
- `scope`: `core` or `incidental`. Incidental means the rule only bites on a rare event: demolition (Housing Crisis Act, LA RPO), Ellis withdrawal, temporary capital-improvement displacement, or condo conversion. Incidental rules stay in `rules.json` but are omitted from `lookups.json` (or shown as "event-triggered" in the UI).
- This turns about 500 likely-wrong `applies` rows into nothing, through an automated, logged step.
- Also tell the extraction prompt that a home-rule petition or special law for one city has `jurisdiction` = that city (fixes the H.3744 records).

**6. Prefer official spans.** In `reconcile.build_rule`, when a primary candidate comes from a secondary source, search the official corpus docs of the same jurisdiction for a supporting span, using `SpanIndex.closest_passages` plus the existing `REPAIR_TEMPLATE`.
- `CA-SCREEN-02` should come from D016 (calcivilrights.ca.gov has the criminal-history text). Or merge it into `CA-SCREEN-01` as one FEHA rule.
- `LA-DEP-01` should come from D041 (section "Interest Payments on Security Deposits").
- This lifts the official-corpus share of `applies` answers from 91% to about 97%. HOB/JC algorithmic bans have no corpus text, so they stay secondary.

**7. Citation canonicaliser, second pass.** Extend `clean_citation` in `reconcile.py`:
- **(a)** If a quoted or supporting span contains a parenthetical statute cite such as "(N.J.S.A. 46:8-21.2)", prefer it over a range.
- **(b)** Normalise `1/2` to `½` (and keep an ASCII alias).
- **(c)** Where an ordinance name has a known code chapter in the same rule's text (Berkeley 13.76, Hoboken 158 Art. II), use the code cite.
- **(d)** Add a `citation_aliases` list for bill names ("AB 325", "SB 763", "AB 1482", "AB 12"). The scorer reads `citation`, so keep `citation` short and canonical, in the same form as the brief's table.
- **(e)** For `SF-DEP-01`, only use "S.F. Admin. Code ch. 49" if the text supports it. Otherwise mark `citation_source: "not stated in source"` rather than inventing one.

**8. Date policy: an official null should not beat secondary evidence.**
- When official text gives no date and a secondary member gives one, set it and set `date_source: secondary`, with a conflict note and confidence capped at 0.6.
- Cases: `SD-ALG-01` = 2025-06. `BERK-ALG-01` = 2026-01 (D002), with a note that the guide reports 2026-03-01 in the ordinance text.
- Add an **"Open questions in the law"** card on the method tab and in the README. It should list the guide's four §9 items (Berkeley date, FAIR preemption, LA RSO 2026-02-02 vs 01-24, CA fee cap with no 2026 figure), plus what Lexmap does with each. This is explicitly a bonus.

**9. Close the corpus gaps by human capture. This is the user's call; check site terms first.**
- `D056`, 803 CMR 5 (mass.gov, official, script-blocked with a 403): open it in a browser and save the PDF to `data/manual/`.
- `D070–D072` (Newark) and `D032–D033` (Hoboken), ecode360: read the terms. If manual viewing and copying is allowed, save each page's text by hand.
- `D035` (Hudson County View, JC ban details).
- Store each file with `SOURCE` / `RETRIEVED` / `CAPTURE: manual browser copy` headers and run the normal extraction.
- This is not bulk scraping, but say so in the README.
- Expected gain: up to 3 key rules, and the rows for 90 NJ + 110 MA addresses, mostly `unknown` (NJ has no unit counts), which beats missing.
- If terms forbid it, add a "no corpus text" finding to `gaps.json` for each, with the URL.

**10. UI (`docs/app.js`, `index.html`, `style.css`).**
- **(a) "At a glance" table** at the top of each address: one line per category with the governing rule, key figure, citation and status pill. Mirror the brief's illustrative output.
- **(b) Evidence-backed "no rule" cards.** Generate them from a `no_rule_findings` list in `site.py`, each with a reason and a cite: MA rent (c.40P §4 bar + IP 25-21 struck, linking T5), MA just cause (only notice statutes c.186 §§11, 12, 31), and NJ statewide rent (no statewide cap; local only). Also write `submission/no_rule_findings.json`. The scorer may ignore it, but judges will see it is handled.
- **(c) Plain "why" sentences** from `describe_leaf` ("Built 1926, before the 13 June 1979 cut-off, so the rent limits apply"), translated in ES.
- **(d)** Change "five change cases" to six once T6 lands.
- **(e) Custom lookup:** default `property_type` to unknown and `units_min` to null, not "multifamily" and 1.
- **(f)** Add `aria-selected` on tabs.

**11. Conflict-flag hygiene.**
- In `reconcile.build_rule`, keep `conflict_note` but set `conflict_flag` only when the disagreement is unresolved. Downgrade cases where the note itself says "both accurate for different amendments" or "kept X". Example: `CA-DEP-01` 2024-07-01 vs 2026-01-01 is operative date vs amendment date.
- Add `needs_review: true` (an extra key, harmless) to lookup rows when confidence < 0.65 or the source is secondary, and show a "Low confidence – review" pill.
- Append "(source: law-firm summary; ordinance text not in corpus)" to explanations for secondary-only rules.

**12. Submission narrative.**
- Videos: see §3.
- README: add a **"Scores"** block. Self-check 44/44 → (new count). T1–T6 table with affected counts. Official-corpus quote share. Lookup distribution. "No score.py was provided; here is what we measured instead."
- **Reconcile the verbatim claim.** The README says "129/129 verified: 90 exact and 39 whitespace-normalised", while the video says "character-for-character". State that whitespace-normalised *matching* still stores the exact raw characters, and say this identically everywhere.
- Explain `align_test_ids`: ids are aligned to the test-case ids so the organisers' T-tests can find the rules. Results are not tuned.
- METHOD_NOTE: add a short "What we deliberately do not report" paragraph (failed measures, special-subset rules, no-rule cells). It must still fit on one page.

---

## 3. Videos (≤ 60 s each)

**General rules:**
- The brief requires showing scores in the videos, T1–T6, and the hour-16 ordinance being processed.
- The guide adds: "You should show the extraction pipeline in the demo."
- Record at 1080p, zoom the browser to 125%, and use no music under the voice.

### Demo video (product, judged for plain language and usability)

| t | Shot | Voice (≈140 words total) |
|---|---|---|
| 0–5 | Live site, "Not legal advice" banner highlighted | "Lexmap: which housing rules apply at this address, today and on any date." |
| 5–17 | A0016 SF 1926: at-a-glance table, rent row says `superseded`; open the source quote | "Rent control applies, so California's cap is superseded. Every line quotes the law and its retrieval date." |
| 17–25 | A0107 LA built 1978: `unknown` card naming the missing fact | "Built in the cut-off year: we say unknown and name the missing fact." |
| 25–33 | A0065 Dorchester → Boston: rent "no rule" card citing c.40P and the struck ballot question | "Dorchester is Boston. Massachusetts bars rent control; the 2026 ballot question was struck. No cap reported." |
| 33–43 | A0002 Hoboken, date chip Jul 2 2027: FAIR Act flips to `applies`, ⚑ conflict | "Move the date: the FAIR Act takes effect and the city ban is flagged for possible preemption." |
| 43–55 | "What's changing" tab: T1–T6 green, open T6 (hour-16 Cambridge ordinance) with its effective date and affected count | "All six change tests, including the hour-16 ordinance, read automatically." |
| 55–60 | Toggle ES for 2 s, ending on the banner | "In English and Spanish. Not legal advice." |

### Technical video (method and scores)

| t | Shot | Voice |
|---|---|---|
| 0–8 | README diagram | "The model reads law; a deterministic three-valued evaluator decides." |
| 8–20 | **Live, uncached**: `python run.py whatif <hour16 file> --jurisdiction "Cambridge, MA"` streaming extraction → verified quote → effective date → affected list | "Here's the hour-16 ordinance going through the pipeline live, with no hand-coding. The quote is verified against the file." |
| 20–30 | One rule in `rules.json`: `coverage_logic`, `quoted_span`, `provenance` | "Each rule compiles to executable coverage logic." |
| 30–45 | `selfcheck_report.md` with the summary line and T1–T6 rows, and a terminal one-liner printing the lookup result distribution and official-quote share | "Our scores: N of N checks; T1–T6 match; 97% of applies answers quote the official corpus." |
| 45–55 | `audit_log.jsonl` grep for one answer; `node tests/parity.js` 2000/2000 | "Every answer is audited and reproducible offline." |
| 55–60 | Scalability slide: new city = documents + manifest row | "New jurisdictions need only documents." |

**Do not:**
- Show `python run.py` finishing in 1 s from cache without saying it is a cache replay. A judge checking "automated extraction" wants to see a live model call.
- Use the fictional team-written ordinance in place of the organiser's hour-16 file.

---

## 4. Red flags a judge would penalise

1. **Hand-coded exclusion.** `SKIP_DOCS = {"D078": ...}` in `extract.py`, and its stated reason is factually wrong (the page names the SF Fair Chance Ordinance). Remove it or make it data-driven.
2. **Statewide answers that are legally wrong for the address.**
   - Civ. Code §1947.9 shown as `applies` in LA, San Diego and Berkeley. It is SF-only.
   - Housing Crisis Act and RPO demolition relocation shown as `applies` to every building with the bare explanation "Statewide California rule." To a judge this reads like a legal conclusion the source does not support.
3. **Undisclosed guessing in the custom lookup.** `property_type: "multifamily"` and `units_min: 1` are assumed, while the UI says "never guessed".
4. **Non-citations in the citation field.** `SF-DEP-01` ("…interest rate") and `CA-SCREEN-02` ("…regulations on use of criminal history") are names, not cites.
5. **Secondary-only rules presented as `applies` without a caveat in the answer.** HOB-ALG-01 and JC-ALG-01 come from a Morgan Lewis client alert, and `SA-ALG-01` from a news page.
6. **Conflict-flag noise.** 14 rules are flagged, several over resolved non-issues, which weakens the "flag for human review" story.
7. **Over-claims to soften.**
   - "Adding a jurisdiction is just documents plus one command": `config.py` (`JURISDICTION_CODE`, `CENSUS_PLACE_TO_JURISDICTION`) and `app.js` (`PLACE_TO_CITY`) are hard-coded city tables. Derive them from the manifest or say "plus one config line".
   - "129/129 verified … character-for-character" next to "39 whitespace-normalised" (see item 12).
8. **Test-shaped id assignment.** `align_test_ids` renames records to the change-test ids. This is legitimate, but explain it, or it looks like fitting to the test.
9. **Missing T6 and missing Newark rules.** Newark has zero rules: judges will open a Newark address and see five "no rule found" cards, with rent control the obvious absence.
10. **Overprecise numbers.** Confidence values such as 0.98 suggest calibration that does not exist. Label it "model-reported confidence, capped by source type".

Not red flags (good): "Not legal advice" on every screen; no evasion advice in the summaries (I checked the plain-language text); public data only; the custom lookup sends the address only to the Census geocoder; GitHub links point to `main`, which exists; `METHOD_NOTE.md` and `README.md` exist; the live URL works.
