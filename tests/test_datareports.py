"""3.3.0 owner: Report a Problem on Codex pages; admins review; hidden rows leave Game Search and Mod Lab."""
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from soe2 import datareports as DR  # noqa: E402
from soe2 import datareports_page, gamesearch  # noqa: E402


class Data(unittest.TestCase):
    def setUp(self):
        DR.reset({})
        p = mock.patch.object(DR, "save_json", lambda *a: True)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(DR.reset)

    def test_what_is_sent_and_what_is_refused(self):
        b = DR.body("ratemods", " unique:x:# life ", "wrong", "X", "+(1-2) Life", "  it is   3 now ")
        self.assertEqual((b["page"], b["ref"], b["note"]), ("ratemods", "unique:x:# life", "it is 3 now"))
        self.assertEqual(DR.body("pricecheck", "r", "wrong"), "This page cannot be reported from.")
        self.assertEqual(DR.body("maps", "r", ""), "Pick what is wrong.")
        self.assertEqual(DR.body("maps", "  ", "wrong"), "Pick a row first, then report it.")
        with mock.patch("soe2.cleantext.problem", lambda t: "bad" if "nasty" in str(t) else None):
            self.assertEqual(DR.body("maps", "r", "wrong", note="nasty"), "That wording is not allowed.")

    def test_send_goes_to_the_board_and_an_old_board_says_so(self):
        seen = []
        ok = DR.send("maps", "Burial Bog", "removed", "Burial Bog", call=lambda m, p, body=None: (seen.append((m, p, body["kind"])), (True, {}))[1])
        self.assertEqual(ok, (True, ""))
        self.assertEqual(seen, [("POST", "/reports", "removed")])
        self.assertIn("next board update", DR.send("maps", "r", "wrong", call=lambda *a, **k: (False, "not found"))[1])

    def test_hidden_rows_are_kept_by_page_and_cleaned(self):
        DR.pull(call=lambda m, p: (True, {"hidden": [["search", "g|Fishing Rod"], ["search", "db:7"],
                                                     ["ratemods", "unique:x:# life"], ["evil", "x"], ["maps", 5], "junk"]}))
        self.assertEqual(DR.hidden("search"), {"g|Fishing Rod", "db:7"})
        self.assertEqual(DR.hidden("ratemods"), {"unique:x:# life"})
        self.assertEqual(DR.hidden("evil"), set())
        self.assertIsNone(DR.pull(call=lambda m, p: (False, "down")))
        self.assertEqual(DR.hidden("search"), {"g|Fishing Rod", "db:7"}, "a board that is down changes nothing")

    def test_game_search_leaves_them_out(self):
        DR.reset({"search": ["g|Fishing Rod", "db:7"]})
        with mock.patch.object(gamesearch, "_hide_entries", lambda: []):
            self.assertIn("db:7", gamesearch.hidden_ids())
            self.assertIn(("Fishing Rod", "g"), gamesearch.hidden_names())
        self.assertEqual(gamesearch.report_ref({"db": True, "id": "db:7", "g": "x", "n": "y"}), "db:7")
        self.assertEqual(gamesearch.report_ref({"g": "Other Items", "n": "Fishing Rod"}), "Other Items|Fishing Rod")

    def test_reports_are_never_sent_with_the_board_key(self):
        from soe2 import board as B
        seen = []

        class R:
            status_code = 200

            def json(self):
                return {}

        def get(method, url, **kw):
            seen.append((method, url.rsplit("/", 2)[-1], "Authorization" in kw["headers"]))
            return R()
        with mock.patch.object(B, "configured", lambda: True), mock.patch.object(B, "url", lambda: "https://b"), \
                mock.patch.object(B, "session", lambda: {"token": "secret"}):
            B.call("POST", "/reports", body={}, get=get)
            B.call("GET", "/reports/hidden", get=get)
            B.call("GET", "/reports", get=get)
        self.assertEqual(seen, [("POST", "reports", False), ("GET", "hidden", False), ("GET", "reports", True)],
                         "only an admin's own list carries the key")

    def test_the_board_s_own_test_passes(self):
        if not shutil.which("node"):
            self.skipTest("needs node")
        r = subprocess.run(["node", os.path.join(ROOT, "board", "test", "reports.test.mjs")], capture_output=True,
                           text=True, timeout=120)
        self.assertIn("reports: ok", r.stdout, r.stderr[-1500:])


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Boxes(unittest.TestCase):
    def setUp(self):
        from soe2 import style
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        style.apply_look()

        class H(datareports_page.DataReportsPage):
            admin = False
            said = []

            def dlg_parent(self):
                return self.root

            def run_bg(self, work, done):
                return done(work())

            def share_is_admin(self):
                return self.admin

            def _say(self, text, secs=0):
                self.said.append(text)
        self.h = H()
        self.h.root = self.root

    def test_a_report_needs_what_is_wrong_then_sends_once(self):
        sent = []
        with mock.patch.object(DR, "send", lambda *a, **k: (sent.append(a), (True, ""))[1]):
            dlg = self.h.dr_report("ratemods", "unique:x:# life", "X", "+(1-2) Life")
            dlg.dr_send()
            self.assertEqual(dlg.dr_vars["msg"].cget("text"), "Pick what is wrong.")
            self.assertEqual(sent, [])
            dlg.dr_vars["kind"].set("wrong")
            dlg.dr_send()
        self.assertEqual(sent, [("ratemods", "unique:x:# life", "wrong", "X", "+(1-2) Life", "")])
        self.assertFalse(dlg.winfo_exists())
        self.assertEqual(self.h.said, ["✓ Report sent. Thank you."])

    def test_the_header_button_with_nothing_picked_says_what_to_do(self):
        shown = []
        with mock.patch("tkinter.messagebox.showinfo", lambda *a, **k: shown.append(a[1])):
            self.assertIsNone(self.h.dr_report_page("maps"))
        self.assertIn("Pick a row", shown[0])

    def test_reports_list_is_admins_only_and_buttons_follow_the_pick(self):
        self.assertIsNone(self.h.dr_reports())
        self.h.admin = True
        rows = [{"id": 1, "page": "ratemods", "ref": "k", "kind": "wrong", "item": "X", "line": "L", "note": "",
                 "version": "", "n": 3, "status": "open"},
                {"id": 2, "page": "search", "ref": "db:7", "kind": "removed", "item": "Rod", "line": "", "note": "",
                 "version": "", "n": 1, "status": "hidden"}]
        acted = []
        with mock.patch.object(DR, "reports", lambda: (True, rows)), \
                mock.patch.object(DR, "act", lambda rid, a: (acted.append((rid, a)), (True, {}))[1]), \
                mock.patch.object(DR, "pull", lambda: None):
            dlg = self.h.dr_reports()
            p = dlg.dr_parts
            self.assertEqual(self.h.dr_count(), 1)
            self.assertTrue(all(b.instate(["disabled"]) for b in p["btns"].values()), "grey until a report is picked")
            self.assertEqual([a for a, b in p["btns"].items() if str(b.cget("style")) == "Primary.TButton"], ["hide"])
            p["tv"].selection_set("1")
            self.root.update()
            self.assertFalse(p["btns"]["hide"].instate(["disabled"]))
            self.assertTrue(p["btns"]["reopen"].instate(["disabled"]), "an open one cannot be shown again")
            p["do"]("hide")
            p["tv"].selection_set("2")
            self.root.update()
            self.assertTrue(p["btns"]["hide"].instate(["disabled"]), "a hidden one cannot be hidden again")
            self.assertEqual(p["tv"].item("2", "values")[5], "● Hidden", "said in words")
            dlg.destroy()
        self.assertEqual(acted, [(1, "hide")])


if __name__ == "__main__":
    unittest.main()
