# Video scripts (each ≤ 60 seconds, MP4/MOV)

Record with any screen recorder (Windows: Snipping Tool's screen recording, or Xbox Game Bar with Win+Alt+R; macOS: Shift+Cmd+5). Use the live site https://suvyakth.github.io/lexmap/. Speak calmly; about 140 words fit in 60 seconds. The brief asks for your scores in the videos, so the technical video shows the self-check report and T1–T5.

---

## 1. Team introduction (≤ 60 s): camera on you, or a photo plus voice

> Hi, I'm **[your name]**, from **[school / city]**, and this is **Lexmap**, my entry for the RealPage Rental Housing Law Navigator challenge.
> I built it solo this weekend, with Claude as my pair programmer.
> I picked this challenge because housing law is public, but almost nobody can read it at the level that matters: one address.
> Renters don't know their rights, and small landlords don't know their obligations.
> Lexmap turns 67 documents of state and city law into executable rules. It answers any address with a quote from the law itself.
> My focus was trust: no invented rules, honest "unknown" answers, and an audit trail for every answer.
> Thanks for watching. The demo and the technical walkthrough are next.

---

## 2. Product demo (≤ 60 s): screen recording of the live site

| Time | Show | Say |
|---|---|---|
| 0–8 s | Home page, "Not legal advice" banner visible | "Lexmap answers one question: which housing rules apply at this address, and what's about to change." |
| 8–20 s | Click the chip **San Francisco, 1926** (A0016). Scroll the Rent increases section | "A 1926 San Francisco building. Local rent control applies, and California's statewide cap shows as *superseded* because the city ordinance governs. Every card quotes the law." Click **Source quote**. |
| 20–28 s | Click **San Francisco, 2019** (A0105) | "A 2019 building: no rent cap at all, because it's newer than both cut-offs. Just-cause protection still applies." |
| 28–38 s | Click **Los Angeles, built 1978** (A0107) | "Built in 1978, the cut-off year. Year built isn't the certificate-of-occupancy date, so Lexmap says *unknown* and names the missing fact. It doesn't guess." |
| 38–50 s | Click **Hoboken** (A0002). Click the date chip **Jul 2, 2027** | "Hoboken's local algorithmic-pricing ban applies today. Move the date to July 2027 and New Jersey's FAIR Act takes effect. Lexmap flags a possible preemption conflict for human review." |
| 50–60 s | Click the **What's changing** tab | "All five change cases are computed by the same engine, with every affected address listed. You can switch to Spanish too." Click **ES** for a second. |

---

## 3. Technical walkthrough (≤ 60 s): screen recording of GitHub and a terminal

| Time | Show | Say |
|---|---|---|
| 0–10 s | README "How it works" diagram on GitHub | "The model reads the law. It never decides what applies. Each rule is extracted with machine-readable coverage logic, for example certificate of occupancy after June 13, 1979." |
| 10–22 s | `submission/rules.json`, one rule with `quoted_span`, `coverage_logic`, `provenance` | "Every quote is verified character-for-character against the source file: 129 of 129. A second model merges sources, and an independent QA pass checks every cut-off's direction." |
| 22–35 s | Terminal: `python run.py` (finishes in ~1 s from cache), then `python -m lexmap.selfcheck` | "Every model call is cached by prompt hash, so the whole submission reproduces offline. Our self-check implements the brief's rules: 44 of 44 pass." |
| 35–47 s | Scroll `submission/selfcheck_report.md` to the **C** rows (T1–T5) | "T1 through T5 all match: CA flips on Jan 2, 2026. Hoboken and Jersey City stay inside city limits. The FAIR Act is not yet effective, with 90 conflict flags. The MA bills are pending, and there's no rent cap in Massachusetts." |
| 47–60 s | Terminal: `python run.py whatif data/whatif/fictional_cambridge_ordinance.txt --jurisdiction "Cambridge, MA"` | "A brand-new ordinance goes through the same pipeline. Here a fictional Cambridge one is extracted with its future effective date, and the 44 affected buildings are listed. Adding a jurisdiction is just documents plus one command." |

Tip: before recording, run each command once so the output is ready. `python run.py` needs no API key.
