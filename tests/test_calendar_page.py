"""3.3.0 owner: Dashboard ↳ Calendar - the page."""
import datetime as dt
import os
import sys
import tkinter as tk
from tkinter import ttk
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import calendar_data as CD  # noqa: E402
from soe2 import calendar_page, names, sidebar as SB  # noqa: E402
from soe2.modules.calendar import Calendar  # noqa: E402


class Where(unittest.TestCase):
    def test_it_is_a_child_of_dashboard_with_one_name(self):
        self.assertEqual(Calendar.parent, "dashboard")
        self.assertEqual(names.PAGES["calendar"], "Calendar")
        self.assertEqual(Calendar.title, "Calendar")
        self.assertNotIn("calendar", [k for _g, keys in SB.GROUPS for k in keys], "listed under its parent only")

    def test_it_is_in_the_page_list(self):
        from soe2 import modules
        import inspect
        self.assertIn("Calendar", inspect.getsource(modules.load))


def all_widgets(w):
    out = [w]
    for c in w.winfo_children():
        out += all_widgets(c)
    return out


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        from soe2 import style
        style.apply_look()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        CD.reset({})
        for target, repl in ((CD, ("save", lambda: True)), (calendar_page, ("save_json", lambda *a: True))):
            p = mock.patch.object(target, *repl)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(CD.reset)
        self.day = dt.date.today() + dt.timedelta(days=3)
        CD.set_board([{"id": "b1", "kind": "league", "name": "Start", "start": CD.at(self.day, 20), "end": 0,
                       "link": "https://example.com/x"}])

        class H(calendar_page.CalendarPage):
            undone = []

            def undo_button(self, parent, key, **pack):
                return ttk.Button(parent, text="Undo")

            def list_register(self, key, tree, delete=None, multi=True):
                self.reg = (key, delete)

            def push_undo(self, key, label, restore):
                self.undone.append((key, label, restore))

            def dlg_parent(self):
                return self.root
        self.h = H()
        self.h.root = self.root
        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True)
        self.addCleanup(self.body.destroy)
        with mock.patch.object(self.root, "after", lambda *a, **k: None):
            self.h.build_calendar(self.body)
        self.h.cal_day = self.day
        self.h.cal_ym = (self.day.year, self.day.month)
        self.h.cal_refresh()
        self.root.update()

    def buttons(self, frame=None):
        return {str(b.cget("text")): b for b in all_widgets(frame or self.body) if isinstance(b, ttk.Button)}

    def test_search_is_first_and_one_orange_button(self):
        bar = self.body.winfo_children()[0]
        kids = [w for w in bar.winfo_children() if w.winfo_manager()]
        entries = [w for w in kids if isinstance(w, ttk.Entry)]
        self.assertTrue(entries and kids.index(entries[0]) <= 1, "search box first, after its magnifier")
        orange = [str(b.cget("text")) for b in all_widgets(self.body)
                  if isinstance(b, ttk.Button) and str(b.cget("style")) == "Primary.TButton"]
        self.assertEqual(orange, ["Add Reminder"])

    def test_every_kind_filter_says_a_mark_a_tick_and_a_word(self):
        for kind, lab in self.h.cal_kind_lbls.items():
            self.assertEqual(lab.cget("text"), f"✓ {CD.mark(kind)} {CD.FILTER_WORDS[kind]}")
        self.h.cal_kind_flip("league")
        self.assertTrue(self.h.cal_kind_lbls["league"].cget("text").startswith("– "), "hidden is said, not only dimmed")
        self.assertEqual(self.h.cal_events(), [])
        self.h.cal_kind_flip("league")

    def test_buttons_that_cannot_work_are_grey(self):
        b = self.buttons(self.h.cal_day_box)
        self.assertTrue(b["Delete"].instate(["disabled"]), "a board event is not yours to delete")
        self.assertFalse(b["Open Link"].instate(["disabled"]))
        self.assertFalse(b["Change Reminder"].instate(["disabled"]))
        mine = CD.add_mine("Sell", CD.at(self.day, 9))
        self.h.cal_pick = mine["id"]
        self.h.cal_refresh()
        b = self.buttons(self.h.cal_day_box)
        self.assertFalse(b["Delete"].instate(["disabled"]))
        self.assertTrue(b["Open Link"].instate(["disabled"]), "no link, so nothing to open")

    def test_a_day_with_nothing_says_so_with_one_button(self):
        self.h.cal_day = self.day + dt.timedelta(days=40)
        self.h.cal_refresh()
        self.assertTrue(self.h.cal_empty.winfo_manager())
        self.assertIn("Nothing on this day", self.h.cal_empty.cget("text"))
        self.assertEqual(self.buttons(self.h.cal_day_box), {})

    def test_delete_is_only_for_mine_and_can_be_undone(self):
        self.h.cal_delete()
        self.assertEqual(len(CD.events()), 1, "a board event stays")
        mine = CD.add_mine("Sell", CD.at(self.day, 9))
        self.h.cal_pick = mine["id"]
        self.h.cal_delete()
        self.assertEqual([e["id"] for e in CD.events()], ["b1"])
        self.h.undone[-1][2]()
        self.assertEqual(len(CD.events()), 2)

    def test_the_month_grid_draws_each_event_with_its_mark(self):
        self.h.cal_grid.config(width=700, height=500)
        self.root.update()
        self.h.cal_draw()
        texts = [self.h.cal_grid.itemcget(i, "text") for i in self.h.cal_grid.find_all()
                 if self.h.cal_grid.type(i) == "text"]
        self.assertTrue(any(t.startswith("◆ League") for t in texts), texts)
        self.assertEqual(len(self.h.cal_cells) % 7, 0)
        self.assertTrue(any(str(self.day.day) == t.split(" ")[0] for t in texts))

    def test_remind_me_sets_then_clears(self):
        self.h.cal_remind_me("b1")
        self.assertEqual(CD.reminders({"id": "b1"}), [86400, 0])
        self.h.cal_remind_me("b1")
        self.assertEqual(CD.reminders({"id": "b1"}), [])

    def test_a_due_reminder_shows_one_alert_card(self):
        CD.set_reminders("b1", [0])
        shown = []
        with mock.patch("soe2.alertcard.show", lambda *a, **k: shown.append((a[1], a[2], k.get("mark")))), \
                mock.patch("soe2.alerts_page.game_rect", lambda *a, **k: None):
            self.h.cal_fire(CD.at(self.day, 20) + 5)
            self.h.cal_fire(CD.at(self.day, 20) + 30)
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0][0], "◆ League: Start")
        self.assertEqual(shown[0][2], "◆")

    def test_no_parenthesis_in_what_the_page_says(self):
        for w in all_widgets(self.body):
            try:
                t = str(w.cget("text"))
            except tk.TclError:
                continue
            self.assertNotIn("(", t, t)


if __name__ == "__main__":
    unittest.main()
