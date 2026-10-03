# Lexmap: method note (one page)

**Question.** For any apartment address: which housing rules apply on a given date, and how do law changes affect the answer? Every answer must cite its source text.

**Core idea.** The LLM *reads law*. It never decides whether a rule applies. Each extracted rule carries machine-readable coverage logic, and a deterministic three-valued evaluator applies it to building facts. Answers are therefore reproducible, explainable and identical for every run and every date.

## Pipeline
1. **Corpus.** We read 54 official corpus texts and 13 organiser-listed secondary pages, fetched once. Code publishers marked "check-terms" were not fetched. Navigation lines that repeat across one site's pages are dropped. Text is never rewritten, and no document is excluded by hand.
2. **Extraction.** One model call per document (Claude Sonnet 5.5) returns schema records plus `coverage_logic`. The logic is a predicate tree over certificate-of-occupancy date, year built, units, property type, owner facts, or a named "other fact". Validation enforces the schema and computes "first day of the Nth month after enactment" dates in code. Every quote is located in the **raw** file and stored as its exact characters. Unlocatable quotes are re-selected or rejected.
3. **Reconciliation.** Candidates are grouped by jurisdiction and category. Claude Opus 5.5 merges records of the same law, preferring official sources. Citations are reduced to their primary form; the full text is kept.
4. **Legal QA.** An independent pass reviews each rule against its own source excerpts and sibling rules. It checks cut-off direction, status and dates, landlord vs municipality level, citation, city-limited state statutes, event-only scope (demolition, conversion), and whether any source disagreement is still open. It may change only whitelisted fields, and every change is logged. It corrected 32 of 56 records.
5. **Re-sourcing.** Where a rule's quote comes from a law-firm or news page, an official document of the same jurisdiction is searched for a passage stating the same requirement. A found passage is verified and becomes the primary quote.
6. **Graph.** Ids follow `<JUR>-<CAT>-<nn>`, and the seven names used by the change tests are aligned to their records. That is a rename only. State rules link to local rules they yield to, giving `superseded`. Preemption by core state laws flags local rules for review (NJ FAIR Act vs Jersey City and Hoboken). State laws exempting buildings from local rules remove them (NJ 30-year new-construction exemption).
7. **Addresses.** The U.S. Census Geocoder gives the legal Incorporated Place. Matches with a different house number are rejected. 487 of 500 are matched; 13 fall back to the mailing city and are flagged. Out-of-state owner ZIPs are ignored. Facts are **intervals**: year built maps to a certificate-of-occupancy date somewhere in that year, and unit lower bounds come from assessor codes. A unit count that contradicts the assessor class is not used.
8. **Evaluation.** Rules are dropped if failed, repealed, municipality-only, out of jurisdiction, or outside their `applies_only_in` cities. Then coverage and exemption are checked: false means omitted. Then `pending` or `not_yet_effective` by date. Then state exemptions of local rules. Then `superseded` if a local rule applies. Remaining unknowns give `unknown` with the missing fact named; everything else is `applies`. Event-only rules are shown on the site but not listed in `lookups.json`.
9. **Change tracking.** T1–T5 are computed generically from `change_tests.json`. Any organiser hour-16 file dropped in `data/hour16/` becomes corpus plus an automatic T6. This was rehearsed: effective date 2027-03-01 correct, 45 affected addresses. `whatif.py` runs any new law live.

## Evaluation
No `score.py` or dev key was in our pack, so `selfcheck.py` implements 44 checks from the brief, and all pass:
- Schema validity, 129 / 129 quotes located verbatim, and all 500 addresses.
- Rules only inside their geocoded jurisdiction, failed measures never reported, and every `unknown` naming its fact.
- T1–T5 expected sets plus T3's 90 conflict flags, and no rent cap in Massachusetts.

96% of `applies` answers quote official corpus text. The browser engine matches Python on 2,000 / 2,000 answers, and 129 unit and end-to-end tests pass. Independent reviewer agents audited the rules against their sources and scored the build against the rubric. Their findings drove the QA scope, city-limit, geocoding and re-sourcing stages.

## Responsible AI
- "Not legal advice" appears on every screen, and every answer has an as-of date.
- Enacted, not-yet-effective, pending and failed measures stay separate.
- Answers say `unknown` instead of guessing.
- Only 3 rules carry conflict flags, all genuinely open questions. Resolved discrepancies stay visible.
- Secondary-only rules are capped at 0.6 confidence and say so in their answers.
- EN/ES summaries are discarded if they contain any number not in the record.
- The audit log records source hashes, model-call hashes, rejected candidates and every answer.
- Public data only.

## Limitations and next steps
The corpus has no ordinance text for Newark, nor for Hoboken and Jersey City rent control, and owner facts are absent. Lexmap shows these as gaps and unknowns. Next steps:
- Bill-status refresh from LegiScan or Open States.
- Re-extraction when a source hash changes.
- County parcel feeds for building facts.
- A reviewer UI for QA changes.
- New jurisdictions, each needing only documents plus one configuration line.
