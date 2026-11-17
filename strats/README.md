# Farming Strategies strats

> **GGG ToS safety check - read first.** One key press = one action, only when you press it · nothing acts in the game by itself (helpers only read and show) · never touch the game's memory, code or traffic · the mouse is never moved or clicked for you · it reads Client.txt, the trade site (within its limits) and poe.ninja, and your clipboard or screen only once per key press (the Read Key, a copy key). Every change must pass all of [TOS.md](../TOS.md) (`tools/check_tos.py` checks the code on every PR).

> **Who we build for - read second.** Path of Exile players are utilitarian: they love data and information, problem solving and creative thinking. So every feature shows its numbers *and how they were worked out*, lets you sort, filter, compare and export them (CSV), keeps power-user depth (keys, versions, raw data) one click away instead of hiding it, explains in plain words, and leaves the decision to the player. Pretty is welcome; vague is not.

Each strat is **one file** in this folder, in the standard layout below: a `.csv` file (2.46.0 - what the app saves
with **Export**; opens in Excel / Google Sheets), or `.json`. The older plain-text `.txt`
layout still reads. One-liners for **Quick tips** (folded at the bottom of Farming Strategies › Find) go in
`oneliners.json`. `tools/build_strats.py` checks every file and builds `moneymakers.json`, which ships with the app
**and** is fetched from `main` by the app (at most every 12 h), so a merged strat reaches everyone without a new release.

**Sharing:** players post straight from the app to the **Community** board (no login - just a name), upvote and
report there. Admins **promote** the best posts and they join the Official list. Strats in
this folder are the hand-curated part of the Official list: copy `_template.json` and send a PR. Files starting with `_` are ignored.

**What a strat is** = one **Category** and one **Type** inside it. Breach farming is `Mapping` › `Breach`: the
type is the main thing you farm, the category is how you do it. Everything else goes in **tags**.

| Category | Types |
|---|---|
| Mapping | Breach, Delirium, Ritual, Expedition, Abyss, Essence, Strongbox, Rogue Exiles, Shrines, Overseer, Temple, Juiced mapping, Alch & go |
| Bossing | Pinnacle bosses, Map bosses, Simulacrum, Trial of the Sekhemas, Trial of Chaos |

Farming only (3.0.6, owner): no crafting, trading, flipping or vendor recipes. A strat of a category that was dropped
is kept as it is but doesn't show in Find; one-liners about them are kept in `_not_farming_oneliners.json` (ignored).

| Tag group | Tags (any number) |
|---|---|
| Also uses | Abyss, Breach, Delirium, Ritual, Expedition, Essence, Strongbox, Rogue Exiles, Shrines, Overseer, Temple |
| Farm type | City area farm, Sacred Bloom farm, Juiced maps, Low-tier maps, Campaign zones |
| Budget | League start, Low budget, Mid budget, High budget |
| Play style | SSF friendly, Trade league, Party play, Hardcore safe |

Searching a tag finds both: `Breach` finds Mapping › Breach and strats tagged "Also uses: Breach".

| Field | Need | What |
|---|---|---|
| `id` | yes | lower-case-with-dashes, same as the file name |
| `name`, `author`, `summary` | yes | text; summary = one line |
| `updated` | yes | `YYYY-MM-DD` |
| `patch` | yes | game version, e.g. `0.4` |
| `league` | no | the league it's for, e.g. `Forbidden Rites` (empty: the league of its game version - Find's League filter) |
| `category`, `type` | yes | from the table above |
| `thoughts_per_click` | yes | Effort (how much thinking), 1-5: 1 Autopilot, 2 Easy, 3 Moderate, 4 Hard, 5 Big brain (New strat asks Easy / Medium / Hard: 2 / 3 / 4) |
| `clicks_per_hour` | yes | `Chill`, `Steady`, `Busy` or `Frantic` |
| `steps` | yes | list of lines, in order |
| `tags` | no | from the tag table |
| `waystone_tiers` | no | `{"min": 1-16, "max": 1-16}` |
| `est_cost` | no | per run: `{"amount", "unit"}` or `{"low", "high", "unit"}` - unit `div`, `ex` or `chaos` |
| `est_profit` | no | per hour: `{"low", "high", "unit"}` (may be negative) |
| `tablets`, `waystones`, `atlas`, `craft_steps` | no | lists of lines: tablets / waystones used, atlas and master setup, crafting steps |
| `requirements`, `setup`, `loot`, `tips`, `risks` | no | lists of lines (`loot` = item names to sell) |
| `regex` | no | a stash search string |
| `sources` | no | `[{"title", "url"}]` |

| `items` | no | `[{"kind", "base", "name", "count", "lasts", "key_mods", "mods", "rarity"}]` - what a run uses, with the mods that matter (`key_mods`; `mods` = every line of the copy): the app checks their trade price once a day (Cost per map) |
| `masters` | no | Atlas masters: ONE master and up to 4 of its choices, e.g. `{"Doryani's Science": ["Refined Formula", ...]}` (`moneymakers.MASTERS`) |
| `ledger` | no | numbers from the author's Strat Tracker: `runs`, `minutes`, `cost_per_run_div`, `loot_per_run_div`, `profit_per_run_div`, `div_per_hour` |

**The CSV layout** (one header for every Money Makers CSV): `section,field,value,note`. `strat` rows hold the fields
above (`thinking` as a word, `est_cost_div` a run, `est_profit_div` an hour), `tag` rows one tag each (field = its
group), list rows one line each (section = the list, field = 1, 2, 3 ...), `source` rows a link (note = its title),
`item` rows `1:kind`, `1:base`, `1:count`, `1:lasts`, `1:key_mod` (repeat for more mods; `1:mod` for a line that
doesn't matter), `master` rows one Atlas masters pick each (field = the master - one master), and `ledger` rows the Farm
Ledger's numbers under the same names as its own CSV. The `note` column is help - the app ignores it.

One-liner (`oneliners.json`): `{"id", "text", "author"}` + optional `category`, `type`, `tags`, `updated`.
`content.json` holds the Content tag groups (pinnacles, bosses, map content - 2.78.0): add a new league's content
there and every app gets it from `moneymakers.json`. `atlas_image` is `"b:<id>"`, an atlas screenshot on the board
(the app uploads it when you post).

The tag `example` marks a sample strat. Check your files with `py tools/build_strats.py --check`.
