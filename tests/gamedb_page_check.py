"""Run by tests/test_gamedb.py in its own process: Game Search's page with the game database's categories."""
import json
import os
import sys
import tempfile
import tkinter as tk

HOME = tempfile.mkdtemp(prefix="soe2-gamedb-page-")
for k in ("HOME", "APPDATA", "USERPROFILE"):
    os.environ[k] = HOME
os.environ["SOE2_TRADE_API"] = "http://127.0.0.1:9/api/trade2"
os.environ["SOE2_NINJA"] = "http://127.0.0.1:9"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from soe2 import __version__, config, names      # noqa: E402

os.makedirs(config.DATA_DIR, exist_ok=True)
with open(os.path.join(config.DATA_DIR, "settings.json"), "w") as f:
    json.dump({"labs": True, "seen_version": __version__, "quickstart_done": True, "share_asked": True,
               "board_name_asked": True, "lb_name_asked": True, "wealth_setup_seen": True, "check_updates": False,
               "league": "Standard", "desecrate": {"asked": True}, "tracker": {"chips_asked": True}}, f)
from soe2.app import App                          # noqa: E402

root = tk.Tk()
app = App(root)
root.geometry("1500x1000+0+0")


def pump(n=15):
    for _ in range(n):
        root.update()


def labels(w):
    out = []
    for c in w.winfo_children():
        if isinstance(c, tk.Label):
            out.append(str(c.cget("text")))
        out += labels(c)
    return out


pump(30)
app.shell.open("search")
pump(20)
labs = labels(app.gs_chips)
for g in names.GAME_SEARCH_GROUPS:
    assert g in labs, g
assert "94" in labs and "54" in labs, labs


def drawn():
    cv = app.gs_cards.canvas
    return "\n".join(cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text")


app.gs_pick("Waystones")
pump()
assert app.gs_cards.winfo_ismapped() and not app.gs_text.winfo_ismapped()        # cards, not the text
assert "Waystone (Tier 15)" in app.gs_cards.texts()
assert "Waystone Drop Chance" in drawn()
assert not any(h[4][0] == "wiki" for h in app.gs_cards._hits)                      # (database rows have no wiki link)
app.gs_q.set("painful")
app._gs_go()
pump()
t = drawn()
assert "(5—24)% increased Monster Damage" in t.replace("Painful", "Painful") or "(5—24)%" in t, t
assert "more ›" in t and "Source:" not in t, t
r = app.gs_last[0]
app.gs_toggle(r["n"] + "|" + r["g"])
pump()
t = drawn()
assert "Source: regexdata.json waystone · Game 0.5.5" in t, t
assert "Row id" not in t and "Trade stat" not in t and "explicit.stat_" not in t, t     # (not drawn: right-click copies the id)
rid = r["id"]
assert rid == "waystone/mod/increased-monster-damage" and app.gs_cards.row_at(type("E", (), {"y": 5})) is not None
app.gs_cards.copy_id(rid)
assert root.clipboard_get() == rid
assert "explicit.stat_" in r["t"] or "trade stat" in r["t"].lower()                    # (still searchable)
# an item row from the export: kind, properties with the unit fixed, "Requires Level 1", and a wiki link
app.gs_active = "Armour"
app.gs_q.set("rusted cuirass")
app._gs_go()
pump()
t = drawn()
assert "Body Armour · Strength" in t and "\u22125%" in t and "Requires Level 1" in t, t
assert "-500" not in t and "str_armour" not in t and "ezomyte_basetype" not in t, t
assert any(h[4][0] == "wiki" for h in app.gs_cards._hits)
# the empty page is still the text
app.gs_clear()
app.gs_active = None
pump()
assert app.gs_text.winfo_ismapped() and not app.gs_cards.winfo_ismapped()
root.destroy()
print("ok")
