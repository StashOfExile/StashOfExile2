from . import Module
from ..config import PAGE_PC


class PriceCheck(Module):
    """2.80.0: one item at a time - its card with every filter, and the trade site's listings beside it."""
    key, title, icon = "pricecheck", PAGE_PC, "🔍"
    blurb = "Price the item under your mouse with Ctrl+D."

    def build(self, body):
        self.app.build_pc(body)
