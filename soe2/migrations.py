"""2.117.0: every one-time change to your settings and data in one ordered list (they were spread over app.py,
config.py and market.py, each with its own "done" flag).

A step runs once per PC, in order, at its stage:
  * "settings" - when settings.json is loaded (config.py), before any window
  * "app"      - when the app starts, after your data is loaded and before the windows are built
Done steps are listed in SETTINGS["migrations_done"]. A step that was done before 2.117.0 under its old flag
(`legacy`) counts as done - the flag is kept, so an older build put back on the PC doesn't run it again. A step that
fails goes to the app's log and is tried again next start, at most TRIES times; then it's left (and logged).
Settings are saved once, after the stage.

Adding one: a function at the end of STEPS - ("short_id", "version", "stage", fn, legacy flag or None). fn returns
nothing; it changes SETTINGS (and saves its own data files). Never reorder or rename one that has shipped.

The data files' own format upgrades (ledger.json, moneymakers, mod rule keys) stay with the code that reads them -
they run on every load and change nothing once a file is up to date. The overlay's own settings (overlay.json) keep
their steps in tracker_page.py / overlay.py."""
from . import buglog

TRIES = 3


# ---------------------------------------------------------------- the steps (oldest first)
def _rules_scoped(S):
    """2.6.0: waystone / relic rules set from Regex move to their own names (mods.migrate_scoped_rules)."""
    from . import regex as R
    from .config import save_json
    from .mods import RULES, migrate_scoped_rules

    def lines(kind):
        return [ln for m in R.mods(kind) for ln in (m.get("lines") or [m["line"]])]
    if migrate_scoped_rules(lines("waystone"), lines("relic")):
        save_json("mod_rules.json", RULES)


def _status_ib(S):
    """2.79.2 (feedback): the default seller is Instant Buyout."""
    S["status"] = "Instant Buyout"


def _copy_hotkey_only(S):
    """2.98.3: One-key copy and "Other ways of copying" are gone - Bulk Pricing adds only your own Ctrl+Alt+C."""
    S.pop("quick_copy_key", None)
    S.pop("hotkey_only", None)


def _gear_plus(S):
    """2.99.0: gear rules lose their leading "+" (Mod book › Gear rules lists lines without one)."""
    from .config import save_json
    from .gearbook import migrate_plus
    from .mods import RULES, TIERS
    if migrate_plus(RULES, TIERS):
        save_json("mod_rules.json", RULES)
        save_json("mod_tiers.json", TIERS)


def _tier_only(S):
    """2.114.0: one rating - a tier you gave decides High / Normal (S / A = High, B-D = Normal)."""
    from .config import save_json
    from .mods import RULES, TIERS, migrate_tier_only
    if migrate_tier_only():
        save_json("mod_rules.json", RULES)
        save_json("mod_tiers.json", TIERS)


def _modbook_import(S):
    """1.x mod book (modbook.json) into the market's database, once."""
    from .config import MODBOOK
    from .market import MARKET
    if MODBOOK:
        MARKET.import_old_modbook(MODBOOK, float(S.get("good_div", 0.5)))


def _ux_2119(S):
    """2.119.0 (UX pass): settings that are gone - Pace (always the old Balanced), Accent color and Text size (a theme
    keeps its own look), the start-up screen switch (always shown), "The overlay only while Path of Exile 2 is in
    front" (always) and Expedition's Auto switch and key (always Auto)."""
    for k in ("pace", "accent", "ui_scale", "splash", "overlay_game_only"):
        S.pop(k, None)
    rm = S.get("remnant")
    if isinstance(rm, dict):
        rm.pop("auto", None)
        rm.pop("key", None)


def _no_recap_2124(S):
    """2.124.0: the joke Death Recap card is gone; the lines over the bar are part of the overlay now (no Dock
    switch, no spot of their own)."""
    S.pop("recap_seen", None)
    t = S.get("tracker")
    if isinstance(t, dict):
        t.pop("goal_dock", None)
        t.pop("goal_pos", None)


def _cols_2125(S):
    """2.125.3: Bulk Pricing shows every column (Columns ▾ turns them off); the old "extra columns on" list goes, and
    the Item column's remembered width (it hid the columns after it)."""
    S.pop("bulk_cols", None)
    cw = S.get("col_widths")
    if isinstance(cw, dict):
        cw.pop("name", None)


