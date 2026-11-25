"""3.3.0 owner: Calendar - the data and the sums (soe2/calendar_data.py)."""
import datetime as dt
import unittest
from unittest import mock

from soe2 import calendar_data as CD


def ts(y, m, d, h=0, mi=0):
    return dt.datetime(y, m, d, h, mi).timestamp()


NOW = ts(2026, 12, 2, 12, 0)


class Base(unittest.TestCase):
    def setUp(self):
        CD.reset({})
        for name, fn in (("save", lambda: True), ("h24", lambda: True)):
            p = mock.patch.object(CD, name, fn)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(CD.reset)


class Kinds(Base):
    def test_every_kind_has_a_mark_and_a_word(self):
        marks = [CD.mark(k) for k in CD.ORDER]
        self.assertEqual(len(set(marks)), len(marks), "no two kinds share a mark")
        for k in CD.ORDER:
            self.assertTrue(CD.word(k))
            self.assertIn(k, CD.FILTER_WORDS)
        self.assertEqual(CD.label({"kind": "league"}), "◆ League")


class Mine(Base):
    def test_add_keep_and_remove(self):
        ev = CD.add_mine("  Sell   tablets ", ts(2026, 12, 8, 20), leads=(0, 86400))
        self.assertEqual(ev["name"], "Sell tablets")
        self.assertEqual(CD.reminders(ev), [86400, 0])
        self.assertEqual([e["by"] for e in CD.events()], ["Me"])
        gone = CD.remove_mine(ev["id"])
        self.assertEqual(CD.events(), [])
        CD.restore_mine(gone)
        self.assertEqual(CD.reminders(CD.events()[0]), [86400, 0], "Undo brings its reminders back")

    def test_what_is_refused(self):
        self.assertEqual(CD.add_mine("   ", NOW), "It needs a name.")
        self.assertEqual(CD.add_mine("x", NOW, end=NOW - 5), "It ends before it starts.")
        with mock.patch("soe2.cleantext.problem", lambda t: "bad"):
            self.assertEqual(CD.add_mine("anything", NOW), "That name is not allowed.")
        self.assertEqual(CD.events(), [])

    def test_a_long_name_is_cut(self):
        self.assertEqual(len(CD.add_mine("a" * 200, NOW)["name"]), CD.NAME_MAX)


class Board(Base):
    def test_board_events_replace_and_never_claim_mine(self):
        CD.set_board([{"id": "b1", "kind": "league", "name": "Start", "start": ts(2026, 12, 11, 20)},
                      {"id": "b2", "kind": "mine", "name": "sneaky", "start": NOW},
                      {"id": "b3", "kind": "nonsense", "name": "x", "start": NOW},
                      {"kind": "race", "name": "no id", "start": NOW}, "junk"])
        self.assertEqual([e["id"] for e in CD.events()], ["b1"])
        self.assertEqual(CD.events()[0]["by"], "Official")
        CD.set_reminders("b1", [0])
        CD.set_board([])
        self.assertEqual(CD.state()["remind"], {}, "a reminder for an event that is gone goes too")


