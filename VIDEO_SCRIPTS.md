# Video scripts (each ≤ 60 seconds, MP4/MOV)

Record with any screen recorder (Windows: Snipping Tool's screen recording, or Xbox Game Bar with Win+Alt+R; macOS: Shift+Cmd+5). Use 1080p and zoom the browser to 125%; no music under the voice. Use the live site https://suvyakth.github.io/lexmap/. About 140 spoken words fit in 60 seconds. The brief asks for your scores in the videos, so the technical video shows the self-check report and T1–T5.

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
| 0–6 s | Home page, "Not legal advice" banner | "Lexmap: which housing rules apply at this address, today or on any date." |
| 6–17 s | Click the chip **San Francisco, 1926**. Point at the at-a-glance table, then open one **Source quote** | "A 1926 San Francisco building. Local rent control applies, so California's statewide cap is *superseded*. Every line quotes the law and when it was retrieved." |
| 17–25 s | Click **Los Angeles, built 1978** | "Built in the cut-off year. Year built isn't the certificate-of-occupancy date, so Lexmap says *unknown* and names the missing fact. It never guesses." |
| 25–33 s | Click **Dorchester → Boston**. Scroll to Rent increases | "Dorchester is legally Boston. Massachusetts bars local rent control, and the 2026 ballot question was struck. So no rent cap, and the card explains why." |
| 33–45 s | Click **Hoboken**, then the date chip **Jul 2, 2027** | "Hoboken's algorithmic-pricing ban applies today. Move the date to July 2027: New Jersey's FAIR Act takes effect, and Lexmap flags a possible preemption for human review." |
| 45–55 s | **What's changing** tab: T1–T5 green, then the what-if card | "All five change tests pass, with every affected address listed. A brand-new ordinance goes through the same pipeline, with its future effective date and the 45 buildings it would cover." |
| 55–60 s | Click **ES** for two seconds | "In English and Spanish. Not legal advice." |

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
