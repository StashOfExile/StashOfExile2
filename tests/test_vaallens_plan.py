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
        self.assertEqual(order[:3], ["Atziri", "the key room", "the Architect"])
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
        # (3.0.6: a room goes beside a path or a room it works with - a path runs left for the chains)
        self.b = board({**BASE, (-1, 2): ("room", "Garrison", 1), (2, 7): ("architect", "Architect", 1),
                        (-1, 3): ("path", None, 1), (-2, 3): ("path", None, 1), (-2, 2): ("path", None, 1)})

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
        self.assertTrue(all(VP.quadrant(t) in ("left", None) for t, f, _w in plan if f != "Path"))

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

    def test_atziri_joined_by_paths_only(self):
        # (owner: "it's better to use paths to connect to atziri's chamber at the end" - a room chain can break)
        r = VP.full_plan(self.b(), ["Path", "Bronzeworks", "Depot", "Path", "Guardhouse", "Path"])
        atz = [(t, f) for t, f, w in r["plan"] if w.endswith("Atziri")]
        self.assertEqual([f for _t, f in atz], ["Path"] * 3)
        self.assertEqual([t for t, _f in atz], [(0, 7), (0, 8), (0, 9)], "up the gold path, path to path")

    def test_a_path_never_starts_from_a_room(self):
        b = self.b()
        b[(0, 7)] = {"kind": "room", "name": "Garrison", "tier": 1}       # a room chain up the middle
        b[(0, 8)] = {"kind": "room", "name": "Armoury", "tier": 1}
        r = VP.full_plan(b, ["Path"] * 4)
        net = VP.path_network(VP.names(b))
        first = next(t for t, f, w in r["plan"] if f == "Path")
        self.assertTrue(any(n in net for n in VP.near(first)), "the first path touches a path")

    def test_spare_paths_become_filler(self):
        # (owner: spare paths go down as filler - destabilization takes them before your rooms)
        r = VP.full_plan(self.b(), ["Path"] * 6)
        self.assertTrue(any(w == "filler" for _t, _f, w in r["plan"]))

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


class KeyRoomPreview(unittest.TestCase):
    def test_key_card_held_and_its_spot_lit_is_step_1(self):
        # 3.0.6 (owner): the game shows the key room on the one square it can go - number it, card and tile
        b = board({**BASE, (2, 3): ("key", "Key Room", 1)})
        r = VP.full_plan(b, ["Royal Access Chamber", "Path", "Path"])
        self.assertEqual(r["plan"][0], ((2, 3), "Key Room", "the key room"))
        self.assertEqual(VP.steps(r["plan"])[0], 1)


class OwnersRound2(unittest.TestCase):
    def test_room_chain_to_atziri_when_paths_run_short(self):
        # (owner: Garrison / Commander snaked up to Atziri, one more room after it to guard the chain)
        cells = {(0, j): ("path", None, 1) for j in range(1, 7)}
        cells.update({(0, 7): ("room", "Garrison", 1), (-4, 5): ("reward", "Reward", 1)})
        r = VP.full_plan(board(cells), ["Guardhouse", "Commander's Chamber", "Guardhouse", "Commander's Chamber"])
        whys = [w for _t, _f, w in r["plan"]]
        self.assertIn("joins Atziri", whys)
        self.assertIn("guards the chain to Atziri", whys)

    def test_vault_card_on_a_side_wall_touching_nothing(self):
        r = VP.full_plan(board(dict(BASE)), ["Kishara's Vault"])
        t = next(t for t, f, w in r["plan"] if f == "Kishara's Vault")
        self.assertEqual(abs(t[0]), 4)
        self.assertFalse(any(VP.names(board(dict(BASE))).get(n) for n in VP.near(t)))

    def test_spymaster_never_beside_a_commander(self):
        b = board({**BASE, (-1, 3): ("room", "Commander", 1)})
        r = VP.full_plan(b, ["Spymaster's Study"])
        for t, f, _w in r["plan"]:
            if f == "Spymaster":
                self.assertNotIn((-1, 3), VP.near(t))


