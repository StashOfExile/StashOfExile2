"""A removed feature leaves nothing behind (2.126.0, UX rule: "Removing a feature: run tools/check_removed.py; clean
code, docs, tests, settings").

REMOVED below lists every feature taken out of the app: the words a person read for it and the names the code used
(functions, variables, setting keys). The check looks for them in:
  * the app's text - strings in soe2/ and stashofexile2.py (not comments or docstrings, which keep the history)
  * the app's code - names and setting keys (a line that only clears an old key - .pop( / del - is fine)
  * the docs - README.md, TOS.md and the folders' README.md files (ROADMAP.md is the history and is left alone)
  * the tests, with --tests DIR (the tests in DIR/runall.sh): a test may check a feature is gone ("not hasattr",
    "not in", "gone"), not use it; a line that needs an old name (a migration's test data) says "removed" in a comment
Left alone: migrations.py (it clears the old settings) and whatsnew.py (the release notes are the history).

Removing a feature: add a line to REMOVED (version, what it was, its words, its names), then run this.
A line marked pending=True is a known leftover still to clear: it is listed as a warning and doesn't fail the run.
Run: python tools/check_removed.py [--tests DIR]   (exit 1 lists each place)."""
import io
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"migrations.py", "whatsnew.py", "names.py"}      # (names.py lists old names on purpose)
DOCS = ("README.md", "TOS.md", "linux/README.md", "themes/README.md", "strats/README.md")

