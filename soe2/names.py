"""One name per feature (2.126.0, UX rule: "One name per feature (soe2/names.py). No synonyms.").

PAGES   - every page's name, by its module key (soe2/modules/). Page names are in Title Case.
FEATURES - the names of the parts inside pages that a person meets by name (helpers, switches, sections).
OLD     - names that were used before, or crept in as synonyms -> the one name to use. They never appear in the
          app's text; the app still knows the old page names (App.page_key), so an old saved layout or a link opens
          the right page.

Adding a feature: put its name here first, use that exact name everywhere (labels, tooltips, What's new, README).
Renaming one: change it here, add the old name to OLD, and run tools/check_names.py (it lists every leftover)."""

PAGES = {
    "dashboard": "Dashboard",           # UI overhaul: the first page
    "pricecheck": "Price Checks",
    "checks": "Bulk Pricing",
    "favorites": "Favorites",
    "insights": "Market Insights",
    "library": "Under the Hood",
    "modbook": "Mod Book",
    "ratemods": "Mod Lab",              # 3.2.0 owner: was Rate Mods
    "wealth": "Wealth",
    "money": "Farming Strategies",          # UI overhaul: was Money Makers (Craft Helper moved to its own page)
    "crafthelper": "Craft Helper",      # UI overhaul: was a Money Makers tab
    "regex": "Regex",
    "search": "Game Search",
    "rates": "Exchange Rates",
    "tracker": "Overlay",               # nav phase 2: one page, tabs Helpers · On the Overlay · Look · Options (+ Sessions)
    "maps": "Map Library",
    "leaderboards": "Leaderboards",
    "plan": "League Plan",
    "mapprofit": "Map Profit",         # 2.132.6 Overlay ↳ Map Profit
    "notes": "Notes",
    "settings": "Settings",
}

