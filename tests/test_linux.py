"""Linux paths (linux/README.md): the OCR engine's choice and its "needs OCR" state, Client.txt under Steam / Proton,
the session and the tools, the game window over X11's hints, the key watchers (X11 RECORD, the desktop-shortcut
socket), key sending, the clipboard tools, the screen picture's tool, the Linux check and the Linux update channel.
The X11 parts run for real when there's an X server (Xvfb) and xdotool; else they're skipped.

    python3.12 -m unittest tests.test_linux          (or tests/runall.sh)"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import clipread as CR, linkeys as LK, linsys as L, ocrengine as OE    # noqa: E402
from soe2 import remnant as RM, screenread as SR                                  # noqa: E402
from soe2.winsys import KeyWatch                                                  # noqa: E402

LINUX = sys.platform.startswith("linux")
HAS_X = bool(os.environ.get("DISPLAY")) and shutil.which("xdotool") is not None


def tool_dir(*names, body='#!/bin/sh\nexit 0\n'):
    """A folder with stand-in commands (for PATH)."""
    d = tempfile.mkdtemp(prefix="soe2-bin-")
    for n in names:
        p = os.path.join(d, n)
        with open(p, "w") as f:
            f.write(body)
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    return d


class Session(unittest.TestCase):
    def test_session_type(self):
        self.assertEqual(L.session_type({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}), "x11")
        self.assertEqual(L.session_type({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"}), "wayland")
        self.assertEqual(L.session_type({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}), "wayland")
        self.assertEqual(L.session_type({"DISPLAY": ":1"}), "x11")
        self.assertEqual(L.session_type({}), "unknown")
        self.assertTrue(L.has_x({"DISPLAY": ":0", "WAYLAND_DISPLAY": "w"}))      # XWayland
        self.assertEqual(L.desktop({"HYPRLAND_INSTANCE_SIGNATURE": "x"}), "Hyprland")
        self.assertEqual(L.desktop({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}), "ubuntu")

    def test_distro_and_install_lines(self):
        d = tempfile.mkdtemp()
        cases = {'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\n': "debian", 'ID=fedora\n': "fedora",
                 'ID="cachyos"\nID_LIKE="arch"\n': "arch", 'ID=opensuse-tumbleweed\nID_LIKE="opensuse suse"\n': "suse",
                 'ID=nixos\n': None}
        for text, fam in cases.items():
            p = os.path.join(d, "os-release")
            with open(p, "w") as f:
                f.write(text)
            self.assertEqual(L.distro(p), fam, text)
        self.assertIsNone(L.distro(os.path.join(d, "missing")))
        self.assertEqual(L.install_cmd("tesseract", "debian"), "sudo apt install tesseract-ocr")
        self.assertEqual(L.install_cmd("tesseract", "fedora"), "sudo dnf install tesseract tesseract-langpack-eng")
        self.assertEqual(L.install_cmd("tesseract", "arch"), "sudo pacman -S tesseract tesseract-data-eng")
        self.assertEqual(L.install_cmd("tesseract", "nope"), "sudo apt install tesseract-ocr / sudo dnf install "
                                                            "tesseract tesseract-langpack-eng / sudo pacman -S "
                                                            "tesseract tesseract-data-eng")

    def test_tools(self):
        x11 = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}
        way = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "DISPLAY": ":0"}
        pure = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w"}
        empty = tool_dir()
        both = tool_dir("xclip", "wl-paste", "wl-copy", "xdotool", "ydotool")
        self.assertEqual(L.clipboard_tool(x11, both), "xclip")
        self.assertEqual(L.clipboard_tool(way, both), "xclip", "the game's copies are on XWayland's clipboard")
        self.assertEqual(L.clipboard_tool(pure, both), "wl-paste")
        self.assertEqual(L.clipboard_tool(pure, tool_dir("wl-paste")), None, "wl-paste without wl-copy can't write")
        self.assertIsNone(L.clipboard_tool(x11, empty))
        self.assertEqual(L.key_tool(x11, both), "xdotool")
        self.assertEqual(L.key_tool(way, both), "xdotool", "the game is an XWayland window: xdotool reaches it")
        self.assertEqual(L.key_tool(pure, both), "ydotool")
        self.assertIsNone(L.key_tool(x11, empty))


class ClientTxt(unittest.TestCase):
    def make(self, rel):
        p = os.path.join(self.home, rel, *L.LOG_REL.split(os.sep))
        os.makedirs(os.path.dirname(p))
        open(p, "w").close()
        return p

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="soe2-steam-")

    def test_native_steam(self):
        p = self.make(".local/share/Steam")
        roots = [os.path.join(self.home, ".local/share/Steam"), os.path.join(self.home, ".steam/steam")]
        self.assertEqual(L.find_log(roots, prefixes=[]), p)

    def test_flatpak_steam(self):
        p = self.make(".var/app/com.valvesoftware.Steam/.local/share/Steam")
        self.assertEqual(L.find_log([os.path.join(self.home, ".var/app/com.valvesoftware.Steam/.local/share/Steam")],
                                    prefixes=[]), p)

    def test_other_library_from_vdf(self):
        root = os.path.join(self.home, ".steam/steam")
        os.makedirs(os.path.join(root, "steamapps"))
        lib = os.path.join(self.home, "games/SteamLibrary")
        p = self.make("games/SteamLibrary")
        with open(os.path.join(root, "steamapps", "libraryfolders.vdf"), "w") as f:
            f.write('"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n'
                    % (root, lib))
        self.assertIn(lib, L.steam_libraries([root]))
        self.assertEqual(L.find_log([root], prefixes=[]), p)

    def test_wine_prefix(self):
        pre = os.path.join(self.home, "Games/path-of-exile-2")
        p = os.path.join(pre, L.PREFIX_REL[0])
        os.makedirs(os.path.dirname(p))
        open(p, "w").close()
        self.assertEqual(L.find_log([], prefixes=[pre]), p)

    def test_nothing(self):
        self.assertIsNone(L.find_log([os.path.join(self.home, "nope")], prefixes=[]))

    @unittest.skipUnless(LINUX, "Linux")
    def test_gamelog_uses_it(self):
        from soe2 import gamelog
        p = self.make(".local/share/Steam")
        with mock.patch.object(L, "STEAM_ROOTS", [os.path.join(self.home, ".local/share/Steam")]), \
                mock.patch.object(L, "PREFIXES", []):
            self.assertIn(p, gamelog.candidates())
            gamelog.FOUND.clear()
            self.assertEqual(gamelog.find_log(), p)


class Ocr(unittest.TestCase):
    def tearDown(self):
        OE.ENGINE[0] = OE.TESS[0] = OE.RUNNER[0] = None
        OE.rescan()

    @unittest.skipUnless(LINUX, "Linux")
    def test_engine_choice(self):
        OE.TESS[0] = "/usr/bin/tesseract"
        self.assertEqual(OE.engine(), "tesseract")
        self.assertEqual(OE.problem(), "")
        self.assertEqual(RM.ocr_available(), "")
        OE.TESS[0] = ""
        OE._FOUND["pyt"] = True
        self.assertEqual(OE.engine(), "pytesseract")
        OE._FOUND["pyt"] = False
        self.assertEqual(OE.engine(), "")

    @unittest.skipUnless(LINUX, "Linux")
    def test_missing_state(self):
        OE.TESS[0] = ""
        OE._FOUND["pyt"] = False
        why = RM.ocr_available()
        self.assertTrue(why.startswith("needs OCR - install tesseract (sudo "), why)
        self.assertLess(len(why), 90, "one short line")
        with self.assertRaises(RM.OcrUnavailable):
            RM.ocr(None)
        self.assertIn("unavailable: needs OCR", RM.selftest())
        tip = OE.help_text()
        for line in ("sudo apt install tesseract-ocr", "sudo dnf install tesseract", "sudo pacman -S tesseract "
                     "tesseract-data-eng"):
            self.assertIn(line, tip)
        # the rows: text-only helpers warn, picture matchers keep working and say what needs OCR
        st, txt = OE.row_state("temple", "on", "On - press your key with the Temple Console open.")
        self.assertEqual(st, "warn")
        self.assertTrue(txt.startswith("Can't read the screen: needs OCR - install tesseract") and txt.endswith("ⓘ"))
        st, txt = OE.row_state("remnant", "warn", f"Can't read the screen: {why}.")
        self.assertEqual((st, txt.count("ⓘ")), ("warn", 1))
        st, txt = OE.row_state("sekhemas", "on", "On - press it on the trial map")
        self.assertEqual(st, "on")
        self.assertTrue(txt.endswith("reading text needs OCR  ⓘ"))
        self.assertEqual(OE.row_state("breach", "on", "On - x"), ("on", "On - x"))
        self.assertEqual(OE.row_state("temple", "off", "Off"), ("off", "Off"))
        OE.TESS[0] = "/usr/bin/tesseract"
        self.assertEqual(OE.row_state("temple", "on", "On - y"), ("on", "On - y"))

    def test_parse_tsv(self):
        tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
               "1\t1\t0\t0\t0\t0\t0\t0\t800\t200\t-1\t\n"
               "5\t1\t1\t1\t1\t1\t20\t40\t60\t20\t95\tOrb\n"
               "5\t1\t1\t1\t1\t2\t90\t42\t30\t18\t96\tof\n"
               "5\t1\t1\t1\t1\t3\t130\t40\t120\t22\t94\tAlchemy\n"
               "5\t1\t2\t1\t1\t1\t20\t100\t40\t20\t90\tx3\n"
               "5\t1\t2\t1\t1\t2\t70\t100\t40\t20\t90\t \n")
        self.assertEqual(OE.parse_tsv(tsv, scale=2.0),
                         [("Orb of Alchemy", (10, 20, 125, 31)), ("x3", (10, 50, 30, 60))])
        self.assertEqual(OE.parse_tsv(""), [])

    @unittest.skipUnless(LINUX, "Linux")
    def test_one_run_per_picture(self):
        from PIL import Image
        runs = []
        OE.TESS[0] = "/usr/bin/tesseract"
        OE.RUNNER[0] = lambda args, data, timeout: (runs.append((args, data[:8])), "level\n5\t1\t1\t1\t1\t1\t2\t2\t8"
                                                                                   "\t8\t90\tHi\n")[1]
        out = RM.ocr(Image.new("RGB", (100, 40), (10, 10, 10)))
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0][0][1:3], ["stdin", "stdout"])
        self.assertEqual(runs[0][1], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(out, [("Hi", (1, 1, 5, 5))])

    @unittest.skipUnless(LINUX, "Linux")
    def test_no_picture_for_text_only_helpers(self):
        from soe2.look_page import LookPage
        names = ("hover_look_job", "temple_console_job", "remnant_look_job", "favours_look_job",
                 "ru_look_job", "ws_look_job", "topup_look_job", "sekhemas_look_job")
        App = type("App", (LookPage,), {n: (lambda n: lambda self, ctx: (n, None, None))(n) for n in names})
        OE.TESS[0] = ""
        OE._FOUND["pyt"] = False
        got = [j[0] for j in App().look_jobs({"area": "map"})]
        self.assertNotIn("hover_look_job", got)
        self.assertNotIn("temple_console_job", got)
        self.assertIn("favours_look_job", got, "picture matching helpers still apply")
        self.assertIn("sekhemas_look_job", got)
        OE.TESS[0] = "/usr/bin/tesseract"
        self.assertEqual(len(App().look_jobs({"area": "map"})), len(names))

    @unittest.skipUnless(LINUX and shutil.which("tesseract"), "tesseract")
    def test_real_tesseract(self):
        self.assertIn("Alchemy", RM.selftest())


class GameWindow(unittest.TestCase):
    class FakeX:
        def __init__(self, active, wins):
            self.a, self.wins = active, wins

        def supported(self):
            return True

        def active(self):
            return self.a

        def clients(self):
            return list(self.wins)

        def info(self, wid):
            return dict(self.wins[wid], id=wid)

        def rect(self, wid):
            return (100, 50, 1920, 1080)

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": ""})
        self.env.start()
        L._X["sup_t"] = 0

    def tearDown(self):
        L.XLIB[0] = None
        L._X["sup_t"] = 0
        self.env.stop()

    def test_proton_game_in_front(self):
        L.XLIB[0] = self.FakeX(7, {7: {"class": "steam_app_2694490", "initialClass": "steam_app_2694490",
                                       "title": "Path of Exile 2", "pid": 1},
                                   9: {"class": "Stashofexile2", "title": "StashOfExile2", "pid": os.getpid()}})
        self.assertTrue(L.can_tell())
        self.assertTrue(L.game_active())
        self.assertTrue(L.game_open())
        self.assertEqual(L.game_rect(), (100, 50, 1920, 1080))
        self.assertIs(L.app_in_front(), False)
        L.XLIB[0].a = 9
        self.assertFalse(L.game_active())
        self.assertIs(L.app_in_front(), True)

    def test_title_must_match_exactly(self):
        L.XLIB[0] = self.FakeX(3, {3: {"class": "firefox", "title": "Path of Exile 2 build guide - YouTube"}})
        self.assertFalse(L.game_active(), "a browser tab named after the game isn't the game")
        self.assertFalse(L.game_open())
        L.XLIB[0] = self.FakeX(3, {3: {"class": "pathofexile.exe", "title": "Path of Exile 2"}})
        self.assertTrue(L.game_active(), "the standalone client under Wine: by its window name")

    def test_nothing_can_tell(self):
        L.XLIB[0] = type("NoWM", (self.FakeX,), {"supported": lambda s: False})(None, {})
        self.assertFalse(L.can_tell())
        self.assertFalse(L.game_active())
        self.assertTrue(L.game_open(), "can't tell: don't block anything")
        self.assertIsNone(L.game_rect())
        self.assertIsNone(L.app_in_front())


class Keys(unittest.TestCase):
    def test_keysyms(self):
        self.assertEqual(LK.vk_of_keysym("r"), 0x52)
        self.assertEqual(LK.vk_of_keysym("R"), 0x52)
        self.assertEqual(LK.vk_of_keysym("F9"), 0x78)
        self.assertEqual(LK.vk_of_keysym("KP_5"), 0x65)
        self.assertEqual(LK.vk_of_keysym("Control_L"), 0xA2)
        self.assertEqual(LK.vk_of_keysym("Escape"), 0x1B)
        self.assertIsNone(LK.vk_of_keysym("XF86AudioPlay"))

    def test_auto_repeat_is_not_a_press(self):
        r = LK.Repeats()
        self.assertEqual(r.feed("down", 27, 1000), [("down", 27)])
        self.assertEqual(r.feed("up", 27, 1500), [])                 # held back until the next event
        self.assertEqual(r.feed("down", 27, 1500), [], "release + press at the same time = X11's auto-repeat")
        self.assertEqual(r.feed("up", 27, 1600), [])
        self.assertEqual(r.feed("down", 27, 1900), [("up", 27), ("down", 27)], "a real second press")
        self.assertEqual(r.feed("up", 27, 2000), [])
        self.assertEqual(r.feed("down", 30, 2000), [("up", 27), ("down", 30)])

    def test_feed_and_modifiers(self):
        kw, got, ups = KeyWatch(), [], []
        kw.listener = lambda *a: (got.append(a), a[0] == 0x70)[1]
        kw.up_listener = ups.append
        kw.feed(0xA2, True, False)
        kw.feed(0xA4, True, False)
        kw.feed(0x43, True, False)
        self.assertTrue(kw.combo_recent())
        self.assertEqual(got, [(0x43, True, True, False)])
        kw.feed(0x43, False, True)
        kw.feed(0xA4, False, True)
        kw.feed(0xA2, False, True)
        self.assertFalse(kw.ctrl or kw.alt)
        self.assertTrue(kw.feed(0x70, True, False), "an app hotkey says it used the key")
        self.assertTrue(kw.feed(0x70, False, True))
        self.assertEqual(ups, [0x43, 0xA4, 0xA2, 0x70])

    def test_socket_one_message_one_press(self):
        kw, got, ups = KeyWatch(), [], []
        kw.listener = lambda *a: got.append(a)
        kw.up_listener = ups.append
        path = os.path.join(tempfile.mkdtemp(), "s.sock")
        sk = LK.SocketKeys(kw, path)
        self.assertEqual(sk.open(), "")
        import threading
        threading.Thread(target=sk.run, daemon=True).start()
        try:
            self.assertEqual(LK.send("Ctrl+Shift+R", path), 0)
            self.assertEqual(LK.send("no such key", path), 1)
            self.assertEqual(got, [(0x52, True, False, True)])
            self.assertEqual(ups, [0x52, 0xA0, 0xA2])
            self.assertFalse(kw.ctrl or kw.shift)
            self.assertEqual(LK.SocketKeys(kw, path).open(), "another StashOfExile2 is listening")
        finally:
            sk.close()
        self.assertEqual(LK.send("F9", path), 2, "the app isn't running")

    def test_send_tools(self):
        from soe2 import overlay as OV
        ev = []
        OV.send_copy(sender=ev.extend)
        self.assertEqual(LK.xdotool_args(ev), [["xdotool", "keyup", "Shift_L", "keydown", "Control_L", "keydown",
                                                "Alt_L", "keydown", "c", "sleep", "0.01", "keyup", "c", "keyup",
                                                "Alt_L", "keyup", "Control_L"]])
        self.assertEqual(LK.ydotool_args(ev), [["ydotool", "key", "42:0", "29:1", "56:1", "46:1", "46:0", "56:0",
                                                "29:0"]])
        typed = [(0x0D, None, False), (0x0D, None, True), (None, "h", False), (None, "h", True), (None, "i", False),
                 (None, "i", True), (0x0D, None, False), (0x0D, None, True)]
        enter = ["xdotool", "keydown", "Return", "sleep", "0.01", "keyup", "Return"]
        self.assertEqual(LK.xdotool_args(typed), [enter, ["xdotool", "type", "--delay", "0", "--", "hi"], enter])

    @unittest.skipUnless(LINUX, "Linux")
    def test_send_keys_linux(self):
        from soe2 import overlay as OV
        runs = []
        OV.KEY_TOOL[0], OV.KEY_RUNNER[0] = "xdotool", runs.append
        try:
            OV.send_copy()
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0][0], "xdotool")
            self.assertTrue(LK.ours(), "the app's own keys aren't yours for a moment")
            OV.KEY_TOOL[0] = ""
            self.assertFalse(OV._send_keys([(0x0D, None, False)]), "no tool: nothing sent, no crash")
        finally:
            OV.KEY_TOOL[0] = OV.KEY_RUNNER[0] = None
            LK.SENDING[0] = 0.0

    @unittest.skipUnless(LINUX and HAS_X, "an X server and xdotool")
    def test_x11_record_hears_presses(self):
        kw, got = KeyWatch(), []
        kw.listener = lambda *a: got.append(a)
        xw = LK.XRecordWatch(kw)
        why = xw.open()
        if why:
            self.skipTest(why)
        import threading
        threading.Thread(target=xw.run, daemon=True).start()
        time.sleep(0.3)
        subprocess.run(["xdotool", "key", "ctrl+shift+r"], check=True)
        subprocess.run(["xdotool", "key", "F9"], check=True)
        for _ in range(30):
            if len(got) >= 2:
                break
            time.sleep(0.1)
        self.assertEqual(got[:2], [(0x52, True, False, True), (0x78, False, False, False)])
        LK.SENDING[0] = time.time() + 2                 # the app's own key presses: not heard
        subprocess.run(["xdotool", "key", "F8"], check=True)
        time.sleep(0.4)
        LK.SENDING[0] = 0.0
        self.assertNotIn(0x77, [g[0] for g in got])


class FakeHyprland:
    """Hyprland's IPC socket ($XDG_RUNTIME_DIR/hypr/<sig>/.socket.sock) and a hyprctl on PATH that records the binds
    it's given (they then show in j/binds, like the real one)."""

    def __init__(self, active=None, clients=()):
        import json
        import socket
        import threading
        self.json = json
        self.run_dir = tempfile.mkdtemp(prefix="soe2-hypr-")
        self.sig = "testsig"
        d = os.path.join(self.run_dir, "hypr", self.sig)
        os.makedirs(d)
        self.active, self.clients = active or {}, list(clients)
        self.log = os.path.join(self.run_dir, "hyprctl.log")
        self.bin = tool_dir("hyprctl", body='#!/bin/sh\nprintf "%s\\n" "$*" >> "' + self.log + '"\n'
                            'case "$1" in eval) echo "error: no lua here"; exit 0;; esac\necho ok\n')
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(os.path.join(d, ".socket.sock"))
        self.srv.listen(8)
        threading.Thread(target=self.serve, daemon=True).start()
        self.env = mock.patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": self.sig,
                                                "XDG_RUNTIME_DIR": self.run_dir,
                                                "PATH": self.bin + os.pathsep + os.environ.get("PATH", "")})

    def binds(self):
        out = []
        try:
            with open(self.log) as f:
                for ln in f:
                    if ln.startswith("keyword bindnd "):
                        parts = [p.strip() for p in ln[len("keyword bindnd "):].split(",", 4)]
                        out.append({"modmask": parts[0], "key": parts[1], "description": parts[2],
                                    "arg": parts[4].strip()})
        except OSError:
            pass
        return out

    def calls(self):
        try:
            with open(self.log) as f:
                return [ln.rstrip("\n") for ln in f]
        except OSError:
            return []

    def serve(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            with c:
                cmd = c.recv(256).decode()
                ans = {"j/version": {"tag": "v0.56.0"}, "j/binds": self.binds(), "j/activewindow": self.active,
                       "j/clients": self.clients}.get(cmd)
                c.sendall(self.json.dumps(ans).encode())

    def __enter__(self):
        self.env.start()
        return self

    def __exit__(self, *a):
        self.env.stop()
        self.srv.close()


GAME = {"class": "steam_app_2694490", "initialClass": "steam_app_2694490", "title": "Path of Exile 2",
        "at": [0, 0], "size": [2560, 1440], "pid": 4242}


@unittest.skipUnless(LINUX, "Linux")
class Hyprland(unittest.TestCase):
    """The main tested setup (Arch + Hyprland, the game through Proton): IPC, the pass-through binds, the socket."""

    def tearDown(self):
        LK.RUN[0] = None
        LK.HYPR.update(keys=None, added=[], have=0, want=0, err=None, writer=None)
        L._X["sup_t"] = 0

    def test_key_names(self):
        for text, line in (("Ctrl+Shift+R", "ctrl+shift+r"), ("Ctrl+D", "ctrl+d"), ("F6", "f6"), ("Esc", "escape"),
                           ("Ctrl+;", "ctrl+semicolon"), ("Numpad3", "kp_3"), ("Ctrl+Alt+C", "ctrl+alt+c")):
            self.assertEqual(LK.key_line(text), line, text)
            self.assertEqual(LK.line_key(line), __import__("soe2.overlay", fromlist=["x"]).parse_key(text), line)
        self.assertIsNone(LK.key_line("Mouse4"), "mouse buttons can't be Hyprland binds")
        self.assertIsNone(LK.key_line(""))
        self.assertEqual(LK.bind_parts("ctrl+shift+r"), (["CTRL", "SHIFT"], "R"))
        cmd = "echo {line} | socat - UNIX-CONNECT:/run/user/1000/stashofexile2.sock"
        self.assertEqual(LK.keyword_bind("ctrl+shift+r", cmd), "CTRL SHIFT, R, SoE2 ctrl+shift+r, exec, echo "
                         "ctrl+shift+r | socat - UNIX-CONNECT:/run/user/1000/stashofexile2.sock")
        self.assertEqual(LK.lua_bind("f6", cmd), 'hl.bind("F6", hl.dsp.exec_cmd("echo f6 | socat - UNIX-CONNECT:'
                         '/run/user/1000/stashofexile2.sock"), { non_consuming = true, description = "SoE2 f6" })')

    def test_only_missing_binds_are_added(self):
        calls = []
        LK.RUN[0] = lambda args: (calls.append(args), (0, "ok") if args[1] == "eval" else (0, "ok"))[1]
        keys = ["Ctrl+Shift+R", "Ctrl+D", "Esc", "F1", "Mouse4", "Ctrl+D"]       # Read Key, price check, close, chat
        have = [{"description": "SoE2 ctrl+d"}, {"description": "my own bind"}]
        added = LK.sync_binds(keys, binds=have, path="/x.sock")
        self.assertEqual(added, ["ctrl+shift+r", "escape", "f1", "ctrl+alt+c", "ctrl+c"])
        self.assertEqual([c[1] for c in calls], ["eval"] * 5, "Lua configs: hl.bind")
        self.assertEqual((LK.HYPR["want"], LK.HYPR["have"]), (6, 6))
        calls.clear()
        LK.RUN[0] = lambda args: (calls.append(args), (0, "error: lua isn't on") if args[1] == "eval" else (0, "ok"))[1]
        self.assertEqual(LK.sync_binds(["F9"], binds=[], path="/x.sock")[:1], ["f9"])
        self.assertEqual([c[1:3] for c in calls[:2]], [["eval", calls[0][2]], ["keyword", "bindnd"]],
                         "classic configs: keyword bindnd")
        calls.clear()
        everything = [{"description": "SoE2 " + ln} for ln in LK.wanted_lines(keys)]
        self.assertEqual(LK.sync_binds(keys, binds=everything, path="/x.sock"), [])
        self.assertEqual(calls, [], "all there: no hyprctl at all (one IPC request was the whole check)")
        self.assertEqual(LK.sync_binds(keys, binds="nope"), [])
        self.assertEqual(LK.HYPR["err"], "Hyprland's IPC didn't answer")

    def test_ipc_game_window(self):
        with FakeHyprland(active=GAME, clients=[GAME]):
            self.assertIsNotNone(L.hypr_socket())
            self.assertTrue(L.can_tell())
            self.assertTrue(L.game_active())
            self.assertEqual(L.game_rect(), (0, 0, 2560, 1440))
            self.assertIs(L.app_in_front(), False)
        tab = dict(GAME, **{"class": "firefox", "initialClass": "firefox", "title": "Path of Exile 2 - wiki"})
        with FakeHyprland(active=tab, clients=[tab]):
            self.assertFalse(L.game_active(), "a browser tab isn't the game")

    @unittest.skipUnless(shutil.which("socat"), "socat")
    def test_bind_to_socket_end_to_end(self):
        """The app adds the binds; Hyprland running one (its command, here run by hand) is one key press."""
        with FakeHyprland(active=GAME, clients=[GAME]) as hy:
            kw, got, ups = KeyWatch(), [], []
            kw.listener = lambda *a: got.append(a)
            kw.up_listener = ups.append
            kw.keys_source = lambda: ["Ctrl+Shift+R", "Ctrl+D", "F1"]
            LK.start(kw)
            try:
                for _ in range(50):
                    if len(hy.binds()) >= 5:
                        break
                    time.sleep(0.1)
                self.assertIsNot(LK.STATE["x11"], True, "Hyprland: no X11 watcher (a press would come twice)")
                b = {x["description"]: x for x in hy.binds()}
                self.assertEqual(sorted(b), sorted("SoE2 " + ln for ln in ("ctrl+shift+r", "ctrl+d", "f1",
                                                                          "ctrl+alt+c", "ctrl+c")))
                self.assertTrue(any(c.startswith("eval hl.bind(") for c in hy.calls()), "Lua tried first")
                subprocess.run(b["SoE2 ctrl+shift+r"]["arg"], shell=True, check=True, capture_output=True)
                for _ in range(30):
                    if got:
                        break
                    time.sleep(0.05)
                self.assertEqual(got, [(0x52, True, False, True)], "the Read Key, once")
                self.assertEqual(ups, [0x52, 0xA0, 0xA2], "and let go (the next press is a new one)")
                n = len(hy.calls())
                LK.sync_binds(kw.keys_source())
                self.assertEqual(len(hy.calls()), n, "binds in place: the check runs no hyprctl")
                from soe2 import lincheck as LC
                st, what, fix = LC.hypr_line(running={"hypr": True})
                self.assertEqual(st, "ok", what)
                self.assertIn("IPC ok (0.56.0)", what)
                self.assertIn("5 of 5 pass-through binds", what)
                rows = LC.report(running={"hypr": True, "socket": True})
                self.assertEqual(rows[0][0], "Hyprland", "Hyprland comes first")
                self.assertEqual({r[0]: r[1] for r in rows}["Keys"], "ok")
            finally:
                try:
                    os.remove(LK.sock_path())
                except OSError:
                    pass

    def test_check_without_socat(self):
        from soe2 import lincheck as LC
        with FakeHyprland(active=GAME, clients=[GAME]):
            st, what, fix = LC.hypr_line(path=tool_dir())
        self.assertEqual(st, "fix")
        self.assertIn("install socat", fix)


class Clipboard(unittest.TestCase):
    def setUp(self):
        CR.reset()
        CR.LOGGER[0] = lambda line: None

    def tearDown(self):
        CR.TOOL[0] = CR.LOGGER[0] = None
        CR.reset()

    @unittest.skipUnless(LINUX, "Linux")
    def test_one_read_per_press_with_xclip(self):
        d = tool_dir("xclip", body='#!/bin/sh\necho "$@" >> "$(dirname "$0")/calls"\nprintf "Item Class: Rings"\n')
        CR.TOOL[0] = "xclip"
        with mock.patch.dict(os.environ, {"PATH": d + os.pathsep + os.environ.get("PATH", "")}):
            gid = CR.grant("Ctrl+C", hold=0x43, now=100.0)
            self.assertEqual(CR.take(gid, "Price Checks", now=100.3), "Item Class: Rings")
            self.assertIsNone(CR.take(gid, "Price Checks", now=100.4), "no second read for the same press")
            self.assertTrue(CR.write_text("/hideout"))
            self.assertTrue(CR.clear())
        with open(os.path.join(d, "calls")) as f:
            calls = f.read().split("\n")
        self.assertEqual(calls[:3], ["-selection clipboard -o", "-selection clipboard -i",
                                     "-selection clipboard -i /dev/null"])

    @unittest.skipUnless(LINUX, "Linux")
    def test_no_tool_off_the_window_thread(self):
        CR.TOOL[0] = ""
        import threading
        out = []
        t = threading.Thread(target=lambda: out.append((CR._raw_linux(), CR._write_linux("x"))))
        t.start()
        t.join()
        self.assertEqual(out, [(None, False)], "Tk's clipboard is never touched from another thread")


class Capture(unittest.TestCase):
    def test_tool_choice(self):
        x11 = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}
        hypr = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "DISPLAY": ":0",
                "HYPRLAND_INSTANCE_SIGNATURE": "abc"}
        gnome = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "GNOME"}
        kde = dict(gnome, XDG_CURRENT_DESKTOP="KDE")
        pure = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w"}
        tools = tool_dir("grim", "spectacle", "gnome-screenshot")
        none = tool_dir()
        self.assertEqual(SR.capture_tool(x11, none)[0], "mss")
        self.assertEqual(SR.capture_tool(hypr, tools)[0], "grim")
        self.assertEqual(SR.capture_tool(gnome, tools)[0], "gnome-screenshot")
        self.assertEqual(SR.capture_tool(kde, tools)[0], "spectacle")
        self.assertEqual(SR.capture_tool(gnome, none)[0], "mss", "through XWayland")
        self.assertIsNone(SR.capture_tool(pure, none)[0])
        self.assertEqual(SR.capture_tool(dict(x11, SOE2_CAPTURE="grim"), tools)[0], "grim")
        self.assertIsNone(SR.capture_tool(dict(x11, SOE2_CAPTURE="grim"), none)[0])
        self.assertEqual(SR.capture_check(pure, none)[0], "fix")
        self.assertEqual(SR.capture_check(gnome, none)[0], "warn")

    @unittest.skipUnless(LINUX, "Linux")
    def test_grim_one_picture(self):
        from PIL import Image
        png = os.path.join(tempfile.mkdtemp(), "p.png")
        Image.new("RGB", (40, 30), (200, 10, 10)).save(png)
        d = tool_dir("grim", body=f'#!/bin/sh\necho "$@" >> "$(dirname "$0")/calls"\ncat "{png}"\n')
        env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "HYPRLAND_INSTANCE_SIGNATURE": "x",
               "PATH": d + os.pathsep + os.environ.get("PATH", "")}
        with mock.patch.dict(os.environ, env):
            img = SR._grab_linux((10, 20, 50, 50))
        self.assertEqual(img.size, (40, 30))
        with open(os.path.join(d, "calls")) as f:
            self.assertEqual(f.read().strip(), "-g 10,20 40x30 -")

    @unittest.skipUnless(LINUX and os.environ.get("DISPLAY"), "an X server")
    def test_x11_grab_through_the_gate(self):
        SR.reset()
        SR.LOGGER[0] = SR.SAID[0] = lambda *a: None
        SR.AREA[0] = lambda: (0, 0, 200, 100)
        try:
            with mock.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}):
                self.assertIsNone(SR.capture((0, 0, 50, 50), "Test"), "no key press: no picture")
                self.assertTrue(SR.grant("F9", hold=0x78))
                img = SR.capture((0, 0, 50, 50), "Test")
            self.assertEqual(img.size, (50, 50))
            self.assertEqual(SR.COUNT["shots"], 1)
            SR.finish()
        finally:
            SR.AREA[0] = SR.LOGGER[0] = SR.SAID[0] = None
            SR.reset()


