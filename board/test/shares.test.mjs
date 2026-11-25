// Pooled prices, 3.3.0: one share per install, its weight capped, fading with time; gems take the middle price.
//      node board/test/shares.test.mjs
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createHash } from "node:crypto";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "../src/index.js"), "utf8");
const code = src.slice(src.indexOf("const BATCH_EVERY"), src.indexOf("// UI overhaul: the usage count"));
const seed = src.slice(src.indexOf("async function seedShares"), src.indexOf("// 3.0.6, once: leaderboard times"));
const tables = [...src.matchAll(/`(CREATE TABLE IF NOT EXISTS (?:mod_shares|base_shares|gem_shares)[^`]+)`/g)].map((m) => m[1]);
assert.equal(tables.length, 3);
const schema = readFileSync(join(here, "../schema.sql"), "utf8");
for (const t of ["mod_shares", "base_shares", "gem_shares"]) assert.ok(schema.includes(`CREATE TABLE IF NOT EXISTS ${t}`), t);

const raw = new DatabaseSync(":memory:");
for (const t of tables) raw.exec(t);
raw.exec(`CREATE TABLE contributors (cid TEXT PRIMARY KEY, last INTEGER, batches INTEGER);
  CREATE TABLE mod_prices (league TEXT, base TEXT, sid TEXT, n INTEGER, w REAL, slog REAL, batches INTEGER, updated INTEGER);
  CREATE TABLE base_prices (league TEXT, base TEXT, n INTEGER, w REAL, slog REAL, batches INTEGER, updated INTEGER);
  CREATE TABLE gem_prices (league TEXT, kind TEXT, level INTEGER, name TEXT, div REAL, n INTEGER, updated INTEGER);
  CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);`);
const named = (sql) => sql.replace(/\?(\d)/g, "@p$1");
const params = (sql, args) => Object.fromEntries([...new Set(sql.match(/\?\d/g) ?? [])].map((q) => [`p${q[1]}`, args[Number(q[1]) - 1]]));
const positional = (sql) => !/\?\d/.test(sql);
const wrap = (sql, args = []) => ({
  sql, args,
  bind: (...a) => wrap(sql, a),
  run: async () => (positional(sql) ? raw.prepare(sql).run(...args) : raw.prepare(named(sql)).run(params(sql, args))),
  first: async () => (positional(sql) ? raw.prepare(sql).get(...args) : raw.prepare(named(sql)).get(params(sql, args))) ?? null,
  all: async () => ({ results: positional(sql) ? raw.prepare(sql).all(...args) : raw.prepare(named(sql)).all(params(sql, args)) }),
});
const env = { DB: { prepare: (sql) => wrap(sql), batch: async (list) => { for (const s of list) await s.run(); } } };
let NOW = 1795000000;
const now = () => NOW;
const json = (o, status = 200) => ({ status, body: o });
const fail = (status, error) => ({ status, body: { error } });
const sha256 = async (t) => createHash("sha256").update(t).digest("hex");
const meta = {};
const B = new Function("json", "fail", "now", "readBody", "ipKey", "allowance", "sha256", "metaGet", "metaSet",
  code + seed + "; return { modBatch, modStats, gemPrices, middleGems, seedShares, pooled, SHARE_CAP, SHARE_FADE };")(
  json, fail, now, async (r) => r.body, async () => "ip", async () => true, sha256,
  async (_e, k) => meta[k] ?? null, async (_e, k, v) => { meta[k] = String(v); });

const cid = (i) => String(i).padStart(32, "a").replace(/[^a-f0-9]/g, "a").slice(0, 32);
const ids = Array.from({ length: 6 }, (_x, i) => (i.toString(16).repeat(32)).slice(0, 32));
const send = async (who, prices, extra = {}) => {
  const res = await B.modBatch({ body: { cid: who, league: "L", prices, ...extra } }, env);
  NOW += 46 * 60;                                     // the next send is allowed
  return res;
};
const stats = async () => (await B.modStats({ searchParams: new URLSearchParams("league=L") }, env)).body.stats;
const price = (rows, sid) => rows.find((r) => r[1] === sid);

// one install sending again and again holds one share and never more than the cap
for (let i = 0; i < 50; i++) await send(ids[0], [{ base: "Ring", sid: "explicit.a", med: 1000, n: 10 }]);
let share = raw.prepare("SELECT COUNT(*) AS c, MAX(w) AS w FROM mod_shares").get();
assert.equal(share.c, 1, "one row an install and a mod");
assert.ok(share.w <= B.SHARE_CAP + 1e-9, `weight capped, got ${share.w}`);
let s = price(await stats(), "explicit.a");
assert.equal(s[5], 1, "the app is told how many installs, not how many sends");
assert.ok(Math.abs(s[3] - 1000) < 1);

// five honest installs at 10 outweigh the one: the middle of many players
for (const who of ids.slice(1)) await send(who, [{ base: "Ring", sid: "explicit.a", med: 10, n: 10 }]);
s = price(await stats(), "explicit.a");
assert.equal(s[5], 6);
assert.ok(Math.abs(s[3] - 10) < 0.01, `the middle of the many, got ${s[3]}`);

// old weight fades: a share not renewed for the fade time is gone from the pool
NOW += B.SHARE_FADE + 60;
assert.equal(price(await stats(), "explicit.a"), undefined, "faded out");
await send(ids[2], [{ base: "Ring", sid: "explicit.a", med: 20, n: 5 }]);
s = price(await stats(), "explicit.a");
assert.equal(s[5], 1, "only the fresh share counts");
assert.ok(Math.abs(s[3] - 20) < 0.01);

// a share fades part way: half the fade time later it weighs half
NOW += B.SHARE_FADE / 2;
await send(ids[3], [{ base: "Ring", sid: "explicit.a", med: 80, n: 5 }]);
s = price(await stats(), "explicit.a");
assert.ok(Math.abs(s[3] - 80) < 0.01, `the half-faded share weighs less, got ${s[3]}`);

// a lift is the mod's middle over the base's middle
await send(ids[5], [], { bases: [{ base: "Ring", med: 4, n: 30 }] });
s = price(await stats(), "explicit.a");
assert.ok(Math.abs(s[4] - 20) < 0.01, `lift 80 / 4, got ${s[4]}`);

// bases are shared the same way
for (let i = 0; i < 20; i++) await send(ids[4], [], { bases: [{ base: "Ring", med: 5, n: 30 }] });
const b = raw.prepare("SELECT COUNT(*) AS c, MAX(w) AS w FROM base_shares WHERE cid = ?").get(await sha256(ids[4]));
assert.equal(b.c, 1);
assert.ok(b.w <= B.SHARE_CAP * 3 + 1e-9);

// gems: the middle of the installs' newest prices, never just the newest sender
const gem = (div) => ({ gems: [{ name: "fireball", kind: "skill", level: 20, div }] });
await send(ids[0], [], gem(1));
await send(ids[1], [], gem(1.2));
await send(ids[2], [], gem(500));
await send(ids[2], [], gem(900));                     // the same install again: still one voice
let g = (await B.gemPrices({ searchParams: new URLSearchParams("league=L") }, env)).body.gems;
assert.equal(g.length, 1);
assert.equal(g[0][3], 1.2, "the middle of 1, 1.2 and 900");
assert.equal(g[0][5], 3, "three installs");
await send(ids[3], [], gem(1.1));
g = (await B.gemPrices({ searchParams: new URLSearchParams("league=L") }, env)).body.gems;
assert.equal(g[0][3], 1.15, "an even count takes the two in the middle");
NOW += 15 * 86400;
assert.equal((await B.gemPrices({ searchParams: new URLSearchParams("league=L") }, env)).body.gems.length, 0, "old gem prices drop off");
assert.deepEqual(B.middleGems([]), []);

// what was learned before is kept once, as one share
raw.exec("DELETE FROM mod_shares; DELETE FROM base_shares; DELETE FROM gem_shares;");
raw.prepare("INSERT INTO mod_prices VALUES ('L', 'Amulet', 'explicit.b', 40, 400, ?, 90, ?)").run(400 * Math.log(7), NOW);
raw.prepare("INSERT INTO gem_prices VALUES ('L', 'skill', 20, 'spark', 2, 9, ?)").run(NOW);
await B.seedShares(env);
await B.seedShares(env);
const seeded = raw.prepare("SELECT cid, w, slog FROM mod_shares").all();
assert.equal(seeded.length, 1);
assert.equal(seeded[0].cid, "earlier");
assert.ok(seeded[0].w <= B.SHARE_CAP);
assert.ok(Math.abs(Math.exp(seeded[0].slog / seeded[0].w) - 7) < 1e-6, "its price is kept");
assert.equal(raw.prepare("SELECT COUNT(*) AS c FROM gem_shares").get().c, 1);
raw.exec("DELETE FROM mod_shares");
await B.seedShares(env);
assert.equal(raw.prepare("SELECT COUNT(*) AS c FROM mod_shares").get().c, 0, "once only");
console.log("shares: ok");
