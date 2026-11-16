# GGG Terms of Service (ToS) safety check

**Read this first, before any change, plan or release.** Every guide in this project (README, ROADMAP, the handovers,
`strats/`, `board/`, `linux/`) starts with a short copy of this check and points here.

Grinding Gear Games doesn't approve or certify third-party tools. Their support answer is that they "cannot comment on
the legality of third-party tools". So StashOfExile2 stays well inside the rules GGG staff *have* stated, as
collected in the forum guide [What a macro is allowed to do in Path of Exile](https://www.pathofexile.com/forum/view-thread/2077975):
one action per key press, nothing automated, nothing that moves the cursor or clicks for you, whatever tool sends it.
GGG's [Terms of Use](https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy) (checked Nov 2026), clause 7,
forbid without written approval: modifying the game client or its data, including through third-party tools (7.2);
automated software or bots (7.3); connecting to their servers with anything but the game client (7.5); data
extraction tools on their website (7.6); reverse engineering (7.9). Clause 22: never try to get around the website
API's limits.

GGG's [API policies and third-party requirements](https://www.pathofexile.com/developer/docs#policy) (checked
15 Nov 2026) add, for tools that use the screen, the clipboard or the game's logs:

> "You may only read this information as long as the user is aware of what you are doing with that data."
>
> "Reading from the screen or clipboard may only be performed once per manual key press."

and for macros: invoked manually (no timers, file-change or screen-reading triggers), one set function, one action
that interacts with the game (one chat message or command counts as one). Reading Client.txt has no per-press limit.
Never read game memory, never interact with the game's files. Their [guidelines](https://www.pathofexile.com/developer/docs/index#guidelines)
also ask for this notice, word for word, and a User-Agent that says how to reach us:

> This product isn't affiliated with or endorsed by Grinding Gear Games in any way.

## The check (every feature must pass all of these)

1. **One key press = one action, and only when you press it.** No macro does two things, rotates, repeats, or fires on
   a timer or a game event (life, mana, flasks, logout ...).
2. **Nothing acts in the game by itself.** Helpers (Breach, Ritual and its Favours prices, Expedition Remnant
   Price Checker, Top Up Reminders ...) only *read and show*: a banner, a sound, a price tag. They never press, click,
   type or send anything.
