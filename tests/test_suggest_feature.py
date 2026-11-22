"""3.2.0 (owner): Suggest a Feature next to Report a bug - a small form, every word shown before it's sent, an [Idea]
issue on GitHub through the board, GitHub's own page if the board can't take it.

    DISPLAY=:99 python3.12 -m unittest tests.test_suggest_feature          (or tests/runall.sh)"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-idea-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import tkinter as tk                                 # noqa: E402

from soe2 import feedback_page as F                 # noqa: E402


class Host(F.FeedbackPage):
    def __init__(self, root):
        self.root = root
        self.toasts = []

    def dlg_parent(self):
        return self.root

    def run_bg(self, work, done):
        done(work())

    def app_toast(self, text, title, kind=""):
        self.toasts.append(text)


class Form(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.withdraw()
        from soe2 import style as S, themes as TH
        S.apply_look(TH.DEFAULT, self.root)
        S.setup_style(self.root)
        self.h = Host(self.root)

    def tearDown(self):
        self.root.destroy()

    def fill(self, title="Cost of 10 uses", what="Show the full cost of the waystone and tablets.", why="",
             credit=""):
        h = self.h
        h.idea_vars["title"].set(title)
        h.idea_vars["what"].insert("1.0", what)
        if why:
            h.idea_vars["why"].insert("1.0", why)
        h.idea_vars["credit"].set(credit)
        h._idea_preview()
        self.root.update()

    def test_send_waits_for_a_title_and_the_idea(self):
        h = self.h
        self.root.deiconify()                        # (a dialog over a hidden app stays hidden with it)
        h.idea_open()
        self.root.update()
        self.assertEqual(h.idea_win.state(), "normal", "shown once it is built")
        self.assertEqual(str(h.idea_send_btn.cget("state")), "disabled")
        self.assertIn("Still needed", h.idea_msg.cget("text"))
        self.fill()
        self.assertEqual(str(h.idea_send_btn.cget("state")), "normal")
        self.assertEqual(h.idea_msg.cget("text"), "")

    def test_preview_is_what_goes(self):
        h = self.h
        h.idea_open()
        self.fill(why="I farm with tablets.", credit="Worm")
        shown = h.idea_prev.get("1.0", "end-1c")
        self.assertTrue(shown.startswith("[Idea] Cost of 10 uses"))
        for part in ("**The idea**", "**How it would help**\nI farm with tablets.", "**Credit me as** Worm", "**App**"):
            self.assertIn(part, shown)
        sent = {}

        def call(method, path, body=None):
            sent.update(method=method, path=path, body=body)
            return True, {"number": 301, "url": "https://github.com/x/301"}
        with mock.patch.object(F.B, "call", call):
            h.idea_send()
        self.assertEqual((sent["method"], sent["path"], sent["body"]["kind"]), ("POST", "/bugs", "idea"))
        self.assertEqual(shown, f"[Idea] {sent['body']['title']}\n\n{sent['body']['body']}", "word for word")
        self.assertEqual(h.toasts, ["Thanks! Your idea is #301 on GitHub."])
        self.assertIsNone(h.idea_win)

    def test_no_name_no_credit(self):
        h = self.h
        h.idea_open()
        self.fill()
        self.assertNotIn("Credit me as", h.idea_prev.get("1.0", "end-1c"))

    def test_board_down_opens_github(self):
        h = self.h
        h.idea_open()
        self.fill()
        opened = []
        with mock.patch.object(F.B, "call", lambda *a, **k: (False, "the board is down")), \
                mock.patch.object(F.webbrowser, "open", opened.append):
            h.idea_send()
        self.assertEqual(len(opened), 1)
        self.assertIn("labels=enhancement", opened[0])
        self.assertIn("%5BIdea%5D", opened[0])
        self.assertIn("Press Submit there", h.idea_msg.cget("text"))
        self.assertEqual(str(h.idea_send_btn.cget("state")), "normal")

    def test_one_window(self):
        h = self.h
        w = h.idea_open()
        self.assertIs(h.idea_open(), w)


class Bar(unittest.TestCase):
    def test_next_to_report_a_bug(self):
        src = open(os.path.join(ROOT, "soe2", "feedback_page.py"), encoding="utf-8").read()
        self.assertIn('text="💡 Suggest a Feature"', src)
        self.assertIn("before=self.bug_btn)", src.split("self.idea_btn = ")[1].split("def ")[0])

    def test_no_parentheses_in_its_words(self):
        src = open(os.path.join(ROOT, "soe2", "feedback_page.py"), encoding="utf-8").read()
        part = src.split("# ================================================================ Suggest a Feature")[1]
        for line in (F.FeedbackPage.IDEA_INTRO, F.FeedbackPage.IDEA_CREDIT):
            self.assertNotIn("(", line)
        self.assertNotIn('(optional)', part)


@unittest.skipUnless(shutil.which("node"), "no node")
class Board(unittest.TestCase):
    def test_board_takes_ideas(self):
        r = subprocess.run(["node", os.path.join(ROOT, "board", "test", "bugs.test.mjs")], capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("bugs.test.mjs: ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
