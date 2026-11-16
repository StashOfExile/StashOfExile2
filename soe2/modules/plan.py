from . import Module


class GamePlan(Module):
    key, title, short, icon, kind = "plan", "League Plan", "Plan", "🎯", "tool"
    parent = None                      # UI overhaul: its own page (was under Overlay - it isn't an overlay setting)
    blurb = ("Your goals by phase, a stockpile to buy while it's cheap, your farm plan and a build lock - "
             "set it once, the overlay brings it back when it matters.")

    def build(self, body):
        self.app.build_game_plan(body).pack(fill="both", expand=True)

    def on_show(self):
        self.app.gp_fill()
