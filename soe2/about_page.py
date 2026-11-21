"""Settings > About (2.10.0).

About: version, what's new in this version, the GitHub page, the Discord (feedback and help), the license and credits.
(3.0.6: the quick start is gone - the first start's Setup is the guide; About has Run setup again.)"""
import tkinter as tk
import webbrowser
from tkinter import ttk

from . import buglog
from .config import APP_VERSION, pretty_version, save_json, SETTINGS
from .style import C, FONT_TITLE, Tooltip
from .updates import REPO

GITHUB_URL = f"https://github.com/{REPO}"
DISCORD_URL = "https://discord.gg/8dwn9kaGNr"
DISCORD = "#5865F2"
DISCORD_HOVER = "#4752c4"


def _keep_discord():
    """2.116.0 (P10: the Join the Discord button came out gray in some themes): Discord's own colors stay."""
    try:
        from . import themes as _th
        _th.KEEP.update({DISCORD.lower(), DISCORD_HOVER})
    except Exception:
        buglog.caught()


_keep_discord()

def open_link(url):
    try:
        webbrowser.open(url)
    except Exception:
        buglog.caught()


# 2.98.3: who we thank, and their GitHub pages (README › Credits says the same)
CREDITS = (
    ("RePoE (repoe-fork)", "the game data behind the mod lists, Regex, Game Search and tiers - exported from Path of "
                           "Exile 2's own files.", "https://github.com/repoe-fork/repoe-fork"),
    ("poe.ninja (rasmuskl)", "the economy data: Exchange Rates, the rates window over the game, Remnant prices and "
                             "currency values.", "https://github.com/rasmuskl"),
    ("Exiled Exchange 2 (Kvan7)", "general ideas, and the base types, mod wordings, trade-site stat ids and "
                                  "pseudo-total rules in gamedata.json, from its data files under its MIT license; "
                                  "and (2.113.0) the ideas of counting each seller once and keeping a mod's Min "
                                  "within its tier - written our own way.", "https://github.com/Kvan7/Exiled-Exchange-2"),
    ("Sidekick (Sidekick-Poe)", "general ideas. None of its code is used.", "https://github.com/Sidekick-Poe/Sidekick"),
    ("hypr-exiled (gfsd3v)", "the idea for the Trade Whisper Watcher - ours is built from scratch, none of its code "
                             "is used.", "https://github.com/gfsd3v/hypr-exiled"),
    ("poe2pricer (saxe78)", "the idea for Favours prices - finding the Ritual window by a piece of its own art and its "
                            "rewards by their pictures. Ours is written from scratch; none of its code is used.",
     "https://github.com/saxe78/poe2pricer"),
    ("gruvbox by Pavel Pertsev (morhetz)", "the colors of the Gruvbox Dark and Gruvbox Light themes (MIT)",
     "https://github.com/morhetz/gruvbox"),
    ("Catppuccin by the Catppuccin team", "the colors of the Catppuccin Mocha and Catppuccin Latte themes (MIT)",
     "https://github.com/catppuccin/catppuccin"),
    ("Nord by Sven Greb (Arctic Ice Studio)", "the colors of the Nord theme (MIT)",
     "https://github.com/nordtheme/nord"),
    ("Dracula by Zeno Rocha and the Dracula Theme team", "the colors of the Dracula theme (MIT)",
     "https://github.com/dracula/dracula-theme"),
    ("Tokyo Night by Enkia", "the colors of the Tokyo Night theme (MIT)",
     "https://github.com/enkia/tokyo-night-vscode-theme"),
    ("Rosé Pine by the Rosé Pine team", "the colors of the Rosé Pine and Rosé Pine Dawn themes (MIT)",
     "https://github.com/rose-pine/rose-pine-theme"),
    ("Everforest by sainnhe", "the colors of the Everforest Dark theme (MIT)",
     "https://github.com/sainnhe/everforest"),
    ("Kanagawa by Tommaso Laurenzi (rebelot)", "the colors of the Kanagawa theme (MIT)",
     "https://github.com/rebelot/kanagawa.nvim"),
    ("Solarized by Ethan Schoonover", "the colors of the Solarized Dark and Solarized Light themes (MIT)",
     "https://github.com/altercation/solarized"),
    ("NeverSink and Ryonnen (reddit)", "the game's hidden setting that applies your item filter to the Ritual window "
                                       "(Filter in the Ritual window).", "https://www.youtube.com/watch?v=6hiQtcQhB3k"),
    ("Path of Building PoE2 (PathOfBuildingCommunity)", "the anoint recipes.", "https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2"),
    ("Cinzel (Natanael Gama)", "a font of the ornate overlay styles. SIL Open Font License.",
     "https://github.com/NDISCOVER/Cinzel"),
    ("EB Garamond (Georg Duffner, Octavio Pardo)", "a font of the ornate overlay styles. SIL Open Font License.",
     "https://github.com/octaviopardo/EBGaramond12"),
    ("Cormorant (Christian Thalmann)", "the fonts of the Gloom overlay style. SIL Open Font License.",
     "https://github.com/CatharsisFonts/Cormorant"),
    ("Marcellus SC (Brian J. Bonislawsky, Astigmatic)", "the font of the Warbanner overlay style. SIL Open Font "
                                                        "License.", "https://github.com/google/fonts/tree/main/ofl/marcellussc"),
    ("Marcellus (Brian J. Bonislawsky, Astigmatic)", "the Psionic overlay style's text. SIL Open Font License.",
     "https://github.com/google/fonts/tree/main/ofl/marcellus"),
    ("Metamorphous (Sorkin Type)", "the font of the Hellfire overlay style. SIL Open Font License.",
     "https://github.com/google/fonts/tree/main/ofl/metamorphous"),
    ("IM FELL English SC (Igino Marini)", "the font of the Guildhall overlay style. SIL Open Font License.",
     "https://github.com/google/fonts/tree/main/ofl/imfellenglishsc"),
)


