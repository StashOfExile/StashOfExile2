"""3.3.0 owner: every box that takes typed text refuses the board's filtered words, at the box. Notes are free.

The refused words are never written in this file: they are read from the list the board and the app share."""
import json
import os
import sys
import tkinter as tk
from tkinter import ttk
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from soe2 import cleanguard as G, cleantext as CT  # noqa: E402

WORDS = json.load(open(os.path.join(ROOT, "soe2", "cleanwords.json"), encoding="utf-8"))
BAD = [w for w in WORDS["hate"] + WORDS["rude"] if not w.isdigit() and len(w) >= 5]


class Filter(unittest.TestCase):
    def test_the_lists_are_refused_and_so_are_their_disguises(self):
        for w in BAD:
            for form in (w, w.upper(), "my " + w + " build", " ".join(w), w.replace("a", "4").replace("o", "0")):
                self.assertIsNotNone(CT.problem(form), "a listed word, form %d" % len(form))

    def test_the_games_own_words_pass(self):
        for ok in ("Strongbox farming", "Area contains an additional Strongbox", "Bestial Rage", "Mageblood",
                   "Breach Tablets A", "8mod t15", "the strongest build", "assassin", "Game version 4.5.5.2",
                   "Scunthorpe", "Raccoon, Spice and a Torpedo", ""):
            self.assertIsNone(CT.problem(ok), ok)

    def test_board_and_app_share_one_allow_list(self):
        board = json.load(open(os.path.join(ROOT, "board", "src", "gamewords.json"), encoding="utf-8"))
        self.assertEqual(board["allow"], WORDS["allow"])
        self.assertIn("strongbox", WORDS["allow"])

    def test_every_build_ships_the_word_list(self):
        for name, line in (("build_exe.bat", '--add-data "soe2\\cleanwords.json;soe2"'),
                           (os.path.join(".github", "workflows", "release.yml"), '--add-data "soe2\\cleanwords.json;soe2"'),
                           ("build_linux.sh", '--add-data "soe2/cleanwords.json:soe2"')):
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                self.assertIn(line, f.read(), name)
        self.assertGreater(len(WORDS["patterns"]), 100, "a build without the list would refuse nothing")

    def test_a_word_still_being_typed_is_not_judged_yet(self):
        w = BAD[0]
        self.assertIsNone(CT.while_typing(w), "it may grow into a fine word")
        self.assertIsNotNone(CT.while_typing(w + " "))
        self.assertIsNotNone(CT.while_typing("x " + w + " y", 1))


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Boxes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        G.install(cls.root)

    @classmethod
    def tearDownClass(cls):
        G.hide()
        cls.root.destroy()

    def box(self, kind):
        w = {"entry": tk.Entry, "tentry": ttk.Entry, "combo": ttk.Combobox, "text": tk.Text}[kind](self.root)
        w.pack()
        self.root.update()
        w.focus_force()
        self.root.update()
        return w

    def put(self, w, text):
        """Type text the way a paste does: in one go, then the paste check."""
        if isinstance(w, tk.Text):
            w.insert("insert", text)
        else:
            w.insert("insert", text)
        G.check(w, final=True)
        self.root.update()
        return w.get("1.0", "end-1c") if isinstance(w, tk.Text) else w.get()

    def test_every_kind_of_box_refuses(self):
        for kind in ("entry", "tentry", "combo", "text"):
            w = self.box(kind)
            self.assertEqual(self.put(w, "Fast maps"), "Fast maps", kind)
            self.assertEqual(self.put(w, " " + BAD[0]), "Fast maps", kind + ": back to what it held")
            w.destroy()

    def test_it_says_why_with_words(self):
        w = self.box("entry")
        self.put(w, BAD[1])
        self.assertIsNotNone(G._tip[0])
        said = G._tip[0].winfo_children()[0].cget("text")
        self.assertIn(CT.MSG, said)
        self.assertTrue(said.startswith("✕"))
        w.destroy()

    def test_typing_key_by_key(self):
        w = self.box("entry")
        for ch in BAD[0]:
            w.insert("insert", ch)
            w.event_generate("<KeyRelease>", keysym=ch if ch.isalnum() else "space")
            self.root.update()
        self.assertEqual(w.get(), BAD[0], "not judged while the word may still grow")
        w.insert("insert", " ")
        w.event_generate("<KeyRelease>", keysym="space")
        self.root.update()
        self.assertIsNone(CT.problem(w.get()), "judged once a space follows")
        self.assertNotIn(BAD[0], w.get())
        w.destroy()

    def test_leaving_the_box_judges_the_last_word(self):
        w, other = self.box("entry"), tk.Entry(self.root)
        other.pack()
        w.insert("insert", "ok " + BAD[2])
        G.check(w, final=True)
        self.assertEqual(w.get(), "")
        w.destroy()
        other.destroy()

    def test_notes_and_marked_boxes_are_free(self):
        w = G.free(self.box("text"))
        self.assertEqual(self.put(w, BAD[0]), BAD[0])
        w.destroy()
        w = self.box("entry")
        with G.paused():
            self.assertEqual(self.put(w, BAD[0]), BAD[0])
        w.destroy()

    def test_read_only_boxes_are_left(self):
        w = self.box("combo")
        w.set(BAD[0])
        w.configure(state="readonly")
        self.assertIsNone(G.check(w, final=True))
        w.destroy()

    def test_a_dialog_answer_is_asked_again(self):
        answers = iter([BAD[0], "Good name"])
        seen = []

        def fake(title, prompt, **kw):
            seen.append(prompt)
            return next(answers)
        self.assertEqual(G.clean_answer(fake)("Name", "Name:"), "Good name")
        self.assertEqual(len(seen), 2)
        self.assertIn(CT.MSG, seen[1])

    def test_notes_code_marks_itself_free(self):
        import inspect
        from soe2 import overlay, tracker_page
        self.assertIn("_cleanguard.free(text)", inspect.getsource(overlay))
        self.assertIn("with cleanguard.paused():", inspect.getsource(tracker_page))

    def test_wired_once_for_the_whole_app(self):
        import inspect
        from soe2 import listkit
        self.assertIn("cleanguard.install(root)", inspect.getsource(listkit.install))


if __name__ == "__main__":
    unittest.main()