# (version, what it was, words a person read, names in the code / settings keys[, pending])
REMOVED = [
    ("3.0.6", "Farming Strategies' Sort words (owner: \"upvotes per hour?\"): Per hour / Upvotes / Easiest / Name",
     ("Sort: Per hour",), ()),
    ("3.0.6", "Farming Strategies to the approved mockups v2 (owner: the opened strat was \"a wall of text\", \"More "
              "details is confusing\", \"Sacred Bloom farm isn't a real thing\"): New strat's More details and its "
              "inputs (stash regex, waystone tiers, requirements, craft steps, other setup - older strats keep them, "
              "shown under From the author), Farm type (Map type: City, Juiced maps, Low-tier maps, Campaign zones), "
              "the opened strat's Your numbers card (Per hour fills in from your runs) and The guide card",
     ("More details", "Sacred Bloom farm", "Farm type", "Your numbers"),
     ("mm_new_more", "_mm_yours_card", "_mm_guide_card", "_mm_need_card", "MORE_LISTS", "OLD_LISTS")),
    ("3.0.6", "Farming Strategies' Crafting, Trading and Other categories and their types (owner: \"this is for "
              "farming strategies, not crafting, not trading, not flipping, not vendor recipes\" - Mapping and "
              "Bossing; a strat of a dropped category stays on disk, out of Find); New strat's Also uses row in "
              "More details (part 1's Mechanic takes several) and the Atlas masters' colors (one master at a time)",
     ("Tablet crafting", "Waystone crafting", "Gear crafting", "Jewel crafting", "Flask & charm crafting",
      "Currency flipping", "Bulk selling", "Buy low, sell high", "Vendor recipes"),
     ()),
    ("3.0.6", "Farming Strategies: the ＋ Add my own button (one name: ＋ New strat)", ("Add my own",), ()),
    ("3.0.6", "Farming Strategies' Add my own form (owner: \"so hard to understand\" - a popup of labels and switches): "
              "New strat, a page in Farming Strategies with chips, your copied tablets and waystone, Made for you, "
              "Atlas masters and How it goes; profit an hour comes from runs, not a typed estimate (older ones are "
              "kept and read)",
     ("Tags (everything else about it)", "Numbers (estimates)", "Est. profit per hour", "Est. cost per run",
      "The guide (one line per item)", "What it is: the main thing you farm or do", "* = needed. Everything else "
      "is optional."),
     ("mm_form", "mm_form_win", "mm_form_save", "mm_form_vars")),
    ("3.0.6", "Farming Strategies › Find: the Best for you right now card (owner: one list, best per hour first)",
     ("Best for you right now", "BEST FOR YOU RIGHT NOW", "MORE STRATS"), ("_mm_best_card", "run_best")),
    ("3.0.6", "Farming Strategies to the approved mockups: the Lucrative Strats tab (its one-liners are Quick tips, "
              "folded at the bottom of Find - Add, Copy, Upvote, Post, Tags… inside), the Strats tab's name (Find), "
              "the Cards | List switch and its sortable table (a row per strat; Sort orders them), the filter chip "
              "rows with More filters / Fewer filters (one dropdown each: Budget, Effort, Type, From, More; the "
              "Drawer: Filters), the toolbar's community name chip (⋯ › community name) and Track in Strat Tracker "
              "(Run this strat, the one orange button)",
     ("Lucrative Strats", "Lucrative strat", "Track in Strat Tracker", "Track it in the Strat Tracker", "More filters",
      "Fewer filters", "Thoughts/click", "Est. profit/h", "Pick a strat on the left", "+ Add a one-liner",
      "Farming Strategies › Strats", "Strats › Mine"),
     ("mm_layout", "mm_more_filters", "mm_more_paint", "mm_layout_changed", "mm_cards_fill", "mm_cards_reflow",
      "mm_cards_mark", "mm_card_w", "mm_sort_by", "mm_chips_paint", "mm_chip_rows", "_mm_flow", "_mm_chip",
      "_mm_content_chips", "mm_content_menu", "mm_tree", "mm_one_tree", "mm_one_view", "mm_one_q", "mm_one_btns",
      "mm_build_oneliners", "mm_need_items", "mm_cost_lines", "mm_mine_paint", "mm_mine_box", "mm_sash", "mm_pick",
      "mm_one_greys", "mm_acct", "mm_btns", "mm_more")),
    ("3.0.6", "tabs.txt and jewels.txt (owner: no reason to still use .txt - both are one modlists.json now)",
     ("tabs.txt", "jewels.txt"), ("load_tabs", "load_jewels", "clean_jewel_line", "_clean_tab_line")),
    ("3.0.6", "the Search with fewer mods button (owner: Broaden Search does it for every item - the orange button "
              "searches without the lowest-rated ticked mod; one name for it)",
     ("Search with fewer mods",), ()),
    ("3.0.6", "Messages stay for, the Drawer's Width box and Settings › General › Your account (owner: \"needs removed\", "
              "\"we don't need a width input box\" - drag its edge; the account is asked where it's used, Stash tab and "
              "Wealth)",
     ("Messages stay for", "% of the game's width"), ("_drawer_share_pick", "build_account_settings")),
    ("3.0.6", "the Quick start guide and About's Every version's notes link (owner: \"replaced with the thing we give "
              "people on first time startup\" - Setup, Run setup again; the link showed only this version's notes)",
     ("Quick start guide", "Every version's notes"), ("show_quickstart", "quickstart_go", "QUICKSTART")),
    ("3.0.4", "Wealth prices typed by hand (owner: never ask for a price - poe.ninja, else the trade site's exchange, "
              "else No price found) and the Where it is card (owner: it told nothing; What moved it took its place)",
     ("Set my own price", "Use the market price again", "Double-click a price to set your own", "Where it is",
      "Needs a price", "need a price", "set price", "Combine stacks"),
     ("wealth_set_price", "wealth_clear_price", "wealth_breakdown", "wealth_pick_cat", "w_catfilter", "w_bd_mode",
      "wealth_key", "w_combine", "w_unpriced")),
    ("3.0.1", "the name Look key (owner: \"ctrl + shift + r = Read. R for Read.\" - it is the Read Key; its setting "
              "is still look_key, its NEW chip's seen state moves over: migrations.read_key_name) and every line saying "
              "the game still gets the key (owner: nobody understands it - the key still reaches the game)",
     ("Look key", "The game still gets the key", "the game still gets the key", "the game still gets it",
      "it still gets it", "passed through to the game"), ()),
    ("Sekhemas legend", "the Trial of the Sekhemas key count (\"no keys yet\" / \"keys: 1 Silver\" under the legend: it "
                        "counted the log's \"Collected a ... Key\" lines from the app's start and missed keys; the "
                        "game shows them by the map) and the legend's Close buttons (a click on it closes it)",
     ("no keys yet", "Closes the legend"),
     ("sek_log", "_sek_footer", "SANCTUM_KEY", "KEY_KINDS", "close_label")),
    ("drawer build", "the ⌕ Go to anything button on the Overlay Bar (owner: not needed; App ▸ stays and opens the "
                     "Drawer)",
     ("Go to anything in the Drawer", "opens it with Go to anything", "App ▸ and ⌕"), ()),
    ("GGG policy", "the clipboard watcher: Windows' copy counter asked every 150 ms on a timer (the strictest reading: "
                   "any clipboard call on a timer is a read) - a copy key press reads once, READ_DELAY after it",
     ("clipboard watcher restarted",),
     ("poll_clipboard", "clip_seq", "restart_watcher", "last_seq", "poll_gen", "last_poll", "write_clipboard_text",
      "GetClipboardSequenceNumber")),
    ("GGG policy", "the app's buttons and menu items that read the clipboard on a click (a click is not a key press): "
                   "Paste item, Paste from clipboard, Paste a trade link, Paste screenshot, Test on copied item, "
                   "Check my tablet, the right-click menu's Paste, Tk's middle-click paste - Ctrl+V reads instead",
     ("Paste item", "Paste from clipboard", "Paste a trade link", "Paste screenshot", "Test on copied item",
      "Check my tablet", "click here to paste"),
     ("lib_paste", "fd_paste")),
    ("GGG policy", "Tab (the game's map key) as the Look key, and a click on Scan stash's Start reading reading the "
                   "screen - the Look key is a key only for the read, not set until you pick one; Start reading arms",
     ("Look key (Tab)", "Look key - Tab", "the game gets the key too", "Tab by default"),
     ()),
    ("GGG policy", "Fast Beacon Read (Helpers › Temple: a box round your character read 30 times a second) - GGG allows "
                   "one screen read per key press; hover a Beacon and press the Look key",
     ("Fast Beacon Read",), ("temple_fast_on", "temple_fast_set", "temple_fast_start", "temple_fast_wanted",
                             "_tm_fast_poll", "_tm_fast_why", "ev_tm_fast", "al_tfast", "fast_read", "FAST_EVERY")),
    ("GGG policy", "the Ritual helper's Tribute reminder (it needed the Favours window watched until it closed)",
     ("Tribute reminder", "Offer your tribute", "offer it to the King"),
     ("tribute_reminder", "al_rtrib", "alerts_tribute_changed", "ev_favours_tribute", "ev_favours_offered",
      "tribute_offered", "tribute_box", "tribute_of", "favours_hud_read", "ev_ritual_tribute", "favours_tribute_read",
      "rerolls_left", "fv_owed_at", "fv_offered_at")),
    ("GGG policy", "the Delirium helper (Overlay › Helpers row, Quick settings chip, bar switch, End Delirium alert card, "
                   "soe2/delirium_alert.py and its three pictures): its End Delirium check was a screen read of its "
                   "own - the one thing it did - and a Look key press in a map is not an automatic alert",
     ("End Delirium", "Delirium is still on", "Map done - Delirium", "no Delirium seen"),
     ("delirium_alert", "delirium_cfg", "delirium_look_job", "ev_delirium_state", "alerts_test_delirium", "dl_last",
      "dl_win", "delirium_arrows", "map_completed", "objective_completed")),
    ("GGG policy", "the screen-watching helper processes (Ritual watcher --ritual, Delirium alert --delirium, its "
                   "splinter icon and the standalone PoE2DeliriumAlert.exe) - Ritual and Delirium read on the Look key",
     ("PoE2DeliriumAlert.exe", "Moving the splinter", "Watching for Rituals", "Screen capture problem"),
     ("DeliriumHelper", "RitualHelper", "dl_do_start", "dl_do_stop", "dl_do_test", "util_delirium_autostart",
      "delirium_runner", "app_mark", "find_game_rect", "make_dpi_aware")),
    ("GGG policy", "every timed screen watcher (Temple / Ritual Identifier looks, Expedition, Island Rumors, Favours "
                   "prices, Desecration Helper, Top Up Reminders, Temple Console) - one read per Look key press",
     ("Watching for remnant reward books", "Watching for Vaal Beacons", "looks when you open your inventory"),
     ("hover_tick", "hover_start", "hover_look", "remnant_auto_sync", "_remnant_watch", "rm_auto_gen", "topup_start",
      "topup_tick", "favours_sync", "_fv_watch", "_ru_watch", "ru_start", "ru_stop", "_ws_watch", "ws_start",
      "ws_stop", "temple_console_tick", "temple_start", "temple_look", "grab_bgr", "AUTO_POLL", "AUTO_GONE",
      "SETTLE_READS", "read_clipboard_text")),
    ("GGG policy", "the Temple Helper's Vaal Beacon read (hover a Beacon in a map + the Look key), Map Content's Temple "
                   "icon, the crystals on the overlay's line and the Crystals full alert card - owner decision: the "
                   "crystals are read from the Temple Console only (Vaal Lens shows them)",
     ("Hover a Vaal Beacon", "hover a Vaal Beacon", "Crystals full", "Energised Beacons", "temple_content.png"),
     ("temple_alert", "tm_in_map", "fast_parse", "content_has", "tm_told", "_temple_part", "fast_box",
      "FAST_BOX", "_last_score_log")),
    ("GGG policy", "Map Content's icons (owner decision: nothing looks at the screen on entering a map or to tell it's "
                   "done): the Ritual icon's all-done tick (ritual_alert.content_state, templates/ritual_content.png) "
                   "and the Expedition mark (remnant.has_marker) - Ritual follows Client.txt between Look key presses",
     ("ritual_content.png", "All rituals done", "Expedition mark"),
     ("content_state", "rt_done", "has_marker", "marker_rect", "rm_mark_check", "rm_mark_at", "MARKER_B64",
      "MARKER2_B64", "MARKER_SCORE", "MARKER_STRIP", "TICK_MIN")),
    ("UI overhaul", "the sidebar's Toolkit row and the Toolkit menu (a third list of every page; Go to anything lists "
                    "them, Settings › About has What's new, Quick start and Check for updates). The menu's code is only "
                    "reachable without pages (shell PAGES off) - clearing it is left to the shell cleanup",
     ("Toolkit",), ("_toolkit",), True),
    ("UI overhaul", "Settings › Advanced › Developer options and its Show developer options switch (owner: Debug mode "
                    "and Unmatched mods sit in Problems)",
     ("Developer options", "Show developer options"), ("dev_options", "dev_var", "dev_box")),
    ("UI overhaul", "Overlay › Options › Campaign Helper's Open the route button (owner: it did nothing there)",
     ("Open the route",), ()),
    ("UI overhaul", "the BETA helpers as feature switches (Settings › General › Features listed Top Up Reminders, "
                    "Break reminders, Map profit, Temple Helper, Music Controls - each helper's one switch is its "
                    "Overlay › Helpers row); the Feature Picker popup (Setup asks one question a screen; the data "
                    "folder and unrated-mods questions are in Settings only)",
     ("What do you want to use?", "Feature Picker"),
     ("beta_on", "data_dir_asked", "ask_unrated_asked", "features_restart_ask", "feat_never", "feat_share",
      "feat_folder", "feat_err", "shown_path")),
    ("nav phase 2", "Overlay Settings as a page of its own (Overlay ↳ Overlay Settings, module ovset) - its parts are "
                    "the Overlay page's tabs: Helpers, On the Overlay, Look, Options; the Overlay appearance… button "
                    "(Look is a tab beside Options)",
     ("Overlay Settings", "Overlay appearance…"),
     ("OverlaySettings", "ovset", "tk_settings_btn", "topup_row", "mp_row")),
    ("UI overhaul", "Farming Strategies' Download Format (the blank CSV strat template) - Import file… stays; "
                    "importing guides from popular sites is on the roadmap",
     ("Download Format",), ("mm_download_format",)),
    ("UI overhaul", "the typed Add currency by hand form on Wealth - Count by hand (Ctrl+C on each stack) is the one "
                    "way to add by hand; its old name Count currency is gone too",
     ("Add currency by hand", "Added by hand", "Count currency"),
     ("wealth_manual_add", "wealth_manual_set", "w_man_box", "w_man_name", "w_man_qty", "w_count_btn")),
    ("2.140.0", "the Temple Notepad (the card in the temple is Vaal Lens now: crystals, the board, notes in a fold)",
     ("Temple Notepad",), ()),
    ("2.135.1", "Reduce motion (Settings › Appearance › Motion) and the short fades it switched off - nothing fades now",
     ("Reduce motion makes them appear at once",), ("fade_in", "reduce_motion_var", "on_reduce_motion",
                                                     "windows_animations", "FADE_STEPS")),
    ("2.132.7", "the Regex key window (1-4 favorites per key, typed into the stash search one per press)",
     ("each press types the next one", "+ Add a favorite", "No favorites on this key yet"),
     ("rx_keys_dialog", "rx_keys_win", "rx_keys_state", "MAX_PER_KEY", "type_search", "_rx_key_pos")),
    ("2.132.6", "the single Regex key that copied a search (now Regex keys that type it in the stash search)",
     ("Copy your stash search (in game)", "- it copies"), ("rx_hk_box", "rx_hotkey_pick", "rx_key_lbl")),
    ("2.132.4", "the Ritual Identifier as a helper of its own (its Helpers row, Quick settings chip, BETA feature) - "
                "it's a Ritual helper option now", ("Ritual Identifier (BETA)",), ("ritid_row", "ritid_set", "al_ritid")),
    ("2.131.2", "League Plan's Map supplies (refill every N maps / minutes, its pokes) - Top Up Reminders count the "
                "inventory instead; its list moves there once",
     ("Map supply pokes", "ADD A SUPPLY", "REFILL YOUR MAP SUPPLIES", "Refill every"),
     ("add_supply", "remove_supply", "set_supply", "supplies_due", "supply_used", "SUPPLY_RULES", "SUPPLY_PRESETS",
      "USED_UP", "_gp_supplies", "_gp_sup_rows", "gp_sup_on", "gp_add_supply", "OMEN_USED")),
    ("2.131.0", "the campaign's 4th route (your last run's zone order) - Full, Speedrun and Rush (carry) stay",
     ("My Own",), ()),
    ("2.131.0", "the single Show beta features switch (Features has a Beta cluster); the quick start's sharing page "
                "(the Feature Picker asks)", ("Show beta features (marked BETA)", "Share with the community?"),
     ("on_labs", "labs_var", "set_labs", "SHARE_PAGE", "qs_share_row")),
    ("2.129.2", "Trade whispers' After the campaign option (on is on)", ("After the campaign",
     "Keep on after the campaign"), ("al_wafter", "ww_after_changed", "in_campaign")),
    ("2.11.0", "Recorder", ("Ritual Capture",), ()),
    ("2.31.0", "Lag finder; the toolbar's 'Ctrl+Alt+C only' box", ("Lag finder",), ()),
    ("2.92.0", "Arbitrage (Exchange Helper's flip check stays)", ("Arbitrage",), ()),
    ("2.98.3", "One-key copy and Other ways of copying", ("One-key copy", "Other ways of copying"),
     ("quick_copy_key", "hotkey_only", "any_copy_var", "quick_copy_btn")),
    ("2.68.1", "The notes key (Notes is part of the overlay)", ("Notes key",), ("notes_key",)),
    ("2.118.0", "Community rep", ("Thank someone with rep",), ("rep_give", "rep_btn")),
    ("2.119.0", "Feature tips; the 'only while the game is in front' switch", ("Feature tips",), ("game_only_var",)),
    ("2.125.5", "Skip cheap items; Valuable mods amount; Card over the game", ("Skip cheap items", "Card over the game"),
     ("floor_var", "good_div_var")),
    ("2.125.6", "Mod Book re-check rows and Bulk Pricing shortcuts",
     ("How searches are made", "Re-check a learned mod after", "Learn new mods in the background",
      "Skip a search the Mod Book already agrees on"),
     ("memory_shortcut", "model_shortcut")),
    ("2.106.0", "Wealth's public stash tabs (Scan stash replaces them)", ("Sync stash tabs",), ("w_sync_btn",), True),
]
ABSENT = re.compile(r"\bnot\b|\bgone\b|\bremoved\b|\bno longer\b|\.pop\(|\bdel\b|None\)", re.I)