class LinuxCheck(unittest.TestCase):
    def tearDown(self):
        OE.TESS[0] = None
        OE.rescan()

    @unittest.skipUnless(LINUX, "Linux")
    def test_report(self):
        from soe2 import lincheck as LC
        OE.TESS[0] = ""
        OE._FOUND["pyt"] = False
        env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w"}
        with mock.patch.dict(os.environ, {"PATH": tool_dir(), "HYPRLAND_INSTANCE_SIGNATURE": ""}):
            rows = LC.report(env=env, path=tool_dir())
        names = [r[0] for r in rows]
        self.assertEqual(names, ["Session", "Game window", "Keys", "Screen picture", "Clipboard", "Key sending", "OCR",
                                 "Client.txt"])
        by = {r[0]: r for r in rows}
        self.assertEqual(by["Session"][1], "warn")
        self.assertEqual(by["OCR"][1], "fix")
        self.assertIn("install tesseract (sudo ", by["OCR"][3])
        self.assertEqual(by["Clipboard"][3].split(" (")[0], "install wl-clipboard")
        self.assertIn("xdotool", by["Key sending"][3])
        self.assertTrue(all(r[1] in ("ok", "warn", "fix") for r in rows))
        self.assertTrue(all(r[3] for r in rows if r[1] == "fix"), "every line to fix says how")
        s = LC.summary(rows)
        self.assertTrue(s.startswith(f"{sum(r[1] == 'ok' for r in rows)} of 8 OK · "), s)
        txt = LC.text(rows)
        self.assertIn("✗ FIX   OCR", txt)
        self.assertIn("⚠ NOTE  Session: Wayland", txt)

    def test_cli(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "stashofexile2.py"), "--check-linux"],
                           capture_output=True, text=True, timeout=60)
        self.assertIn("Linux check", r.stdout)
        self.assertIn(r.returncode, (0, 1))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "stashofexile2.py"), "--key", "F9"],
                           capture_output=True, text=True, timeout=60,
                           env=dict(os.environ, XDG_RUNTIME_DIR=tempfile.mkdtemp()))
        self.assertEqual((r.returncode, r.stdout.strip()), (2, "StashOfExile2 isn't running."))


