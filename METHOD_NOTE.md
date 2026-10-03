# Lexmap: method note (one page)

**Question.** For any apartment address: which housing rules apply on a given date, and how do law changes affect the answer? Every answer must cite its source text.

**Core idea.** The LLM *reads law*. It never decides whether a rule applies. Each extracted rule carries machine-readable coverage logic, and a deterministic three-valued evaluator applies it to building facts. Answers are therefore reproducible, explainable and identical for every run and every date.

## Pipeline
1. **Corpus.** We read 54 official corpus texts and 13 organiser-listed secondary pages, fetched once. Code publishers marked "check-terms" were not fetched. Navigation lines that repeat across one site's pages are dropped. Text is never rewritten.
2. **Extraction (Module A).** One model call per document (Claude Sonnet 5.5) returns schema records plus `coverage_logic`. The logic is a predicate tree over certificate-of-occupancy date, year built, units, property type, owner facts, or a named "other fact". It also returns `subject` (landlord or municipality), precedence hints and verbatim quotes. Validation enforces the schema and computes "first day of the Nth month after enactment" dates in code. Each quote is located in the **raw** source file and replaced by the exact raw characters. A quote that cannot be found is re-selected from the closest passages or rejected.
3. **Reconciliation.** Candidates are grouped by jurisdiction and category. A stronger model (Claude Opus 5.5) merges records of the same law, prefers official sources, and writes a conflict note only for genuine disagreements. Deterministic checks then add date disagreements at matching precision and recompute status from dates.
4. **Legal QA.** An independent model pass reviews each consolidated rule against excerpts of its own sources and sibling rules. It may change only whitelisted fields: status, dates, subject, coverage logic, precedence flags and wording. Every change is re-validated and logged. It corrected 26 records, for example the direction of a cut-off, or replacing "unit subject to the RSO" with the RSO's actual 1978-10-01 cut-off.
5. **Graph.** Ids are stable, and the ids used by the change tests are aligned to the right records. State rules marked "yields to local" are linked to local rules of the same category, giving `superseded`. A state law that preempts local ordinances flags the affected local rules (NJ FAIR Act vs Jersey City and Hoboken). A municipality-level state law with coverage removes covered buildings from local rules (NJ new-construction exemption).
6. **Addresses (Module B).** The U.S. Census Geocoder gives the legal Incorporated Place. 487 of 500 addresses were matched; 13 fall back to the mailing city and are flagged. Out-of-state owner ZIPs are detected and ignored. Building facts are **intervals**. Year built maps to a certificate-of-occupancy date somewhere in that calendar year. Unit lower bounds come from assessor codes, never guesses.
7. **Evaluation.** The decision table runs in order: failed, repealed, municipality-only or out-of-jurisdiction rules are omitted. Then `pending`, then `not_yet_effective` (by date), then coverage, then exemption, then state exemptions of local rules, then `superseded` if a local rule applies, then `applies`. An unknown at any step gives `unknown`, with the missing fact named.
8. **Change tracking (Module C).** T1–T5 are computed generically from `change_tests.json`: as-of flips, jurisdiction boundaries, "if enacted" for pending bills, and negative tests. `whatif.py` runs any new ordinance through steps 2–7 and lists the addresses that change.

## Evaluation
No `score.py` or dev key was included in the pack we received, so `selfcheck.py` implements 44 checks from the brief. Examples: schema validity, quotes found verbatim (129/129), all 500 addresses, rules only inside their geocoded jurisdiction, failed measures never reported, every unknown naming its fact, T1–T5 expected sets, T3 conflict flags, and no rent cap in Massachusetts. All 44 pass. The browser engine matches the Python engine on 2,000 of 2,000 (address, date) answers. Unit tests pin down the cut-off-year rule, rolling windows and interval logic.

## Responsible AI
"Not legal advice" appears on every screen. Status always comes with an as-of date. Enacted, pending and failed measures stay separate. Answers are `unknown` rather than guesses. Conflicts and secondary-only sources (confidence 0.6 or lower) are flagged. Plain-language EN/ES summaries are discarded if they contain any number not in the rule record. The audit log records source hashes, model-call hashes, rejected candidates and every answer. Public data only.

## Limitations and next steps
Municipal code text for Hoboken, Newark and Jersey City is not in the corpus, and owner facts are absent. Lexmap shows these as gaps and unknowns. Next steps:
- Bill-status refresh from LegiScan or Open States.
- Re-extraction when a source hash changes.
- County parcel feeds for building facts.
- A reviewer UI that accepts or rejects QA changes.
- New jurisdictions, which need only documents plus one command.
