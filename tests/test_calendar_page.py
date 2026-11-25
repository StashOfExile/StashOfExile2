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

            def share_is_admin(self):
                return self.admin

            def run_bg(self, work, done):
                return done(work())
        H.admin = getattr(self, "ADMIN", False)
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

    def test_right_click_on_a_day_offers_add_reminder_first(self):
        self.h.cal_grid.config(width=700, height=500)
        self.root.update()
        self.h.cal_draw()
        x0, y0, x1, y1, day = next(c for c in self.h.cal_cells if c[4] == self.day)

        class E:
            x, y, x_root, y_root = (x0 + x1) / 2, (y0 + y1) / 2, 0, 0
        with mock.patch("tkinter.Menu.tk_popup", lambda *a, **k: None):
            self.h.cal_day = None
            self.h.cal_grid_menu(E)
        self.assertEqual(self.h.cal_day, self.day, "the day under the mouse is picked")
        m = self.h.cal_day_menu
        labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1) if m.type(i) == "command"]
        self.assertEqual(labels, ["Add Reminder…", "Change Reminder…", "Open Link", "Delete"])
        self.assertEqual(str(m.entrycget(labels.index("Delete") + 2, "state")), "disabled", "a board event")

    def test_the_month_waits_for_its_real_size(self):
        """3.3.0 owner: the first open drew one tiny square. No size yet means nothing is drawn, and it tries again."""
        again = []
        self.h.cal_grid.config(width=1, height=1)
        self.h.cal_grid.pack_propagate(False)
        with mock.patch.object(self.h.cal_grid, "winfo_width", lambda: 1), \
                mock.patch.object(self.h, "cal_draw_soon", lambda tries=0: again.append(tries)):
            self.h.cal_draw()
        self.assertEqual(self.h.cal_cells, [], "no squashed grid")
        self.assertEqual(self.h.cal_grid.find_all(), ())
        self.assertEqual(again, [1], "it draws again once it has a size")
        with mock.patch.object(self.h.cal_grid, "winfo_width", lambda: 1), \
                mock.patch.object(self.h, "cal_draw_soon", lambda tries=0: again.append(tries)):
            self.h.cal_draw(tries=40)
        self.assertEqual(again, [1], "and gives up quietly, never a loop")

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


