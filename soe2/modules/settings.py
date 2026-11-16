from . import Module


class Settings(Module):
    key, title, icon, kind = "settings", "Settings", "⚙", "core"
    blurb = "Price checking, league, features, theme, keybinds, privacy and updates."

    def build(self, body):
        self.app.build_settings(body)
