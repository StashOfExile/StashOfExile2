from . import Module
from ..ratemods_page import INTRO, INTRO_RICH


class RateMods(Module):
    """Mod Lab, was Rate Mods. 2.120.0 (UX pass 2, feedback: the Rate mods window drew badly and sat in Privacy & community): its own page.
    Owner (Rate Mods redesign): in the Mods group - One at a Time (the sets on the left, a card on the right) and
    Table (many mods at once)."""
    key, title, short, icon, kind = "ratemods", "Mod Lab", "Mod Lab", "⭐", "tool"
    report_page = "ratemods"                # 3.3.0 owner: Report a Problem in its header
    parent = None                      # owner: its own row in Mods (was in Trade, a child of Price Checks before that)
    blurb = INTRO                      # owner: the page's one intro line, under its title (more in its ⓘ: blurb_tip)
    blurb_rich = INTRO_RICH            # owner, after 3.1.0: drawn bigger, key words bold in the accent color

    def blurb_tip(self):
        from ..ratemods_page import INTRO_TIP
        return INTRO_TIP

    def build(self, body):
        self.app.build_ratemods_page(body)

    def on_show(self):
        self.app.rm_on_show()
