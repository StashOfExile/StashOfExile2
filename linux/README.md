# StashOfExile2 on Linux (preview)

> **GGG ToS safety check - read first.** One key press = one action, only when you press it · nothing acts in the game by itself (helpers only read and show) · never touch the game's memory, code or traffic · the mouse is never moved or clicked for you · it reads Client.txt, the trade site (within its limits) and poe.ninja, and your clipboard or screen only once per key press (the Read Key, a copy key). The same rules hold on Linux - see [TOS.md](../TOS.md).

The official app is Windows. This is a **preview** Linux build for players who run Path of Exile 2 through Steam / Proton. Please test it and report what doesn't work.

## Install and run

1. Download `StashOfExile2-<version>-linux.tar.gz` and `SHA256SUMS` from the newest **linux-preview** pre-release on [Releases](https://github.com/StashOfExile/StashOfExile2/releases).
2. Check and unpack it:
   ```
   sha256sum -c SHA256SUMS
   tar xzf StashOfExile2-*-linux.tar.gz
   cd StashOfExile2-*-linux
   chmod +x StashOfExile2
   ./StashOfExile2
   ```
3. See what works on your desktop: `./StashOfExile2 --check-linux` (or Settings › Advanced › Linux check). Each line says how to fix it.

Your data lives in `~/.stashofexile2`. Updates: the app checks the Linux preview releases only and saves the new `.tar.gz` next to the app - unpack it over the old folder.

## Packages

| For | Debian / Ubuntu / Mint | Fedora | Arch / SteamOS |
|---|---|---|---|
| OCR (helpers that read text) | `sudo apt install tesseract-ocr` | `sudo dnf install tesseract tesseract-langpack-eng` | `sudo pacman -S tesseract tesseract-data-eng` |
| Clipboard, X11 | `sudo apt install xclip` | `sudo dnf install xclip` | `sudo pacman -S xclip` |
| Clipboard, Wayland | `sudo apt install wl-clipboard` | `sudo dnf install wl-clipboard` | `sudo pacman -S wl-clipboard` |
| Key sending (chat commands, the price check key's copy) | `sudo apt install xdotool` | `sudo dnf install xdotool` | `sudo pacman -S xdotool` |
| Screen picture, Wayland only | `grim` (Hyprland, sway) · `spectacle` (KDE) · `gnome-screenshot` (GNOME) | same | same |

Without Tesseract the helpers that read text (Expedition, Desecration, Temple, the text parts of Ritual and Trial of the Sekhemas) say "needs OCR" on their row; everything else works (the Sekhemas map check, Ritual's counter, Client.txt helpers, price checks).

## X11 or Wayland

**X11 works best** - at the login screen pick "GNOME on Xorg", "Plasma (X11)" or similar. There the app hears your keys, knows when the game is in front, takes the Read Key's picture and presses keys for chat commands with nothing extra.

**Wayland:** the game runs as an XWayland window under Proton, so most things still work while the game is in front:
- Keys: heard while the game has the keyboard. If a key does nothing, bind it in your desktop's keyboard shortcuts to
  `/path/to/StashOfExile2 --key "Ctrl+Shift+R"` (one shortcut per key; most desktops then keep that key from the game - fine for the Read Key). Hyprland passes it through: `bindn = CTRL SHIFT, R, exec, /path/to/StashOfExile2 --key "Ctrl+Shift+R"`.
- Screen picture: install the tool for your desktop (table above). GNOME may ask once for permission. Pick one by hand with `SOE2_CAPTURE=grim|spectacle|gnome-screenshot|mss`.
- Hyprland: window rules in `hyprland.conf` / `hyprland.lua` here.

## Client.txt (Steam / Proton)

Found by itself in every Steam library (`libraryfolders.vdf`), for example:
- `~/.local/share/Steam/steamapps/common/Path of Exile 2/logs/Client.txt`
- `~/.steam/steam/steamapps/common/Path of Exile 2/logs/Client.txt`
- Flatpak Steam: `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Path of Exile 2/logs/Client.txt`
- the standalone client in a Wine / Lutris prefix: `drive_c/Program Files (x86)/Grinding Gear Games/Path of Exile 2/logs/Client.txt`

Somewhere else: Settings › Advanced › Game log › Change….

## Known limits on Linux

- The app's own hotkeys aren't kept from the game (Linux key watchers only listen), so the game gets them too.
- Keys pressed by other programs (xdotool, macro tools) look like yours on X11; the app ignores only its own.
- Wayland: keys are only heard while an XWayland window (the game) is in front, unless you bind them (above).
- Wayland: the screen picture needs grim / spectacle / gnome-screenshot; with none it goes through XWayland and may come out black.
- Overlays: clicks don't go through them, and the see-through overlay styles show with a box. See-through needs a compositor.
- Tray icon: needs a system tray (KDE, Xfce, Cinnamon, MATE; GNOME needs the AppIndicator extension). Without one the window just minimizes.
- Sharp text at high DPI: Tk follows `Xft.dpi` (e.g. `echo "Xft.dpi: 144" | xrdb -merge`).
- Fonts: Segoe UI isn't on Linux; fontconfig picks your sans font. Odd text? Install `fonts-noto` / `noto-fonts`.
- Tesseract reads small game text a little less reliably than Windows' reader.
- Multi-monitor setups with scaling under Wayland may put the picture's area off.
- The tags can't be left out of screenshots and streams (a Windows-only window setting).

## Report a bug

Open an issue on [GitHub](https://github.com/StashOfExile/StashOfExile2/issues) titled `[Linux] ...` with:
- the output of `./StashOfExile2 --check-linux`
- your distro, desktop and session (X11 / Wayland)
- what you did and what happened; Settings › Advanced › Problems › Report a bug can add the app's log (code locations only).

## Run from source

```
sudo apt install python3-tk python3-venv tesseract-ocr xclip xdotool
python3 -m venv .venv && . .venv/bin/activate
pip install -r linux/requirements-linux.txt
python stashofexile2.py
```

Build it yourself: `./build_linux.sh` (PyInstaller; smoke-runs the binary under Xvfb when there's no display).
