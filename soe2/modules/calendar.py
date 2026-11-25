from . import Module


class Calendar(Module):
    """3.3.0 owner: Dashboard ↳ Calendar - leagues, Twitch Drops, events and races, plus reminders of your own."""
    key, title, short, icon, kind = "calendar", "Calendar", "Calendar", "📅", "tool"
    parent = "dashboard"
    blurb = "Leagues, Twitch Drops, events and races, plus reminders of your own."

    def build(self, body):
        self.app.build_calendar(body)

    def on_show(self):
        self.app.cal_refresh()
