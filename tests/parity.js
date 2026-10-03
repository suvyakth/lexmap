// Parity test: the browser engine (docs/engine.js) must give exactly the same answers as the
// Python engine (lexmap/lookup.py) for every sample address at every fixture date.
//   node tests/parity.js
const fs = require("fs");
const path = require("path");
const { Engine } = require("../docs/engine.js");
const root = path.join(__dirname, "..");
const rules = JSON.parse(fs.readFileSync(path.join(root, "docs/data/rules.json"), "utf8"));
const addrs = JSON.parse(fs.readFileSync(path.join(root, "docs/data/addresses.json"), "utf8"));
const fx = JSON.parse(fs.readFileSync(path.join(__dirname, "parity_fixtures.json"), "utf8"));
const eng = new Engine(rules);
let total = 0, bad = 0;
for (const [asOf, expected] of Object.entries(fx)) {
  for (const a of addrs) {
    const got = eng.lookup({ stack: a.stack, facts: a.facts }, asOf).map((e) => [e.team_rule_id, e.result, e.conflict_flag, e.event_only]);
    const want = expected[a.id];
    total++;
    if (JSON.stringify(got) !== JSON.stringify(want)) {
      bad++;
      if (bad <= 5) console.log("MISMATCH", asOf, a.id, "\n  js:", JSON.stringify(got), "\n  py:", JSON.stringify(want));
    }
  }
}
console.log(`parity: ${total - bad}/${total} (address, date) lookups identical`);
process.exit(bad ? 1 : 0);
