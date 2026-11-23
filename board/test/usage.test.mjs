// The usage count (3.3.0): only the app at 3.1 or newer is counted, and rows from older versions stay out.
//      node board/test/usage.test.mjs
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "../src/index.js"), "utf8");
const code = src.slice(src.indexOf("function countedVersion"), src.indexOf("async function mapRatings"));

const raw = new DatabaseSync(":memory:");
raw.exec("CREATE TABLE usage_pings (pid TEXT PRIMARY KEY, last INTEGER NOT NULL)");
raw.exec("ALTER TABLE usage_pings ADD COLUMN ok INTEGER NOT NULL DEFAULT 0");
let T = 1_000_000;
raw.prepare("INSERT INTO usage_pings (pid, last) VALUES (?, ?)").run("an-older-app", T);      // from before 3.3.0
const wrap = (sql, args = []) => ({
  bind: (...a) => wrap(sql, a),
  run: async () => { raw.prepare(sql.replace(/\?\d/g, "?")).run(...args); return {}; },
  first: async () => raw.prepare(sql).get(...args) ?? null,
  _go: () => {
    const n = (sql.match(/\?1|\?2/g) || []).length ? sql.replace(/\?1/g, "@a").replace(/\?2/g, "@b") : sql;
    return n === sql ? raw.prepare(sql).run(...args) : raw.prepare(n).run({ a: args[0], b: args[1] });
  },
});
const DB = { prepare: (sql) => wrap(sql), batch: async (list) => list.forEach((x) => x._go()) };
const env = { DB };
const json = (o, status = 200) => ({ status, body: o });
const now = () => T;
const sha256 = async (x) => "h" + x;
const allowance = async () => true;
const { countedVersion, usagePing, usageCount } =
  new Function("json", "now", "sha256", "allowance", code + "; return { countedVersion, usagePing, usageCount };")(
    json, now, sha256, allowance);

for (const [ua, ok] of [["StashOfExile2/3.1.0 (contact: x)", true], ["StashOfExile2/3.3.0", true],
  ["StashOfExile2/4.0.0", true], ["StashOfExile2/3.0.9", false], ["StashOfExile2/2.143.0", false],
  ["curl/8", false], [null, false]]) assert.equal(countedVersion(ua), ok, String(ua));

const req = (ua, id) => ({ json: async () => ({ id }), headers: { get: (k) => (k === "User-Agent" ? ua : "1.2.3.4") } });
assert.deepEqual((await usageCount(env)).body, { online: 0, week: 0 }, "a row from an older app is not counted");
assert.deepEqual((await usagePing(req("StashOfExile2/3.0.5", "a".repeat(32)), env)).body, { online: 0, week: 0 });
assert.deepEqual((await usagePing(req("StashOfExile2/3.3.0", "b".repeat(32)), env)).body, { online: 1, week: 1 });
assert.deepEqual((await usagePing(req("StashOfExile2/3.3.0", "b".repeat(32)), env)).body, { online: 1, week: 1 });
T += 20 * 60;
assert.deepEqual((await usageCount(env)).body, { online: 0, week: 1 }, "online is the last 15 minutes");
assert.equal((await usagePing(req("StashOfExile2/3.3.0", "nope"), env)).status, 400);
console.log("usage count: ok");