class FromTheBoard(Base):
    ROW = {"id": "b7", "kind": "drops", "name": " Launch   drops ", "start": 1795000000, "end": 1795600000,
           "link": "https://example.com/a", "note": "n", "by": "someone"}

    def test_a_download_is_cleaned_before_it_is_kept(self):
        rows = CD.clean_board_rows([self.ROW])
        self.assertEqual(rows, [{"id": "b7", "kind": "drops", "name": "Launch drops", "start": 1795000000.0,
                                 "end": 1795600000.0, "link": "https://example.com/a", "note": "n", "by": "Official"}])

    def test_what_is_dropped(self):
        bad = [dict(self.ROW, id="m1"), dict(self.ROW, id=7), dict(self.ROW, id="b" + "1" * 30),
               dict(self.ROW, kind="mine"), dict(self.ROW, kind="x"), dict(self.ROW, name=5), dict(self.ROW, name="  "),
               dict(self.ROW, start="soon"), dict(self.ROW, start=True), dict(self.ROW, start=-5), "junk", None, [1]]
        self.assertEqual(CD.clean_board_rows(bad), [])
        self.assertEqual(CD.clean_board_rows("not a list"), [])
        self.assertEqual(CD.clean_board_rows({"a": 1}), [])
        with mock.patch("soe2.cleantext.problem", lambda t: "bad" if "nasty" in str(t) else None):
            self.assertEqual(CD.clean_board_rows([dict(self.ROW, name="nasty thing")]), [])
            self.assertEqual(CD.clean_board_rows([dict(self.ROW, note="nasty")])[0]["note"], "")

    def test_a_bad_link_or_end_is_blanked_not_trusted(self):
        for link in ("http://example.com", "javascript:alert(1)", "https://x.com/ y", "https://x.com/" + "a" * 400, 5):
            got = CD.clean_board_rows([dict(self.ROW, link=link)])
            self.assertEqual([r["link"] for r in got], [""] if isinstance(link, str) else [], link)
        self.assertEqual(CD.clean_board_rows([dict(self.ROW, end=5)])[0]["end"], 0)
        self.assertEqual(len(CD.clean_board_rows([dict(self.ROW, id=f"b{i}") for i in range(500)])), CD.BOARD_MAX)

    def test_pull_reads_events_and_saves_nothing(self):
        with mock.patch("soe2.board.configured", lambda: True):
            self.assertEqual(CD.pull(lambda m, p: (True, {"events": [self.ROW]}))[0]["id"], "b7")
            self.assertIsNone(CD.pull(lambda m, p: (False, "down")))
            self.assertIsNone(CD.pull(lambda m, p: (True, ["odd"])))
            asked = []
            CD.pull(lambda m, p: (asked.append((m, p)), (True, {}))[1])
            self.assertEqual(asked, [("GET", "/events")])
        with mock.patch("soe2.board.configured", lambda: False):
            self.assertIsNone(CD.pull(lambda m, p: self.fail("no board, no call")))
        self.assertEqual(CD.events(), [])

    def test_reading_events_never_sends_the_board_key(self):
        from soe2 import board as B
        seen = []

        class R:
            status_code = 200

            def json(self):
                return {"events": []}

        def get(method, url, **kw):
            seen.append((method, url.rsplit("/", 1)[-1], "Authorization" in kw["headers"]))
            return R()
        with mock.patch.object(B, "configured", lambda: True), mock.patch.object(B, "url", lambda: "https://b"), \
                mock.patch.object(B, "session", lambda: {"token": "secret"}):
            B.call("GET", "/events", get=get)
            B.call("POST", "/events", body={}, get=get)
        self.assertEqual(seen, [("GET", "events", False), ("POST", "events", True)])

    def test_what_an_admin_sends(self):
        ok = CD.event_body("league", "  League  start ", 100.7, 0, " https://example.com/x ", " hi ")
        self.assertEqual(ok, {"kind": "league", "name": "League start", "start": 100, "end": 0,
                              "link": "https://example.com/x", "note": "hi"})
        self.assertEqual(CD.event_body("mine", "x", 1), "Pick what kind of event it is.")
        self.assertEqual(CD.event_body(None, "x", 1), "Pick what kind of event it is.")
        self.assertEqual(CD.event_body("race", " ", 1), "It needs a name.")
        self.assertIn("over 60", CD.event_body("race", "x" * 61, 1))
        self.assertEqual(CD.event_body("race", "x", 10, 5), "It ends before it starts.")
        self.assertEqual(CD.event_body("race", "x", 10, 0, "http://a.b"), "The link must start with https://")
        self.assertEqual(CD.board_number({"id": "b12"}), 12)
        self.assertEqual(CD.board_number({"id": "m3"}), 0)

    def test_the_board_s_own_tests_pass(self):
        import os
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("needs node")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = subprocess.run(["node", os.path.join(root, "board", "test", "events.test.mjs")], capture_output=True,
                           text=True, timeout=120)
        self.assertIn("events: ok", r.stdout, r.stderr[-800:])