def _pc_settings_2125(S):
    """2.125.5 (feedback): Price checking lost Valuable mods (the app's amount again), Skip cheap items (gone) and the
    two "in the app" choices of Where the price shows but Here (the app comes to the front)."""
    from .config import DEFAULTS
    S["good_div"] = DEFAULTS["good_div"]                 # (still read - the app's own amount, no setting)
    S.pop("floor", None)
    S["pc_front"] = True


def _shortcuts_2126(S):
    """2.125.6 (feedback): Bulk Pricing's shortcuts (skip a search the Mod Book agrees on; the model prices by itself)
    are gone - every item is searched."""
    S.pop("memory_shortcut", None)
    S.pop("model_shortcut", None)


def _favours_art_2129(S):
    """2.129.0: Favours prices no longer use poe.ninja's official art - the pictures 2.128 downloaded (art/ninja in
    the data folder) and the first learned file (whole cells) go."""
    import os
    import shutil
    from .config import P
    shutil.rmtree(os.path.join(P("art"), "ninja"), ignore_errors=True)
    try:
        os.remove(P("favour_icons.json"))
    except OSError:
        pass


def _whispers_after_21292(S):
    """2.129.2: Trade whispers is on or off - its "after the campaign" option is gone."""
    w = S.get("whispers")
    if isinstance(w, dict):
        w.pop("after", None)


def _leftovers_2126(S):
    """2.126.0: settings left behind by features removed earlier (one-key copy and "Other ways of copying",
    2.98.3) - nothing reads them."""
    for k in ("quick_copy_key", "hotkey_only"):
        S.pop(k, None)


def _ritual_id_21324(S):
    """2.132.4: the Ritual Identifier is a Ritual helper option (ritual_alert.identify) - its own switch is gone."""
    S.pop("ritual_id", None)


def _regex_keys_21326(S):
    """2.132.6: the one Regex key (it copied a search) becomes Regex key 1 (it types it in the stash search)."""
    key = str(S.get("regex_key") or "")
    if key and not S.get("regex_keys"):
        ref = str(S.get("regex_hotkey_search") or "current:tablet")
        S["regex_keys"] = [{"key": key, "favs": [ref]}]
    S.pop("regex_key", None)


def _no_motion_21351(S):
    """2.135.1: nothing fades any more - the Reduce motion switch is gone."""
    S.pop("reduce_motion", None)


def _alerts_top_21371(S):
    """2.137.1: alert cards move from Center (on your character) to Top center - once; you can pick Center again."""
    c = S.get("alert_card")
    if isinstance(c, dict) and c.get("where") in (None, "center"):
        c["where"] = "top"


def _no_previews_21430(S):
    """2.143.0: no preview builds any more (each version is tested locally, then released) - the switch is gone."""
    S.pop("update_preview", None)


def _helpers_on_ui(S):
    """UI overhaul: every helper on once (each keeps its own switch) - they were opt-in, so most players never found
    them."""
    for key in ("topup", "breaks", "map_profit", "temple", "music"):
        c = S.setdefault(key, {})
        if isinstance(c, dict):
            c["on"] = True
    feats = S.setdefault("features", {})
    for key in ("topup", "breaks", "mapprofit", "temple", "music"):
        feats[key] = True
    ov = S.setdefault("overlay", {})
    if isinstance(ov, dict):
        ov["chat_enabled"] = True


def _helpers_one_switch(S):
    """Features menu: app pages only. The BETA helpers (Top Up Reminders, Break reminders, Map profit, Temple Helper,
    Music Controls) were a feature switch too, and both had to be on - now their own switch in Overlay › Helpers is
    the only one. A helper whose feature was off stays off; the feature keys go."""
    feats = S.get("features")
    if isinstance(feats, dict):
        for fkey, (dkey, sub) in (("topup", ("topup", "on")), ("breaks", ("breaks", "on")),
                                  ("mapprofit", ("map_profit", "on")), ("temple", ("temple", "on")),
                                  ("music", ("music", "on"))):
            if fkey in feats and not feats.pop(fkey):
                d = S.setdefault(dkey, {})
                if isinstance(d, dict):
                    d[sub] = False
        feats.pop("desecrate", None)                     # (2.132.2: the Desecration Helper isn't BETA any more)
    # Setup (first-run, one question a screen): it is for new installs - someone updating has used the app, so it
    # isn't shown to them (Settings › General › Features › Run setup again brings it back). The old picker's
    # data-folder and unrated-mods questions are gone (Settings › Advanced › Data folder; Settings › Price checking).
    if S.get("seen_version") and not S.get("features_asked"):
        S["features_asked"] = "done"
    S.pop("data_dir_asked", None)
    S.pop("ask_unrated_asked", None)