class AboutPage:
    """Mixed into App."""

    # ================================================================ Settings > About
    def build_about(self, wrap):
        from .whatsnew import notes_between, plain_lines
        P1, P2 = C["panel"], C["panel2"]
        head = tk.Frame(wrap, bg=C["panel2"], padx=16, pady=16, highlightthickness=1, highlightbackground=C["line"])
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text="StashOfExile2", bg=C["panel2"], fg=C["text"], font=(FONT_TITLE, 18, "bold"),
                 anchor="w").pack(fill="x")
        from .config import TAGLINE
        tk.Label(head, text=TAGLINE, bg=C["panel2"], fg=C["accent"], font=(FONT_TITLE, 12, "italic"),
                 anchor="w").pack(fill="x")                                               # 2.73.2
        tk.Label(head, text=f"Version {pretty_version()}  ·  a toolkit for Path of Exile 2  ·  free and open source "
                            "(AGPL-3.0)", bg=C["panel2"], fg=C["muted"], anchor="w").pack(fill="x")
        try:                                                     # 2.133.0 (feedback: show an active user count)
            from .communitymods import installs
            got = installs()
        except Exception:
            got = None
        if got:
            row = tk.Frame(head, bg=C["panel2"])
            row.pack(fill="x")
            act = f"  ·  {got[1]} active this week" if got[1] is not None else ""
            tk.Label(row, text=f"Community: {got[0]} installs share data{act}", bg=C["panel2"], fg=C["muted"],
                     anchor="w").pack(side="left")
            ci = tk.Label(row, text="ⓘ", bg=C["panel2"], fg=C["muted"], cursor="question_arrow")
            ci.pack(side="left", padx=(4, 0))
            Tooltip(ci, "Only installs with Community data sharing on are counted. Active = sent data in the last 7 "
                        "days. A count only - nothing about who.")
        btns = tk.Frame(head, bg=C["panel2"])
        btns.pack(fill="x", pady=(8, 0))
        self.about_discord = tk.Label(btns, text="  💬  Join the Discord  ", bg=DISCORD, fg="#ffffff", cursor="hand2",
                                      font=("Segoe UI", 12, "bold"), padx=8, pady=8)
        self.about_discord.pack(side="left")
        self.about_discord.bind("<Button-1>", lambda e: open_link(DISCORD_URL))
        self.about_discord.bind("<Enter>", lambda e: self.about_discord.config(bg=DISCORD_HOVER))
        self.about_discord.bind("<Leave>", lambda e: self.about_discord.config(bg=DISCORD))
        ttk.Button(btns, text="GitHub page", command=lambda: open_link(GITHUB_URL), style="Quiet.TButton").pack(side="left", padx=(8, 0))
        rs = ttk.Button(btns, text="Run setup again", command=self.features_picker)   # 3.0.6 (owner: the first-start
        rs.pack(side="left", padx=(8, 0))                                               # setup, not a quick start)
        Tooltip(rs, "Setup: your features, the Overlay and its helpers - one question a screen.")
        tk.Label(wrap, text="The Discord is the place for questions, ideas and bug reports. Code, releases and the "
                            "roadmap are on GitHub.", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w",
                 justify="left", wraplength=620).pack(fill="x", pady=(0, 8))

        box = tk.Frame(wrap, bg=P2, padx=16, pady=8, highlightthickness=1, highlightbackground=C["line"])
        box.pack(fill="x", pady=(0, 8))
        tk.Label(box, text=f"What's new in {pretty_version()}", bg=P2, fg=C["accent"], font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x")
        notes = plain_lines(dict(notes_between(None, APP_VERSION)).get(APP_VERSION) or ["(nothing listed)"])
        for line in notes:
            tk.Label(box, text="•  " + line, bg=P2, fg=C["text"], anchor="w", justify="left", wraplength=600,
                     font=("Segoe UI", 9)).pack(fill="x", pady=(4, 0))
        # (3.0.6: the "Every version's notes" line showed only this version's - removed)

        box = tk.Frame(wrap, bg=P2, padx=16, pady=8, highlightthickness=1, highlightbackground=C["line"])
        box.pack(fill="x", pady=(0, 8))
        tk.Label(box, text="About this app", bg=P2, fg=C["accent"], font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x")
        for line in (
                "Written with AI (Claude), and open about it. Anyone may use it, change it and share it under the "
                "AGPL-3.0 license - and anything made from it stays open source too.",
                "It reads the game's log file (Client.txt), and your clipboard or screen only once per key press - "
                "a copy key in the game, or your Read Key (Ctrl+Shift+R as the app comes, or a key you pick that the game doesn't use). "
                "Never on a timer or a click; each read shows for a second. Never the game's memory, and it "
                "respects the trade site's limits. One key press = one action.",
                "Prices come from the official trade site and poe.ninja.",
                "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."):
            tk.Label(box, text=line, bg=P2, fg=C["text"], anchor="w", justify="left", wraplength=600,
                     font=("Segoe UI", 9)).pack(fill="x", pady=(4, 0))
        # 2.98.3 (feedback): credit where it's due - each with a link to its developers' GitHub page
        box = tk.Frame(wrap, bg=P2, padx=16, pady=8, highlightthickness=1, highlightbackground=C["line"])
        box.pack(fill="x", pady=(0, 8))
        tk.Label(box, text="Credits - thank you!", bg=P2, fg=C["accent"], font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x")
        from .remnant import CREDIT_NAME, CREDIT_URL
        for name, what, url in CREDITS + ((CREDIT_NAME, "the idea for the Expedition Remnant Price Checker. None of "
                                                        "its code is used (it isn't open source).", CREDIT_URL),):
            row = tk.Frame(box, bg=P2)
            row.pack(fill="x", pady=(8, 0))
            ln = tk.Label(row, text=name + " ›", bg=P2, fg=C["blue"], anchor="w", font=("Segoe UI", 9, "bold"),
                          cursor="hand2")
            ln.pack(anchor="w")
            ln.bind("<Button-1>", lambda e, u=url: open_link(u))
            tk.Label(row, text=what, bg=P2, fg=C["text"], anchor="w", justify="left", wraplength=600,
                     font=("Segoe UI", 9)).pack(fill="x")