class ClearMarks(unittest.TestCase):
    def test_clear_hides_marks_and_reads_nothing(self):
        from soe2.temple_page import TemplePage
        hid = []

        class Mk:
            def hide(self):
                hid.append(1)

        class A(TemplePage):
            pass
        a = A()
        a.tm_marks_win, a.tm_marks = Mk(), {(0, 1): ("p", (1, "path"))}
        a.temple_marks_clear()
        self.assertEqual(hid, [1])
        self.assertEqual(a.tm_marks, {})


class CorruptionFirst(unittest.TestCase):
    def test_upgrade_and_lock_go_to_the_corruption_chamber(self):
        # (owner: "Corruption chamber takes upgrade + lock priority over everything else")
        b = board({**BASE, (1, 3): ("room", "Corruption Chamber", 2), (1, 4): ("room", "Thaumaturge", 1),
                   (-2, 5): ("room", "Smithy", 3), (-2, 4): ("room", "Golem Works", 1)})
        r = VP.full_plan(b, ["Path"], ["Quipolatl's Medallion", "Juatalotli's Medallion"])
        self.assertEqual(r["targets"].get((1, 3)), ("Upgrade", "Corruption Chamber"))
        self.assertTrue(any("Lock the Corruption Chamber" in n for n in r["notes"]))

    def test_two_raisers_make_a_corruption_chamber_worth_placing(self):
        b = board({**BASE, (1, 3): ("room", "Thaumaturge", 1), (2, 2): ("room", "Thaumaturge", 1),
                   (1, 2): ("path", None, 1), (-1, 2): ("key", "Key Room", 1)})
        r = VP.full_plan(b, [], ["Uromoti's Medallion: Corruption Chamber"], ["Corruption Chamber"])
        self.assertIn("Corruption Chamber", [f for _t, f, _w in r["plan"]], "beside two Thaumaturges: tier 3")


class Destabilisation(unittest.TestCase):
    """3.0.6, measured on the owner's boards: dead ends are lost most; a spare path guards a valuable dead end."""
    def test_spare_path_guards_a_dead_end(self):
        cells = {(0, j): ("path", None, 1) for j in range(1, 6)}
        cells[(1, 3)] = ("room", "Corruption Chamber", 3)            # touches only the gold path: a dead end
        cells[(-2, 9)] = ("reward", "Reward", 1)
        b = board(cells)
        self.assertEqual(VP.dead_ends(VP.names(b), b), [(1, 3)])
        r = VP.full_plan(b, ["Path"] * 8 + ["Royal Access Chamber"])
        fill = [t for t, f, w in r["plan"] if w == "filler"]
        self.assertTrue(any(t in VP.near((1, 3)) for t in fill), "a filler path beside the Corruption Chamber")


class ArchitectConsole(unittest.TestCase):
    def test_only_his_cards_no_medallion_advice(self):
        r = VP.full_plan(board(dict(BASE)), ["Jiquani's Vault", "Vault of Reverence", "Extraction Chamber"],
                         ["Juatalotli's Medallion", "Quipolatl's Medallion"])
        self.assertEqual(r["targets"], {})
        self.assertEqual(len(r["plan"]), 3, "each restricted card gets a spot")
        self.assertTrue(all("reward" in w for _t, _f, w in r["plan"]))


class Placement(unittest.TestCase):
    def test_sealed_vault_only_beside_a_path(self):
        # (owner: "sealed vaults have to connect to a path and cannot connect to anything else")
        b = board({**BASE, (1, 3): ("room", "Garrison", 2), (-1, 2): ("key", "Key Room", 1)})
        r = VP.full_plan(b, ["Sealed Vault"])
        n = VP.names(b)
        for t, f, _w in r["plan"]:
            if f == "Sealed Vault":
                self.assertTrue(any(n.get(x) == "Path" or x == VP.ENTRANCE for x in VP.near(t)))
                self.assertFalse(any(n.get(x) in VP.ROOMS for x in VP.near(t)))

    def test_room_needs_a_path_or_a_partner(self):
        self.assertFalse(VP.can_place({(1, 3): "Smithy"}, (2, 3), "Garrison"))
        self.assertTrue(VP.can_place({(1, 3): "Commander"}, (2, 3), "Garrison"))
        self.assertTrue(VP.can_place({(1, 3): "Path"}, (2, 3), "Garrison"))


