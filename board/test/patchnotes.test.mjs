// Patch notes from GGG's forum, 3.3.0: an RSS feed or the forum page, PoE2 only, never dropping one.
//      node board/test/patchnotes.test.mjs
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "../src/index.js"), "utf8");
const code = src.slice(src.indexOf("// patch notes: start"), src.indexOf("// patch notes: end"));
const { patchParse, patchMerge, patchIsPoe2 } = new Function(code + "; return { patchParse, patchMerge, patchIsPoe2 };")();
assert.ok(readFileSync(join(here, "../wrangler.toml"), "utf8").includes("crons"), "the board runs once an hour");

const rss = `<rss><channel>
<item><title>0.5.5h Patch Notes</title><link>https://www.pathofexile.com/forum/view-thread/1</link><pubDate>Tue, 24 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title><![CDATA[3.28.0k Patch Notes]]></title><link>https://www.pathofexile.com/forum/view-thread/2</link></item>
<item><title>Hotfix 1.0.0b</title><link>/forum/view-thread/3</link></item>
<item><title>Community Spotlight</title><link>https://www.pathofexile.com/forum/view-thread/4</link></item>
</channel></rss>`;
const found = patchParse(rss);
assert.equal(found.length, 4);
assert.equal(found[2].url, "https://www.pathofexile.com/forum/view-thread/3");
assert.ok(patchIsPoe2("0.5.5h Patch Notes") && patchIsPoe2("Hotfix 1.0.0b"));
assert.ok(!patchIsPoe2("3.28.0k Patch Notes"), "Path of Exile 1 is left out");
assert.ok(!patchIsPoe2("Community Spotlight"));

let { list, added } = patchMerge([], found, 1000);
assert.equal(added, 2);
assert.deepEqual(list.map((n) => n.title).sort(), ["0.5.5h Patch Notes", "Hotfix 1.0.0b"]);
({ list, added } = patchMerge(list, [], 2000));
assert.equal(list.length, 2, "an empty read drops nothing");
assert.equal(added, 0);

const page = `<a href="/forum/view-thread/9">1.0.1 Patch Notes</a> <a href="/forum/view-thread/9">1.0.1 Patch Notes</a>`;
assert.equal(patchParse(page).length, 1, "the forum page works too");
console.log("patchnotes: ok");
