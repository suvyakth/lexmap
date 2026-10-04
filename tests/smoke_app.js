// Smoke test for docs/app.js without a browser: a tiny DOM stub records every innerHTML
// write, so all render paths (lookup, change tests, rules table, method) execute.
//   node tests/smoke_app.js
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = path.join(__dirname, "..", "docs");
const els = {};
function el(sel) {
  if (els[sel]) return els[sel];
  const e = {
    sel, innerHTML: "", textContent: "", value: sel === "#asof" ? "2026-10-01" : "", hidden: false, dataset: {},
    classList: { toggle() {}, add() {}, remove() {}, contains: () => false },
    addEventListener() {}, appendChild() {}, remove() {}, after() {}, closest: () => null,
    querySelector: (s) => el(sel + " " + s), querySelectorAll: () => [],
  };
  return (els[sel] = e);
}
const document = { querySelector: el, querySelectorAll: () => [], addEventListener() {}, body: el("body"), documentElement: { setAttribute() {}, removeAttribute() {} }, getElementById: () => null, createElement: () => el("new" + Math.random()) };
const fetch = async (u) => ({ json: async () => JSON.parse(fs.readFileSync(path.join(root, u), "utf8")) });
const ctx = { window: {}, document, fetch, history: { replaceState() {} }, location: { hash: process.argv[2] || "" },
  console, setTimeout, clearTimeout, Promise, Object, JSON, Math, Array, String, Number, Set, Map, Date, Infinity, isNaN, parseInt, encodeURIComponent,
  URLSearchParams, localStorage: { getItem: () => null, setItem() {} }, scrollTo() {}, scrollY: 0 };
ctx.window = ctx; ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root, "engine.js"), "utf8"), ctx);
vm.runInContext(fs.readFileSync(path.join(root, "app.js"), "utf8"), ctx);
setTimeout(() => {
  const r = els["#result"].innerHTML, ch = els["#changes"].innerHTML, rt = els["#rules-table"].innerHTML, m = els["#method"].innerHTML;
  const checks = [
    ["lookup rendered", r.includes("class=\"card addr\"")],
    ["six category sections", (r.match(/class="cat"/g) || []).length === 6],
    ["rule cards present", (r.match(/class="card rule /g) || []).length > 3],
    ["source quotes present", r.includes("<blockquote>")],
    ["change tests rendered (T1-T5)", ["T1", "T2", "T3", "T4", "T5"].every((x) => ch.includes(`<h3>${x} · `))],
    ["what-if ordinance card rendered", ch.includes("What-if") && ch.includes("fictional")],
    ["all change tests match", !ch.includes("check failed")],
    ["rules table rendered", rt.includes("<table>") && rt.includes("r-row")],
    ["method rendered", m.includes("Self-checks passing")],
    ["no 'undefined' text leaked", ![r, ch, rt, m].some((h) => />[^<]*\bundefined\b[^<]*</.test(h))],
    ["no NaN leaked", ![r, ch, rt, m].some((h) => /NaN/.test(h))],
  ];
  let bad = 0;
  for (const [n, ok] of checks) { console.log((ok ? "PASS " : "FAIL ") + n); if (!ok) bad++; }
  const shown = (r.match(/<div class="rid">([A-Z0-9-]+)/g) || []).map((x) => x.replace(/.*>/, ""));
  console.log("rules shown:", shown.join(" "));
  process.exit(bad ? 1 : 0);
}, 500);
