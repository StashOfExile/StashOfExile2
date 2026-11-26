from . import Module
from ..config import PAGE_CHECKS


class PriceChecks(Module):
    key, title, icon = "checks", PAGE_CHECKS, "⚖"
    parent = None                      # nav phase 1: its own row in Trade (2.80.0-UI overhaul: a child of Price Checks)
    blurb = "Price many items at once: hover each in game and press Ctrl+Alt+C, Manually Add."

    def build(self, body):
        self.app.build_checks(body)

    def blurb_tip(self):
        """The header's ⓘ: what the prices are made from (the real settings) and where that is set."""
        return self.app.bk_rules_tip()

    def blurb_click(self):
        self.app.settings_open("Price checking", "pc_bulk")
