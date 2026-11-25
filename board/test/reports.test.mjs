// Data reports, 3.3.0: anyone reports a Codex row, admins review, hidden rows go to every app.
//      node board/test/reports.test.mjs
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "../src/index.js"), "utf8");
const code = src.slice(src.indexOf("// ------------------------------------------------------------------ 3.3.0 owner: data reports"),
  src.indexOf("// reports: end"));
const table = /`(CREATE TABLE IF NOT EXISTS data_reports[^`]+)`/.exec(src)[1];
assert.ok(readFileSync(join(here, "../schema.sql"), "utf8").includes("CREATE TABLE IF NOT EXISTS data_reports"));
const raw = new DatabaseSync(":memory:");
raw.exec(table);
const named = (sql) => sql.replace(/\?(\d)/g, "@p$1");
const params = (sql, args) => Object.fromEntries([...new Set(sql.match(/\?\d/g) ?? [])].map((q) => [`p${q[1]}`, args[Number(q[1]) - 1]]));
const wrap = (sql, args = []) => ({
  bind: (...a) => wrap(sql, a),
  run: async () => { const r = raw.prepare(named(sql)).run(params(sql, args)); return { meta: { changes: Number(r.changes) } }; },
  all: async () => ({ results: raw.prepare(named(sql)).all(params(sql, args)) }),
});
const env = { DB: { prepare: (sql) => wrap(sql) } };
let NOW = 1795000000, left = 3;
const R = new Function("json", "fail", "now", "readBody", "textProblem", "allowance", "ipKey", "canPostEvents",
  code + "; return { reportProblem, reportSend, reportList, reportAct, reportHidden };")(
  (o, status = 200) => ({ status, body: o }), (status, error) => ({ status, body: { error } }), () => NOW,
  async (r) => r.body, (t) => (String(t).includes("BADWORD") ? "Please keep it clean" : null),
  async () => left-- > 0, async () => "ip", (me) => !!me && !!me.admin && !me.banned);
const app = (body) => ({ body, headers: { get: (k) => ({ "content-type": "application/json", "x-soe2": "1" })[k] ?? null } });
const admin = { id: "a", admin: 1 }, user = { id: "u", admin: 0 };
const good = { page: "ratemods", ref: "unique:astramentis:# to all attributes", kind: "wrong", item: "Astramentis",
  line: "+(5-7) to all Attributes", note: "", version: "3.3.0" };

// what is refused
for (const [over, want] of [[{ page: "pricecheck" }, /cannot be reported/], [{ kind: "rude" }, /pick what/],
  [{ ref: " " }, /nothing to report/], [{ ref: "x".repeat(301) }, /nothing to report/], [{ note: "n".repeat(501) }, /too long/],
  [{ note: "BADWORD" }, /keep it clean/], [{ item: 5 }, /too long/]]) {
  assert.match(R.reportProblem({ ...good, ...over }) ?? "ok", want, JSON.stringify(over));
}
assert.equal(R.reportProblem(good), null);
assert.equal((await R.reportSend({ body: good, headers: { get: () => null } }, env)).status, 400, "only the app sends reports");

// the same row and kind again counts up; a new note replaces the old
assert.equal((await R.reportSend(app(good), env)).status, 201);
assert.equal((await R.reportSend(app({ ...good, note: "it is 5-8 now" }), env)).status, 201);
assert.equal((await R.reportSend(app({ ...good, kind: "removed" }), env)).status, 201);
assert.equal((await R.reportSend(app(good), env)).status, 429, "a daily limit per address");
let list = (await R.reportList(env, admin)).body.reports;
assert.deepEqual(list.map((r) => [r.kind, r.n, r.note]), [["wrong", 2, "it is 5-8 now"], ["removed", 1, ""]]);
const [W, RM] = list.map((r) => r.id);

// admins only
assert.equal((await R.reportList(env, user)).status, 403);
assert.equal((await R.reportAct({ body: { action: "hide" } }, env, user, W)).status, 403);
assert.deepEqual((await R.reportHidden(env)).body.hidden, []);

// hide reaches every app; fixed and dismissed leave the list; reopen brings it back
assert.equal((await R.reportAct({ body: { action: "hide" } }, env, admin, W)).body.status, "hidden");
assert.deepEqual((await R.reportHidden(env)).body.hidden, [["ratemods", good.ref]]);
assert.equal((await R.reportAct({ body: { action: "explode" } }, env, admin, W)).status, 400);
assert.equal((await R.reportAct({ body: { action: "fixed" } }, env, admin, RM)).status, 200);
list = (await R.reportList(env, admin)).body.reports;
assert.deepEqual(list.map((r) => r.status), ["hidden"], "fixed ones leave the list");
assert.equal((await R.reportAct({ body: { action: "reopen" } }, env, admin, W)).body.status, "open");
assert.deepEqual((await R.reportHidden(env)).body.hidden, [], "reopened: shown again");
assert.equal((await R.reportAct({ body: { action: "hide" } }, env, admin, 99)).status, 404);
left = 5;
await R.reportSend(app({ ...good, kind: "removed" }), env);
assert.equal(raw.prepare("SELECT status FROM data_reports WHERE id = ?").get(RM).status, "open", "reported again: open again");
console.log("reports: ok");
