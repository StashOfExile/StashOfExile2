from . import Module


class MoneyMakers(Module):
    key, title, short, icon, kind = "money", "Farming Strategies", "Strats", "🪙", "module"
    labs = True                     # 2.97.3 (feedback): a Labs feature - hidden while Labs is off (was beta: always shown)
    blurb = "Pick a way to farm, run it, see what it made."

    def build(self, body):
        self.app.build_money_window(body)

    def on_show(self):
        self.app.mm_on_show()