# ---------------------------------------------------------------- 3.0.6 round 14 (the owner's run, 15 screenshots)
R = ("reward", "Reward", 1)
WALLS = [(-4, 9), (-3, 9), (2, 9), (3, 9), (4, 9), (4, 8), (-4, 7), (4, 7), (-4, 6), (-4, 5), (4, 5), (-4, 4),
         (-4, 3), (4, 3), (-4, 1), (-3, 1), (-2, 1), (2, 1), (4, 1)]
T_NE = {"NE", "SW", "SE"}                       # the owner's T card (round 14, picture 1)
CORNER = {"NE", "SE"}
STRAIGHT = {"NW", "SE"}
HAT = {"SW", "SE"}


def run1():
    """Picture 1: the gold path to row 5, rooms up the middle to the Flesh Surgeon, a reward room beside Atziri's
    doorstep, the Architect at (2, 6)."""
    c = {(0, j): ("path", None, 1) for j in range(1, 6)}
    c.update({(-1, 4): ("path", None, 1), (-1, 5): ("path", None, 1), (-1, 6): ("path", None, 1),
              (0, 6): ("room", "Golem Works", 2), (0, 7): ("room", "Synthflesh Lab", 2),
              (0, 8): ("room", "Flesh Surgeon", 2), (-1, 7): ("room", "Transcendent Barracks", 3),
              (1, 7): ("room", "Transcendent Barracks", 2), (-2, 6): ("room", "Generator", 1),
              (-2, 5): ("room", "Smithy", 4), (-2, 4): ("room", "Golem Works", 1), (-2, 3): ("key", "Key Room", 1),
              (1, 4): ("room", "Thaumaturge", 1), (2, 4): ("room", "Corruption Chamber", 3),
              (1, 5): ("room", "Golem Works", 1), (2, 6): ("architect", "Architect", 1), (-1, 9): R})
    c.update({w: R for w in WALLS})
    return board(c)


def after_close():
    """Picture 6: what the close left - the gold path, two paths left of it, the Flesh Surgeon chain to Atziri."""
    c = {(0, j): ("path", None, 1) for j in range(1, 6)}
    c.update({(-1, 5): ("path", None, 1), (-1, 6): ("path", None, 1), (0, 7): ("room", "Synthflesh Lab", 2),
              (0, 8): ("room", "Flesh Surgeon", 2), (0, 9): ("room", "Synthflesh Lab", 2),
              (-1, 7): ("room", "Transcendent Barracks", 2), (2, 6): ("architect", "Architect", 1)})
    c.update({w: R for w in WALLS})
    return board(c)


