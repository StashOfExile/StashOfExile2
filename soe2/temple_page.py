"""2.132.1 Temple Helper - its read (GGG policy, Nov 2026: once per Read Key press - the Temple Console in a temple
area, temple_console_job), Vaal Lens (the card in Vaal Ruins and the temple: the crystals, the plan) and its row in
Overlay › Helpers (temple.py parses). Owner decision: the Vaal Beacon tooltip read in maps, the crystals on the
overlay's line and the "crystals full" alert are gone."""
import time
import tkinter as tk

from . import buglog
from . import temple as TM
from .config import SETTINGS, save_json


class TemplePage:
    """Mixed into App."""

    def temple_on(self):
        from . import features as FEAT
        return bool(TM.cfg().get("on")) and FEAT.on("overlay")     # (its one switch: Overlay › Helpers)

    def temple_set(self, on):
        TM.cfg()["on"] = bool(on)
        if not on:
            self.temple_pad_close()                         # 2.136.0
        elif getattr(self, "tm_in_temple", False) and TM.cfg().get("notepad", True):
            self.root.after_idle(self.temple_pad_show)
        save_json("settings.json", SETTINGS)
        if on:
            if getattr(self, "br_reader", None) is None:    # (the game's log says when you're in the temple)
                try:
                    self.breach_start()
                except Exception:
                    buglog.caught()
        try:
            self.overlay_capture_sync()                     # (in the temple: the bar out of captures - the count
        except Exception:                                   # under it is read)
            buglog.caught()

    def temple_seen(self, got):
        """A Temple Console read (have, most) or None (no console count there)."""
        if not got:
            return None
        old = TM.state()
        st = TM.state_set(*got)
        if not old or (old["have"], old["most"]) != got or old.get("old"):
            buglog.debug("Temple", f"crystals {got[0]}/{got[1]}")
            self.temple_pad_refresh()
        return st

    # ---------------------------------------------------------------- 2.136.0 (2.140.0: Vaal Lens)
    # A card over the game in Vaal Ruins and the temple: your crystals, what's on the Temple Console's board (read
    # off the screen while the console is open - vaallens.py), your notes in a fold. Dragged anywhere, in the overlay's
    # style; its notes and spot are kept (SETTINGS["temple"]); Helpers › Temple › Vaal Lens switches it.
    def temple_area(self, area_id):
        """Every area change: in the temple -> the notepad shows (when it's on); anywhere else -> it goes."""
        here = str(area_id or "") in TM.TEMPLE_AREAS
        if str(area_id or "") != getattr(self, "tm_area", ""):   # 3.0.6 audit: a new area - last run's board,
            self.temple_board_forget()                            # plan and marks are gone (read again)
        self.tm_in_temple = here
        self.tm_area = str(area_id or "")
        if str(area_id or "") == TM.RUN_AREA:                # 2.136.1: a run spends crystals - the number is old now
            TM.mark_old()
            self.temple_pad_refresh()
        try:
            self.overlay_capture_sync()                     # 2.136.1: the bar out of captures here (the count under it)
        except Exception:
            buglog.caught()
        if here and self.temple_on() and not getattr(self, "_tm_con_job", None):
            self._tm_con_job = self.root.after(500, self.temple_marks_tick)
        if here and self.temple_pad_on():
            self.temple_pad_show()
        elif not here:
            self.temple_pad_close()

    def temple_board_forget(self):
        """What the last read saw of the Console: forgotten (a new area) - the marks go until the next press."""
        self.tm_board, self.tm_plan, self.tm_marks, self.tm_pick = None, [], {}, None
        self._tm_hist, self._tm_plan_shown, self._tm_plan_next = {}, None, None
        self._tm_prev = None                                # (a new run: a new plan)
        mk = getattr(self, "tm_marks_win", None)
        if mk is not None:
            try:
                mk.hide()
            except Exception:
                buglog.caught()

    def temple_marks_tick(self):
        """Every 2 s in a temple area (nothing is read): Vaal Lens' marks show only while the game is in front."""
        self._tm_con_job = None
        if not getattr(self, "tm_in_temple", False) or not self.temple_on():
            return
        self._tm_con_job = self.root.after(2000, self.temple_marks_tick)
        try:
            from .overlaywin import foreground_ok
            if not foreground_ok():
                mk = getattr(self, "tm_marks_win", None)
                if mk is not None:
                    mk.hide()                                # 2.141.0: the marks only over the game
        except Exception:
            buglog.caught()

    def temple_console_job(self, ctx):
        """2.136.1 (GGG policy: on a Read Key press in a temple area): the Temple Console's "18/60" under its Run Temple
        button (the bar is out of captures there, so it sees under it); with Vaal Lens on, the board and the Medallions
        panel too - all from the press's one picture. No console open = nothing read, nothing changed."""
        if not getattr(self, "tm_in_temple", False) or not self.temple_on():
            return None
        from . import screenread as SR
        g = ctx["g"]
        box = TM.console_box(g)
        st = TM.state()
        most = st["most"] if st else None
        # 2.140.0 Vaal Lens: the board is read while the card shows (GGG policy: each Read Key press).
        # 2.142.0: in the temple too (the console opens there), from one picture of the game; the Medallions panel
        # (V) is read each look while the card shows - its count, and a hovered slot's name with the slot under the mouse
        if not self.temple_pad_shown() and self.temple_pad_on():
            self.temple_pad_show()          # 3.0.6 (owner: "turned off after the run"): a press here brings it back
        lens = self.temple_pad_shown()
        lens_any = lens
        gx, gy, gw, gh = g
        ptr = ctx.get("ptr")
        covered = self._temple_covered(g)

        def work():
            from . import remnant as RM
            board, medal = None, None
            try:
                full = SR.capture((gx, gy, gx + gw, gy + gh), "Vaal Lens") if lens else None
                img = full.crop((box[0] - gx, box[1] - gy, box[2] - gx, box[3] - gy)) if full else \
                    SR.capture(box, "Temple")
                if img is None:
                    return None, None, None, None
                img = img.resize((img.width * 3, img.height * 3))      # small digits read better bigger
                lines = RM.ocr(img)
                got = TM.parse_console(lines, most)
            except Exception as e:
                buglog.caught()
                return None, e.__class__.__name__, None, None
            if not lens:
                return got, lines, None, None
            from . import vaallens as V
            try:
                medal = self._temple_medal_look(full, g, ptr)
            except Exception:
                buglog.caught()
            if got or lens_any:
                try:
                    board = V.read(V.frame(full))
                    # 2.141.0: a card picked (the game lights its tiles) - its name, from the card list
                    # (2.142.0: several cards there - the picked one glows)
                    # (2.142.0: every card in the list is read - the hand's plan uses them all)
                    if V.seen(board):
                        cb = V.card_box(g)
                        pic = full.crop((cb[0] - gx, cb[1] - gy, cb[2] - gx, cb[3] - gy))
                        cl = RM.ocr(pic.resize((pic.width * 2, pic.height * 2)))
                        named = V.card_names(cl)
                        by_row = V.card_rows_read(pic, RM.ocr, cl)
                        if len(by_row) > len(named):
                            named = by_row
                        board["cards"] = [n for n, _y in named]
                        # 3.0.6 (owner: inside the temple, V opens the console only to look - no Room Cards list):
                        # with no list there's nothing to place, so no plan (the Architect's reward rooms bring it)
                        board["placing"] = bool(named) or any(
                            "room cards" in " ".join(str(t).lower().split()) for t, _b in cl or [])
                        board["card_icons"] = V.card_icons(pic, named, 2)
                        # 3.0.6 (owner: "a number on the room card on the left"): each card's spot on screen
                        sc = pic.height / (V.CARD_BOX[3] - V.CARD_BOX[1])
                        board["card_rows"] = [(n, (cb[0] + (V.DIAMOND_X[1] + 24) * sc, cb[1] + y / 2))
                                              for n, y in named]
                        if medal and medal.get("open"):
                            self._temple_medal_cards(medal, pic, named, sc)
                        if board.get("lit"):
                            board["card"] = V.card_pick(pic, cl, 2)
                except Exception:
                    buglog.caught()
            return got, lines, board, medal

        def done(res):
            got, seen, board, medal = res or (None, None, None, None)
            if medal is not None:
                self.temple_medal_seen(medal)
            if board is not None:
                self.temple_board_seen(board, covered)
            if got:
                self.temple_seen(got)
                return
            # 2.136.2: why nothing was read, at most once a minute (the box holds only the count: no names)
            if seen and time.time() - getattr(self, "_tm_con_said", 0.0) > 60:
                self._tm_con_said = time.time()
                txt = seen if isinstance(seen, str) else " | ".join(str(t) for t, _b in seen)[:60]
                buglog.debug("Temple", f"console count not read: {txt}")
        return "Temple", work, done

    def temple_pad_on(self):
        return self.temple_on() and bool(TM.cfg().get("notepad", True))

    def temple_pad_set(self, on):
        TM.cfg()["notepad"] = bool(on)
        save_json("settings.json", SETTINGS)
        if on and getattr(self, "tm_in_temple", False) and self.temple_on():
            self.temple_pad_show()
        elif not on:
            self.temple_pad_close()

    def temple_pad_shown(self):
        w = getattr(self, "tm_pad", None)
        try:
            return w is not None and w.winfo_exists()
        except tk.TclError:
            return False

    def temple_pad_close(self):
        self._temple_pad_keep()
        mk = getattr(self, "tm_marks_win", None)
        if mk is not None:
            mk.hide()
        w, self.tm_pad = getattr(self, "tm_pad", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def _temple_pad_keep(self):
        t = getattr(self, "tm_pad_text", None)
        try:
            if t is not None and t.winfo_exists():
                TM.cfg()["notes"] = t.get("1.0", "end-1c")
                save_json("settings.json", SETTINGS)
        except tk.TclError:
            pass

    def temple_pad_line(self):
        """2.136.2 (feedback: "it shouldn't say that, it should just be reading my crystals"): the count only."""
        return TM.count_text(TM.state())

    def _temple_covered(self, g):
        """2.142.2 (feedback: the marks and the card should show in screen shares - so the screen reader sees them
        too): the tiles under our own marks and card right now; their last read is kept."""
        from . import vaallens as V
        import sys
        if sys.platform == "win32":                     # 3.0.6: the press's picture sees through our windows
            return set()                                # (screenread.see_through) - nothing is covered
        out = set()
        mk = getattr(self, "tm_marks_win", None)
        if mk is not None and mk.shown():
            out |= set(getattr(self, "tm_marks", None) or {})
        pad = getattr(self, "tm_pad", None)
        try:
            if pad is not None and pad.winfo_exists() and pad.winfo_ismapped():
                l, t = pad.winfo_rootx(), pad.winfo_rooty()
                r, b = l + pad.winfo_width(), t + pad.winfo_height()
                s = V.placing(g)[0]
                for c in V.CELLS:
                    x, y = V.on_screen(g, *V.xy(*c))
                    if l - 70 * s <= x <= r + 70 * s and t - 60 * s <= y <= b + 60 * s:
                        out.add(c)
        except tk.TclError:
            pass
        return out

    def temple_board_seen(self, board, covered=()):
        """2.140.0: a look at the screen in Vaal Ruins: the console open = its board is kept and the card follows.
        2.142.2: tiles under our own marks or card keep their last read; their lit state only while another tile is
        lit (a card is still picked)."""
        from . import vaallens as V
        prev = getattr(self, "tm_board", None)
        if covered and prev and V.seen(board):
            others = [c for c in board.get("lit") or [] if c not in covered]
            for c in covered:
                if c in prev:
                    board[c] = prev[c]
            board["lit"] = others + ([c for c in prev.get("lit") or [] if c in covered] if others else [])
        icons = dict(getattr(self, "tm_icons", None) or {})
        icons.update(board.get("card_icons") or {})
        self.tm_icons = icons
        was = getattr(self, "tm_board_open", False)
        self.tm_board_open = V.seen(board)
        if self.tm_board_open:
            self._temple_steady(board, V)
        else:
            self._tm_hist = {}
        if self.tm_board_open:
            self.tm_board = board
            n = V.summary(board)
            if n != getattr(self, "_tm_board_said", None):
                self._tm_board_said = n
                buglog.debug("Vaal Lens", "board " + " ".join(f"{k}={v}" for k, v in sorted(n.items())) +
                             " | cards: " + ", ".join(board.get("cards") or []))
        self.temple_marks_sync(board)
        if self.tm_board_open or was:
            self.temple_pad_refresh()

    def _temple_steady(self, board, V, keep=1):
        """UI overhaul (feedback: "the suggestions alternate between options in a very confusing way"): a tile read
        as "unknown" keeps what it was. 3.0.6 audit: one read per Read Key press - each press's read counts at once
        (it took the most of the last 3 reads, from when the board was read on a timer: a card placed took 2 presses)."""
        hist = self.__dict__.setdefault("_tm_hist", {})
        for c in V.CELLS:
            cell = board.get(c)
            if not isinstance(cell, dict):
                continue
            h = hist.setdefault(c, [])
            if cell.get("kind", "unknown") != "unknown":
                h.append(dict(cell))
                del h[:-keep]
            if not h:
                continue
            kinds = [x.get("kind") for x in h]
            best = max(set(kinds), key=lambda k: (kinds.count(k), kinds[::-1].index(k) * -1))
            if cell.get("kind") != best or cell.get("kind", "unknown") == "unknown":
                board[c] = dict(next(x for x in reversed(h) if x.get("kind") == best))

    def temple_marks_sync(self, board=None):
        """2.141.0: a picked card's lit tiles -> 1 / 2 and ✕ over the game (vaallens_marks); none = none drawn."""
        from . import vaallens as V, vaallens_plan as VP
        marks = {}
        board = board if board is not None else getattr(self, "tm_board", None)
        seen = bool(board and V.seen(board) and self.temple_pad_shown())
        if seen and board.get("placing") is False:
            seen = False                                # (looking only: medallions are still read, no plan)
        # 3.0.6 (owner, TEMPLE_RULES.md): the full plan - key room and Atziri, the Architect, then every room in hand
        # by quadrant; and where the upgrade and the lock medallions go
        if seen:
            from . import medallions as M
            have, _most, medals = self.temple_medal_hand()
            medals = medals[:have or 0]
            rooms_ = [M.base(h)[1] for h in medals if h and M.base(h)[1]]
            from collections import Counter
            hand = Counter([VP.card(n) for n in board.get("cards") or [] if VP.card(n)] + [("med", f) for f in rooms_])
            prev = getattr(self, "_tm_prev", None)
            # 3.0.6 (owner: "too many changed decisions happening per each card I place"): while the hand only gets
            # smaller (cards placed), the last plan's steps stay; new cards are planned after them
            keep = prev[0] if prev and not (hand - prev[1]) else ()
            full = VP.full_plan(board, board.get("cards") or [], medals, rooms_, prev=keep)
            self._tm_prev = (full["plan"], hand)
        else:
            full = {"plan": [], "targets": {}, "notes": []}
        plan = self._temple_plan_steady(full["plan"], board)
        self.tm_plan, self.tm_targets, self.tm_notes = plan, full["targets"], full["notes"]
        if seen and board.get("lit") and VP.card(board.get("card")) == ("path", None):
            # 3.0.6 (owner: "It wants me to place a path where I cannot place a path"): a path card's shape decides
            # where it fits - the game lights those squares; none of the planned ones lit = this card doesn't fit
            want = [t for t, f, _w in plan if f == "Path"]
            if want and not set(want) & set(board["lit"]):
                self.tm_notes = ["This Path card's shape doesn't fit the planned squares: pick your other Path "
                                 "card."] + list(self.tm_notes)
        if seen and board.get("lit"):
            what = VP.card(board.get("card"))
            marks = VP.marks(board, board["lit"], what)
            marks = VP.with_plan(marks, plan, board["lit"], what, board.get("card"))
        elif seen:
            marks = VP.with_plan({}, plan, (), None)
        for t, (word, fam) in (self.tm_targets if seen else {}).items():
            if t not in marks or marks[t][0] == "p":
                marks[t] = ("do", (word, fam))           # (an upgrade / lock medallion: which room it goes on)
        if seen and plan:
            marks.update(self._temple_step_labels(board, plan))
        self.tm_marks = marks
        self.tm_pick = (board or {}).get("card") if marks and board.get("lit") else None
        mk = getattr(self, "tm_marks_win", None)
        try:
            from .alerts_page import game_rect
            g = game_rect() if marks else None
            if marks and g:
                if mk is None:
                    from .vaallens_marks import Marks
                    mk = self.tm_marks_win = Marks(self.root)
                from .overlaywin import pal
                chain = VP.architect_chain(board) if board and V.seen(board) else None
                mk.show(g, marks, pal(), getattr(self, "tm_icons", None), chain)
            elif mk is not None:
                mk.hide()
        except Exception:
            buglog.caught()

    def _temple_step_labels(self, board, plan):
        """3.0.6 (owner: "a number on the room card on the left, and then number the square ... factor for my
        medallions also"): each step's number beside the card (or the medallion) that does it -> {("@", x, y):
        ("lbl", step)} at screen points. A path step takes one path card per tile."""
        from . import medallions as M, vaallens_plan as VP
        rows = [(VP.card(n), xy) for n, xy in (board or {}).get("card_rows") or []]
        slots = [(M.base(h)[1] if h else None, box) for h, box in getattr(self, "tm_medal_boxes", None) or []]
        used, out = set(), {}
        for step, (_t, fam, _w) in zip(VP.steps(plan), plan):
            rw = VP.card(fam) if fam not in ("Path", "Key Room") else None
            want = ("path", None) if fam == "Path" else ("key", None) if fam == "Key Room" else \
                rw if rw and rw[0] == "reward" else ("room", fam)
            k = next((i for i, (w, _xy) in enumerate(rows) if w == want and ("c", i) not in used), None)
            if k is not None:
                used.add(("c", k))
                x, y = rows[k][1]
                out[("@", int(x), int(y))] = ("lbl", step)
                continue
            if want[0] == "room":
                k = next((i for i, (room, _b) in enumerate(slots) if room == fam and ("m", i) not in used), None)
                if k is not None:
                    used.add(("m", k))
                    b = slots[k][1]
                    out[("@", int(b[0] + 14), int(b[1] + 14))] = ("lbl", step)
        return out

    def _temple_plan_steady(self, plan, board):
        """3.0.6 audit: each press's plan shows at once (it waited for two reads in a row to agree - from the timed
        reads; with one read per press that took two presses)."""
        self._tm_plan_shown, self._tm_plan_next = (repr(plan), plan), None
        return plan

    def _temple_medal_look(self, full, g, ptr):
        """(a background thread) The game's picture -> what the Medallions panel shows: {"count", "hand" (names by
        slot, None = not known), "learn": (name, vec) when a slot is hovered and its tooltip read}. None: not open."""
        from . import medallions as M, remnant as RM, vaallens as V
        gx, gy = g[0], g[1]
        mb = V.side_box(g, V.MEDAL_BOX, right=True)
        pic = full.crop((mb[0] - gx, mb[1] - gy, mb[2] - gx, mb[3] - gy))
        lines = [(t, (b[0] + mb[0], b[1] + mb[1], b[2] + mb[0], b[3] + mb[1])) for t, b in RM.ocr(pic) if b]
        got = M.parse(lines)
        if not got["head"]:
            # 3.0.6 (owner's 6/6 panel read "MEDALLIONS (616)"): the title alone is enough - the slots are counted
            # from the picture, not the number
            got["head"] = next((b for t, b in lines if "MEDALLIONS" in M.letters(t) and len(M.letters(t)) <= 14),
                               None)
        if not got["head"]:
            return {"open": False, "names": got["names"], "room": got["room"]}
        s = V.placing(g)[0]
        filled = [sl for sl in M.slots(got["head"], s, 6) if M.slot_filled(
            full.crop(tuple(int(v) - o for v, o in zip(M.icon_box(sl), (gx, gy, gx, gy)))))]
        have = len(filled)
        most = got["count"][1] if got["count"] else max(have, (TM.cfg().get("medals") or {}).get("most") or 0, 3)
        icons = M.known_icons(self._temple_medal_file())
        hand, learn, pics, boxes, vecs = [], None, {}, [], []
        for k, sl in enumerate(filled):
            ib = M.icon_box(sl)
            vec = M.feat(full.crop((ib[0] - gx, ib[1] - gy, ib[2] - gx, ib[3] - gy)))
            boxes.append(sl)
            vecs.append(vec)
            who = M.identify(vec, icons)
            if who is None:                                 # 2.142.1: a room medallion shows its room's icon
                room = M.room_from_icon(full, sl, origin=(gx, gy))
                who = f"Uromoti's Medallion: {room}" if room else None
                if room:                                    # 2.142.2: its picture, for the board's marks
                    pics[room] = full.crop((ib[0] - gx, ib[1] - gy, ib[2] - gx, ib[3] - gy))
            hand.append(who)
            if ptr and sl[0] <= ptr[0] <= sl[2] and sl[1] <= ptr[1] <= sl[3] and got["names"]:
                n = got["names"][0][0]
                if n == "Uromoti's Medallion" and got["room"]:     # (its picture is its room's: kept by room)
                    n = f"{n}: {got['room']}"
                learn = (n, vec, k)
        return {"open": True, "count": (have, most), "hand": hand, "learn": learn, "room": got["room"], "icons": pics,
                "boxes": boxes, "vecs": vecs}

    def _temple_medal_cards(self, medal, pic, named, sc):
        """(the background thread) A room medallion not known by its room's board picture: its picture against the
        room cards in the list (3.0.6, owner's 4/6 panel: a Sealed Vault medallion matched its card at 0.86)."""
        from . import medallions as M, vaallens as V, vaallens_plan as VP
        cx, r = (V.DIAMOND_X[0] + V.DIAMOND_X[1]) / 2 * sc, 32 * sc
        feats = []
        for n, y in named:
            what = VP.card(n)
            if what and what[0] == "room":
                y1 = y / 2
                feats.append((what[1], M.feat(pic.crop((int(cx - r), int(y1 - r), int(cx + r), int(y1 + r))),
                                              inner=False)))
        for k, (who, vec) in enumerate(zip(medal["hand"], medal.get("vecs") or [])):
            if who is not None or not feats:
                continue
            sims = sorted(((float(vec @ f), fam) for fam, f in feats), reverse=True)
            others = [x for x in sims if x[1] != sims[0][1]]
            if sims[0][0] >= 0.8 and (not others or sims[0][0] - others[0][0] >= 0.07):
                medal["hand"][k] = f"Uromoti's Medallion: {sims[0][1]}"

    def _temple_medal_file(self):
        from .config import P as data_file
        return data_file("medallion_icons_v2.json")       # (3.0.6: the middle of the icon - the old file is set aside)

    def temple_medal_seen(self, medal):
        """The panel read: the hand is kept (names only); a hovered slot teaches its picture."""
        from . import medallions as M
        c = TM.cfg()
        if not medal.get("open"):
            return
        learn = medal.get("learn")
        hand = list(medal.get("hand") or [])
        if learn:
            name, vec, k = learn
            try:
                M.learn(self._temple_medal_file(), name, vec)
            except OSError:
                buglog.caught()
            if k < len(hand):
                hand[k] = name
            buglog.debug("Vaal Lens", f"medallion slot {k + 1} learned")
        if medal.get("icons"):
            icons = dict(getattr(self, "tm_icons", None) or {})
            icons.update(medal["icons"])
            self.tm_icons = icons
        have, most = medal["count"]
        old = c.get("medals") or {}
        vecs = list(medal.get("vecs") or [])
        was = getattr(self, "_tm_medal_vecs", None) or []
        if old.get("have") == have and len(old.get("hand") or []) == len(hand) and len(was) == len(vecs):
            # 3.0.6: a slot known stays known (same count) - only while its picture is the same (owner: a
            # Zantipi's swapped for a Synthflesh Lab at 6/6 was still called "Waystone modifier")
            hand = [h or (o if w is not None and float(v @ w) >= 0.95 else None)
                    for h, o, v, w in zip(hand, old["hand"], vecs, was)]
        self._tm_medal_vecs = vecs
        buglog.debug("Vaal Lens", f"medallions {have}/{most}: " + ", ".join(h or "?" for h in hand))
        self.tm_medal_boxes = list(zip(hand, medal.get("boxes") or []))     # 3.0.6: where each slot is (its step)
        new = {"have": have, "most": most, "hand": hand}
        if new != c.get("medals"):
            c["medals"] = new
            save_json("settings.json", SETTINGS)
            self.temple_pad_refresh()

    def temple_medal_hand(self):
        m = TM.cfg().get("medals") or {}
        return m.get("have"), m.get("most"), list(m.get("hand") or [])

    def temple_medal_drop(self, name, room=None):
        """A medallion seen on the ground (the screen reader, in the temple) -> take it or leave it (an alert card,
        once a minute per name)."""
        from . import medallions as M
        seen = getattr(self, "_tm_medal_said", {})
        if time.time() - seen.get(name, 0.0) < 60:
            return None
        have, most, hand = self.temple_medal_hand()
        st = TM.state()
        got = M.advice(name, hand, have, most, room, st["most"] if st else None)
        buglog.debug("Vaal Lens", f"on the ground: {name}{' (' + room + ')' if room else ''} -> "
                                  f"{got[0] if got else 'no advice'} ({have}/{most})")
        if not got:
            return None
        seen[name] = time.time()
        self._tm_medal_said = seen
        verdict, line = got
        title = {"take": "Take it", "skip": "Leave it", "learn": "Medallions full"}[verdict]
        mark = {"take": "▲", "skip": "–", "learn": "?"}[verdict]
        from . import alertcard
        from .alerts_page import game_rect
        self.tm_medal_win = alertcard.show(self.root, title, line, color="#d9a441", mark=mark, secs=8,
                                           game=game_rect(), tag="Vaal Lens", rank=3)
        return verdict

    def temple_hand_rooms(self, board):
        """-> the room families in hand: each room card in the list, and each medallion that adds a room."""
        from . import medallions as M, vaallens_plan as VP
        out = []
        for n in (board or {}).get("cards") or []:
            what = VP.card(n)
            if what and what[0] == "room":
                out.append(what[1])
        have, _most, hand = self.temple_medal_hand()
        for h in hand[:have or 0]:
            room = M.base(h)[1]
            if room:
                out.append(room)
        return out

    def temple_plan_lines(self):
        """-> [(mark, text)]: the plan's steps in order ("1  Path to the key room (2 tiles)", "2  Thaumaturge's
        Laboratory" ...), then where the medallions go, then the notes (3.0.6, TEMPLE_RULES.md)."""
        from . import medallions as M, vaallens_plan as VP
        plan = getattr(self, "tm_plan", None) or []
        board = getattr(self, "tm_board", None) or {}
        cards = {}
        for n in board.get("cards") or []:
            what = VP.card(n)
            if what and what[0] == "room":
                cards.setdefault(what[1], VP.card_title(n))
        hand = self.temple_medal_hand()[2]
        out = []
        for step, (_t, fam, why) in zip(VP.steps(plan), plan):
            if fam == "Path":
                if not out or out[-1][0] != str(step):
                    n = sum(1 for _x, f, w in plan if f == "Path" and w == why)
                    tail = ", then kill him" if why == "the Architect" else ""
                    tiles = f"{n} tile{'s' if n != 1 else ''}"
                    out.append((str(step), f"Spare paths as filler ({tiles}): lost first when rooms destabilize"
                                if why == "filler" else f"Path to {why} ({tiles}){tail}"))
                continue
            if fam == "Key Room":
                out.append((str(step), "Royal Access Chamber"))
                continue
            src = cards.get(fam) or (fam + (" (medallion)" if any(M.base(h)[1] == fam for h in hand) else ""))
            out.append((str(step), src))
        for _t, (word, fam) in (getattr(self, "tm_targets", None) or {}).items():
            out.append(("▲" if word == "Upgrade" else "■", f"{word}: {fam}"))
        if not getattr(self, "tm_targets", None):
            pays = [fam for _t, fam, _w in plan if fam in ("Corruption Chamber", "Sacrificial Chamber", "Alchemy Lab")]
            if pays:
                out += [st for st in VP.combo(pays[0], hand) if st[0] != "+"]
        # 3.0.6 (owner: "most people probably aren't going to read the plan, it needs to be more concise"): the two
        # notes that matter most
        out += [("!", n) for n in (getattr(self, "tm_notes", None) or [])[:2]]
        return out

    def temple_medal_line(self):
        """The card's medallions line: "Medallions 3/6: Lock, Upgrade, 1 not known" (3.0.6, owner: "medallion card not
        seen") - or how to read them."""
        from . import medallions as M
        have, most, hand = self.temple_medal_hand()
        if not most:
            return f"Medallions: open them (V) and press {self.look_key_text()}."
        # 3.0.6 (owner: "one vertical list instead of a wall of text, a list only of the names"): a room medallion by
        # its room, the rest by what they do (Lock, Upgrade ...)
        known = [M.base(h)[1] or M.MEDALLIONS.get(M.base(h)[0], (M.base(h)[0],))[0] for h in hand[:have] if h]
        unknown = have - len(known)
        tail = [f"? {unknown} not known: hover it, press {self.look_key_text()}"] if unknown else []
        return "\n".join([f"Medallions {have}/{most}"] + known + tail)

    def temple_pad_show(self):
        if self.temple_pad_shown():
            return self.tm_pad
        from .overlaywin import OverlayWindow, pal
        P = pal()
        c = TM.cfg()
        if c.get("pad_x") is None or c.get("pad_y") is None:
            from .alerts_page import game_rect
            r = game_rect() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
            x, y = r[0] + int(r[2] * 0.02), r[1] + int(r[3] * 0.18)
        else:
            x, y = int(c["pad_x"]), int(c["pad_y"])

        def moved(nx, ny, ww, hh):
            c.update(pad_x=int(nx), pad_y=int(ny), pad_w=int(ww), pad_h=int(hh))
            save_json("settings.json", SETTINGS)
        w = OverlayWindow(self.root, "Vaal Lens", "◆", (x, y, c.get("pad_w") or 300, None),
                          palette=P, locked=bool(self.tracker_cfg().get("mlocked")), on_lock=self.overlay_lock,
                          on_close=self.temple_pad_close, on_moved=moved, follow_game=True, min_size=(220, 160))
        w.withdraw()
        f9, f10 = (P["font"], self.ov_font(9)), (P["font"], self.ov_font(10))
        body = tk.Frame(w.body, bg=P["bg"], padx=8, pady=8)
        body.pack(fill="both", expand=True)
        top = tk.Frame(body, bg=P["bg"])
        top.pack(fill="x")
        self.tm_pad_head = tk.Label(top, text=self.temple_pad_line(), bg=P["bg"], fg=P["head"],
                                    font=(P["font"], self.ov_font(10), "bold"), anchor="w", justify="left",
                                    wraplength=max(140, int(c.get("pad_w") or 300) - 70))
        self.tm_pad_head.pack(side="left")
        tk.Label(top, text="BETA", bg=P["bg"], fg=P["muted"], font=(P["font"], self.ov_font(8), "bold"),
                 highlightthickness=1, highlightbackground=P["line"], padx=4).pack(side="right")
        # 2.141.0: crystals as pips (one per run's worth, 6 each) under the count
        self.tm_pad_pips = self._temple_pips(body, P)
        # 2.142.2 (feedback: "all of this filler detail is overwhelming, we're meant to simplify temple"): the plan,
        # in steps matching the numbers on the board - nothing else
        tk.Frame(body, bg=P["head"], height=2).pack(fill="x", pady=(8, 0))
        hd = tk.Frame(body, bg=P["bg"])
        hd.pack(fill="x", pady=(8, 0))
        tk.Label(hd, text="THE PLAN", bg=P["bg"], fg=P["muted"], font=(P["font"], self.ov_font(8), "bold"),
                 anchor="w").pack(side="left")
        tip = tk.Label(hd, text=" ⓘ", bg=P["bg"], fg=P["muted"], font=(P["font"], self.ov_font(8)))
        tip.pack(side="left")
        from .style import Tooltip
        Tooltip(tip, "On the board: each card's picture where it goes, numbered in order. A solid frame: where the "
                     "card you picked goes. ✕: not there - it touches a reward room.")
        self.tm_plan_tip = tip
        self.tm_lens_box = tk.Frame(body, bg=P["bg"])
        self.tm_lens_box.pack(fill="x")
        # notes in a fold (feedback: "maybe a dropdown clickable thing if someone wants to add notes to it")
        fold = tk.Label(body, bg=P["bg"], fg=P["muted"], font=(P["font"], self.ov_font(8), "bold"), anchor="w",
                        cursor="hand2")
        fold.pack(fill="x", pady=(8, 0))
        t = tk.Text(body, bg=P.get("field") or P["cell_bg"], fg=P["text"], insertbackground=P["text"], relief="flat",
                    highlightthickness=1, highlightbackground=P["line"], wrap="word", height=4, width=1, font=f10, padx=8,
                    pady=4)                         # (width=1: it fills the card - 80 characters stretched it off screen)
        t.insert("1.0", c.get("notes") or "")
        t.bind("<FocusOut>", lambda _e: self._temple_pad_keep(), add="+")
        t.bind("<KeyRelease>", lambda _e: self._temple_pad_soon(), add="+")

        def show_notes(open_):
            fold.config(text="NOTES ▾" if open_ else "NOTES ▸")
            if open_:
                t.pack(fill="both", expand=True)
            else:
                t.pack_forget()

        def flip(_e=None):
            c["notes_open"] = not c.get("notes_open")
            save_json("settings.json", SETTINGS)
            show_notes(c["notes_open"])
        c.setdefault("notes_open", bool((c.get("notes") or "").strip()))
        fold.bind("<Button-1>", flip)
        show_notes(c["notes_open"])
        self.tm_pad, self.tm_pad_text, self.tm_pad_fold = w, t, fold
        self.temple_pad_refresh()
        w.show()                    # (2.142.2: seen in screen shares; the tiles under it keep their last read)
        return w

    def _temple_pad_soon(self):
        job = getattr(self, "_tm_pad_job", None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._tm_pad_job = self.root.after(800, self._temple_pad_keep)

    def temple_pad_restyle(self):
        """The overlay's style or lock changed: built again, where it was."""
        if self.temple_pad_shown():
            self.temple_pad_close()
            self.temple_pad_show()

    def _temple_pips(self, parent, P):
        """A row of pill pips (a canvas); its .fill = (n, of) is drawn at the canvas's width."""
        cv = tk.Canvas(parent, bg=P["bg"], height=12, highlightthickness=0, bd=0)
        cv.pack(fill="x", pady=(4, 0))
        cv.fill = (0, 0)

        def draw(_e=None):
            cv.delete("all")
            n, of = cv.fill
            if not of:
                return
            w = max(40, cv.winfo_width())
            gap, r = 5, 4
            step = (w - 2 * r + gap) / of
            for k in range(of):
                x0 = r + k * step
                cv.create_line(x0, 6, x0 + step - gap - r, 6, width=2 * r, capstyle="round",
                               fill=P["head"] if k < n else P["line"])
        cv.redraw = draw
        cv.bind("<Configure>", draw)
        return cv

    def temple_pad_refresh(self):
        """The crystals line and the board follow each new read."""
        lab = getattr(self, "tm_pad_head", None)
        try:
            if lab is not None and lab.winfo_exists():
                lab.config(text=self.temple_pad_line())
            pips = getattr(self, "tm_pad_pips", None)
            if pips is not None and pips.winfo_exists():
                st = TM.state()
                pips.fill = (TM.runs(st), (st["most"] // TM.RUN) if st else 0)
                pips.redraw()
        except tk.TclError:
            pass
        box = getattr(self, "tm_lens_box", None)
        try:
            if box is None or not box.winfo_exists():
                return
        except tk.TclError:
            return
        from .overlaywin import pal
        P = pal()
        for k in box.winfo_children():
            k.destroy()
        f10 = (P["font"], self.ov_font(10))
        wrap = max(180, int(TM.cfg().get("pad_w") or 300) - 24)
        if not getattr(self, "tm_board", None):
            tk.Label(box, text=f"Open the Temple Console, then press {self.look_key_text()}.", bg=P["bg"],
                     fg=P["muted"], font=f10, anchor="w", wraplength=wrap, justify="left").pack(fill="x")
            return
        plan = self.temple_plan_lines()
        if not plan and (self.tm_board or {}).get("placing") is False:
            tk.Label(box, text="No Room Cards open: nothing to place. Your medallions are below.", bg=P["bg"],
                     fg=P["muted"], font=f10, anchor="w", wraplength=wrap, justify="left").pack(fill="x")
        elif not plan:
            tk.Label(box, text="Nothing to plan with these cards.", bg=P["bg"], fg=P["muted"], font=f10,
                     anchor="w").pack(fill="x")
        tk.Label(box, text=self.temple_medal_line(), bg=P["bg"], fg=P["muted"], font=f10, anchor="w",
                 justify="left", wraplength=wrap).pack(fill="x", side="bottom", pady=(8, 0))
        for mark, text in plan:
            tk.Label(box, text=f"{mark}  {text}", bg=P["bg"], fg=P["text"], font=f10, anchor="w", justify="left",
                     wraplength=wrap).pack(fill="x")

    def temple_pad_test(self):
        """Overlay › Helpers › Temple › Test: the Vaal Lens card now, wherever you are (its × closes it)."""
        return self.temple_pad_show()
