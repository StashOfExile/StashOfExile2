"""2.131.0 Feature Picker, now Setup (feedback: ask the player which features they want, with menu options to
enable or disable them - a disabled feature does not listen for its hotkey): the app's features in a few
groups, each one switch. Off: its pages leave the menu and its keys do nothing (the game gets them); its data is
kept. Setup asks on a new install, one question a screen (features_page.py): closed without choosing, it comes back
at the next start. The same switches live in Settings › General › Features (one place in Settings). The beta features are a cluster of their own - this replaces the single "Show beta features" switch.
Only app pages and features are here; every overlay helper's one switch is in Overlay › Helpers (HELPER_SWITCHES)."""
from .config import SETTINGS

GROUPS = (
    {"key": "price", "name": "Price checking", "keys": "pc_key",
     "what": "Hover an item in game and press the key: its price from the trade site's listings. Pages: "
             "Price Checks, Favorites, Rate Mods, Mod Book.",
     "modules": ("pricecheck", "favorites", "modbook", "ratemods", "library")},
    {"key": "bulk", "name": "Bulk Pricing", "keys": "Ctrl+Alt+C",
     "what": "Add many items in game (Manually Add), or Add from stash tab: they're priced as a list, in the "
             "background. Best for tablets, waystones and jewels; price expensive gear with Price Checks.",
     "modules": ("checks",)},
    # nav phase 1: named as the sidebar names it (was "Game Overlay"); the Regex page is no longer in it - switching
    # the overlay off hides the overlay's Regex part and the Regex keys, not the Regex page
    {"key": "overlay", "name": "Overlay", "keys": "",
     "what": "Over the game: a session timer, Notes, Calc, Regex and the helpers (Breach, Ritual, "
             "Expedition, Trade whispers...).",
     "modules": ("notes",)},                  # (nav phase 2: its page, Overlay, is in SHARED - Overlay Settings is gone)
    {"key": "planning", "name": "League tools", "keys": "",             # nav phase 1: the sidebar's group name (was
                                                                  # "Planning & Farming")
     "what": "League Plan (your goals and farm plan), Map Library (rank every map) and Leaderboards (fastest "
             "runs).",
     "modules": ("plan", "maps", "leaderboards")},
    {"key": "rates", "name": "Exchange Rates", "keys": "",
     "what": "What each currency is worth in divines (poe.ninja), a converter, and the Rates menu on the Overlay.",
     "modules": ("rates",)},
    {"key": "wealth", "name": "Wealth",
     "what": "What your stash is worth in divines: Scan stash reads your currency and league tabs from the screen; "
             "each scan adds a point to your worth over time.",
     "modules": ("wealth",)},
    {"key": "insights", "name": "Market Insights",
     "what": "From your own price checks: your most valuable items, the mods worth the most and the priciest listings "
             "seen - by kind of item. Nothing extra is searched.",
     "modules": ("insights",)},
    {"key": "search", "name": "Game Search",                  # (2.143.0: these three out of BETA)
     "what": "Look up any skill, item, mod or keyword in the game's own data, on your PC.", "modules": ("search",)},
)
BETA = (
    {"key": "money", "name": "Farming Strategies",
     "what": "Farming strategies from the community: pick one, run it, see what it really made.",
     "modules": ("money",)},
    {"key": "crafthelper", "name": "Craft Helper",
     "what": "Copy a tablet or jewel: each mod gets a letter, S to F, and the item a next step - worth pricing, craft "
             "on, reforge or vendor. No prices are shown.",
     "modules": ("crafthelper",)},
)
# Features owner feedback (the overlay-related helpers do not belong in this features menu: group them with the
# overlay settings helpers and only there): these helpers are no features - each has ONE switch,
# its own row in Overlay › Helpers (the helper's own setting below). Their old feature keys are gone
# (migrations._helpers_one_switch).
HELPER_SWITCHES = {       # Helpers-table key -> (its settings dict, its on key, its name - names.FEATURES)
    "topup": ("topup", "on", "Top Up Reminders"),
    "breaks": ("breaks", "on", "Break reminders"),
    "mapprofit": ("map_profit", "on", "Map profit"),
    "temple": ("temple", "on", "Temple Helper"),
    "music": ("music", "on", "Music Controls"),                    # 2.134.0
    "sekhemas": ("sekhemas", "on", "Trial of the Sekhemas"),       # the trial map's legend (BETA)
}
# the BETA helpers (Overlay › Helpers and Setup say "Beta · " in their gray line). (Owner: Break reminders, Top Up
# Reminders and Music Controls are out of beta.)
BETA_HELPERS = ("temple", "mapprofit", "sekhemas")
ALL = GROUPS + BETA
# the Overlay page (its tabs: Helpers, On the Overlay, Look, Options, Sessions): shown while the overlay feature is on
SHARED = {"tracker": ("overlay",)}          # (UI overhaul: the planning pages are their own now)


def cfg():
    """{feature: on} - every group on and the beta ones as the old Beta features switch was, until you choose."""
    c = SETTINGS.setdefault("features", {})
    for g in GROUPS:
        c.setdefault(g["key"], True)
    for g in BETA:
        c.setdefault(g["key"], True)
    return c


def on(key):
    return bool(cfg().get(key, True))


def group_of(module_key):
    for g in ALL:
        if module_key in g["modules"]:
            return g["key"]
    return None


def module_on(module_key):
    """Is this page's feature on? (A page in no group - Settings, the Overlay page's own - always is.)"""
    if module_key in SHARED:
        return any(on(k) for k in SHARED[module_key])
    g = group_of(module_key)
    return True if g is None else on(g)


def helper_on(key):
    """One of HELPER_SWITCHES' helpers: its own switch (Overlay › Helpers) - its one setting (defaults filled in)."""
    import importlib
    d, k, _name = HELPER_SWITCHES[key]
    try:
        return bool(importlib.import_module("." + key, __package__).cfg().get(k))
    except Exception:
        return bool((SETTINGS.get(d) or {}).get(k))


def any_beta():
    """A BETA feature or a BETA helper is on (their notes in What's new show then)."""
    return any(on(g["key"]) for g in BETA) or any(helper_on(k) for k in BETA_HELPERS)


def set_on(key, value):
    cfg()[key] = bool(value)
    SETTINGS["labs"] = any_beta()          # (older code: "a beta feature is on")


def asked():
    """Setup (features_page.py): None (ask at the next start), "done" (answered or skipped) or "never" (an older
    build's Never ask again)."""
    return SETTINGS.get("features_asked")
