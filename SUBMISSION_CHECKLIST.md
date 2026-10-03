# Submission checklist (deadline 2026-10-04 16:15 Europe/Kyiv, grace included)

Two submissions are required: the **HackOS platform form** and the **Google Form** linked at the top of the platform page.

## Platform form fields
- [ ] **Project name:** Lexmap
- [ ] **Challenge:** Rental Housing Law Navigator (RealPage)
- [ ] **GitHub repository:** https://github.com/suvyakth/lexmap
- [ ] **Live project URL:** https://suvyakth.github.io/lexmap/
- [ ] **Team photo:** JPG, PNG or WebP, ≤ 10 MB
- [ ] **Team introduction video:** MP4 or MOV, ≤ 60 s ([script](VIDEO_SCRIPTS.md#1-team-introduction--60-s-camera-on-you-or-a-photo--voice))
- [ ] **Product demo video:** ≤ 60 s ([script](VIDEO_SCRIPTS.md#2-product-demo--60-s-screen-recording-of-the-live-site))
- [ ] **Technical walkthrough video:** ≤ 60 s, showing the self-check score and T1–T5 ([script](VIDEO_SCRIPTS.md#3-technical-walkthrough--60-s-screen-recording-of-github--terminal))
- [ ] Click **Save draft** after each upload, then **Submit project**

## Google Form
- [ ] Same links and videos as above. Paste the one-paragraph description below if it asks for one.

## Files judges look for (all in the repo)
- `submission/rules.json`, `submission/lookups.json`, `submission/changes.json`
- `README.md` (how to run), `METHOD_NOTE.md` (one-page method note)
- `submission/selfcheck_report.md` (scores), `submission/audit_log.jsonl`

## One-paragraph description (copy and paste)
Lexmap turns 67 documents of real state and city housing law into executable rules. It answers, for any address in California, New Jersey or Massachusetts and for any date, which rent-cap, just-cause, deposit, fee, screening and algorithmic-pricing rules apply. Each answer quotes the source verbatim. An LLM only reads the law: it extracts each rule with machine-readable coverage logic, every quote is verified character-for-character, and a second model reconciles sources and QA-checks every cut-off. A deterministic three-valued evaluator then decides "applies / unknown / superseded / not yet effective / pending". It names the missing fact instead of guessing, and flags conflicts such as the NJ FAIR Act preempting city bans. All five change tests pass, the 44-check self-check passes, and every model call is cached, so the whole submission reproduces offline. Not legal advice.