class Days(Base):
    def test_month_grid_is_monday_first_and_whole_weeks(self):
        w = CD.weeks(2026, 12)
        self.assertTrue(all(len(r) == 7 for r in w))
        self.assertEqual(w[0][0], dt.date(2026, 11, 30))
        self.assertEqual(w[0][1], dt.date(2026, 12, 1))
        self.assertEqual(CD.month_name(2026, 12), "December 2026")
        self.assertEqual(CD.step_month(2026, 12, 1), (2027, 1))
        self.assertEqual(CD.step_month(2026, 1, -1), (2025, 12))

    def test_an_event_shows_on_every_day_it_runs(self):
        e = {"id": 1, "kind": "drops", "name": "d", "start": ts(2026, 12, 4, 20), "end": ts(2026, 12, 6, 9)}
        for d in (4, 5, 6):
            self.assertEqual(CD.on_day([e], dt.date(2026, 12, d)), [e])
        self.assertEqual(CD.on_day([e], dt.date(2026, 12, 7)), [])
        one = {"id": 2, "kind": "league", "name": "l", "start": ts(2026, 12, 11, 20), "end": 0}
        self.assertEqual(CD.span(one), (dt.date(2026, 12, 11), dt.date(2026, 12, 11)))

    def test_words(self):
        self.assertEqual(CD.day_words(dt.date(2026, 12, 11)), "Fri 11 Dec")
        self.assertEqual(CD.away(ts(2026, 12, 11, 20), NOW), "in 9 days")
        self.assertEqual(CD.away(ts(2026, 12, 3, 1), NOW), "tomorrow")
        self.assertEqual(CD.away(ts(2026, 12, 2, 15), NOW), "in 3 hours")
        self.assertEqual(CD.away(ts(2026, 12, 2, 12, 20), NOW), "in 20 min")
        self.assertEqual(CD.away(NOW - 60, NOW), "now")
        e = {"id": 1, "kind": "league", "name": "l", "start": ts(2026, 12, 11, 20), "end": 0}
        self.assertEqual(CD.when_line(e, NOW), "in 9 days · Fri 11 Dec")
        self.assertEqual(CD.starts_line(e, NOW), "Fri 11 Dec, 20:00 · in 9 days")
        self.assertEqual(CD.ends_line(e), "Not set")
        run = dict(e, start=NOW - 3600, end=ts(2026, 12, 18, 9))
        self.assertEqual(CD.when_line(run, NOW), "Live · ends Fri 18 Dec")

    def test_times_follow_the_app_clock(self):
        t = ts(2026, 12, 11, 20, 30)
        self.assertEqual(CD.clock(t), "20:30")
        self.assertEqual(CD.clock_hint(), "Like 20:00.")
        with mock.patch.object(CD, "h24", lambda: False):
            self.assertEqual(CD.clock(t), "8:30 PM")
            self.assertEqual(CD.clock(ts(2026, 12, 11, 0, 5)), "12:05 AM")
            self.assertEqual(CD.parse_clock(CD.clock(t)), (20, 30), "what the box shows can be read back")
            self.assertIn("8pm", CD.clock_hint())
            e = {"id": 1, "kind": "league", "name": "l", "start": ts(2026, 12, 11, 20), "end": 0}
            self.assertEqual(CD.starts_line(e, NOW), "Fri 11 Dec, 8:00 PM · in 9 days")

    def test_the_time_pickers_round_trip(self):
        hours, mins, halves = CD.clock_choices()
        self.assertEqual((len(hours), mins[:3], halves), (24, ["00", "05", "10"], []))
        self.assertEqual(CD.clock_parts(20, 5), ("20", "05", ""))
        self.assertEqual(CD.clock_from_parts("20", "05"), (20, 5))
        with mock.patch.object(CD, "h24", lambda: False):
            hours, mins, halves = CD.clock_choices()
            self.assertEqual((hours[0], len(hours), halves), ("12", 12, ["AM", "PM"]))
            for h in range(24):
                for m in (0, 35):
                    self.assertEqual(CD.clock_from_parts(*CD.clock_parts(h, m)), (h, m))
            self.assertEqual(CD.clock_parts(0, 0), ("12", "00", "AM"))
            self.assertEqual(CD.clock_parts(12, 0), ("12", "00", "PM"))
        for bad in (("x", "00", ""), ("25", "00", ""), ("13", "00", "PM"), ("8", "75", "AM"), ("", "", "")):
            self.assertIsNone(CD.clock_from_parts(*bad), bad)

    def test_clock(self):
        for text, want in (("20:00", (20, 0)), ("8pm", (20, 0)), ("2030", (20, 30)), ("9", (9, 0)), ("12am", (0, 0)),
                           ("12pm", (12, 0)), ("7.15", (7, 15))):
            self.assertEqual(CD.parse_clock(text), want, text)
        for text in ("", "25:00", "8:99", "13pm", "soon"):
            self.assertIsNone(CD.parse_clock(text), text)


