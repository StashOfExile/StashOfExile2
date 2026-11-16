from . import Module


class Insights(Module):
    key, title, short, icon, kind = "insights", "Market Insights", "Insights", "💎", "tool"
    parent = None                      # UI overhaul: its own page under Trade (was under Price Checks)
    blurb = "Your most valuable items, the top mods and the priciest listings seen - all from your price checks."

    def build(self, body):
        self.app.build_insights_window(body)

    def on_show(self):
        self.app.refresh_insights()
