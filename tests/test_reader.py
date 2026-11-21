"""3.0.6: soe2/reader.py - the one reader every screen-reading helper calls: lines read on their own, matching a closed
list (by letters, letter shapes and cut-short lines; never a guess between two) and the picture memory. Only drawn
pictures and misread game text (the OCR's output for lines of the game) are used; the OCR is a stand-in, so this runs
without Tesseract.

    python3.12 -m unittest tests.test_reader          (or tests/runall.sh)"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from soe2 import medallions as M, reader as R, rumours as RU, temple as TM, vaallens as V  # noqa: E402

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "soe2", "fonts", "cinzel-400.ttf")


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def line_pic(text, size=28, ink=(30, 25, 20), paper=(215, 205, 180), pad=(14, 8), width=None):
    f = font(size)
    w = width or int(f.getlength(text)) + pad[0] * 2
    img = Image.new("RGB", (w, size + pad[1] * 2), paper)
    ImageDraw.Draw(img).text((pad[0], pad[1] - 2), text, fill=ink, font=f)
    return img


def elsewhere(img, k=0.8, left=30, width=None):
    """The same line in another picture: the game window another size (the line scaled), on a wider row."""
    small = img.resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
    out = Image.new("RGB", (width or small.width + left + 20, small.height + 6), img.getpixel((1, 1)))
    out.paste(small, (left, 3))
    return out


class Mem(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="soe2-reader-")
        R.Memory.DIR[0] = self.dir
        R._MEMS.clear()

    def tearDown(self):
        R.Memory.DIR[0] = None
        R._MEMS.clear()
        shutil.rmtree(self.dir, ignore_errors=True)


class Prep(unittest.TestCase):
    def test_light_text_on_dark_becomes_dark_on_light(self):
        img = line_pic("36/60", ink=(235, 230, 220), paper=(20, 18, 15))
        for how in ("gray", "white-text", "bright", "otsu"):
            g, k = R.prep(img, how, 2)
            self.assertEqual(g.size, (img.width * 2, img.height * 2), how)
            hist = g.convert("L").histogram()
            light = sum(hist[128:])
            self.assertGreater(light, sum(hist[:128]), how)           # (mostly white backing)

    def test_dark_ink_on_parchment(self):
        g, _k = R.prep(line_pic("Cold as ice..."), "dark-text", 2)
        self.assertEqual(set(g.convert("L").get_flattened_data()) - {0, 255}, set())
        self.assertIn(0, set(g.get_flattened_data()))

    def test_never_bigger_than_the_engine_takes(self):
        g, k = R.prep(Image.new("RGB", (2000, 40)), "gray", 3)
        self.assertLessEqual(max(g.size), R.MAX_SIDE)
        self.assertLess(k, 3)


class ReadLines(unittest.TestCase):
    def test_each_line_read_on_its_own_boxes_in_the_pictures_pixels(self):
        pic = Image.new("RGB", (400, 300), (10, 10, 10))
        seen = []

        def ocr(img):
            seen.append(img.size)
            return [("WORD", (10, 4, 50, 20))]
        got = R.read_lines(pic, lines=[(100, 50, 200, 80), (100, 120, 200, 150)], kind="medallion-title", ocr=ocr)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0][0], "WORD")
        k = seen[0][1] / 30.0                                 # (enlarged)
        self.assertGreaterEqual(k, 2)
        self.assertEqual(got[0][1][:2], (100 + int(10 / k), 50 + int(4 / k)))
        self.assertTrue(120 <= got[1][1][1] < 150)

    def test_whole_box_read_once(self):
        pic = Image.new("RGB", (400, 300))
        calls = []

        def ocr(img):
            calls.append(img.size)
            return [("A LINE", (0, 0, 40, 20)), ("", (0, 30, 5, 40)), ("ANOTHER", (0, 40, 80, 60))]
        got = R.read_lines(pic, (100, 100, 300, 200), ocr=ocr)
        self.assertEqual(len(calls), 1)
        self.assertEqual([t for t, _b in got], ["A LINE", "ANOTHER"])
        self.assertEqual(got[0][1][:2], (100, 100))

    def test_ways_tried_until_the_text_is_wanted(self):
        pic = Image.new("RGB", (200, 50), (20, 20, 20))
        texts = iter([".LAST MAP'S PROFIT", "“LR 36/60", "never asked"])
        t, _b, how = R.read_one(pic, (0, 0, 200, 50), kind="console", want=lambda s: TM.parse_console([(s, None)]),
                                ocr=lambda img: [(next(texts), (0, 0, 10, 10))])
        self.assertEqual(t, "“LR 36/60")
        self.assertEqual(how, R.KINDS["console"][1][0])
        self.assertEqual(TM.parse_console([(t, None)]), (36, 60))

    def test_nothing_wanted_gives_the_first_text(self):
        texts = iter(["first", "second", "third"])
        t, _b, how = R.read_one(Image.new("RGB", (80, 30)), (0, 0, 80, 30), kind="console", want=lambda s: False,
                                ocr=lambda img: [(next(texts), (0, 0, 5, 5))])
        self.assertEqual(t, "first")

    def test_an_empty_box_reads_nothing(self):
        self.assertEqual(R.read_one(Image.new("RGB", (50, 50)), (60, 60, 90, 90), ocr=lambda i: [("x", None)])[0], "")
        self.assertEqual(R.read_lines(Image.new("RGB", (50, 50)), (10, 10, 11, 11), ocr=lambda i: [("x", None)]), [])


RUMORS = {r: i for r, i in RU.RUMOURS}


class MatchClosed(unittest.TestCase):
    def m(self, text, **kw):
        kw.setdefault("min_score", RU.MATCH)
        kw.setdefault("min_lead", RU.LEAD)
        return R.match_closed(text, RUMORS, **kw)

    def test_misread_rumors(self):
        # (tests/test_read_misses.py, tests/test_rumours_read.py: what the readers returned for the card's rows)
        for text, want in (("IWviw' to driwk..", "Stagnant Basin"), ("Wawo but risklå...", "Grazed Prairie"),
                           ("Somedtviw' Osho...", "Barren Atoll"), ("SomedQiw' Osho...", "Barren Atoll"),
                           ("Wodviw' to c(riwkv..", "Stagnant Basin"), ("| Wothiw' to drink...", "Stagnant Basin"),
                           ("Wavw but risky...", "Grazed Prairie"), ("Dowell fishy...", "Barren Atoll"),
                           ("B*. Coldasice.. am", "Frigid Bluffs"), ("Its dry at least. Ke - ul", "Sloughed Gully"),
                           ("Cold as ice...", "Frigid Bluffs")):
            self.assertEqual(self.m(text), want, text)

    def test_heading_lines_are_no_entry(self):
        for t in ("USE A LOGBOOK TO CHART THE AR", "b!fSLAND RUMOURS?", "REQUIRES:", "Expedition Logbook", "CONSUMES:",
                  "MUSE A meee TO CHART THE ARE", ""):
            self.assertIsNone(self.m(t), t)

    def test_cut_short_line_one_entry_only(self):
        self.assertEqual(self.m("least..."), "Sloughed Gully")
        self.assertIsNone(self.m("fall..."))                  # three rumors end so: no guess
        self.assertIsNone(self.m("least...", taken=("Sloughed Gully",)))
        self.assertIsNone(self.m("least...", parts=False))

    def test_never_a_guess_between_two(self):
        vocab = ["Exalted Orb", "Exalted Shard"]
        self.assertIsNone(R.match_closed("Exalted Or", vocab, min_lead=0.1, parts=False))
        self.assertIsNone(R.match_closed("Exalted", vocab))                # (the start of both)
        self.assertEqual(R.match_closed("Exalted Shad", vocab, min_lead=0.05, parts=False), "Exalted Shard")

    def test_shapes_find_a_swapped_letter_line(self):
        self.assertIsNone(self.m("Wodviw' to c(riwkv..", shapes=False))
        self.assertEqual(self.m("Wodviw' to c(riwkv.."), "Stagnant Basin")

    def test_medallion_names(self):
        vocab = list(M.MEDALLIONS)
        for text, want in (("ESTAZU NTI rs MEDALLION", "Estazunti's Medallion"), ("UROMOTY S MEDALLION.", "Uromoti's Medallion"),
                           ("ZANTIP MEDALLION", "Zantipi's Medallion"), ('"PUHUARTE 5 MEDALLION', "Puhuarte's Medallion")):
            self.assertEqual(R.match_closed(text, vocab, min_score=0.85, min_lead=0.05), want, text)
        self.assertIsNone(R.match_closed("MEDALLIONS (6/6)", vocab, min_score=0.85, min_lead=0.05))

    def test_detail(self):
        hit = self.m("Cold as ice...", detail=True)
        self.assertEqual((hit.entry, hit.how, hit.key), ("Frigid Bluffs", "text", "Cold as ice..."))
        self.assertGreaterEqual(hit.lead, RU.LEAD)
        self.assertEqual(self.m("least...", detail=True).how, "part")


class Memory(Mem):
    def test_a_line_known_by_its_picture(self):
        mem = R.memory("rumor-row")
        cold, warm = line_pic("Cold as ice..."), line_pic("Warm but risky...")
        self.assertTrue(mem.teach(cold, "Cold as ice..."))
        self.assertTrue(mem.teach(warm, "Warm but risky..."))
        # the same line in another picture: a little smaller, moved, on a wider row
        again = elsewhere(cold, 0.75, width=360)
        self.assertEqual(mem.recall(again), "Cold as ice...")
        self.assertEqual(mem.recall(elsewhere(warm, 1.3)), "Warm but risky...")
        self.assertIsNone(mem.recall(line_pic("Sulphite!")))              # never seen: not a guess
        self.assertIsNone(mem.recall(Image.new("RGB", (200, 40), (215, 205, 180))))     # no text
        self.assertIsNone(mem.recall(again, among={"Warm but risky..."}))

    def test_kept_between_runs_and_capped(self):
        mem = R.memory("card-name")
        mem.teach(line_pic("GARRISON"), "Garrison")
        R._MEMS.clear()
        self.assertEqual(R.memory("card-name").recall(elsewhere(line_pic("GARRISON"), 0.9)), "Garrison")
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "card-name.json")))
        mem = R.memory("card-name")
        for k in range(R.PER_ENTRY + 4):
            mem.teach(elsewhere(line_pic("GARRISON"), 0.7 + 0.05 * k), "Garrison")
        self.assertLessEqual(len(mem._load()["Garrison"]), R.PER_ENTRY)

    def test_an_unsure_match_never_teaches(self):
        mem = R.memory("rumor-row")
        self.assertFalse(mem.teach(line_pic("least..."), "It's dry at least...", R.Hit("Sloughed Gully", 0, 0, "part")))
        self.assertEqual(mem._load(), {})

    def test_a_picture_like_another_entrys_is_kept_by_neither(self):
        mem = R.memory("rumor-row")
        mem.teach(line_pic("Cold as ice..."), "Cold as ice...")
        self.assertFalse(mem.teach(elsewhere(line_pic("Cold as ice..."), 1.0), "Sulphite!"))
        self.assertNotIn("Sulphite!", mem._load())


class ReadClosed(Mem):
    def test_by_text_then_by_picture(self):
        pic = Image.new("RGB", (600, 200), (40, 30, 20))
        row = line_pic("Somethin' fishy...", width=400)
        pic.paste(row, (50, 60))
        box = (50, 60, 50 + row.width, 60 + row.height)
        calls = []

        def ocr(img):
            calls.append(1)
            return [("Somedtviw' Osho...", (5, 5, 300, 40))]
        hit = R.read_closed(pic, box, RU._VOCAB, kind="rumor-row", match=RU._closed, ocr=ocr)
        self.assertEqual(hit.entry, ("Somethin' fishy...", "Barren Atoll"))
        self.assertEqual(hit.how, "text")
        n = len(calls)
        again = R.read_closed(pic, box, RU._VOCAB, kind="rumor-row", match=RU._closed, ocr=ocr)
        self.assertEqual(again.entry[1], "Barren Atoll")
        self.assertEqual(again.how, "picture")
        self.assertEqual(len(calls), n)                           # (known by its picture: not read again)

    def test_a_misread_never_seen_and_no_picture_is_a_miss(self):
        pic = line_pic("Wild roaming free...")
        hit = R.read_closed(pic, (0, 0, pic.width, pic.height), RU._VOCAB, kind="rumor-row", match=RU._closed,
                            ocr=lambda img: [("~~ ,. ;", (0, 0, 9, 9))])
        self.assertIsNone(hit)
        self.assertEqual(R.memory("rumor-row")._load(), {})


def card_pic(rumors):
    """A drawn Uncharted Waters card: its logbook strip, the blue-gray banner, then a row per rumor."""
    w, row = 460, 56
    h = 50 + 42 + row * len(rumors) + 10
    img = Image.new("RGB", (w + 200, h + 120), (8, 10, 12))
    card = Image.new("RGB", (w, h), (205, 198, 175))
    d = ImageDraw.Draw(card)
    d.text((30, 12), "USE A LOGBOOK TO CHART THE AREA", fill=(60, 50, 40), font=font(20))
    d.rectangle((90, 54, w - 90, 92), fill=(140, 165, 170))
    d.text((130, 58), "ISLAND RUMOURS", fill=(240, 240, 240), font=font(22))
    for k, r in enumerate(rumors):
        y = 96 + k * row
        d.line((0, y, w, y), fill=(70, 60, 50), width=2)
        d.text((110, y + 12), r, fill=(20, 18, 15), font=font(28))
    img.paste(card, (60, 60))
    return img, (60, 60, 60 + w, 60 + h)


class RumorCard(Mem):
    def test_rows_found_below_the_banner(self):
        for rumors in (["Nothin' to drink...", "Warm but risky...", "Somethin' fishy..."],
                       ["Somethin' fishy...", "Reflective waters..."], ["Cold as ice..."]):
            img, card = card_pic(rumors)
            anchor, banner, rows = RU.card_lines(img, card)
            self.assertEqual(len(rows), len(rumors), rumors)
            self.assertLess(anchor[3], banner[3])
            for k, b in enumerate(rows):                          # each row holds its line's middle
                mid = 60 + 96 + k * 56 + 28
                self.assertTrue(b[1] <= mid <= b[3], (rumors, k, b))

    def test_read_card_with_the_misreads(self):
        img, card = card_pic(["Nothin' to drink...", "Warm but risky...", "Somethin' fishy..."])
        _a, _b, rows = RU.card_lines(img, card)
        said = iter(["USE A LOGBOOK TO CHART THE AREA", "IWviw' to driwk..", "Wawo but risklå...", "Somedtviw' Osho..."])
        ok, got = RU.read_card(img, card, ocr=lambda pic: [(next(said), (0, 0, 20, 20))])
        self.assertTrue(ok)
        self.assertEqual([i for _r, i, _b in got], ["Stagnant Basin", "Grazed Prairie", "Barren Atoll"])
        self.assertEqual([b for _r, _i, b in got], rows)

    def test_no_anchor_no_card(self):
        img, card = card_pic(["Cold as ice..."])
        ok, got = RU.read_card(img, card, ocr=lambda pic: [("Cold as ice...", (0, 0, 20, 20))])
        self.assertFalse(ok)                                       # (a lit floor read as a rumor: not the card)
        self.assertEqual(R.memory("rumor-row")._load(), {})        # (and nothing learned from it)

    def test_merge_keeps_the_row_reads(self):
        first = [("Cold as ice...", "Frigid Bluffs", (0, 100, 9, 150))]
        more = [("Sulphite!", "Scorched Cay", (0, 110, 9, 140)), ("Warm but risky...", "Grazed Prairie", (0, 160, 9, 200)),
                ("Cold as ice...", "Frigid Bluffs", (0, 210, 9, 240))]
        self.assertEqual([i for _r, i, _b in RU.merge_rows(first, more)], ["Frigid Bluffs", "Grazed Prairie"])


class ConsoleAndTitle(unittest.TestCase):
    def test_console_misreads_still_parse(self):
        for t in ("“LR 36/60", "“=a @ 36/60), — FETE", "“Sal @ 54/60). FETE"):
            self.assertIsNotNone(TM.parse_console([(t, None)]), t)
        for t in (". LAST MAPS PROFIT 7", "| : TTORPeEronre"):
            self.assertIsNone(TM.parse_console([(t, None)]), t)

    def test_title_box_on_screen(self):
        tb = V.side_box((0, 0, 2560, 1440), V.MEDAL_TITLE, right=True)
        self.assertEqual(tb, V.MEDAL_TITLE)
        small = V.side_box((0, 0, 1920, 1080), V.MEDAL_TITLE, right=True)
        self.assertEqual(small[2], int(1920 - (2560 - V.MEDAL_TITLE[2]) * 0.75))


class BookLines(unittest.TestCase):
    def test_an_unmatched_reward_line_is_read_again(self):
        from soe2 import remnant as RM
        names = RM.Names(["Orb of Alchemy", "Divine Orb", "Exalted Orb"])
        pic = Image.new("RGB", (500, 200), (200, 190, 160))
        lines = [("3x Orb of Alchemv", (10, 10, 300, 40)), ("2x Dlvlne 0rh", (10, 60, 300, 90)),
                 ("Skill Level 20: Rain of Blades", (10, 110, 300, 140)), ("Monsters gain:", (10, 150, 300, 180))]
        asked = []

        def ocr(img):
            asked.append(img.size)
            return [("2x Divine Orb" if len(asked) == 1 else "Monsters gain:", (0, 0, 50, 20))]
        out = RM.reread_lines(pic, lines, names, ocr=ocr)
        self.assertEqual(out[1][0], "2x Divine Orb")
        self.assertEqual(out[0], lines[0])                       # (it matched already)
        self.assertEqual(out[2], lines[2])                       # (a gem line: left)
        self.assertEqual(out[3], lines[3])                       # (read again, still no item: as it was)
        self.assertEqual(len(asked), 1 + len(R.KINDS["book-line"]))


if __name__ == "__main__":
    unittest.main()
