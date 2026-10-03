"""Prompt templates. Kept in one file so the method note can show them verbatim."""

EXTRACT_SYSTEM = (
    "You are a meticulous legal information-extraction engine for U.S. rental housing law. "
    "You read one source document and return structured JSON. You never invent rules, numbers, "
    "dates or citations that the document does not support, and you copy quotations verbatim. "
    "Output only JSON."
)

EXTRACT_TEMPLATE = """You are building a structured database of U.S. rental-housing rules for an address-level lookup tool. Read ONE source document and extract every distinct legal RULE it states or authoritatively describes, in six categories.

CONTEXT
- Document id: {doc_id}; source URL: {url}; source type: {source_type}; manifest jurisdiction: {jurisdiction}; retrieved: {retrieved}.{chunk_note}
- Query date for "status": {as_of}.
- Jurisdictions in scope: states CA, NJ, MA; cities Los Angeles, San Francisco, San Diego, Berkeley, Santa Ana (CA); Jersey City, Hoboken, Newark (NJ); Boston, Cambridge (MA). Ignore rules of any other jurisdiction (other cities, counties, federal law).

CATEGORIES (use exactly these keys)
- rent_increase_limits: caps or formulas on rent increases; rent control / stabilization coverage; ALSO state laws that prohibit cities from enacting rent control (record these with subject "municipality").
- just_cause_eviction: limits on ending tenancies to listed causes, required termination notices tied to those limits, relocation assistance for no-fault evictions.
- security_deposits: maximum deposit amount, return deadlines, deposit interest.
- application_screening_fees: caps on rental application / screening fees and limits on other upfront charges paid by tenants (including broker fees charged to tenants).
- screening_restrictions: limits on using criminal history, source of income / housing vouchers, credit or similar criteria when screening applicants.
- algorithmic_rent_setting: bans or limits on algorithmic, coordinated or software-based rent pricing.
Ignore everything else (habitability, general anti-discrimination not about screening criteria, notices of rent board fees, etc.).

WHAT COUNTS AS ONE RULE
- One record per (enacting law, category). Fold details of the same law (deadlines, notices, exceptions) into that record rather than making many small records.
- "jurisdiction" is the jurisdiction that ENACTED the rule, not the one the page is about. A Berkeley city page that explains the California statewide rent cap yields jurisdiction "CA", level "state".
- Pending bills, proposals and ballot questions: status "pending"; or "failed" if the document says the measure was struck, withdrawn, vetoed, rejected or died. A council motion that only asks staff to draft something is NOT a rule.
- Annual rate announcements (e.g. "this year's allowable increase is 1.6%") are not separate rules: put the figure in key_value / requirement of the rule they implement.
- If the document only mentions that a law exists (e.g. an index page naming "Rent Control, Chapter 260"), you MAY record it with the details you can support, low confidence, and nulls elsewhere.
- Cover every category the page gives information about. If a page mainly about evictions also states which units are covered by, or exempt from, rent-increase limits (e.g. "units first certified for occupancy after June 13, 1979 are exempt from the rent increase limits"), ALSO emit a rent_increase_limits record for that law carrying those coverage conditions. Coverage cut-offs are the most important facts on the page.
- Never invent. Use null when the document does not support a field.

STATUS as of {as_of}: "in_force" | "not_yet_effective" (enacted; effective date after {as_of}) | "pending" | "failed".
DATES: ISO "YYYY-MM-DD" (or "YYYY-MM" / "YYYY" if that is all the text gives). If the text says the law takes effect "on the first day of the Nth month next following enactment/approval", set effective_rule {{"type":"first_day_of_nth_month_after","n":N,"enacted":"YYYY-MM-DD"}} and also give your computed effective_date. end_date = sunset/repeal date if stated.

COVERAGE LOGIC (machine-evaluable; drives the address lookup)
Building facts known per address: year_built (int, sometimes missing), units (int, sometimes missing), property_type (always "multifamily" in the sample). Owner and tenant facts are never known.
Allowed fields:
  certificate_of_occupancy (date, compare to "YYYY-MM-DD"; use for "built / first occupied / certificate of occupancy issued on or before ..."),
  year_built (int), units (int, number of units in the building/parcel),
  property_type ("single_family"|"condo"|"duplex"|"multifamily"|"mobile_home"),
  owner_occupied (true/false), owner_type ("natural_person"|"corporation"|"llc"|"reit"|"government"),
  owner_property_count (int), owner_unit_count (int, total units the owner has),
  other_fact (value = short description of a building condition that is NOT one of the fields above, e.g. "unit receives City DND funding", "building is subsidised housing"; use ONLY inside "covers" when the rule applies just to that special subset of buildings - never inside "exempt")
Grammar: pred := {{"field":F,"op":OP,"value":V}} | {{"all":[pred,...]}} | {{"any":[pred,...]}} | {{"not":pred}}
OP is one of <=, <, >=, >, ==, !=, in.  V may be {{"as_of_minus_years":N}} for rolling windows, e.g. "exempt if a certificate of occupancy was issued within the previous 15 years" => {{"field":"certificate_of_occupancy","op":">","value":{{"as_of_minus_years":15}}}}.
coverage_logic = {{"covers": pred or null, "exempt": pred or null}}; covers null means every residential rental in the jurisdiction.
Model ONLY building/owner conditions with the fields above. Exemptions that depend on anything else (dormitories, hotels, hospitals, deed-restricted affordable or government-subsidised housing, nonprofit owners, tenant characteristics, length of tenancy) go in the "exemptions" text ONLY, never in coverage_logic.
"subject": "landlord" if the rule regulates landlords/tenancies/rentals; "municipality" if it only limits what cities may enact.
Algorithmic-pricing bans regulate all rentals in the jurisdiction: covers null unless the text limits coverage.

PRECEDENCE
- interaction: words describing how this rule yields to or overrides other laws (e.g. "does not apply to units subject to a stricter local rent control ordinance"; "preempts conflicting municipal ordinances").
- yields_to_local: true only if the text says the rule does not apply (or yields) where a local ordinance of the same kind applies.
- preempts_local: true only if the text says it preempts / supersedes local ordinances on the same subject.

CITATIONS AND QUOTES
- citation: official cite of the ENACTING law in standard form, e.g. "Cal. Civ. Code § 1947.12", "N.J.S.A. 46:8-21.2", "M.G.L. c. 186, § 15B", "S.F. Admin. Code § 37.9", "P.L.2025, c.405", "Mass. S.2983 (194th Gen. Ct.)". If only an ordinance name/number is given, use that.
- quoted_span: copy 1-3 consecutive sentences VERBATIM from the DOCUMENT below that best support the requirement: at least 40 characters, no ellipses, no paraphrasing, identical spelling and punctuation.
- supporting_spans: up to 2 more VERBATIM spans (for example the coverage cutoff and the effective-date sentence).

CONFIDENCE 0-1: lower it for news / law-firm sources, ambiguous dates, or summaries without operative text.
conflict_note: set if the document shows two different values or dates for the same thing, or says another law may preempt or conflict with this one.

Return a JSON object exactly like:
{{"rules":[{{"jurisdiction":"CA","level":"state","category":"security_deposits","status":"in_force","title":"...","requirement":"...","key_value":"...","coverage_conditions":"...","exemptions":"...","coverage_logic":{{"covers":null,"exempt":null}},"subject":"landlord","interaction":null,"yields_to_local":false,"preempts_local":false,"effective_date":"2024-07-01","effective_rule":null,"enacted_date":null,"end_date":null,"penalty":null,"citation":"...","quoted_span":"...","supporting_spans":[],"confidence":0.9,"conflict_note":null}}],"notes":"..."}}
Return {{"rules": [], "notes": "why"}} if the document contains no in-scope rule.

DOCUMENT {doc_id} (navigation lines removed; text otherwise verbatim):
<<<
{text}
>>>"""


