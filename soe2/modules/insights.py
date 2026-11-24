from . import Module


class Insights(Module):
    key, title, short, icon, kind = "insights", "Market Insights", "Insights", "💎", "tool"
    parent = None                      # owner: its own page under Mods (was under Trade, Price Checks before that)
    blurb = "Your most valuable items and the priciest listings seen - all from your price checks."

    def build(self, body):
        self.app.build_insights_window(body)

    def on_show(self):
        self.app.refresh_insights()