def _no_dev_options(S):
    """Owner: Settings › Advanced › Developer options and its Show developer options switch are gone - Debug mode
    sits in Problems on its own. Debug mode only worked with that switch on, so it stays off for anyone who had the
    switch off."""
    if not S.pop("dev_options", False):
        S["debug_mode"] = False


def _look_key_policy(S):
    """GGG policy (Nov 2026: one screen read per key press): the helpers read on the Read Key. Gone: the Delirium
    helper process (its switch util_delirium_autostart; the helper itself is gone - _delirium_gone), Fast Beacon
    Read (temple.fast_read) and the Ritual tribute reminder (ritual_alert.tribute_reminder)."""
    S.pop("util_delirium_autostart", None)
    t = S.get("temple")
    if isinstance(t, dict):
        t.pop("fast_read", None)
    r = S.get("ritual_alert")
    if isinstance(r, dict):
        r.pop("tribute_reminder", None)


def _delirium_gone(S):
    """GGG policy (Nov 2026): the Delirium helper is removed (its End Delirium check needed a screen read of its own):
    its settings (delirium: on, sound), its switch on the overlay bar and the old process's switch go."""
    S.pop("delirium", None)
    S.pop("util_delirium_autostart", None)
    tr = S.get("tracker")
    if isinstance(tr, dict):
        tr.pop("delirium", None)
        if isinstance(tr.get("bar"), dict):
            tr["bar"].pop("delirium", None)


def _ritual_only_favours_306(S):
    """3.0.6 (owner: reminders, counting and identifying rituals can't be automated under GGG policy): the Ritual helper
    keeps Favours prices only. Gone: the counter's readout (ritual_alert.readout), the leave reminder
    (leave_reminder), the Ritual Identifier (identify) and the helper's alert sound (sound). Favours prices was its
    own switch (favours): it is the helper now - someone who had the helper on with Favours prices off turns the
    helper off (it would price again otherwise)."""
    r = S.get("ritual_alert")
    if not isinstance(r, dict):
        return
    if r.pop("favours", True) is False:
        r["on"] = False
    for k in ("readout", "leave_reminder", "identify", "sound"):
        r.pop(k, None)


def _breach_reminder_follows_helper(S):
    """Hiveblood's leave reminder is part of the helper being on: its own setting (leave_reminder) is gone."""
    b = S.get("breach_alert")
    if isinstance(b, dict):
        b.pop("leave_reminder", None)


def _look_key_default(S):
    """GGG policy, owner decision: the Read Key is Ctrl+Shift+R as the app comes. A Read Key that is unset (or was the
    old Tab, cleared by look_key_dedicated) becomes it; a key you picked is kept. A person with an older install is
    told once (look_page.look_key_notice). Cleared later by you: it stays cleared (the empty state)."""
    from .screenread import DEFAULT_KEY
    k = str(S.get("look_key") or "").replace(" ", "").lower()
    if not k or k == "tab":
        S["look_key"] = DEFAULT_KEY
        if S.get("seen_version"):
            S["look_key_notice"] = True


def _look_key_dedicated(S):
    """GGG policy, the strictest reading (owner): a read needs a key pressed for it - the Read Key is a key only for
    the read, not set as the app comes. Tab (the game's map key, the old default - an unset key meant Tab after
    look_key_policy) is cleared; someone who read on Tab gets one notice saying why (look_page.look_key_notice)."""
    k = S.get("look_key")
    was_tab = str(k or "").replace(" ", "").lower() == "tab" or (
        not k and "look_key_policy" in (S.get("migrations_done") or []))    # (a build where unset meant Tab)
    if not k or was_tab:
        S["look_key"] = ""
        if was_tab and S.get("seen_version"):    # (someone who read on Tab is told why; others meet it in What's new)
            S["look_key_notice"] = True