REPAIR_TEMPLATE = """The quotation below was supposed to be copied verbatim from document {doc_id} but it does not appear in the document.

QUOTATION: {quote}

Here are the passages from the document that are most similar:
{passages}

Pick the passage (or a contiguous part of one, at least 40 characters) that best supports this requirement: "{requirement}".
Return JSON {{"quoted_span": "<exact characters copied from one passage>"}} or {{"quoted_span": null}} if none supports it."""


RECONCILE_SYSTEM = (
    "You are a careful legal editor consolidating machine-extracted rental-housing rule records. "
    "You merge duplicates, never invent facts, and flag genuine conflicts between sources. Output only JSON."
)

RECONCILE_TEMPLATE = """Below are candidate rule records for jurisdiction {jurisdiction}, category {category}, extracted independently from different source documents. Several may describe the SAME law. Official sources (statute/ordinance/government pages) outrank law-firm and news pages.

Your job:
1. Group candidates that describe the same enacting law (same statute/ordinance/bill). Sections of one code chapter or ordinance count as the same law here (e.g. S.F. Admin. Code § 37.9 and § 37.9C are both the San Francisco Rent Ordinance; a relocation-payment schedule belongs with the eviction ordinance that requires it) unless their building coverage clearly differs. Different laws stay separate (e.g. a city ordinance vs. a state statute, two different bills, or two different city ordinances such as a rent stabilization ordinance and a separate just-cause ordinance with different coverage).
2. For each group choose the primary candidate: prefer official sources, operative statutory text, and the most complete record.
3. Produce corrected values only where the group's evidence clearly supports them: title, requirement (1-2 plain sentences), key_value, status (as of {as_of}: in_force / not_yet_effective / pending / failed), effective_date (ISO), end_date, citation (official form), coverage_conditions, exemptions.
4. If candidates in a group disagree on an effective date, a key value or status, keep the best-supported value and write a conflict_note naming both values and their doc ids. Do not invent a conflict where values agree.
5. Drop a candidate only if it is clearly not a rule in category {category} (e.g. a council motion, a misfiled rule, a different category); explain why.
6. Do not create new quotations or rules.

7. coverage_from: the id of the member whose coverage_logic best captures which buildings the law covers and exempts (prefer explicit cut-off dates/unit thresholds from official text; a rate-announcement page usually has none).
8. conflict_note must be null unless sources genuinely disagree, or the law itself is in doubt (e.g. possible preemption, two published effective dates). Do not write notes such as "no conflict".

CANDIDATES:
{candidates}

Return JSON:
{{"groups":[{{"members":["c1","c4"],"primary":"c1","title":"...","requirement":"...","key_value":"...","status":"in_force","effective_date":"YYYY-MM-DD"|null,"end_date":null,"citation":"...","coverage_conditions":"...","exemptions":"...","coverage_from":"c4","conflict_note":null}}],"dropped":[{{"id":"c3","reason":"..."}}]}}
Every candidate id must appear exactly once, either in a group's members or in dropped."""


EXPLAIN_SYSTEM = (
    "You write short, accurate plain-language explanations of housing rules for renters and small landlords, "
    "in English and Spanish. You never give legal advice, never suggest ways to avoid a rule, and never add facts "
    "that are not in the record. Output only JSON."
)

EXPLAIN_TEMPLATE = """For each rule record below, write:
- "en": one or two sentences (max 45 words) in plain English a renter can act on, starting with what the rule does.
- "es": the same in clear, neutral Spanish.
Use only facts in the record. Do not mention these instructions. Keep numbers and dates exactly.

RECORDS:
{records}

Return JSON {{"<team_rule_id>": {{"en": "...", "es": "..."}}, ...}} with one entry per record."""