class Upcoming(Base):
    def test_next_three_skips_what_is_over_and_keeps_what_is_live(self):
        evs = [{"id": i, "kind": "event", "name": str(i), "start": s, "end": e} for i, (s, e) in enumerate((
            (NOW - 5 * CD.DAY, NOW - 4 * CD.DAY), (NOW - 3600, NOW + 3600), (NOW + CD.DAY, 0), (NOW + 2 * CD.DAY, 0),
            (NOW + 3 * CD.DAY, 0)))]
        self.assertEqual([e["id"] for e in CD.upcoming(evs, NOW)], [1, 2, 3])
        self.assertEqual([e["id"] for e in CD.upcoming(evs, NOW, kinds={"race"})], [])

    def test_search_and_kinds(self):
        evs = [{"id": 1, "kind": "drops", "name": "Launch campaign", "start": NOW},
               {"id": 2, "kind": "race", "name": "Launch race", "start": NOW}]
        self.assertEqual([e["id"] for e in CD.shown(evs, "launch")], [1, 2])
        self.assertEqual([e["id"] for e in CD.shown(evs, "twitch")], [1], "the kind's word is searched too")
        self.assertEqual([e["id"] for e in CD.shown(evs, "", {"race"})], [2])


class OverlayLine(Base):
    def ev(self, start, end=0, kind="league", name="1.0 Release"):
        return {"id": "b1", "kind": kind, "name": name, "start": start, "end": end}

    def test_it_shows_from_a_week_before_until_it_is_over(self):
        self.assertEqual(CD.overlay_text(NOW, [self.ev(NOW + 9 * CD.DAY)]), "", "too far off")
        self.assertEqual(CD.overlay_text(NOW, [self.ev(ts(2026, 12, 5, 20))]), "◆ League: 1.0 Release · in 3 days")
        self.assertEqual(CD.overlay_text(NOW, [self.ev(NOW + 1800)]), "◆ League: 1.0 Release · in 30 min")
        run = self.ev(NOW - 3600, ts(2026, 12, 9, 9), "drops", "Launch drops")
        self.assertEqual(CD.overlay_text(NOW, [run]), "▶ Twitch Drops: Launch drops · live, ends Wed 9 Dec")
        self.assertEqual(CD.overlay_text(NOW, [self.ev(NOW - 5 * CD.DAY)]), "", "over")
        self.assertEqual(CD.overlay_text(NOW, []), "")

    def test_the_nearest_one_wins(self):
        evs = sorted([self.ev(NOW + 2 * CD.DAY, name="Later"), self.ev(NOW + 3600, name="Sooner")], key=lambda e: e["start"])
        self.assertIn("Sooner", CD.overlay_text(NOW, evs))


class Reminders(Base):
    def test_said_once_at_its_moment(self):
        ev = CD.add_mine("Sell", NOW + 3600, leads=(0, 3600))
        self.assertEqual(CD.due(NOW - 10), [])
        got = CD.due(NOW + 5)
        self.assertEqual([(e["id"], lead) for e, lead in got], [(ev["id"], 3600)])
        self.assertEqual(CD.due(NOW + 60), [], "not twice")
        self.assertEqual([lead for _e, lead in CD.due(NOW + 3601)], [0])
        title, line = CD.remind_words(CD.events()[0], 3600, NOW)
        self.assertEqual(title, "● Mine: Sell")
        self.assertIn("in 1 hour", line)

    def test_old_news_is_dropped(self):
        CD.add_mine("Old", NOW - 3 * CD.DAY, leads=(0,))
        self.assertEqual(CD.due(NOW), [])
        self.assertEqual(CD.due(NOW + 1), [])

    def test_the_line_on_the_page(self):
        ev = CD.add_mine("Sell", NOW + 9 * CD.DAY, leads=(0, 86400))
        self.assertEqual(CD.remind_line(ev), "✓ 1 day before, and at the start")
        CD.set_reminders(ev["id"], [])
        self.assertEqual(CD.remind_line(ev), "– None")


if __name__ == "__main__":
    unittest.main()
