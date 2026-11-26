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
const env = { DB: { prepare: (sql) => wrap(sql) }, AUTO_EVENTS: "0" };   // the draft flow; AUTO_EVENTS on: below
const json = (o, status = 200) => ({ status, body: o });
const fail = (status, error) => ({ status, body: { error } });
let NOW = 1795000000;
const now = () => NOW;
const readBody = async (req) => req.body;
const textProblem = (t) => (String(t).includes("BADWORD") ? "Please keep it clean" : null);
const meta = {};
const metaGet = async (_e, k) => meta[k] ?? null;
const metaSet = async (_e, k, v) => { meta[k] = String(v); };
let FEEDS = {}, asked = [], steamDown = false;
const fetchStub = async (url, opts) => {
  asked.push([url, opts?.headers?.["User-Agent"] ?? ""]);
  if (steamDown) throw new Error("down");
  const appid = /appid=(\d+)/.exec(url)[1];
  return { ok: true, json: async () => ({ appnews: { newsitems: FEEDS[appid] ?? [] } }) };
};
const E = new Function("json", "fail", "now", "readBody", "textProblem", "metaGet", "metaSet", "fetch",
  code + "; return { eventProblem, eventList, eventDrafts, eventSave, eventDelete, canPostEvents, steamKind, steamStart, steamTime, steamDrafts, steamCheck, eventCheckNow };")(json, fail, now, readBody, textProblem, metaGet, metaSet, fetchStub);

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
// ---- Steam news: which of GGG's titles become drafts, taken from the real feed on 2026-11-24
const kinds = {
  "Path of Exile 1: Covens of Umbra Twitch Drops": "drops",
  "The Final Path of Exile 1 ExileCon Qualifier Begins Tomorrow - New Twitch Drops": "drops",
  "Curse of the Allflame Twitch Drops": "drops",
  "Play Path of Exile: Covens of Umbra on November 13 PST": "league",
  "Path of Exile: Curse of the Allflame Releases on July 24 PDT": "league",
  "Path of Exile 1 3.30 Expansion Timeline": "league",
  "Path of Exile: Covens of Umbra is Now Available!": "league",
  "Path of Exile: Curse of the Allflame is Now Live!": "league",
  "Play the Return of the Ancestors Event on June 25th PDT": "event",
  "Zizaran’s Class Gauntlet Event Starts on April 8th": "race",
  "The Third Path of Exile 1 ExileCon Qualifier Is Going Live!": "race",
  "Path of Exile 1 ExileCon Qualifiers Begin Next Week": null,
  "The Last of the Druids Microtransactions Are Now Available in Store": null,
  "The Third Edict Mystery Box Microtransactions Now Available in Store": null,
  "New Skill Effects - Kirac's Vault is Now Available": null,
  "Weekend Stash Tab Sale": null,
  "Fan Art Competition Winners": null,
  "Path of Exile: Covens of Umbra - What We’re Working On": null,
  "3.28.0e Patch Notes Preview": null,
  "ExileCon 2026 Race Qualifier VODs": null,
  "Rapture Gauntlet Stats": null,
  "Path of Exile: Mirage Original Soundtrack": null,
  "New Unique - The Draugur’s Lantern": null,
  "Hideout Showcase": null,
};
for (const [title, want] of Object.entries(kinds)) assert.equal(E.steamKind(title), want, title);
// events go live on their own now, so a shop post must never read as a league
assert.equal(E.steamKind("New Skill Effects - Kirac's Vault is Now Available"), null);

const P = Math.floor(Date.UTC(2026, 10, 3, 21) / 1000);          // posted 3 Nov 2026
const utc = (y, m, d) => Math.floor(Date.UTC(y, m, d, 20) / 1000);
assert.equal(E.steamStart("Play Path of Exile: Covens of Umbra on November 13 PST", P), utc(2026, 10, 13));
assert.equal(E.steamStart("Play the Return of the Ancestors Event on June 25th PDT", P), utc(2026, 5, 25), "this year when not long past");
assert.equal(E.steamStart("Qualifier Begins Tomorrow - New Twitch Drops", P), utc(2026, 10, 4));
assert.equal(E.steamStart("Curse of the Allflame Twitch Drops", P), P, "no day in the title: the post's own time");
assert.equal(E.steamStart("Starts on January 9", Math.floor(Date.UTC(2026, 11, 20) / 1000)), utc(2027, 0, 9), "a December post about January");
assert.equal(E.steamStart("on November 99", P), P);

NOW = P + 3600;
const item = (gid, title, over = {}) => ({ gid, title, date: P, feedname: "steam_community_announcements", ...over });
const drafted = E.steamDrafts(238960, [
  item("1", "Covens of Umbra Twitch Drops"),
  item("2", "A new Path of Exile update promises loot Twitch Drops", { feedname: "PCGamesN" }),
  item("3", "Weekend Stash Tab Sale"),
  item("4", "Old Twitch Drops", { date: P - 40 * 86400 }),
  item("5", "Twitch Drops BADWORD"),
  item("six", "Twitch Drops with an odd id"),
  item("7", "Twitch Drops from the future", { date: P + 9 * 86400 }),
  { gid: "8" }, null, "junk",
  item("9", "Play Path of Exile: Covens of Umbra on November 13 PST"),
], NOW);
assert.deepEqual(drafted.map((d) => [d.source, d.kind]), [["steam:1", "drops"], ["steam:9", "league"]],
  "only GGG's own recent posts, never the press feeds");