FEATURES = (
    "Suggest a Feature",        # 3.2.0 owner: the bottom bar, next to Report a bug - an idea becomes a GitHub issue
    "Compare a currency",       # Exchange Helper: one currency's worth in every other (was Check a flip)
    "Name badge",               # GGG policy audit: STASH OF EXILE 2 in a small badge under the overlay's clock, every
                                # style and layout (ovlight.BADGE) - so the overlay never reads as part of the game
    "Alert card",               # 2.131.0 every helper's alert over the game (alertcard.py); 2.131.6: was "calm alert card"
    "Regex keys",               # 2.132.6 a key types 1-4 Regex favorites in the stash search, one per press
    "Temple Helper",
    "Music Controls",
    "Vaal Lens",                # 2.140.0 a card in Vaal Ruins and the temple: crystals, the console's board, notes
    "Trial of the Sekhemas",    # BETA helper: press the Read Key on the trial map - its legend beside it: Rooms,
                                # Boons, Afflictions (✓ Take / ✕ Avoid / ! Mild); a hovered affliction or boon gets
                                # a one-line card
    "Map profit",               # 2.132.0 what each map earned, from your inventory (Overlay › Helpers)
    "Alerts show",              # 2.131.0 Overlay › Helpers: where and how big the alert card is
    "Hide all overlay information from screen captures",   # 3.0.6 one switch, in Overlay › Options (Helpers and
                                # Quick settings show its state and link there; was "Hide the overlay from screen
                                # captures", the bar only)
    "Data folder",              # 2.131.0 where your settings and lists live (Settings › Advanced)
    "Setup",                    # the first start's questions, one a screen: features, the Overlay, its helpers
                                # (2.131.0 - UI overhaul: the Feature Picker; Settings › General › Run setup again)
    "Top Up Reminders",         # 2.131.0 what's running low in your inventory (Overlay › Helpers)
    "Back from a map",          # owner decision: the one card back home after a map - one Read Key press counts the
                                # map's loot (Map profit) and checks your top ups (Top Up Reminders)
    "Features",                 # 2.131.0 Settings › General: one switch per app feature, plus the BETA ones (the
                                # overlay's helpers are switched in Overlay › Helpers only)
    "Break reminders",          # 2.131.0 Overlay › Helpers: a kind nudge in long sessions
    "Campaign Helper",
    "Campaign Bar",             # the overlay in campaign zones: the line over the bar (what to do now) and the bar's
                                # Zone · You · Got so far · Act time (the Panel: one card)
    "Clear All",                # Bulk Pricing › Items strip: empties the list shown
    "Community data sharing",
    "Error reports",            # 2.137.0 Settings › Privacy & community: what went wrong in the app, opt-in
    "Data pack",                # the Craft Helper's mod data from GitHub
    "Keybinds",                 # Settings: every key the app listens for (2.127.0: was Keys)
    "Read Key",                 # GGG policy (Nov 2026): a key only for this - each press, the helpers read the
                                # screen once (Ctrl+Shift+R as the app comes; Settings › Keybinds)
    "Read mark",                # GGG policy: the chip that shows for a second at each screen / clipboard read -
                                # "Reading the screen", or "Read the screen · nothing here" when the press found
                                # nothing a helper could use (readmark.READING / READ_NOTHING)
    "Desecration Helper",       # at The Well of Souls
    "Exchange Helper",
    "Favours prices",           # what the Ritual helper does: prices on the Favours window's rewards (3.0.6: not a
                                # separate switch - the Ritual helper on = Favours prices on)
    "Filter in the Ritual window",   # the Ritual helper: the game's hidden setting that applies your filter there
    "Mechanic Helper",
    "Quick settings",           # the overlay's ⚙
    "Reset position",           # Overlay › Options: the overlay back in its own place
    # nav phase 2 (the owner's words): Layout = the overlay's shape, Style = how the overlay looks, Theme = the whole
    # app's look. "Style" is never the app's look, "Theme" never the overlay's.
    "Layout",                   # Overlay › Look and Quick settings: Bar | Panel | Split
    "Split",                    # the Layout of two halves by the orbs (the run half, the tools half) - any Style
                                # (was the "flanks" style, shown as Split)
    "Swap sides",               # Quick settings, shown only while the Layout is Split: shown as "⇄ Swap sides" -
                                # the run half by the mana orb, the tools half by the life orb
    "Style",                    # Overlay › Look: the overlay styles (Classic, Light, Ornate)
    "Theme",                    # Settings › Appearance: the app's look
    "Scan stash",
    "Search Options",           # Settings › Price checking
    "Session timer",
    "Manually Add",             # Bulk Pricing: Ctrl+Alt+C on each item in game, into the tab shown (was "Copy items";
                                # 3.0.7: the only way - Add from stash tab is removed, so there is no switch)
    "Trade Whisper Watcher",
    "History",                  # UI overhaul: Price Checks ↳ History - every item you priced (was the Recent menu)
    # drawer build (drawer/PLAN.md 1.1): never "compact", "side panel", "game mode" or "portable" for these
    "Drawer",                   # the app shown as a side panel over the game (Settings › General › Window)
    "Full window",              # the app as a normal window, where you left it
    "Put away",                 # the app off screen: minimized (its taskbar button stays) or in the tray
    "Drawer key",               # shows the app and puts it away (Settings › Keybinds; Ctrl+Shift+Space)
    "Widened",                  # owner (base widening): a white / blue base's card - the line saying how its search
                                # widened (quality, item level, listed within) after Broaden Search
    "Broaden Search",           # owner: the price check's orange button while too few were found - each click
                                # runs the next widening step (one search); shown as "↔ Broaden Search". A white /
                                # blue base widens its boxes; 3.0.6, any other item: values 10%, then 20% looser,
                                # then one mod fewer (engine.broaden_step)
    "Price check overlay",      # the price card over the game (pcpop.py) - "Where the price shows"
    "NEW chip",                 # 3.0.0 (newchip.py): the word NEW on a new feature's row and its page's rail icon,
                                # until you open or use it
    # 3.0.6 Farming Strategies (the approved mockups): Find (the tab: was Strats) - the search, the filters, a row per
    # strat (best per hour first; no "Best for you right now" card - owner, 2026-11-17) and Quick tips folded at the bottom (was the Lucrative Strats
    # tab). An opened strat (3.0.6, mockup v2): In your map device (its slots), How it goes (its steps), Atlas master,
    # Content, Loot to sell, From the author (older text, folded); Where your money came from (your logs)
    "Find",
    "Run this strat",
    "Quick tips",
    "How it goes",
    "Where your money came from",
    # 3.0.6 New strat (was the Add my own form): one page in five parts - What it is, Your tablets, Your waystone,
    # Atlas masters, How it goes - with Made for you (a regex and a trade search from the ticked mods of your copies)
    # and Cost per map; Find's League filter (your league, or All leagues). Never another tool's words for these
    # ("Session Configuration", "Loadout"): what you put in for a map is "in your map device"
    "New strat",
    "Made for you",
    "Atlas masters",
    "Cost per map",
    "All leagues",
    "In your map device",
    "All",                      # 3.0.6 Find › From: Official, Community and Mine together (the default)
    "Map type",                 # 3.0.6 New strat › What you farm (was Farm type): City, Juiced maps ...
    "Pick by hand",             # 3.0.6 New strat › In your map device: a slot filled without a copy
    "Waystone modifiers",       # 3.0.6 Waystone by hand: its numbers (at least), as a waystone reads them
    "From the author",          # 3.0.6 an opened strat: its older free text, folded at the bottom
    "Parts",                    # 3.0.6 New strat's side panel: what's done
    # Rate Mods (owner, the Rate Mods redesign): the page's two views, the card's three facts, the Table's bar and the
    # tier groups (MIX B: "How much is each kind of roll worth?" - Top rolls, Middle rolls, Low rolls)
    "One at a Time",            # Rate Mods: one mod on a card, S A B C D F
    "Table",                    # Rate Mods: many mods at once, ticked rows and Rate selected
    "Seen in listings",         # the middle asking price and how many listings the app saw with the mod
    "Players",                  # what most players rate the mod (the community's ratings) and how many votes
    "Your rating",              # your letter for the mod and what it counts as (High, Normal, Ignore)
    "Rate selected",            # Rate Mods › Table: one rating for every ticked row
    "By roll",                  # a mod's letter per group of rolls (Top rolls, Middle rolls, Low rolls) - the Table
                                # shows "same" or "S · B · F"; a price check gives a roll its group's letter (F: left
                                # out the low-tier way - not searched, a note, tick it to search on it)
    "Same for every roll",      # By roll's default: every group takes the mod's one letter
    "Next up",                  # Rate Mods › One at a Time, under the card: the next 3 mods
    "Just rated",               # Rate Mods › One at a Time, under the card: the last 5 you rated
    "Rate mods one at a time",  # Rate Mods › Table: the one orange button (opens One at a Time)
    "Linux check",              # Linux build: Settings › Advanced and  StashOfExile2 --check-linux  - session, keys,
                                # screen picture, clipboard, key sending, OCR, Client.txt, each with its fix
)

