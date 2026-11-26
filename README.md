# StashOfExile2

*One tool to rule them all.*

> **GGG ToS safety check.** One key press is one action. Nothing plays the game for you. The app never touches the game's memory, code or traffic. It reads Client.txt, the trade site and poe.ninja, and reads your clipboard or screen only once per key press. Every change must pass [TOS.md](TOS.md).

StashOfExile2 is a free, open-source Windows and Linux companion for **Path of Exile 2**: price checks, bulk pricing, exchange rates, helpers over the game, league planning and a searchable copy of the game's data. Claude, an AI by Anthropic, writes the code; a human player directs and tests it.

![Full window: the Dashboard](docs/screenshots/full-window.png)

| Game Search | Mod Lab |
|---|---|
| ![Game Search: every unique, mod and keyword from the game's data](docs/screenshots/game-search.png) | ![Mod Lab: rate mods by base, like Abyss Tablet or Ruby](docs/screenshots/mod-lab.png) |

| The Drawer, for one monitor | The Overlay over the game |
|---|---|
| ![The Drawer over the game's side, on the Dashboard](docs/screenshots/drawer.png) | ![The overlay in town: the bar, Notes, a price check card and Music Controls](docs/screenshots/overlay.png) |

*Screenshots use sample data and made-up listings over a real game screen.*

## New in 3.3

- **Calendar** - leagues, Twitch Drops, events and races from Steam news, plus your own reminders. The next one shows on the Dashboard and over the game.
- **Patch Notes** on the Dashboard, from GGG's forum and Steam.
- **Game Search** - every unique's lines are searchable, with their older versions, every league has its game version, and **Changed in 1.0** lists what a patch changed.
- **Mod Lab** - every mod says its kind: Prefix, Suffix, Implicit, Corrupted and more. Groups are the bases, like Abyss Tablet, Ruby or Vase Relic.
- **Report a Problem** on Codex pages: flag a wrong line for review.
- **Game data updates itself.** After a patch, the app downloads the new data files once a day. No new release needed.
- **Keybinds** use short names, and **Ctrl+Shift+N** opens poe.ninja.

A **NEW** chip marks what's new on its row and on its page's icon until you open or use it.

## Third-party policy

GGG's rule for tools: *"Reading from the screen or clipboard may only be performed once per manual key press."* The app follows it at its strictest: only a key you press starts a read. A timer, a click, a file change or the app starting never does.

- **One read per key press.** Holding a key reads once. Each read shows the read mark (👁) for a second and writes a line in the app's log.
- **Your screen: only on the Read Key.** **Ctrl+Shift+R** as the app comes (Settings › Keybinds). One picture of the game window; every helper that applies where you are reads its part, then it's dropped. Clear the key and nothing reads the screen.
- **Your clipboard: only on a copy key.** The price check key (Ctrl+D), Ctrl+Alt+C for Bulk Pricing: one read, 0.2 s after the press. A chat command key reads it once, to put your text back. Ctrl+V in one of the app's boxes. Nothing watches the clipboard.
- **The game's log (Client.txt)** is followed all the time: where you are, Breach warnings, whispers.
- **Never** the game's memory, files or network traffic. The game client is never changed.
- **Never a macro.** After your key press the app does at most one thing in the game: the game's own item copy, or one chat command. The mouse is never moved or clicked for you.
- The trade site is searched only for what you started, well inside its limits, with a User-Agent that says who is asking. Rates come from poe.ninja.
- **No game art ships with the app.** Item pictures load from poe.ninja and the trade site when needed and stay only on your PC.
- The full list of every read and its trigger: [TOS.md](TOS.md).
- **Older versions are gone.** Every release before 3.0.0 was removed from GitHub, because those versions read the screen by themselves. Don't use them with the game. Details: [docs/REMOVED_VERSIONS.md](docs/REMOVED_VERSIONS.md).

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.

## What it does

**Trade**
- **Price Checks** - hover an item, press **Ctrl+D**: price, how sure, and how it was worked out. Too few listings for a base? **Broaden Search** widens it, one step a click.
- **Bulk Pricing** - **Ctrl+Alt+C** on many items (tablets, waystones, jewels): priced as a list.
- **Favorites**, **Exchange Rates** - poe.ninja rates, a converter, and Compare a currency. Pick which ones show over the game.

**Mods**
- **Mod Lab** - rate mods One at a Time or in a Table. Your ratings tune your price checks. A mod that rolls in tiers can have a letter for its top, middle and low rolls.
- **Market Insights** - your most valuable items and the priciest listings seen.
- **Craft Helper** (BETA) - each mod of a tablet or jewel rated S to F, and a next step.

**Stash**
- **Wealth** - what your stash is worth: Scan stash reads one tab per Read Key press.
- **Regex** - stash search strings for tablets, waystones, relics, jewels and gear.

**League**
- **League Plan**, **Map Profit** BETA, **Farming Strategies** BETA and **Leaderboards**, which you opt in to.
- **Calendar** and **Patch Notes** on the Dashboard.

**Codex**
- **Game Search** - every skill, item, unique, mod and keyword, from the game's own data, on your PC.
- **Mod Lab** - every item mod by base, with its kind.
- **Map Library** - every map ranked from S to Avoid.

**Overlay** (over the game: Bar, Panel or Split layout, in any style)
- **Session timer**, Notes, Calc, Regex and Rates menus, the **Price check overlay**.
- Helpers - press your **Read Key** where one applies: **Ritual** (Favours prices, and Filter in the Ritual window), **Expedition** (remnant rewards, Island rumors), **Desecration Helper**, **Temple Helper** (BETA, Vaal Lens), **Trial of the Sekhemas** (BETA), **Back from a map** (Map profit, Top Up Reminders).
- From the game's log: **Breach**, **Campaign Helper** and the **Campaign Bar**, **Trade whispers**, **Break reminders**. Plus **Music Controls**.

## Window: Drawer or Full window

- **Drawer** - suggested for one monitor. The app over the game's side; **Ctrl+Shift+Space** (the Drawer key) shows it and puts it away.
- **Full window** - suggested for two or more monitors. A normal window, where you left it.
- Switch any time: Settings › General › Window.

## Install and update

Download `Setup-StashOfExile2-<version>.exe` from the [latest release](https://github.com/StashOfExile/StashOfExile2/releases/latest). It asks first:

- **Full Install** - puts it in your Start menu and Windows search, and in Settings › Apps to uninstall. Your settings live in `%APPDATA%\StashOfExile2`
- **Portable** - one folder you pick. Nothing else on your PC changes. A new player's settings live in that folder too; if you already use the app, your settings stay where they are.

Both install for you only, so there's no admin prompt. Both can update themselves; this is off until you turn it on. Game data updates on its own once a day.

The project moved to [github.com/StashOfExile/StashOfExile2](https://github.com/StashOfExile/StashOfExile2). If your 2.x app doesn't offer 3.0 by itself, download it once from Releases - it updates itself from then on, and your settings are kept.

Each release lists the SHA-256 of every download and a VirusTotal scan of the exe: open the [latest release](https://github.com/StashOfExile/StashOfExile2/releases/latest), then the VirusTotal link under **Check your download**.

### Windows SmartScreen and VirusTotal

**Windows SmartScreen** may say "Windows protected your PC" the first time you run a new version, because the app isn't signed with a paid code-signing certificate and each new version starts with no download history. To run it, press **More info**, then **Run anyway**.

**VirusTotal** usually shows one or two of about 70 engines flagging the exe, with generic names like `W32.Malware`. These are false positives:

- **PyInstaller.** The app is written in Python and packed into one exe with PyInstaller. Some malware uses the same packer, so a few engines flag anything packed with it. VirusTotal's own PyInstaller rule says this alone doesn't mean a file is malicious.
- **The tags** `overlay`, `obfuscated`, `detect-debug-environment` and `calls-wmi` describe how PyInstaller and Python work: the code is stored as a compressed archive at the end of the exe, and Python asks Windows which version it's running on.
- **`checks-user-input`** is the Read Key and the other hotkeys you set. The app waits for your key press, then reads.
- **Cloudflare `workers.dev`** is where Leaderboards, Farming Strategies posts and Community data sharing live. It's an info-level note, not a warning.

To check it yourself:

- Compare the exe's SHA-256 with the one on the release page.
- Read the code. Everything the exe runs is in this repo.
- Build it yourself. Each release has a build kit zip with the exact code for that version; run `build_exe.bat` in it. Or run it from source, below.
- Upload the exe to VirusTotal yourself, or scan it with your own antivirus.

From source (Python 3.12): `py -m pip install requests pystray pillow mss numpy opencv-python-headless` then `py stashofexile2.py`.

### Linux

Every release has a Linux download on the same page: `StashOfExile2-<version>-linux.tar.gz` (and its checksum, `SHA256SUMS-linux.txt`). Same code and same version as the Windows app, built at the same time.

- Tested on Arch + Hyprland. X11 desktops and other Wayland compositors should work too, with limits.
- `tar xzf StashOfExile2-*-linux.tar.gz`, then `./StashOfExile2 --check-linux`: it lists what works on your setup, each with its fix.
- The same third-party rules hold: the screen and clipboard are read only once per key press.
- It updates itself from the same releases. Packages, window rules and known issues: [linux/README.md](linux/README.md).

## Privacy

- Everything is opt-in. Nothing is shared anywhere else or sold. Shared data lives on the app's community server on Cloudflare, which never keeps your internet address. Bug reports and feature ideas you send become public GitHub issues.
- **Count me as a user** is off until you turn it on, on the Dashboard or in Settings › Privacy & community. It sends a random id made on your PC every 10 minutes, so we know how many people use the app. It never sends your account, name or PC details.
- Nothing else leaves your PC unless you turn on Community data sharing, and then only anonymous data for price checks, map ranks and the campaign guide. Never your account or character names, personal information or anything about your currency or wealth. Leaderboard times show under the community name you pick.
- Error reports are off until you turn them on. They send where in the code an error happened and its type, never messages, names, items or files.
- Logs, `app_log.txt` and `crash_report.txt`, stay on your PC and leave out your names and folders. You see every word before a bug report is sent. A bug report can add your screen setup: screen size, scaling, HDR and the game window's mode, from Windows, never from the game.
- Settings › Privacy & community › Leave and delete my data removes everything of yours from the community board.

## Community

Questions and bug reports: [Discord](https://discord.gg/8dwn9kaGNr). Plans: [ROADMAP.md](ROADMAP.md). Bugs and ideas also go in through **Report a bug** and **Suggest a Feature** in the app.

## Credits

- **[RePoE](https://github.com/repoe-fork/repoe-fork)** (repoe-fork): the game data behind the mod lists, Regex, Game Search and tiers, exported from Path of Exile 2's own files.
- **[poe.ninja](https://github.com/rasmuskl)** (rasmuskl): the economy data behind Exchange Rates, the rates window over the game, the Remnant prices and currency values.
- **[Exiled Exchange 2](https://github.com/Kvan7/Exiled-Exchange-2)** (Kvan7, MIT): general ideas, and the base types, mod wordings, trade-site stat ids and pseudo-total rules in `gamedata.json`, from its data files under its license; and the ideas (2.113.0) of counting each seller once and keeping a mod's Min within its tier, written our own way.
- **[Sidekick](https://github.com/Sidekick-Poe/Sidekick)**: general ideas. None of its code is used.
- **[hypr-exiled](https://github.com/gfsd3v/hypr-exiled)** (gfsd3v): the idea for the Trade Whisper Watcher, built from scratch here; none of its code is used.
- **[Path of Building PoE2](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2)** (MIT): the anoint recipes, and every unique's lines and older versions in `uniquedata.json` and `snapshots/`.
- **[poe2pricer](https://github.com/saxe78/poe2pricer)** (saxe78): the idea for Favours prices (finding the Ritual window by a piece of its own art, its rewards by their pictures). Written from scratch here; none of its code is used.
- **gruvbox** by Pavel Pertsev (morhetz), MIT: the colors of the Gruvbox Dark and Gruvbox Light themes ([github](https://github.com/morhetz/gruvbox)).
- **Catppuccin** by the Catppuccin team, MIT: the colors of the Catppuccin Mocha and Catppuccin Latte themes ([github](https://github.com/catppuccin/catppuccin)).
- **Nord** by Sven Greb (Arctic Ice Studio), MIT: the colors of the Nord theme ([github](https://github.com/nordtheme/nord)).
- **Dracula** by Zeno Rocha and the Dracula Theme team, MIT: the colors of the Dracula theme ([github](https://github.com/dracula/dracula-theme)).
- **Tokyo Night** by Enkia, MIT: the colors of the Tokyo Night theme ([github](https://github.com/enkia/tokyo-night-vscode-theme)).
- **Rosé Pine** by the Rosé Pine team, MIT: the colors of the Rosé Pine and Rosé Pine Dawn themes ([github](https://github.com/rose-pine/rose-pine-theme)).
- **Everforest** by sainnhe, MIT: the colors of the Everforest Dark theme ([github](https://github.com/sainnhe/everforest)).
- **Kanagawa** by Tommaso Laurenzi (rebelot), MIT: the colors of the Kanagawa theme ([github](https://github.com/rebelot/kanagawa.nvim)).
- **Solarized** by Ethan Schoonover, MIT: the colors of the Solarized Dark and Solarized Light themes ([github](https://github.com/altercation/solarized)).
- **NeverSink and Ryonnen** (reddit): the game's hidden setting that applies your item filter to the Ritual window (`apply_item_filter_to_ritual`), which Filter in the Ritual window walks you through ([NeverSink's video](https://www.youtube.com/watch?v=6hiQtcQhB3k)).
- **[PoE Ancients Price Helper](https://github.com/pedro-quiterio/PoeAncientsPriceHelper)** (Pedro Quitério): the idea for the Expedition Remnant Price Checker. None of its code is used.
- **[Path of Exile 2 Wiki](https://www.poe2wiki.net/wiki/Guide:Acts_quick_guide)** (poe2wiki.net editors): the Campaign Helper's Rush (carry) route follows the order and essentials of its Guide:Acts quick guide, rewritten here from the carrier's side.
- **Fonts of the ornate overlay styles** (SIL Open Font License 1.1, licenses in `soe2/fonts`): **[Cinzel](https://github.com/NDISCOVER/Cinzel)** (Natanael Gama), **[EB Garamond](https://github.com/octaviopardo/EBGaramond12)** (Georg Duffner, Octavio Pardo), **[Cormorant](https://github.com/CatharsisFonts/Cormorant)** (Christian Thalmann) **[Marcellus and Marcellus SC](https://github.com/google/fonts/tree/main/ofl/marcellussc)** (Brian J. Bonislawsky, Astigmatic), **[Metamorphous](https://github.com/google/fonts/tree/main/ofl/metamorphous)** (Sorkin Type) and **[IM FELL English SC](https://github.com/google/fonts/tree/main/ofl/imfellenglishsc)** (Igino Marini). Cinzel, EB Garamond and Cormorant were converted to TTF from [Fontsource](https://github.com/fontsource/fontsource)'s Latin files.

## License

The code is free software under the **GNU Affero General Public License v3.0** ([LICENSE](LICENSE)): you can use it, change it and share it. Anything made from it has to stay under the same license, with its source - and that includes a changed version people use over a network (a website or an online service), not only one you hand out. Versions up to 2.129.4 were released under the GNU GPL v3.0.

Game data in `regexdata.json`, `searchdata.json`, `modlists.json`, `tierdata.json` and `snapshots/` comes from [RePoE](https://github.com/repoe-fork/repoe-fork); `gamedata.json` (base types, mod wordings, trade-site stat ids, pseudo-total rules) is built from [Exiled Exchange 2](https://github.com/Kvan7/Exiled-Exchange-2)'s data files (MIT) (anoint recipes in `anointdata.json`: [Path of Building PoE2](https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2)) and belongs to Grinding Gear Games; it isn't covered by this license. Other sources and their licenses are in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).

This product isn't affiliated with or endorsed by Grinding Gear Games in any way. Path of Exile 2 is a trademark of Grinding Gear Games.