assert.equal(drafted[0].link, "https://store.steampowered.com/news/app/238960");
assert.equal(E.eventProblem({ ...drafted[1], end: 0 }, NOW), null, "a draft is a valid event once an admin saves it");
assert.deepEqual(E.steamDrafts(1, "junk", NOW), []);

// the check itself: every 6 hours, drafts only, never twice, a dismissed one stays dismissed
raw.exec("DELETE FROM events");
FEEDS = { 238960: [item("11", "Covens of Umbra Twitch Drops")], 2694490: [item("21", "Play Path of Exile 2: Something on December 11 PST")] };
assert.equal((await E.eventCheckNow(env, user)).status, 403);
assert.equal(asked.length, 0, "nobody but an admin makes the board call Steam");
let res = await E.steamCheck(env);
assert.deepEqual(res, { checked: true, added: 2, read: 2 });
assert.equal(asked.length, 2);
assert.ok(asked.every(([u, ua]) => u.startsWith("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=") &&
  u.includes("feeds=steam_community_announcements") && ua.startsWith("StashOfExile2-board")), "says who is asking");
assert.equal((await E.eventList(env)).body.events.length, 0, "a draft reaches no user");
let dr = (await E.eventDrafts(env, admin)).body.events;
assert.deepEqual(dr.map((d) => d.source).sort(), ["steam:11", "steam:21"]);
assert.deepEqual(await E.steamCheck(env), { checked: false, added: 0 }, "not again inside 6 hours");
assert.equal(asked.length, 2);
NOW += 7 * 3600;
assert.equal((await E.steamCheck(env)).added, 0, "the same posts are not drafted twice");
const drops = dr.find((d) => d.source === "steam:11"), league = dr.find((d) => d.source === "steam:21");
assert.equal((await E.eventDelete(env, admin, Number(drops.id.slice(1)))).status, 200);
assert.equal((await E.eventCheckNow(env, admin)).body.added, 0, "dismissed stays dismissed");
assert.equal((await E.eventDrafts(env, admin)).body.events.length, 1);
assert.equal((await E.eventDelete(env, admin, Number(drops.id.slice(1)))).status, 404, "a dismissed one cannot be deleted again");
await E.eventSave({ body: { kind: "league", name: "PoE2 league start", start: league.start } }, env, admin, Number(league.id.slice(1)));
assert.deepEqual((await E.eventList(env)).body.events.map((e) => e.name), ["PoE2 league start"], "approved by an admin: live");
assert.equal((await E.eventCheckNow(env, admin)).body.added, 0, "an approved one is not drafted again");
steamDown = true;
assert.deepEqual((await E.eventCheckNow(env, admin)).body, { checked: true, added: 0, read: 0 }, "Steam down: no error, nothing added");
steamDown = false;
FEEDS = { 238960: Array.from({ length: 30 }, (_x, i) => item(String(100 + i), `Twitch Drops ${i}`, { date: NOW })) };
assert.equal((await E.eventCheckNow(env, admin)).body.added, 10, "at most 10 new drafts a check");
NOW += 200 * 86400;
FEEDS = {};
await E.eventCheckNow(env, admin);
assert.equal(raw.prepare("SELECT COUNT(*) AS n FROM events WHERE status <> 'live'").get().n, 0, "old drafts are swept");
assert.equal(raw.prepare("SELECT COUNT(*) AS n FROM events WHERE status = 'live'").get().n, 1, "live events are kept");

// AUTO_EVENTS on (the default): a Steam post goes live with no admin
{
  raw.exec("DELETE FROM events");
  const live = { DB: env.DB };
  FEEDS = { 238960: [item("31", "Covens of Umbra Twitch Drops", { date: NOW })], 2694490: [] };
  steamDown = false;
  NOW += 7 * 3600;
  await E.steamCheck(live, true);
  assert.deepEqual((await E.eventList(live)).body.events.map((e) => e.name), ["Covens of Umbra Twitch Drops"], "live at once");
}

// 3.3.0 owner: GGG's own time and zone become one moment, shown in each player's time
{
  const posted = Date.UTC(2026, 10, 20) / 1000;
  assert.equal(E.steamStart("Path of Exile 2 Full Release on December 11", posted, "Launches December 11 at 1pm PST (10am NZDT December 12)."),
    Date.UTC(2026, 11, 11, 21, 0) / 1000, "1pm PST is 21:00 UTC");
  assert.equal(E.steamStart("Twitch Drops start December 12 at 11am NZDT", posted), Date.UTC(2026, 11, 11, 22, 0) / 1000, "11am NZDT is 22:00 UTC the day before");
  assert.equal(E.steamStart("Race on July 4 at 2:30 PM PT", Date.UTC(2026, 5, 1) / 1000), Date.UTC(2026, 6, 4, 21, 30) / 1000, "PT in summer is PDT");
  assert.equal(E.steamTime("Launches December 11 PST"), null, "a zone with no time is not a time");
  assert.equal(E.steamTime("at 1pm PST")?.said, "1pm PST");
  assert.equal(E.steamStart("Full Release on December 11 PST", posted), Date.UTC(2026, 11, 11, 20) / 1000, "no time: 20:00 UTC as before");
}
console.log("events: ok");