2b. **One screen or clipboard read per key press - nothing reads by itself.** The owner takes GGG's rule at its
   strictest ("we MUST be in compliance with this across everything"): a read happens only on a key pressed FOR it -
   never a timer, a thread, a loop, a click, a file change, the app's window getting the focus or the app starting.
   The screen is read once when you press your **Look key** in the game: a key only for the read (Settings ›
   Keybinds, or Setup's helpers step). It is Ctrl+Shift+R as the app comes; if you clear it, nothing reads the screen. It
   can't be Tab (the game's map key, the old default - cleared once, with a notice), Enter, Space, Esc, Ctrl+C,
   another of the app's keys or a mouse button; in the game the app only listens - the key is never blocked or swallowed, the game still gets it - so a key the game doesn't use. One
   picture of the game window, which every helper that applies where you are cuts its part from, then drops. A held
   key reads once (its repeats aren't presses). The clipboard's text is read once for each copy key you press in the
   game - 0.2 s after the press (clipread.READ_DELAY), one read, no retry ("The copy didn't land - press the key
   again.") - once per chat command key (your text, to put it back), and when you press Ctrl+V in one of the app's
   boxes. Never a copy made in another program, never on a click, and nothing watches the clipboard (the 150 ms
   copy-counter timer is gone). Each read shows the **read mark** for a second (over the game and on the status
   line: "👁 Screen read once: Ritual, Temple") and writes a line in the app's log. Anything that needs watching
   between presses comes from Client.txt, or doesn't exist (the Favours tribute reminder, the Delirium helper
   and Fast Beacon Read are gone for this reason). In maps nothing looks at the screen on entering one or to tell
   that it's done: Map Content's icons are never read - the helpers there follow Client.txt (area changes, rituals
   started / disrupted) and read only what you press the Look key for.
3. **Never touch the game client.** No reading or writing its memory, no injecting code, no hooking its graphics, no
   reading or changing its network traffic.
4. **The app's only input to the game:** after *your* key press, one game action - the game's own item copy
   (Ctrl+Alt+C), or one chat command (pasted, one Enter). The mouse is never moved or clicked for you.
5. **What the app reads, and when** (the user is told - each helper's one line names the Look key, the read mark
   shows each read for a second, and the app's log writes each one: "F9 pressed: read the screen once for Ritual,
   Temple" / "Ctrl+C pressed: read the clipboard once for Price Checks"):

   | What | Trigger (and only this) | Who uses it |
   |---|---|---|
   | Your screen (one picture of the game window, kept in memory) | one per press of your Look key in the game - a key only for this, Ctrl+Shift+R as the app comes; held = one; no Look key (cleared) = never | Ritual counter and tribute (never Map Content); Temple (the Temple Console's crystal count and board, Vaal Lens); Ritual Identifier; Expedition reward book; Favours prices; Island rumors; Desecration Helper; Top Up Reminders and Map profit; Trial of the Sekhemas (is the trial map open, and a hovered affliction or boon's name); Scan stash (once Start reading armed it) |
   | Your clipboard's text | one per copy key pressed in the game, 0.2 s after it, no retry: Ctrl+C / Ctrl+Alt+C (only when something takes it: Bulk Pricing, the Strat Tracker's boxes, Price Checks or Top Up on Ctrl+C, Wealth's Count by hand), the price check key, the Top Up key | Price Checks, Bulk Pricing, Wealth's Count by hand, Top Up teaching, Map profit, the Strat Tracker, Mod Book › Manual feed |
   | Your clipboard's text | one per chat command key press (before the command is pasted - to put your text back; a mouse-button chat key reads nothing and doesn't put it back) | chat commands |
   | Your clipboard's text or picture | one per Ctrl+V / Shift+Insert in one of the app's boxes (Tk's own paste in text boxes; Favorites' list, the Strat Tracker's item and Atlas steps, Craft Helper's and Regex's check boxes) | what you paste |
   | Client.txt (the game's log) | all the time, new lines only | area changes, Breach warnings, rituals started / disrupted, whispers, deaths, levels |

   **Everything else that could look like reading the screen or clipboard** (audited Nov 2026 - none of it is the
   screen's content or the clipboard's content):

   | What | Trigger | Why it isn't a screen / clipboard read |
   |---|---|---|
   | The mouse's position (Tk `winfo_pointerxy`, `GetCursorPos`) | the Look key press (which inventory cell / tooltip is under the mouse); the Ctrl+Alt+C copy mark; the price check / Top Up key (which cell to learn); placing a popup or menu; Esc-minimize check; Go to anything closing on an outside click | two numbers from Windows, never pixels |
   | Window rects, the window in front, window titles and class names (`GetWindowRect`, `GetForegroundWindow`, `GetWindowText`, `EnumWindows`, `GetClassName`; Hyprland's IPC on Linux) | timers (the overlay's 0.5 s tick: is the game open / in front, where is it; the game-window rect for placing cards); each key press (is the game in front) | window metadata from the OS - not screen content; titles only to find "Path of Exile 2" |
   | Monitor sizes (`MonitorFromWindow`, `GetMonitorInfo`, Tk screen size) | placing a window | geometry, not pixels |
   | DPI awareness / scaling | none in the main app (the helper processes that changed it are gone) | - |
   | Key state (`GetAsyncKeyState`), the keyboard hook (`winsys.KeyWatch`) and the mouse-button hook | the hook sees key presses (that's how a press is known); `GetAsyncKeyState` on a minimize / outside click | keys, not screen or clipboard; the mouse hook is only on while a hotkey uses a mouse button |
   | The Drawer's side flip (branch `drawer`, not in this build) | the price check key press | `GetCursorPos` + `GetWindowRect`: positions only - it must stay that way when merged |
   | Writing the clipboard (`clipread.write_text` / `clear`, Tk `clipboard_append`) | a chat command key; Copy buttons and Ctrl+C in the app; Regex keys; emptying it just before the app presses the game's copy | writing, never reading |
   | `vaallens_draw` (`GetDC(None)` + `UpdateLayeredWindow`) | drawing Vaal Lens over the game | it draws a window; it reads nothing back |
   | The read mark, toasts, cards over the game | after a read / an event | windows the app draws; left out of screen captures where Windows allows it |
   | Favours prices / Top Up keep their cut of the press's picture in memory up to 120 s | your price check key / Top Up key on a reward or item in that time teaches its icon (saved as a small icon) | no new read - the cut of the last Look key press, never saved whole |
   | Atlas screenshots (Strat Tracker) | Ctrl+V on the Atlas step (one read) or Pick an image file… | your own picture, by your key press or your file pick |
   | Report a bug; Error reports (opt-in, Settings › Privacy & community) | your click on Send; Error reports hourly once you opt in | text only: the app's log and what you type - no screenshot, no clipboard |
   | Scan stash | Start reading (a click) only arms; each Look key press reads one tab | the click reads nothing |

   Plus public websites: the official trade site's search API, only for
   searches you started (a copied item, a sync you pressed), always inside the limits it sends back (clause 22), and
   always saying who is asking (User-Agent "StashOfExile2/<version> (contact: stashofexile@gmail.com)", config.APP_UA) -
   never automated buying, whispers or listing, never scraping its pages - and poe.ninja.
   The app never connects to the game's servers (7.5) and never changes the game client or its files (7.2).
6. **Overlays are just windows on top.** Click-through where they sit over the game, they never change what the game
   draws or does, and they're left out of screen captures where Windows allows it (the bar, while a Look key read
   needs the game's counters under it). A card or panel that only shows something (the alert card, the Trial of the
   Sekhemas legend, Island rumors, the Desecration Helper's notice) closes on a click on it - that click is the app's
   own and never reaches the game; clicks beside it go to the game.
   Music Controls (2.134.0): a click on the app's own window hands Windows one app command (play / pause, next,
   previous - what a keyboard's media key does). No key is pressed or sent; the game never gets it.
7. **When in doubt, leave it out** - or make it a manual, one-press action, and ask before shipping it.

## How it's enforced

- `tools/check_tos.py` runs on every pull request (`.github/workflows/checks.yml`) and in the test suite. It fails on:
  game-memory / process APIs (ReadProcessMemory, WriteProcessMemory, OpenProcess, VirtualAllocEx, CreateRemoteThread
  ...), mouse movement or clicks (SetCursorPos, mouse_event, mouse SendInput), packet tools (pydivert, scapy, pcap),
  input-automation libraries (pyautogui, pynput, keyboard, AutoHotkey), SendInput anywhere but `soe2/overlay.py`, and
  a screen watcher that can send keys. The base rule, for the whole program (GGG policy, Nov 2026):
  - screen capture (mss, ImageGrab, BitBlt, PrintWindow, grim, d3dshot, dxcam, win32ui) anywhere but
    `soe2/screenread.py`;
  - any clipboard API (OpenClipboard, GetClipboardData, SetClipboardData, EmptyClipboard, clipboard_get,
    grabclipboard, win32clipboard, pyperclip, GetClipboardSequenceNumber ...) anywhere but `soe2/clipread.py`, and
    anything that watches the clipboard (GetClipboardSequenceNumber, AddClipboardFormatListener, SetClipboardViewer,
    WM_CLIPBOARDUPDATE) anywhere at all;
  - in `soe2/screenread.py` and `soe2/clipread.py`: a timer (`.after`, `after_idle`, `threading.Timer`), a thread, a
    while loop, or a loop that reads;
  - `screenread.grant` / `clipread.grant` called from anything but the key watcher (look_on_key, clip_on_key,
    pc_hotkey, topup_hotkey, Overlay.on_key - each reached from App.on_any_key, the keyboard hook's listener);
  - `screenread.grant` called from anything but `look_on_key`: the Look key is the one key that opens a screen read
    (no second key, no per-helper key, no click - Scan stash included); at run time `screenread.ONLY_KEY` refuses a
    grant for any other key;
  - the key watcher's listener (`App.on_any_key`) using the answer of `look_on_key` / `clip_on_key`, or returning True
    for a key that isn't one of the app's own hotkeys: the Look key and copy keys are passed through to the game;
  - a function that reads the clipboard and puts itself back on a timer (a watcher);
  - a key sender (SendInput, send_copy, type_chat) reachable from a timer (`.after`, `after_idle`, `threading.Timer`);
  - the notice above missing from README.md or Settings › About, or a User-Agent without "(contact: ".
- `tools/check_screenread.py` proves it at run time: no reads without a key press (every key, Look key unset: no
  picture, no clipboard read); no reads on clicks (mouse buttons never grant, Scan stash's Start reading only arms,
  Ctrl+V paths read nothing without a key event, no Paste button or menu item); one read per press (one picture
  shared by every helper, one clipboard read per copy key press READ_DELAY after it with no retry, a held key reads
  nothing more, a chat key reads once); no clipboard timer exists (no watcher in the app, nothing re-reads on a
  timer); Tab / a mouse button / another app key can't be the Look key; Ctrl+Shift+R is the default and clashes with no
  app key; the key watcher never swallows the Look key; no other key opens a read; the migrations give Tab / unset the default; each read writes
  its log line and tells the read mark; and check_tos catches each of these if it came back.
- Every helper that reads the screen has a `*_look_job` (look_page.py) and its module notes say what it reads and
  that it sends nothing. A new one never gets a watcher. A new paste is a key binding that calls
  `clipread.app_paste(widget, event)` - never a button.
