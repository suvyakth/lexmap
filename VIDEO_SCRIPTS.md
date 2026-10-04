# Video scripts (each ≤ 60 seconds, MP4/MOV)

Record with any screen recorder (Windows: Snipping Tool's screen recording, or Xbox Game Bar with Win+Alt+R; macOS: Shift+Cmd+5). Use 1080p and zoom the browser to 125%; no music under the voice. Use the live site https://suvyakth.github.io/lexmap/. About 140 spoken words fit in 60 seconds. The organisers asked that videos show the team's own system output and validation (not score.py), so the technical video shows our self-check report, T1–T5 and the tests.

---

## 1. Team introduction (≤ 60 s): camera on you, or a photo plus voice

> Hi, I'm **[your name]**, from **[school / city]**, and this is **Lexmap**, my entry for the RealPage Rental Housing Law Navigator challenge.
> I built it solo this weekend, with Claude as my pair programmer.
> I picked this challenge because housing law is public, but almost nobody can read it at the level that matters: one address.
> Renters don't know their rights, and small landlords don't know their obligations.
> Lexmap turns 67 documents of state and city law into executable rules. It answers any address, on any date, with a quote from the law itself.
> My focus was trust: no invented rules, honest "unknown" answers, and an audit trail behind every answer.
> Thanks for watching. The demo and the technical walkthrough are next.

---

## 2. Product demo (≤ 60 s): screen recording of the live site

| Time | Show | Say |
|---|---|---|
| 0–6 s | Landing page: headline, search box, feature cards | "Lexmap answers one question: which housing rules apply at this address, today or on any date." |
| 6–20 s | Click the chip **San Francisco, 1926**. Point at **What matters most at this address** | "For a renter it says what matters here: rent can rise at most 1.6% this year, because this building is older than San Francisco's 1979 cut-off. Each point cites the law; click it to see the exact quote." Click the citation. |
| 20–26 s | Click **Landlord** in the View-as switch | "Same building, worded for the landlord." |
| 26–38 s | Click **A shop in NJ (live)** | "Any real address works. Here New Jersey's public parcel records show it's a commercial property, so Lexmap says these rules don't apply instead of guessing." |
| 38–48 s | Type a house address, e.g. `387 Spring Valley Road, Paramus, NJ`, then answer **Does the owner live in the building?** | "When a fact is missing it asks one question, and every answer updates instantly." |
| 48–60 s | **What's changing** tab: the city coverage bars, then T1–T5 | "Advocates see who is protected city by city, and all five change tests pass. Not legal advice." |

---

## 3. Technical walkthrough (≤ 60 s): screen recording of GitHub and a terminal

| Time | Show | Say |
|---|---|---|
| 0–8 s | README "How it works" diagram | "The model only reads the law. A deterministic three-valued evaluator decides what applies." |
| 8–22 s | Terminal: `python run.py whatif data/whatif/fictional_cambridge_ordinance.txt --jurisdiction "Cambridge, MA" --live` (a real model call, about 10 s) | "Here's a new ordinance going through the pipeline live, with no hand-coding. The quote is verified against the file, the effective date is computed, and the affected buildings are listed." |
| 22–32 s | `submission/rules.json`: one rule showing `coverage_logic`, `quoted_span`, `provenance.qa` | "Each rule compiles to executable coverage logic. Then an independent QA pass checks every cut-off, its scope and its citation against the source." |
| 32–47 s | `submission/selfcheck_report.md`: the "44/44" line, then the T1–T5 rows | "Our scores: 44 of 44 self-checks pass. T1 to T5 all match, including 90 conflict flags for the FAIR Act. 96% of 'applies' answers quote the official corpus." |
| 47–55 s | Terminal: `python run.py` (say "cached replay"), then `node tests/parity.js` | "Every model call is cached by prompt hash, so the whole submission replays offline. The browser engine matches Python on all 2,000 answers." |
| 55–60 s | README "Scalability path" | "A new city needs only its documents and one config line." |

Tip: run each command once before recording. `python run.py` needs no API key. The `--live` what-if call uses your Claude Code login (or `OPENROUTER_API_KEY`).
