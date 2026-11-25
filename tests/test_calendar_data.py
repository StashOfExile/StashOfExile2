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
        p = mock.patch.object(CD, "save", lambda: True)
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