class PathShapes(unittest.TestCase):
    """3 pictures: the T card lit the 3 squares north-west of the gold path, none south-east (no turning); rooms
    lit on both sides (the gold path's tiles take a neighbor on either side)."""
    def test_a_path_card_goes_as_drawn(self):
        b = VP.names(run1())
        for t in ((-1, 1), (-1, 2), (-1, 3)):
            self.assertTrue(VP.path_fits(b, t, T_NE), t)
        for t in ((1, 1), (1, 2), (1, 3)):
            self.assertFalse(VP.path_fits(b, t, T_NE), f"{t}: its closed side faces the gold path")
        self.assertTrue(VP.path_fits(b, (1, 2), None), "shape not read: any way")

    def test_no_path_square_the_game_would_not_light(self):
        b = run1()
        b["card_shapes"] = [None, None, T_NE, None, CORNER]
        r = VP.full_plan(b, ["Prosthetic Research", "Workshop", "Path", "Guardhouse", "Path"])
        names = dict(VP.names(b))
        for t, f, _w in r["plan"]:
            if f == "Path":
                k = r["path_cards"][t]
                self.assertTrue(VP.path_fits(names, t, b["card_shapes"][k]), t)
            names[t] = "Path" if f == "Path" else f
        self.assertNotIn((1, 3), [t for t, f, _w in r["plan"] if f == "Path"], "the square the owner couldn't use")

    def test_each_path_card_where_its_shape_fits(self):
        # (picture 7 -> 8: a straight and a corner made the path to the Architect)
        b = after_close()
        b["card_shapes"] = [STRAIGHT, HAT]
        r = VP.full_plan(b, ["Path", "Path"])
        arch = [(t, r["path_cards"][t]) for t, f, w in r["plan"] if f == "Path" and w == "the Architect"]
        self.assertEqual({t for t, _k in arch}, {(0, 6), (1, 6)})
        names = VP.names(b)
        for t, k in arch:
            names = dict(names)
            self.assertTrue(VP.path_fits(names, t, b["card_shapes"][k]))
            names[t] = "Path"
        self.assertTrue(any(c.startswith("Path to the Architect: 2 paths") for c in r["chains"]))

    def test_shape_read_from_the_card_art(self):
        from PIL import Image
        from soe2 import vaallens as V
        im = Image.new("RGB", (480, 300), (22, 22, 23))              # the dark tiled backing
        y = 150
        for side, (dx, dy) in (("NE", (1, -1)), ("SE", (1, 1)), ("SW", (-1, 1))):
            for t in range(0, 34):                                   # floor out to three sides (a T)
                x0 = V.CARD_MID_X + dx * V.CARD_HALF[0] * t / 33
                y0 = y + dy * V.CARD_HALF[1] * t / 33
                im.paste((40, 33, 25), (int(x0) - 4, int(y0) - 4, int(x0) + 5, int(y0) + 5))
        self.assertEqual(V.path_shape(im, y, 1.0), frozenset(T_NE))
        self.assertIsNone(V.path_shape(Image.new("RGB", (480, 300), (22, 22, 23)), y, 1.0))


class AtziriFirst(unittest.TestCase):
    """2 pictures (1 -> 3, and the later run): the owner joined Atziri with a Prosthetic Research beside his Flesh
    Surgeon, on her doorstep beside a reward room - the only way in."""
    def test_her_doorstep_beside_a_reward_room(self):
        r = VP.full_plan(run1(), ["Prosthetic Research", "Workshop", "Path", "Guardhouse", "Path"])
        self.assertEqual(r["plan"][0], ((0, 9), "Synthflesh Lab", "joins Atziri"))
        self.assertEqual(VP.steps(r["plan"])[0], 1)
        self.assertIn("Chain to Atziri: 1 room.", r["chains"])

    def test_doorstep_not_crossed_out(self):
        b = run1()
        m = VP.marks(b, [(0, 9), (1, 8)], ("room", "Synthflesh Lab"))
        self.assertNotEqual(m.get((0, 9), ("",))[0], "x")

    def test_joined_by_a_room_is_joined(self):
        r = VP.full_plan(after_close(), ["Path"])
        self.assertFalse([w for _t, _f, w in r["plan"] if "Atziri" in w])
        self.assertFalse(any("Atziri" in n and "path" in n.lower() and "No safe" in n for n in r["notes"]))

    def test_chain_never_touches_an_x_square(self):
        # (owner: "built in protections of the x rooms not to connect to") - a reward room beside the only way up
        c = {(0, j): ("path", None, 1) for j in range(1, 7)}
        c.update({(0, 7): ("room", "Garrison", 1), (1, 8): R, (-1, 8): R})
        b = board(c)
        r = VP.full_plan(b, ["Guardhouse", "Commander's Chamber", "Depot"])
        names = VP.names(b)
        for t, _f, w in r["plan"]:
            if t != VP.DOOR:
                self.assertFalse(VP.touches_reward(names, t), f"{t} ({w}) touches a reward room")


