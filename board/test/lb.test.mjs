// Leaderboard (3.0.6): up to 10 times per player per board entry. Runs the Worker's own lb code (cut out of
// src/index.js) against a real SQLite (node:sqlite) - the old table is migrated, sends are deduped and trimmed,
// GET /lb honours `per`.      node board/test/lb.test.mjs
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "../src/index.js"), "utf8");
const cut = (from, to) => src.slice(src.indexOf(from), src.indexOf(to));
const code = cut("async function lbMulti", "// 2.89.3, once: posts") + cut("const LB_CATS", "async function lbReport");
const DAY = 86400;
let clock = 1_800_000_000;

function makeDb() {
  const raw = new DatabaseSync(":memory:");
  const wrap = (sql, args = []) => ({
    bind: (...a) => wrap(sql, a),
    run: async () => { raw.prepare(sql).run(...args); return {}; },
    first: async () => raw.prepare(sql).get(...args) ?? null,
    all: async () => ({ results: raw.prepare(sql).all(...args) }),
    _run: () => raw.prepare(sql).run(...args),
  });
  return { raw, prepare: (sql) => wrap(sql),
    batch: async (stmts) => { raw.exec("BEGIN"); try { stmts.forEach((s) => s._run()); raw.exec("COMMIT"); } catch (e) { raw.exec("ROLLBACK"); throw e; } } };
}
const o = await import("obscenity");
const GAMEWORDS_SRC = "const GAMEWORDS = " + readFileSync(join(here, "../src/gamewords.json"), "utf8") + ";";
const clean = GAMEWORDS_SRC + src.slice(src.indexOf("const MATCHER"), src.indexOf("const APPROVALS")).replace(/export /g, "");
const lib = new Function("RegExpMatcher", "englishDataset", "englishRecommendedTransformers", "DAY", "now", "json", "fail",
  "readBody", "canReview", `${clean}; ${code}; return { lbMulti, lbSend, lbList };`)(o.RegExpMatcher, o.englishDataset,
  o.englishRecommendedTransformers,
  DAY, () => clock, (o, status = 200) => ({ status, body: o }), (status, msg) => ({ status, body: { error: msg } }),
  async (req) => req, () => false);

const OLD = `CREATE TABLE lb (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, cat TEXT NOT NULL,
  key TEXT NOT NULL, league TEXT NOT NULL, cls TEXT NOT NULL DEFAULT '', secs REAL NOT NULL, level INTEGER NOT NULL DEFAULT 0,
  deaths INTEGER NOT NULL DEFAULT 0, at INTEGER NOT NULL, sent INTEGER NOT NULL, reports INTEGER NOT NULL DEFAULT 0,
  hidden INTEGER NOT NULL DEFAULT 0, UNIQUE (user_id, cat, key, league, cls));
CREATE INDEX lb_board ON lb (cat, key, league, hidden, secs);
CREATE TABLE lb_reports (lb_id INTEGER NOT NULL, user_id TEXT NOT NULL, reason TEXT, created INTEGER NOT NULL, PRIMARY KEY (lb_id, user_id));
CREATE TABLE reviews (target TEXT NOT NULL, user_id TEXT NOT NULL, vote TEXT NOT NULL, created INTEGER NOT NULL, PRIMARY KEY (target, user_id));
CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL, admin INTEGER NOT NULL DEFAULT 0, banned INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL);`;

