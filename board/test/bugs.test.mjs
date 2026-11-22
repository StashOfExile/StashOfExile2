// Report a bug and Suggest a Feature (3.2.0): both post to /bugs. Runs the Worker's own bugReport (cut out of
// src/index.js) with GitHub and Discord faked: an idea becomes an [Idea] issue labelled enhancement, a bug stays a
// [Bug] issue, names and home folders are masked, and the daily limit counts both.      node board/test/bugs.test.mjs
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "../src/index.js"), "utf8");
const cut = (from, to) => src.slice(src.indexOf(from), src.indexOf(to));
const code = cut("const MATCHER", "const APPROVALS").replace(/export /g, "") +
  cut("const scrubText", "// ------------------------------------------------------------------ 2.137.0") +
  cut("async function bugReport", "// ------------------------------------------------------------------ 2.78.0");
const { RegExpMatcher, englishDataset, englishRecommendedTransformers } = await import("obscenity");

const raw = new DatabaseSync(":memory:");
raw.exec("CREATE TABLE bug_limits (ip TEXT PRIMARY KEY, n INTEGER NOT NULL, day TEXT NOT NULL)");
const wrap = (sql, args = []) => ({
  bind: (...a) => wrap(sql, a),
  run: async () => { raw.prepare(sql).run(...args); return {}; },
  first: async () => raw.prepare(sql).get(...args) ?? null,
});
const DB = { prepare: (sql) => wrap(sql) };

const sent = [];
const fakeFetch = async (url, opts) => {
  sent.push({ url, body: JSON.parse(opts.body) });
  if (url.includes("api.github.com")) return { ok: true, json: async () => ({ number: sent.length, html_url: `https://github.com/i/${sent.length}` }) };
  return { ok: true };
};
const lib = new Function("RegExpMatcher", "englishDataset", "englishRecommendedTransformers",
  "json", "fail", "readBody", "ipKey", "today", "fetch",
  `${code}; return { bugReport, textProblem, nameProblem, postProblem };`)(RegExpMatcher, englishDataset, englishRecommendedTransformers,
  (o, status = 200) => ({ status, body: o }), (status, msg) => ({ status, body: { error: msg } }),
  async (req) => req.json, async () => "ip1", () => "2026-11-22", fakeFetch);

const req = (body) => ({ json: body, headers: { get: (k) => ({ "content-type": "application/json", "x-soe2": "1" })[k] } });
const env = { DB, GITHUB_TOKEN: "t", DISCORD_WEBHOOK: "https://discord/hook", BUGS_PER_DAY: "3" };

