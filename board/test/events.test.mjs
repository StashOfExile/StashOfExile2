// The Calendar's events, 3.3.0: anyone reads the live ones, only admins add, change or delete.
//      node board/test/events.test.mjs
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "../src/index.js"), "utf8");
const code = src.slice(src.indexOf("const EVENT_KINDS"), src.indexOf("// events: end"));
const table = /`(CREATE TABLE IF NOT EXISTS events[^`]+)`/.exec(src)[1];
assert.ok(readFileSync(join(here, "../schema.sql"), "utf8").includes("CREATE TABLE IF NOT EXISTS events"),
  "schema.sql has the table too");

const raw = new DatabaseSync(":memory:");
raw.exec(table);
const named = (sql) => sql.replace(/\?(\d)/g, "@p$1");
const params = (sql, args) => Object.fromEntries([...new Set(sql.match(/\?\d/g) ?? [])].map((q) => [`p${q[1]}`, args[Number(q[1]) - 1]]));
const wrap = (sql, args = []) => ({
  bind: (...a) => wrap(sql, a),
  run: async () => {
    const r = raw.prepare(named(sql)).run(params(sql, args));
    return { meta: { changes: Number(r.changes), last_row_id: Number(r.lastInsertRowid) } };
  },
  all: async () => ({ results: raw.prepare(named(sql)).all(params(sql, args)) }),
});
const env = { DB: { prepare: (sql) => wrap(sql) } };
const json = (o, status = 200) => ({ status, body: o });
const fail = (status, error) => ({ status, body: { error } });
let NOW = 1795000000;
const now = () => NOW;
const readBody = async (req) => req.body;
const textProblem = (t) => (String(t).includes("BADWORD") ? "Please keep it clean" : null);
const E = new Function("json", "fail", "now", "readBody", "textProblem",
  code + "; return { eventProblem, eventList, eventDrafts, eventSave, eventDelete, canPostEvents };")(json, fail, now, readBody, textProblem);

const admin = { id: "a1", admin: 1 }, user = { id: "u1", admin: 0 }, banned = { id: "a2", admin: 1, banned: 1 };
const good = { kind: "league", name: "  League   start ", start: NOW + 86400, end: 0, link: "https://example.com/x", note: "" };

// who may post
assert.equal(E.canPostEvents(admin), true);
for (const who of [user, banned, null, undefined]) assert.equal(E.canPostEvents(who), false);
for (const who of [user, banned, null]) {
  assert.equal((await E.eventSave({ body: good }, env, who)).status, 403);
  assert.equal((await E.eventDelete(env, who, 1)).status, 403);
  assert.equal((await E.eventDrafts(env, who)).status, 403);
}
assert.equal((await E.eventList(env)).body.events.length, 0, "nothing got in");

// what is refused
const bad = (over, want) => assert.match(E.eventProblem({ ...good, ...over }, NOW) ?? "ok", want, JSON.stringify(over));
bad({ kind: "mine" }, /pick a kind/);
bad({ kind: "anything" }, /pick a kind/);
bad({ name: "   " }, /needs a name/);
bad({ name: "x".repeat(61) }, /over 60/);
bad({ name: "a BADWORD" }, /keep it clean/);
bad({ note: "a BADWORD" }, /keep it clean/);
bad({ note: "n".repeat(401) }, /too long/);
bad({ start: "soon" }, /not a real date/);
bad({ start: 1.5 }, /not a real date/);
bad({ start: NOW + 10 * 366 * 86400 }, /not a real date/);
bad({ end: NOW }, /ends before/);
bad({ end: -1 }, /ends before/);
bad({ link: "http://example.com" }, /https/);
bad({ link: "javascript:alert(1)" }, /https/);
bad({ link: "https://x.com/ a" }, /https/);
bad({ link: "https://x.com/" + "a".repeat(300) }, /https/);
assert.equal(E.eventProblem(null, NOW), "bad event");
assert.equal(E.eventProblem([], NOW), "bad event");
assert.equal(E.eventProblem(good, NOW), null);
assert.equal(E.eventProblem({ ...good, link: "" }, NOW), null, "a link is not needed");
assert.equal((await E.eventSave({ body: { ...good, kind: "mine" } }, env, admin)).status, 400);

// an admin posts, changes and deletes
const made = await E.eventSave({ body: good }, env, admin);
assert.equal(made.status, 201);
assert.deepEqual(made.body.event, { id: "b1", kind: "league", name: "League start", start: NOW + 86400, end: 0,
  link: "https://example.com/x", note: "", by: "Official" });
let list = (await E.eventList(env)).body.events;
assert.deepEqual(list.map((e) => e.id), ["b1"]);
assert.deepEqual(Object.keys(list[0]).sort(), ["by", "end", "id", "kind", "link", "name", "note", "start"], "no admin id goes out");
const changed = await E.eventSave({ body: { ...good, name: "New name", kind: "race" } }, env, admin, 1);
assert.equal(changed.status, 200);
assert.equal((await E.eventList(env)).body.events[0].name, "New name");
assert.equal((await E.eventSave({ body: good }, env, admin, 99)).status, 404);

// a draft is not shown until an admin saves it
raw.prepare("INSERT INTO events (kind, name, start, status, source) VALUES ('drops', 'Draft drops', ?, 'draft', 'steam:1')").run(NOW + 5);
assert.deepEqual((await E.eventList(env)).body.events.map((e) => e.id), ["b1"]);
const drafts = (await E.eventDrafts(env, admin)).body.events;
assert.deepEqual(drafts.map((e) => [e.id, e.source]), [["b2", "steam:1"]]);
await E.eventSave({ body: { kind: "drops", name: "Draft drops", start: NOW + 5 } }, env, admin, 2);
assert.deepEqual((await E.eventList(env)).body.events.map((e) => e.id), ["b2", "b1"], "approved: live, earliest first");
assert.equal((await E.eventDrafts(env, admin)).body.events.length, 0);

// old ones drop off the list, a running one stays
raw.prepare("INSERT INTO events (kind, name, start, end) VALUES ('event', 'Long ago', ?, 0)").run(NOW - 40 * 86400);
raw.prepare("INSERT INTO events (kind, name, start, end) VALUES ('event', 'Still running', ?, ?)").run(NOW - 40 * 86400, NOW + 86400);
assert.deepEqual((await E.eventList(env)).body.events.map((e) => e.name), ["Still running", "Draft drops", "New name"]);

assert.equal((await E.eventDelete(env, admin, 1)).status, 200);
assert.equal((await E.eventDelete(env, admin, 1)).status, 404);
assert.ok(!(await E.eventList(env)).body.events.some((e) => e.id === "b1"));
console.log("events: ok");