def _read_key_name(S):
    """3.0.1 (Ctrl+Shift+R = Read, R for Read): the Look key is the Read Key. Its NEW chip went once
    you opened Settings › Keybinds or pressed it (settings.json "new_seen", by the feature's name) - that stays so
    under the new name; the old name is kept too (an older build put back still finds it). The key itself was always
    saved as look_key: nothing to move."""
    seen = S.get("new_seen")
    if isinstance(seen, dict) and seen.get("Look key") and not seen.get("Read Key"):
        seen["Read Key"] = seen["Look key"]


def _strats_find_306(S):
    """3.0.6 Farming Strategies (the approved mockups): one row per strat (the Cards | List switch is gone) and one
    dropdown per filter (More filters / Fewer filters is gone) - their saved choices go."""
    S.pop("mm_layout", None)
    S.pop("mm_more_filters", None)


def _split_layout(S):
    """Owner decision: Split is a Layout, not a style - a saved "flanks" style becomes Layout Split with Style
    Hairline (the same box-less look; ovlight.retire_look)."""
    from .ovlight import retire_look
    t = S.get("tracker")
    if isinstance(t, dict):
        retire_look(t)


def _topup_key_gone(S):
    """Owner decision: Top Up no longer learns an item from a key press - you pick items in Top Up Reminders. The
    saved key goes quietly."""
    S.pop("topup_key", None)
    S.pop("topup_key_2131", None)


def _no_stash_reading_307(S):
    """3.0.7 (GGG policy audit): reading a stash tab through the trade site (Bulk Pricing's Add from stash tab, Wealth's
    synced tabs) is gone, and the app keeps no account name. Deleted: the account name, every stash-tab price and
    marker price, the tab list's order and the reading's log file. Bulk Pricing's tabs are plain lists now: the
    Manually Add list is Tab 1, and a stash tab's list that has items (session.json) stays as the next tab."""
    import os
    import re
    from .config import load_json, P
    for k in ("wealth_account", "own_markers", "stash_order", "wealth_skip_tab"):
        S.pop(k, None)
    if isinstance(S.get("notices_closed"), dict):
        S["notices_closed"].pop("pctab_beta", None)          # (the stash tab reading's BETA notice)
    pc = S.get("pctab") if isinstance(S.get("pctab"), dict) else {}
    try:
        recs = (load_json("session.json", {}) or {}).get("records") or []
        used = {str(r.get("src")) for r in recs if isinstance(r, dict)}
    except Exception:
        used = set()
    tabs = [{"id": "manual", "name": "Tab 1", "renamed": False}]
    for t in pc.get("tabs") or []:
        if not isinstance(t, dict) or not t.get("id") or t["id"] == "manual" or f"tab:{t['id']}" not in used:
            continue
        name = str(t.get("name") or "").strip()[:24]
        renamed = t["renamed"] if "renamed" in t else not re.fullmatch(r"Tab \d+", name)
        tabs.append({"id": str(t["id"]), "name": name, "renamed": bool(renamed and name)})
    cur = pc.get("current") if pc.get("mode") == "Stash tab" else "manual"
    S["pctab"] = {"tabs": tabs, "current": cur if cur in [t["id"] for t in tabs] else "manual"}
    try:
        os.remove(P("tab_reader_log.txt"))
    except OSError:
        pass


