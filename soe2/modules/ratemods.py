from . import Module
from ..ratemods_page import INTRO


class RateMods(Module):
    """2.120.0 (UX pass 2, feedback: the Rate mods window drew badly and sat in Privacy & community): its own page.
    Owner (Rate Mods redesign): in the Mods group - One at a Time (the sets on the left, a card on the right) and
    Table (many mods at once)."""
    key, title, short, icon, kind = "ratemods", "Rate Mods", "Rate Mods", "⭐", "tool"
    parent = None                      # owner: its own row in Mods (was in Trade, a child of Price Checks before that)
    blurb = INTRO                      # owner: the page's one intro line, under its title (more in its ⓘ: blurb_tip)

    def blurb_tip(self):
        from ..ratemods_page import INTRO_TIP
        return INTRO_TIP

    def build(self, body):
        self.app.build_ratemods_page(body)

    def on_show(self):
        self.app.rm_on_show()