class Upgrades(unittest.TestCase):
    """Owner: "it also wants me to upgrade the flesh surgeon, that's like way low priority, I'm saving the upgrade
    for the next corruption chamber upgrade"; "the t3/t4 barracks and synthflesh were useless"; "why is it suggesting
    I upgrade the generator/dynamo?" (3 pictures)."""
    def test_kept_for_the_corruption_chamber(self):
        meds = ["Quipolatl's Medallion", "Uromoti's Medallion: Generator", "Uromoti's Medallion: Thaumaturge",
                "Quipolatl's Medallion", "Uromoti's Medallion: Thaumaturge",
                "Uromoti's Medallion: Corruption Chamber"]
        r = VP.full_plan(after_close(), ["Path"], meds, ["Generator", "Thaumaturge", "Thaumaturge",
                                                         "Corruption Chamber"])
        self.assertEqual(r["targets"], {}, "no Upgrade on the Flesh Surgeon or the Synthflesh Lab")
        self.assertIn("Keep the Upgrade for the Corruption Chamber.", r["notes"])

    def test_never_on_rooms_that_only_add_monsters(self):
        b = board({**BASE, (1, 2): ("room", "Synthflesh Lab", 1), (-1, 2): ("room", "Generator", 1),
                   (1, 3): ("room", "Transcendent Barracks", 2), (-1, 3): ("room", "Garrison", 1)})
        r = VP.full_plan(b, [], ["Quipolatl's Medallion", "Juatalotli's Medallion"])
        self.assertEqual(r["targets"], {})
        self.assertIn("Keep the Upgrade for next run: nothing here pays for it.", r["notes"])
        self.assertIn("Keep the Lock for next run: nothing here pays for it.", r["notes"])

    def test_unread_medallions_keep_it_off_the_flesh_surgeon(self):
        r = VP.full_plan(after_close(), [], ["Quipolatl's Medallion", None, None])
        self.assertEqual(r["targets"], {})

    def test_two_upgrades_each_name_their_own_room(self):
        from soe2.temple_page import TemplePage

        class A(TemplePage):
            pass
        a = A()
        a.tm_plan, a.tm_notes = [], []
        a.tm_targets = {(1, 3): ("Upgrade", "Corruption Chamber"), (-2, 5): ("Upgrade", "Smithy")}
        up = "Quipolatl's Medallion"
        self.assertEqual(a._temple_medal_say(up, 0), "Upgrade · use on Corruption Chamber")
        self.assertEqual(a._temple_medal_say(up, 1), "Upgrade · use on Smithy")
        self.assertEqual(a._temple_medal_say(up, 2), "Upgrade · keep for next run")


class CorruptionChain(unittest.TestCase):
    """Owner: "I will place the corruption chamber and thaumaturge, upgrade corruption chamber and lock it so I get
    2 runs out of it which is 2 guaranteed architect's orbs" (2 pictures)."""
    MEDS = ["Uromoti's Medallion: Thaumaturge", "Uromoti's Medallion: Corruption Chamber", "Quipolatl's Medallion"]

    def test_waits_for_an_upgrade_and_a_lock(self):
        r = VP.full_plan(board(dict(BASE)), [], self.MEDS, ["Thaumaturge", "Corruption Chamber"])
        self.assertNotIn("Corruption Chamber", [f for _t, f, _w in r["plan"]])
        self.assertNotIn("Thaumaturge", [f for _t, f, _w in r["plan"]], "no Thaumaturge left alone")
        self.assertTrue(any("2 runs" in n and "Architect" in n for n in r["notes"]))

    def test_goes_down_together_with_both(self):
        r = VP.full_plan(board(dict(BASE)), [], self.MEDS + ["Juatalotli's Medallion"],
                         ["Thaumaturge", "Corruption Chamber"])
        got = {f: t for t, f, _w in r["plan"]}
        self.assertIn("Thaumaturge", got)
        self.assertIn("Corruption Chamber", got)
        self.assertIn(got["Corruption Chamber"], VP.near(got["Thaumaturge"]))
        self.assertTrue(any("Corruption Chamber beside the Thaumaturge" in c for c in r["chains"]))

    def test_no_clean_square_both_wait(self):
        # (picture 11: the only square beside the Thaumaturge's spots loops back into the gold path)
        c = {(0, j): ("path", None, 1) for j in range(1, 7)}
        c.update({(-1, 6): ("path", None, 1), (0, 7): ("room", "Synthflesh Lab", 3), (0, 8): ("room", "Flesh Surgeon", 4),
                  (-1, 7): ("room", "Transcendent Barracks", 3), (-2, 6): ("room", "Generator", 1),
                  (2, 6): ("architect", "Architect", 1), (2, 4): ("key", "Key Room", 1), (2, 3): R, (-2, 3): R})
        c.update({w: R for w in WALLS})
        meds = self.MEDS + ["Juatalotli's Medallion", "Uromoti's Medallion: Thaumaturge"]
        r = VP.full_plan(board(c), ["Path", "Prosthetic Research"], meds,
                         ["Thaumaturge", "Corruption Chamber", "Thaumaturge"])
        fams = [f for _t, f, _w in r["plan"]]
        self.assertNotIn("Thaumaturge", fams)
        self.assertNotIn("Corruption Chamber", fams)


