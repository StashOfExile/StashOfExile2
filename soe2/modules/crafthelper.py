from . import Module


class CraftHelper(Module):
    """UI overhaul: was a Money Makers tab; its own page under Earn."""
    key, title, short, icon, kind = "crafthelper", "Craft Helper", "Craft", "⚒", "module"
    labs = True
    blurb = "Copy a tablet or jewel: each mod gets a letter, S to F, and the item a next step - no prices."

    def build(self, body):
        import tkinter as tk
        from ..style import C
        page = tk.Frame(body, bg=C["panel"])
        page.pack(fill="both", expand=True)
        self.app.mm_build_tablets(page)

    def on_show(self):
        self.app.mm_tab_fill()
