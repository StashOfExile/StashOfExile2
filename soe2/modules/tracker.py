from . import Module


class Tracker(Module):
    # 2.44.0: "Overlays" (was Session tracker) - the Session timer, the Mechanic Helper, Notes and their Look in one
    # window. The key stays "tracker" (saved window places, older settings).
    # 2.59.0: "Overlay" - one screen, one window over the game
    # nav phase 2: one page with tabs - Helpers, On the Overlay, Look, Options (and Sessions, until Map Runs takes
    # them); Overlay Settings, its child page, is gone
    key, title, short, icon, kind = "tracker", "Overlay", "Overlay", "⏱", "utility"
    blurb = "The Overlay: its helpers, what it shows, its Layout and Style, and your sessions."

    def build(self, body):
        self.app.build_overlays_hub(body)

    def on_show(self):
        self.app.tracker_fill_history()

    def status(self):
        return self.app.tracker_status()
