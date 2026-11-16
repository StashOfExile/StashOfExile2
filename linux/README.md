# StashOfExile2 on Linux (preview)

> **GGG ToS safety check - read first.** One key press = one action, only when you press it · nothing acts in the game by itself (helpers only read and show) · never touch the game's memory, code or traffic · the mouse is never moved or clicked for you · it reads Client.txt, the trade site (within its limits) and poe.ninja, and your clipboard or screen only once per key press (the Read Key, a copy key). The same rules hold on Linux - see [TOS.md](../TOS.md).

The official app is Windows. The Linux build is a preview. **Tested setup: Arch + Hyprland** (Wayland, the game through Steam / Proton as an XWayland window) - a player builds every release there with `build_linux.sh` and plays with it daily. X11 desktops and other Wayland compositors work too, with the limits below.

## Arch + Hyprland (tested)

1. Packages:
   ```
   sudo pacman -S tesseract tesseract-data-eng grim socat xdotool ttf-liberation
   ```
   tesseract: OCR for the helpers that read text · grim: the Read Key's screen picture · socat: the key binds tell the app · xdotool: the price check key's copy and chat commands (the game hears XTest keys; `wtype` doesn't reach it) · ttf-liberation: fonts for the app's text.
2. Get the app: the newest **linux-preview** pre-release on [Releases](https://github.com/StashOfExile/StashOfExile2/releases) (`sha256sum -c SHA256SUMS`, then `tar xzf StashOfExile2-*-linux.tar.gz`), or build it: `./build_linux.sh` (makes `dist/StashOfExile2`).
3. Window rules: add `hyprland.lua` (Lua configs) or `hyprland.conf` (classic) from this folder to your config. The app's class is `Stashofexile2`.
4. Run it: `./StashOfExile2`. Then `./StashOfExile2 --check-linux` (or Settings › Advanced › Linux check): the first line should read `Hyprland: IPC ok · N of N pass-through binds in place · socat`.

**Keys:** for every key in Settings › Keybinds (Read Key Ctrl+Shift+R, the price check key, Ctrl+C / Ctrl+Alt+C, chat keys ...) the app adds a pass-through Hyprland bind while it runs - `hyprctl eval 'hl.bind(...)'`, else `hyprctl keyword bindnd`, described `SoE2 <key>`. Your config file is never edited; only missing binds are added (checked every 20 s over Hyprland's IPC, so a config reload is fine). Mouse-button keys can't be Hyprland binds. Pick keys the game doesn't use.

**Fonts:** the app asks for Windows fonts (Segoe UI, Tahoma, Consolas). Its own `fonts.conf` maps them to Liberation / Noto / DejaVu for this app only (`FONTCONFIG_FILE`; yours wins if set, `SOE2_SYSTEM_FONTS=1` turns it off).

**Data:** `~/.stashofexile2`. Updates: the Linux build checks the linux-preview releases only and saves the new `.tar.gz` next to the app.

## Known issues (Hyprland)

- **Run the game windowed** (the compositor can still make it fill the screen). In fullscreen the game holds the pointer: a click on the app's window also clicks the game.
- **Copying from a Wayland app:** XWayland hands the Wayland clipboard to X11 apps when an X11 window gets focus, so the app sees it once you click it. Copies made in the game are seen at once.
- The app's hotkeys reach the game too (pass-through) - Windows can keep them; Linux can't.
- Overlays don't let clicks through; the see-through styles show with a box.
- Tags can't be left out of screenshots and streams (Windows-only).
- Tesseract reads small game text a little less reliably than Windows' reader.

## Other desktops (secondary)

| | X11 (GNOME on Xorg, Plasma X11, Xfce ...) | Other Wayland (GNOME, KDE, sway) |
|---|---|---|
| Keys | heard by the app (X11 RECORD) | heard while the game (XWayland) is in front; else bind a desktop shortcut to `StashOfExile2 --key "Ctrl+Shift+R"` |
| Game in front | the window manager's hints | the same, through XWayland |
| Screen picture | built in | `grim` (sway), `spectacle` (KDE), `gnome-screenshot` (GNOME, may ask once); `SOE2_CAPTURE=...` picks one |
| Clipboard / keys out | `xclip`, `xdotool` | `xclip` (XWayland), `xdotool` (XWayland) or `ydotool` |

Debian / Ubuntu: `sudo apt install tesseract-ocr xclip xdotool socat` · Fedora: `sudo dnf install tesseract tesseract-langpack-eng xclip xdotool socat`. Tray icon: only with a system tray (GNOME needs the AppIndicator extension).

## Client.txt (Steam / Proton)

Found by itself in every Steam library (`libraryfolders.vdf`): `~/.local/share/Steam/...`, `~/.steam/steam/...`, Flatpak `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/...`, then `steamapps/common/Path of Exile 2/logs/Client.txt`; also Wine / Lutris prefixes. Elsewhere: Settings › Advanced › Game log › Change….

## Report a bug

A GitHub [issue](https://github.com/StashOfExile/StashOfExile2/issues) titled `[Linux] ...` with the output of `./StashOfExile2 --check-linux`, your distro, compositor and what happened. Settings › Advanced › Problems › Report a bug can add the app's log (code locations only).

## Run from source

```
sudo pacman -S python tk tesseract tesseract-data-eng grim socat xdotool ttf-liberation
python -m venv .venv && . .venv/bin/activate
pip install -r linux/requirements-linux.txt
python stashofexile2.py
```
OCR check without the game: `python -c "from soe2 import remnant; print(remnant.selftest())"` prints `Orb of Alchemy x3`.