STEPS = (
    ("modbook_import", "1.x", "app", _modbook_import, "modbook_imported"),
    ("rules_scoped", "2.6.0", "app", _rules_scoped, "rules_scoped_26"),
    ("status_ib", "2.79.2", "settings", _status_ib, "status_ib_2792"),
    ("copy_hotkey_only", "2.98.3", "app", _copy_hotkey_only, "copy_2983"),
    ("gear_plus", "2.99.0", "app", _gear_plus, "gear_plus_299"),
    ("tier_only", "2.114.0", "app", _tier_only, "tier_only_2114"),
    ("ux_2119", "2.119.0", "settings", _ux_2119, None),
    ("no_recap_2124", "2.124.0", "settings", _no_recap_2124, None),
    ("cols_2125", "2.125.3", "settings", _cols_2125, None),
    ("pc_settings_2125", "2.125.5", "settings", _pc_settings_2125, None),
    ("shortcuts_2126", "2.125.6", "settings", _shortcuts_2126, None),
    ("leftovers_2126", "2.126.0", "settings", _leftovers_2126, None),
    ("favours_art_2129", "2.129.0", "settings", _favours_art_2129, None),
    ("whispers_after_21292", "2.129.2", "settings", _whispers_after_21292, None),
    ("ritual_id_21324", "2.132.4", "settings", _ritual_id_21324, None),
    ("regex_keys_21326", "2.132.6", "settings", _regex_keys_21326, None),
    ("no_motion_21351", "2.135.1", "settings", _no_motion_21351, None),
    ("alerts_top_21371", "2.137.1", "settings", _alerts_top_21371, None),
    ("no_previews_21430", "2.143.0", "settings", _no_previews_21430, None),
    ("helpers_on_ui", "UI overhaul", "settings", _helpers_on_ui, None),
    ("helpers_one_switch", "UI overhaul", "settings", _helpers_one_switch, None),
    ("no_dev_options", "UI overhaul", "settings", _no_dev_options, None),
    ("look_key_policy", "GGG policy", "settings", _look_key_policy, None),
    ("look_key_dedicated", "GGG policy", "settings", _look_key_dedicated, None),
    ("delirium_gone", "GGG policy", "settings", _delirium_gone, None),
    ("look_key_default", "GGG policy", "settings", _look_key_default, None),
    ("read_key_name", "3.0.1", "settings", _read_key_name, None),
    ("strats_find_306", "3.0.6", "settings", _strats_find_306, None),
    ("ritual_only_favours_306", "3.0.6", "settings", _ritual_only_favours_306, None),
    ("breach_reminder_follows_helper", "3.0.6", "settings", _breach_reminder_follows_helper, None),
    ("split_layout", "Split layout", "settings", _split_layout, None),
    ("topup_key_gone", "3.0.6", "settings", _topup_key_gone, None),
    ("no_stash_reading_307", "3.0.7", "settings", _no_stash_reading_307, None),
)


# ---------------------------------------------------------------- the runner
def pending(S, stage=None):
    """The steps not done yet (of one stage, or all)."""
    done = set(S.get("migrations_done") or [])
    return [s for s in STEPS if s[0] not in done and not (s[4] and S.get(s[4])) and (stage is None or s[2] == stage)]


def run(S, stage, save=None):
    """Run this stage's steps not done yet, in order. -> [ids done now]. Never raises."""
    done_now = []
    try:
        todo = pending(S, stage)
    except Exception:
        buglog.record("error", "migrations: reading what's done", exc=True)
        return done_now
    if not todo:
        return done_now
    done = list(S.get("migrations_done") or [])
    tries = dict(S.get("migrations_tries") or {})
    for sid, ver, _stage, fn, legacy in todo:
        try:
            fn(S)
        except Exception:
            tries[sid] = tries.get(sid, 0) + 1
            gave_up = tries[sid] >= TRIES
            buglog.record("error", f"settings update {sid} ({ver})" + (" - tried 3 times, left" if gave_up else ""),
                          exc=True)
            if not gave_up:
                continue
        done.append(sid)
        done_now.append(sid)
        tries.pop(sid, None)
        if legacy:
            S[legacy] = True                    # (an older build put back on this PC skips it too)
    S["migrations_done"] = done
    if tries:
        S["migrations_tries"] = tries
    else:
        S.pop("migrations_tries", None)
    if save is not None:
        try:
            save()
        except Exception:
            buglog.record("error", "migrations: saving settings", exc=True)
    return done_now


# 3.0.6 (owner): a strat's Farm type tags are Map type now - City area farm is City; Sacred Bloom farm isn't a real
# thing (dropped). moneymakers.retag uses this when a strat is read (the shared file, yours, the board, an import).
STRAT_OLD_TAGS = {"City area farm": "City", "Sacred Bloom farm": None}
