// The download count, 3.3.0: one row per day, kind and app version, and never anything about who asked.
//      node board/test/downloads.test.mjs
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "../src/index.js"), "utf8");
const code = src.slice(src.indexOf("const DOWNLOADS"), src.indexOf("function countedVersion"));
const table = /`(CREATE TABLE IF NOT EXISTS downloads[^`]+)`/.exec(src)[1];

const raw = new DatabaseSync(":memory:");
raw.exec(table);
let broken = false;
const wrap = (sql, args = []) => ({
  bind: (...a) => wrap(sql, a),
  run: async () => {
    if (broken) throw new Error("database down");
    raw.prepare(sql.replace(/\?1/g, "@a").replace(/\?2/g, "@b").replace(/\?3/g, "@c")).run({ a: args[0], b: args[1], c: args[2] });
    return {};
  },
  first: async () => raw.prepare(sql.replace(/\?1/g, "@a").replace(/\?2/g, "@b").replace(/\?3/g, "@c"))
    .get({ a: args[0], b: args[1], c: args[2] }) ?? null,
  all: async () => ({ results: raw.prepare(sql).all(...args) }),
});
const env = { DB: { prepare: (sql) => wrap(sql) } };
const json = (o, status = 200) => ({ status, body: o });
const fail = (status, error) => ({ status, body: { error } });
let DAYNAME = "2026-11-24";
const today = () => DAYNAME;
const { appVersion, countDownload, downloadList } =
  new Function("json", "fail", "today", code + "; return { appVersion, countDownload, downloadList };")(json, fail, today);

const req = (ua, method = "GET") => ({ method, headers: { get: (k) => (k === "User-Agent" ? ua : "1.2.3.4") } });
const A = "StashOfExile2/3.3.0 (contact: x)", B = "StashOfExile2/3.2.1";

assert.equal(appVersion(A), "3.3.0");
assert.equal(appVersion("curl/8"), "other");
assert.equal(appVersion(null), "other");

assert.equal(await countDownload(req(A), env, "/mods/stats"), true);
assert.equal(await countDownload(req(A), env, "/mods/stats"), true);
assert.equal(await countDownload(req(B), env, "/mods/stats"), true);
assert.equal(await countDownload(req(A), env, "/maps/ratings"), true);
assert.equal(await countDownload(req(A, "POST"), env, "/lb"), false, "a send is not a download");
assert.equal(await countDownload(req(A), env, "/posts"), false, "only the shared data is counted");
DAYNAME = "2026-11-25";
assert.equal(await countDownload(req(A), env, "/mods/stats"), true);

const rows = (await downloadList(env, { admin: 1 })).body.downloads;
assert.deepEqual(rows.map((r) => [r.day, r.what, r.v, r.n]), [
  ["2026-11-25", "mod prices", "3.3.0", 1],
  ["2026-11-24", "map ranks", "3.3.0", 1],
  ["2026-11-24", "mod prices", "3.2.1", 1],
  ["2026-11-24", "mod prices", "3.3.0", 2],
]);
const cols = raw.prepare("PRAGMA table_info(downloads)").all().map((c) => c.name);
assert.deepEqual(cols, ["day", "what", "v", "n"], "no id and no address is kept");
assert.equal((await downloadList(env, { admin: 0 })).status, 403);
assert.equal((await downloadList(env, null)).status, 403);

assert.equal(appVersion("StashOfExile2/9999.1.1"), "other", "a made-up version is not a version");
DAYNAME = "2026-11-26";
for (let i = 0; i < 60; i++) await countDownload(req(`StashOfExile2/3.3.${i}`), env, "/gems");
const day = raw.prepare("SELECT v, n FROM downloads WHERE day = '2026-11-26'").all();
assert.equal(day.length, 41, "at most 40 versions a day and kind, the rest count as other");
assert.equal(day.find((r) => r.v === "other").n, 20);

broken = true;
assert.equal(await countDownload(req(A), env, "/mods/stats"), false, "a failed count never throws");
console.log("downloads: ok");