class AdminPage(Page):
    ADMIN = True

    def test_buttons_that_cannot_work_are_grey(self):
        b = self.buttons(self.h.cal_day_box)
        self.assertFalse(b["Edit Event"].instate(["disabled"]))
        self.assertFalse(b["Delete Event"].instate(["disabled"]))
        mine = CD.add_mine("Sell", CD.at(self.day, 9))
        self.h.cal_pick = mine["id"]
        self.h.cal_refresh()
        b = self.buttons(self.h.cal_day_box)
        self.assertTrue(b["Edit Event"].instate(["disabled"]), "yours is not a board event")
        self.assertTrue(b["Delete Event"].instate(["disabled"]))

    def test_right_click_on_a_day_offers_add_reminder_first(self):
        self.h.cal_grid.config(width=700, height=500)
        self.root.update()
        self.h.cal_draw()
        x0, y0, x1, y1, _d = next(c for c in self.h.cal_cells if c[4] == self.day)

        class E:
            x, y, x_root, y_root = (x0 + x1) / 2, (y0 + y1) / 2, 0, 0
        with mock.patch("tkinter.Menu.tk_popup", lambda *a, **k: None):
            self.h.cal_grid_menu(E)
        m = self.h.cal_day_menu
        labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1) if m.type(i) == "command"]
        self.assertEqual(labels[0], "Add Reminder…")
        self.assertEqual(labels[-3:], ["Admin: Post Event…", "Admin: Edit Event…", "Admin: Delete Event"])

    def test_post_event_is_there_and_still_one_orange_button(self):
        self.assertTrue(self.h.cal_post_btn.winfo_manager())
        self.assertNotEqual(str(self.h.cal_post_btn.cget("style")), "Primary.TButton")

    def test_posting_sends_one_checked_event_and_reads_the_list_again(self):
        sent, pulls = [], []
        new = {"id": "b9", "kind": "race", "name": "Launch race", "start": CD.at(self.day, 20), "end": 0}
        with mock.patch("soe2.board.event_save", lambda body, eid=None: (sent.append((body, eid)), (True, {}))[1]), \
                mock.patch.object(CD, "pull", lambda call=None: (pulls.append(1), CD.clean_board_rows([new]))[1]), \
                mock.patch.object(CD, "h24", lambda: True):
            dlg = self.h.cal_post()
            v = dlg.cal_vars
            dlg.cal_save()
            self.assertEqual(v["msg"].cget("text"), "Pick what kind of event it is.")
            self.assertEqual(sent, [], "nothing is sent until it is right")
            v["kind"].set("⚑ Race")
            v["name"].set("Launch race")
            v["link"].set("http://not-secure.example")
            dlg.cal_save()
            self.assertEqual(v["msg"].cget("text"), "The link must start with https://")
            v["link"].set("")
            v["sclock"].set("nonsense")
            dlg.cal_save()
            self.assertIn("not clear", v["msg"].cget("text"))
            v["sclock"].set("20:00")
            dlg.cal_save()
        self.assertEqual(sent, [({"kind": "race", "name": "Launch race", "start": int(CD.at(self.day, 20)), "end": 0,
                                  "link": "", "note": ""}, None)])
        self.assertFalse(dlg.winfo_exists(), "the box closes once the board said yes")
        self.assertEqual(pulls, [1])
        self.assertEqual([e["id"] for e in CD.events()], ["b9"], "the Calendar shows what the board now has")

    def test_the_board_s_no_is_shown_in_the_box(self):
        with mock.patch("soe2.board.event_save", lambda body, eid=None: (False, "admins only")), \
                mock.patch.object(CD, "h24", lambda: True):
            dlg = self.h.cal_post()
            dlg.cal_vars["kind"].set("◆ League")
            dlg.cal_vars["name"].set("x")
            dlg.cal_save()
            self.assertEqual(dlg.cal_vars["msg"].cget("text"), "admins only")
            self.assertTrue(dlg.winfo_exists())
        for said in ("The board answered 404.", "not found"):   # the live board's own words, from the owner's test
            with mock.patch("soe2.board.event_save", lambda body, eid=None, s=said: (False, s)):
                dlg.cal_vars["msg"].config(text="")
                dlg.cal_save()
                self.assertIn("does not have the Calendar yet", dlg.cal_vars["msg"].cget("text"), said)
        dlg.destroy()

    def test_edit_sends_the_board_number_and_delete_asks_first(self):
        sent, gone = [], []
        with mock.patch("soe2.board.event_save", lambda body, eid=None: (sent.append(eid), (True, {}))[1]), \
                mock.patch("soe2.board.event_delete", lambda eid: (gone.append(eid), (True, {}))[1]), \
                mock.patch.object(CD, "pull", lambda call=None: None), mock.patch.object(CD, "h24", lambda: True):
            CD.set_board([{"id": "b4", "kind": "league", "name": "Start", "start": CD.at(self.day, 20), "end": 0}])
            self.h.cal_pick = None
            self.h.cal_refresh()
            self.h.cal_edit_event()
            box = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
            self.assertEqual(box.cal_vars["name"].get(), "Start")
            box.cal_save()
            self.assertEqual(sent, [4])
            with mock.patch("tkinter.messagebox.askyesno", lambda *a, **k: False):
                self.assertFalse(self.h.cal_delete_event())
            self.assertEqual(gone, [])
            with mock.patch("tkinter.messagebox.askyesno", lambda *a, **k: True):
                self.assertTrue(self.h.cal_delete_event())
            self.assertEqual(gone, [4])


    def test_drafts_review_makes_it_live_and_dismiss_drops_it(self):
        drafts = [{"id": "b20", "kind": "drops", "name": "Covens Twitch Drops", "start": CD.at(self.day, 12), "end": 0,
                   "link": "https://store.steampowered.com/news/app/238960", "note": "Drafted from Steam news."},
                  {"id": "b21", "kind": "league", "name": "Play on December 11", "start": CD.at(self.day, 12), "end": 0}]
        saved, gone, checks = [], [], []

        def save(body, eid=None):
            saved.append((body["name"], eid))
            drafts[:] = [d for d in drafts if d["id"] != f"b{eid}"]
            return True, {}

        def delete(eid):
            gone.append(eid)
            drafts[:] = [d for d in drafts if d["id"] != f"b{eid}"]
            return True, {}
        with mock.patch("soe2.board.event_drafts", lambda: (True, {"events": list(drafts)})), \
                mock.patch("soe2.board.event_save", save), mock.patch("soe2.board.event_delete", delete), \
                mock.patch("soe2.board.event_check", lambda: (checks.append(1), (True, {"added": 0}))[1]), \
                mock.patch.object(CD, "pull", lambda call=None: None), mock.patch.object(CD, "h24", lambda: True):
            dlg = self.h.cal_drafts()
            p = dlg.cal_parts
            self.assertEqual(list(p["tv"].get_children()), ["b20", "b21"])
            self.assertTrue(p["review"].instate(["disabled"]) and p["dismiss"].instate(["disabled"]),
                            "grey until a draft is picked")
            self.assertEqual(str(p["review"].cget("style")), "Primary.TButton")
            p["tv"].selection_set("b20")
            self.root.update()
            self.assertFalse(p["review"].instate(["disabled"]))
            before = set(self.root.winfo_children())
            p["do_review"]()
            box = next(w for w in self.root.winfo_children() if w not in before)
            self.assertEqual(box.title(), "Review Draft")
            self.assertEqual(box.cal_vars["name"].get(), "Covens Twitch Drops")
            self.assertEqual(box.cal_vars["kind"].get(), "▶ Twitch Drops")
            box.cal_save()
            self.assertEqual(saved, [("Covens Twitch Drops", 20)], "saving a draft is what posts it")
            self.assertEqual(list(p["tv"].get_children()), ["b21"], "the list is read again")
            p["tv"].selection_set("b21")
            p["do_dismiss"]()
            self.assertEqual(gone, [21])
            self.assertEqual(list(p["tv"].get_children()), [])
            self.assertIn("No drafts", p["msg"].cget("text"))
            p["check"]()
            self.assertEqual(checks, [1])
            self.assertIn("Checked Steam: 0 new", p["msg"].cget("text"))
            dlg.destroy()
        with mock.patch("soe2.board.event_drafts", lambda: (False, "not found")):
            dlg = self.h.cal_drafts()
            self.assertIn("does not have the Calendar yet", dlg.cal_parts["msg"].cget("text"))
            dlg.destroy()


    def test_waiting_drafts_are_said_in_words_on_the_button(self):
        self.assertEqual(self.h.cal_drafts_btn.cget("text"), "Drafts")
        with mock.patch("soe2.board.event_drafts", lambda: (True, {"events": [
                {"id": "b30", "kind": "drops", "name": "A", "start": 5}, {"id": "b31", "kind": "league", "name": "B", "start": 5}]})):
            self.h.cal_drafts_pull()
        self.assertEqual(self.h.cal_drafts_count(), 2)
        self.assertEqual(self.h.cal_drafts_btn.cget("text"), "● Drafts: 2 to review", "a mark and words, not a color")
        self.assertNotEqual(str(self.h.cal_drafts_btn.cget("style")), "Primary.TButton", "still one orange button")
        with mock.patch("soe2.board.event_drafts", lambda: (False, "down")):
            self.h.cal_drafts_pull()
        self.assertEqual(self.h.cal_drafts_count(), 2, "a board that does not answer changes nothing")
        self.h.cal_drafts_set(0)
        self.assertEqual(self.h.cal_drafts_btn.cget("text"), "Drafts")


class NotAdmin(Page):
    def test_no_admin_parts_for_everyone_else(self):
        self.assertFalse(self.h.cal_post_btn.winfo_manager())
        self.assertNotIn("Edit Event", self.buttons(self.h.cal_day_box))
        self.assertIsNone(self.h.cal_post())
        self.assertIsNone(self.h.cal_drafts())
        self.assertFalse(self.h.cal_drafts_btn.winfo_manager())
        with mock.patch("soe2.board.event_drafts", lambda: self.fail("only an admin asks the board for drafts")):
            self.h.cal_drafts_pull()
        self.h.cal_drafts_n = 5
        self.assertEqual(self.h.cal_drafts_count(), 0)
        self.assertIsNone(self.h.cal_delete_event())
        self.assertFalse(any(a and str(a[0]).startswith("Admin") for a in self.h.cal_menu_actions()))


if __name__ == "__main__":
    unittest.main()
