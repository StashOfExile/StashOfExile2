from . import Module


class Regex(Module):
    key, title, icon, kind = "regex", "Regex", "✱", "tool"
    blurb = "Stash search patterns for tablets, waystones, relics, jewels and gear (like poe2.re)."

    def build(self, body):
        self.app.build_regex_page(body)