# The item card's sections (Price Checks, Bulk Pricing), top to bottom - the owner's one order. A listing's Whole item
# (soe2/listingcard.py) uses the same words, in the same order, for the parts it has.
CARD_SECTIONS = {"props": "BASE AND PROPERTIES", "req": "REQUIREMENTS", "aug": "AUGMENTS", "misc": "ITEM FLAGS",
                 "stats": "MODS", "pseudo": "PSEUDO FILTERS", "trade": "TRADE FILTERS"}

# 3.0.6 Scan stash: the Socketables tab's five pages, named for the buttons along its top, left to right (the game's
# buttons show pictures only). The scan's card says which button: "Open your Socketables tab (Idols page, button 4 of 5)".
SOCKETABLES_PAGES = ("Runes", "Kalguuran Runes", "Soul Cores", "Idols", "Ancient Augments")   # (the game's own names, on hover)

# Game Search's categories that come from gamedb.json (tools/build_gamedb.py), in the order they follow "Endgame Items".
# Title Case. gamedb.json, Game Search and the build tool all use exactly these.
GAME_SEARCH_GROUPS = ("Tablets", "Waystones", "Atlas Masters", "Vaal Temple", "Pinnacles & Areas",
                      "Trial of the Sekhemas", "Trial of Chaos", "Ritual Altars", "Leagues")

