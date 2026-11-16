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
                        board["cards"] = [n for n, _y in named]
                        board["card_icons"] = V.card_icons(pic, named, 2)
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
                buglog.debug("Vaal Lens", "board " + " ".join(f"{k}={v}" for k, v in sorted(n.items())))
        self.temple_marks_sync(board)
        if self.tm_board_open or was:
            self.temple_pad_refresh()

    def _temple_steady(self, board, V, keep=3):
        """UI overhaul (feedback: "the suggestions alternate between options in a very confusing way"): one read of a
        tile can be off (a hover, an animation) - each tile shows what most of its last 3 reads said, and a tile read
        as "unknown" keeps what it was. So the plan only changes when the board really does (a card placed)."""
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
        # 2.142.0: the hand's plan - the room cards in the list and the rooms your medallions add
        plan = VP.hand_plan(board, self.temple_hand_rooms(board)) if seen else []
        plan = self._temple_plan_steady(plan, board)
        self.tm_plan = plan
        if seen and board.get("lit"):
            what = VP.card(board.get("card"))
            marks = VP.marks(board, board["lit"], what)
            marks = VP.with_plan(marks, plan, board["lit"], what, board.get("card"))
        elif seen:
            marks = VP.with_plan({}, plan, (), None)
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

    def _temple_plan_steady(self, plan, board):
        """UI overhaul: a new plan shows once two reads in a row agree on it (a card picked shows at once)."""
        key = repr(plan)
        if not plan or (board or {}).get("lit"):
            self._tm_plan_shown, self._tm_plan_next = (key, plan), None
            return plan
        shown = getattr(self, "_tm_plan_shown", None)
        if shown is None or shown[0] == key:
            self._tm_plan_shown, self._tm_plan_next = (key, plan), None
            return plan
        nxt = getattr(self, "_tm_plan_next", None)
        if nxt == key:
            self._tm_plan_shown, self._tm_plan_next = (key, plan), None
            return plan
        self._tm_plan_next = key
        return shown[1]

    def _temple_medal_look(self, full, g, ptr):
        """(a background thread) The game's picture -> what the Medallions panel shows: {"count", "hand" (names by
        slot, None = not known), "learn": (name, vec) when a slot is hovered and its tooltip read}. None: not open."""
        from . import medallions as M, remnant as RM, vaallens as V
        gx, gy = g[0], g[1]
        mb = V.side_box(g, V.MEDAL_BOX, right=True)
        pic = full.crop((mb[0] - gx, mb[1] - gy, mb[2] - gx, mb[3] - gy))
        got = M.parse([(t, (b[0] + mb[0], b[1] + mb[1], b[2] + mb[0], b[3] + mb[1])) for t, b in RM.ocr(pic) if b])
        if not got["count"] or not got["head"]:
            return {"open": False, "names": got["names"], "room": got["room"]}
        have, most = got["count"]
        s = V.placing(g)[0]
        icons = M.known_icons(self._temple_medal_file())
        hand, learn, pics = [], None, {}
        for k, sl in enumerate(M.slots(got["head"], s, have)):
            ib = M.icon_box(sl)
            vec = M.feat(full.crop((ib[0] - gx, ib[1] - gy, ib[2] - gx, ib[3] - gy)))
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
        return {"open": True, "count": (have, most), "hand": hand, "learn": learn, "room": got["room"], "icons": pics}

    def _temple_medal_file(self):
        from .config import P as data_file
        return data_file("medallion_icons.json")

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
        """-> [(mark, text)]: "1  Thaumaturge's Laboratory" ... in the board's order, then upgrade and lock."""
        from . import medallions as M, vaallens_plan as VP
        plan = getattr(self, "tm_plan", None) or []
        if not plan:
            return []
        board = getattr(self, "tm_board", None) or {}
        cards = {}
        for n in board.get("cards") or []:
            what = VP.card(n)
            if what and what[0] == "room":
                cards.setdefault(what[1], VP.card_title(n))
        hand = self.temple_medal_hand()[2]
        out = []
        n_path = sum(1 for _t, f, _w in plan if f == "Path")
        for step, (_t, fam, _why) in zip(VP.steps(plan), plan):
            if fam == "Path":                               # 2.143.0: the Architect first - one step
                if not out or out[-1][0] != str(step):
                    out.append((str(step), f"Path to the Architect ({n_path} tile{'s' if n_path != 1 else ''}), "
                                                           "then kill him"))
                continue
            src = cards.get(fam) or (fam + (" (medallion)" if any(M.base(h)[1] == fam for h in hand) else ""))
            out.append((str(step), src))
        pays = [fam for _t, fam, _w in plan if fam in ("Corruption Chamber", "Sacrificial Chamber", "Alchemy Lab")]
        if pays:
            out += [st for st in VP.combo(pays[0], hand) if st[0] != "+"]
        return out

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
            tk.Label(box, text="Open the Temple Console.", bg=P["bg"], fg=P["muted"], font=f10, anchor="w").pack(
                fill="x")
            return
        plan = self.temple_plan_lines()
        if not plan:
            tk.Label(box, text="Nothing to plan with these cards.", bg=P["bg"], fg=P["muted"], font=f10,
                     anchor="w").pack(fill="x")
        for mark, text in plan:
            tk.Label(box, text=f"{mark}  {text}", bg=P["bg"], fg=P["text"], font=f10, anchor="w", justify="left",
                     wraplength=wrap).pack(fill="x")

    def temple_pad_test(self):
        """Overlay › Helpers › Temple › Test: the Vaal Lens card now, wherever you are (its × closes it)."""
        return self.temple_pad_show()
