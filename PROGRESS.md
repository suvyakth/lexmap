# Build progress (for auto-resume)
Deadline: 2026-10-04 16:15 Europe/Kyiv. Plan: C:\Users\AcharyaSuvyakth\.claude\plans\enchanted-doodling-anchor.md
Live: https://suvyakth.github.io/lexmap/  Repo: https://github.com/suvyakth/lexmap

- [x] Pipeline: extract -> reconcile -> QA -> geocode -> lookup -> changes -> explain -> selfcheck -> site (python run.py)
- [x] Determinism: second run makes 0 model calls; cache pruned to used entries (python run.py --extract --prune-cache)
- [x] Browser engine docs/engine.js, parity 2000/2000 (node tests/parity.js); stub-DOM smoke test (node tests/smoke_app.js)
- [x] whatif.py + fictional Cambridge ordinance demo
- [x] README, METHOD_NOTE, VIDEO_SCRIPTS, SUBMISSION_CHECKLIST
- [x] GitHub Pages live
- [ ] Apply findings from build/review_legal.md, build/review_judge.md, unit-test bug report
- [ ] Final numbers in README/METHOD_NOTE re-checked after last pipeline run