OLD = {
    "Rate Mods": "Mod Lab",                     # owner, after 3.1.0
    # 2.132.4 - 2.143.0: the overlay's settings were a child page, Overlay ↳ Overlay Settings. Nav phase 2: they are
    # the Overlay page's tabs (Helpers, On the Overlay, Look, Options) - an old name opens the Overlay page
    "Overlay Settings": "Overlay",
    "Overlay ↳ Settings": "Overlay",
    "Overlay › Settings": "Overlay",
    "Overlay appearance": "Overlay › Look",          # (the button that opened Settings › Appearance › Overlay)
    # page names before Title Case (2.120.0) and before their renames
    "Price checks": "Price Checks",
    "Mod book": "Mod Book",
    "Map library": "Map Library",
    "Exchange rates": "Exchange Rates",
    "Game search": "Game Search",
    "Under the hood": "Under the Hood",
    "Item library": "Under the Hood",
    "Item inspector": "Under the Hood",
    "Price breakdown": "Under the Hood",
    "Utilities": "Notes",
    "Money makers": "Farming Strategies",
    "Money Makers": "Farming Strategies",
    "Farming Strats": "Farming Strategies",
    "Market insights": "Market Insights",
    "League plan": "League Plan",
    "Bulk pricing": "Bulk Pricing",
    "Bulk Price Checker": "Bulk Pricing",
    # nav phase 1: the overlay's feature switch is named as the sidebar names the overlay
    "Game Overlay": "Overlay",
    # Features: app pages only - the first start's popup asks one question a screen
    "Feature Picker": "Setup",
    # features
    "Calm alerts": "Alert card",          # 2.131.6 (feedback: the old name sounded wrong)
    "calm alert card": "Alert card",
    "Labs": "Features",
    "Beta features": "Features",
    "Craft helper": "Craft Helper",
    "Desecration helper": "Desecration Helper",
    "Well of Souls helper": "Desecration Helper",
    "Campaign helper": "Campaign Helper",
    "Exchange helper": "Exchange Helper",
    "Mechanic helper": "Mechanic Helper",
    "Whisper watcher": "Trade Whisper Watcher",
    "Session tracker": "Session timer",
    "Stash scan": "Scan stash",
    "Quick Settings": "Quick settings",
    "Flanks": "Split",                  # the Split layout was the "flanks" style
    "Swap halves": "Swap sides",
    "Community Data Sharing": "Community data sharing",
    "How searches are made": "Search Options",
    "dearest": "most valuable",          # 2.129.0 (feedback): nobody uses that word
    "Clear list": "Clear All",          # Bulk Pricing's button (2.126.0: on screen, in the Items strip)
    "Settings › Keys": "Settings › Keybinds",          # 2.127.0
    "Settings > Keys": "Settings › Keybinds",
    "Overlay + Here": "Price check overlay",          # drawer build: each choice names one place (In the app | ...)
    "Read key": "Read Key",             # GGG policy: one name for the key the helpers read on (a name: Title Case)
    "Screen key": "Read Key",
    "Look key": "Read Key",             # 3.0.1 (owner: Ctrl+Shift+R = Read, R for Read)
    "Hide the overlay from screen captures": "Hide all overlay information from screen captures",   # 3.0.6
    "Lucrative Strats": "Quick tips",   # 3.0.6 Farming Strategies: the tab folded into Find
    "Lucrative strats": "Quick tips",
    "Track in Strat Tracker": "Run this strat",
    "You need": "In your map device",                # 3.0.6 an opened strat's slots (mockup v2)
    "Session Configuration": "In your map device",     # 3.0.6: other tools' words - never ours
    "Active Loadout": "In your map device",
    "Loadout": "In your map device",
    "Check a flip": "Compare a currency",      # Exchange Helper (owner, 3.0.7)
    "Copy items": "Manually Add",              # Bulk Pricing's source switch (owner, 3.0.7)
    # 3.0.7 (GGG policy audit): reading a stash tab through the trade site is removed - Manually Add is the one way
    "Read a stash tab": "Manually Add",
    "Add from stash tab": "Manually Add",
}

# an old page name that now means another page: before 2.80.0, Bulk Pricing was called "Price checks"
WAS_PAGE = {"Price checks": "checks"}

SMALL = {"a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "by", "at"}


def title_case(name):
    """True if a page name is in Title Case: every word starts with a capital, except small words inside it."""
    words = name.split()
    return all(w[:1].isupper() or (i and w in SMALL) or not w[:1].isalpha() for i, w in enumerate(words))


def key_of(name):
    """The page key for a page name, old or new (None if it isn't a page)."""
    if name in WAS_PAGE:
        return WAS_PAGE[name]
    name = OLD.get(name, name)
    return next((k for k, v in PAGES.items() if v == name), None)
