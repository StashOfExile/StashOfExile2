from . import Module


class MapProfit(Module):
    """2.132.6 Overlay ↳ Map Profit (feedback: "a child under Overlay if you have map profit enabled ... a log by date
    ... with graphs and bars ... All Time, Daily, Hourly"; "above leaderboards, below map library")."""
    key, title, short, icon, kind = "mapprofit", "Map Profit", "Map Profit", "▲", "tool"
    parent = None                      # UI overhaul: its own page (was under Overlay - it isn't an overlay setting)
    blurb = ("What each map earned: one Look key press with your inventory open when you're back from it, priced by "
             "poe.ninja. On your PC only.")

    def shown(self):
        return self.app.mp_on()

    def build(self, body):
        self.app.build_map_profit(body)

    def on_show(self):
        self.app.mp_list_refresh()