const day = (n) => Math.floor(clock / DAY) * DAY - n * DAY;
const entry = (secs, over = {}) => ({ cat: "map", key: "Citadel", secs, league: "L", cls: "Witch", level: 80, deaths: 0, at: day(1), ...over });
const send = (env, me, entries) => lib.lbSend({ entries }, env, me);
const list = (env, q, me = null) => lib.lbList(new URL("https://x/lb?" + new URLSearchParams(q)), env, me);
const rows = (env, where = "1=1") => env.DB.raw.prepare(`SELECT * FROM lb WHERE ${where} ORDER BY secs`).all();
const A = { id: "a" }, B = { id: "b" };
let env;
function fresh(schema = OLD) {
  env = { DB: makeDb(), LB_EVERY: 0 };
  env.DB.raw.exec(schema);
  env.DB.raw.exec("INSERT INTO users VALUES ('a','Anna',0,0,1),('b','Bo',0,0,1)");
}
const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test("old table: rows, ids and reports survive the migration; running it twice is harmless", async () => {
  fresh();
  env.DB.raw.exec(`INSERT INTO lb (id, user_id, cat, key, league, cls, secs, at, sent, reports, hidden) VALUES
    (7,'a','map','Citadel','L','Witch',400,${day(2)},1,2,1),(9,'b','map','Citadel','L','Witch',500,${day(2)},1,0,0)`);
  env.DB.raw.exec("INSERT INTO lb_reports VALUES (7,'b','x',1)");
  await lib.lbMulti(env);
  const r = rows(env);
  assert.deepEqual(r.map((x) => [x.id, x.secs, x.reports, x.hidden]), [[7, 400, 2, 1], [9, 500, 0, 0]]);
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) n FROM lb_reports").get().n, 1);
  await lib.lbMulti(env);                                          // (once more: nothing to do)
  assert.equal(rows(env).length, 2);
  await send(env, A, [entry(300), entry(350)]);                    // the new UNIQUE allows several per player
  assert.equal(rows(env, "user_id = 'a'").length, 3);
  const nextId = env.DB.raw.prepare("SELECT MAX(id) m FROM lb").get().m;
  assert.ok(nextId > 9, "ids keep counting up");
});

test("a send keeps the fastest 10 per key; the same run again is one row", async () => {
  fresh();
  await lib.lbMulti(env);
  const sent = Array.from({ length: 14 }, (_, i) => entry(100 + i * 10, { at: day(i) }));
  const res = await send(env, A, sent);
  assert.equal(res.body.ok, true);
  assert.deepEqual(rows(env, "user_id = 'a'").map((x) => x.secs), Array.from({ length: 10 }, (_, i) => 100 + i * 10));
  await send(env, A, sent.slice(0, 10));                           // re-send (every 15 minutes)
  assert.equal(rows(env, "user_id = 'a'").length, 10);
  await send(env, A, [entry(95, { at: day(0) })]);                 // a new best pushes the 10th out
  const r = rows(env, "user_id = 'a'");
  assert.equal(r.length, 10);
  assert.deepEqual([r[0].secs, r[9].secs], [95, 180]);
});

test("floor / ceil are still checked; other keys, leagues and classes are separate groups", async () => {
  fresh();
  await lib.lbMulti(env);
  const res = await send(env, A, [entry(5), entry(99999), entry(100), entry(100, { key: "Other" }),
    entry(100, { league: "M" }), entry(100, { cls: "Monk" })]);
  assert.deepEqual([res.body.kept, res.body.refused], [4, 2]);
  assert.equal(rows(env).length, 4);
});

test("the 10-minute limit still holds", async () => {
  fresh();
  env.LB_EVERY = 600;
  await lib.lbMulti(env);
  assert.equal((await send(env, A, [entry(100)])).status, 200);
  assert.equal((await send(env, A, [entry(100)])).status, 429);
  clock += 601;
  assert.equal((await send(env, A, [entry(100)])).status, 200);
});

test("a re-sent hidden run stays hidden (and keeps its reports)", async () => {
  fresh();
  await lib.lbMulti(env);
  await send(env, A, [entry(100)]);
  env.DB.raw.exec("UPDATE lb SET hidden = 1, reports = 3");
  await send(env, A, [entry(100)]);
  const r = rows(env);
  assert.deepEqual([r.length, r[0].hidden, r[0].reports], [1, 1, 3]);
});