class Updates(unittest.TestCase):
    def test_linux_channel(self):
        from soe2 import updates as U
        rels = [{"tag_name": "v3.0.0", "assets": []},
                {"tag_name": "v3.0.1-linux-preview", "prerelease": True},
                {"tag_name": "v3.0.2-linux-preview", "prerelease": True},
                {"tag_name": "v3.0.9-linux-preview", "draft": True}]
        self.assertEqual(U.newest_linux(rels)["tag_name"], "v3.0.2-linux-preview")
        self.assertIsNone(U.newest_linux([{"tag_name": "v3.0.0"}]))
        # 3.0.5 on: the Linux download is on the full release itself
        tar = [{"name": "StashOfExile2-3.0.5-linux.tar.gz"}]
        both = rels + [{"tag_name": "v3.0.5", "assets": [{"name": "StashOfExile2.exe"}] + tar},
                       {"tag_name": "v3.0.6", "assets": [{"name": "StashOfExile2.exe"}]},           # (Linux job failed)
                       {"tag_name": "v3.0.7", "prerelease": True, "assets": tar}]
        self.assertEqual(U.newest_linux(both)["tag_name"], "v3.0.5")
        base = f"https://github.com/{U.REPO}/releases/download/v3/"
        rel = {"assets": [{"name": "StashOfExile2.exe", "browser_download_url": base + "StashOfExile2.exe"},
                          {"name": "StashOfExile2-3.0.1-linux.tar.gz",
                           "browser_download_url": base + "StashOfExile2-3.0.1-linux.tar.gz"},
                          {"name": "SHA256SUMS", "browser_download_url": base + "SHA256SUMS"}]}
        with mock.patch.object(U.sys, "platform", "linux"):
            self.assertEqual(U.pick_asset(rel, frozen=True)["name"], "StashOfExile2-3.0.1-linux.tar.gz")
            self.assertIsNone(U.pick_asset({"assets": rel["assets"][:1]}, frozen=True), "never the Windows exe")


if __name__ == "__main__":
    unittest.main()
