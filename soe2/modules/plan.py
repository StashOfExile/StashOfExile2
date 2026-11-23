from . import Module


class GamePlan(Module):
    key, title, short, icon, kind = "plan", "League Plan", "Plan", "🎯", "tool"
    parent = None                      # UI overhaul: its own page (was under Overlay - it isn't an overlay setting)
    beta = True                        # 3.2.1 owner: beta until its full rework
    blurb = "Your league goals, in order. The app counts what it can see."

    def blurb_tip(self):
        return ("Next up is your first goal not done. It shows on the overlay, and as a reminder when you're back in "
                "town. Levels, acts, maps and boss runs come from the game's log. Net worth comes from Wealth, div an "
                "hour from Map Profit, Stock up from your Stockpile on Exchange Rates.")

    def build(self, body):
        self.app.build_game_plan(body).pack(fill="both", expand=True)

    def on_show(self):
        self.app.gp_fill()