class ArchitectsCards(unittest.TestCase):
    """Owner (3 pictures): "where the key room is by itself and has an option to connect a reward room to it, it's
    okay to place it beside it as long as it doesn't connect to other reward rooms. I will take a currency vault";
    "I also placed a currency vault on the opposite side because I can safely access it and connect to it next run
    without breaking my outside 'block' rooms along the walls"."""
    def b(self):
        c = {(0, j): ("path", None, 1) for j in range(1, 7)}
        c.update({(-1, 6): ("path", None, 1), (1, 6): ("path", None, 1), (0, 7): ("room", "Synthflesh Lab", 3),
                  (0, 8): ("room", "Flesh Surgeon", 4), (0, 9): ("room", "Synthflesh Lab", 2),
                  (-2, 6): ("room", "Generator", 1), (2, 6): ("architect", "Architect", 1)})
        c.update({w: R for w in WALLS})
        b = board(c)
        b["lit"], b["card"] = [(-2, 3), (2, 4)], "Royal Access Chamber"
        return b

    CARDS = ["Royal Access Chamber", "Vault of Reverence", "Kishara's Vault", "Kishara's Vault", "Jiquani's Vault"]

    def test_key_room_on_a_lit_square_currency_vault_beside_it(self):
        r = VP.full_plan(self.b(), self.CARDS)
        self.assertEqual(r["plan"][0], ((2, 4), "Key Room", "the key room"), "the bottom one of the lit squares")
        self.assertEqual(r["plan"][1], ((2, 3), "Kishara's Vault", "beside the key room: joins with it"))
        self.assertFalse([f for _t, f, _w in r["plan"] if f == "Path"], "no path at his console")

    def test_vaults_a_later_path_reaches_safely(self):
        b = self.b()
        r = VP.full_plan(b, self.CARDS)
        names = dict(VP.names(b))
        third = r["plan"][2]
        self.assertEqual(third[1], "Kishara's Vault", "a currency vault where he can reach it")
        for t, f, _w in r["plan"][:3]:
            names[t] = "Reward" if f != "Key Room" else "Key Room"
        names.pop(third[0])
        self.assertTrue(VP.reachable_later(names, third[0]))
        self.assertFalse(VP.reachable_later(names, (-4, 8)), "between two wall reward rooms: opens them too")


class AtziriDoorOpenSpace(unittest.TestCase):
    """Owner (2026-11-18): Atziri's doorstep may touch a reward room "only if that reward room is placed alongside it
    in open space"."""

    def test_reward_room_alone_beside_the_doorstep(self):
        from soe2 import vaallens_plan as P
        b = {(-1, 9): "Reward"}
        self.assertFalse(P.blocked(b, P.DOOR, goal=P.ATZIRI))

    def test_reward_room_touching_other_rooms(self):
        from soe2 import vaallens_plan as P
        b = {(-1, 9): "Reward", (-2, 9): "Smithy"}
        self.assertTrue(P.blocked(b, P.DOOR, goal=P.ATZIRI))
        self.assertTrue(P.blocked({(-1, 9): "Reward"}, P.DOOR, goal=None))