test("a run that drops out of the 10 takes its reports with it", async () => {
  fresh();
  await lib.lbMulti(env);
  await send(env, A, Array.from({ length: 10 }, (_, i) => entry(100 + i, { at: day(i) })));
  const slow = rows(env).at(-1);
  env.DB.raw.prepare("INSERT INTO lb_reports VALUES (?, 'b', 'x', 1)").run(slow.id);
  await send(env, A, [entry(50)]);
  assert.equal(env.DB.raw.prepare("SELECT COUNT(*) n FROM lb_reports").get().n, 0);
});

test("GET /lb: up to 10 rows per player, fastest first, rank_in_player; per=1 is the old view", async () => {
  fresh();
  await lib.lbMulti(env);
  await send(env, A, Array.from({ length: 12 }, (_, i) => entry(100 + i * 10, { at: day(i) })));
  await send(env, B, [entry(105), entry(115, { at: day(2) })]);
  const all = (await list(env, { cat: "map", key: "Citadel" }, A)).body.rows;
  assert.equal(all.length, 12);                                    // 10 of Anna + 2 of Bo
  assert.deepEqual(all.slice(0, 4).map((r) => [r.name, r.secs, r.rank_in_player]),
    [["Anna", 100, 1], ["Bo", 105, 1], ["Anna", 110, 2], ["Bo", 115, 2]]);
  assert.ok(all.every((r, i) => i === 0 || all[i - 1].secs <= r.secs));
  assert.equal(all.find((r) => r.name === "Anna").mine, true);
  const one = (await list(env, { cat: "map", key: "Citadel", per: "1" })).body.rows;
  assert.deepEqual(one.map((r) => [r.name, r.secs, r.rank_in_player]), [["Anna", 100, 1], ["Bo", 105, 1]]);
  const capped = (await list(env, { cat: "map", key: "Citadel", per: "99" })).body.rows;
  assert.equal(capped.length, 12);                                 // (10 is the most)
  const three = (await list(env, { cat: "map", key: "Citadel", per: "3" })).body.rows;
  assert.equal(three.length, 5);                                 // (Anna 3 + Bo 2)
  for (const k of ["id", "name", "secs", "cls", "league", "level", "deaths", "at", "mine", "hidden"]) assert.ok(k in all[0], k);
});

test("GET /lb without key: the key list keeps its counts (players, best)", async () => {
  fresh();
  await lib.lbMulti(env);
  await send(env, A, [entry(100), entry(120, { at: day(3) })]);
  await send(env, B, [entry(90)]);
  const d = (await list(env, { cat: "map" })).body;
  assert.deepEqual(JSON.parse(JSON.stringify(d.keys)), [{ key: "Citadel", players: 2, best: 90 }]);
});

test("hidden runs are left out of the board, and don't count in a player's ranks", async () => {
  fresh();
  await lib.lbMulti(env);
  await send(env, A, [entry(100), entry(120, { at: day(3) })]);
  env.DB.raw.exec("UPDATE lb SET hidden = 1 WHERE secs = 100");
  const r = (await list(env, { cat: "map", key: "Citadel" })).body.rows;
  assert.deepEqual(r.map((x) => [x.secs, x.rank_in_player]), [[120, 1]]);
});

test("a new database (the new table) is left alone by lbMulti", async () => {
  fresh(readFileSync(join(here, "../schema.sql"), "utf8"));
  const before = env.DB.raw.prepare("SELECT sql FROM sqlite_master WHERE name = 'lb'").get().sql;
  assert.match(before, /UNIQUE \(user_id, cat, key, league, cls, secs, at\)/);
  await lib.lbMulti(env);
  assert.equal(env.DB.raw.prepare("SELECT sql FROM sqlite_master WHERE name = 'lb'").get().sql, before);
});

let failed = 0;
for (const [name, fn] of tests) {
  try { await fn(); console.log("ok   -", name); } catch (e) { failed++; console.log("FAIL -", name, "\n", e.stack); }
}
console.log(failed ? `${failed} failed` : `${tests.length} passed`);
process.exit(failed ? 1 : 0);