def tokens(path):
    """(kind, text, line) for the strings that aren't docstrings, and the names."""
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    out, prev = [], "NEWLINE"
    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    for i, t in enumerate(toks):
        name = tokenize.tok_name[t.type]
        if name == "STRING":
            nxt = next((tokenize.tok_name[x.type] for x in toks[i + 1:] if tokenize.tok_name[x.type] != "NL"), "")
            if not (prev in ("NEWLINE", "INDENT", "DEDENT") and nxt == "NEWLINE"):      # (a docstring)
                out.append(("str", t.string, t.start[0]))
        elif name == "FSTRING_MIDDLE":
            out.append(("str", t.string, t.start[0]))
        elif name == "NAME":
            out.append(("name", t.string, t.start[0]))
        if name not in ("NL", "COMMENT"):
            prev = name
    return out, src.splitlines()


def word_rx(w):
    return re.compile(r"(?<!\w)" + re.escape(w) + r"(?!\w)")         # (as the label read: "a card over the game" is fine)


def check_code(found):
    files = [os.path.join(ROOT, "stashofexile2.py")] + sorted(
        os.path.join(ROOT, "soe2", f) for f in os.listdir(os.path.join(ROOT, "soe2")) if f.endswith(".py"))
    for path in files:
        if os.path.basename(path) in SKIP:
            continue
        toks, lines = tokens(path)
        for ent in REMOVED:
            words, names = [word_rx(w) for w in ent[2]], set(ent[3])
            for kind, text, ln in toks:
                line = lines[ln - 1]
                if kind == "str":
                    inner = re.sub(r"^[rbfuRBFU]*['\"]{1,3}|['\"]{1,3}$", "", text)
                    if inner in names and not ABSENT.search(line):
                        found.append((ent, path, ln, f"setting key {inner!r}"))
                    for rx in words:
                        if rx.search(text):
                            found.append((ent, path, ln, f"text {rx.search(text).group(0)!r}"))
                elif text in names and not ABSENT.search(line):
                    found.append((ent, path, ln, f"name {text}"))


