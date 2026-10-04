# Build progress (for auto-resume)
Deadline: 2026-10-04 16:15 Europe/Kyiv. Plan: C:\Users\AcharyaSuvyakth\.claude\plans\enchanted-doodling-anchor.md
Live: https://suvyakth.github.io/lexmap/  Repo: https://github.com/suvyakth/lexmap

- [x] Pipeline: extract -> reconcile -> QA -> geocode -> lookup -> changes -> explain -> selfcheck -> site (python run.py)
- [x] Determinism: second run makes 0 model calls; cache pruned to used entries (python run.py --extract --prune-cache)
- [x] Browser engine docs/engine.js, parity 2000/2000 (node tests/parity.js); stub-DOM smoke test (node tests/smoke_app.js)
- [x] whatif.py + fictional Cambridge ordinance demo
- [x] README, METHOD_NOTE, VIDEO_SCRIPTS, SUBMISSION_CHECKLIST
- [x] GitHub Pages live
- [x] Apply findings from build/review_legal.md, build/review_judge.md, unit-test bug report (event scope, city limits, re-sourcing, geocode house numbers, T6 readiness)
- [x] Final numbers in README/METHOD_NOTE re-checked after last pipeline run
- [x] Final independent review round (regressions) and fixes: dates stage (amendments), coverage normalisation, confidence cap, no-rule reasons, unread-source notes, cache-miss exit code
- [x] CI reproduce workflow green (Linux, cache-only, byte-identical outputs)
- [x] Organisers confirmed: v5 is current, no score.py/dev key, hour-16 removed (T1–T5 only), citation metric = corpus text only. Hourly Drive check cancelled.
- [ ] Morning: user records 3 videos, team photo, submits platform + Google Form (SUBMISSION_CHECKLIST.md)
