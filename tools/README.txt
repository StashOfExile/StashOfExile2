tools/build_gamedata.py rebuilds gamedata.json (the Item library: base types, base groups, modifier stats).
You only need it after a game patch, when Exiled Exchange 2 has published updated data.

  1. Get Exiled Exchange 2:   git clone --depth 1 https://github.com/Kvan7/Exiled-Exchange-2.git
  2. Next to the launcher:    py tools/build_gamedata.py path\to\Exiled-Exchange-2 gamedata.json
  3. In tools/build_gamedata.py raise GAMEDATA_VERSION by 1, and in soe2/config.py raise "gamedata.json" in
     BUNDLED_DATA to the same number, so the new file replaces the old one in everyone's data folder.
  4. Build the exe as usual (build_exe.bat).

tools/build_regexdata.py rebuilds regexdata.json (the Regex page: tablet, waystone and relic mods and their search
tokens). After a game patch, once RePoE has published updated data:

  1. Get RePoE's PoE 2 data:  git clone --depth 1 https://github.com/repoe-fork/poe2 repoe2
  2. Next to the launcher:    py tools/build_regexdata.py repoe2\data\mods.json regexdata.json
  3. In soe2/config.py raise "regexdata.json" in BUNDLED_DATA by 1, then build the exe as usual.

tools/check_items.py (2.121.0) reads every base type and unique in gamedata.json as a copied item - its base, class
and a search the trade site takes (unidentified uniques too). Run it after rebuilding gamedata.json:

  py tools/check_items.py           (prints what failed; exits 1 if anything did)

Bases and uniques newer than gamedata.json don't need a rebuild to work: the app downloads the trade site's own item
list once a day (trade_items.json in the data folder) and uses it where the game data has nothing.

tools/build_gamedb.py rebuilds gamedb.json (Game Search's offline game database: Tablets, Waystones, Atlas Masters, Vaal
Temple, Pinnacles & Areas, Trial of the Sekhemas, Trial of Chaos, Ritual Altars, Leagues). Only facts from the game's own
files: it reads modlists.json, regexdata.json, mapdata.json, trialdata.json, gamedata.json, searchdata.json and a few names in the app's code - no
community ratings, nothing looked up when the app runs. Run it after any of those files changes:

  py tools/build_gamedb.py            build, verify, write gamedb.json
  py tools/build_gamedb.py --check    verify only (and says if gamedb.json is out of date)

It checks every row before writing and refuses to write (exit 1, each failure printed) if one fails: every tablet and
waystone mod has a stat in gamedata.json, every item name exists, modlists.json and regexdata.json agree on each tablet
type's mods and ranges, and every mod line on the real copies in tests/fixtures/gamedb_samples.txt matches a row. To
refresh those copies from the test build's data folder (session.json and unpriced_items.txt; only item text is kept):

  py tools/build_gamedb.py --refresh-samples C:\path\to\Builds\soe2\testdata

trialdata.json (the Trial of Chaos facts) comes from the RePoE poe2 export: py tools/build_trialdata.py path\to\repoe2\data
It is a build input only (not shipped). Anything the export doesn't hold is left out, never filled from a website.

SOURCE BLACKLIST (permanent owner rule): never use game8 or fextralife (game8.co, poe2.game8.co, any fextralife wiki) as
a data source - their pages are AI-written and wrong. build_gamedb.py fails any row whose source, text or tags mention
them, and the name must not appear in the code or data credits either. Allowed: the game's own files (RePoE export,
gamedata.json, searchdata.json, trade site lists) and the owner's own real item copies.

After a rebuild raise "gamedb.json" in BUNDLED_DATA (soe2/config.py) by 1.

Removing a wrong row without a rebuild: add its id to gamedb_hide.json, one entry per row with a one-line reason:

  [{"id": "tablet/any/mod/increased-rarity-of-items-found-in-map", "reason": "the game text differs in 0.5.6"}]

Game Search leaves the row out the next time it opens, and the build skips it. Row ids are in gamedb.json and shown in a
row's details (more ›). Raise "gamedb_hide.json" in BUNDLED_DATA by 1 when you ship a changed hide list.

tools/build_searchdata.py also drops the Path of Exile 1 leftovers (scarabs, Maven's Invitations, watchstones ...): see its
docstring. Without the PoE2-Search.html page, py tools/build_searchdata.py --refilter filters the searchdata.json here.

Checks a release runs (each exits 1 and lists what to fix):

  py tools/check_names.py      one name per feature: page names from soe2/names.py, in Title Case; no old names
  py tools/check_removed.py    a removed feature leaves no text, setting or test behind (REMOVED lists them;
                               add --tests path\to\tests to look at the tests too)
  py tools/check_ui_text.py    no parenthesis aside in a UI string - the detail goes in the tooltip; older ones
                               are listed in tools/ui_text_baseline.txt, which only shrinks: --update drops fixed ones
  py tools/check_ux.py         opens every page in an empty data folder (offline): one orange button and one BETA
                               chip per screen; lists icon buttons without a tip, list pages whose search box isn't
                               first, and buttons that are on with nothing picked (UX round 2)

Page smoke test (Linux, Xvfb + Pillow): opens every page and tab the way the sidebar does, plus Settings, Go to
anything and the status bar; records tracebacks, blank pages, titles, sidebar rows and a screenshot each.

  python3.12 tools/smoke_pages.py --run NAME [--checks]     (outputs/smoke/NAME/report.json, exit 1 on a failure)
  python3.12 tools/smoke_pages.py --compare baseline NAME   (failures vs. expected changes: titles, sidebar order)