def check_docs(found):
    for rel in DOCS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        for ln, line in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
            for ent in REMOVED:
                for w in ent[2]:
                    if word_rx(w).search(line) and not ABSENT.search(line):
                        found.append((ent, path, ln, f"doc {w!r}"))


def check_tests(found, folder):
    run = os.path.join(folder, "runall.sh")
    names = sorted(set(re.findall(r"\b(test_\w+)", open(run).read()))) if os.path.exists(run) else []
    for n in names:
        path = os.path.join(folder, n + ".py")
        if not os.path.exists(path):
            continue
        for ln, line in enumerate(open(path, encoding="utf-8", errors="ignore").read().splitlines(), 1):
            if ABSENT.search(line) or line.lstrip().startswith("#"):
                continue
            for ent in REMOVED:
                for nm in ent[3]:
                    if re.search(r"(?<!\w)" + re.escape(nm) + r"(?!\w)", line):
                        found.append((ent, path, ln, f"test uses {nm}"))


def main(argv):
    found = []
    check_code(found)
    check_docs(found)
    if "--tests" in argv:
        check_tests(found, argv[argv.index("--tests") + 1])
    bad = [f for f in found if not (len(f[0]) > 4 and f[0][4])]
    warn = [f for f in found if f not in bad]
    for ent, path, ln, what in warn:
        print(f"warning (pending, {ent[0]} {ent[1]}): {os.path.relpath(path, ROOT)}:{ln}: {what}")
    for ent, path, ln, what in bad:
        print(f"{os.path.relpath(path, ROOT)}:{ln}: {what} - removed in {ent[0]} ({ent[1]})")
    print(f"check_removed: {len(REMOVED)} removed features, {len(bad)} leftovers" + (f", {len(warn)} pending" if warn else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
