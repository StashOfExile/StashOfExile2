// Dumps the board's word filter as data for the app: soe2/cleanwords.json. The library's patterns and whitelist, and
// the board's own lists. One list, two readers: the board refuses a post, the app refuses the typing.
//      node tools/build_cleanwords.mjs board soe2/cleanwords.json
import { readFileSync, writeFileSync } from "node:fs";
const lib = readFileSync(process.argv[2] + "/node_modules/obscenity/dist/preset/english.js", "utf8");
const src = readFileSync(process.argv[2] + "/src/index.js", "utf8");
const body = lib.slice(lib.indexOf("exports.englishDataset = new DataSet_1.DataSet()"));
const patterns = [...body.matchAll(/Pattern_1\.pattern\)\s*`([^`]+)`/g)].map((m) => m[1]);
const white = [...body.matchAll(/addWhitelistedTerm\('([^']+)'\)/g)].map((m) => m[1]);
const thr = [...lib.slice(lib.indexOf("englishRecommendedBlacklistMatcherTransformers"), lib.indexOf("englishRecommendedWhitelistMatcherTransformers = ["))
  .matchAll(/\['(.)',\s*(\d+)\]/g)].map((m) => [m[1], Number(m[2])]);
const arr = (name) => JSON.parse("[" + new RegExp("const " + name + " = \\[([^\\]]+)\\]", "s").exec(src)[1].replace(/\s+/g, " ") + "]");
const out = { note: "Made by tools/build_cleanwords.mjs from board/src/index.js and the obscenity library (MIT). Do not edit by hand.",
  patterns, white, keep: Object.fromEntries(thr), hate: arr("HATE"), rude: arr("RUDE_WORDS"), phrases: arr("HATE_PHRASES") };
writeFileSync(process.argv[3], JSON.stringify(out));
console.log("patterns", patterns.length, "white", white.length, "keep", JSON.stringify(out.keep), "hate", out.hate.length, "rude", out.rude.length, "phrases", out.phrases.length);
