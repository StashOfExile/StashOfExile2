"""3.0.6 Vaal Lens full plan (owner's rules, Builds\\temple_reference\\TEMPLE_RULES.md): key room and Atziri first, then
the Architect, then every room in hand by quadrant (chains left, bottom kept for the key room, top / right for the
Architect), no loops, never beside a reward room; where the upgrade / lock medallions go; a reroll for a junk hand."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import vaallens_plan as VP  # noqa: E402


def board(cells):
    return {c: {"kind": k, "name": n, "tier": t} for c, (k, n, t) in cells.items()}


BASE = {(0, 1): ("path", None, 1), (0, 2): ("path", None, 1), (0, 3): ("path", None, 1),
        (-4, 3): ("reward", "Reward", 1), (4, 5): ("reward", "Reward", 1), (-2, 9): ("reward", "Reward", 1)}


class Quadrants(unittest.TestCase):
    def test_split_by_gold_path_and_middle_row(self):
        self.assertEqual(VP.quadrant((-2, 2)), "left")
        self.assertEqual(VP.quadrant((-2, 8)), "top")
        self.assertEqual(VP.quadrant((2, 8)), "right")
        self.assertEqual(VP.quadrant((2, 2)), "bottom")
        self.assertIsNone(VP.quadrant((0, 4)))
        self.assertIsNone(VP.quadrant((3, 5)))


class Priorities(unittest.TestCase):
    def test_atziri_then_key_room_then_architect(self):
        # 3.0.6 (owner): "#1: Atziri Chamber #2: Key Room (if available) #3: Architect"
        b = board({**BASE, (3, 2): ("key", "Key Room", 1), (2, 7): ("architect", "Architect", 1)})
        r = VP.full_plan(b, ["Thaumaturge's Laboratory"] + ["Path"] * 12)
        whys = [w for _t, f, w in r["plan"] if f == "Path"]
        self.assertEqual(whys[0], "Atziri")
        order = [w for k, w in enumerate(whys) if w not in whys[:k]]
        self.assertEqual(order, ["Atziri", "the key room", "the Architect"])
        self.assertGreater(len(set(VP.steps(r["plan"]))), 2, "Atziri, key room, Architect: separate steps")

    def test_atziri_first_even_without_a_key_room(self):
        # (owner's board: the gold path stopped at row 6 and the plan placed rooms instead of joining Atziri)
        b = board({**BASE, (-1, 8): ("architect", "Architect", 1)})
        r = VP.full_plan(b, ["Path", "Bronzeworks", "Depot", "Path", "Guardhouse", "Path"])
        self.assertEqual(r["plan"][0][2], "Atziri")
        tiles = [t for t, f, w in r["plan"] if f == "Path"]
        self.assertTrue(all(t[0] == 0 for t in tiles), "straight up the gold path")

    def test_key_spot_kept_free(self):
        b = board(dict(BASE))
        r = VP.full_plan(b, ["Path"] * 10 + ["Bronzeworks", "Depot", "Guardhouse"])
        keep = VP.key_spot(VP.names(b))
        self.assertTrue(keep)
        self.assertFalse({t for t, f, w in r["plan"] if f != "Path"} & keep, "no room on the key room's spot")

    def test_filler_blocks_a_bare_wall(self):
        self.assertIn((-4, 3), VP.edge_blocks({}))
        self.assertNotIn((-4, 2), VP.edge_blocks({}), "every other square")
        self.assertNotIn((-4, 3), VP.edge_blocks({(-4, 8): "Reward"}), "a wall with a reward room is left alone")

    def test_card_with_art_read_as_a_digit(self):
        self.assertEqual(VP.card("DEPOT 4"), ("room", "Armoury"))
        self.assertEqual(VP.card("PATH 4"), ("path", None))

    def test_architect_before_rooms(self):
        b = board({**BASE, (2, 7): ("architect", "Architect", 1)})
        plan = VP.full_plan(b, ["Thaumaturge's Laboratory", "Crimson Hall"] + ["Path"] * 6)["plan"]
        self.assertEqual(plan[0][1], "Path")
        kinds = [f for _t, f, _w in plan]
        self.assertLess(max(i for i, f in enumerate(kinds) if f == "Path"), kinds.index("Thaumaturge"))


class Rooms(unittest.TestCase):
    def setUp(self):
        self.b = board({**BASE, (-1, 2): ("room", "Garrison", 1), (2, 7): ("architect", "Architect", 1)})

    def test_every_room_in_hand_is_planned_safely(self):
        plan = VP.full_plan(self.b, ["Thaumaturge's Laboratory", "Crimson Hall", "Surgeon's Ward",
                                     "Prosthetic Research", "Workshop"])["plan"]
        fams = [f for _t, f, _w in plan if f != "Path"]
        for fam in ("Thaumaturge", "Corruption Chamber", "Flesh Surgeon", "Synthflesh Lab", "Golem Works"):
            self.assertIn(fam, fams)
        taken = VP.names(self.b)
        for t, f, _w in plan:
            if f != "Path":
                self.assertFalse(VP.touches_reward(taken, t), f"{f} beside a reward room")
                self.assertNotEqual(VP.quadrant(t), "bottom", f"{f} in the key room's quadrant")
                self.assertNotIn(t, VP.LANE, f"{f} on the gold path")

    def test_partners_side_by_side(self):
        plan = VP.full_plan(self.b, ["Surgeon's Ward", "Prosthetic Research", "Thaumaturge's Laboratory",
                                     "Crimson Hall"])["plan"]
        at = {f: t for t, f, _w in plan}
        self.assertIn(at["Flesh Surgeon"], VP.near(at["Synthflesh Lab"]), "tier-3 Flesh Surgeon beside Synthflesh")
        self.assertIn(at["Corruption Chamber"], VP.near(at["Thaumaturge"]))

    def test_chains_go_left(self):
        plan = VP.full_plan(self.b, ["Thaumaturge's Laboratory", "Crimson Hall"])["plan"]
        self.assertTrue(all(VP.quadrant(t) == "left" for t, f, _w in plan if f != "Path"))

    def test_generator_only_on_a_path(self):
        plan = VP.full_plan(self.b, ["Dynamo"])["plan"]
        t = next(t for t, f, _w in plan if f == "Generator")
        b = {**VP.names(self.b), **{x: f for x, f, _w in plan}}
        self.assertTrue(any(b.get(n) in ("Path", "Entrance") for n in VP.near(t)))

    def test_no_loop_when_there_is_room(self):
        plan = VP.full_plan(self.b, ["Thaumaturge's Laboratory", "Crimson Hall"])["plan"]
        b = dict(VP.names(self.b))
        for t, f, _w in plan:
            self.assertFalse(VP._loops(b, t), f"{f} closes a loop")
            b[t] = f


class Medallions(unittest.TestCase):
    def test_upgrade_then_lock_the_corruption_chamber(self):
        b = board({**BASE, (-1, 2): ("room", "Thaumaturge", 1), (-1, 3): ("room", "Corruption Chamber", 2),
                   (-2, 2): ("room", "Garrison", 1)})
        r = VP.full_plan(b, [], ["Quipolatl's Medallion", "Juatalotli's Medallion"])
        self.assertEqual(r["targets"].get((-1, 3)), ("Upgrade", "Corruption Chamber"))
        self.assertIn("Lock the Corruption Chamber after its upgrade.", r["notes"])

    def test_lock_a_tier_three(self):
        b = board({**BASE, (-1, 3): ("room", "Corruption Chamber", 3), (-1, 2): ("room", "Garrison", 1)})
        r = VP.full_plan(b, [], ["Juatalotli's Medallion"])
        self.assertEqual(r["targets"].get((-1, 3)), ("Lock", "Corruption Chamber"))

    def test_reroll_a_junk_hand(self):
        b = board(BASE)
        r = VP.full_plan(b, ["Spymaster's Study", "Commander's Chamber"], ["Puhuarte's Medallion"])
        self.assertTrue(any("reroll" in n for n in r["notes"]))
        r = VP.full_plan(b, ["Thaumaturge's Laboratory"], ["Puhuarte's Medallion"])
        self.assertFalse(any("reroll" in n for n in r["notes"]), "a paying card: no reroll")


class KeyRoomCard(unittest.TestCase):
    def test_lands_in_the_bottom_quadrant(self):
        r = VP.full_plan(board(BASE), ["Royal Access Chamber"])
        spot = next(t for t, f, _w in r["plan"] if f == "Key Room")
        self.assertEqual(VP.quadrant(spot), "bottom")

    def test_no_clean_spot_says_next_run(self):
        cells = dict(BASE)
        for i in range(-4, 5):
            for j in range(1, 10):
                if (i, j) not in cells and i != 0:
                    cells[(i, j)] = ("room", "Garrison", 1)
        r = VP.full_plan(board(cells), ["Royal Access Chamber"])
        self.assertTrue(any("next run" in n for n in r["notes"]))


class Draw(unittest.TestCase):
    def test_marks_and_word_badges_render(self):
        from soe2 import vaallens_draw as VD
        marks = {(-3, 3): ("x", "touches"), (-2, 3): ("do", ("Upgrade", "Corruption Chamber")),
                 (0, 4): ("p", (1, "path")), (0, 5): ("p", (None, "path")), (-1, 4): ("p", (2, "Thaumaturge"))}
        img, at = VD.render((0, 0, 2560, 1440), marks, {"head": "#f0a04a"}, {}, None)
        self.assertIsNotNone(img)
        self.assertGreater(img.getbbox()[2], 0)

    def test_path_number_on_every_tile(self):
        plan = [((0, 4), "Path", "the Architect"), ((0, 5), "Path", "the Architect"), ((-1, 4), "Thaumaturge", "x")]
        out = VP.with_plan({}, plan, (), None)
        self.assertEqual(out[(0, 4)][1][0], 1)
        self.assertEqual(out[(0, 5)][1][0], 1, "every path tile numbered (one path card each)")
        self.assertEqual(out[(-1, 4)][1][0], 2)


if __name__ == "__main__":
    unittest.main()


class Numbers(unittest.TestCase):
    """3.0.6 (owner): a number on each card / medallion and the same number on its tile; medallion slots read where
    the game puts them (right column first)."""

    def test_card_title_snaps_ocr(self):
        self.assertEqual(VP.card_title("Wor Kshop"), "Workshop")
        self.assertEqual(VP.card_title("SEALED VAULT"), "Sealed Vault")
        self.assertEqual(VP.card("PATH >"), ("path", None))
        self.assertEqual(VP.card("Path"), ("path", None))

    def test_medallion_slots_right_column_first(self):
        from soe2 import medallions as M
        head = (2336, 609, 2557, 663)                    # owner's 4/6 panel at 2560x1440
        got = M.slots(head, 1.0, 4)
        self.assertEqual([b[:2] for b in got], [(2273, 680), (2417, 680), (2417, 824), (2417, 968)])
        self.assertEqual(len(M.slots(head, 1.0, 6)), 6)

    def test_labels_match_steps(self):
        from soe2 import temple_page as TP
        f = TP.TemplePage()
        f.tm_medal_boxes = [("Uromoti's Medallion: Smithy", (2417, 680, 2537, 805))]
        b = {"card_rows": [("Path", (504, 338)), ("Workshop", (504, 627)), ("Path", (504, 770))]}
        plan = [((0, 4), "Path", "the key room"), ((0, 5), "Path", "the key room"), ((-1, 3), "Smithy", "x"),
                ((-2, 3), "Golem Works", "beside Smithy")]
        lab = f._temple_step_labels(b, plan)
        self.assertEqual(lab[("@", 504, 338)], ("lbl", 1))
        self.assertEqual(lab[("@", 504, 770)], ("lbl", 1), "a 2-tile path: both path cards are step 1")
        self.assertEqual(lab[("@", 2431, 694)], ("lbl", 2), "the Smithy medallion")
        self.assertEqual(lab[("@", 504, 627)], ("lbl", 3), "the Workshop card")

    def test_no_room_pictures_on_tiles(self):
        from soe2 import vaallens_draw as VD
        marks = {(-1, 4): ("p", (2, "Thaumaturge")), ("@", 504, 338): ("lbl", 1),
                 (-2, 3): ("do", ("Lock", "Corruption Chamber"))}
        img, _xy = VD.render((0, 0, 2560, 1440), marks, {"head": "#f0a04a"}, {"Thaumaturge": None}, None)
        self.assertIsNotNone(img)


class UsesWhatYouHave(unittest.TestCase):
    """3.0.6 (owner: "It needs to use what I have, not what I don't have"): paths only from path cards; a room card
    can join something when the path cards run out; an unread placed tile ("?") is joined."""

    def test_no_more_path_tiles_than_path_cards(self):
        b = board({**BASE, (3, 6): ("key", "Key Room", 1)})
        r = VP.full_plan(b, ["Path"])
        self.assertLessEqual(sum(1 for _t, f, _w in r["plan"] if f == "Path"), 1)
        self.assertTrue(any("more path card" in n for n in r["notes"]))

    def test_a_cheap_room_joins_when_paths_run_out(self):
        b = board({**BASE, (2, 4): ("key", "Key Room", 1), (1, 3): ("path", None, 1), (1, 2): ("path", None, 1),
                   (1, 1): ("path", None, 1)})
        r = VP.full_plan(b, ["Sealed Vault"])
        self.assertIn(((1, 4), "Sealed Vault", "joins the key room"), r["plan"])

    def test_unknown_placed_tile_is_joined(self):
        b = board({**BASE, (-1, 3): ("unknown", None, 1), (-2, 3): ("key", "Key Room", 1)})
        self.assertIn((-1, 3), VP.network(VP.names(b)))
        self.assertFalse([w for _t, _f, w in VP.full_plan(b, ["Path"])["plan"] if w == "the key room"],
                         "already joined through it")


class KeepForNextRun(unittest.TestCase):
    """3.0.6 (owner): a Commander - card or medallion - alone is kept for a run with a Garrison; beside one it goes."""

    def test_lone_commander_medallion_is_kept(self):
        r = VP.full_plan(board(BASE), [], [], ["Commander"])
        self.assertFalse([1 for _t, f, _w in r["plan"] if f == "Commander"])
        self.assertIn("Keep the Commander medallion for a run with a Garrison to sit beside.", r["notes"])

    def test_commander_beside_a_garrison_goes(self):
        b = board({**BASE, (-1, 2): ("room", "Garrison", 1)})
        r = VP.full_plan(b, [], [], ["Commander"])
        t = next(t for t, f, _w in r["plan"] if f == "Commander")
        self.assertIn((-1, 2), VP.near(t))


class OwnersBoard(unittest.TestCase):
    """3.0.6, the owner's board (2026-11-18): the gold path to row 6, the Architect at (-1, 8), a Garrison chain on
    the right, three Smithies round a Golem Works on the left."""
    def b(self):
        cells = {(0, j): ("path", None, 1) for j in range(1, 7)}
        cells.update({(-1, 8): ("architect", "Architect", 1), (1, 6): ("room", "Commander", 1),
                      (1, 7): ("room", "Garrison", 2), (1, 8): ("room", "Commander", 1),
                      (-2, 5): ("room", "Smithy", 3), (-1, 4): ("room", "Smithy", 2), (-2, 4): ("room", "Golem Works", 1),
                      (1, 5): ("room", "Alchemy Lab", 1), (-4, 3): ("reward", "Reward", 1), (4, 5): ("reward", "Reward", 1),
                      (-3, 9): ("reward", "Reward", 1), (2, 9): ("reward", "Reward", 1)})
        return board(cells)

    def test_rooms_that_gain_join_atziri(self):
        r = VP.full_plan(self.b(), ["Path", "Bronzeworks", "Depot", "Path", "Guardhouse", "Path"])
        atz = [(t, f) for t, f, w in r["plan"] if w.endswith("Atziri")]
        self.assertEqual(atz[0][0][0], 0, "up the gold path")
        self.assertIn("Garrison", [f for _t, f in atz], "the Guardhouse joins Atziri beside the Commander")

    def test_both_upgrades_go_to_tier_2_first(self):
        meds = ["Quipolatl's Medallion", "Quipolatl's Medallion", "Juatalotli's Medallion"]
        r = VP.full_plan(self.b(), ["Path"] * 3, meds)
        ups = {t for t, (w, _f) in r["targets"].items() if w == "Upgrade"}
        self.assertIn((-1, 4), ups, "the tier-2 Smithy beside the Golem Works")
        self.assertEqual(len(ups), 2)

    def test_no_loop_into_the_gold_path(self):
        r = VP.full_plan(self.b(), ["Path"] * 3, ["Uromoti's Medallion: Golem Works"], ["Golem Works"])
        self.assertNotIn((-1, 5), [t for t, f, w in r["plan"]], "it would loop the Smithies back into the road")

    def test_plan_kept_as_cards_are_placed(self):
        b = self.b()
        cards = ["Path", "Bronzeworks", "Depot", "Path", "Guardhouse", "Path"]
        first = VP.full_plan(b, cards)["plan"]
        t, f, _w = first[0]
        b[t] = {"kind": "room" if f != "Path" else "path", "name": f, "tier": 1}
        left = list(cards)
        left.remove({"Garrison": "Guardhouse", "Armoury": "Depot", "Smithy": "Bronzeworks"}.get(f, "Path"))
        again = VP.full_plan(b, left, prev=first)["plan"]
        self.assertEqual(again, first[1:], "the rest of the plan stays as it was")


class CardRows(unittest.TestCase):
    def test_gold_text_drops_white_numbers(self):
        from PIL import Image
        from soe2 import vaallens as V
        im = Image.new("RGB", (40, 10), (20, 20, 20))
        im.paste((200, 165, 100), (0, 0, 10, 10))        # gold letters
        im.paste((240, 240, 240), (20, 0, 30, 10))       # the game's white Life numbers
        g = V._gold_text(im)
        self.assertEqual(g.getpixel((5, 5)), 0)
        self.assertEqual(g.getpixel((25, 5)), 255)
