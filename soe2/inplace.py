"""UI rule 22 (no flicker: change in place): small helpers so a click, a tick, a typed value or a new number changes
only the widgets that changed. Nothing here reads the screen or the game."""
import tkinter as tk


def set_cfg(w, **kw):
    """w.config(...) with only the options that really differ (a label's text, a button's state or color)."""
    try:
        diff = {k: v for k, v in kw.items() if str(w.cget(k)) != str(v)}
        if diff:
            w.config(**diff)
    except tk.TclError:
        pass


def tv_sync(tv, rows, parent=""):
    """Make the Treeview's rows under `parent` equal `rows` - [(iid, {text=, values=, tags=, image=...})].
    The same rows in the same order: only the cells that differ are changed (nothing is deleted, so the scroll
    position, the selection and the focus stay). Other rows: they are built again, with the selection and the scroll
    position kept. -> True when it was done in place."""
    have = list(tv.get_children(parent))
    if have == [i for i, _kw in rows]:
        for iid, kw in rows:
            for k, v in kw.items():
                if k == "values":
                    if tuple(str(x) for x in tv.item(iid, "values")) != tuple(str(x) for x in v):
                        tv.item(iid, values=v)
                elif k == "tags":
                    if tuple(tv.item(iid, "tags")) != tuple(v):
                        tv.item(iid, tags=v)
                elif k == "image":
                    if str(tv.item(iid, "image")) != str(v):
                        tv.item(iid, image=v)
                elif str(tv.item(iid, k)) != str(v):
                    tv.item(iid, **{k: v})
        return True
    sel = [i for i in tv.selection() if tv.parent(i) == parent]
    top = tv.yview()[0]
    if have:
        tv.delete(*have)
    for iid, kw in rows:
        tv.insert(parent, "end", iid=iid, **kw)
    keep = [i for i in sel if tv.exists(i)]
    if keep:
        tv.selection_set(keep)
    if top:
        tv.yview_moveto(top)
    return False