// an idea
let r = await lib.bugReport(req({ kind: "idea", title: "A cost per 10 uses", body: "Show it next to Cost per map. C:\\Users\\Sam\\x Worm#1234", version: "3.2.0" }), env);
assert.equal(r.status, 201);
let gh = sent.find((s) => s.url.includes("github")).body;
assert.equal(gh.title, "[Idea] A cost per 10 uses");
assert.deepEqual(gh.labels, ["enhancement", "from the app"]);
assert.match(gh.body, /Sent from StashOfExile2 3\.2\.0 \(Suggest a Feature\)\./);
assert.ok(!gh.body.includes("Sam") && !gh.body.includes("Worm#1234"), "names and home folders masked");
assert.match(sent.find((s) => s.url.includes("discord")).body.content, /^💡 New idea #1/);

// a bug, as before
sent.length = 0;
r = await lib.bugReport(req({ title: "Crash on start", body: "It closed by itself.", version: "3.2.0" }), env);
assert.equal(r.status, 201);
gh = sent.find((s) => s.url.includes("github")).body;
assert.equal(gh.title, "[Bug] Crash on start");
assert.deepEqual(gh.labels, ["bug", "from the app"]);
assert.match(sent.find((s) => s.url.includes("discord")).body.content, /^🐞 New bug report/);

// too short says what's missing, in the idea's words
r = await lib.bugReport(req({ kind: "idea", title: "Hi", body: "x" }), env);
assert.equal(r.status, 400);
assert.match(r.body.error, /what you'd like/);

// the daily limit counts ideas and bugs together
r = await lib.bugReport(req({ kind: "idea", title: "Third one", body: "Another idea for today." }), env);
assert.equal(r.status, 201);
r = await lib.bugReport(req({ kind: "idea", title: "Fourth one", body: "One more idea for today." }), env);
assert.equal(r.status, 429);
assert.match(r.body.error, /ideas today/);
console.log("bugs.test.mjs: ok");

// 3.2.0 owner: inappropriate words are refused, like usernames - in the title and the typed words, never in the log
{
  const before = sent.length;
  const env2 = { ...env, BUGS_PER_DAY: "99" };
  let r2 = await lib.bugReport(req({ title: "PENIS", body: "**What happened**\nnothing at all here\n\n**App** 3.2.0", version: "3.2.0" }), env2);
  assert.equal(r2.status, 400);
  assert.match(r2.body.error, /^Please keep it clean: reword "PENIS"/);
  r2 = await lib.bugReport(req({ kind: "idea", title: "A better map list", body: "**The idea**\nyou f4ggot make it\n\n**App** 3.2.0", version: "3.2.0" }), env2);
  assert.equal(r2.status, 400);
  r2 = await lib.bugReport(req({ title: "Inventory not found", body: "**What happened**\nThe Assassin's homogeneous grid, 1488 exalted, then a Cocktail.\n\n**App** 3.2.0\n\n**App log**\nshit 1488 kkk", version: "3.2.0" }), env2);
  assert.equal(r2.status, 201, JSON.stringify(r2.body));
  assert.equal(sent.length, before + 2);                     // only the clean one reached GitHub and Discord
  assert.equal(lib.textProblem("my tranny build"), 'Please keep it clean: reword "tranny" and send again.');
  assert.equal(lib.textProblem("Hitler's map"), 'Please keep it clean: reword "hitler" and send again.');
  assert.equal(lib.textProblem("Therapist, Raccoon, Spice and a Torpedo"), null);
  for (const bad of ["pen1s", "P3nis", "p3n1s", "p e n i s", "p.e.n.i.s", "p-e-n-i-s", "P 3 N 1 S", "peeeenis", "pénis",
    "f*ck", "phuck", "c u n t", "cvnt", "kunt", "n1gg3r", "fa66ot", "sp1c", "n4zi", "kys", "kill urself", "Hang your self"])
    assert.ok(lib.textProblem(`my ${bad} here`), bad);
  for (const ok of ["the pen is broken", "analysis", "cumulative", "assassin", "Sextant", "Cockatrice", "Scunthorpe",
    "Nigeria", "Niggle", "Nazir", "spicy", "a b c", "T 1 6 map", "i hit 1 4 8 8 dmg", "kill your self-cast",
    "I'm off to die in the Trial", "Titan", "harass"])
    assert.equal(lib.textProblem(ok), null, ok);
}
// 3.2.1 owner: racist words and slurs are refused in names, reports, ideas and every typed text in a post
for (const bad of ["nigger", "n1gger", "N1GG3R", "n i g g e r", "n.i.g.g.e.r", "niqqer", "niqqa", "nigga", "nibba",
  "nigguh", "kike", "kyke", "chink", "gook", "spic", "spik", "wetback", "beaner", "raghead", "coon", "jigaboo",
  "towelhead", "paki", "faggot", "f4ggot", "tranny", "retard", "heil hitler", "sieg heil", "kkk", "white power",
  "slant eye", "zipperhead", "go back to africa"]) {
  assert.ok(lib.textProblem(`you ${bad}`), bad);
  assert.ok(lib.nameProblem(bad), bad);
}
assert.ok(lib.nameProblem("1488"));
for (const ok of ["I hit 1488 damage", "Raccoon", "cocoon", "Pakistan", "spike", "Kyle", "nibbler", "the wet backpack", "Nigeria"])
  assert.equal(lib.textProblem(ok), null, ok);
assert.ok(lib.postProblem({ name: "Clean name", steps: ["run maps", "kill the n1gger boss"] }));
assert.ok(lib.postProblem({ summary: "p e n i s" }));
assert.equal(lib.postProblem({ name: "Breach farm", regex: "!ass|pen", items: [{ base: "Cockatrice", mods: ["+1 kkk"] }] }), null);
console.log("bugs: clean words ok");

